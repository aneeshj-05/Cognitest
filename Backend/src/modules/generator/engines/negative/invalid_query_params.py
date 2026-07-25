"""
Negative test generator — Invalid Query Parameters.

For endpoints that declare query parameters, generates tests with:
  - Wrong types for typed query params

Note: "Unexpected/unknown query parameter" tests have been intentionally
removed because most APIs (correctly) ignore unknown query params.

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType
from .payload_generator import apply_single_mutation, generate_valid_payload


def generate_invalid_query_param_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate tests with invalid query parameter usage.

    Only generates tests for endpoints that have declared query parameters.

    Expected status codes are derived from the Swagger spec's responses section.
    If the spec does not define a relevant error status code, the test is skipped.
    """
    tests: list[dict] = []

    if not endpoint.query_params:
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 400)
    if resolved_status is None:
        return tests

    base_payload = generate_valid_payload(endpoint, spec=spec) if endpoint.body_schema else {}

    for param in endpoint.query_params:
        param_name = param.get("name", "")
        param_type = param.get("type", "string")

        # Wrong type for typed params (only if param expects a specific type)
        if param_type in ("integer", "number"):
            query_payload = apply_single_mutation({param_name: "1"}, param_name, "not-a-number")
            tests.append({
                "id": str(uuid.uuid4()),
                "name": (
                    f"Non-numeric value for '{param_name}' (expects {param_type}) "
                    f"- {endpoint.method} {endpoint.path}"
                ),
                "mutation_type": MutationType.SCHEMA_TYPE_MISMATCH,
                "expected_status": [resolved_status],
                "test_type": "Negative",
                "category": "NEGATIVE",
                "sub_category": "INVALID_QUERY_PARAMS",
                "endpoint_path": f"{endpoint.path}?{param_name}={query_payload[param_name]}",
                "method": endpoint.method,
                "description": (
                    f"Sends 'not-a-number' for query param '{param_name}' which "
                    f"expects {param_type}. The API should reject the request."
                ),
                "request_data": base_payload or None,
                "target_field": param_name,
                "requires_auth": endpoint.requires_auth,
            })

    return tests
