import uuid
import re
import json

# Keywords to identify authentication-related endpoints
AUTH_KEYWORDS = ['register', 'signup', 'sign-up', 'login', 'signin', 'sign-in', 'auth', 'token', 'session']
TOKEN_KEYWORDS = ['login', 'signin', 'sign-in', 'auth/login', 'authenticate', 'token']

def is_auth_endpoint(path, name=""):
    """Check if an endpoint is authentication-related"""
    path_lower = path.lower()
    name_lower = name.lower() if name else ""
    return any(kw in path_lower or kw in name_lower for kw in AUTH_KEYWORDS)

def is_token_endpoint(path, name=""):
    """Check if an endpoint should capture a token"""
    path_lower = path.lower()
    name_lower = name.lower() if name else ""
    return any(kw in path_lower or kw in name_lower for kw in TOKEN_KEYWORDS)

def get_priority(tc):
    """Assign priority for ordering: auth endpoints first"""
    path = tc.get("path", "").lower()
    name = tc.get("name", "").lower()
    
    # Register/signup should be first
    if any(kw in path or kw in name for kw in ['register', 'signup', 'sign-up', 'create user']):
        return 0
    # Login should be second
    if any(kw in path or kw in name for kw in ['login', 'signin', 'sign-in', 'authenticate']):
        return 1
    # Other auth endpoints
    if is_auth_endpoint(path, name):
        return 2
    # Regular endpoints
    return 3

def build_postman_collection(parsed, testcases):
    items = []
    base_url = parsed.get("baseUrl", "")
    
    # Sort testcases: auth endpoints first
    sorted_testcases = sorted(testcases, key=get_priority)

    for tc in sorted_testcases:
        path = tc["path"].replace("{", "{{").replace("}", "}}")
        name = tc.get("name", "")
        method = tc["method"]
        
        # Build headers - always include auth token for non-auth endpoints
        headers = [{"key": "Content-Type", "value": "application/json"}]
        
        # Add authorization header for protected routes (non-auth endpoints)
        if not is_auth_endpoint(path, name):
            headers.append({
                "key": "Authorization",
                "value": "Bearer {{authToken}}",
                "type": "text"
            })
        
        # Build request body for POST/PUT/PATCH methods
        request_body = None
        body_data = {}
        if method in ["POST", "PUT", "PATCH"]:
            # Add sample body based on endpoint type
            body_data = tc.get("body", {})
            if not body_data:
                if "register" in path.lower() or "signup" in path.lower() or "user" in path.lower():
                    body_data = {
                        "username": "testuser_{{$randomInt}}",
                        "email": "testuser{{$randomInt}}@test.com",
                        "password": "TestPassword123!"
                    }
                elif "login" in path.lower() or "signin" in path.lower():
                    body_data = {
                        "username": "{{testUsername}}",
                        "password": "{{testPassword}}"
                    }
            
            if body_data:
                request_body = {
                    "mode": "raw",
                    "raw": json.dumps(body_data, indent=2)
                }
                # Store full payload in testcase for frontend display
                tc['payloadData'] = body_data if body_data else {}
        else:
            # For GET, DELETE, etc., no payload
            tc['payloadData'] = {}
        
        # Build test script
        test_script = [
            f"pm.test('Status {tc['expected']}', function () {{",
            f"  pm.response.to.have.status({tc['expected']});",
            "});",
            "",
            "// Capture token from response if available",
            "try {",
            "  var jsonData = pm.response.json();",
            "  ",
            "  // Look for token in various common locations",
            "  var token = jsonData.token || jsonData.accessToken || jsonData.access_token || ",
            "              (jsonData.data && (jsonData.data.token || jsonData.data.accessToken)) ||",
            "              (jsonData.auth && jsonData.auth.token);",
            "  ",
            "  if (token) {",
            "    pm.collectionVariables.set('authToken', token);",
            "    console.log('Token captured and saved');",
            "  }",
            "  ",
            "  // Also capture user info if this is a register/login endpoint",
            "  if (jsonData.user || jsonData.username) {",
            "    var user = jsonData.user || jsonData;",
            "    if (user.username) pm.collectionVariables.set('testUsername', user.username);",
            "    if (user.id) pm.collectionVariables.set('userId', user.id);",
            "  }",
            "} catch(e) {",
            "  // Response is not JSON, check headers for token",
            "  var authHeader = pm.response.headers.get('Authorization');",
            "  if (authHeader) {",
            "    pm.collectionVariables.set('authToken', authHeader.replace('Bearer ', ''));",
            "  }",
            "}"
        ] if is_token_endpoint(path, name) else [
            f"pm.test('Status {tc['expected']}', function () {{",
            f"  pm.response.to.have.status({tc['expected']});",
            "});"
        ]
        
        item = {
            "name": tc["name"],
            "request": {
                "method": method,
                "header": headers,
                "url": {
                    "raw": "{{baseUrl}}" + path,
                    "host": ["{{baseUrl}}"],
                    "path": [p for p in path.split("/") if p]
                }
            },
            "event": [{
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": test_script
                }
            }]
        }
        
        # Add body if present
        if request_body:
            item["request"]["body"] = request_body
        
        items.append(item)

    collection = {
        "info": {
            "_postman_id": str(uuid.uuid4()),
            "name": "Generated Collection",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "item": items,
        "variable": [
            {
                "key": "baseUrl",
                "value": base_url,
                "type": "string"
            },
            {
                "key": "authToken",
                "value": "",
                "type": "string"
            },
            {
                "key": "testUsername",
                "value": "testuser",
                "type": "string"
            },
            {
                "key": "testPassword", 
                "value": "TestPassword123!",
                "type": "string"
            },
            {
                "key": "userId",
                "value": "",
                "type": "string"
            }
        ]
    }

    return collection