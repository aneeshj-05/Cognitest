import re
from typing import Any
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

SENSITIVE_KEYS = {
    "token", "api_key", "apikey", "key", "password", 
    "secret", "auth", "authorization", "client_secret",
    "access_token", "refresh_token", "pass", "pwd", "session"
}

def is_sensitive_key(key: str) -> bool:
    key_lower = key.lower()
    return any(sens in key_lower for sens in SENSITIVE_KEYS)

def redact_url(url: str) -> str:
    """Parse URL and redact sensitive query parameters."""
    if not url:
        return url
        
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
            
        # Parse query params, keeping blank values
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        redacted_params = []
        
        for k, v in query_params:
            if is_sensitive_key(k):
                redacted_params.append((k, "***REDACTED***"))
            else:
                redacted_params.append((k, v))
                
        # Reconstruct URL
        new_query = urlencode(redacted_params)
        new_parsed = parsed._replace(query=new_query)
        return urlunparse(new_parsed)
    except Exception:
        # If parsing fails, fall back to regex replacement as a safety net
        return re.sub(r'([?&])([^=]*token[^=&]*)=([^&]*)', r'\1\2=***REDACTED***', url, flags=re.IGNORECASE)


def redact_dict(data: dict | None) -> dict | None:
    """Recursively redact sensitive values in a dictionary."""
    if not data or not isinstance(data, dict):
        return data
        
    redacted = {}
    for k, v in data.items():
        if isinstance(k, str) and is_sensitive_key(k):
            redacted[k] = "***REDACTED***"
        elif isinstance(v, dict):
            redacted[k] = redact_dict(v)
        elif isinstance(v, list):
            redacted[k] = [redact_dict(item) if isinstance(item, dict) else item for item in v]
        else:
            redacted[k] = v
            
    return redacted

def redact_request_data(req: dict[str, Any]) -> dict[str, Any]:
    """
    Redact sensitive info from a structured request dictionary containing 
    'url', 'headers', 'body', etc.
    """
    if not req:
        return req
        
    result = req.copy()
    
    if "url" in result and isinstance(result["url"], str):
        result["url"] = redact_url(result["url"])
        
    if "headers" in result and isinstance(result["headers"], dict):
        result["headers"] = redact_dict(result["headers"])
        
    if "body" in result and isinstance(result["body"], dict):
        result["body"] = redact_dict(result["body"])
        
    return result
