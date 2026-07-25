"""
Negative test generator — Resource Not Found.

For endpoints that have path parameters (e.g. ``/api/chirps/{chirpId}``),
sends requests with valid-format but non-existent IDs.

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status

from .mutation_taxonomy import MutationType

# Fake IDs that look valid but should not exist in any real database
_FAKE_IDS: dict[str, list[tuple[str, str]]] = {
    "uuid": [
        ("non-existent UUID", "ffffffff-ffff-ffff-ffff-ffffffffffff"),
    ],
    "generic": [
        ("non-existent ID", "999999999"),
        ("non-existent slug", "this-resource-does-not-exist"),
    ],
}


def generate_resource_not_found_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate 404 tests by substituting fake IDs into path parameters.

    Only applies to endpoints with at least one path parameter.
    Only targets GET and DELETE methods (most common for resource lookup).

    Expected status codes are derived from the Swagger spec's responses section.
    If the spec does not define a relevant error status code, the test is skipped.
    """
    tests: list[dict] = []

    if not endpoint.path_params:
        return tests

    if endpoint.method not in ("GET", "DELETE"):
        return tests

    # Derive expected status from the spec — do not assume or hardcode
    resolved_status = get_expected_status(endpoint, 404)
    if resolved_status is None:
        return tests

    for param_name in endpoint.path_params:
        if "id" in param_name.lower() or "uuid" in param_name.lower():
            fake_entries = _FAKE_IDS["uuid"] + _FAKE_IDS["generic"][:1]
        else:
            fake_entries = _FAKE_IDS["generic"]

        for label, fake_value in fake_entries:
            resolved_path = endpoint.path.replace(
                f"{{{param_name}}}", fake_value
            )

            tests.append({
                "id": str(uuid.uuid4()),
                "name": (
                    f"Not found ({label}) for '{param_name}' "
                    f"- {endpoint.method} {endpoint.path}"
                ),
                "mutation_type": MutationType.RESOURCE_NOT_FOUND,
                "expected_status": [resolved_status],
                "test_type": "Negative",
                "category": "NEGATIVE",
                "sub_category": "RESOURCE_NOT_FOUND",
                "endpoint_path": resolved_path,
                "method": endpoint.method,
                "description": (
                    f"Sends a {endpoint.method} request to {resolved_path} "
                    f"with a {label} for '{param_name}'. "
                    f"The API should return {resolved_status}."
                ),
                "request_data": None,
                "target_field": param_name,
                "requires_auth": endpoint.requires_auth,
            })

    return tests
