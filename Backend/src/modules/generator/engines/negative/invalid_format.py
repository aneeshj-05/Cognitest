"""
Negative test generator — Invalid Format Values.

For fields that declare a ``format`` (email, date-time, uuid, uri, etc.),
sends values that violate the expected format.

Expected status codes are derived from the Swagger spec's responses section.
If the spec does not define a relevant error status code, the test is skipped.
"""
from typing import Any
import uuid
from src.modules.generator.spec_parser import Endpoint, get_expected_status
from .mutation_taxonomy import MutationType
from .payload_generator import apply_single_mutation, generate_valid_payload


# Common bad values for each OpenAPI format.
_BAD_FORMAT_VALUES: dict[str, list[tuple[str, str]]] = {
    "email": [
        ("missing-at-sign", "not-an-email"),
        ("missing-domain", "user@"),
        ("spaces", "user @example.com"),
    ],
    "date-time": [
        ("not-a-date", "not-a-date"),
        ("invalid-month", "2025-13-01T00:00:00Z"),
        ("invalid-day", "2025-01-32T00:00:00Z"),
    ],
    "date": [
        ("not-a-date", "not-a-date"),
        ("invalid-month", "2025-13-01"),
    ],
    "uuid": [
        ("not-a-uuid", "not-a-uuid"),
        ("too-short", "12345"),
        ("malformed", "xxxx-xxxx-xxxx-xxxx"),
    ],
    "uri": [
        ("no-scheme", "example.com/path"),
        ("spaces", "http://exa mple.com"),
    ],
    "ipv4": [
        ("out-of-range", "999.999.999.999"),
        ("letters", "abc.def.ghi.jkl"),
    ],
    "ipv6": [
        ("not-ipv6", "not-an-ipv6"),
    ],
}


def generate_invalid_format_tests(endpoint: Endpoint, spec: dict[str, Any] | None = None) -> list[dict]:
    """
    Generate tests that violate declared field formats.

    Only meaningful for POST / PUT / PATCH endpoints whose body schema
    has properties with a ``format`` attribute.

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
        fmt = field_schema.get("format")
        if not fmt:
            continue

        bad_entries = _BAD_FORMAT_VALUES.get(fmt)
        if not bad_entries:
            continue

        # Use the first bad value for each format to keep test count manageable
        label, bad_value = bad_entries[0]
        mutated_payload = apply_single_mutation(base_payload, field_name, bad_value)
        tests.append({
            "id": str(uuid.uuid4()),
            "name": (
                f"Invalid {fmt} format for '{field_name}' ({label}) "
                f"- {endpoint.method} {endpoint.path}"
            ),
            "mutation_type": MutationType.FORMAT_VIOLATION,
            "sub_category": "INVALID_PARAMS",
            "expected_status": [resolved_status],
            "test_type": "Negative",
            "category": "NEGATIVE",
            "endpoint_path": endpoint.path,
            "method": endpoint.method,
            "request_data": mutated_payload,
            "description": (
                f"Sends '{bad_value}' for field '{field_name}' which expects "
                f"format '{fmt}'. The API should reject the input."
            ),
            "target_field": field_name,
            "requires_auth": endpoint.requires_auth,
        })


    return tests
