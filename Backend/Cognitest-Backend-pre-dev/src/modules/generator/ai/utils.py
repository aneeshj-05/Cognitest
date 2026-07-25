from typing import Any

def prune_schema_for_ai(schema: Any) -> Any:
    """
    Remove unnecessary fields from a JSON schema to reduce token usage
    while keeping the structural definition intact for AI.
    """
    if isinstance(schema, list):
        return [prune_schema_for_ai(item) for item in schema]
    
    if not isinstance(schema, dict):
        return schema
    
    # Fields to keep
    keep_keys = {
        "type", "properties", "items", "required", "enum", 
        "format", "minimum", "maximum", "minLength", "maxLength",
        "pattern", "additionalProperties", "allOf", "anyOf", "oneOf",
        "$ref"
    }
    
    pruned = {}
    for k, v in schema.items():
        if k in keep_keys:
            pruned[k] = prune_schema_for_ai(v)
            
    return pruned
