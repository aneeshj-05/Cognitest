"""
Path traversal fuzz test generators.
Generates tests with directory traversal sequences in path/query parameters.
"""
import uuid
from ...spec_parser import Endpoint, get_expected_status


PATH_TRAVERSAL_PAYLOADS = [
    "../../../etc/passwd",
    "..\\..\\..\\windows\\system32\\config\\sam",
    "....//....//....//etc/passwd",
    "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
    "..%252f..%252f..%252fetc%252fpasswd",
    "..%c0%af..%c0%af..%c0%afetc/passwd",
    "/etc/passwd%00.jpg",
    "....\\\\....\\\\....\\\\etc\\\\passwd",
    "..;/..;/..;/etc/passwd",
    "file:///etc/passwd",
]


def generate_path_traversal_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate path traversal fuzz tests.
    Tests if the API is vulnerable to directory traversal attacks.
    """
    tests = []

    # Path traversal in path params
    expected_path_err = get_expected_status(endpoint, 400)
    if expected_path_err:
        for param in endpoint.path_params:
            for payload in PATH_TRAVERSAL_PAYLOADS[:4]:
                path = endpoint.path.replace(f"{{{param}}}", payload)
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"Path traversal in path param '{param}'",
                    "test_type": "Fuzz",
                    "fuzz_type": "PATH_TRAVERSAL",
                    "endpoint_path": path,
                    "method": endpoint.method,
                    "headers": {},
                    "body": None,
                    "query_params": {},
                    "expected_status": expected_path_err,
                    "expected_behavior": f"Should block path traversal attempt (Expected {expected_path_err})",
                    "description": f"Sends path traversal '{payload[:40]}' in path param '{param}'",
                })

    # Path traversal in query params (file/path-type params)
    expected_query_err = get_expected_status(endpoint, 400)
    if expected_query_err:
        for param in endpoint.query_params:
            param_name = param["name"].lower()
            if any(kw in param_name for kw in ("file", "path", "url", "dir", "name", "doc")):
                for payload in PATH_TRAVERSAL_PAYLOADS[:3]:
                    tests.append({
                        "id": str(uuid.uuid4()),
                        "name": f"Path traversal in query param '{param['name']}'",
                        "test_type": "Fuzz",
                        "fuzz_type": "PATH_TRAVERSAL",
                        "endpoint_path": endpoint.path,
                        "method": endpoint.method,
                        "headers": {},
                        "body": None,
                        "query_params": {param["name"]: payload},
                        "expected_status": expected_query_err,
                        "expected_behavior": f"Should reject path traversal sequence (Expected {expected_query_err})",
                        "description": f"Sends path traversal in file-related query param",
                    })

    # Path traversal in body fields
    if endpoint.method in ("POST", "PUT", "PATCH") and endpoint.body_schema:
        expected_body_err = get_expected_status(endpoint, 400)
        if expected_body_err:
            properties = endpoint.body_schema.get("properties", {})
            for field_name, field_schema in list(properties.items())[:2]:
                if field_schema.get("type") == "string":
                    for payload in PATH_TRAVERSAL_PAYLOADS[:2]:
                        tests.append({
                            "id": str(uuid.uuid4()),
                            "name": f"Path traversal in body field '{field_name}'",
                            "test_type": "Fuzz",
                            "fuzz_type": "PATH_TRAVERSAL",
                            "endpoint_path": endpoint.path,
                            "method": endpoint.method,
                            "headers": {"Content-Type": "application/json"},
                            "body": {field_name: payload},
                            "query_params": {},
                            "expected_status": expected_body_err,
                            "expected_behavior": f"Should sanitize path traversal in body (Expected {expected_body_err})",
                            "description": f"Sends path traversal in body field '{field_name}'",
                        })

    return tests
