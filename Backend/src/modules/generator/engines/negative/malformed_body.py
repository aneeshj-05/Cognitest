"""
Negative test generator — Malformed Request Bodies.

Sends structurally broken payloads:
  - raw string instead of JSON
  - empty body on POST/PUT/PATCH
  - null body
  - array instead of object (and vice-versa)

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType


def generate_malformed_body_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate tests with structurally invalid request bodies.

    Only applies to POST / PUT / PATCH endpoints that declare a body schema.
    """
    tests: list[dict] = []

    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    if not endpoint.body_schema:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 400)
    if resolved_status is None:
        return tests

    # 1. Raw string instead of JSON
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Raw string body - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.STRUCTURE_INVALID,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_PARAMS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            "Sends a plain string ('this is not json') instead of a JSON body. "
            "The API should return an error due to malformed JSON."
        ),
        "request_data": "this is not json",
        "target_field": None,
        "requires_auth": endpoint.requires_auth,
    })

    # 2. Empty body
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Empty body - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_PARAMS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            "Sends a completely empty request body. "
            "The API should reject the request because a body is required."
        ),
        "request_data": None,
        "target_field": None,
        "requires_auth": endpoint.requires_auth,
    })
    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"Null JSON body - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_PARAMS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            "Sends JSON null as the body. "
            "The API should return an error because an object/array was expected."
        ),
        "request_data": None,
        "send_json_null": True,
        "target_field": None,
        "requires_auth": endpoint.requires_auth,
    })
    if endpoint.body_schema and endpoint.body_schema.get("type") != "array":
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Array instead of object body - {endpoint.method} {endpoint.path}",
            "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "INVALID_PARAMS",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "description": (
                "Sends a JSON array ([1, 2, 3]) where an object is expected. "
                "The API should return an error due to schema validation failure."
            ),
            "request_data": [1, 2, 3],
            "target_field": None,
            "requires_auth": endpoint.requires_auth,
        })
    if endpoint.body_schema and endpoint.body_schema.get("type") == "array":
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Object instead of array body - {endpoint.method} {endpoint.path}",
            "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "INVALID_PARAMS",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "description": (
                'Sends a JSON object ({"key": "value"}) where an array is expected. '
                "The API should return an error due to schema validation failure."
            ),
            "request_data": {"key": "value"},
            "target_field": None,
            "requires_auth": endpoint.requires_auth,
        })

    return tests
