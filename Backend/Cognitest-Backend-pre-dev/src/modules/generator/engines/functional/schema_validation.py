"""
JSON/XML schema validation test generators.

Generates tests that verify API responses conform to their declared schema:
- Required fields are present
- Field types match the schema
- Content-Type header is correct
- Required vs optional body fields on requests
"""
import uuid
from typing import Any

from ...spec_parser import Endpoint, get_expected_status
from src.modules.generator.services.data_provider import data_provider


def generate_schema_validation_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate schema validation tests for an endpoint.

    Validates that:
    - Response contains all declared fields
    - Response field types match schema
    - Content-Type is application/json
    - Required request body fields are enforced
    """
    tests = []

    # Pre-generate a valid request body for any positive tests
    valid_body = {}
    if endpoint.body_schema and endpoint.method in ["POST", "PUT", "PATCH"]:
        body_props = endpoint.body_schema.get("properties", {})
        for f_name, f_schema in body_props.items():
            valid_body[f_name] = data_provider.get_sample_value(f_name, f_schema.get("type", "string"), f_schema)

    # --- Response schema validation ---
    expected_ok = get_expected_status(endpoint, 200)
    if not expected_ok:
        return tests # Cannot generate success tests if no success code in spec

    if endpoint.response_schema:
        properties = endpoint.response_schema.get("properties", {})
        required_fields = endpoint.response_schema.get("required", [])

        if properties:
            # Test: Response contains all declared fields
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"{endpoint.method} {endpoint.path} — response contains declared fields",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "expected_status": expected_ok,
                "request_body": valid_body if valid_body else None,
                "description": (
                    f"Validates that the response from {endpoint.method} {endpoint.path} "
                    f"contains all fields declared in the schema: "
                    f"{', '.join(list(properties.keys())[:8])}."
                ),
                "expected_response": {
                    "expected_fields": list(properties.keys()),
                },
                "assertions": [
                    f"Response contains field '{f}'" for f in list(properties.keys())[:6]
                ] + ["All declared schema fields are present"],
            })

            # Test: Response field types match schema
            type_checks: list[str] = []
            for field_name, field_schema in list(properties.items())[:6]:
                field_type = field_schema.get("type", "unknown")
                type_checks.append(f"'{field_name}' is type '{field_type}'")

            if type_checks:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"{endpoint.method} {endpoint.path} — response field types match schema",
                    "test_type": "Functional",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "expected_status": expected_ok,
                    "request_body": valid_body if valid_body else None,
                    "description": (
                        f"Validates that response field types match the OpenAPI schema declaration."
                    ),
                    "assertions": type_checks,
                })

        # Test: Required fields are present in response
        if required_fields:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"{endpoint.method} {endpoint.path} — required response fields present",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "expected_status": expected_ok,
                "request_body": valid_body if valid_body else None,
                "description": (
                    f"Validates that all required fields are present in the response: "
                    f"{', '.join(required_fields[:6])}."
                ),
                "assertions": [
                    f"Required field '{f}' is present and non-null" for f in required_fields[:6]
                ],
            })

    # --- Content-Type validation ---
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"{endpoint.method} {endpoint.path} — Content-Type is application/json",
        "test_type": "Functional",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "expected_status": expected_ok,
        "request_body": valid_body if (endpoint.body_schema and endpoint.method in ["POST", "PUT", "PATCH"]) else None,
        "description": (
            f"Validates that the response Content-Type header is 'application/json'."
        ),
        "assertions": [
            "Response Content-Type header is 'application/json'",
            "Response body is valid JSON",
        ],
    })

    # --- Request body required fields enforcement ---
    if endpoint.method in ["POST", "PUT", "PATCH"] and endpoint.body_schema:
        required_body_fields = endpoint.body_schema.get("required", [])
        body_properties = endpoint.body_schema.get("properties", {})

        for field_name in required_body_fields[:4]:  # Limit to first 4
            # Build a body missing this one required field
            sample_body: dict[str, Any] = {}
            for f_name, f_schema in body_properties.items():
                if f_name == field_name:
                    continue  # Omit this field
                f_type = f_schema.get("type", "string")
                sample_body[f_name] = data_provider.get_sample_value(f_name, f_type, f_schema)

            expected_err_status = get_expected_status(endpoint, 400)
            if not expected_err_status:
                continue # Skip negative test if no validation error code in spec

            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"{endpoint.method} {endpoint.path} — missing required field '{field_name}'",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "expected_status": expected_err_status,
                "description": (
                    f"Sends a request body with required field '{field_name}' omitted. "
                    f"Should return {expected_err_status}."
                ),
                "request_headers": {"Content-Type": "application/json"},
                "request_body": sample_body,
                "assertions": [
                    f"Status code is {expected_err_status}",
                    f"Error message mentions missing field '{field_name}'",
                ],
            })

    return tests
