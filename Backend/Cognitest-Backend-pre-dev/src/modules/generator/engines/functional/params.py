"""
Query, header, cookie, and path parameter test generators.

Generates functional tests that validate parameter handling:
- Each query param with a valid value
- Each path param with a valid value
- Header-based parameters (Accept, Content-Type)
- Required vs optional parameter behavior
"""
import uuid
from typing import Any

from ...spec_parser import Endpoint, get_expected_status


def _sample_value_for_type(param_type: str) -> str:
    """Return a plausible sample value string for a given schema type."""
    type_map = {
        "string": "test_value",
        "integer": "42",
        "number": "3.14",
        "boolean": "true",
        "array": "item1,item2",
    }
    return type_map.get(param_type, "test_value")


def generate_param_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate parameter validation tests for an endpoint.

    Produces tests for query params, path params, and header params.
    """
    tests = []
    expected_ok = get_expected_status(endpoint, 200)
    if not expected_ok:
        return tests

    # --- Query parameter tests ---
    for param in endpoint.query_params:
        param_name = param.get("name", "unknown")
        param_type = param.get("type", "string")
        param_required = param.get("required", False)
        sample_val = _sample_value_for_type(param_type)

        # Valid query param value
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"{endpoint.method} {endpoint.path} — valid query param '{param_name}' → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "expected_status": expected_ok,
            "description": (
                f"Sends a valid value for query parameter '{param_name}' "
                f"(type: {param_type}). Expects {expected_ok}."
            ),
            "request_query": {param_name: sample_val},
            "assertions": [
                f"Status code is {expected_ok}",
                f"Query parameter '{param_name}' is accepted",
                f"Response reflects the effect of '{param_name}={sample_val}'",
            ],
        })

        # Wrong type for query param
        wrong_val = "not_a_number" if param_type in ("integer", "number") else ""
        if param_type in ("integer", "number"):
            expected_err = get_expected_status(endpoint, 400)
            if expected_err:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"{endpoint.method} {endpoint.path} — invalid type for query param '{param_name}' → {expected_err}",
                    "test_type": "Functional",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "expected_status": expected_err,
                    "description": (
                        f"Sends a non-{param_type} value ('{wrong_val}') for query parameter "
                        f"'{param_name}'. Should return {expected_err}."
                    ),
                    "request_query": {param_name: wrong_val},
                    "assertions": [
                        f"Status code is {expected_err}",
                        f"Error message indicates invalid type for '{param_name}'",
                    ],
                })

        # Required query param omitted
        if param_required:
            expected_err = get_expected_status(endpoint, 400)
            if expected_err:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"{endpoint.method} {endpoint.path} — missing required query param '{param_name}' → {expected_err}",
                    "test_type": "Functional",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "expected_status": expected_err,
                    "description": (
                        f"Omits required query parameter '{param_name}'. "
                        f"Should return {expected_err}."
                    ),
                    "assertions": [
                        f"Status code is {expected_err}",
                        f"Error message indicates missing required param '{param_name}'",
                    ],
                })

    # --- Path parameter tests ---
    for param in endpoint.path_params:
        # Valid path param
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"{endpoint.method} {endpoint.path} — valid path param '{param}' → {expected_ok}",
            "test_type": "Functional",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "expected_status": expected_ok,
            "description": (
                f"Sends a valid value for path parameter '{param}'. "
                f"Expects {expected_ok} with matching resource."
            ),
            "path_params": {param: "valid-test-id"},
            "assertions": [
                f"Status code is {expected_ok}",
                f"Resource matches path param '{param}'",
            ],
        })

        # Non-existent path param value
        expected_err = get_expected_status(endpoint, 404)
        if expected_err:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"{endpoint.method} {endpoint.path} — non-existent '{param}' returns {expected_err}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "expected_status": expected_err,
                "description": (
                    f"Sends a non-existent value for path parameter '{param}'. "
                    f"Expects {expected_err}."
                ),
                "path_params": {param: "nonexistent-id-99999"},
                "assertions": [
                    f"Status code is {expected_err}",
                    "Error message indicates resource not found",
                ],
            })

    # --- Header parameter tests ---
    # Accept header validation
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"{endpoint.method} {endpoint.path} — Accept: application/json → {expected_ok}",
        "test_type": "Functional",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "expected_status": expected_ok,
        "description": (
            f"Sends request with 'Accept: application/json' header. "
            f"Expects {expected_ok}."
        ),
        "request_headers": {"Accept": "application/json"},
        "assertions": [
            f"Status code is {expected_ok}",
            "Response Content-Type is application/json",
        ],
    })

    # Unsupported Accept header
    expected_err = get_expected_status(endpoint, 406)
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"{endpoint.method} {endpoint.path} — unsupported Accept header",
        "test_type": "Functional",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "expected_status": expected_err,
        "description": (
            f"Sends request with 'Accept: application/xml' (unsupported). "
            f"Should return {expected_err} or fall back to JSON."
        ),
        "request_headers": {"Accept": "application/xml"},
        "assertions": [
            f"Status code is {expected_err} or response falls back to JSON",
        ],
    })

    return tests
