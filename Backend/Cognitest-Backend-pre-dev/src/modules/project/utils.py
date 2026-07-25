import json
import re
from typing import Any
from prisma import Json as PrismaJson

def _strip_null_bytes(obj: Any) -> Any:
    """
    Recursively replace null bytes (\\u0000) in all string values.

    PostgreSQL text and JSONB columns cannot store \\u0000 (null byte) characters.
    Fuzz test cases legitimately contain null bytes in their payloads as adversarial
    inputs. We replace them with the printable marker '[NULL]' so the intent is
    preserved and the record is still storable.
    """
    if isinstance(obj, str):
        return obj.replace("\u0000", "[NULL]")
    if isinstance(obj, dict):
        return {k: _strip_null_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_strip_null_bytes(item) for item in obj]
    return obj


def sanitize_json(data, default=None):
    """Force-sanitize data through JSON roundtrip and wrap with PrismaJson for Prisma Json fields.
    
    Also strips null bytes (\\u0000) which PostgreSQL cannot store in text/JSONB columns.
    This is especially important for fuzz test payloads which use null bytes as adversarial inputs.

    Returns PrismaJson(default) if data is None/empty to satisfy Prisma's required Json fields.
    Use default=[] for list fields, default={} for dict fields.
    """
    if data is None:
        if default is not None:
            return PrismaJson(default)
        return None
    try:
        # Strip null bytes BEFORE roundtrip — PostgreSQL rejects \u0000 in text/JSONB
        cleaned = _strip_null_bytes(data)
        clean = json.loads(json.dumps(cleaned, default=str))
        return PrismaJson(clean)
    except (TypeError, ValueError):
        if default is not None:
            return PrismaJson(default)
        return None


def substitute_path_params(path_template: str, path_params: dict[str, Any] | None) -> str:
    rendered = (path_template or "/")
    for k, v in (path_params or {}).items():
        rendered = rendered.replace("{" + str(k) + "}", str(v))

    # Final safety: Convert any remaining literal {id} to {{id}} as requested
    rendered = re.sub(r"\{([a-zA-Z0-9_-]+)\}", r"{{\1}}", rendered)
    return rendered

def normalize_test_category(cat: str, default: str = "FUNCTIONAL") -> str:
    if not cat:
        return default
    cat = cat.upper().strip()
    # Valid Prisma TestCategory enum values — pass through directly
    if cat in ("FUNCTIONAL", "NEGATIVE", "CONTRACT", "SECURITY", "FUZZ"):
        return cat
    # Common aliases
    if cat in ("FUNC",): return "FUNCTIONAL"
    if cat in ("NEG",): return "NEGATIVE"
    if cat in ("CON",): return "CONTRACT"
    if cat in ("SEC",): return "SECURITY"
    # Internal engine sub-labels that belong to FUNCTIONAL
    if cat in ("WORKFLOW", "CRUD", "SCHEMA", "PARAMS", "PARAM",
               "PAGINATION", "FILTERING", "SORTING", "VALIDATION",
               "AUTH", "CHAINING", "WORKFLOW_CHAINING",
               "PERFORMANCE", "LOAD"):
        return "FUNCTIONAL"
    # Internal engine sub-labels that belong to NEGATIVE
    if cat in ("NEG_PARAMS", "MISSING", "INVALID", "PARAMS"):
        return "NEGATIVE"
    return default

def normalize_test_sub_category(sub: str, default: str = "CRUD_VALIDATION") -> str:
    if not sub:
        return default
    sub = sub.upper().strip().replace(" ", "_")
    
    # Valid Prisma Enum Values (as of current schema)
    valid_enums = {
        "CRUD_VALIDATION", "SCHEMA_VALIDATION", "QUERY_PARAM_TEST", "HEADER_TEST",
        "COOKIE_TEST", "PATH_PARAM_TEST", "WORKFLOW_CHAINING", "PAGINATION",
        "FILTERING", "SORTING", "INVALID_PARAMS", "MISSING_PARAMS",
        "INVALID_AUTH", "EXPIRED_TOKEN", "UNSUPPORTED_METHOD", "INCORRECT_DATA_TYPE",
        "INVALID_ENUM", "SQL_INJECTION", "NOSQL_INJECTION", "XSS_INJECTION",
        "COMMAND_INJECTION", "BOLA", "EXCESSIVE_DATA_EXPOSURE", "SECURITY_MISCONFIGURATION",
        "REPLAY_ATTACK", "BRUTE_FORCE", "TOKEN_THEFT", "TOKEN_MANIPULATION",
        "TLS_SSL_ENFORCEMENT", "OPENAPI_CONFORMANCE", "SCHEMA_DRIFT", "BACKWARD_COMPATIBILITY",
        "RANDOM_STRING", "UNICODE_INPUT", "LONG_INPUT", "XSS_FUZZ",
        "PATH_TRAVERSAL", "PAYLOAD_INJECTION"
    }

    if sub in valid_enums:
        return sub
    
    # Mapping for common engine-emitted strings to Prisma enum values
    mapping = {
        "MISSING_REQUIRED": "MISSING_PARAMS",
        "UNAUTHORIZED": "INVALID_AUTH",
        "METHOD_CONFUSION": "UNSUPPORTED_METHOD",
        "QUERY_FUZZ": "QUERY_PARAM_TEST",
        "PATH_FUZZ": "PATH_PARAM_TEST",
        "BOUNDARY_VALUE": "INVALID_PARAMS",
        "TYPE_MISMATCH": "INCORRECT_DATA_TYPE",
        "ENUM_VIOLATION": "INVALID_ENUM",
        "INVALID_FORMAT": "INVALID_PARAMS",
        "EXTRA_FIELDS": "SCHEMA_VALIDATION",
        "MALFORMED_JSON": "SCHEMA_VALIDATION",
        "DATA_EXPOSURE": "EXCESSIVE_DATA_EXPOSURE",
    }
    
    return mapping.get(sub, default)
