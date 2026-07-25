"""
Negative Test Service Module

Centralizes all negative test related logic including:
- Auth failure handling (missing, invalid, expired tokens)
- Status code evaluation and classification
- Expected status building for negative test cases
- Token mutation utilities
- Legacy negative test compatibility

This module was extracted from:
- execution_service.py (src/modules/project/services/)
- generation_service.py (src/modules/project/services/)

to eliminate merge conflicts and improve code organization.
"""

import json
import logging
import re
from typing import Any, Optional

from src.modules.generator.engines.negative.core import TokenMutator

logger = logging.getLogger(__name__)

# Standard error statuses for negative tests
STANDARD_ERROR_STATUSES = {400, 401, 403, 404, 405, 409, 415, 422, 429}

# OWASP category display labels
CATEGORY_LABEL = {
    "Injection": "4.1  Injection",
    "Auth": "4.2  Authentication",
    "BOLA": "4.3  BOLA / IDOR",
    "Exposure": "4.4  Excessive Data Exposure",
    "RateLimit": "4.5  Rate Limiting",
    "VerbTamper": "4.6  Verb Tampering",
    "TLS": "4.7  TLS / SSL",
    "Misconfiguration": "4.8  Misconfiguration",
    "WrongRole": "Privilege Escalation",
}


def classify_status(code: int) -> str:
    """Classify HTTP status code into failure category."""
    if code == 401:
        return "auth"
    if code == 422:
        return "validation"
    if code == 400:
        return "schema"
    if code == 404:
        return "not_found"
    if code == 429:
        return "rate_limit"
    return "unknown"


def default_reason_for_status(status: int) -> str:
    """Get default human-readable reason for HTTP status code."""
    return {
        400: "Malformed request body",
        401: "Unauthorized",
        403: "Access Denied",
        404: "Resource not found",
        422: "Validation failure",
        429: "Rate limit exceeded",
    }.get(status, f"HTTP {status}")


def category_error_label(category: str) -> str:
    """Get display label for failure category."""
    return {
        "validation": "validation error",
        "auth": "auth error",
        "schema": "schema error",
        "rate_limit": "rate_limit error",
        "not_found": "not_found error",
        "unknown": "unknown error",
    }.get(category, f"{category} error")


def derive_failure_category(statuses: list[int], explicit: Any = None) -> str:
    """
    Derive failure category from expected statuses or explicit marker.
    
    Args:
        statuses: List of expected HTTP status codes
        explicit: Explicit failure category if provided
        
    Returns:
        Failure category string (validation, auth, not_found, rate_limit, schema, or empty)
    """
    valid = {"validation", "auth", "schema", "rate_limit", "not_found"}
    explicit_val = str(explicit or "").strip().lower()
    if explicit_val in valid:
        return explicit_val
    if not statuses:
        return ""
    if 422 in statuses:
        return "validation"
    if 401 in statuses:
        return "auth"
    if 404 in statuses:
        return "not_found"
    if 429 in statuses:
        return "rate_limit"
    if 400 in statuses:
        return "schema"
    if any(code >= 400 for code in statuses):
        return "schema"
    return ""


def db_expected_status_value(value: Any) -> int:
    """
    Extract expected status value from various formats.
    Handles dict, list, and primitive types.
    """
    if isinstance(value, dict):
        value = value.get("status")
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                item = item.get("status")
            try:
                return int(item)
            except (TypeError, ValueError):
                continue
        return 200
    try:
        return int(value)
    except (TypeError, ValueError):
        return 200


def single_expected_status(expected_statuses: list[int], actual: int, fallback: Any) -> Any:
    """Get single expected status for display purposes."""
    if expected_statuses:
        return actual if actual in expected_statuses else expected_statuses[0]
    return db_expected_status_value(fallback)


def build_expected_entries(
    case: dict[str, Any],
    meta: dict[str, Any],
    contract_meta: dict[str, Any],
    expected: Any,
) -> tuple[list[dict[str, Any]], list[int], list[str], str]:
    """
    Build expected status entries from case metadata.
    
    Returns:
        Tuple of (entries, expected_statuses, expected_statuses_str, failure_category)
    """
    raw_expected = case.get("expected") or meta.get("expected")
    entries: list[dict[str, Any]] = []
    extra_status_tokens: list[str] = []

    if isinstance(raw_expected, list):
        for item in raw_expected:
            if not isinstance(item, dict):
                continue
            status_raw = item.get("status")
            try:
                status = int(status_raw)
            except (TypeError, ValueError):
                token = str(status_raw).strip()
                if token:
                    extra_status_tokens.append(token)
                continue
            reason = str(item.get("reason") or "").strip()
            entries.append({"status": status, "reason": reason})

    if not entries:
        expected_statuses_raw = meta.get("expected_statuses") or contract_meta.get("expected_statuses")
        if not expected_statuses_raw and isinstance(case.get("expected_status"), list):
            expected_statuses_raw = case["expected_status"]
        if not expected_statuses_raw and isinstance(expected, list):
            expected_statuses_raw = expected

        if not expected_statuses_raw:
            legacy_expected_statuses = legacy_negative_expected_statuses(case, expected)
            if legacy_expected_statuses:
                expected_statuses_raw = legacy_expected_statuses

        if not expected_statuses_raw:
            expected_statuses_raw = [expected]

        if not isinstance(expected_statuses_raw, list):
            expected_statuses_raw = [expected_statuses_raw]

        for raw in expected_statuses_raw:
            try:
                status = int(raw)
            except (TypeError, ValueError):
                token = str(raw).strip()
                if token:
                    extra_status_tokens.append(token)
                continue
            entries.append({"status": status, "reason": ""})

    for entry in entries:
        if not entry.get("reason"):
            entry["reason"] = default_reason_for_status(int(entry["status"]))

    expected_statuses = [int(entry["status"]) for entry in entries]
    failure_category = derive_failure_category(
        expected_statuses,
        case.get("failure_category") or meta.get("failure_category"),
    )
    expected_statuses_str = [str(entry["status"]) for entry in entries]
    for token in extra_status_tokens:
        if token not in expected_statuses_str:
            expected_statuses_str.append(token)
    return entries, expected_statuses, expected_statuses_str, failure_category


def legacy_negative_expected_statuses(case: dict[str, Any], expected: Any) -> list[int]:
    """
    Backward compatibility for older NEGATIVE/FUZZ test cases.
    
    Older tests were stored with only expected_status=400 without metadata.expected_statuses.
    FastAPI/Pydantic-style validation commonly returns 422 for these scenarios.
    Header/content-type negatives may also return 415.
    """
    if expected != 400:
        return []

    def _enumish_upper(value: Any) -> str:
        if hasattr(value, "value"):
            value = value.value
        elif hasattr(value, "name") and not isinstance(value, str):
            value = value.name
        txt = str(value or "").upper()
        if "." in txt:
            txt = txt.rsplit(".", 1)[-1]
        return txt

    category = _enumish_upper(case.get("category"))
    test_type = _enumish_upper(case.get("test_type"))
    if category not in {"NEGATIVE", "FUZZ"} and test_type not in {"NEGATIVE", "FUZZ"}:
        return []

    sub_category = _enumish_upper(case.get("sub_category") or case.get("subCategory"))
    validation_like_subcategories = {
        "MISSING_PARAMS",
        "INCORRECT_DATA_TYPE",
        "INVALID_ENUM",
        "INVALID_PARAMS",
        "QUERY_PARAM_TEST",
        "INVALID_QUERY_PARAMS",
        "HEADER_TEST",
        "INVALID_HEADERS",
        "SCHEMA_VALIDATION",
        "CRUD_VALIDATION",
        "RANDOM_STRING",
        "UNICODE_INPUT",
        "LONG_INPUT",
    }
    if sub_category and sub_category not in validation_like_subcategories:
        return []

    if sub_category in {"HEADER_TEST", "INVALID_HEADERS"}:
        return [400, 415, 422]

    return [400, 422]


def contract_allowed_status(expected_statuses_str: str, actual: int, kind: str) -> bool:
    """
    Check if actual status code is allowed given expected statuses.
    
    Args:
        expected_statuses_str: Comma-separated string of expected statuses
        actual: Actual HTTP status code received
        kind: Test kind (positive/negative)
        
    Returns:
        True if status is allowed, False otherwise
    """
    if not expected_statuses_str:
        return True

    # Handle both list and comma-separated string
    if isinstance(expected_statuses_str, list):
        expected = {str(s).strip() for s in expected_statuses_str}
    else:
        expected = {s.strip() for s in str(expected_statuses_str).split(",")}

    if "default" in expected:
        if 500 <= actual <= 599:
            return True

    if kind.startswith("negative"):
        if kind == "negative_auth_missing":
            return actual in (401, 403)
        return actual in STANDARD_ERROR_STATUSES

    if str(actual) in expected:
        return True

    # Class-level match (e.g. 201 matches 2xx)
    for s in expected:
        if s.isdigit() and int(s) // 100 == actual // 100:
            return True

    return False


def evaluate_pass_fail(expected: Any, actual: int, case: dict) -> bool:
    """
    Evaluate if actual status passes given expected status and case metadata.
    
    Handles OWASP categories and special cases like BOLA, WrongRole, etc.
    """
    if isinstance(expected, list):
        return actual in expected
    if actual == expected:
        return True
    
    test_name = case.get("name", "").lower()
    owasp = case.get("owasp_category", "")
    if owasp == "BOLA" or "bola" in test_name:
        return actual in (403, 404)
    if owasp == "WrongRole" or "privilege" in test_name:
        return actual in (403, 401)
    if owasp == "Injection" or any(k in test_name for k in ("injection", "xss", "sql", "command")):
        return actual in (400, 401, 403, 404, 409, 415, 422)
    if owasp == "VerbTamper":
        return actual in (404, 405, 410)
    if owasp == "TLS" and expected == 301:
        return actual in (200, 301, 302, 404)
    if owasp in ("Misconfiguration",) and expected == 200:
        return actual in (200, 404)
    
    return False


# ============================================================================
# Auth Token Handling Functions
# ============================================================================

def normalize_token(token: str | None) -> str | None:
    """Normalize auth token by stripping Bearer prefix if present."""
    if token is None:
        return None
    t = str(token).strip()
    if not t:
        return None
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t or None


def find_header_key(headers: dict[str, Any], name: str) -> str | None:
    """Find header key case-insensitively."""
    target = name.lower()
    for key in headers:
        if str(key).lower() == target:
            return str(key)
    return None


def remove_header_case_insensitive(headers: dict[str, Any], name: str) -> None:
    """Remove header by name case-insensitively."""
    target = name.lower()
    for key in list(headers.keys()):
        if str(key).lower() == target:
            headers.pop(key, None)


def upsert_authorization_header(headers: dict[str, Any], token: str) -> None:
    """
    Upsert Authorization header with Bearer token.
    
    Handles various edge cases:
    - Adds new header if none exists
    - Replaces placeholder tokens ({{...}})
    - Replaces empty/invalid tokens
    """
    normalized = normalize_token(token)
    if not normalized:
        return

    auth_key = find_header_key(headers, "Authorization")
    if auth_key is None:
        headers["Authorization"] = f"Bearer {normalized}"
        return

    existing = str(headers.get(auth_key) or "").strip()
    should_replace = (
        not existing
        or "{{" in existing
        or existing.lower() in {"bearer", "none", "null", "undefined"}
    )
    if should_replace:
        headers[auth_key] = f"Bearer {normalized}"


def auth_header_present(headers: dict[str, Any]) -> bool:
    """Check if Authorization header is present and non-empty."""
    auth_key = find_header_key(headers, "Authorization")
    if auth_key is None:
        return False
    return bool(str(headers.get(auth_key) or "").strip())


def mask_auth_header(headers: dict[str, Any]) -> dict[str, Any]:
    """Mask Authorization header for safe logging/display."""
    masked = dict(headers or {})
    auth_key = find_header_key(masked, "Authorization")
    if auth_key:
        raw = str(masked.get(auth_key) or "").strip()
        token = raw[7:].strip() if raw.lower().startswith("bearer ") else raw
        suffix = token[-4:] if token else ""
        masked[auth_key] = f"Bearer ****{suffix}" if suffix else "Bearer ****"
    return masked


def resolve_auth_type(case: dict[str, Any]) -> str:
    """
    Resolve auth type from case metadata.
    
    Returns one of: "", "missing", "invalid", "expired"
    """
    raw = str(case.get("auth_type") or "").strip().lower()
    if raw:
        return raw

    metadata = case.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    if isinstance(metadata, dict):
        raw = str(metadata.get("auth_type") or "").strip().lower()
        if raw:
            return raw

    # Check for auth-negative markers
    auth_marker = (
        str(case.get("sub_category") or case.get("subCategory") or "").upper() == "AUTH_FAILURE"
        or str(case.get("mutation_type") or (metadata.get("mutation_type") if isinstance(metadata, dict) else "") or "").upper() in {"AUTH_MISSING", "AUTH_INVALID"}
        or bool(case.get("auth_negative") or (metadata.get("auth_negative") if isinstance(metadata, dict) else False))
        or "missing auth token" in str(case.get("name") or "").lower()
        or "invalid auth token" in str(case.get("name") or "").lower()
        or "expired auth token" in str(case.get("name") or "").lower()
    )
    if not auth_marker:
        return ""

    name = str(case.get("name") or "").lower()
    description = str(case.get("description") or "").lower()
    if "expired" in name or "expired" in description:
        return "expired"
    if "invalid" in name or "invalid" in description:
        return "invalid"
    return "missing"


# ============================================================================
# Token Mutation Functions
# ============================================================================

def apply_auth_mutation(headers: dict[str, Any], auth_type: str) -> None:
    """
    Apply auth token mutation based on auth_type.
    
    Args:
        headers: Request headers dict (mutated in place)
        auth_type: One of "missing", "invalid", "expired"
    """
    if auth_type == "missing":
        remove_header_case_insensitive(headers, "Authorization")
    elif auth_type == "invalid":
        headers["Authorization"] = TokenMutator.malformed()["Authorization"]
    elif auth_type == "expired":
        headers["Authorization"] = TokenMutator.expired()["Authorization"]


def get_mutated_auth_header(auth_type: str) -> dict[str, str]:
    """
    Get mutated auth header for testing.
    
    Returns:
        Dict with Authorization header containing mutated token
    """
    if auth_type == "invalid":
        return TokenMutator.malformed()
    elif auth_type == "expired":
        return TokenMutator.expired()
    return {}


# ============================================================================
# Contract Meta Extraction
# ============================================================================

def extract_contract_meta(case: dict[str, Any]) -> dict[str, Any]:
    """
    Best-effort extraction of strict contract metadata.
    
    Contract tests are generated with extra fields like `expected_statuses`,
    `security_required`, and `auth_negative`, but those fields are not part of
    the DB model and can be lost after persistence.
    
    To keep the UI/runner compatible, we persist a compact JSON blob in the
    `assertions` string list and rehydrate it here.
    """
    meta: dict[str, Any] = {}

    # Direct fields (in-memory draft cases before persistence)
    if isinstance(case.get("expected_statuses"), list):
        meta["expected_statuses"] = case.get("expected_statuses")
    if "security_required" in case:
        meta["security_required"] = bool(case.get("security_required"))
    if "auth_negative" in case:
        meta["auth_negative"] = bool(case.get("auth_negative"))
    if "kind" in case:
        meta["kind"] = case.get("kind")
    if "operation_key" in case:
        meta["operation_key"] = case.get("operation_key")

    # Rehydrate from persisted assertions
    assertions = case.get("assertions")
    if isinstance(assertions, list):
        for a in assertions:
            if not isinstance(a, str):
                continue
            if a.startswith("__contract_meta__="):
                try:
                    meta.update(json.loads(a.split("=", 1)[1]))
                except Exception:
                    pass
                break

    return meta


# ============================================================================
# Generation Service Helpers
# ============================================================================

def derive_failure_category_for_generation(statuses: list[int], explicit: Any = None) -> str:
    """
    Derive failure category for test generation (alias for backward compatibility).
    """
    return derive_failure_category(statuses, explicit)


def default_reason_for_status_code(status: int) -> str:
    """Alias for default_reason_for_status for backward compatibility."""
    return default_reason_for_status(status)


def classify_status_code(code: int) -> str:
    """Alias for classify_status for backward compatibility."""
    return classify_status(code)
