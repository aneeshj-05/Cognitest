"""
BOLA (Broken Object-Level Authorization) test generators.

Covers OWASP API Security Top 10 - API1:2023 BOLA/IDOR.

These tests are tagged ``requires_stateful: true`` because they need a real
authenticated user (User B) trying to access User A's owned resources.
Without a valid token the server always returns 401 — making it impossible
to tell whether the *authorization* layer is protecting resources correctly.

The runner in ``router.py`` detects these tags, creates two test users
(User A as resource owner, User B as attacker), and runs tests with
User B's token against User A's resources.

Dynamic IDs:
  Path param placeholders like ``{id}`` are intentionally left as-is.
  The runtime replaces them with real resource IDs created during stateful
  setup using the ``exec_context`` dict (key = param name).
"""
import uuid
from ...spec_parser import Endpoint


def generate_bola_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate BOLA tests for endpoints with path ID parameters.

    All tests are marked ``requires_stateful: True`` so the unified runner
    knows to execute them with a real user-B token against user-A's resource.

    Path parameter placeholders are kept as ``{param}`` — they will be
    dynamically resolved to the actual resource ID created during setUp.
    """
    tests = []

    if not endpoint.path_params:
        return tests

    for param in endpoint.path_params:
        # The runner will fill {param} with the real resource_id_a from User A's setup
        # Test 1: Attacker (User B) tries to access User A's resource
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"BOLA: Unauthorized access to {endpoint.method} {endpoint.path}",
            "test_type": "Security",
            "owasp_category": "BOLA",
            "endpoint_path": endpoint.path,  # Keep {param} — runner resolves it
            "method": endpoint.method,
            "expected_status": 403,
            "requires_stateful": True,
            # Context keys the runner will use to substitute the path param
            "bola_path_param": param,
            "description": (
                f"Uses User B's real token to access a resource owned by User A via '{param}'. "
                f"Server must return 403 Forbidden, not 200. "
                f"BOLA vulnerability if the server allows cross-user access."
            ),
        })

        # Test 2: Mutating endpoints — attacker tries to modify/delete User A's resource
        if endpoint.method in ("DELETE", "PUT", "PATCH"):
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"BOLA: Cross-user modification - {endpoint.method} {endpoint.path}",
                "test_type": "Security",
                "owasp_category": "BOLA",
                "endpoint_path": endpoint.path,  # Keep {param} — runner resolves it
                "method": endpoint.method,
                "expected_status": 403,
                "requires_stateful": True,
                "bola_path_param": param,
                "description": (
                    f"Sends User B's token to modify/delete User A's resource via '{param}'. "
                    f"Should return 403 Forbidden — BOLA vulnerability if 200 is returned."
                ),
            })

    return tests
