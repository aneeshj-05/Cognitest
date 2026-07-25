"""
Negative test generator — Boundary / Edge-Case Values.

Tests values that fall just outside defined constraints:
  - minimum / maximum  (integers / numbers)
  - minLength / maxLength  (strings)
  - minItems / maxItems  (arrays)

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import apply_single_mutation, generate_valid_payload


def generate_boundary_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate boundary-value tests for constrained fields.

    Only applies to POST / PUT / PATCH with a body schema.
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
        if field_name not in base_payload:
            continue
        field_type = field_schema.get("type", "string")

        # --- Numeric boundaries ---
        if field_type in ("integer", "number"):
            minimum = field_schema.get("minimum")
            maximum = field_schema.get("maximum")

            if minimum is not None:
                below = minimum - 1
                mutated_payload = apply_single_mutation(base_payload, field_name, below)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Below minimum ({below}) for '{field_name}'",
                    mutated_payload,
                    f"Sends value {below} which is below the minimum of {minimum}.",
                    resolved_status,
                ))

            if maximum is not None:
                above = maximum + 1
                mutated_payload = apply_single_mutation(base_payload, field_name, above)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Above maximum ({above}) for '{field_name}'",
                    mutated_payload,
                    f"Sends value {above} which exceeds the maximum of {maximum}.",
                    resolved_status,
                ))

        # --- String length boundaries ---
        if field_type == "string":
            min_len = field_schema.get("minLength")
            max_len = field_schema.get("maxLength")

            if min_len is not None and min_len > 0:
                short = "a" * (min_len - 1) if min_len > 1 else ""
                mutated_payload = apply_single_mutation(base_payload, field_name, short)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Below minLength for '{field_name}' (sent {len(short)} chars)",
                    mutated_payload,
                    f"Sends a string shorter than the minimum length of {min_len}.",
                    resolved_status,
                ))

            if max_len is not None:
                long_str = "a" * (max_len + 10)
                mutated_payload = apply_single_mutation(base_payload, field_name, long_str)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Above maxLength for '{field_name}' (sent {len(long_str)} chars)",
                    mutated_payload,
                    f"Sends a string longer than the maximum length of {max_len}.",
                    resolved_status,
                ))

        # --- Array item count boundaries ---
        if field_type == "array":
            min_items = field_schema.get("minItems")
            max_items = field_schema.get("maxItems")

            if min_items is not None and min_items > 0:
                short_arr = ["x"] * (min_items - 1) if min_items > 1 else []
                mutated_payload = apply_single_mutation(base_payload, field_name, short_arr)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Below minItems for '{field_name}' (sent {len(short_arr)} items)",
                    mutated_payload,
                    f"Sends an array with fewer items than the minimum of {min_items}.",
                    resolved_status,
                ))

            if max_items is not None:
                long_arr = ["x"] * (max_items + 5)
                mutated_payload = apply_single_mutation(base_payload, field_name, long_arr)
                tests.append(_make(
                    endpoint,
                    field_name,
                    f"Above maxItems for '{field_name}' (sent {len(long_arr)} items)",
                    mutated_payload,
                    f"Sends an array with more items than the maximum of {max_items}.",
                    resolved_status,
                ))

    return tests


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make(
    endpoint: Endpoint,
    field: str,
    title_suffix: str,
    request_data: dict,
    detail: str,
    resolved_status: int,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "name": f"Boundary: {title_suffix} - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.VALUE_OUT_OF_RANGE,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "INVALID_PARAMS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": f"{detail} The API should reject the payload.",
        "request_data": request_data,
        "target_field": field,
        "requires_auth": endpoint.requires_auth,
    }
