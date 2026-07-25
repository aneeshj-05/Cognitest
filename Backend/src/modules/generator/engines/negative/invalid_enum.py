"""
Negative test generator — Invalid Enum Values.

For fields that declare an ``enum`` constraint, sends a value
that is not in the allowed list.

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import apply_single_mutation, generate_valid_payload


def generate_invalid_enum_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate tests that send out-of-enum values.

    Only applies to POST / PUT / PATCH endpoints whose body schema
    has properties with an ``enum`` list.

    Expected status codes are derived from the Swagger spec's responses section.
    If the spec does not define a relevant error status code, the test is skipped.
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

    properties = endpoint.body_schema.get("properties", {})
    base_payload = generate_valid_payload(endpoint, spec=spec)
    if base_payload is None or not isinstance(base_payload, dict):
        return tests
    for field_name, field_schema in properties.items():
        enum_values = field_schema.get("enum")
        if not enum_values:
            continue

        # Construct a value guaranteed to be outside the enum
        bad_value = _make_bad_enum_value(enum_values)

        if field_name not in base_payload:
            continue

        mutated_payload = apply_single_mutation(base_payload, field_name, bad_value)

        tests.append({
            "id": str(uuid.uuid4()),
            "name": (
                f"Invalid enum value for '{field_name}' "
                f"- {endpoint.method} {endpoint.path}"
            ),
            "mutation_type": MutationType.ENUM_VIOLATION,
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "INVALID_ENUM",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "description": (
                f"Sends '{bad_value}' for field '{field_name}' which only accepts "
                f"{enum_values}. The API should reject the payload."
            ),
            "request_data": mutated_payload,
            "target_field": field_name,
            "requires_auth": endpoint.requires_auth,
        })

    # --- Query param enums ---
    for param in endpoint.query_params:
        enum_values = param.get("enum")
        if not enum_values:
            continue

        bad_value = _make_bad_enum_value(enum_values)

        query_payload = apply_single_mutation({param["name"]: "valid"}, param["name"], bad_value)
        tests.append({
            "id": str(uuid.uuid4()),
            "name": (
                f"Invalid enum value for query param '{param['name']}' "
                f"- {endpoint.method} {endpoint.path}"
            ),
            "mutation_type": MutationType.ENUM_VIOLATION,
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "INVALID_ENUM",
            "endpoint_path": f"{endpoint.path}?{param['name']}={query_payload[param['name']]}",
            "method": endpoint.method,
            "description": (
                f"Sends '{bad_value}' for query param '{param['name']}' which only "
                f"accepts {enum_values}. The API should reject the request."
            ),
            "request_data": base_payload or None,
            "target_field": param["name"],
            "requires_auth": endpoint.requires_auth,
        })

    return tests


def _make_bad_enum_value(enum_values: list) -> str:
    """Create a value that is definitely not in the enum list."""
    candidate = "INVALID_ENUM_VALUE_XYZ"
    while candidate in enum_values:
        candidate += "_X"
    return candidate
