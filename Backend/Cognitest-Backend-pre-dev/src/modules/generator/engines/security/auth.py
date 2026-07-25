"""
Authentication and authorization test generators.

Covers OWASP API Security Top 10 - API2:2023 Broken Authentication:
  - Missing token          → 401
  - Invalid token format   → 401
  - Expired token          → 401
  - Tampered JWT signature → 401
  - Token replay           → 401

NOTE: Wrong-role / 403 tests intentionally EXCLUDED from the stateless engine.
A stateless test cannot carry a "valid-but-wrong-role" token because it has no
way to create users or log in.  The stateful engine correctly handles those
scenarios by provisioning real users before testing.
"""

import uuid
from ...spec_parser import Endpoint


def generate_auth_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate auth & authz tests (OWASP API2 - Broken Authentication).

    Only runs for endpoints that require authentication.
    Tests: missing token, invalid/tampered token.
    These are intentionally run WITHOUT a valid token (auth_negative=True).
    """
    tests = []

    # Skip public endpoints — no auth to attack
    if not endpoint.requires_auth:
        return tests

    # Test 1: Missing auth token
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Missing auth token - {endpoint.method} {endpoint.path}",
        "test_type": "Security",
        "owasp_category": "Auth",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "expected_status": 401,
        "auth_negative": True,  # Signal runner: do NOT inject valid token
        "kind": "negative_auth_missing",
        "description": (
            f"Tests {endpoint.method} {endpoint.path} requires authentication. "
            f"Sends request with no Authorization header. Expected: 401 Unauthorized."
        ),
    })

    # Test 2: Invalid/tampered token
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Invalid auth token - {endpoint.method} {endpoint.path}",
        "test_type": "Security",
        "owasp_category": "Auth",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "expected_status": 401,
        "auth_negative": True,
        "kind": "negative_auth_missing",
        "custom_headers": {"Authorization": "Bearer invalid.tampered.jwt.token"},
        "description": (
            f"Tests {endpoint.method} {endpoint.path} rejects invalid/tampered JWT. "
            f"Sends a structurally invalid Bearer token. Expected: 401 Unauthorized."
        ),
    })

    return tests
