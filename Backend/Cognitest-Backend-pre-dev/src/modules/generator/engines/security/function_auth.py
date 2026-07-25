"""
Broken Function Level Authorization test generators.

Covers OWASP API Security Top 10 - API5:2023.

BOLA (API1) = User B accessing User A's *object* (same role, different owner).
Function-Level Auth (API5) = Regular user calling *admin/privileged functions*.

These are stateful — User B's token (a regular user) is sent to endpoints
that are admin-only or privileged. The server must return 403, not 200.

Detection heuristics for admin/privileged endpoints:
  - Path contains: /admin, /internal, /manage, /superuser, /staff, /system
  - Method is DELETE/PUT on a resource the spec marks as admin-only
  - Endpoint has no security requirement but sits under an admin path
"""
import uuid
from ...spec_parser import Endpoint

_ADMIN_PATH_KEYWORDS = {
    "admin", "internal", "manage", "management", "superuser",
    "staff", "system", "privileged", "root", "sudo",
}


def generate_function_level_auth_tests(endpoints: list[Endpoint]) -> list[dict]:
    """
    Generate function-level authorization tests for admin/privileged endpoints.

    Uses User B's token (regular user) against endpoints that appear to be
    admin-only based on path keywords or HTTP method semantics.
    """
    tests = []
    seen_paths: set[tuple[str, str]] = set()

    for ep in endpoints:
        path_lower = ep.path.lower()
        is_admin_path = any(kw in path_lower for kw in _ADMIN_PATH_KEYWORDS)

        if not is_admin_path:
            continue

        key = (ep.path, ep.method)
        if key in seen_paths:
            continue
        seen_paths.add(key)

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Function-Level AuthZ: regular user on {ep.method} {ep.path}",
            "test_type": "Security",
            "owasp_category": "FunctionAuth",
            "endpoint_path": ep.path,
            "method": ep.method,
            "expected_status": 403,
            "requires_stateful": True,
            "description": (
                f"Sends User B's regular-user token to the privileged endpoint "
                f"{ep.method} {ep.path}. "
                f"Server must return 403 Forbidden. "
                f"A 200/201 means a regular user can perform admin actions — "
                f"a Broken Function Level Authorization vulnerability (OWASP API5)."
            ),
        })

    return tests
