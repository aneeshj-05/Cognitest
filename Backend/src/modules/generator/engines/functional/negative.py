"""
Negative test sub-generators — generates tests for invalid inputs,
missing parameters, wrong methods, etc.
"""
import uuid
from typing import Any
from ...spec_parser import Endpoint, get_expected_status


def generate_negative_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate negative test cases for an endpoint.
    
    Args:
        endpoint: Parsed endpoint object with path, method, body_schema, etc.
    
    Returns:
        List of test case dicts.
    """
    cases: list[dict[str, Any]] = []
    method = endpoint.method.upper()
    path = endpoint.path

    # Missing required fields (POST/PUT/PATCH with body)
    if method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        required = endpoint.body_schema.get("required", [])
        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            for field in required:
                cases.append({
                "id": str(uuid.uuid4()),
                "name": f"{method} {path} — missing '{field}' → {expected_err}",
                "test_type": "Negative",
                "endpoint_path": path,
                "method": method,
                "expected_status": expected_err,
                "description": f"Omits required field '{field}' from request body.",
                "category": "params",
                "fuzz_type": "MISSING_PARAMS",
            })

    # Wrong HTTP method
    wrong_methods = {"GET": "DELETE", "POST": "GET", "PUT": "POST", "DELETE": "PUT", "PATCH": "DELETE"}
    wrong = wrong_methods.get(method)
    if wrong:
        expected_method_err = get_expected_status(endpoint, 405)
        if expected_method_err:
            cases.append({
            "id": str(uuid.uuid4()),
            "name": f"{wrong} {path} — wrong method → {expected_method_err}",
            "test_type": "Negative",
            "endpoint_path": path,
            "method": wrong,
            "expected_status": expected_method_err,
            "description": f"Uses {wrong} instead of {method}.",
            "category": "params",
            "fuzz_type": "UNSUPPORTED_METHOD",
        })

    return cases
