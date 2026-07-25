"""
Long/oversized input fuzz test generators.
Generates tests with extremely long strings and oversized payloads.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


def generate_long_input_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate oversized input fuzz tests.
    Tests buffer overflow, DoS, and size limit handling.
    """
    tests = []

    long_payloads = [
        ("1K chars", "A" * 1000),
        ("10K chars", "B" * 10000),
        ("100K chars", "C" * 100000),
        ("Repeated JSON key", '{"a":' * 500 + '"x"' + '}' * 500),
    ]

    # Fuzz query params with long strings
    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for param in endpoint.query_params[:2]:
            for label, payload in long_payloads[:2]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Long input ({label}) in query param '{param['name']}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "LONG_INPUT",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {param["name"]: payload},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should reject oversized input (Expected {expected_err})",
                    "description": f"Sends {label} string in query param to test size limits",
                })

    # Fuzz body with oversized payloads
    if endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            properties = endpoint.body_schema.get("properties", {})
            for field_name, field_schema in list(properties.items())[:2]:
                if field_schema.get("type") == "string":
                    for label, payload in long_payloads[:3]:
                        tests.append({
                            "id": str(uuid.uuid4()),
                            "name": f"Long input ({label}) in body field '{field_name}'",
                            "test_type": "Fuzz",
                            "fuzz_type": "LONG_INPUT",
                            "endpoint_path": endpoint.path,
                            "method": endpoint.method,
                            "headers": {"Content-Type": "application/json"},
                            "body": {field_name: payload},
                            "query_params": {},
                            "expected_status": expected_body_err,
                            "expected_behavior": f"Should not crash, should reject (Expected {expected_body_err})",
                            "description": f"Sends oversized ({label}) body to test buffer handling",
                        })

    # Oversized raw body (regardless of schema)
    if endpoint.method in ("POST", "PUT", "PATCH"):
        expected_size_err = get_expected_status(endpoint, 413)
        if expected_size_err:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Oversized raw body (50KB) to {endpoint.method} {endpoint.path}",
                "test_type": "Fuzz",
                "fuzz_type": "LONG_INPUT",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {"Content-Type": "application/json"},
                "body": {"data": "X" * 50000},
                "query_params": {},
                "expected_status": expected_size_err,
                "expected_behavior": f"Should return {expected_size_err} Payload Too Large",
                "description": "Sends a 50KB payload to test body size limits",
            })

    return tests
