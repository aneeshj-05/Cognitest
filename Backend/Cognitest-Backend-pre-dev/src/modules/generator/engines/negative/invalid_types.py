"""
Negative test generator — Incorrect Data Types.

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import generate_valid_payload, apply_single_mutation


# Map each schema type to wrong values
_WRONG_VALUES: dict[str, list[tuple[str, object]]] = {
    "string":  [("integer", 12345), ("boolean", True)],
    "integer": [("string", "not-a-number"), ("boolean", True)],
    "number":  [("string", "not-a-number"), ("boolean", True)],
    "boolean": [("string", "yes"), ("integer", 42)],
    "array":   [("string", "not-an-array"), ("integer", 123)],
    "object":  [("string", "not-an-object"), ("array", [1, 2, 3])],
}


def generate_invalid_type_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    tests: list[dict] = []

    # Only for body-based endpoints
    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    if not endpoint.body_schema:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 400)
    if resolved_status is None:
        return tests

    properties = endpoint.body_schema.get("properties", {})
    base_payload = generate_valid_payload(endpoint, spec=spec)
    if base_payload is None or not isinstance(base_payload, dict):
        return tests

    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        wrong_entries = _WRONG_VALUES.get(field_type, [])

        if not wrong_entries:
            continue
        if field_name not in base_payload:
            continue

        # Take one mutation per field (avoid explosion)
        wrong_type_label, wrong_value = wrong_entries[0]

        mutated_payload = apply_single_mutation(
            base_payload,
            field_name,
            wrong_value
        )

        tests.append({
            "id": str(uuid.uuid4()),
            "name": (
                f"Wrong type for '{field_name}' "
                f"(sent {wrong_type_label} instead of {field_type}) "
                f"- {endpoint.method} {endpoint.path}"
            ),

            "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,

            "expected_status": [resolved_status],

            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "INCORRECT_DATA_TYPE",

            "endpoint_path": endpoint.path,
            "method": endpoint.method,

            "request_data": mutated_payload,
            "target_field": field_name,

            "description": (
                f"Sends {wrong_type_label} value for '{field_name}', "
                f"which expects {field_type}."
            ),
            "requires_auth": endpoint.requires_auth,
        })

    return tests
