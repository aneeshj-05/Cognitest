"""
XSS fuzz test generators.
Generates tests with cross-site scripting payloads in API inputs.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "javascript:alert(1)",
    "<svg onload=alert(1)>",
    "<body onload=alert(1)>",
    "'-alert(1)-'",
    "\"><script>alert(1)</script>",
    "<iframe src='javascript:alert(1)'>",
    "{{constructor.constructor('alert(1)')()}}",
    "${alert(1)}",
    "<details open ontoggle=alert(1)>",
    "<marquee onstart=alert(1)>",
]


def generate_xss_fuzz_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate XSS fuzz tests for an endpoint.
    Tests if the API reflects or stores XSS payloads unsanitized.
    """
    tests = []

    # XSS in query params
    expected_err = get_expected_status(endpoint, 400)
    if expected_err:
        for param in endpoint.query_params:
            for payload in XSS_PAYLOADS[:4]:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"XSS fuzz in query param '{param['name']}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "XSS_FUZZ",
                    "endpoint_path": endpoint.path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {param["name"]: payload},
                    "expected_status": expected_err,
                    "expected_behavior": f"Should sanitize/reject XSS payload (Expected {expected_err})",
                    "description": f"Sends XSS payload '{payload[:30]}' in query param",
                })

    # XSS in body fields
    if endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            properties = endpoint.body_schema.get("properties", {})
            for field_name, field_schema in list(properties.items())[:3]:
                if field_schema.get("type") == "string":
                    for payload in XSS_PAYLOADS[:3]:
                        tests.append({
                            "id": str(uuid.uuid4()),
                            "name": f"XSS fuzz in body field '{field_name}'",
                            "test_type": "Fuzz",
                            "fuzz_type": "XSS_FUZZ",
                            "endpoint_path": endpoint.path,
                            "method": endpoint.method,
                            "headers": {"Content-Type": "application/json"},
                            "body": {field_name: payload},
                            "query_params": {},
                            "expected_status": expected_body_err,
                            "expected_behavior": f"Should not reflect XSS in response (Expected {expected_body_err})",
                            "description": f"Sends XSS payload in body field '{field_name}'",
                        })

    # XSS in path params
    expected_path_err = get_expected_status(endpoint, 400)
    if expected_path_err:
        for param in endpoint.path_params:
            for payload in XSS_PAYLOADS[:2]:
                path = endpoint.path.replace(f"{{{param}}}", payload)
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"XSS fuzz in path param '{param}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "XSS_FUZZ",
                    "endpoint_path": path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {},
                    "expected_status": expected_path_err,
                    "expected_behavior": f"Should reject XSS in path (Expected {expected_path_err})",
                    "description": f"Sends XSS payload in path param '{param}'",
                })

    return tests
