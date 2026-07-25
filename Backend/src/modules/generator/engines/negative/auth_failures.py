""" 
Negative test generator — Authentication Failures.

For endpoints that declare ``security``, generates tests with:
  - Missing Authorization header
  - Invalid / malformed Bearer token
  - Expired-style garbage JWT

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
import uuid
import re
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType

def _resolve_path(path: str) -> str:
    """Replaces literal path parameters like {id} with safe strings to prevent TCP drops."""
    if "{" not in path:
        return path
        
    def replace_param(match):
        return generate_fake_id(match.group(1))
        
    return re.sub(r"\{([^}]+)\}", replace_param, path)


def generate_fake_id(param_name: str) -> str:
    if "uuid" in str(param_name).lower():
        return "ffffffff-ffff-ffff-ffff-ffffffffffff"
    return "999999999"


def generate_auth_failure_tests(endpoint: Endpoint) -> list[dict]:
    tests: list[dict] = []

    if not endpoint.requires_auth:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status_missing = get_expected_status(endpoint, 401)
    resolved_status_invalid = get_expected_status(endpoint, 401)

    # If the spec defines neither 401 nor 403, skip auth failure tests
    if resolved_status_missing is None and resolved_status_invalid is None:
        return tests

    # FIX: Resolve the path so it doesn't contain illegal { } characters
    safe_path = _resolve_path(endpoint.path)

    # 1. Missing Authorization header entirely
    if resolved_status_missing is not None:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Missing auth token - {endpoint.method} {safe_path}",
            "mutation_type": MutationType.AUTH_MISSING,
            "auth_type": "missing",
            "expected_status": [resolved_status_missing],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "AUTH_FAILURE",
            "endpoint_path": safe_path,
            "method": endpoint.method,
            "description": f"Sends request without Auth header. API should return {resolved_status_missing}.",
            "request_data": None,
            "target_field": None,
            "requires_auth": True,
        })

    # 2. Invalid / malformed Bearer token
    if resolved_status_invalid is not None:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Invalid auth token - {endpoint.method} {safe_path}",
            "mutation_type": MutationType.AUTH_INVALID,
            "auth_type": "invalid",
            "expected_status": [resolved_status_invalid],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "AUTH_FAILURE",
            "endpoint_path": safe_path,
            "method": endpoint.method,
            "description": "Sends structurally valid but cryptographically invalid Bearer token.",
            "request_data": None,
            "target_field": None,
            "requires_auth": True,
        })

    # 3. Expired-style JWT
    if resolved_status_invalid is not None:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Expired auth token - {endpoint.method} {safe_path}",
            "mutation_type": MutationType.AUTH_INVALID,
            "auth_type": "expired",
            "expected_status": [resolved_status_invalid],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "AUTH_FAILURE",
            "endpoint_path": safe_path,
            "method": endpoint.method,
            "description": "Sends a JWT with an expired timestamp.",
            "request_data": None,
            "target_field": None,
            "requires_auth": True,
        })

    return tests
