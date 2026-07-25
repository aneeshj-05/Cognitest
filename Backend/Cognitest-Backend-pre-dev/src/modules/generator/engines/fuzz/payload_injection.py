"""
Payload injection fuzz test generators.
Generates tests with JSON injection, malformed bodies, and content-type mismatch.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


def generate_payload_injection_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate payload injection fuzz tests.
    Tests malformed JSON, type confusion, and content-type mismatch.
    """
    tests = []

    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    # Malformed JSON bodies
    malformed_payloads = [
        ("Unclosed brace", '{"key": "value"'),
        ("Trailing comma", '{"key": "value",}'),
        ("Single quotes", "{'key': 'value'}"),
        ("No quotes on key", '{key: "value"}'),
        ("XML instead of JSON", '<?xml version="1.0"?><root><key>value</key></root>'),
        ("Empty body", ""),
        ("Just null", "null"),
        ("Just array", "[]"),
        ("Nested deep", '{"a":' * 100 + '1' + '}' * 100),
    ]

    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for label, payload in malformed_payloads:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Payload injection ({label}) to {endpoint.method} {endpoint.path}",
                "test_type": "Fuzz",
                "fuzz_type": "PAYLOAD_INJECTION",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {"Content-Type": "application/json"},
                "body": payload,  # raw string, not dict — intentionally malformed
                "query_params": {},
                "expected_status": expected_err,
                "expected_behavior": f"Should return {expected_err} Bad Request for malformed payload",
                "description": f"Sends malformed payload ({label}) to test JSON parser robustness",
            })

    # Content-type mismatch
    content_type_mismatches = [
        ("text/plain", '{"key": "value"}'),
        ("application/xml", '{"key": "value"}'),
        ("multipart/form-data", '{"key": "value"}'),
        ("application/json", "not json at all"),
    ]

    expected_ct_err = get_expected_status(endpoint, 400)
    if expected_ct_err:
        for ct, body in content_type_mismatches:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Content-Type mismatch ({ct}) to {endpoint.method} {endpoint.path}",
                "test_type": "Fuzz",
                "fuzz_type": "PAYLOAD_INJECTION",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {"Content-Type": ct},
                "body": body,
                "query_params": {},
                "expected_status": expected_ct_err,
                "expected_behavior": f"Should reject or handle content-type mismatch (Expected {expected_ct_err})",
                "description": f"Sends body with mismatched Content-Type: {ct}",
            })

    # Type confusion in body fields
    if endpoint.body_schema:
        properties = endpoint.body_schema.get("properties", {})
        type_confusion = [
            ("array instead of string", ["a", "b", "c"]),
            ("number instead of string", 99999),
            ("boolean instead of string", True),
            ("object instead of string", {"nested": "object"}),
            ("null instead of string", None),
        ]
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            for field_name, field_schema in list(properties.items())[:2]:
                for label, value in type_confusion:
                    tests.append({
                        "id": str(uuid.uuid4()),
                        "name": f"Type confusion ({label}) in '{field_name}'",
                        "test_type": "Fuzz",
                        "fuzz_type": "PAYLOAD_INJECTION",
                        "endpoint_path": endpoint.path,
                        "method": endpoint.method,
                        "headers": {"Content-Type": "application/json"},
                        "body": {field_name: value},
                        "query_params": {},
                        "expected_status": expected_body_err,
                        "expected_behavior": f"Should validate types and reject (Expected {expected_body_err})",
                        "description": f"Sends {label} in field '{field_name}' to test type validation",
                    })

    return tests
