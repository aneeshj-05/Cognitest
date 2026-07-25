"""
HTTP Verb Tampering test generators.

Covers OWASP API Security 4.6:
  - Sending unsupported HTTP methods to every endpoint (expect 405)
  - TRACE method probe (Cross-Site Tracing / XST)

REMOVED from stateless engine (require runtime header inspection):
  - X-HTTP-Method-Override tunnelling  → a server that correctly ignores the
    override header will return 200 for a GET, so expected_status=405 was always
    a false positive.  This can only be validated by inspecting the *response
    payload*, not just the status code.
  - _method query-param tunnelling     → same reasoning.
"""

import uuid
from ...spec_parser import Endpoint

_ALL_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}


def generate_verb_tampering_tests(endpoints: list[Endpoint]) -> list[dict]:
    """
    Generate HTTP verb tampering tests.

    For each declared path, probe the ONE most meaningful unsupported method
    and expect 405 Method Not Allowed.  Also probes TRACE (XST attack).

    Method-override header / _method query-param tests are intentionally
    excluded: a compliant server ignores those headers and returns the normal
    response code for the real method, making status-code comparison useless.
    """
    tests = []

    path_to_methods: dict[str, set[str]] = {}
    for ep in endpoints:
        path_to_methods.setdefault(ep.path, set()).add(ep.method.upper())

    seen_paths: set[str] = set()

    for ep in endpoints:
        path = ep.path
        declared_method = ep.method.upper()

        # ---------------------------------------------------------------
        # 1) Unsupported method — ONE per path
        # ---------------------------------------------------------------
        if path not in seen_paths:
            seen_paths.add(path)
            declared = path_to_methods[path]
            unsupported = _ALL_METHODS - declared - {"TRACE"}
            candidates = sorted(unsupported)[:1]
            for bad_method in candidates:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Verb Tampering: {bad_method} on {path} (only {', '.join(sorted(declared))} allowed)",
                    "test_type": "Security",
                    "endpoint_path": path,
                    "method": bad_method,
                    # Both 405 (method not allowed) and 404 (route not found for that method)
                    # are acceptable rejections. Many frameworks (Express, Next.js) return 404
                    # for unregistered route+method combos rather than 405.
                    # The test FAILS only on 200/201/2xx (method was accepted — real vulnerability).
                    "expected_status": 405,
                    "description": (
                        f"Sends an unsupported {bad_method} request to {path}. "
                        f"Should return 405 Method Not Allowed or 404 Not Found. "
                        f"A 2xx response would mean the server accepted an undeclared method."
                    ),
                })

        # ---------------------------------------------------------------
        # 2) TRACE method probe (XST attack — one per path)
        # ---------------------------------------------------------------
        if declared_method == "GET" and path not in {
            ep2.path for ep2 in endpoints if ep2.method.upper() == "TRACE"
        }:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"TRACE Method Probe on {path}",
                "test_type": "Security",
                "endpoint_path": path,
                "method": "TRACE",
                "expected_status": 405,
                "description": (
                    f"Sends TRACE {path}. The TRACE method echoes the request back and "
                    f"could expose authentication headers (Cross-Site Tracing / XST attack). "
                    f"Server should return 405 Method Not Allowed."
                ),
            })

    return tests
