"""
CRUD operation validation test generators.

Generates functional tests for Create, Read, Update, and Delete operations
based on the endpoint's HTTP method, body schema, and response schema.
"""
import uuid
from typing import Any

from ...spec_parser import Endpoint, get_expected_status


def _generate_sample_body(body_schema: dict[str, Any] | None) -> dict | None:
    """Generate a sample request body from a JSON schema."""
    if not body_schema:
        return None

    properties = body_schema.get("properties", {})
    if not properties:
        return None

    sample: dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        field_type = field_schema.get("type", "string")
        field_format = field_schema.get("format", "")
        
        # 1. First, check explicitly for binary/byte/file formats or field names suggesting media
        is_media_field = (
            field_format in ("binary", "byte") or 
            any(media_keyword in field_name.lower() for media_keyword in ["image", "file", "avatar", "photo", "picture", "logo", "thumbnail", "attachment", "document", "url", "link"])
        )
        
        if is_media_field:
            if field_format == "byte":
                # Some swaggers use 'byte' format for base64 encoded strings
                sample[field_name] = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4//8/w38GIAXDIBKE0DHxgljNBAAO9TXL0Y4OHwAAAABJRU5ErkJggg=="
            else:
                # Preferred fallback for general image fields and multipart endpoints
                sample[field_name] = "https://via.placeholder.com/300"
            continue

        # 2. Standard types logic
        if field_type == "string":
            # Use enum values if available
            enum_values = field_schema.get("enum")
            if enum_values:
                sample[field_name] = enum_values[0]
            else:
                low_name = field_name.lower()
                if "email" in low_name:
                    sample[field_name] = "user@demo.com"
                elif "password" in low_name:
                    sample[field_name] = "Password123!"
                elif "phone" in low_name or "contact" in low_name:
                    sample[field_name] = "+1234567890"
                elif "url" in low_name or "link" in low_name:
                    sample[field_name] = "https://example.com"
                else:
                    sample[field_name] = f"test_{field_name}"
        elif field_type == "integer":
            sample[field_name] = 1
        elif field_type == "number":
            sample[field_name] = 1.0
        elif field_type == "boolean":
            sample[field_name] = True
        elif field_type == "array":
            sample[field_name] = []
        elif field_type == "object":
            sample[field_name] = {}
        else:
            sample[field_name] = f"test_{field_name}"

    return sample


def _get_response_keys(response_schema: dict[str, Any] | None) -> list[str]:
    """Extract expected response field names from response schema."""
    if not response_schema:
        return []
    return list(response_schema.get("properties", {}).keys())


def generate_crud_tests(endpoint: Endpoint) -> list[dict]:
    """
    Generate CRUD operation validation tests for an endpoint.

    Produces tests based on the endpoint's HTTP method:
    - GET    → Read operation (200)
    - POST   → Create operation (201)
    - PUT    → Full update operation (200)
    - PATCH  → Partial update operation (200)
    - DELETE → Delete operation (200/204)
    """
    tests = []
    sample_body = _generate_sample_body(endpoint.body_schema)
    response_keys = _get_response_keys(endpoint.response_schema)
    # Carry over the content type from the Swagger spec
    ct = getattr(endpoint, "content_type", "application/json")

    # --- GET: Read operation ---
    if endpoint.method == "GET":
        expected_ok = get_expected_status(endpoint, 200)
        if expected_ok:
            test: dict[str, Any] = {
                "id": str(uuid.uuid4()),
                "name": f"GET {endpoint.path} — valid read returns {expected_ok}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "GET",
                "expected_status": expected_ok,
                "description": f"Sends a valid GET request to {endpoint.path} and expects a {expected_ok} response.",
                "assertions": [f"Status code is {expected_ok}", "Response body is valid JSON"],
            }
            if response_keys:
                test["assertions"].append(
                    f"Response contains expected fields: {', '.join(response_keys[:5])}"
                )
                test["expected_response"] = {
                    "expected_fields": response_keys[:5],
                }
            tests.append(test)

            # GET with path params — verify valid ID returns data
            if endpoint.path_params:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"GET {endpoint.path} — valid ID returns resource",
                    "test_type": "Functional",
                    "endpoint_path": endpoint.path,
                    "method": "GET",
                    "path_params": {p: "valid-test-id" for p in endpoint.path_params},
                    "expected_status": expected_ok,
                    "description": f"Fetches a specific resource by ID. Expects {expected_ok} with matching resource data.",
                    "assertions": [
                        f"Status code is {expected_ok}",
                        "Returned resource matches requested ID",
                    ],
                })

    # --- POST: Create operation ---
    elif endpoint.method == "POST":
        expected_status = get_expected_status(endpoint, 201)
        if expected_status:
            test = {
                "id": str(uuid.uuid4()),
                "name": f"POST {endpoint.path} — valid create returns {expected_status}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "POST",
                "expected_status": expected_status,
                "description": f"Creates a new resource at {endpoint.path} with valid data.",
                "request_headers": {"Content-Type": ct},
                "content_type": ct,
                "assertions": [
                    f"Status code is {expected_status}",
                    "Response body contains created resource",
                ],
            }
            if sample_body:
                test["request_body"] = sample_body
                test["assertions"].append(
                    "Response body reflects submitted data"
                )
            if response_keys:
                test["expected_response"] = {"expected_fields": response_keys[:5]}
            tests.append(test)

        # POST: duplicate creation should be handled
        if sample_body:
            expected_err = get_expected_status(endpoint, 409)
            if expected_err:
                tests.append({
                    "id": str(uuid.uuid4()),
                    "name": f"POST {endpoint.path} — duplicate create handled",
                    "test_type": "Functional",
                    "endpoint_path": endpoint.path,
                    "method": "POST",
                    "expected_status": expected_err,
                    "description": f"Attempts to create a duplicate resource. Expects {expected_err} Conflict or appropriate handling.",
                    "request_headers": {"Content-Type": ct},
                    "content_type": ct,
                    "request_body": sample_body,
                    "assertions": [
                        f"Status code is {expected_err} or similar conflict response",
                        "Error message indicates duplicate resource",
                    ],
                })

    # --- PUT: Full update operation ---
    elif endpoint.method == "PUT":
        expected_ok = get_expected_status(endpoint, 200)
        if expected_ok:
            test = {
                "id": str(uuid.uuid4()),
                "name": f"PUT {endpoint.path} — valid full update returns {expected_ok}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "PUT",
                "expected_status": expected_ok,
                "description": f"Sends a full update to {endpoint.path} with valid data. Expects {expected_ok}.",
                "request_headers": {"Content-Type": ct},
                "content_type": ct,
                "assertions": [
                    f"Status code is {expected_ok}",
                    "Response body reflects updated data",
                ],
            }
            if sample_body:
                test["request_body"] = sample_body
            if endpoint.path_params:
                test["path_params"] = {p: "valid-test-id" for p in endpoint.path_params}
            tests.append(test)

    # --- PATCH: Partial update operation ---
    elif endpoint.method == "PATCH":
        expected_ok = get_expected_status(endpoint, 200)
        if expected_ok:
            test = {
                "id": str(uuid.uuid4()),
                "name": f"PATCH {endpoint.path} — valid partial update returns {expected_ok}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "PATCH",
                "expected_status": expected_ok,
                "description": f"Sends a partial update to {endpoint.path}. Expects {expected_ok}.",
                "request_headers": {"Content-Type": ct},
                "content_type": ct,
                "assertions": [
                    f"Status code is {expected_ok}",
                    "Only specified fields are updated",
                    "Unspecified fields remain unchanged",
                ],
            }
            # Use only the first field from the body schema for partial update
            if sample_body:
                first_key = next(iter(sample_body))
                test["request_body"] = {first_key: sample_body[first_key]}
            if endpoint.path_params:
                test["path_params"] = {p: "valid-test-id" for p in endpoint.path_params}
            tests.append(test)

    # --- DELETE: Delete operation ---
    elif endpoint.method == "DELETE":
        expected_status = get_expected_status(endpoint, 204)
        if expected_status:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"DELETE {endpoint.path} — valid delete returns {expected_status}",
                "test_type": "Functional",
                "endpoint_path": endpoint.path,
                "method": "DELETE",
                "expected_status": expected_status,
                "description": f"Deletes a resource at {endpoint.path}. Expects {expected_status}.",
                "path_params": {p: "valid-test-id" for p in endpoint.path_params} if endpoint.path_params else None,
                "assertions": [
                    f"Status code is {expected_status}",
                    "Resource is no longer accessible after deletion",
                ],
            })

            # GET after DELETE should return 404
            if endpoint.path_params:
                expected_err = get_expected_status(endpoint, 404)
                if expected_err:
                    tests.append({
                        "id": str(uuid.uuid4()),
                        "name": f"GET {endpoint.path} after DELETE — returns {expected_err}",
                        "test_type": "Functional",
                        "endpoint_path": endpoint.path,
                        "method": "GET",
                        "expected_status": expected_err,
                        "description": f"After deleting a resource, a GET for the same ID should return {expected_err}.",
                        "path_params": {p: "deleted-test-id" for p in endpoint.path_params},
                        "assertions": [
                            f"Status code is {expected_err}",
                            "Resource is confirmed deleted",
                        ],
                    })

    return tests
