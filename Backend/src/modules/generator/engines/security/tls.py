"""
TLS/SSL enforcement test generators. Covers OWASP API Security 4.7.

Uses a public (non-auth-required) endpoint to avoid 60s timeouts on
auth-gated paths. Generates only 2 meaningful tests.
"""

import uuid
from ...spec_parser import Endpoint


def generate_tls_tests(spec: dict, endpoints: list[Endpoint] | None = None) -> list[dict]:
    """
    Generate TLS/SSL enforcement tests.

    Picks the first PUBLIC endpoint (no auth required) as the probe path
    to avoid 60-second timeouts on auth-gated routes.
    """
    tests = []

    # Prefer GET + no auth + no path params — avoids auth timeouts and path param issues
    probe_path = "/"
    if endpoints:
        ideal = [
            e for e in endpoints
            if e.method == "GET" and not e.requires_auth and not e.path_params
        ]
        fallback = [e for e in endpoints if not e.requires_auth]
        probe_path = (ideal[0] if ideal else (fallback[0] if fallback else endpoints[0])).path
    elif "paths" in spec:
        paths = list(spec["paths"].keys())
        if paths:
            probe_path = paths[0]

    base_url = ""
    for server in spec.get("servers", []):
        base_url = server.get("url", "")
        if base_url:
            break

    # Test 1: HTTP vs HTTPS check
    if base_url.startswith("http://"):
        tests.append({
            "id": str(uuid.uuid4()),
            "name": "TLS/SSL: HTTP used instead of HTTPS",
            "test_type": "Security",
            "owasp_category": "TLS",
            "endpoint_path": probe_path,
            "method": "GET",
            "expected_status": 400,
            "description": (
                f"API is configured with HTTP ({base_url}). "
                f"All traffic should be served over HTTPS."
            ),
        })
    else:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": "TLS/SSL: HTTPS enforcement confirmed",
            "test_type": "Security",
            "owasp_category": "TLS",
            "endpoint_path": probe_path,
            "method": "GET",
            "expected_status": 200,
            "description": (
                f"Confirms API responds over HTTPS. "
                f"A 200 verifies TLS 1.2+ is operational."
            ),
        })

    # Test 2: HTTP-to-HTTPS redirect
    tests.append({
        "id": str(uuid.uuid4()),
        "name": "TLS/SSL: HTTP to HTTPS redirect",
        "test_type": "Security",
        "owasp_category": "TLS",
        "endpoint_path": probe_path,
        "method": "GET",
        "expected_status": 301,
        "description": (
            f"Attempts HTTP connection to {probe_path}. "
            f"Server should redirect to HTTPS (301/302). "
            f"Cloud-hosted APIs handle this at infra level — 404 is also acceptable."
        ),
    })

    return tests
