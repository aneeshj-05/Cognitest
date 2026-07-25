"""
Injection attack test generators.

Covers OWASP API Security Top 10 - API1:2023 / API3:2023:
  - SQL Injection
  - NoSQL Injection (MongoDB operators)
  - XSS
  - Command Injection

Generates tests for ALL endpoints that:
  - Accept a body (POST/PUT/PATCH) with a schema, OR have query params (GET/DELETE)
  - Auth-required endpoints get token_a injected during execution so the payload
    reaches the business logic layer. If token_a is unavailable, the test is
    marked inconclusive (401 response) rather than a false failure.
"""

import uuid
from ...spec_parser import Endpoint

_INJECTION_PAYLOADS = {
    "sql": ("' OR 1=1 --", "SQL Injection"),
    "nosql": ('{"$gt": ""}', "NoSQL Injection"),
    "xss": ("<script>alert(1)</script>", "XSS Injection"),
    "cmd": ("; cat /etc/passwd", "Command Injection"),
}


def generate_injection_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate one injection test per endpoint that can actually receive a payload.

    Skips:
      - Endpoints with no body schema AND no query params (nothing to inject into)

    Auth-required endpoints are included — token_a is injected at execution time
    so the payload reaches the business logic layer.
    """

    has_body = endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema
    has_query = endpoint.method in ("GET", "DELETE") and endpoint.query_params
    has_path_params = bool(endpoint.path_params)

    if not has_body and not has_query and not has_path_params:
        return []

    tests = []
    for payload_type, (payload, label) in _INJECTION_PAYLOADS.items():
        if has_body:
            props = endpoint.body_schema.get("properties", {})
            body = {}
            for field, schema in props.items():
                field_type = schema.get("type", "string")
                body[field] = "' OR 1=1" if field_type in ("integer", "number") else payload
            extra = {"request_body": body}
        elif has_query:
            extra = {"request_query": {p["name"]: payload for p in endpoint.query_params}}
        else:
            extra = {"path_params": {param: payload for param in endpoint.path_params}}

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"{label}: {endpoint.method} {endpoint.path}",
            "test_type": "Security",
            "owasp_category": "Injection",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "expected_status": 400,
            "requires_auth": endpoint.requires_auth,
            **extra,
            "description": (
                f"Tests {endpoint.method} {endpoint.path} for {label} vulnerabilities. "
                f"Server must reject with 4xx, not 500 (crash) or 200 (accepted)."
            ),
        })

    return tests
