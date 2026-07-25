"""
Random string fuzz test generators.
Generates tests with random characters, boundary values, special chars, and null bytes.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


RANDOM_STRING_PAYLOADS = [
    "",                                    # empty string
    " ",                                   # single space
    "null",                                # literal null
    "undefined",                           # literal undefined
    "true",                                # boolean as string
    "0",                                   # zero
    "-1",                                  # negative
    "9999999999999999999",                  # huge number as string
    "\x00",                                # null byte
    "\x00\x00\x00",                        # multiple null bytes
    "aaa%00bbb",                           # null byte in middle
    "%n%n%n%n",                             # format string
    "%s%s%s%s",                             # format string
    "%d%d%d%d",                             # format string
    "%x%x%x%x",                             # format string hex
    "A" * 10,                              # short repeated
    "{{}}",                                # template syntax
    "${7*7}",                              # expression injection
    "NaN",                                 # not a number
    "Infinity",                            # infinity
]


def generate_random_string_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate random string fuzz tests for an endpoint.
    Targets query params, path params, and body string fields.
    """
    tests = []

    # Fuzz query params
    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for param in endpoint.query_params:
            for payload in RANDOM_STRING_PAYLOADS[:5]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Random string in query param '{param['name']}' — {repr(payload)[:30]}",
                    "test_type": "Fuzz",
                    "fuzz_type": "RANDOM_STRING",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {param["name"]: payload},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should return {expected_err} or reject gracefully",
                    "description": f"Sends random/boundary string '{repr(payload)[:40]}' in query param '{param['name']}'",
                })

    # Fuzz path params
    expected_path_err = get_expected_status(endpoint, 400)
    if expected_path_err:
        for param in endpoint.path_params:
            for payload in RANDOM_STRING_PAYLOADS[:3]:
                path = endpoint.path.replace(f"{{{param}}}", str(payload))
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Random string in path param '{param}' — {repr(payload)[:30]}",
                    "test_type": "Fuzz",
                    "fuzz_type": "RANDOM_STRING",
                    "endpoint_path": path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {},
                    "expected_status": expected_path_err,
                    "expected_behavior": f"Should return {expected_path_err} or similar error",
                    "description": f"Sends random string in path param '{param}'",
                })

    # Fuzz body fields
    if endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            properties = endpoint.body_schema.get("properties", {})
            for field_name, field_schema in list(properties.items())[:3]:
                if field_schema.get("type") == "string":
                    for payload in RANDOM_STRING_PAYLOADS[:3]:
                        tests.append({
                            "id": str(uuid.uuid4()),
                            "name": f"Random string in body field '{field_name}'",
                            "test_type": "Fuzz",
                            "fuzz_type": "RANDOM_STRING",
                            "endpoint_path": endpoint.path,
                            "method": endpoint.method,
                            "headers": {"Content-Type": "application/json"},
                            "body": {field_name: payload},
                            "query_params": {},
                            "expected_status": expected_body_err,
                            "expected_behavior": f"Should validate and reject with {expected_body_err}",
                            "description": f"Sends random string '{repr(payload)[:30]}' in body field '{field_name}'",
                        })

    return tests
