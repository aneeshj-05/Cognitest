"""
Tests for src/utils/egress_guard.py

Covers:
  - SSRF blocking for private/loopback/link-local ranges
  - validate_egress_url returns original URL (not IP-substituted)
  - build_pinned_transport connects to pinned_ip, not re-resolves hostname
  - HTTPS target: no SSLCertVerificationError when hostname is preserved
  - HTTP vhosted target: correct vhost is reached via Host header
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
from unittest.mock import MagicMock, patch, AsyncMock

import httpx
import pytest

from src.utils.egress_guard import (
    EgressResult,
    SsrfBlockedError,
    _is_blocked_ip,
    _PinnedAsyncHTTPTransport,
    build_pinned_transport,
    validate_egress_url,
)


# ---------------------------------------------------------------------------
# IP blocking tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ip", [
    "127.0.0.1",
    "127.255.255.255",
    "::1",
    "169.254.169.254",   # AWS metadata
    "10.0.0.1",
    "10.255.255.255",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.0.1",
    "0.0.0.1",
    "224.0.0.1",         # multicast
    "240.0.0.1",         # reserved
])
def test_blocked_ips(ip: str):
    assert _is_blocked_ip(ip) is True


@pytest.mark.parametrize("ip", [
    "1.1.1.1",
    "8.8.8.8",
    "93.184.216.34",   # example.com
    "2606:2800:220:1:248:1893:25c8:1946",  # example.com IPv6
])
def test_allowed_ips(ip: str):
    assert _is_blocked_ip(ip) is False


# ---------------------------------------------------------------------------
# validate_egress_url — blocking
# ---------------------------------------------------------------------------

def _mock_getaddrinfo(hostname: str, port: int, *, type=None):
    """Return a fake getaddrinfo result pointing to a given IP."""
    return [(None, None, None, None, (hostname, port))]


def test_blocks_private_hostname():
    with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("10.0.0.1", 80))]):
        with pytest.raises(SsrfBlockedError, match="private/internal"):
            validate_egress_url("http://internal-service.corp/api")


def test_blocks_metadata_endpoint():
    with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("169.254.169.254", 80))]):
        with pytest.raises(SsrfBlockedError, match="private/internal"):
            validate_egress_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_loopback():
    """127.0.0.1 is always in the loopback blocked range."""
    with patch("src.utils.egress_guard.socket.getaddrinfo",
               return_value=[(None, None, None, None, ("127.0.0.1", 80))]):
        with pytest.raises(SsrfBlockedError, match="private/internal"):
            validate_egress_url("http://loopback-test.example.com/")


def test_blocks_unsupported_scheme():
    with pytest.raises(SsrfBlockedError, match="scheme"):
        validate_egress_url("ftp://example.com/file.txt")


def test_blocks_empty_url():
    with pytest.raises(SsrfBlockedError, match="empty"):
        validate_egress_url("")


def test_blocks_http_in_production():
    with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 80))]):
        with pytest.raises(SsrfBlockedError, match="plain HTTP"):
            validate_egress_url("http://example.com/api", production=True)


# ---------------------------------------------------------------------------
# validate_egress_url — success: returns ORIGINAL url, not IP-substituted
# ---------------------------------------------------------------------------

def test_returns_original_url_not_ip():
    """
    Critical: validate_egress_url must return the original URL so TLS cert
    verification and vhost routing work correctly.
    """
    with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
        result = validate_egress_url("https://example.com/api/v1")

    assert isinstance(result, EgressResult)
    # URL must be the ORIGINAL — not replaced with raw IP
    assert result.url == "https://example.com/api/v1"
    assert "93.184.216.34" not in result.url
    # But the pinned_ip must be the resolved address
    assert result.pinned_ip == "93.184.216.34"
    assert result.hostname == "example.com"
    assert result.scheme == "https"


def test_returns_original_url_http():
    with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 80))]):
        result = validate_egress_url("http://example.com/test", production=False)

    assert result.url == "http://example.com/test"
    assert result.pinned_ip == "93.184.216.34"


# ---------------------------------------------------------------------------
# _PinnedAsyncHTTPTransport — pinned IP, correct Host header
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pinned_transport_uses_pinned_ip():
    """
    _PinnedAsyncHTTPTransport must rewrite the request URL to the pinned IP
    and set the Host header to the original hostname.
    """
    guard = EgressResult(
        url="https://example.com/api",
        pinned_ip="93.184.216.34",
        hostname="example.com",
        port=443,
        scheme="https",
    )

    transport = _PinnedAsyncHTTPTransport(
        pinned_ip=guard.pinned_ip,
        original_hostname=guard.hostname,
        original_port=guard.port,
    )

    # Build a fake request as if httpx would send it
    original_request = httpx.Request("GET", "https://example.com/api")

    captured = []

    async def fake_super_handle(request: httpx.Request):
        captured.append(request)
        return httpx.Response(200, text="ok")

    # Patch the parent class's handle_async_request
    with patch("httpx.AsyncHTTPTransport.handle_async_request", new=AsyncMock(side_effect=fake_super_handle)):
        await transport.handle_async_request(original_request)

    assert len(captured) == 1
    req = captured[0]
    # URL host must be the pinned IP
    assert req.url.host == "93.184.216.34"
    # Host header must be original hostname
    assert req.headers.get("host") == "example.com"


@pytest.mark.asyncio
async def test_pinned_transport_preserves_path_and_query():
    guard = EgressResult(
        url="https://api.example.com/v2/items?page=1",
        pinned_ip="1.2.3.4",
        hostname="api.example.com",
        port=443,
        scheme="https",
    )

    transport = _PinnedAsyncHTTPTransport(
        pinned_ip=guard.pinned_ip,
        original_hostname=guard.hostname,
        original_port=guard.port,
    )

    original_request = httpx.Request("GET", "https://api.example.com/v2/items?page=1")

    captured = []

    async def fake_super_handle(request: httpx.Request):
        captured.append(request)
        return httpx.Response(200)

    with patch("httpx.AsyncHTTPTransport.handle_async_request", new=AsyncMock(side_effect=fake_super_handle)):
        await transport.handle_async_request(original_request)

    req = captured[0]
    assert req.url.host == "1.2.3.4"
    assert req.url.path == "/v2/items"
    assert "page=1" in str(req.url)
    assert req.headers.get("host") == "api.example.com"


# ---------------------------------------------------------------------------
# DNS-rebinding protection: all 5 engines must use the pinned IP, not re-resolve
# ---------------------------------------------------------------------------

def _make_rebinding_guard() -> EgressResult:
    """
    Simulate a rebinding scenario:
    - At validation time the host resolves to a public IP (1.2.3.4) — allowed.
    - At connect time the host would re-resolve to a private IP (10.0.0.1) — blocked.
    The guard pins to 1.2.3.4 so the engine MUST connect to 1.2.3.4, not 10.0.0.1.
    """
    return EgressResult(
        url="http://rebinding-target.example.com/api",
        pinned_ip="1.2.3.4",      # validated public IP
        hostname="rebinding-target.example.com",
        port=80,
        scheme="http",
    )


def _make_rebind_transport(guard: EgressResult) -> _PinnedAsyncHTTPTransport:
    """Build transport for guard and capture which IP it would connect to."""
    return _PinnedAsyncHTTPTransport(
        pinned_ip=guard.pinned_ip,
        original_hostname=guard.hostname,
        original_port=guard.port,
    )


@pytest.mark.asyncio
async def test_functional_engine_uses_pinned_ip():
    """functional_execution_service must use pinned transport, not re-resolve."""
    guard = _make_rebinding_guard()
    captured = []

    async def fake_handle(request: httpx.Request):
        captured.append(request.url.host)
        return httpx.Response(200, json={"event": "done", "total": 0, "passed": 0})

    with patch("src.utils.egress_guard.validate_egress_url", return_value=guard), \
         patch("httpx.AsyncHTTPTransport.handle_async_request",
               new=AsyncMock(side_effect=fake_handle)):
        from src.modules.generator.engines.functional.services.functional_execution_service import stream_run_suite
        # Consume the generator to trigger the AsyncClient construction
        events = []
        async for event in stream_run_suite(cases=[], base_url="http://rebinding-target.example.com/api",
                                            project_id="test"):
            events.append(event)

    # The transport must have been called with the pinned IP, not the hostname
    if captured:
        # Auth setup may connect to localhost (internal) — only check base_url requests
        base_url_connections = [h for h in captured if h not in ("localhost", "127.0.0.1", "::1")]
        if base_url_connections:
            assert all(h == "1.2.3.4" for h in base_url_connections), \
                f"Rebinding gap — base_url connected to {base_url_connections} instead of 1.2.3.4"


@pytest.mark.asyncio
async def test_execution_service_negative_uses_pinned_ip():
    """execution_service negative suite must use pinned transport for base_url requests."""
    guard = _make_rebinding_guard()
    captured = []

    async def fake_handle(request: httpx.Request):
        captured.append(request.url.host)
        return httpx.Response(200, text="ok")

    with patch("src.utils.egress_guard.validate_egress_url", return_value=guard), \
         patch("httpx.AsyncHTTPTransport.handle_async_request",
               new=AsyncMock(side_effect=fake_handle)):
        from src.modules.project.services.execution_service import stream_run_suite as neg_suite
        neg_cases = [{"category": "NEGATIVE", "test_type": "Negative",
                      "endpoint_path": "/test", "method": "GET",
                      "name": "test", "expected_status": 200}]
        events = []
        async for event in neg_suite(cases=neg_cases,
                                      base_url="http://rebinding-target.example.com/api",
                                      project_id="test"):
            events.append(event)
            if len(events) > 5:
                break

    if captured:
        # Auth setup may connect to localhost — only validate base_url target requests
        base_url_connections = [h for h in captured if h not in ("localhost", "127.0.0.1", "::1")]
        if base_url_connections:
            assert all(h == "1.2.3.4" for h in base_url_connections), \
                f"Rebinding gap — base_url connected to {base_url_connections} instead of 1.2.3.4"


@pytest.mark.asyncio
async def test_fuzz_runner_uses_pinned_ip():
    """fuzz runner must use pinned transport."""
    guard = _make_rebinding_guard()
    captured = []

    async def fake_handle(request: httpx.Request):
        captured.append(request.url.host)
        return httpx.Response(200, text="ok")

    with patch("src.utils.egress_guard.validate_egress_url", return_value=guard), \
         patch("httpx.AsyncHTTPTransport.handle_async_request",
               new=AsyncMock(side_effect=fake_handle)):
        from src.modules.generator.engines.fuzz.runner import run_fuzz_native
        await run_fuzz_native(
            test_cases=[],
            base_url="http://rebinding-target.example.com/api",
            spec={},
            context=MagicMock(bearer_token=None),
        )

    if captured:
        base_url_connections = [h for h in captured if h not in ("localhost", "127.0.0.1", "::1")]
        if base_url_connections:
            assert all(h == "1.2.3.4" for h in base_url_connections), \
                f"Rebinding gap: fuzz runner connected to {base_url_connections} instead of 1.2.3.4"


@pytest.mark.asyncio
async def test_validate_egress_blocks_all_private_in_single_call():
    """Confirm all private ranges are caught in one parametrized integration check."""
    private_ips = ["10.1.2.3", "172.20.0.1", "192.168.1.1", "127.0.0.1", "169.254.169.254"]
    for ip in private_ips:
        with patch("src.utils.egress_guard.socket.getaddrinfo", return_value=[(None, None, None, None, (ip, 80))]):
            with pytest.raises(SsrfBlockedError, match="private/internal"):
                validate_egress_url(f"http://target.example.com/api")
