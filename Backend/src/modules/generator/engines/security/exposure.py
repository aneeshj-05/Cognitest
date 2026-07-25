"""
Excessive Data Exposure test generators. Covers OWASP API Security 4.4.

Only generates tests for GET endpoints that:
  - Have a response schema with sensitive field names
  - Are public (no auth required) OR auth-required (runner injects token)

Skips POST/PUT/PATCH endpoints — mass assignment tests are unreliable
without knowing valid request payloads.
"""
import uuid
from ...spec_parser import Endpoint

SENSITIVE_FIELDS = [
    "password", "passwd", "pwd",
    "token", "access_token", "refresh_token", "api_key", "apikey",
    "secret", "client_secret",
    "hash", "salt",
    "ssn", "social_security",
    "credit_card", "cvv",
]


def generate_exposure_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate data exposure tests for GET endpoints with sensitive response fields.
    """
    tests = []

    # Only meaningful for GET endpoints that return data
    if endpoint.method != "GET":
        return tests

    if not endpoint.response_schema:
        return tests

    properties = endpoint.response_schema.get("properties", {})
    # Also check nested array items
    if not properties and endpoint.response_schema.get("type") == "array":
        items = endpoint.response_schema.get("items", {})
        properties = items.get("properties", {}) if isinstance(items, dict) else {}

    for field_name in properties:
        field_lower = field_name.lower()
        for sensitive in SENSITIVE_FIELDS:
            if sensitive in field_lower:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Excessive Data Exposure: '{field_name}' in response of {endpoint.path}",
                    "test_type": "Security",
                    "owasp_category": "Exposure",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "expected_status": 200,
                    "requires_auth": endpoint.requires_auth,
                    "description": (
                        f"Calls {endpoint.method} {endpoint.path} and checks that "
                        f"sensitive field '{field_name}' is not present in the response. "
                        f"If the field appears with a real value, this is a data exposure vulnerability."
                    ),
                })
                break

    return tests
