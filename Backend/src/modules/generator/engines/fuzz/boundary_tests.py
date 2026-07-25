"""
Boundary value and schema-aware fuzz test generators.

Uses OpenAPI schema properties (enum, required, maxLength, type, format)
to generate intelligent fuzz tests:
  - Boundary values (0, -1, MAX_INT, empty arrays)
  - Missing required fields
  - Extra unexpected fields
  - Type mismatches
  - Malformed JSON
  - Nested object corruption
  - Enum violations
"""
import uuid
import json
from typing import Any
from ...spec_parser import Endpoint, get_expected_status


def _get_properties(schema: dict | None) -> dict[str, Any]:
    """Safely extract properties from a schema dict."""
    if not schema or not isinstance(schema, dict):
        return {}
    return schema.get("properties", {})


def _get_required_fields(schema: dict | None) -> list[str]:
    """Get required field names from schema."""
    if not schema or not isinstance(schema, dict):
        return []
    return schema.get("required", [])


def generate_boundary_value_tests(endpoint: Endpoint) -> list[dict]:
    """Generate tests with boundary values for numeric/string fields."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH") or not endpoint.body_schema:
        return tests

    properties = _get_properties(endpoint.body_schema)

    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string") if isinstance(field_schema, dict) else "string"

        if field_type in ("integer", "number"):
            boundary_values = [
                (0, "zero"),
                (-1, "negative"),
                (2147483647, "MAX_INT"),
                (-2147483648, "MIN_INT"),
                (9999999999999, "overflow"),
                (0.0001, "tiny float"),
            ]
            expected_err = get_expected_status(endpoint, 400)
            if expected_err:
                for val, desc in boundary_values[:3]:
                    tests.append({
                        "id": str(uuid.uuid4()),
                        "name": f"Boundary '{desc}' in '{field_name}'",
                        "test_type": "Fuzz",
                        "fuzz_type": "RANDOM_STRING",
                        "endpoint_path": endpoint.path,
                        "method": endpoint.method,
                        "headers": {"Content-Type": "application/json"},
                        "body": {field_name: val},
                        "query_params": {},
                        "expected_status": expected_err,
                        "expected_behavior": f"Should validate boundary value {desc}",
                        "description": f"Sends boundary value {desc} ({val}) in field '{field_name}'",
                    })

        elif field_type == "string":
            max_length = field_schema.get("maxLength") if isinstance(field_schema, dict) else None
            if max_length:
                expected_err = get_expected_status(endpoint, 400)
                if expected_err:
                    # Generate one char over the limit
                    over_length = "A" * (max_length + 10)
                    tests.append({
                        "id": str(uuid.uuid4()),
                        "name": f"Exceeds maxLength in '{field_name}'",
                        "test_type": "Fuzz",
                        "fuzz_type": "LONG_INPUT",
                        "endpoint_path": endpoint.path,
                        "method": endpoint.method,
                        "headers": {"Content-Type": "application/json"},
                        "body": {field_name: over_length},
                        "query_params": {},
                        "expected_status": expected_err,
                        "expected_behavior": f"Should reject input exceeding maxLength of {max_length}",
                        "description": f"Sends string exceeding maxLength ({max_length}) in '{field_name}'",
                    })

        elif field_type == "array":
            expected_err = get_expected_status(endpoint, 400)
            if expected_err:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Empty array in '{field_name}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "RANDOM_STRING",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {"Content-Type": "application/json"},
                    "body": {field_name: []},
                    "query_params": {},
                    "expected_status": expected_err,
                    "expected_behavior": "Should handle empty array",
                    "description": f"Sends empty array in '{field_name}'",
                })

    return tests


def generate_missing_required_tests(endpoint: Endpoint) -> list[dict]:
    """Generate tests that omit each required field one at a time."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH") or not endpoint.body_schema:
        return tests

    properties = _get_properties(endpoint.body_schema)
    required = _get_required_fields(endpoint.body_schema)

    if not required or not properties:
        return tests

    # Build a "valid" body with all required fields set to dummy values
    base_body = {}
    for field in required:
        field_schema = properties.get(field, {})
        field_type = field_schema.get("type", "string") if isinstance(field_schema, dict) else "string"
        if field_type == "string":
            base_body[field] = "test_value"
        elif field_type in ("integer", "number"):
            base_body[field] = 1
        elif field_type == "boolean":
            base_body[field] = True
        elif field_type == "array":
            base_body[field] = []
        elif field_type == "object":
            base_body[field] = {}

    # Omit each required field
    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for field in required:
            body = {k: v for k, v in base_body.items() if k != field}
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Missing required field '{field}'",
                "test_type": "Fuzz",
                "fuzz_type": "RANDOM_STRING",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {"Content-Type": "application/json"},
                "body": body,
                "query_params": {},
                "expected_status": expected_err,
                "expected_behavior": f"Should return {expected_err} for missing required field '{field}'",
                "description": f"Omits required field '{field}' from request body",
            })

    return tests


def generate_type_mismatch_tests(endpoint: Endpoint) -> list[dict]:
    """Generate tests with wrong types (string where int expected, etc.)."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH") or not endpoint.body_schema:
        return tests

    properties = _get_properties(endpoint.body_schema)

    type_mismatches = {
        "string": [42, True, [], {}],
        "integer": ["not_a_number", True, [], {}],
        "number": ["not_a_number", True, [], {}],
        "boolean": ["not_bool", 42, [], {}],
        "array": ["not_array", 42, True, {}],
        "object": ["not_object", 42, True, []],
    }

    for field_name, field_schema in list(properties.items())[:5]:
        field_type = field_schema.get("type", "string") if isinstance(field_schema, dict) else "string"
        mismatches = type_mismatches.get(field_type, [42, "wrong_type"])

        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            for mismatch_val in mismatches[:2]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Type mismatch in '{field_name}' (expected {field_type})",
                    "test_type": "Fuzz",
                    "fuzz_type": "RANDOM_STRING",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {"Content-Type": "application/json"},
                    "body": {field_name: mismatch_val},
                    "query_params": {},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should reject wrong type for '{field_name}'",
                    "description": f"Sends {type(mismatch_val).__name__} where {field_type} expected in '{field_name}'",
                })

    return tests


def generate_enum_violation_tests(endpoint: Endpoint) -> list[dict]:
    """Generate tests with values outside the allowed enum set."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH") or not endpoint.body_schema:
        return tests

    properties = _get_properties(endpoint.body_schema)

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            continue
        enum_values = field_schema.get("enum")
        if not enum_values:
            continue

        # Generate invalid values
        invalid_values = [
            "INVALID_ENUM_VALUE",
            "",
            "null",
            f"NOT_{enum_values[0]}" if enum_values else "INVALID",
        ]

        expected_err = get_expected_status(endpoint, 400)
        if expected_err:
            for invalid in invalid_values[:2]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Invalid enum '{invalid}' in '{field_name}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "RANDOM_STRING",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {"Content-Type": "application/json"},
                    "body": {field_name: invalid},
                    "query_params": {},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should reject invalid enum value (valid: {enum_values})",
                    "description": f"Sends invalid enum value '{invalid}' for field '{field_name}' (valid: {enum_values})",
                })

    return tests


def generate_extra_fields_test(endpoint: Endpoint) -> list[dict]:
    """Generate test with unexpected extra fields in the body."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH") or not endpoint.body_schema:
        return tests

    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Extra unexpected fields in body",
            "test_type": "Fuzz",
            "fuzz_type": "PAYLOAD_INJECTION",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "headers": {"Content-Type": "application/json"},
            "body": {
                "__proto__": {"isAdmin": True},
                "constructor": {"prototype": {"isAdmin": True}},
                "_internal_flag": True,
                "admin": True,
                "role": "superadmin",
            },
            "query_params": {},
            "expected_status": expected_err,
            "expected_behavior": "Should reject or ignore unexpected fields",
            "description": "Sends extra unexpected/dangerous fields in request body (prototype pollution attempt)",
        })

    return tests


def generate_malformed_json_tests(endpoint: Endpoint) -> list[dict]:
    """Generate tests with malformed JSON bodies."""
    tests = []
    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    # These will be sent as raw strings, not parsed JSON
    malformed_payloads = [
        ('{"key": "value"', "Unclosed JSON object"),
        ("{key: value}", "Unquoted keys"),
        ("", "Empty body"),
        ("null", "Literal null"),
        ("[]", "Empty array instead of object"),
    ]

    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for payload, desc in malformed_payloads[:3]:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Malformed JSON: {desc}",
                "test_type": "Fuzz",
                "fuzz_type": "PAYLOAD_INJECTION",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {"Content-Type": "application/json"},
                "body": payload,  # raw string, not dict
                "query_params": {},
                "expected_status": expected_err,
                "expected_behavior": f"Should return {expected_err} for malformed JSON",
                "description": f"Sends malformed JSON body: {desc}",
            })

    return tests
