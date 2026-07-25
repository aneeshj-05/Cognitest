"""
Negative test generator — Missing Required Fields.

For each required field in the request body, generates a test case that
omits that field. Also generates an "all missing" test with an empty body.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import REMOVE_FIELD, apply_single_mutation, generate_valid_payload


def generate_missing_field_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate tests that omit required body fields one at a time.

    Only applies to POST / PUT / PATCH endpoints that define a body schema
    with a ``required`` list.

    Expected status codes are derived from the Swagger spec's responses section.
    If the spec does not define a relevant error status code, the test is skipped.
    """
    tests: list[dict] = []

    if endpoint.method not in ("POST", "PUT", "PATCH"):
        return tests

    if not endpoint.body_schema:
        return tests

    required_fields = endpoint.body_schema.get("required", [])

    if not required_fields:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 400)
    if resolved_status is None:
        return tests

    base_payload = generate_valid_payload(endpoint, spec=spec)
    if base_payload is None or not isinstance(base_payload, dict):
        return tests
    # --- One test per missing required field ---
    for field in required_fields:
        if field not in base_payload:
            continue
        body_without_field = apply_single_mutation(base_payload, field, REMOVE_FIELD)

        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Missing required field '{field}' - {endpoint.method} {endpoint.path}",
            "mutation_type": MutationType.SCHEMA_MISSING_FIELD,
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "sub_category": "MISSING_PARAMS",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "description": (
                f"Omits the required field '{field}' from the request body. "
                "The API should reject the invalid payload."
            ),
            "request_data": body_without_field,
            "target_field": field,
            "requires_auth": endpoint.requires_auth,
        })

    # --- All required fields missing (empty JSON object) ---
    present_required = [f for f in required_fields if f in base_payload]
    if not present_required:
        return tests
    all_missing = apply_single_mutation(base_payload, present_required[0], REMOVE_FIELD)
    for field in present_required[1:]:
        all_missing = apply_single_mutation(all_missing, field, REMOVE_FIELD)

    tests.append({
        "id": str(uuid.uuid4()),
        "name": f"All required fields missing - {endpoint.method} {endpoint.path}",
        "mutation_type": MutationType.SCHEMA_MISSING_FIELD,
        "expected_status": [resolved_status],
        "test_type": "Negative",
        "category": "NEGATIVE",
        "sub_category": "MISSING_PARAMS",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "description": (
            "Sends a payload missing all required fields. "
            "Required fields are missing, so the API should reject the payload."
        ),
        "request_data": all_missing,
        "target_field": None,
        "requires_auth": endpoint.requires_auth,
    })

    return tests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
