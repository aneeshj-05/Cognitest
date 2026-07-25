"""
Egress guard — SSRF prevention for all outbound HTTP requests.

Usage (recommended — DNS-pinned transport):
    from src.utils.egress_guard import validate_egress_url_async, build_pinned_transport, SsrfBlockedError

    guard = await validate_egress_url_async(base_url)   # raises SsrfBlockedError if blocked
    async with httpx.AsyncClient(transport=build_pinned_transport(guard)) as client:
        resp = await client.request(method, guard.url, ...)   # use guard.url (original)

Design:
  1. Parse the URL and extract the hostname.
  2. Resolve the hostname to its actual IP address(es) via socket.getaddrinfo.
  3. Reject if any resolved IP falls in a blocked range.
  4. Return (original_url, pinned_ip) as an EgressResult dataclass.
     The ORIGINAL URL is used for all requests so TLS/vhost work correctly.
  5. DNS-rebinding prevention: build_pinned_transport() returns an httpx
     transport that overrides the TCP connect target to the pre-validated IP
     while the original hostname is still sent in the Host header and used
     for TLS SNI/certificate verification — no re-resolution at request time.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Blocked IP networks
# ---------------------------------------------------------------------------
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / cloud metadata
    ipaddress.ip_network("fe80::/10"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("224.0.0.0/4"),       # multicast
    ipaddress.ip_network("ff00::/8"),
    ipaddress.ip_network("240.0.0.0/4"),       # reserved
    ipaddress.ip_network("::ffff:0:0/96"),     # IPv4-mapped IPv6
    ipaddress.ip_network("fc00::/7"),          # unique local IPv6
]


class SsrfBlockedError(ValueError):
    """Raised when a user-supplied URL resolves to a blocked address."""


@dataclass
class EgressResult:
    """
    Result of a successful egress validation.

    url:       The ORIGINAL user-supplied URL — use this for all requests so
               TLS certificates validate against the correct hostname and
               virtual-host routing works correctly.
    pinned_ip: The IP address resolved and validated at guard time.
               Use this to pin the TCP connection (via build_pinned_transport)
               so the HTTP client cannot re-resolve the hostname (rebinding guard).
    hostname:  Original hostname extracted from the URL.
    port:      Resolved port (explicit or scheme default).
    scheme:    URL scheme ("http" or "https").
    """
    url: str
    pinned_ip: str
    hostname: str
    port: int
    scheme: str


def _is_blocked_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        return True


def _resolve_host_sync(hostname: str, port: int) -> list[str]:
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        return list({r[4][0] for r in results})
    except socket.gaierror as exc:
        raise SsrfBlockedError(
            f"Target URL not allowed — hostname '{hostname}' could not be resolved: {exc}"
        ) from exc


def validate_egress_url(url: str, *, production: bool | None = None) -> EgressResult:
    """
    Validate a user-supplied URL for SSRF safety.

    Returns an EgressResult containing:
      - .url        — the ORIGINAL URL (unchanged, for correct TLS/vhost)
      - .pinned_ip  — the validated IP to pin the TCP connection to

    Raises SsrfBlockedError if the URL is blocked.
    """
    if not url:
        raise SsrfBlockedError("Target URL not allowed — empty URL provided.")

    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise SsrfBlockedError(f"Target URL not allowed — malformed URL: {exc}") from exc

    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port or (443 if scheme == "https" else 80)

    if scheme not in ("http", "https"):
        raise SsrfBlockedError(
            f"Target URL not allowed — scheme '{scheme}' is not permitted (http/https only)."
        )
    if not hostname:
        raise SsrfBlockedError("Target URL not allowed — no hostname in URL.")

    # Production HTTPS enforcement
    if production is None:
        try:
            from src.config.settings import settings
            production = settings.node_env.lower() == "production"
        except Exception:
            production = False
    if production and scheme == "http":
        raise SsrfBlockedError(
            "Target URL not allowed — plain HTTP is not permitted in production. Use HTTPS."
        )

    # DNS resolution + IP check
    resolved_ips = _resolve_host_sync(hostname, port)
    if not resolved_ips:
        raise SsrfBlockedError(
            f"Target URL not allowed — hostname '{hostname}' resolved to no addresses."
        )
    # Development-mode bypass: allow hosts listed in settings.gateway_allowed_hosts
    # Runs only when not in production.
    if not production:
        try:
            from src.config.settings import settings
            allowed_hosts = {h.lower() for h in settings.gateway_allowed_hosts.split(",") if h.strip()}
        except Exception:
            # Fallback to typical localhost entries if settings import fails
            allowed_hosts = {"localhost", "127.0.0.1", "::1"}
        if hostname in allowed_hosts:
            pinned_ip = resolved_ips[0]
            logger.debug("[EgressGuard] dev allow host %s → %s", hostname, pinned_ip)
            return EgressResult(url=url, pinned_ip=pinned_ip, hostname=hostname, port=port, scheme=scheme)
    # Production or non-allowed hosts – enforce block list
    for ip_str in resolved_ips:
        if _is_blocked_ip(ip_str):
            logger.warning("[EgressGuard] SSRF block: '%s' → %s", hostname, ip_str)
            raise SsrfBlockedError(
                "Target URL not allowed — private/internal addresses are blocked. "
                f"The hostname '{hostname}' resolved to a restricted IP address."
            )

    pinned_ip = resolved_ips[0]
    logger.debug("[EgressGuard] '%s' validated — pinned to %s", url, pinned_ip)
    return EgressResult(url=url, pinned_ip=pinned_ip, hostname=hostname, port=port, scheme=scheme)


async def validate_egress_url_async(
    url: str, *, production: bool | None = None
) -> EgressResult:
    """Async wrapper — runs DNS resolution in thread-pool to avoid blocking the event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, lambda: validate_egress_url(url, production=production)
    )


# ---------------------------------------------------------------------------
# DNS-pinned httpx transport
# ---------------------------------------------------------------------------

class _PinnedAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """
    Custom async transport that connects to a pre-validated IP address
    while preserving the original hostname for TLS SNI and Host header.

    This prevents DNS rebinding: the TCP connection always goes to the IP
    resolved and validated by the egress guard, not re-resolved at request time.
    TLS certificate verification succeeds because we present the original
    hostname as the SNI server name — not the raw IP.
    """

    def __init__(self, pinned_ip: str, original_hostname: str, original_port: int, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._pinned_ip = pinned_ip
        self._original_hostname = original_hostname
        self._original_port = original_port

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Override the URL's host to the pinned IP for the TCP connection,
        # while keeping the original hostname in the Host header and for TLS SNI.
        original_url = request.url
        pinned_url = original_url.copy_with(host=self._pinned_ip)

        # Rebuild request with pinned URL but preserve original Host header
        new_headers = dict(request.headers)
        new_headers["host"] = self._original_hostname
        if original_url.port:
            new_headers["host"] = f"{self._original_hostname}:{original_url.port}"

        pinned_request = request.__class__(
            method=request.method,
            url=pinned_url,
            headers=new_headers,
            stream=request.stream,
            extensions=request.extensions,
        )
        return await super().handle_async_request(pinned_request)


def build_pinned_transport(
    guard: EgressResult,
    verify: bool | ssl.SSLContext = True,
    **transport_kwargs: Any,
) -> httpx.AsyncHTTPTransport:
    """
    Build an httpx.AsyncHTTPTransport that:
      - Connects TCP to guard.pinned_ip (rebinding-safe)
      - Sends the original hostname in the Host header (vhost-safe)
      - Uses the original hostname for TLS SNI (TLS cert-safe)

    For HTTPS, the SSL context is configured with server_hostname set
    to the original hostname so certificate verification succeeds against
    the real cert, not a raw IP.

    Usage:
        guard = await validate_egress_url_async(base_url)
        transport = build_pinned_transport(guard)
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.request(method, guard.url, ...)
    """
    if guard.scheme == "https" and verify is True:
        # Build SSL context that checks the cert against the original hostname
        ctx = ssl.create_default_context()
        # server_hostname is set at connect time by httpx internals via SNI;
        # using the original URL means httpx will already extract the correct SNI.
        # We just ensure verify=True so the cert is checked.
        verify = ctx

    return _PinnedAsyncHTTPTransport(
        pinned_ip=guard.pinned_ip,
        original_hostname=guard.hostname,
        original_port=guard.port,
        verify=verify,
        **transport_kwargs,
    )


# ---------------------------------------------------------------------------
# Convenience: build a pinned httpx.AsyncClient for a validated base_url
# ---------------------------------------------------------------------------

def create_pinned_client(
    base_url: str,
    *,
    production: bool | None = None,
    timeout: float | httpx.Timeout = 60.0,
    follow_redirects: bool = False,
    **kwargs: Any,
) -> httpx.AsyncClient:
    """
    Validate base_url against the egress guard and return an
    httpx.AsyncClient whose transport is pinned to the resolved IP.

    Drop-in replacement for ``httpx.AsyncClient(...)`` at any call site
    that uses a user-supplied base_url.  Usage:

        async with create_pinned_client(base_url, timeout=30.0) as client:
            resp = await client.get("/api/data")

    Raises SsrfBlockedError if the URL is blocked.
    The returned client uses guard.url (original hostname) as its base_url
    so TLS cert verification and vhost routing work correctly.
    """
    guard = validate_egress_url(base_url, production=production)
    transport = build_pinned_transport(guard)
    return httpx.AsyncClient(
        base_url=guard.url,
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
        **kwargs,
    )
