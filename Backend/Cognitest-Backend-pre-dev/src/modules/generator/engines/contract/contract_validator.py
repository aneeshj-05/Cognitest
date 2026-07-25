from __future__ import annotations

import json
import copy
import os
import re
from typing import Any, Dict, List, Optional

try:
    from typing import TypedDict
except ImportError:  # Python < 3.8
    from typing_extensions import TypedDict  # type: ignore

import logging
from jsonschema import Draft202012Validator, FormatChecker

from .contract_rules import normalize_content_type

logger = logging.getLogger(__name__)


# ================================
# FORMAL RESULT MODEL
# ================================

class ValidationResult(TypedDict):
    """Formal return type of validate_exchange.

    validation_status:
        PASS            — all contract rules satisfied
        FAIL            — one or more contract rules violated
        WARNING         — only low-severity violations (e.g. drift in non-strict mode)
        NOT_EVALUATED   — called defensively with no status code (should not happen in normal flow)

    violations:
        List of individual contract violations.  Only populated for FAIL/WARNING.
        Every violation carries a normalised violation_type from the fully
        hierarchical contract.* taxonomy:

            contract.status         — HTTP status code not in documented set
            contract.schema         — Response body fails JSON Schema
            contract.content_type   — Content-Type missing or mismatched
            contract.header         — Required response header missing or invalid
            contract.auth           — Auth-related violation (positive 401, auth-negative wrong status)
            contract.negative       — Negative test did not get expected error response
            contract.semantic       — Semantic error (error payload in 2xx response)
            contract.drift          — Undocumented response fields (schema evolution signal)
            contract.example        — OpenAPI spec example fails its own schema
            contract.server_error   — Server returned 5xx (always a contract failure signal)
    """
    validation_status: str
    violations: List[Dict[str, Any]]

REQUEST_VALIDATION_NEGATIVES = {
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
}

# Negative kinds that have their OWN specific violation block in validate_exchange.
# The generic "negative returned 2xx" guard must exclude these to prevent
# duplicate contract.negative entries for the same finding.
_ALREADY_HANDLED_NEGATIVES: frozenset = frozenset(
    REQUEST_VALIDATION_NEGATIVES | {"negative_auth_missing"}
)

INFRA_ERROR_STATUSES = {502, 503, 504}

IGNORE_HEADERS = {
    "date",
    "server",
    "set-cookie",
    "content-length",
    "connection",
}

VALIDATOR_CACHE: dict[str, Draft202012Validator] = {}

def detect_wrong_server(statuses: list[int]):

    total = len(statuses)

    if total == 0:
        return

    counts: dict[int, int] = {}

    for s in statuses:
        counts[s] = counts.get(s, 0) + 1

    if not counts:
        return

    # Use __getitem__ to keep the key function non-Optional for type checkers.
    most_common = max(counts, key=counts.__getitem__)

    if counts[most_common] / total > 0.8:
        logger.warning(
            f"{most_common} returned for "
            f"{counts[most_common]}/{total} tests. "
            "Possible wrong API base URL."
        )

# ================================
# ADVANCED FEATURES CONFIGURATION
# ================================

# Enterprise strictness must be environment-driven.
STRICT_MODE = str(os.getenv("COGNITEST_VALIDATOR_STRICT", "0") or "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

# Schema tolerance is configurable (default: enabled for real-world APIs).
TOLERANT_SCHEMA = str(os.getenv("COGNITEST_TOLERANT_SCHEMA", "1") or "1").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}

ENABLE_EXAMPLE_VALIDATION = True
ENABLE_SEMANTIC_ERROR_DETECTION = True


# ================================
# HELPER FUNCTIONS
# ================================

def _violation(
    *,
    severity: str = "HIGH",
    method: str,
    path: str,
    expected_statuses: list[str],
    actual_status: Optional[int],
    security_required: bool,
    auth_provided: bool,
    content_type: Optional[str],
    schema_errors: Optional[list[str]] = None,
    violation_type: str = "contract.mismatch",
) -> dict[str, Any]:

    return {
        "severity": severity,
        "violation": violation_type,
        "method": method,
        "path": path,
        "expected_statuses": expected_statuses,
        "actual_status": actual_status,
        "security_required": security_required,
        "auth_provided": auth_provided,
        "content_type": content_type,
        "schema_validation_errors": schema_errors or [],
    }


def _allowed_status(expected_statuses: list[str], actual: int, kind: str) -> bool:

    expected = {str(x) for x in expected_statuses}

    # NOTE: Even if the spec includes `default`, server errors are NEVER considered pass.

    # Strict contract validation
    if str(actual) in expected:
        return True

    # Wildcard support (2XX, 4XX, etc)
    for s in expected:
        s_norm = str(s).strip().upper()
        if re.fullmatch(r"[1-5]XX", s_norm):
            if int(s_norm[0]) == actual // 100:
                return True

    return False


def _pick_success_class_response(responses: dict[str, Any], actual_status: int):

    cls = actual_status // 100

    for code, resp in responses.items():

        if isinstance(code, str) and code.isdigit():

            if int(code) // 100 == cls and isinstance(resp, dict):
                return resp

    return None


def _make_schema_tolerant(schema: dict):

    if not isinstance(schema, dict):
        return

    if schema.get("type") == "object":
        schema.setdefault("additionalProperties", True)

    if isinstance(schema.get("type"), str):
        schema["type"] = [schema["type"], "null"]

    props = schema.get("properties")
    if isinstance(props, dict):
        for sub in props.values():
            _make_schema_tolerant(sub)

    items = schema.get("items")
    if isinstance(items, dict):
        _make_schema_tolerant(items)


def _collect_drift_fields(
    instance: Any,
    schema: dict,
    path: str = "",
    *,
    max_depth: int = 8,
) -> List[str]:
    """Recursively collect dotted paths to all undocumented response fields.

    Walks the FULL response JSON tree and compares every object against the
    corresponding schema's `properties`.  Fields present in the actual
    response but absent from the schema are reported as drift.

    Policy (strict contract testing — NOT lenient OpenAPI parsing):
        - `additionalProperties: true`  → explicitly permitted → no drift
        - `additionalProperties: <schema>` → explicitly permitted → no drift
        - `additionalProperties` absent or `false` → treated as NOT permitted
          (the API returns fields the contract does not document → drift)

    This is intentionally stricter than the JSON Schema default
    (absent additionalProperties === {} === allow anything) because this
    platform is a contract governance tool, not an OpenAPI linter.

    Handles:
        - Nested objects  (via `properties`)
        - Arrays of objects (via `items`, samples first 3 items)
        - allOf / anyOf / oneOf composition (merges sub-schema properties)
    """
    if max_depth <= 0 or not isinstance(schema, dict):
        return []

    undocumented: List[str] = []

    if isinstance(instance, dict):
        # Merge properties from the direct schema + any composition sub-schemas
        props: dict = dict(schema.get("properties") or {})
        for combiner in ("allOf", "anyOf", "oneOf"):
            for sub in (schema.get(combiner) or []):
                if isinstance(sub, dict):
                    props.update(sub.get("properties") or {})

        # No documented properties at all → nothing to compare; skip
        if not props:
            return []

        # Contract explicitly allows additional properties → do not flag,
        # but still recurse into documented sub-schemas for deeper drift.
        add_props = schema.get("additionalProperties")
        explicitly_open = add_props is True or isinstance(add_props, dict)

        for key in instance:
            field_path = f"{path}.{key}" if path else key
            if key in props:
                # Recurse into documented fields to find nested undocumented content
                sub_schema = props[key]
                if isinstance(sub_schema, dict):
                    undocumented.extend(
                        _collect_drift_fields(
                            instance[key], sub_schema, field_path,
                            max_depth=max_depth - 1,
                        )
                    )
            elif not explicitly_open:
                # Undocumented field and the contract does not permit extras
                undocumented.append(field_path)

    elif isinstance(instance, list):
        items_schema = schema.get("items")
        if isinstance(items_schema, dict):
            # Sample at most 3 items — enough to detect structural drift
            # without blowing up on large paginated arrays.
            seen_paths: set = set()
            for item in instance[:3]:
                for p in _collect_drift_fields(
                    item, items_schema,
                    f"{path}[*]" if path else "[*]",
                    max_depth=max_depth - 1,
                ):
                    if p not in seen_paths:
                        seen_paths.add(p)
                        undocumented.append(p)

    return undocumented


def _validate_schema_example(schema: dict, example: Any):

    try:
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(example))
        return errors
    except Exception:
        return []


def _derive_validation_status(violations: list) -> str:
    if not violations:
        return "PASS"
    if all(v.get("severity", "HIGH") == "LOW" for v in violations):
        return "WARNING"
    return "FAIL"


def _detect_semantic_errors(instance: Any):
    """Detect APIs returning a success HTTP status with an error payload body.

    Only fires when there is strong, unambiguous evidence of an error — a
    non-empty 'error'/'errors' field or a clearly populated error-code/message
    field.  Generic fields such as 'message' and 'errorType' are intentionally
    excluded because they appear in legitimate success responses across nearly
    all real-world APIs (e.g. {"message": "Order created", "data": {...}}).
    """

    if not isinstance(instance, dict):
        return None

    # 'error' — flag only when the value is a truthy non-empty string/object.
    # Ignore False, 0, None, "" which some APIs use to mean "no error".
    error_val = instance.get("error")
    if error_val is not None and error_val is not False and error_val != 0:
        if isinstance(error_val, str) and error_val.strip():
            return "Response contains non-empty 'error' field despite success status"
        if isinstance(error_val, (dict, list)) and error_val:
            return "Response contains non-empty 'error' field despite success status"

    # 'errors' — flag only when the collection is non-empty.
    errors_val = instance.get("errors")
    if errors_val is not None:
        if isinstance(errors_val, list) and errors_val:
            return "Response contains non-empty 'errors' array despite success status"
        if isinstance(errors_val, str) and errors_val.strip():
            return "Response contains non-empty 'errors' field despite success status"
        if isinstance(errors_val, dict) and errors_val:
            return "Response contains non-empty 'errors' field despite success status"

    # Explicit error-code fields — only flag when value is clearly an error
    # indicator (non-zero, non-empty, non-null, non-false).
    for field in ("error_message", "errorCode", "error_code"):
        val = instance.get(field)
        if val is None or val is False or val == 0 or val == "":
            continue
        if isinstance(val, str) and not val.strip():
            continue
        return f"Response contains '{field}' field despite success status"

    # 'message' and 'errorType' are intentionally excluded — they are too
    # common in success payloads to be reliable semantic-error signals.

    return None


def _parse_header_value(raw: Any, schema: dict):

    if raw is None:
        return None, None

    raw = str(raw)

    t = schema.get("type")

    if t in (None, "string"):
        return raw, None

    if t == "integer":
        try:
            return int(raw), None
        except Exception:
            return None, "expected integer"

    if t == "number":
        try:
            return float(raw), None
        except Exception:
            return None, "expected number"

    if t == "boolean":

        s = raw.lower()

        if s in ("true", "1"):
            return True, None

        if s in ("false", "0"):
            return False, None

        return None, "expected boolean"

    return raw, None


def _validate_response_headers(
    *,
    documented_headers: dict[str, Any],
    actual_headers: dict[str, Any],
):

    errors = []

    actual_lc = {str(k).lower(): v for k, v in actual_headers.items()}

    for header_name, header_spec in documented_headers.items():

        name_lc = header_name.lower()

        if name_lc in IGNORE_HEADERS:
            continue

        required = bool(header_spec.get("required"))
        schema = header_spec.get("json_schema", {})

        actual = actual_lc.get(name_lc)

        if required and actual is None:
            errors.append(f"response.headers.{header_name}: required header missing")
            continue

        if actual is None:
            continue

        parsed, err = _parse_header_value(actual, schema)

        if err:
            errors.append(f"response.headers.{header_name}: {err}")
            continue

        try:

            validator = Draft202012Validator(schema, format_checker=FormatChecker())

            for e in validator.iter_errors(parsed):

                path_str = ".".join(str(p) for p in e.absolute_path)
                loc = f"response.headers.{header_name}{'.'+path_str if path_str else ''}"

                errors.append(f"{loc}: {e.message}")

        except Exception:
            pass

    return sorted(set(errors))


def _extract_json(resp):

    if resp.get("json") is not None:
        return resp.get("json")

    body = resp.get("body")

    if isinstance(body, str):
        try:
            return json.loads(body)
        except Exception:
            return None

    return None


# ================================
# MAIN VALIDATION FUNCTION
# ================================

def validate_exchange(
    *,
    operation: dict[str, Any],
    test_case: dict[str, Any],
    exchange: dict[str, Any],
    auth_provided: bool,
):

    op = operation
    tc = test_case

    method = str(tc.get("method") or op.get("method") or "GET").upper()
    path = str(tc.get("endpoint_path") or op.get("path") or "/")

    security_required = bool(tc.get("security_required") or op.get("security_required"))

    resp = exchange.get("response") or {}

    actual_status = resp.get("status_code") or resp.get("status")

    actual_status_int = None

    if isinstance(actual_status, int):
        actual_status_int = actual_status
    elif isinstance(actual_status, str) and actual_status.isdigit():
        actual_status_int = int(actual_status)

    content_type = normalize_content_type(resp.get("content_type"))

    responses = op.get("responses") or {}

    expected_statuses = tc.get("expected_statuses")
    if not expected_statuses:
        expected_statuses = sorted(str(k) for k in responses.keys())

    violations = []

    # Validator is only invoked when execution_status == EXECUTED.
    # A None status_code here indicates an unexpected call path; treat as
    # non-evaluable rather than a contract failure.
    if actual_status_int is None:
        return {"validation_status": "NOT_EVALUATED", "violations": []}

    body = resp.get("body") or ""

    if (
        actual_status_int in INFRA_ERROR_STATUSES
        and isinstance(body, str)
        and "<html" in body.lower()
    ):
        return {"validation_status": _derive_validation_status(violations), "violations": violations}

    tc_type = str(tc.get("kind") or "positive")

    # Strict rule: positive tests must NEVER return 401.
    # If they do, it's an auth failure, not a contract pass.
    if tc_type == "positive" and actual_status_int == 401:
        violations.append(
            _violation(
                method=method,
                path=path,
                expected_statuses=expected_statuses,
                actual_status=actual_status_int,
                security_required=security_required,
                auth_provided=auth_provided,
                content_type=content_type,
                schema_errors=["Positive test failed with 401 Unauthorized"],
                violation_type="contract.auth",
            )
        )
        return {"validation_status": _derive_validation_status(violations), "violations": violations}

    # -------------------------------------------------
    # Request validation negatives must return 4xx
    # -------------------------------------------------

    if tc_type in REQUEST_VALIDATION_NEGATIVES:

        if not (400 <= actual_status_int <= 499):

            if tc_type == "negative_required_missing" and 200 <= actual_status_int < 300:
                schema_errors = ["Required-field negative returned 2xx — API accepted a request missing a required field"]
            elif tc_type == "negative_format_invalid" and 200 <= actual_status_int < 300:
                schema_errors = ["Invalid format accepted by API — format constraint not enforced by the server"]
            elif 200 <= actual_status_int < 300:
                schema_errors = [f"Validation negative ({tc_type}) returned 2xx — API accepted an invalid request"]
            else:
                schema_errors = [f"Validation negative ({tc_type}) did not return a client error (4xx); got {actual_status_int}"]

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=schema_errors,
                    violation_type="contract.negative",
                )
            )


    # Special handling for auth-negative tests
    if tc_type == "negative_auth_missing":

        if actual_status_int not in (401, 403):

            if 200 <= actual_status_int < 300:
                schema_errors = ["Auth-negative returned 2xx"]
            else:
                schema_errors = ["Auth negative test did not return 401/403"]

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=["401", "403"],
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=schema_errors,
                    violation_type="contract.auth",
                )
            )


    is_negative = tc_type.startswith("negative")

    # Production rule: ANY 5xx is always a contract failure signal (never pass).
    if 500 <= actual_status_int <= 599:
        violations.append(
            _violation(
                method=method,
                path=path,
                expected_statuses=expected_statuses,
                actual_status=actual_status_int,
                security_required=security_required,
                auth_provided=auth_provided,
                content_type=content_type,
                schema_errors=["Server returned 5xx (always fail)"],
                violation_type="contract.server_error",
            )
        )
        return {"validation_status": _derive_validation_status(violations), "violations": violations}

    # Generic negative-returned-2xx guard.
    # Only fires for negative kinds NOT already handled by a specific block
    # above (REQUEST_VALIDATION_NEGATIVES and negative_auth_missing each
    # produce their own, more specific violation).  Firing here for those
    # kinds would produce duplicate contract.negative entries.
    if (
        is_negative
        and 200 <= actual_status_int < 300
        and tc_type not in _ALREADY_HANDLED_NEGATIVES
    ):
        violations.append(
            _violation(
                method=method,
                path=path,
                expected_statuses=expected_statuses,
                actual_status=actual_status_int,
                security_required=security_required,
                auth_provided=auth_provided,
                content_type=content_type,
                schema_errors=[
                    f"Negative test ({tc_type}) returned success status {actual_status_int} "
                    f"— expected a non-2xx response"
                ],
                violation_type="contract.negative",
            )
        )


    if not _allowed_status(expected_statuses, actual_status_int, tc_type):

        violations.append(
            _violation(
                method=method,
                path=path,
                expected_statuses=expected_statuses,
                actual_status=actual_status_int,
                security_required=security_required,
                auth_provided=auth_provided,
                content_type=content_type,
                schema_errors=["Status code not allowed per contract"],
                violation_type="contract.status",
            )
        )

        return {"validation_status": _derive_validation_status(violations), "violations": violations}

    doc_resp = responses.get(str(actual_status_int))

    if not doc_resp and 200 <= actual_status_int < 300:
        doc_resp = _pick_success_class_response(responses, actual_status_int)

    if not doc_resp:
        doc_resp = responses.get("default")

    if not isinstance(doc_resp, dict):
        return {"validation_status": _derive_validation_status(violations), "violations": violations}

    documented_ct = normalize_content_type(doc_resp.get("content_type"))

    if documented_ct:

        if content_type is None:

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=["Response Content-Type header missing"],
                    violation_type="contract.content_type",
                )
            )

        elif not content_type.startswith(documented_ct):

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=["Response Content-Type does not match documented media type"],
                    violation_type="contract.content_type",
                )
            )

    # Header validation
    documented_headers = doc_resp.get("headers") or {}
    actual_headers = resp.get("headers") or {}

    if documented_headers:

        header_errors = _validate_response_headers(
            documented_headers=documented_headers,
            actual_headers=actual_headers,
        )

        if header_errors:

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=header_errors,
                    violation_type="contract.header",
                )
            )

    schema = doc_resp.get("json_schema")

    if isinstance(schema, dict) and content_type and ("json" in content_type or "+json" in content_type):

        instance = _extract_json(resp)

        if instance is None:

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=["Response body is not valid JSON"],
                    violation_type="contract.schema",
                )
            )

            return {"validation_status": _derive_validation_status(violations), "violations": violations}

        schema_copy = copy.deepcopy(schema)

        if TOLERANT_SCHEMA:
            _make_schema_tolerant(schema_copy)

        # Stable cache key: id(schema_copy) is always different.
        try:
            schema_key = json.dumps(schema_copy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            schema_key = repr(schema_copy)

        validator = VALIDATOR_CACHE.get(schema_key)

        if validator is None:
            validator = Draft202012Validator(schema_copy, format_checker=FormatChecker())
            VALIDATOR_CACHE[schema_key] = validator
            
        errors = list(validator.iter_errors(instance))

        if errors:

            msgs = []

            for e in errors:
                path_str = ".".join(str(p) for p in e.absolute_path)
                loc = f"response.json{'.'+path_str if path_str else ''}"

                actual_val = None
                try:
                    cur: Any = instance
                    for p in e.absolute_path:
                        if isinstance(cur, dict):
                            cur = cur[p]
                        elif isinstance(cur, list):
                            cur = cur[int(p)]
                        else:
                            break
                    else:
                        actual_val = cur
                except Exception:
                    actual_val = None

                msgs.append(f"{loc}: {e.message} (actual={actual_val})")

            violations.append(
                _violation(
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=sorted(set(msgs)),
                    violation_type="contract.schema",
                )
            )

        # ── Drift detection: schema-driven, recursive, strict by policy ─────────
        #
        # Walks the FULL response JSON (not just top-level) using the ORIGINAL
        # schema — NOT schema_copy — because _make_schema_tolerant injects
        # `additionalProperties: True` everywhere, which would suppress all
        # drift findings in the recursive walker.
        #
        # Policy (contract testing, not lenient OpenAPI parsing):
        #   absent additionalProperties → NOT permitted → drift
        #   explicit additionalProperties: true → permitted → no drift at that level
        #
        # Severity:
        #   STRICT_MODE=1 → HIGH → FAIL  (any undocumented field is a violation)
        #   STRICT_MODE=0 → LOW  → WARNING (additive-safe drift, spec-lag signal)
        #
        # Scope: 2xx SUCCESS RESPONSES ONLY.
        #   Error response schemas (4xx) are routinely underspecified in OpenAPI
        #   specs — frameworks like FastAPI/Pydantic add extra diagnostic fields
        #   (e.g. `url` in validation error details) that specs rarely enumerate.
        #   Running drift on 4xx produces high-noise, low-value findings.
        #   The contract.status and contract.schema checks already govern whether
        #   an error response is semantically correct.
        #
        # This detects (on success responses):
        #   • top-level undocumented fields
        #   • nested undocumented fields inside documented objects
        #   • undocumented fields inside array items
        drift_paths = _collect_drift_fields(instance, schema) if 200 <= actual_status_int < 300 else []
        if drift_paths:
            drift_mode = "breaking" if STRICT_MODE else "additive-safe"
            # Deduplicate (preserve discovery order for readability)
            drift_paths = list(dict.fromkeys(drift_paths))

            # ── Rich per-field diagnostic messages ────────────────────────────
            # Each undocumented field gets its own message so the UI can render
            # one line per finding.  Messages carry enough context for a
            # developer to understand WHAT drifted, WHERE in the structure,
            # and WHY it was flagged (contract governance stance).
            def _drift_msg(fp: str) -> str:
                if "[*]" in fp:
                    loc_kind = "array element field"
                    guidance = "The array items schema does not document this field"
                elif "." in fp:
                    depth = fp.count(".")
                    loc_kind = f"nested field (depth {depth})"
                    guidance = "The parent object schema does not document this field"
                else:
                    loc_kind = "top-level response field"
                    guidance = "The response schema does not document this field"
                action = "Contract violation" if STRICT_MODE else "Spec-lag signal"
                return (
                    f"[{drift_mode}] '{fp}': undocumented {loc_kind} — "
                    f"{guidance}. {action}: update the OpenAPI schema to document "
                    f"this field or explicitly set additionalProperties: true to "
                    f"allow extensibility."
                )

            MAX_DRIFT_MSGS = 25
            drift_errors = [_drift_msg(fp) for fp in drift_paths[:MAX_DRIFT_MSGS]]
            if len(drift_paths) > MAX_DRIFT_MSGS:
                overflow = len(drift_paths) - MAX_DRIFT_MSGS
                drift_errors.append(
                    f"... and {overflow} more undocumented field(s) not shown "
                    f"(total: {len(drift_paths)} drift findings across this response)"
                )

            violations.append(
                _violation(
                    severity=("HIGH" if STRICT_MODE else "LOW"),
                    method=method,
                    path=path,
                    expected_statuses=expected_statuses,
                    actual_status=actual_status_int,
                    security_required=security_required,
                    auth_provided=auth_provided,
                    content_type=content_type,
                    schema_errors=drift_errors,
                    violation_type="contract.drift",
                )
            )

        if ENABLE_SEMANTIC_ERROR_DETECTION and 200 <= actual_status_int < 300:

            semantic_error = _detect_semantic_errors(instance)

            if semantic_error:

                violations.append(
                    _violation(
                        method=method,
                        path=path,
                        expected_statuses=expected_statuses,
                        actual_status=actual_status_int,
                        security_required=security_required,
                        auth_provided=auth_provided,
                        content_type=content_type,
                        schema_errors=[semantic_error],
                        violation_type="contract.semantic",
                    )
                )

    if ENABLE_EXAMPLE_VALIDATION:

        example = doc_resp.get("example")

        if example and isinstance(schema, dict):

            example_errors = _validate_schema_example(schema, example)

            if example_errors:

                violations.append(
                    _violation(
                        method=method,
                        path=path,
                        expected_statuses=expected_statuses,
                        actual_status=actual_status_int,
                        security_required=security_required,
                        auth_provided=auth_provided,
                        content_type=content_type,
                        schema_errors=["OpenAPI example does not match schema"],
                        violation_type="contract.example",
                    )
                )

    return {"validation_status": _derive_validation_status(violations), "violations": violations}