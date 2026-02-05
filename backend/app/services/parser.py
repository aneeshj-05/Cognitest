import json
import yaml
from typing import List, Dict, Any
from app.schemas import EndpointMetadata

def load_spec_file(file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    Parses bytes into a Python Dictionary (supports JSON and YAML).
    """
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        return yaml.safe_load(file_content)
    return json.loads(file_content)

def has_request_body(method_details: Dict[str, Any]) -> bool:
    """
    Checks if an endpoint expects a request body.
    Supports OpenAPI v3 ('requestBody') and Swagger v2 ('parameters' in body).
    Reference: Design Doc [cite: 64]
    """
    # OpenAPI v3 check
    if "requestBody" in method_details:
        return True
    
    # Swagger v2 check
    if "parameters" in method_details:
        for param in method_details["parameters"]:
            if param.get("in") == "body":
                return True
    return False

def requires_auth(method_details: Dict[str, Any], root_spec: Dict[str, Any]) -> bool:
    """
    Checks for authentication hints.
    Reference: Design Doc [cite: 65, 71]
    """
    # Check method-level security
    if "security" in method_details and len(method_details["security"]) > 0:
        return True
    
    # Check global security (applied to all endpoints)
    if "security" in root_spec and len(root_spec["security"]) > 0:
        return True
        
    return False

def parse_swagger(file_content: bytes, filename: str) -> List[EndpointMetadata]:
    """
    Main logic to extract endpoints.
    Reference: Design Doc [cite: 61-63]
    """
    try:
        spec = load_spec_file(file_content, filename)
    except Exception as e:
        print(f"Error parsing file: {e}")
        return []

    extracted_endpoints = []
    
    paths = spec.get("paths", {})
    
    for path, methods in paths.items():
        # Iterate over HTTP methods (get, post, put, etc.)
        for method, details in methods.items():
            if method.lower() not in ["get", "post", "put", "patch", "delete"]:
                continue
                
            # Extract metadata
            metadata = EndpointMetadata(
                endpoint=path,                  # [cite: 62]
                method=method.upper(),          # [cite: 63]
                hasRequestBody=has_request_body(details), # [cite: 64]
                requiresAuth=requires_auth(details, spec) # [cite: 65]
            )
            
            extracted_endpoints.append(metadata)
            
    return extracted_endpoints