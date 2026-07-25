"""
OpenAPI/Swagger spec parser for extracting endpoints and metadata.
Includes $ref resolution for component schemas.

Handles:
  - $ref resolution (local JSON pointers like #/components/schemas/Foo)
  - URL fragment stripping  (paths like /api/login#missing-email → /api/login)
  - Deduplication of identical (path, method) combinations
"""
import re
from typing import Any
from pydantic import BaseModel

class CircularReferenceError(RuntimeError):
    """Raised when a $ref chain loops back to a schema already being resolved."""
    pass


class Endpoint(BaseModel):
    """Represents a parsed API endpoint."""
    path: str
    method: str
    query_params: list[dict[str, Any]]
    path_params: list[str]
    body_schema: dict[str, Any] | None
    response_schema: dict[str, Any] | None
    requires_auth: bool
    # The content type the endpoint expects for request body
    # e.g. "application/json" or "multipart/form-data"
    content_type: str = "application/json"
    # List of status codes defined in the spec for this operation
    status_codes: list[str] = []


def endpoint_requires_auth(operation: dict, path_item: dict, spec: dict) -> bool:
    """Determine if endpoint requires authentication according to OpenAPI rules.

    Precedence:
      - Operation-level security (including explicit `security: []` to disable)
      - Path-level security
      - Global security
    """
    if isinstance(operation, dict) and "security" in operation:
        return bool(operation.get("security"))

    if isinstance(path_item, dict) and "security" in path_item:
        return bool(path_item.get("security"))

    if isinstance(spec, dict) and "security" in spec:
        return bool(spec.get("security"))

    return False


def _resolve_ref(ref_str: str, spec: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve a $ref string like '#/components/schemas/Chirp' to the actual schema.
    
    Args:
        ref_str: The $ref string (e.g. '#/components/schemas/Chirp')
        spec: The full OpenAPI spec for lookup.
    
    Returns:
        The resolved schema dict, or empty dict if not found.
    """
    if not ref_str.startswith("#/"):
        return {}

    parts = ref_str[2:].split("/")
    current = spec
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return {}
    return current if isinstance(current, dict) else {}


def _resolve_schema(schema: dict[str, Any] | None, spec: dict[str, Any], _seen_refs: set[str] | None = None) -> dict[str, Any] | None:
    """
    Recursively resolve $ref in a schema.
    
    Handles:
      - Direct $ref: {"$ref": "#/components/schemas/Foo"}
      - Array items $ref: {"type": "array", "items": {"$ref": "..."}}
      - Nested property $ref: {"properties": {"bar": {"$ref": "..."}}}
      - allOf / oneOf / anyOf
    """
    if _seen_refs is None:
        _seen_refs = set()
    if schema is None:
        return None

    if not isinstance(schema, dict):
        return schema

    # Direct $ref
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in _seen_refs:
            raise CircularReferenceError(f"Circular $ref detected: {ref}")
        _seen_refs.add(ref)
        try:
            resolved = _resolve_ref(ref, spec)
            return _resolve_schema(resolved, spec, _seen_refs)
        finally:
            _seen_refs.remove(ref)

    result = dict(schema)

    # Resolve items (arrays)
    if "items" in result and isinstance(result["items"], dict):
        result["items"] = _resolve_schema(result["items"], spec, _seen_refs)

    # Resolve properties
    if "properties" in result and isinstance(result["properties"], dict):
        resolved_props = {}
        for prop_name, prop_schema in result["properties"].items():
            resolved_props[prop_name] = _resolve_schema(prop_schema, spec, _seen_refs)
        result["properties"] = resolved_props

    # Resolve allOf / oneOf / anyOf
    for key in ("allOf", "oneOf", "anyOf"):
        if key in result and isinstance(result[key], list):
            result[key] = [_resolve_schema(s, spec, _seen_refs) for s in result[key]]

    # Resolve additionalProperties
    if "additionalProperties" in result and isinstance(result["additionalProperties"], dict):
        result["additionalProperties"] = _resolve_schema(result["additionalProperties"], spec, _seen_refs)

    return result


def extract_endpoints(spec: dict[str, Any]) -> list[Endpoint]:
    """
    Parse OpenAPI spec and extract all endpoints with metadata.
    - Strips URL fragments
    - Resolves all $ref references to their actual schemas.
    - Deduplicates (path, method) pairs.
    
    Args:
        spec: OpenAPI/Swagger specification dictionary

    Returns:
        List of Endpoint objects
    """
    endpoints: list[Endpoint] = []
    seen: set[tuple[str, str]] = set()  # (clean_path, METHOD)
    paths = spec.get("paths", {})

    for raw_path, path_item in paths.items():
        # Strip URL fragment
        clean_path = raw_path.split("#")[0]

        for method in ["get", "post", "put", "patch", "delete", "options", "head"]:
            if method not in path_item:
                continue

            key = (clean_path, method.upper())
            if key in seen:
                continue
            seen.add(key)

            operation = path_item[method]

            # Extract query parameters
            query_params: list[dict[str, Any]] = []
            path_params: list[str] = []
            parameters = operation.get("parameters", [])

            for param in parameters:
                if param.get("in") == "query":
                    query_params.append({
                        "name": param.get("name"),
                        "type": param.get("schema", {}).get("type", "string"),
                        "required": param.get("required", False),
                    })
                elif param.get("in") == "path":
                    path_params.append(param.get("name"))

            # Extract path parameters from path string
            path_param_matches = re.findall(r'\{(\w+)\}', clean_path)
            path_params.extend([p for p in path_param_matches if p not in path_params])
            
            # Extract & resolve request body schema
            body_schema = None
            request_content_type = "application/json"  # default
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                # Prefer application/json, but detect multipart/form-data
                if "application/json" in content:
                    json_content = content["application/json"]
                    request_content_type = "application/json"
                elif "multipart/form-data" in content:
                    json_content = content["multipart/form-data"]
                    request_content_type = "multipart/form-data"
                else:
                    # Fallback: pick the first content type
                    json_content = {}
                    for ct, ct_val in content.items():
                        json_content = ct_val
                        request_content_type = ct
                        break
                raw_schema = json_content.get("schema")
                if raw_schema:
                    body_schema = _resolve_schema(raw_schema, spec)
            
            # Extract & resolve response schema (200/201 responses)
            response_schema = None
            responses = operation.get("responses", {})
            status_codes = list(responses.keys())
            for status in ["200", "201"]:
                if status in responses:
                    content = responses[status].get("content", {})
                    json_content = content.get("application/json", {})
                    raw_schema = json_content.get("schema")
                    if raw_schema:
                        response_schema = _resolve_schema(raw_schema, spec)
                    break

            # Check if authentication is required
            requires_auth = endpoint_requires_auth(operation, path_item, spec)

            endpoints.append(Endpoint(
                path=clean_path,
                method=method.upper(),
                query_params=query_params,
                path_params=path_params,
                body_schema=body_schema,
                response_schema=response_schema,
                requires_auth=requires_auth,
                content_type=request_content_type,
                status_codes=status_codes
            ))

    return endpoints


def get_expected_status(endpoint: Endpoint, target: int) -> int | None:
    """
    STRICT CONTRACT PARSER:
    Resolve the expected status code for a test case ONLY from the API spec.
    If the spec explicitly defines a status code that corresponds to the target category,
    use it. Otherwise, return None to signal that this test should not be generated.

    Rules:
    - No assumed defaults (400, 401, etc.)
    - Single source of truth is endpoint.status_codes
    """
    spec_codes = [str(c) for c in endpoint.status_codes]
    
    # 1. Direct Match
    if str(target) in spec_codes:
        return target

    # 2. Validation / Input Error Category (Target 400/422)
    if target in (400, 422):
        if "422" in spec_codes: return 422
        if "400" in spec_codes: return 400
        # If neither 400 nor 422 is in spec, we can't assume what validation error looks like
        return None
    
    # 3. Conflict / Duplicate Category (Target 409)
    if target == 409:
        if "409" in spec_codes: return 409
        if "422" in spec_codes: return 422
        if "400" in spec_codes: return 400
        return None

    # 4. Not Found Category (Target 404)
    if target == 404:
        if "404" in spec_codes: return 404
        if "400" in spec_codes: return 400
        return None

    # 5. Unauthorized / Forbidden Category (Target 401/403)
    if target in (401, 403):
        if "403" in spec_codes: return 403
        if "401" in spec_codes: return 401
        return None

    # 6. Method Not Allowed (Target 405)
    if target == 405:
        if "405" in spec_codes: return 405
        return None

    # 7. Success Categories (Target 200/201/204)
    if target in (200, 201, 204):
        if str(target) in spec_codes: return target
        if "201" in spec_codes: return 201
        if "200" in spec_codes: return 200
        if "204" in spec_codes: return 204
        return None

    # 8. Broad Fallback (Only if explicitly in spec)
    # If we are looking for ANY error (4xx) and target isn't there, find first 4xx in spec.
    if 400 <= target <= 499:
        for code in spec_codes:
            if code.startswith("4"):
                return int(code)
    
    # If we are looking for ANY success (2xx) and target isn't there, find first 2xx in spec.
    if 200 <= target <= 299:
        for code in spec_codes:
            if code.startswith("2"):
                return int(code)

    return None
