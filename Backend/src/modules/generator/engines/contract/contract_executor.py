from __future__ import annotations

"""
Contract Executor — Production-grade, schema-driven, deterministic.

================================================================================
RESPONSIBILITIES (the full lifecycle this module owns)
================================================================================

1. INPUT INTAKE
   - Receives an ordered list of test cases produced by `contract_generator`.
   - Receives the canonical OpenAPI spec (so the validator can find the matching
     operation per test case).
   - Sorts test cases strictly by `execution_order` (already topologically
     ordered by the generator) — never re-orders.

2. EXECUTION CONTEXT (single source of state for the run)
   The executor maintains ONE `execution_context` dict that holds:
       * entities[resource_key] -> [ {id, raw, flat, ...}, ... ]
            Producers populate; consumers read via `tc.dependency_map`.
            `resource_key` always comes from the generator (NEVER guessed
            from the path).
       * token / auth_token            captured from a successful login
       * auth_type                     'bearer' | 'cookie' | None
       * cookie_name                   raw cookie name when session-based
       * auth_user                     {email,password} from signup, replayed
                                        on login.
       * phase                         pass1 | pass2 | pass3
       * current_path                  path of the currently executing test

3. AUTH BOOTSTRAP (optional)
   - If the suite has positive secured routes AND a login endpoint exists in
     the suite, the executor performs an internal signup→login (or just login)
     to bootstrap a token before pass1. Tokens are sourced from response body
     OR Authorization header OR Set-Cookie — schema-aware, never hardcoded.

4. PER-TEST EXECUTION (`_run_one`)
   For every test case, in order:

   a) Resolve canonical operation (`operation_key` -> spec.operations[op_key]).
   b) Pre-flight mutations driven by `tc.kind` and `tc.mutation_meta`:

         negative_auth_missing           -> strip Authorization/Cookie
         negative_required_missing       -> remove `missing_field` (path/query/
                                            header/body) AND prevent dep_map
                                            from re-filling it.
         negative_format_invalid         -> set `format_field` to
                                            `invalid_value_for_format(format)`
                                            from contract_rules.
         negative_*_type_invalid         -> swap value with a wrong type.
         negative_*_enum_invalid         -> generator already emitted the
                                            invalid enum value; trust it.
         negative_pattern, negative_min*/
         negative_max*, negative_min_items,
         negative_max_items              -> generator emitted the invalid
                                            value; trust it.
         negative_additional_properties  -> generator emitted extras; trust it.
         negative_not_found              -> replace path IDs with synthetic
                                            non-existent values (UUID/ObjectId/
                                            numeric/string-aware).
         403 Forbidden                   -> swap path ID with one from a
                                            foreign resource bucket.

   c) DEPENDENCY INJECTION (single source of truth = `tc.dependency_map`):
        * Path placeholders: every {ph} must have an entry in dep_map AND a
          matching producer entity in `execution_context.entities[source]`.
        * Body fields with id-like leaf names: inject by dotted path.
        * Query parameters: inject if param name is present in `tc.request_query`.
        * For `negative_required_missing` / `negative_*_required_missing`, the
          target field is added to a "skip-injection" set so dep_map does not
          re-fill it.

   d) AUTH INJECTION:
        * Skip for auth endpoints (login/signup) and for `negative_auth_missing`.
        * Inject Bearer for positive secured routes when a token is present.
        * Inject Cookie when session-based auth was captured at login.

   e) HTTP REQUEST (sequential, with httpx). Optional 503-retry, idempotent
      retry on RequestError.

   f) RESPONSE CAPTURE:
        * If status is 2xx and `tc.is_producer_endpoint`/`produces_entity`,
          extract IDs using `produced_id_paths` (preferred) or universal walk
          (fallback). Bucket entities under `tc.resource_key` ONLY.
        * If path looks like login/signup (or generator marked
          is_auth_endpoint=true) and 2xx, capture token from JSON / header /
          Set-Cookie.

   g) VALIDATION via `validate_exchange(operation, test_case, exchange)` from
      `contract_validator`. The streamed result includes `violations`, and
      `passed = (len(violations) == 0)`. Status-code-only matching is no
      longer the source of truth.

   h) Build the result dict (full request/response/exchange/violations/status).

5. EXECUTION STRATEGY
   - PASS 1: non-destructive tests (everything except DELETE).
   - PASS 2: retry tests skipped because of missing dependencies (entities may
     have become available after later producers ran).
   - PASS 3: destructive (DELETE) tests last so previously created entities
     remain available for PASS 1/2.

6. RUN-LEVEL OUTPUT
   - Coverage (statuses, methods, schemas validated, content_types, headers).
   - `detect_wrong_server` heuristic.
   - Persists suite + cases + results + violations (best-effort, tolerates a
     missing/unhealthy DB).
   - Confidence score.

NO HARDCODED RESOURCE NAMES.  NO PATH-BASED RESOURCE INFERENCE.  All resource
identity flows from `resource_key` and `dependency_map` produced by the
generator. The only schema-derived inference is a last-resort fallback when a
resource_key is missing (single-segment singularization) — kept off the
critical path.
================================================================================
"""

import asyncio
import base64
import copy
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from src.utils.redact import redact_request_data
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict  # type: ignore

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Optional Prisma layer (best-effort persistence — must not break runs).
# ─────────────────────────────────────────────────────────────────────────────
try:
    from prisma.types import Json as PrismaJson  # type: ignore
except Exception:  # pragma: no cover
    try:
        from prisma import Json as PrismaJson  # type: ignore
    except Exception:  # pragma: no cover
        def PrismaJson(x):  # type: ignore
            return x

try:
    from src.config import prisma  # type: ignore
    from src.services.prisma_compat import (  # type: ignore
        create_testsuite_compat,
        normalize_test_category,
    )
    _PRISMA_AVAILABLE = True
except Exception:  # pragma: no cover
    prisma = None  # type: ignore
    create_testsuite_compat = None  # type: ignore
    normalize_test_category = None  # type: ignore
    _PRISMA_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Sibling modules.
# ─────────────────────────────────────────────────────────────────────────────
from .contract_rules import (  # noqa: E402
    UNIQUE_FORMAT_VALUES,
    invalid_value_for_format,
    normalize_content_type,
    reset_unique_cache,
    valid_value_for_format,
)
from .contract_generator import (  # noqa: E402
    coerce_canonical_spec,
    generate_contract_test_cases,
)
from .contract_validator import detect_wrong_server, validate_exchange  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Configuration (env-driven; safe production defaults).
# ─────────────────────────────────────────────────────────────────────────────
def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "y", "on"}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)) or default)
    except Exception:
        return default


def _int_env(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default)) or default))
    except Exception:
        return default


DEBUG = _truthy_env("COGNITEST_EXECUTOR_DEBUG", "0")
DEBUG_DEPENDENCY = _truthy_env("COGNITEST_DEBUG_DEPENDENCY", "0")
DEBUG_AUTH = _truthy_env("COGNITEST_DEBUG_AUTH", "0")
STRICT_MODE = _truthy_env("COGNITEST_STRICT_MODE", "0")  # default permissive: fall back to inference if dep_map empty
AUTO_AUTH_BOOTSTRAP = _truthy_env("COGNITEST_AUTO_AUTH_BOOTSTRAP", "1")
AUTO_AUTH_BOOTSTRAP_ALLOW_SIGNUP = _truthy_env("COGNITEST_AUTO_AUTH_BOOTSTRAP_ALLOW_SIGNUP", "1")
ENABLE_PASS2_RETRY = _truthy_env("COGNITEST_ENABLE_PASS2_RETRY", "1")

REQUEST_DELAY = _float_env("REQUEST_DELAY", 0.0)
PACING_BASE_S = _float_env("COGNITEST_REQUEST_PACING_SECONDS", 0.0)
PACING_STRESSED_S = _float_env("COGNITEST_REQUEST_PACING_STRESSED_SECONDS", 0.5)
RETRY_503_ATTEMPTS = _int_env("COGNITEST_RETRY_503_ATTEMPTS", 1)
RETRY_503_SLEEP_S = _float_env("COGNITEST_RETRY_503_SLEEP_SECONDS", 1.0)
RETRY_IDEMPOTENT = _int_env("COGNITEST_HTTP_RETRIES_IDEMPOTENT", 1)
RETRY_NON_IDEMPOTENT = _int_env("COGNITEST_HTTP_RETRIES_NON_IDEMPOTENT", 0)
RETRY_PRODUCER_EXTRA = _int_env("COGNITEST_HTTP_RETRIES_PRODUCER_EXTRA", 1)

SENSITIVE_HEADERS = {"authorization", "x-api-key", "cookie"}
IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}

# Negative test kinds that take a "missing" approach — these MUST NOT have the
# missing field re-injected by the dependency-injection step.
_REQUEST_VALIDATION_NEGATIVES = frozenset({
    "negative_required_missing",
    "negative_query_required_missing",
    "negative_header_required_missing",
    "negative_cookie_required_missing",
    "negative_path_required_missing",
    "negative_query_type_invalid",
    "negative_path_type_invalid",
    "negative_query_enum_invalid",
    "negative_path_enum_invalid",
    "negative_header_enum_invalid",
    "negative_body_enum_invalid",
    "negative_additional_properties",
    "negative_min_items",
    "negative_max_items",
    "negative_min_length",
    "negative_max_length",
    "negative_pattern",
    "negative_minimum",
    "negative_maximum",
    "negative_format_invalid",
})

# ── Intent-aware injection policy (PART 1 — orchestration governance) ─────────
#
# The executor must ask "SHOULD this testcase receive this runtime state?"
# based on the generator's explicit `kind` label — not "CAN I inject?"
# based on derived heuristics like `is_negative`.
#
# Kinds where body-level dep_map injection MUST NOT run:
# The generator already crafted a specifically invalid body for these.
# Injecting producer entity values would corrupt the test's negative intent
# (e.g., auto-filling a required field that was intentionally removed).
_KINDS_NO_BODY_INJECTION: frozenset = frozenset({
    "negative_auth_missing",
    "negative_auth_invalid",
    "negative_auth_expired",
    "negative_auth_malformed",
    "negative_required_missing",
    "negative_query_required_missing",
    "negative_header_required_missing",
    "negative_cookie_required_missing",
    "negative_path_required_missing",
    "negative_format_invalid",
    "negative_query_type_invalid",
    "negative_path_type_invalid",
    "negative_query_enum_invalid",
    "negative_path_enum_invalid",
    "negative_header_enum_invalid",
    "negative_body_enum_invalid",
    "negative_pattern",
    "negative_min_length",
    "negative_max_length",
    "negative_minimum",
    "negative_maximum",
    "negative_min_items",
    "negative_max_items",
    "negative_additional_properties",
})

# Kinds that must have ALL auth stripped (not just absent — actively removed).
# All other negative kinds still receive a valid auth token because they are
# testing schema/format/constraint violations, not auth — they need authenticated
# state to reach the validation layer at all.
_KINDS_STRIP_AUTH: frozenset = frozenset({
    "negative_auth_missing",
    "negative_auth_invalid",
    "negative_auth_expired",
    "negative_auth_malformed",
})


def _kind_permits_body_injection(
    kind: str,
    is_404: bool,
    is_403: bool,
    is_negative: bool = False,
) -> bool:
    """Intent-aware body injection policy.

    Asks "Should this testcase receive producer body values from dep_map?"
    based on the generator's explicit kind label, falling back to the
    expected_status signal (is_negative) when kind is absent or unrecognised.

    Rules:
        - 404 tests always receive real bodies (only path ID becomes synthetic).
        - 403 tests always receive real bodies (only resource ownership changes).
        - Positive tests always receive injected values.
        - Explicitly listed negative kinds keep the generator's crafted body.
        - Any kind starting with "negative_" keeps the generator's body.
        - Unknown / empty kind: defer to is_negative from expected_status.
          If is_negative=True (expected_status >= 400), block injection so
          that real entity IDs cannot accidentally produce a valid body that
          the API accepts, masking the negative test's intent.
    """
    # 404/403 always need real bodies regardless of kind.
    if is_404 or is_403:
        return True

    # Explicit positive — always inject.
    if kind == "positive":
        return True

    # Explicitly listed validation-focused negatives — never inject.
    if kind in _KINDS_NO_BODY_INJECTION:
        return False

    # Any kind using the standard "negative_" prefix — never inject.
    if kind.startswith("negative_"):
        return False

    # Empty or non-standard kind: fall back to the expected_status signal.
    # This prevents real entity IDs from being injected into a test that is
    # semantically negative (expected_status >= 400) even when the generator
    # did not emit a recognised kind string.
    if not kind or is_negative:
        return False

    # Non-negative, non-empty, unrecognised kind — allow injection.
    return True


# =============================================================================
# SECTION 1 — Generic helpers
# =============================================================================
def _get_header_ci(headers: Dict[str, Any], name: str) -> Optional[str]:
    target = name.lower()
    for k, v in (headers or {}).items():
        if str(k).lower() == target:
            if isinstance(v, list) and v:
                return str(v[0])
            return None if v is None else str(v)
    return None


def _get_header_value_ci(headers: Dict[str, Any], name: str) -> Any:
    target = name.lower()
    for k, v in (headers or {}).items():
        if str(k).lower() == target:
            return v
    return None


def _pop_header_ci(headers: Dict[str, Any], name: str) -> None:
    target = name.lower()
    for k in list(headers.keys()):
        if str(k).lower() == target:
            headers.pop(k, None)


def _normalize_token(token: Optional[str]) -> Optional[str]:
    if token is None:
        return None
    t = str(token).strip()
    if not t:
        return None
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t or None


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<missing>"
    v = str(value)
    return "<set>" if len(v) <= 8 else f"{v[:4]}…{v[-4:]}"


def _masked_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    masked = dict(headers or {})
    for k in list(masked.keys()):
        if str(k).lower() in SENSITIVE_HEADERS:
            masked[k] = "********"
    return masked


def _normalize_entity_scalar(v: Any) -> Optional[Any]:
    """Filter values that look like valid entity IDs."""
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, int):
        return None if v == 0 else v
    if isinstance(v, float):
        if not v.is_integer():
            return None
        iv = int(v)
        return None if iv == 0 else iv
    if isinstance(v, str):
        sv = v.strip()
        if not sv or sv.lower() in {"null", "none", "0"}:
            return None
        return sv
    return None


def _is_id_like_name(name: str) -> bool:
    n = (name or "").lower()
    return n == "id" or n == "_id" or n.endswith("id") or n.endswith("_id") or n.endswith("uuid")


# Dotted path get/set/delete
def _get_by_dotted_path(obj: Any, dotted: str) -> Any:
    if dotted is None:
        return None
    cur = obj
    for part in [p for p in str(dotted).split(".") if p != ""]:
        if isinstance(cur, dict):
            if part not in cur:
                return None
            cur = cur[part]
        elif isinstance(cur, list):
            if not part.isdigit():
                return None
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        else:
            return None
    return cur


def _set_by_dotted_path(obj: Any, dotted: str, value: Any) -> bool:
    """Set an existing dotted path. Does NOT create missing intermediate keys."""
    if dotted is None:
        return False
    parts = [p for p in str(dotted).split(".") if p != ""]
    if not parts:
        return False
    cur = obj
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if isinstance(cur, dict):
            if last:
                if part not in cur:
                    return False
                cur[part] = value
                return True
            if part not in cur:
                return False
            cur = cur[part]
        elif isinstance(cur, list):
            if not part.isdigit():
                return False
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return False
            if last:
                cur[idx] = value
                return True
            cur = cur[idx]
        else:
            return False
    return False


def _delete_by_dotted_path(obj: Any, dotted: str) -> bool:
    """Remove a dotted-path leaf if present."""
    if dotted is None:
        return False
    parts = [p for p in str(dotted).split(".") if p != ""]
    if not parts:
        return False
    cur = obj
    for i, part in enumerate(parts):
        last = i == len(parts) - 1
        if isinstance(cur, dict):
            if part not in cur:
                return False
            if last:
                del cur[part]
                return True
            cur = cur[part]
        elif isinstance(cur, list):
            if not part.isdigit():
                return False
            idx = int(part)
            if idx < 0 or idx >= len(cur):
                return False
            if last:
                del cur[idx]
                return True
            cur = cur[idx]
        else:
            return False
    return False


def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dict/list into dotted-path keys."""
    res: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            res.update(_flatten(v, key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            key = f"{prefix}.{i}" if prefix else str(i)
            res.update(_flatten(v, key))
    else:
        res[prefix] = obj
    return res


def substitute_path_params(template: str, params: Dict[str, Any]) -> str:
    out = template or "/"
    for k, v in (params or {}).items():
        out = out.replace("{" + str(k) + "}", str(v))
    return out


def _path_placeholders(path_template: str) -> List[str]:
    return [str(n) for n in re.findall(r"\{([^}]+)\}", path_template or "")]


# =============================================================================
# SECTION 2 — Auth path heuristics (only used when generator does not mark it)
# =============================================================================
_LOGIN_KEYWORDS = ("/login", "/signin", "/sign-in", "/auth/login", "/auth/token", "/authenticate")
_SIGNUP_KEYWORDS = ("/signup", "/sign-up", "/register")


def _looks_like_login_path(path: str) -> bool:
    p = (path or "").lower()
    return any(k in p for k in _LOGIN_KEYWORDS)


def _looks_like_signup_path(path: str) -> bool:
    p = (path or "").lower()
    return any(k in p for k in _SIGNUP_KEYWORDS)


def _is_auth_endpoint(tc: Dict[str, Any]) -> bool:
    v = tc.get("is_auth_endpoint")
    if v is not None:
        return bool(v)
    p = str(tc.get("endpoint_path") or "")
    return _looks_like_login_path(p) or _looks_like_signup_path(p)


def _case_security_required(tc: Dict[str, Any]) -> bool:
    """Read security_required from the test case, with fallbacks."""
    for key in ("security_required", "requires_auth", "requiresAuth", "auth_required"):
        v = tc.get(key)
        if v is not None:
            return bool(v)
    hints = tc.get("execution_hints") or {}
    if isinstance(hints, dict):
        for key in ("requires_auth", "requiresAuth"):
            if key in hints:
                return bool(hints[key])
    return False


def _case_auth_negative(tc: Dict[str, Any]) -> bool:
    """True for tests that must run WITHOUT credentials (auth-negative intent).

    Intent-aware: `kind` is the primary authority.  The generator explicitly
    labels auth-testing tests so the executor never has to guess.  Legacy
    fallback flags (auth_negative, missing_auth, mutation_meta) are kept for
    backward compatibility with older generator output only.
    """
    # Kind-driven (authoritative) — explicit auth-negative variants.
    kind = str(tc.get("kind") or "").strip().lower()
    if kind in _KINDS_STRIP_AUTH:
        return True
    # Broader pattern: any kind the generator names with "negative_auth" prefix.
    if "negative_auth" in kind:
        return True

    # Legacy / backward-compat flags from older generator versions.
    if tc.get("auth_negative") is True:
        return True
    if tc.get("missing_auth") is True:
        return True
    test_type = str(tc.get("test_type") or "").strip().lower()
    if test_type in {"missing_auth", "missingauth", "auth_missing", "auth_negative"}:
        return True
    auth_type = str(tc.get("auth_type") or "").strip().lower()
    if auth_type in {"missing", "invalid", "expired"}:
        return True
    mm = tc.get("mutation_meta") or {}
    if isinstance(mm, dict) and (mm.get("auth_removed") or mm.get("no_auth")):
        return True
    return False


# =============================================================================
# SECTION 3 — Token & cookie extraction
# =============================================================================
_TOKEN_KEYS = ("access_token", "accessToken", "token", "id_token", "idToken", "jwt", "auth_token", "authToken")
_TOKEN_ENVELOPES = ("data", "session", "user", "auth", "result", "payload")


def _extract_token_from_json(payload: Any, depth: int = 4) -> Optional[str]:
    if payload is None or depth <= 0:
        return None
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, list):
        for item in payload:
            t = _extract_token_from_json(item, depth - 1)
            if t:
                return t
        return None
    if not isinstance(payload, dict):
        return None
    # Direct keys first
    for k in _TOKEN_KEYS:
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    # Common envelopes
    for env in _TOKEN_ENVELOPES:
        inner = payload.get(env)
        if isinstance(inner, (dict, list)):
            t = _extract_token_from_json(inner, depth - 1)
            if t:
                return t
    # Generic walk
    for v in payload.values():
        if isinstance(v, (dict, list)):
            t = _extract_token_from_json(v, depth - 1)
            if t:
                return t
    return None


def _extract_token_from_set_cookie(set_cookie: Any) -> Tuple[Optional[str], Optional[str]]:
    """Return (token, cookie_name) from Set-Cookie header(s)."""
    def _parse_one(s: str) -> Tuple[Optional[str], Optional[str]]:
        first = (s or "").split(";", 1)[0].strip()
        if not first or "=" not in first:
            return None, None
        name, value = first.split("=", 1)
        name = name.strip()
        value = value.strip().strip('"')
        if not value or not name:
            return None, None
        if name.lower() in {"access_token", "token", "jwt", "id_token", "session", "session_id"}:
            return value, name
        return None, None

    if set_cookie is None:
        return None, None
    if isinstance(set_cookie, list):
        for item in set_cookie:
            t, n = _parse_one(str(item))
            if t:
                return t, n
        return None, None
    return _parse_one(str(set_cookie))


def _capture_token_anywhere(resp_json: Any, response: httpx.Response) -> Tuple[Optional[str], Optional[str]]:
    """Return (token, source) where source ∈ {body, header, cookie}."""
    t = _normalize_token(_extract_token_from_json(resp_json))
    if t:
        return t, "body"
    t = _normalize_token(_get_header_ci(dict(response.headers), "Authorization"))
    if t:
        return t, "header"
    sc_list = response.headers.get_list("set-cookie") if hasattr(response.headers, "get_list") else None
    if not sc_list:
        sc_raw = response.headers.get("set-cookie")
        sc_list = [sc_raw] if sc_raw else []
    t, _ = _extract_token_from_set_cookie(sc_list)
    if t:
        return _normalize_token(t), "cookie"
    return None, None


# =============================================================================
# SECTION 4 — Producer entity extraction (schema-driven)
# =============================================================================
def _extract_value_at_id_path(payload: Any, dotted: str) -> Optional[Any]:
    """Resolve a `produced_id_paths` entry against a response.

    The generator emits paths relative to the success response schema. Examples:
        "id"            -> top-level scalar
        "data.id"       -> nested object
        "items.0.id"    -> array element

    For array responses we also accept the first element transparently.
    """
    if payload is None:
        return None
    if isinstance(payload, list) and payload:
        v = _get_by_dotted_path(payload[0], dotted)
        if v is not None:
            return _normalize_entity_scalar(v)
    v = _get_by_dotted_path(payload, dotted)
    return _normalize_entity_scalar(v)


def _walk_id_fields(payload: Any) -> List[Tuple[str, Any, Dict[str, Any]]]:
    """Universal fallback: walk a JSON response and collect (key, id, container_dict).

    Used ONLY when the generator did not provide `produced_id_paths`. The result
    is still bucketed under the test case's `resource_key`, so this is a safe
    additive fallback rather than a path-based guess.
    """
    out: List[Tuple[str, Any, Dict[str, Any]]] = []
    data = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else payload

    def walk(obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        for k, v in obj.items():
            if _is_id_like_name(k):
                nv = _normalize_entity_scalar(v)
                if nv is not None:
                    out.append((k, nv, obj))
            if isinstance(v, dict):
                walk(v)

    walk(data)
    return out


def _capture_producer_entities(
    *,
    test_case: Dict[str, Any],
    resp_json: Any,
    execution_context: Dict[str, Any],
) -> int:
    """Capture entities from a successful producer response.

    Bucket is ALWAYS `tc.resource_key` (or `resource_prefix`/`resource` aliases)
    — never path-derived. Returns the number of entities captured.
    """
    bucket = (
        test_case.get("resource_key")
        or test_case.get("resource_prefix")
        or test_case.get("resource")
    )
    if not bucket:
        return 0
    bucket = str(bucket).strip().lower()
    if not bucket or bucket == "default":
        return 0

    captured: List[Dict[str, Any]] = []
    produced_paths = test_case.get("produced_id_paths") or []
    if isinstance(produced_paths, list) and produced_paths:
        for dp in produced_paths:
            if not isinstance(dp, str):
                continue
            val = _extract_value_at_id_path(resp_json, dp)
            if val is None:
                continue
            leaf = dp.rsplit(".", 1)[-1]
            container = resp_json
            if isinstance(resp_json, list) and resp_json:
                container = resp_json[0]
            captured.append({
                "id": val,
                leaf: val,                       # accessor by exact field name
                "raw": container if isinstance(container, dict) else {leaf: val},
                "flat": _flatten(container) if isinstance(container, dict) else {leaf: val},
                "_source_path": dp,
            })
    else:
        # Fallback: universal walk (additive, still bucketed by resource_key)
        for key_name, val, raw_obj in _walk_id_fields(resp_json):
            captured.append({
                "id": val,
                key_name: val,
                "raw": raw_obj,
                "flat": _flatten(raw_obj),
                "_source_path": key_name,
            })

    if not captured:
        return 0

    entities = execution_context.setdefault("entities", {})
    bucket_list = entities.setdefault(bucket, [])
    for ent in captured:
        bucket_list.append(ent)
    # Trim to last 10 to avoid unbounded growth.
    if len(bucket_list) > 10:
        del bucket_list[: len(bucket_list) - 10]
    return len(captured)


def _resolve_dependency_value(
    *,
    source: str,
    field: str,
    execution_context: Dict[str, Any],
) -> Any:
    """Look up a value from the entities bucket under `source` for `field`.

    The producer bucket entry stores both `{leaf_name: value}` and a flattened
    map under `flat`, so dotted-path field references work transparently.
    """
    if not source:
        return None
    bucket = execution_context.get("entities", {}).get(str(source).strip().lower())
    if not bucket:
        return None
    latest = bucket[-1]
    if not isinstance(latest, dict):
        return _normalize_entity_scalar(latest)
    field = field or "id"
    # Direct key
    if field in latest:
        nv = _normalize_entity_scalar(latest[field])
        if nv is not None:
            return nv
    # Flattened dotted key
    flat = latest.get("flat") or {}
    if isinstance(flat, dict) and field in flat:
        nv = _normalize_entity_scalar(flat[field])
        if nv is not None:
            return nv
    # Within raw
    raw = latest.get("raw")
    if isinstance(raw, dict):
        nv = _normalize_entity_scalar(_get_by_dotted_path(raw, field))
        if nv is not None:
            return nv
        nv = _normalize_entity_scalar(raw.get(field))
        if nv is not None:
            return nv
    # Last resort: latest.id
    return _normalize_entity_scalar(latest.get("id"))


def _find_foreign_id(
    current_resource_key: Optional[str],
    execution_context: Dict[str, Any],
) -> Optional[Any]:
    """For 403 tests: find an id from a DIFFERENT resource bucket."""
    cur = (current_resource_key or "").strip().lower()
    for bucket_key, ents in (execution_context.get("entities") or {}).items():
        if str(bucket_key).strip().lower() == cur:
            continue
        for ent in reversed(ents or []):
            if isinstance(ent, dict):
                v = ent.get("id")
                nv = _normalize_entity_scalar(v)
                if nv is not None:
                    return nv
    return None


# =============================================================================
# SECTION 5 — Synthetic non-existent IDs (404 mutation)
# =============================================================================
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_OBJECT_ID_RE = re.compile(r"^[0-9a-fA-F]{24}$")


def _synthetic_nonexistent_id(seed_value: Any) -> str:
    """Produce a syntactically valid but very-unlikely-to-exist id."""
    s = str(seed_value or "").strip()
    if _UUID_RE.match(s):
        return str(uuid.uuid4())
    if _OBJECT_ID_RE.match(s):
        return uuid.uuid4().hex[:24]
    if s.isdigit():
        # Stay numeric, push to a high improbable range.
        return "999999999"
    return f"non-existent-{uuid.uuid4().hex[:8]}"


# =============================================================================
# SECTION 6 — Negative test pre-flight mutation (kind-driven)
# =============================================================================
def _wrong_type_value(current: Any) -> Any:
    """Return a value of a wrong type vs `current`."""
    if isinstance(current, bool):
        return "not-a-boolean"
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        return "not-a-number"
    if isinstance(current, str):
        return 12345
    if isinstance(current, list):
        return {"__not_a_list__": True}
    if isinstance(current, dict):
        return ["__not_a_dict__"]
    return {"__wrong_type__": True}


def _apply_kind_mutations(
    *,
    tc: Dict[str, Any],
    path_params: Dict[str, Any],
    query_params: Dict[str, Any],
    headers: Dict[str, Any],
    body: Any,
    skip_inject: set,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Any]:
    """Apply pre-flight mutations driven by tc.kind / tc.mutation_meta.

    Returns the (possibly mutated) (path_params, query_params, headers, body).

    The `skip_inject` set is populated with the names of fields that the
    dependency injector MUST NOT re-fill (e.g. for `negative_required_missing`).
    """
    kind = str(tc.get("kind") or "").strip().lower()
    if not kind or kind == "positive":
        return path_params, query_params, headers, body

    mm = tc.get("mutation_meta") or {}
    if not isinstance(mm, dict):
        mm = {}

    missing_field = tc.get("missing_field") or mm.get("missing_field")
    format_field = tc.get("format_field") or mm.get("format_field")
    format_name = tc.get("format") or mm.get("format")

    # ── Required-field-missing variants ────────────────────────────────────
    if kind == "negative_required_missing" and missing_field:
        # Body is the most common target.
        if isinstance(body, dict):
            if missing_field in body:
                body.pop(missing_field, None)
            else:
                _delete_by_dotted_path(body, missing_field)
        skip_inject.add(missing_field)

    elif kind == "negative_query_required_missing" and missing_field:
        if missing_field in query_params:
            query_params.pop(missing_field, None)
        skip_inject.add(missing_field)

    elif kind == "negative_header_required_missing" and missing_field:
        _pop_header_ci(headers, missing_field)
        skip_inject.add(missing_field)

    elif kind == "negative_cookie_required_missing" and missing_field:
        # We do not have explicit cookie params here; the generator typically
        # encodes cookies via headers["Cookie"] — strip if present.
        _pop_header_ci(headers, "Cookie")
        skip_inject.add(missing_field)

    elif kind == "negative_path_required_missing" and missing_field:
        # The path itself can't be sent without the segment; null out value.
        if missing_field in path_params:
            path_params[missing_field] = None
        skip_inject.add(missing_field)

    # ── Format invalidation ───────────────────────────────────────────────
    elif kind == "negative_format_invalid":
        invalid = invalid_value_for_format(format_name) if format_name else "__invalid__"
        if format_field:
            applied = False
            if isinstance(body, dict):
                if format_field in body:
                    body[format_field] = invalid
                    applied = True
                elif _set_by_dotted_path(body, format_field, invalid):
                    applied = True
            if not applied and format_field in query_params:
                query_params[format_field] = invalid
                applied = True
            if not applied and format_field in path_params:
                path_params[format_field] = invalid
                applied = True
            skip_inject.add(format_field)

    # ── Type invalidation ─────────────────────────────────────────────────
    elif kind == "negative_query_type_invalid":
        target = mm.get("field") or missing_field
        if target and target in query_params:
            query_params[target] = _wrong_type_value(query_params[target])
            skip_inject.add(target)

    elif kind == "negative_path_type_invalid":
        target = mm.get("field") or missing_field
        if target and target in path_params:
            path_params[target] = _wrong_type_value(path_params[target])
            skip_inject.add(target)

    # ── Auth missing ──────────────────────────────────────────────────────
    elif kind == "negative_auth_missing":
        _pop_header_ci(headers, "Authorization")
        _pop_header_ci(headers, "Cookie")

    # For enum-invalid / pattern / min/max / additional_properties / etc.
    # the generator already emitted an invalid VALUE — we don't need to alter
    # it here. We only add the field to skip_inject so dep_map doesn't replace
    # it with a producer ID by accident.
    elif kind in {
        "negative_query_enum_invalid",
        "negative_path_enum_invalid",
        "negative_header_enum_invalid",
        "negative_body_enum_invalid",
        "negative_pattern",
        "negative_min_length",
        "negative_max_length",
        "negative_minimum",
        "negative_maximum",
        "negative_min_items",
        "negative_max_items",
        "negative_additional_properties",
    }:
        target = mm.get("field") or missing_field or format_field
        if target:
            skip_inject.add(target)

    return path_params, query_params, headers, body


# =============================================================================
# SECTION 7 — Dependency injection (strict, dep_map-first)
# =============================================================================
def _inject_dependencies(
    *,
    tc: Dict[str, Any],
    path_params: Dict[str, Any],
    query_params: Dict[str, Any],
    body: Any,
    placeholders: List[str],
    skip_inject: set,
    execution_context: Dict[str, Any],
    is_negative: bool,
    is_404: bool,
) -> Tuple[Any, Dict[str, Any], List[str]]:
    """Resolve dependencies using `tc.dependency_map` STRICTLY.

    Returns (body, resolution_summary, missing_required_path_params).

    For the path placeholders:
        * If a dep_map entry exists, look it up in execution_context.
        * If 404 negative, mutate the resolved value to a synthetic non-
          existent id at the end (404 still requires routing through the
          correct path skeleton).
        * If a dep_map entry is missing AND we're not in strict mode AND
          we're not the 404 negative kind, fall back to a single-segment
          singularization of the path tail. Else mark as missing.

    For non-path keys in dep_map (body / query):
        * Resolve and inject by dotted path or top-level.
        * Skip if the field is in `skip_inject` (e.g. a missing-field negative).
        * Intent-aware: ask "Should this testcase receive body values?" based
          on kind, not "Can I inject?" based on is_negative.
    """
    dep_map = tc.get("dependency_map") or {}
    # Derive intent signals from the test case for body injection policy.
    _kind = str(tc.get("kind") or "").strip().lower()
    _is_403 = int(tc.get("expected_status") or 0) == 403
    if not isinstance(dep_map, dict):
        dep_map = {}

    summary: Dict[str, Any] = {
        "injected_path_params": {},
        "injected_query_params": {},
        "injected_body_fields": {},
        "missing_dependencies": [],
        "skipped_due_to_negative": [],
        "fallback_used": False,
    }
    missing_path: List[str] = []

    # ── Path placeholders ────────────────────────────────────────────────
    for ph in placeholders:
        if ph in skip_inject:
            summary["skipped_due_to_negative"].append({"param": ph, "scope": "path"})
            continue
        dep = dep_map.get(ph)
        value = None
        source = None
        field = "id"
        if isinstance(dep, dict):
            source = dep.get("source")
            field = dep.get("field") or "id"
            value = _resolve_dependency_value(source=source, field=field, execution_context=execution_context)

        if value is None and not STRICT_MODE and not is_404:
            # Tier-2 fallback: use the last entity in the consumer's own bucket.
            own_bucket = (tc.get("resource_key") or tc.get("resource_prefix") or "").strip().lower()
            if own_bucket:
                value = _resolve_dependency_value(source=own_bucket, field=field, execution_context=execution_context)
                if value is not None:
                    summary["fallback_used"] = True

        if value is None and not STRICT_MODE and not is_404 and not isinstance(dep, dict):
            # Tier-3 last-resort: dep_map had NO entry for this placeholder —
            # the generator could not determine the dependency from the swagger
            # spec (e.g. generic {id} in paths like /add-to-cart/{id}).
            # Scan all available entity buckets and use the most-recently-created
            # entity's id.  This is still spec-driven: entities only exist
            # because swagger-documented producers ran and captured a response.
            for _bk, _bents in (execution_context.get("entities") or {}).items():
                if not _bents:
                    continue
                _v = _resolve_dependency_value(
                    source=_bk, field="id", execution_context=execution_context
                )
                if _v is not None:
                    value = _v
                    summary["fallback_used"] = True
                    summary.setdefault("last_resort_buckets", []).append(_bk)
                    break

        if value is None and not is_404:
            summary["missing_dependencies"].append({"param": ph, "source": source, "field": field, "scope": "path"})
            missing_path.append(ph)
            continue

        if value is not None:
            path_params[ph] = value
            summary["injected_path_params"][ph] = {"source": source, "field": field, "value": value}

    # ── 404 mutation: replace path IDs with synthetic non-existent ones ──
    if is_404:
        for ph in placeholders:
            cur = path_params.get(ph)
            if cur is None:
                # Need any id-shape so we can swap to a synthetic; use uuid4 as a generic.
                path_params[ph] = str(uuid.uuid4())
            else:
                path_params[ph] = _synthetic_nonexistent_id(cur)

    # ── Non-path dep_map keys (body / query) ─────────────────────────────
    body_copied = False
    for key, meta in dep_map.items():
        if key in placeholders:
            continue  # already handled
        if key in skip_inject:
            summary["skipped_due_to_negative"].append({"param": key, "scope": "non-path"})
            continue
        if not isinstance(meta, dict):
            continue
        source = meta.get("source")
        field = meta.get("field") or "id"
        value = _resolve_dependency_value(source=source, field=field, execution_context=execution_context)
        if value is None:
            summary["missing_dependencies"].append({"param": key, "source": source, "field": field, "scope": "non-path"})
            continue

        # Intent-aware policy: ask "Should this testcase receive body values?"
        # `is_negative` (from expected_status) is the fallback when kind is
        # absent or unrecognised — prevents valid entity IDs from overwriting
        # an intentionally invalid body and producing a spurious 2xx result.
        if not _kind_permits_body_injection(_kind, is_404, _is_403, is_negative=is_negative):
            summary["skipped_due_to_negative"].append({"param": key, "scope": "negative", "reason": "kind_policy"})
            continue

        # Query param injection (only if param exists)
        if key in (query_params or {}):
            query_params[key] = value
            summary["injected_query_params"][key] = {"source": source, "field": field, "value": value}
            continue

        # Body injection
        if isinstance(body, (dict, list)):
            if not body_copied:
                body = copy.deepcopy(body)
                body_copied = True
            if isinstance(body, dict) and "." not in key and key in body:
                body[key] = value
                summary["injected_body_fields"][key] = {"source": source, "field": field, "value": value}
                continue
            if _set_by_dotted_path(body, key, value):
                summary["injected_body_fields"][key] = {"source": source, "field": field, "value": value}
                continue
            # If field doesn't exist in body, silently skip — the schema didn't ask for it.

    return body, summary, missing_path


# =============================================================================
# SECTION 8 — Auth injection
# =============================================================================
def _inject_auth(
    *,
    tc: Dict[str, Any],
    headers: Dict[str, Any],
    auth_enabled: bool,
    execution_context: Dict[str, Any],
) -> bool:
    """Inject Authorization / Cookie. Returns True if auth was provided.

    Rules (top-down):
        1. If `auth_enabled=False` -> no auth injected.
        2. If tc is `negative_auth_missing` (or any auth-negative variant)
           -> strip Authorization & Cookie, return False.
        3. If tc is the auth endpoint itself (login/signup) -> strip auth.
        4. Otherwise, if a token / cookie was captured -> inject and return True.
        5. Otherwise return False.
    """
    if not auth_enabled:
        return False

    if _case_auth_negative(tc):
        _pop_header_ci(headers, "Authorization")
        _pop_header_ci(headers, "Cookie")
        return False

    if _is_auth_endpoint(tc):
        _pop_header_ci(headers, "Authorization")
        _pop_header_ci(headers, "Cookie")
        return False

    auth_type = execution_context.get("auth_type")
    token = execution_context.get("token") or execution_context.get("auth_token")
    cookie_token = execution_context.get("cookie_token")
    cookie_name = execution_context.get("cookie_name")

    # Cookie auth path
    if auth_type == "cookie" and cookie_token and cookie_name:
        _pop_header_ci(headers, "Authorization")
        _pop_header_ci(headers, "Cookie")
        headers["Cookie"] = f"{cookie_name}={cookie_token}"
        return True

    # Bearer
    if token:
        _pop_header_ci(headers, "Authorization")
        _pop_header_ci(headers, "Cookie")
        headers["Authorization"] = f"Bearer {token}"
        return True

    return False


# =============================================================================
# SECTION 9 — Bootstrap auth (signup → login) when needed
# =============================================================================
async def _bootstrap_auth(
    *,
    test_cases: List[Dict[str, Any]],
    base_url: str,
    client: httpx.AsyncClient,
    client_timeout: httpx.Timeout,
    execution_context: Dict[str, Any],
    auth_state: Dict[str, str],
) -> None:
    """If the suite has positive secured routes and a login endpoint, try to
    obtain a token before pass1. Best-effort, never raises."""
    if not AUTO_AUTH_BOOTSTRAP:
        return
    if execution_context.get("token") or execution_context.get("cookie_token"):
        return

    needs_token = any(
        _case_security_required(tc)
        and str(tc.get("kind") or "") == "positive"
        and not _is_auth_endpoint(tc)
        and not _case_auth_negative(tc)
        for tc in test_cases
    )
    if not needs_token:
        return

    login_tc: Optional[Dict[str, Any]] = None
    signup_tc: Optional[Dict[str, Any]] = None
    for tc in test_cases:
        if str(tc.get("kind") or "") != "positive":
            continue
        p = str(tc.get("endpoint_path") or "")
        if login_tc is None and (tc.get("flow_type") == "auth" or _looks_like_login_path(p)):
            # Login-like (not signup)
            if not _looks_like_signup_path(p):
                login_tc = tc
        if signup_tc is None and _looks_like_signup_path(p):
            signup_tc = tc

    base = (base_url or "").rstrip("/")

    async def _post(path: str, payload: Dict[str, Any]) -> Optional[httpx.Response]:
        try:
            return await client.request(
                method="POST",
                url=f"{base}{path}",
                json=payload,
                headers={"User-Agent": "Cognitest-Contract", "X-Contract-Test": "true"},
                timeout=client_timeout,
            )
        except Exception as e:
            if DEBUG_AUTH:
                logger.warning("[BOOTSTRAP] %s POST failed: %s", path, e)
            return None

    # 1. Try signup first (best chance to also create the user we'll login with).
    if AUTO_AUTH_BOOTSTRAP_ALLOW_SIGNUP and signup_tc is not None:
        signup_path = str(signup_tc.get("endpoint_path") or "")
        signup_body = signup_tc.get("request_body")
        if not isinstance(signup_body, dict) or not signup_body:
            signup_body = {
                "email": auth_state["email"],
                "password": auth_state["password"],
                "confirmPassword": auth_state["password"],
            }
        else:
            signup_body = copy.deepcopy(signup_body)
            for k in list(signup_body.keys()):
                kl = k.lower()
                if "email" in kl:
                    signup_body[k] = auth_state["email"]
                elif "password" in kl or "pwd" in kl:
                    signup_body[k] = auth_state["password"]
        resp = await _post(signup_path, signup_body)
        if resp is not None and 200 <= resp.status_code < 300:
            execution_context["auth_user"] = {"email": auth_state["email"], "password": auth_state["password"]}
            try:
                rj = resp.json()
            except Exception:
                rj = None
            t, src = _capture_token_anywhere(rj, resp)
            if t:
                execution_context["token"] = t
                execution_context["auth_token"] = t
                execution_context["auth_type"] = "cookie" if src == "cookie" else "bearer"
                if DEBUG_AUTH:
                    logger.info("[BOOTSTRAP] token from signup (%s)", src)

    # 2. Try login if no token yet OR there is a real login endpoint.
    if not execution_context.get("token") and login_tc is not None:
        login_path = str(login_tc.get("endpoint_path") or "")
        login_body = login_tc.get("request_body")
        if not isinstance(login_body, dict) or not login_body:
            login_body = {"email": auth_state["email"], "password": auth_state["password"]}
        else:
            login_body = copy.deepcopy(login_body)
            for k in list(login_body.keys()):
                kl = k.lower()
                if "email" in kl or "user" in kl:
                    login_body[k] = auth_state["email"]
                elif "password" in kl or "pwd" in kl:
                    login_body[k] = auth_state["password"]
        resp = await _post(login_path, login_body)
        if resp is not None and 200 <= resp.status_code < 300:
            try:
                rj = resp.json()
            except Exception:
                rj = None
            t, src = _capture_token_anywhere(rj, resp)
            if t:
                execution_context["token"] = t
                execution_context["auth_token"] = t
                execution_context["auth_type"] = "cookie" if src == "cookie" else "bearer"
                if src == "cookie":
                    sc = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [resp.headers.get("set-cookie")]
                    _, name = _extract_token_from_set_cookie(sc)
                    if name:
                        execution_context["cookie_name"] = name
                        execution_context["cookie_token"] = t
                if DEBUG_AUTH:
                    logger.info("[BOOTSTRAP] token from login (%s)", src)


# =============================================================================
# SECTION 10 — Core per-test runner
# =============================================================================

# =============================================================================
# PIPELINE SEMANTIC LAYER — formal models, state taxonomy, derivation logic
# =============================================================================

# ── R3: Warning escalation policy ────────────────────────────────────────────
# When COGNITEST_WARN_AS_FAIL=1, WARNING final_status is promoted to FAIL.
# Use in strict environments where any schema drift must be treated as failure.
# Default: off (WARNING remains WARNING, counted in the passed bucket).
WARN_AS_FAIL = _truthy_env("COGNITEST_WARN_AS_FAIL", "0")

# ── R9: Valid state enumerations (documentation + defensive use) ─────────────
_VALID_EXECUTION_STATES = frozenset({
    "EXECUTED",
    "SKIPPED",
    "TRANSPORT_ERROR",
    "TIMEOUT",
    "CONFIG_ERROR",
})

_VALID_VALIDATION_STATES = frozenset({
    "PASS",
    "FAIL",
    "WARNING",
    "NOT_EVALUATED",
    "VALIDATOR_ERROR",
})

_VALID_FINAL_STATES = frozenset({
    "PASS",
    "FAIL",
    "WARNING",
    "ERROR",
    "SKIPPED",
})

_EXECUTION_ERROR_STATES = frozenset({"TRANSPORT_ERROR", "TIMEOUT", "CONFIG_ERROR"})

# ── R2: Formal pipeline result models ────────────────────────────────────────


class RuntimeContext(TypedDict, total=False):
    """Runtime orchestration metadata produced by the executor for each test.

    Captures provenance data from the execution layer — dependency resolution,
    auth injection, fallback usage, execution phase.  This is runtime metadata
    only; it has no bearing on contract validation truth.
    """
    execution_phase: str          # PASS_1 | PASS_2 | PASS_3
    auth_provided: bool
    auth_type: Optional[str]      # bearer | cookie | None
    fallback_used: bool
    dependency_resolution: Dict[str, Any]
    error_detail: Optional[str]   # raw transport/config error message


class FinalTestResult(TypedDict, total=False):
    """Complete per-test result produced by _run_one / _build_skip_result.

    Three semantic layers are always explicitly present:
        execution_status  — runtime layer (EXECUTED | SKIPPED | TRANSPORT_ERROR | …)
        validation_status — contract layer (PASS | FAIL | WARNING | VALIDATOR_ERROR | …)
        final_status      — derived outcome (PASS | FAIL | WARNING | ERROR | SKIPPED)

    error_category provides human-readable sub-classification for ERROR states
    without changing the stable final_status taxonomy.
    """
    event: str
    id: str
    name: str
    endpoint_path: str
    method: str
    expected_status: int
    actual_status: Optional[int]
    passed: bool
    response_time_ms: int
    error_message: str
    log: str
    execution_status: str
    validation_status: str
    final_status: str
    error_category: Optional[str]
    violations: List[Dict[str, Any]]
    skip_reason: Optional[str]
    runtime_context: RuntimeContext


# ── R4: Error category derivation ────────────────────────────────────────────

def _derive_error_category(execution_status: str, validation_status: str) -> Optional[str]:
    """Returns a specific error sub-category for ERROR final_status, None otherwise.

    Preserves ERROR differentiation without changing the stable final_status
    taxonomy.  Consumers can use this field to distinguish infrastructure
    problems from engine problems from configuration problems.

    Categories:
        runtime.transport   — TCP/DNS/HTTP transport failure
        runtime.timeout     — Request timeout (sub-type of transport failure)
        config.op_missing   — operation_key not found in loaded spec
        engine.validator_crash — internal validator exception
    """
    if execution_status == "TIMEOUT":
        return "runtime.timeout"
    if execution_status == "TRANSPORT_ERROR":
        return "runtime.transport"
    if execution_status == "CONFIG_ERROR":
        return "config.op_missing"
    if execution_status == "EXECUTED" and validation_status == "VALIDATOR_ERROR":
        return "engine.validator_crash"
    return None


# ── Final-status derivation (single authoritative state machine) ──────────────
# Combines execution_status (runtime) + validation_status (contract) into the
# single user-facing outcome.  This is the ONLY place PASS/FAIL/ERROR/SKIPPED
# are determined — never inside the executor or validator independently.
#
#  execution_status       validation_status    → final_status
#  ─────────────────      ─────────────────    ─────────────
#  SKIPPED                *                    → SKIPPED
#  TRANSPORT_ERROR        *                    → ERROR   (runtime.transport)
#  TIMEOUT                *                    → ERROR   (runtime.timeout)
#  CONFIG_ERROR           *                    → ERROR   (config.op_missing)
#  EXECUTED               PASS                 → PASS
#  EXECUTED               WARNING              → WARNING (or FAIL if WARN_AS_FAIL)
#  EXECUTED               FAIL                 → FAIL
#  EXECUTED               VALIDATOR_ERROR      → ERROR   (engine.validator_crash)
#  EXECUTED               NOT_EVALUATED        → ERROR   (defensive; should not occur)
#  <unknown>              *                    → ERROR   (defensive catch-all)


def _derive_final_status(execution_status: str, validation_status: str) -> str:
    if execution_status == "SKIPPED":
        return "SKIPPED"
    if execution_status in _EXECUTION_ERROR_STATES:
        return "ERROR"
    if execution_status == "EXECUTED":
        if validation_status == "PASS":
            return "PASS"
        if validation_status == "WARNING":
            # WARN_AS_FAIL promotes WARNING to FAIL in strict-warning environments.
            return "FAIL" if WARN_AS_FAIL else "WARNING"
        if validation_status == "FAIL":
            return "FAIL"
        # VALIDATOR_ERROR, NOT_EVALUATED, or any unrecognised value:
        # these are engine/infrastructure problems, not API contract failures.
        return "ERROR"
    # Defensive catch-all: any unknown execution_status is an infrastructure ERROR.
    return "ERROR"


def _build_skip_result(
    *,
    tc: Dict[str, Any],
    base: str,
    method: str,
    path_template: str,
    expected_status: int,
    skip_reason: str,
    error_msg: str,
    started_at: float,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    out = {
        "event": "result",
        "id": str(tc.get("id") or ""),
        "name": str(tc.get("name") or f"{method} {path_template}"),
        "endpoint_path": path_template,
        "method": method,
        "expected_status": expected_status,
        "actual_status": None,
        "passed": False,
        "response_time_ms": elapsed_ms,
        "error_message": error_msg,
        "log": f"[{method}] {path_template} -> SKIPPED ({skip_reason}: {error_msg})",
        "request_headers": {},
        "request_body": tc.get("request_body"),
        "response_headers": {},
        "response_body": None,
        "test_case": tc,
        "exchange": {
            "request": {
                "url": f"{base}{path_template}",
                "method": method,
                "headers": {},
                "query": {},
                "body": tc.get("request_body"),
                "sent": False,
            },
            "response": {
                "status_code": None,
                "headers": {},
                "content_type": None,
                "json": None,
                "body": None,
            },
            "error": error_msg,
            "elapsed_ms": elapsed_ms,
            "execution_status": "SKIPPED",
            "validation_status": "NOT_EVALUATED",
            "final_status": "SKIPPED",
            "skip_reason": skip_reason,
            "auth_provided": False,
        },
        "violations": [],
        "execution_status": "SKIPPED",
        "validation_status": "NOT_EVALUATED",
        "final_status": "SKIPPED",
        "error_category": None,
        "skip_reason": skip_reason,
        # ── Runtime provenance (execution layer only) ─────────────────────
        "runtime_context": {
            "execution_phase": None,   # set later by execute_contract_test_cases
            "auth_provided": False,
            "auth_type": None,
            "fallback_used": False,
            "dependency_resolution": extra.get("dependency_resolution") if extra else {},
            "error_detail": error_msg,
        },
        # Top-level aliases preserved for backward compatibility.
        "auth_provided": False,
        "fallback_used": False,
        "dependency_resolution": extra.get("dependency_resolution") if extra else {},
    }
    if extra:
        out.update(extra)
    return out


async def _run_one(
    *,
    tc: Dict[str, Any],
    client: httpx.AsyncClient,
    base: str,
    auth_enabled: bool,
    provided_auth_headers: Dict[str, Any],
    execution_context: Dict[str, Any],
    auth_state: Dict[str, str],
    operations_by_key: Dict[str, Dict[str, Any]],
    client_timeout: httpx.Timeout,
    run_sem: asyncio.Semaphore,
) -> Dict[str, Any]:
    started_at = time.perf_counter()

    method = str(tc.get("method") or "GET").upper()
    path_template = str(tc.get("endpoint_path") or "/")
    expected_status = int(tc.get("expected_status") or 200)
    is_negative = expected_status >= 400
    is_404 = expected_status == 404
    is_403 = expected_status == 403
    kind = str(tc.get("kind") or "").strip().lower()
    is_auth_ep = _is_auth_endpoint(tc)
    is_auth_negative = _case_auth_negative(tc)
    security_required = _case_security_required(tc)

    execution_context["current_path"] = path_template

    # ── Semantic conflict guard ───────────────────────────────────────────
    # A `negative_auth_missing` test on a login/signup endpoint is
    # contradictory: auth endpoints issue tokens, they don't require one.
    # Stripping the Authorization header from a login request produces
    # exactly the same request as a normal (positive) login — there is no
    # semantic difference to test.  Running this case would create a false
    # contract.auth violation when the login correctly returns 200.
    if is_auth_ep and is_auth_negative:
        return _build_skip_result(
            tc=tc, base=base, method=method, path_template=path_template,
            expected_status=expected_status,
            skip_reason="semantic_conflict",
            error_msg=(
                f"negative_auth_missing on auth endpoint {path_template}: "
                "auth endpoints do not require tokens — stripping the "
                "Authorization header produces an identical request to the "
                "positive test; this test carries no semantic content"
            ),
            started_at=started_at,
        )

    # ── Build initial request shape from generator output ────────────────
    raw_path_params = tc.get("path_params") or {}
    path_params: Dict[str, Any] = dict(raw_path_params) if isinstance(raw_path_params, dict) else {}
    raw_query = tc.get("request_query") or {}
    query_params: Dict[str, Any] = dict(raw_query) if isinstance(raw_query, dict) else {}

    request_type = str(tc.get("request_type") or "").strip().lower()
    is_multipart = request_type == "multipart"
    raw_body = tc.get("request_body")
    multipart_files_raw = tc.get("files") or {}
    multipart_form_raw = tc.get("form_data") or {}

    if is_multipart:
        body: Any = dict(multipart_form_raw) if isinstance(multipart_form_raw, dict) else (
            dict(raw_body) if isinstance(raw_body, dict) else {}
        )
    else:
        body = copy.deepcopy(raw_body) if isinstance(raw_body, (dict, list)) else raw_body

    # ── Build request headers (NEVER honor incoming Authorization/Cookie)
    headers: Dict[str, Any] = {
        "User-Agent": "Cognitest-Contract",
        "X-Contract-Test": "true",
    }
    for k, v in (provided_auth_headers or {}).items():
        if str(k).lower() in {"authorization", "cookie"}:
            continue
        headers[str(k)] = str(v)
    for k, v in (tc.get("request_headers") or {}).items():
        if str(k).lower() in {"authorization", "cookie"}:
            continue
        headers[str(k)] = str(v)

    # ── Pre-flight kind-driven mutations + skip-injection set ────────────
    skip_inject: set = set()
    path_params, query_params, headers, body = _apply_kind_mutations(
        tc=tc,
        path_params=path_params,
        query_params=query_params,
        headers=headers,
        body=body,
        skip_inject=skip_inject,
    )

    # ── Dependency injection (uses `dependency_map` strictly) ────────────
    placeholders = _path_placeholders(path_template)
    body, dep_summary, missing_path = _inject_dependencies(
        tc=tc,
        path_params=path_params,
        query_params=query_params,
        body=body,
        placeholders=placeholders,
        skip_inject=skip_inject,
        execution_context=execution_context,
        is_negative=is_negative,
        is_404=is_404,
    )

    # ── 403 Forbidden: swap path id for a foreign-bucket id ──────────────
    if is_403:
        own_rkey = (tc.get("resource_key") or tc.get("resource_prefix") or "").strip().lower()
        foreign = _find_foreign_id(own_rkey, execution_context)
        if foreign is not None:
            for ph in placeholders:
                lk = ph.lower()
                if lk == "id" or lk.endswith("id") or lk.endswith("_id"):
                    path_params[ph] = foreign
                    break

    # ── Skip if path placeholders couldn't be resolved (and not 404) ─────
    if missing_path and not is_404:
        return _build_skip_result(
            tc=tc, base=base, method=method, path_template=path_template,
            expected_status=expected_status,
            skip_reason="dependency_missing",
            error_msg=f"Unresolved path params: {missing_path}",
            started_at=started_at,
            extra={"dependency_resolution": dep_summary},
        )

    # ── Skip secured route with no token (only when not testing 401) ─────
    if security_required and not is_auth_ep and not is_auth_negative and expected_status != 401:
        if not (execution_context.get("token") or execution_context.get("cookie_token")):
            return _build_skip_result(
                tc=tc, base=base, method=method, path_template=path_template,
                expected_status=expected_status,
                skip_reason="auth_missing",
                error_msg=f"Token required for {path_template} but none was captured",
                started_at=started_at,
                extra={"dependency_resolution": dep_summary},
            )

    # ── Auth injection ───────────────────────────────────────────────────
    auth_provided = _inject_auth(
        tc=tc, headers=headers, auth_enabled=auth_enabled,
        execution_context=execution_context,
    )

    # ── Replay stored credentials on positive login (after signup created them) ──
    if not is_negative and is_auth_ep and _looks_like_login_path(path_template):
        stored = execution_context.get("auth_user")
        if stored and isinstance(body, dict):
            for k in list(body.keys()):
                kl = k.lower()
                if "email" in kl or kl == "username":
                    body[k] = stored["email"]
                elif "password" in kl or "pwd" in kl:
                    body[k] = stored["password"]

    # ── Render final URL ─────────────────────────────────────────────────
    rendered_path = substitute_path_params(path_template, path_params)
    if "{" in rendered_path:
        return _build_skip_result(
            tc=tc, base=base, method=method, path_template=path_template,
            expected_status=expected_status,
            skip_reason="unresolved_path_param",
            error_msg=f"Unresolved path template: {rendered_path}",
            started_at=started_at,
            extra={"dependency_resolution": dep_summary},
        )
    url = f"{base}{rendered_path}"

    # ── HTTP execution (sequential per stateful flow) ────────────────────
    is_idempotent = method in IDEMPOTENT_METHODS
    is_producer = bool(tc.get("produces_entity") or tc.get("is_producer_endpoint"))
    base_retries = RETRY_IDEMPOTENT if is_idempotent else RETRY_NON_IDEMPOTENT
    max_retries = base_retries + (RETRY_PRODUCER_EXTRA if is_producer else 0)
    retry_503_attempts = RETRY_503_ATTEMPTS + (1 if is_producer else 0)

    request_headers_for_storage = _masked_headers(headers)
    transport_error = False
    error: Optional[str] = None
    status_code: Optional[int] = None
    resp_headers: Dict[str, Any] = {}
    resp_text: Optional[str] = None
    resp_json: Any = None
    content_type: Optional[str] = None
    request_was_sent = False
    resp: Optional[httpx.Response] = None

    async with run_sem:
        attempt = 0
        retry_503_used = 0
        max_total = 1 + retry_503_attempts + max_retries
        for _ in range(max_total):
            try:
                request_was_sent = True
                if is_multipart:
                    _pop_header_ci(headers, "Content-Type")
                    files_dict: Dict[str, Any] = {}
                    files_obj = multipart_files_raw if isinstance(multipart_files_raw, dict) else {}
                    for field, desc in sorted(files_obj.items()):
                        if not isinstance(field, str):
                            continue
                        if isinstance(desc, (tuple, list)) and len(desc) >= 2:
                            filename = str(desc[0] or "test.png")
                            content_val = desc[1]
                            ctype = str(desc[2] if len(desc) >= 3 else "application/octet-stream")
                            if isinstance(content_val, (bytes, bytearray)):
                                content_bytes = bytes(content_val)
                            elif isinstance(content_val, str) and content_val.strip():
                                try:
                                    content_bytes = base64.b64decode(content_val)
                                except Exception:
                                    content_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                            else:
                                content_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                            files_dict[field] = (filename, content_bytes, ctype)
                            continue
                        if not isinstance(desc, dict):
                            continue
                        filename = str(desc.get("filename") or "test.png")
                        ctype = str(desc.get("content_type") or "application/octet-stream")
                        if isinstance(desc.get("content"), (bytes, bytearray)):
                            content_bytes = bytes(desc.get("content"))
                        else:
                            b64 = desc.get("content_base64")
                            if isinstance(b64, str) and b64.strip():
                                try:
                                    content_bytes = base64.b64decode(b64)
                                except Exception:
                                    content_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                            else:
                                content_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                        files_dict[field] = (filename, content_bytes, ctype)
                    form_data = body if isinstance(body, dict) else {}
                    resp = await client.request(
                        method=method, url=url, headers=headers,
                        params=query_params, data=form_data, files=files_dict,
                        timeout=client_timeout,
                    )
                else:
                    if isinstance(body, (dict, list)):
                        resp = await client.request(
                            method=method, url=url, headers=headers,
                            params=query_params, json=body, timeout=client_timeout,
                        )
                    else:
                        resp = await client.request(
                            method=method, url=url, headers=headers,
                            params=query_params, content=body if isinstance(body, (bytes, str)) else None,
                            timeout=client_timeout,
                        )

                # 503 retry
                if int(getattr(resp, "status_code", 0) or 0) == 503 and retry_503_used < retry_503_attempts:
                    retry_503_used += 1
                    await asyncio.sleep(RETRY_503_SLEEP_S)
                    continue
                break

            except httpx.RequestError as exc:
                if attempt < max_retries:
                    attempt += 1
                    await asyncio.sleep(0.2 * attempt)
                    continue
                transport_error = True
                msg = str(exc) or exc.__class__.__name__
                if isinstance(exc, httpx.ReadTimeout) or "timeout" in msg.lower():
                    error = "timeout"
                else:
                    error = f"{exc.__class__.__name__}: {msg}"
                resp = None
                break
            except Exception as exc:
                error = f"executor.exception: {exc.__class__.__name__}: {exc}"
                resp = None
                break

    elapsed_ms = int((time.perf_counter() - started_at) * 1000)

    # ── Process response ─────────────────────────────────────────────────
    if resp is not None:
        status_code = int(resp.status_code)
        # Preserve multi-valued headers (Set-Cookie etc.)
        tmp: Dict[str, Dict[str, Any]] = {}
        for k, v in resp.headers.multi_items():
            lk = str(k).lower()
            entry = tmp.setdefault(lk, {"name": str(k), "values": []})
            entry["values"].append(str(v))
        resp_headers = {
            entry["name"]: (entry["values"][0] if len(entry["values"]) == 1 else entry["values"])
            for _lk, entry in sorted(tmp.items())
        }
        content_type = normalize_content_type(resp.headers.get("content-type"))
        resp_text = (resp.text or "")[:20000]
        should_try_json = bool(content_type and ("json" in content_type or "+json" in content_type))
        if not should_try_json:
            stripped = (resp_text or "").lstrip()
            if stripped.startswith("{") or stripped.startswith("["):
                should_try_json = True
        if should_try_json:
            try:
                resp_json = resp.json()
            except Exception:
                resp_json = None

    # ── Capture token from auth endpoints (login wins over signup) ──────
    if (
        resp is not None
        and isinstance(status_code, int)
        and 200 <= status_code < 300
        and (is_auth_ep or _looks_like_login_path(path_template) or _looks_like_signup_path(path_template))
    ):
        try:
            t, src = _capture_token_anywhere(resp_json, resp)
            if t:
                if _looks_like_login_path(path_template):
                    execution_context["token"] = t
                    execution_context["auth_token"] = t
                    execution_context["auth_type"] = "cookie" if src == "cookie" else "bearer"
                elif not execution_context.get("token"):
                    execution_context["token"] = t
                    execution_context["auth_token"] = t
                    execution_context["auth_type"] = "cookie" if src == "cookie" else "bearer"
                if src == "cookie":
                    sc_list = resp.headers.get_list("set-cookie") if hasattr(resp.headers, "get_list") else [resp.headers.get("set-cookie")]
                    _, cname = _extract_token_from_set_cookie(sc_list)
                    if cname:
                        execution_context["cookie_name"] = cname
                        execution_context["cookie_token"] = t
            # Capture credentials on successful signup to replay at login
            if _looks_like_signup_path(path_template) and isinstance(raw_body, dict):
                email = raw_body.get("email") or raw_body.get("username")
                password = raw_body.get("password") or raw_body.get("pwd")
                if email and password and execution_context.get("auth_user") is None:
                    execution_context["auth_user"] = {"email": email, "password": password}
        except Exception as e:
            if DEBUG_AUTH:
                logger.warning("[TOKEN CAPTURE] failed: %s", e)

    # ── Capture producer entities (only on successful positive runs) ────
    if (
        resp is not None
        and isinstance(status_code, int)
        and 200 <= status_code < 300
        and not is_negative
        and isinstance(resp_json, (dict, list))
    ):
        if tc.get("produces_entity") or tc.get("is_producer_endpoint") or tc.get("produced_id_paths"):
            try:
                n = _capture_producer_entities(
                    test_case=tc, resp_json=resp_json, execution_context=execution_context
                )
                if DEBUG and n:
                    bk = (tc.get("resource_key") or "").strip().lower()
                    logger.info("[ENTITY] %s captured %d into bucket %r", path_template, n, bk)
            except Exception as e:
                logger.warning("[ENTITY] capture failed for %s: %s", path_template, e)

    # ── Build the exchange dict (validator input) ────────────────────────
    exchange = {
        "request": {
            "url": url,
            "method": method,
            "headers": request_headers_for_storage,
            "query": query_params,
            "body": body,
            "sent": request_was_sent,
        },
        "response": {
            "status_code": status_code,
            "headers": resp_headers,
            "content_type": content_type,
            "json": resp_json,
            "body": resp_text,
        },
        "error": error,
        "elapsed_ms": elapsed_ms,
        "auth_provided": auth_provided,
    }

    # ── Determine execution_status (runtime-only) ────────────────────────
    # This is the ONLY place execution_status is set.  It represents what
    # happened at the transport/runtime layer — nothing about contract truth.
    op = operations_by_key.get(str(tc.get("operation_key") or "")) if operations_by_key else None

    if transport_error:
        execution_status = "TIMEOUT" if (error and "timeout" in str(error).lower()) else "TRANSPORT_ERROR"
    elif op is None:
        execution_status = "CONFIG_ERROR"
    else:
        execution_status = "EXECUTED"

    # ── VALIDATION — invoked only when a real HTTP exchange occurred ──────
    # The validator is the single source of truth for contract correctness.
    # It never runs for transport failures, config errors, or skips.
    validation_status = "NOT_EVALUATED"
    violations: List[Dict[str, Any]] = []

    if execution_status == "EXECUTED":
        try:
            val_result = validate_exchange(
                operation=op, test_case=tc, exchange=exchange, auth_provided=auth_provided
            )
            validation_status = val_result["validation_status"]
            violations = val_result["violations"]
        except Exception as e:
            # An internal engine error during validation does NOT mean the API
            # violated its contract — we simply could not evaluate the contract.
            # VALIDATOR_ERROR is a distinct state from both FAIL and NOT_EVALUATED.
            logger.warning("[VALIDATOR] internal error for %s %s: %s", method, path_template, e)
            validation_status = "VALIDATOR_ERROR"
            violations = []

    # ── Derive final outcome (combines runtime + contract semantics) ──────
    final_status = _derive_final_status(execution_status, validation_status)
    error_category = _derive_error_category(execution_status, validation_status)
    actual_status = status_code if isinstance(status_code, int) else 0
    passed = (final_status == "PASS")

    exchange["execution_status"] = execution_status
    exchange["validation_status"] = validation_status
    exchange["final_status"] = final_status
    exchange["error_category"] = error_category
    exchange["skip_reason"] = None

    log = f"[{method}] {path_template} -> {final_status} (expected {expected_status}, got {actual_status})"
    if error:
        log += f" [error: {error}]"

    return {
        "event": "result",
        "id": str(tc.get("id") or ""),
        "name": str(tc.get("name") or f"{method} {path_template}"),
        "endpoint_path": path_template,
        "method": method,
        "expected_status": expected_status,
        "actual_status": actual_status,
        "passed": passed,
        "response_time_ms": elapsed_ms,
        "error_message": str(error or ""),
        "log": log,
        "request_headers": request_headers_for_storage,
        "request_body": body,
        "response_headers": resp_headers,
        "response_body": resp_json if resp_json is not None else resp_text,
        "test_case": tc,
        "exchange": exchange,
        "violations": violations,
        "execution_status": execution_status,
        "validation_status": validation_status,
        "final_status": final_status,
        "error_category": error_category,
        "skip_reason": None,
        # ── Runtime provenance (execution layer only) ─────────────────────
        "runtime_context": {
            "execution_phase": None,   # set later by execute_contract_test_cases
            "auth_provided": auth_provided,
            "auth_type": execution_context.get("auth_type"),
            "fallback_used": bool(dep_summary.get("fallback_used")),
            "dependency_resolution": dep_summary,
            "error_detail": error,
        },
        # Top-level aliases preserved for backward compatibility.
        "dependency_resolution": dep_summary,
        "auth_provided": auth_provided,
        "fallback_used": bool(dep_summary.get("fallback_used")),
    }


# =============================================================================
# SECTION 11 — Streaming entry point (3-pass execution)
# =============================================================================
async def execute_contract_test_cases(
    test_cases: List[Dict[str, Any]],
    *,
    base_url: str,
    auth_enabled: bool,
    auth_headers: Optional[Dict[str, str]] = None,
    timeout_seconds: float = 8.0,
    concurrency: int = 1,
    operations_by_key: Optional[Dict[str, Dict[str, Any]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Deterministic stateful execution of contract test cases.

    Streaming generator. Yields one result dict per test case (including
    skipped ones). Each result already contains validator violations.

    Three passes:
        1. Non-destructive tests (everything except DELETE).
        2. Retry tests skipped due to dependency_missing.
        3. Destructive tests (DELETE) last.
    """
    test_cases = list(test_cases or [])
    operations_by_key = operations_by_key or {}

    # Strict order enforcement
    for tc in test_cases:
        if tc.get("execution_order") is None:
            raise ValueError(
                f"Missing execution_order for {tc.get('method')} {tc.get('endpoint_path')}"
            )
    test_cases.sort(key=lambda tc: int(tc.get("execution_order") or 0))

    if test_cases:
        max_order = max(int(tc.get("execution_order") or 0) for tc in test_cases)
        logger.info("[EXECUTOR] Starting %d tests (max_order=%d)", len(test_cases), max_order)

    base = (base_url or "").rstrip("/")
    provided_auth_headers = dict(auth_headers or {})

    if UNIQUE_FORMAT_VALUES:
        reset_unique_cache()

    # ── Run-scoped execution context (single source of truth for state) ──
    execution_context: Dict[str, Any] = {
        "entities": {},          # resource_key -> [{id, raw, flat, ...}]
        "token": None,
        "auth_token": None,
        "cookie_token": None,
        "cookie_name": None,
        "auth_type": None,
        "auth_user": None,       # {email, password} from signup, replayed on login
        "phase": None,
        "current_path": None,
    }

    # Seed token if caller provided one (e.g. CI runner)
    incoming_token = None
    for k, v in provided_auth_headers.items():
        if str(k).lower() == "authorization":
            incoming_token = _normalize_token(str(v))
            break
    if incoming_token:
        execution_context["token"] = incoming_token
        execution_context["auth_token"] = incoming_token
        execution_context["auth_type"] = "bearer"

    auth_state = {
        "email": f"cognitest_contract_{uuid.uuid4().hex[:8]}@example.com",
        "password": "CogniTest@2024!",
    }

    # Stateful contract execution must be sequential.
    sem_stateful = asyncio.Semaphore(1)

    # Per-request fixed timeout profile. Production-stable across slow APIs.
    try:
        _ = float(timeout_seconds)
    except Exception:
        timeout_seconds = 8.0
    client_timeout = httpx.Timeout(connect=3.0, read=max(8.0, float(timeout_seconds)), write=8.0, pool=8.0)

    # Split into non-destructive vs destructive — DELETE always last.
    non_destructive = [tc for tc in test_cases if str(tc.get("method") or "").upper() != "DELETE"]
    destructive = [tc for tc in test_cases if str(tc.get("method") or "").upper() == "DELETE"]

    logger.info(
        "[EXECUTOR] non-destructive=%d destructive=%d operations=%d",
        len(non_destructive), len(destructive), len(operations_by_key),
    )

    from src.utils.egress_guard import validate_egress_url, build_pinned_transport
    _guard = validate_egress_url(base_url)
    async with httpx.AsyncClient(
        transport=build_pinned_transport(_guard),
        timeout=client_timeout,
        follow_redirects=False,
    ) as client:
        # ── Bootstrap auth before pass1 ──────────────────────────────────
        try:
            await _bootstrap_auth(
                test_cases=test_cases, base_url=base, client=client,
                client_timeout=client_timeout, execution_context=execution_context,
                auth_state=auth_state,
            )
        except Exception as e:
            logger.warning("[BOOTSTRAP] error (non-fatal): %s", e)

        # ── PASS 1: non-destructive ──────────────────────────────────────
        execution_context["phase"] = "pass1"
        skipped_for_retry: List[Dict[str, Any]] = []
        for tc in non_destructive:
            ex = await _run_one(
                tc=tc, client=client, base=base, auth_enabled=auth_enabled,
                provided_auth_headers=provided_auth_headers,
                execution_context=execution_context, auth_state=auth_state,
                operations_by_key=operations_by_key, client_timeout=client_timeout,
                run_sem=sem_stateful,
            )
            ex["execution_phase"] = "PASS_1"
            if isinstance(ex.get("runtime_context"), dict):
                ex["runtime_context"]["execution_phase"] = "PASS_1"
            if ENABLE_PASS2_RETRY and ex.get("execution_status") == "SKIPPED":
                if ex.get("skip_reason") in ("dependency_missing", "auth_missing"):
                    skipped_for_retry.append(tc)
                    # Don't yield yet — we'll re-run and yield the retry result.
                    continue
            yield ex
            if REQUEST_DELAY > 0:
                await asyncio.sleep(REQUEST_DELAY)
            await asyncio.sleep(0)

        # ── PASS 2: retry the dependency-skipped ones ───────────────────
        if skipped_for_retry:
            execution_context["phase"] = "pass2"
            logger.info("[EXECUTOR] PASS 2 retrying %d skipped tests", len(skipped_for_retry))
            for tc in skipped_for_retry:
                ex = await _run_one(
                    tc=tc, client=client, base=base, auth_enabled=auth_enabled,
                    provided_auth_headers=provided_auth_headers,
                    execution_context=execution_context, auth_state=auth_state,
                    operations_by_key=operations_by_key, client_timeout=client_timeout,
                    run_sem=sem_stateful,
                )
                ex["execution_phase"] = "PASS_2"
                if isinstance(ex.get("runtime_context"), dict):
                    ex["runtime_context"]["execution_phase"] = "PASS_2"
                yield ex
                if REQUEST_DELAY > 0:
                    await asyncio.sleep(REQUEST_DELAY)
                await asyncio.sleep(0)

        # ── PASS 3: destructive (DELETE) ────────────────────────────────
        if destructive:
            execution_context["phase"] = "pass3"
            logger.info("[EXECUTOR] PASS 3 destructive tests: %d", len(destructive))
            for tc in destructive:
                ex = await _run_one(
                    tc=tc, client=client, base=base, auth_enabled=auth_enabled,
                    provided_auth_headers=provided_auth_headers,
                    execution_context=execution_context, auth_state=auth_state,
                    operations_by_key=operations_by_key, client_timeout=client_timeout,
                    run_sem=sem_stateful,
                )
                ex["execution_phase"] = "PASS_3"
                if isinstance(ex.get("runtime_context"), dict):
                    ex["runtime_context"]["execution_phase"] = "PASS_3"
                ex["destructive"] = True
                yield ex
                if REQUEST_DELAY > 0:
                    await asyncio.sleep(REQUEST_DELAY)
                await asyncio.sleep(0)


# =============================================================================
# SECTION 12 — Persistence (best-effort; tolerant of missing DB)
# =============================================================================
async def persist_contract_suite_and_cases(
    *,
    project_id: str,
    triggered_by: str,
    test_cases: List[Dict[str, Any]],
    suite_name: Optional[str] = None,
) -> str:
    """Persist a TestSuite + TestCases. Returns suite id (or "stub-suite")."""
    if not _PRISMA_AVAILABLE or prisma is None:
        return "stub-suite"

    endpoint_lookup: Dict[Tuple[str, str], str] = {}
    try:
        db_endpoints = await prisma.endpoint.find_many(where={"projectId": project_id})  # type: ignore
        for ep in db_endpoints:
            endpoint_lookup[(ep.method.upper(), ep.path)] = ep.id
    except Exception:
        endpoint_lookup = {}

    try:
        suite = await create_testsuite_compat(  # type: ignore
            prisma=prisma,
            project_id=project_id,
            suite_name=suite_name or f"Contract Suite - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            category=normalize_test_category("CONTRACT"),  # type: ignore
            created_by_user_id=triggered_by,
            test_type="Contract",
            generation_method="contract",
            ai_tokens_used=0,
        )
    except Exception as e:
        logger.warning("[PERSIST] suite create failed: %s", e)
        return "stub-suite"

    ordered = sorted(list(test_cases or []), key=lambda tc: int(tc.get("execution_order") or 999999))
    rows: List[Dict[str, Any]] = []
    for tc in ordered:
        method = str(tc.get("method") or "GET").upper()
        path = str(tc.get("endpoint_path") or "/")
        endpoint_id = endpoint_lookup.get((method, path))

        assertions = {
            "test_id": tc.get("test_id"),
            "operation_key": tc.get("operation_key"),
            "kind": tc.get("kind"),
            "expected_statuses": tc.get("expected_statuses") or [],
            "security_required": bool(tc.get("security_required")),
            "auth_negative": bool(tc.get("auth_negative")),
            "missing_field": tc.get("missing_field"),
            "format_field": tc.get("format_field"),
            "format": tc.get("format"),
            "resource_key": tc.get("resource_key"),
            "dependency_map": tc.get("dependency_map") or {},
            "depends_on": tc.get("depends_on") or [],
            # Fields needed by execute_contract_test_cases for entity capture and
            # dependency resolution after a DB round-trip.
            "produces_entity": bool(tc.get("produces_entity")),
            "produced_id_paths": tc.get("produced_id_paths") or [],
            "is_producer_endpoint": bool(tc.get("is_producer_endpoint")),
            "mutation_meta": tc.get("mutation_meta") or {},
        }
        rec: Dict[str, Any] = {
            "id": tc["id"],
            "projectId": project_id,
            "suiteId": suite.id,
            "name": tc.get("name") or f"{method} {path}",
            "description": None,
            "ai_explanation": None,
            "category": "CONTRACT",
            "subCategory": "OPENAPI_CONFORMANCE",
            "test_type": "Contract",
            "endpoint_path": path,
            "method": method,
            "request_headers": PrismaJson(tc.get("request_headers") or {}),
            "request_query": PrismaJson(tc.get("request_query") or {}),
            "request_body": PrismaJson(tc.get("request_body") or {}),
            "path_params": PrismaJson(tc.get("path_params") or {}),
            "expected_status": int(tc.get("expected_status") or 0),
            "expected_response": PrismaJson({}),
            "assertions": PrismaJson(assertions),
            "priority": 1,
            "isActive": True,
            "execution_order": tc.get("execution_order"),
        }
        if endpoint_id:
            rec["endpointId"] = endpoint_id
        rows.append(rec)

    try:
        if rows:
            await prisma.testcase.create_many(data=rows, skip_duplicates=True)  # type: ignore
    except Exception:
        for row in rows:
            try:
                await prisma.testcase.create(data=row)  # type: ignore
            except Exception:
                pass

    return suite.id


# Maps three-layer final_status → DB status enum for TestResult rows.
# WARNING is stored as PASSED because the contract was substantively honored;
# the violations list in assertion_details preserves the full detail.
_FINAL_TO_DB: Dict[str, str] = {
    "PASS": "PASSED",
    "WARNING": "PASSED",
    "FAIL": "FAILED",
    "ERROR": "ERROR",
    "SKIPPED": "SKIPPED",
}

# Maps validation_status → ContractValidation.status DB enum.
# VALIDATOR_ERROR means the engine could not evaluate the contract — no
# conformance determination was made.  NOT_EVALUATED should never reach
# this map (those rows are excluded from CV creation), but is listed for
# defensive completeness.
_VALIDATION_TO_CV_STATUS: Dict[str, str] = {
    "PASS": "CONFORMANT",
    "WARNING": "CONFORMANT",
    "FAIL": "DRIFT_DETECTED",
    "VALIDATOR_ERROR": "NOT_EVALUATED",
    "NOT_EVALUATED": "NOT_EVALUATED",
}


async def persist_contract_run_and_results(
    *,
    project_id: str,
    triggered_by: str,
    suite_id: str,
    base_url: str,
    validated_results: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    if not _PRISMA_AVAILABLE or prisma is None:
        return "stub-run"

    run_id = str(uuid.uuid4())
    started = datetime.now(timezone.utc)
    run_create: Dict[str, Any] = {
        "id": run_id,
        "environment": "contract",
        "status": "RUNNING",
        "categories": ["CONTRACT"],
        "total_tests": len(validated_results),
        "startedAt": started,
        "metadata": PrismaJson({"base_url": base_url, **(metadata or {})}),
        "project": {"connect": {"id": project_id}},
        "user": {"connect": {"id": triggered_by}},
    }
    if suite_id and suite_id != "stub-suite":
        run_create["suite"] = {"connect": {"id": suite_id}}

    try:
        await prisma.testrun.create(data=run_create)  # type: ignore
    except Exception as e:
        logger.warning("[PERSIST] run create failed: %s", e)
        return "stub-run"

    passed = failed = skipped = errors = 0
    testresult_rows: List[Dict[str, Any]] = []
    contractvalidation_rows: List[Dict[str, Any]] = []

    for item in validated_results:
        tc = item.get("test_case") or {}
        exchange = item.get("exchange") or {}
        violations = item.get("violations") or []
        execution_status = str(item.get("execution_status") or exchange.get("execution_status") or "")
        validation_status_item = str(
            item.get("validation_status") or exchange.get("validation_status") or "NOT_EVALUATED"
        )
        final_status_item = str(item.get("final_status") or exchange.get("final_status") or "")
        skip_reason = item.get("skip_reason") or exchange.get("skip_reason")
        resp = exchange.get("response") or {}
        status_code = resp.get("status_code")
        actual_status_int = int(status_code) if isinstance(status_code, int) else 0

        # Backward-compat: derive final_status from old execution_status when absent.
        if not final_status_item or final_status_item not in _FINAL_TO_DB:
            if execution_status == "SKIPPED":
                final_status_item = "SKIPPED"
            elif execution_status == "PASSED":
                final_status_item = "PASS"
            elif execution_status == "FAILED":
                final_status_item = "FAIL" if violations else "ERROR"
            else:
                final_status_item = "ERROR"

        if final_status_item == "SKIPPED":
            skipped += 1
        elif final_status_item in ("PASS", "WARNING"):
            passed += 1
        elif final_status_item == "ERROR":
            errors += 1
        else:
            failed += 1

        db_status = _FINAL_TO_DB.get(final_status_item, "FAILED")

        req = exchange.get("request") or {}
        err = exchange.get("error")
        tc_id = tc.get("id")
        if not tc_id:
            continue

        testresult_rows.append({
            "status": db_status,
            "category": "CONTRACT",
            "subCategory": "OPENAPI_CONFORMANCE",
            "expected_status": int(tc.get("expected_status") or 0),
            "actual_status": actual_status_int,
            "response_time_ms": int(exchange.get("elapsed_ms") or 0),
            "error_message": (str(skip_reason) if final_status_item == "SKIPPED" and skip_reason else err),
            "assertion_details": PrismaJson({
                "execution_status": execution_status,
                "validation_status": validation_status_item,
                "final_status": final_status_item,
                "is_warning": final_status_item == "WARNING",
                "skip_reason": skip_reason,
                "violations": violations,
                "violation_count": len(violations),
                "dependency_resolution": item.get("dependency_resolution") or {},
            }),
            "request_sent": PrismaJson(redact_request_data({
                "url": req.get("url"),
                "method": req.get("method"),
                "headers": req.get("headers"),
                "query": req.get("query"),
                "body": req.get("body"),
                "sent": bool(req.get("sent")),
            })),
            "response_headers": PrismaJson(resp.get("headers") or {}),
            "response_body": PrismaJson(resp.get("json") or {}),
            "runId": run_id,
            "testCaseId": tc_id,
        })

        # ContractValidation records exist only for real HTTP exchanges where
        # contract evaluation was actually attempted.
        # Excluded: transport errors, skips, config errors, validator crashes.
        if execution_status not in {"EXECUTED", "PASSED", "FAILED"}:
            continue
        if validation_status_item == "VALIDATOR_ERROR":
            continue

        cv_status = _VALIDATION_TO_CV_STATUS.get(validation_status_item, "DRIFT_DETECTED")

        # Violation category summary: group violation counts by type for
        # fast analytics and dashboard queries without deserialising the list.
        _vcat: Dict[str, int] = {}
        for _v in violations:
            _vtype = str(_v.get("violation") or "contract.unknown")
            _vcat[_vtype] = _vcat.get(_vtype, 0) + 1

        cv_data: Dict[str, Any] = {
            "status": cv_status,
            "createdBy": triggered_by,
            "expected_schema": PrismaJson({"expected_statuses": tc.get("expected_statuses") or []}),
            "actual_schema": PrismaJson({"status_code": status_code, "content_type": resp.get("content_type")}),
            "diffs": PrismaJson({
                "violations": violations,
                "validation_status": validation_status_item,
                "violation_count": len(violations),
                "violation_category_summary": _vcat,
            }),
            "runId": run_id,
        }
        if tc.get("endpoint_id"):
            cv_data["endpointId"] = tc["endpoint_id"]
        if tc.get("spec_id"):
            cv_data["specId"] = tc["spec_id"]
        contractvalidation_rows.append(cv_data)

    try:
        if testresult_rows:
            await prisma.testresult.create_many(data=testresult_rows)  # type: ignore
    except Exception:
        for row in testresult_rows:
            try:
                await prisma.testresult.create(data=row)  # type: ignore
            except Exception:
                pass
    try:
        if contractvalidation_rows:
            await prisma.contractvalidation.create_many(data=contractvalidation_rows)  # type: ignore
    except Exception:
        for row in contractvalidation_rows:
            try:
                await prisma.contractvalidation.create(data=row)  # type: ignore
            except Exception:
                pass

    completed = datetime.now(timezone.utc)
    duration_ms = int((completed - started).total_seconds() * 1000)
    try:
        await prisma.testrun.update(  # type: ignore
            where={"id": run_id},
            data={
                "status": "COMPLETED",
                # errors (transport/config) are included in failed for the DB
                # counter to avoid a schema migration; the detailed breakdown
                # is in assertion_details on each TestResult row.
                "passed": passed,
                "failed": failed + errors,
                "skipped": skipped,
                "completedAt": completed,
                "durationMs": duration_ms,
            },
        )
    except Exception:
        pass

    return run_id


# =============================================================================
# SECTION 13 — Top-level engine
# =============================================================================
async def run_contract_engine(
    *,
    project_id: str,
    triggered_by: str,
    canonical_spec: Any,
    base_url: str,
    auth_enabled: bool = True,
    token: Optional[str] = None,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """End-to-end strict contract run.

    Pipeline:
        spec -> generate test cases -> execute (with inline validation)
             -> persist -> return summary.
    """
    spec = coerce_canonical_spec(canonical_spec)
    ops = spec.get("operations") or []
    operations_by_key: Dict[str, Dict[str, Any]] = {}
    for op in ops if isinstance(ops, list) else []:
        if isinstance(op, dict) and isinstance(op.get("operation_key"), str):
            operations_by_key[op["operation_key"]] = op

    test_cases = generate_contract_test_cases(spec)
    logger.info("[ENGINE] generated %d test cases", len(test_cases))

    suite_id = "stub-suite"
    try:
        suite_id = await persist_contract_suite_and_cases(
            project_id=project_id, triggered_by=triggered_by, test_cases=test_cases,
        )
    except Exception as e:
        logger.warning("[ENGINE] persist suite failed: %s", e)

    auth_headers: Optional[Dict[str, str]] = None
    norm_token = _normalize_token(token)
    if norm_token:
        auth_headers = {"Authorization": f"Bearer {norm_token}"}

    exchanges: List[Dict[str, Any]] = []
    async for ex in execute_contract_test_cases(
        test_cases,
        base_url=base_url,
        auth_enabled=auth_enabled,
        auth_headers=auth_headers,
        timeout_seconds=timeout_seconds,
        concurrency=1,
        operations_by_key=operations_by_key,
    ):
        exchanges.append(ex)

    # detect_wrong_server hint
    all_statuses: List[int] = []
    for ex in exchanges:
        sc = (ex.get("exchange") or {}).get("response", {}).get("status_code")
        if isinstance(sc, int):
            all_statuses.append(sc)
    detect_wrong_server(all_statuses)

    # Coverage + final shape (validator already ran inline)
    coverage = {
        "statuses": set(),
        "content_types": set(),
        "schemas_validated": set(),
        "headers_checked": set(),
        "methods": set(),
    }

    validated: List[Dict[str, Any]] = []
    for ex in exchanges:
        resp = (ex.get("exchange") or {}).get("response") or {}
        sc = resp.get("status_code")
        if isinstance(sc, int):
            coverage["statuses"].add(sc)
        m = (ex.get("exchange") or {}).get("request", {}).get("method")
        if m:
            coverage["methods"].add(m)
        ct_raw = resp.get("content_type") or _get_header_ci(resp.get("headers") or {}, "Content-Type")
        if ct_raw:
            coverage["content_types"].add(normalize_content_type(ct_raw))

        tc = ex.get("test_case") or {}
        op = operations_by_key.get(str(tc.get("operation_key") or ""))
        # Coverage hooks (no double-validation)
        if op and isinstance(sc, int):
            expected = [str(x) for x in (tc.get("expected_statuses") or [])]
            documented = ("default" in expected) or (str(sc) in expected)
            if documented:
                responses = op.get("responses") or {}
                doc = responses.get(str(sc)) if isinstance(responses, dict) else None
                if not isinstance(doc, dict):
                    doc = responses.get("default") if isinstance(responses, dict) else None
                if isinstance(doc, dict):
                    for header_name in (doc.get("headers") or {}).keys():
                        coverage["headers_checked"].add(str(header_name))
                    documented_ct = normalize_content_type(doc.get("content_type"))
                    actual_ct = normalize_content_type(resp.get("content_type"))
                    schema = doc.get("json_schema")
                    if (
                        documented_ct and actual_ct and documented_ct == actual_ct
                        and documented_ct == "application/json"
                        and isinstance(schema, dict)
                        and resp.get("json") is not None
                    ):
                        coverage["schemas_validated"].add(str(op.get("operation_key") or f"{m} {tc.get('endpoint_path')}"))

        validated.append({
            "test_case": tc,
            "exchange": ex.get("exchange") or {},
            "violations": ex.get("violations") or [],
            "execution_status": ex.get("execution_status") or "TRANSPORT_ERROR",
            "validation_status": ex.get("validation_status") or "NOT_EVALUATED",
            "final_status": ex.get("final_status") or "ERROR",
            "skip_reason": ex.get("skip_reason"),
            "dependency_resolution": ex.get("dependency_resolution") or {},
        })

    run_id = "stub-run"
    try:
        run_id = await persist_contract_run_and_results(
            project_id=project_id, triggered_by=triggered_by, suite_id=suite_id,
            base_url=base_url, validated_results=validated,
            metadata={"doc_id": spec.get("doc_id")},
        )
    except Exception as e:
        logger.warning("[ENGINE] persist run failed: %s", e)

    # Run-level stats — derived from final_status (the three-layer truth).
    # warnings are separately tallied so they remain visible in the summary
    # even though they share the "passed" contract-compliance bucket.
    skipped = sum(1 for v in validated if v.get("final_status") == "SKIPPED")
    failed = sum(1 for v in validated if v.get("final_status") == "FAIL")
    warnings = sum(1 for v in validated if v.get("final_status") == "WARNING")
    passed = sum(1 for v in validated if v.get("final_status") in ("PASS", "WARNING"))
    errors = sum(1 for v in validated if v.get("final_status") == "ERROR")

    coverage_summary = {
        "unique_statuses": len(coverage["statuses"]),
        "schemas_validated": len(coverage["schemas_validated"]),
        "content_types": len(coverage["content_types"]),
        "headers_validated": len(coverage["headers_checked"]),
        "methods_observed": len(coverage["methods"]),
        "total_operations": len(operations_by_key),
    }

    # Confidence score
    transport_errors = 0
    validator_errors = 0
    fallback_positive = 0
    fallback_consumer_positive = 0
    for ex in exchanges:
        es = ex.get("execution_status") or ""
        vs = ex.get("validation_status") or ""
        if es in ("TRANSPORT_ERROR", "TIMEOUT"):
            transport_errors += 1
        if vs == "VALIDATOR_ERROR":
            validator_errors += 1
        if ex.get("fallback_used"):
            tc0 = ex.get("test_case") or {}
            if str(tc0.get("kind") or "") == "positive":
                fallback_positive += 1
                if str(tc0.get("flow_type") or "").lower() == "consumer":
                    fallback_consumer_positive += 1

    total_ops = max(1, coverage_summary["total_operations"])
    schema_ratio = min(1.0, coverage_summary["schemas_validated"] / total_ops)
    methods_score = min(20, coverage_summary["methods_observed"] * 5)
    statuses_score = min(15, coverage_summary["unique_statuses"] * 3)
    schema_score = int(50 * schema_ratio)

    # config_errors = ERROR results that are NOT transport/validator errors
    config_errors = max(0, errors - transport_errors - validator_errors)
    skip_ratio = (skipped / max(1, len(validated))) if validated else 0.0

    # ── Two-dimensional confidence model ──────────────────────────────────
    #
    # Reliability dimension (0-100):
    #   "How trustworthy is the execution pipeline?"
    #   Penalises infrastructure and configuration problems that make results
    #   unreliable regardless of what the API actually does.
    #
    reliability_raw = int(100
        - transport_errors * 25          # API unreachable → results untrustworthy
        - config_errors * 15             # spec mismatch → some contracts untested
        - validator_errors * 15          # engine crash → some contracts unevaluated
        - fallback_consumer_positive * 10  # dep-fallback on consumers → less trustworthy
        - fallback_positive * 5          # dep-fallback on producers → moderate risk
        - int(skip_ratio * 25)           # large skip ratio → coverage gap
    )
    reliability_score = max(0, min(100, reliability_raw))

    # Conformance dimension (0-100):
    #   "How well does the API honor its documented contracts?"
    #   Only applies to tests that were actually evaluated.
    #   Penalises contract failures and drift warnings.
    #
    total_evaluated = max(1, len(validated) - skipped - errors)
    fail_ratio = failed / total_evaluated
    warn_ratio = warnings / total_evaluated
    conformance_raw = int(100
        - int(fail_ratio * 80)           # failures directly indicate non-conformance
        - int(warn_ratio * 15)           # warnings indicate spec drift / evolution
    )
    conformance_score = max(0, min(100, conformance_raw))

    # Coverage depth score (0-100):
    #   "How deeply was the contract exercised?"
    #   Rewards schema validation, method diversity, and status diversity.
    #
    coverage_depth = min(100, 15 + schema_score + methods_score + statuses_score)

    # Weighted final confidence:
    #   30% reliability  — trustworthiness of the execution pipeline
    #   50% conformance  — how well the API honours its contracts
    #   20% coverage     — depth of contract exercised
    confidence_score = int(min(100, max(0,
        0.30 * reliability_score
        + 0.50 * conformance_score
        + 0.20 * coverage_depth
    )))

    return {
        "suite_id": suite_id,
        "run_id": run_id,
        "total": len(validated),
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "skipped": skipped,
        "errors": errors,
        "coverage": coverage_summary,
        "confidence_score": confidence_score,
        "confidence_breakdown": {
            # Two-dimensional model
            "reliability_score": reliability_score,
            "conformance_score": conformance_score,
            "coverage_depth": coverage_depth,
            # Component counts
            "transport_errors": transport_errors,
            "config_errors": config_errors,
            "validator_errors": validator_errors,
            "contract_failures": failed,
            "warnings": warnings,
            "fallback_positive": fallback_positive,
            "fallback_consumer_positive": fallback_consumer_positive,
            "skipped": skipped,
            "errors": errors,
            "total": len(validated),
            "total_evaluated": total_evaluated,
            "fail_ratio": round(fail_ratio, 3),
            "warn_ratio": round(warn_ratio, 3),
            "skip_ratio": round(skip_ratio, 3),
        },
    }