import os
import time
import json
import asyncio
import logging
from collections import Counter
from typing import Any

import pytest
import httpx

from src.modules.generator.spec_parser import extract_endpoints, Endpoint
from .mutation_taxonomy import MutationType
from .expectation_engine import validate_response, validate_response_from_spec

# Dynamic generation lookup imports
import pkgutil
import importlib
import inspect
import src.modules.generator.engines.negative as neg_pkg
from .core import TokenMutator

logger = logging.getLogger(__name__)


def _extract_resource_id(response_json: dict, capture_fields: list[str]) -> str | None:
    """
    Extract a resource ID from a response JSON dict.

    Search order:
      1. Top-level fields in capture_fields priority order
      2. Nested under 'data' key (common envelope pattern)
      3. Nested under 'result' key
      4. Nested under 'resource' key
      5. Any field whose name ends with 'id' or 'Id' at top level
    """
    if not isinstance(response_json, dict):
        return None

    # 1. Top-level exact match
    for f in capture_fields:
        if f in response_json and response_json[f] is not None:
            return str(response_json[f])

    # 2. Envelope patterns: data.id, result.id, resource.id
    for envelope_key in ("data", "result", "resource"):
        nested = response_json.get(envelope_key)
        if isinstance(nested, dict):
            for f in capture_fields:
                if f in nested and nested[f] is not None:
                    return str(nested[f])

    # 3. Any top-level key ending in 'id' or 'Id' as last resort
    for key, val in response_json.items():
        if (key.lower().endswith("id")) and val is not None and not isinstance(val, (dict, list)):
            return str(val)

    return None


def _display_expected_status(case: dict, actual_status: int, fallback: Any) -> Any:
    expected_list = case.get("expected_status", fallback)
    if isinstance(expected_list, list):
        if actual_status in expected_list:
            return actual_status
        return expected_list[0] if expected_list else actual_status
    return expected_list


def normalize_expected(expected: Any, actual_status: int) -> Any:
    if isinstance(expected, list):
        if actual_status in expected:
            return actual_status
        return expected[0] if expected else actual_status
    return expected


def _nonexistent_sentinel(param: str, merged_ids: dict) -> str:
    """Return a format-appropriate non-existent ID for RESOURCE_NOT_FOUND tests."""
    import re as _re
    _UUID_RE = _re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', _re.I)
    # If any existing stored ID looks like a UUID, use a UUID sentinel
    for val in merged_ids.values():
        if _UUID_RE.match(str(val)):
            return "00000000-0000-0000-0000-000000000000"
    if "uuid" in param.lower():
        return "00000000-0000-0000-0000-000000000000"
    return "999999999"


def resolve_path_params(path: str, case: dict, session, *, local_ids: dict | None = None) -> str:
    import re as _re

    mutation_type = str(case.get("mutation_type", "")).upper()

    # Merge ALL available ID sources into one lookup dict
    merged_ids: dict[str, str] = {}
    # 1. resource_context (from seeding phase)
    rc = getattr(session, "resource_context", {}) or {}
    for k, v in rc.items():
        if v not in (None, ""):
            merged_ids[k] = str(v)
    # 2. stored_ids (from auto-seed / previous sequences)
    si = getattr(session, "stored_ids", {}) or {}
    for k, v in si.items():
        if v not in (None, ""):
            merged_ids[k] = str(v)
    # 3. user_id under common key variants
    user_id = getattr(session, "user_id", None)
    if user_id:
        for key in ("user_id", "userId"):
            merged_ids.setdefault(key, str(user_id))
    # 4. Sequence-scoped local_ids (highest priority — overrides globals)
    if local_ids:
        for k, v in local_ids.items():
            if v not in (None, ""):
                merged_ids[k] = str(v)

    # Extract resource type from path for smart matching.
    # "/api/categories/{id}" → "category"
    path_segments = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
    resource_type = path_segments[-1].rstrip("s") if path_segments else ""

    def _lookup(param: str) -> str:
        if mutation_type == "RESOURCE_NOT_FOUND":
            return _nonexistent_sentinel(param, merged_ids)

        normalized = param.lower().strip()
        compact = normalized.replace("-", "_")
        parts = compact.split("_")
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:]) if len(parts) > 1 else compact

        # Priority 1: exact param name match
        for key in (param, normalized, compact, camel):
            if key in merged_ids:
                return merged_ids[key]

        # Priority 2: resource-type-aware lookup
        # If param is generic "id" and path is "/categories/{id}", try "category_id"
        if resource_type and normalized in {"id", "resource_id"}:
            for key in (f"{resource_type}_id", f"{resource_type}Id"):
                if key in merged_ids:
                    return merged_ids[key]

        # Priority 3: user_id for user-scoped paths
        if normalized in {"id", "user_id", "userid"} and user_id:
            return str(user_id)

        # No silent fallback — log error and use sentinel
        logger.warning(
            "[NegEngine] Could not resolve path param '{%s}' for %s %s — "
            "merged_ids=%s. Using sentinel value.",
            param, case.get("method", "?"), path, list(merged_ids.keys()),
        )
        return _nonexistent_sentinel(param, merged_ids)

    return _re.sub(r"\{([^}]+)\}", lambda m: _lookup(m.group(1)), path)


async def _load_spec(client: httpx.AsyncClient) -> dict[str, Any]:
    paths_to_try = [os.environ.get("NEGATIVE_TEST_SPEC_PATH"), "/openapi.json", "/docs/openapi.json", "/swagger.json"]
    paths_to_try = [p for p in paths_to_try if p]
    seen = set()
    for path in paths_to_try:
        if path in seen:
            continue
        seen.add(path)
        try:
            resp = await client.get(path, timeout=15.0)
            if resp.status_code == 200:
                spec = resp.json()
                if "paths" in spec:
                    logger.info(f"[NegEngine] Loaded spec from {path} — {len(spec['paths'])} paths")
                    return spec
        except Exception as exc:
            logger.debug(f"[NegEngine] Failed to load spec from {path}: {exc}")
            continue

    strict = os.environ.get("NEGATIVE_TEST_STRICT", "0").strip() == "1"
    msg = (
        f"[NegEngine] Could not load OpenAPI spec from any known path "
        f"(tried: {paths_to_try}). "
        f"Set NEGATIVE_TEST_SPEC_PATH to the correct URL path."
    )
    if strict:
        pytest.fail(msg)
    else:
        pytest.skip(msg)
    return {}


class TestContextWrapper:
    def __init__(self, session, case, spec_endpoints, spec: dict | None = None):
        self.session = session
        self.case = case
        self.spec_endpoints = spec_endpoints
        self.spec = spec  # Raw OpenAPI spec for deferred payload generation

    def _match_endpoint(self, method: str, path: str):
        """Find the spec endpoint matching method + path (supports parameterized paths)."""
        import re as _re
        case_path = path.split("?")[0].strip().rstrip("/")
        if not case_path.startswith("/"):
            case_path = "/" + case_path
        case_method = method.upper()

        for ep in self.spec_endpoints:
            if ep.method.upper() != case_method:
                continue
            ep_path = ep.path.strip().rstrip("/")
            if not ep_path.startswith("/"):
                ep_path = "/" + ep_path
            if ep_path == case_path:
                return ep
            pattern = _re.sub(r'\{[^}]+\}', '__PARAM__', ep_path)
            pattern = _re.escape(pattern)
            pattern = pattern.replace('__PARAM__', '[^/?]+')
            if _re.fullmatch(pattern, case_path):
                return ep
        return None

    def requires_auth(self) -> bool:
        ep = self._match_endpoint(
            self.case.get("method", ""),
            self.case.get("endpoint_path", ""),
        )
        if ep is not None:
            return ep.requires_auth
        # Fallback: assume auth required except for auth endpoints
        lower_path = self.case.get("endpoint_path", "").lower()
        if any(k in lower_path for k in ("auth", "login", "register", "signup")):
            return False
        return True

    def requires_auth_for(self, method: str, path: str) -> bool:
        """Check auth requirement for an arbitrary method+path (used by sequence steps)."""
        ep = self._match_endpoint(method, path)
        if ep is not None:
            return ep.requires_auth
        lower_path = path.lower()
        if any(k in lower_path for k in ("auth", "login", "register", "signup")):
            return False
        return True


async def _execute_single_case(case: dict, context: TestContextWrapper, client: httpx.AsyncClient) -> dict:
    headers = {}

    # Detect auth requirements from runtime spec, not generator hints.
    requires_auth = context.requires_auth()

    mutation_type = case.get("mutation_type")
    auth_type = str(case.get("auth_type") or "").strip().lower()
    is_auth_failure = mutation_type in [
        "AUTH_MISSING",
        "AUTH_INVALID"
    ] or auth_type in {"missing", "invalid", "expired"}
    token_injected = False

    # AUTH HANDLING — descriptive headers per auth_type
    if is_auth_failure:
        if auth_type == "invalid":
            headers = {"Authorization": TokenMutator.malformed()["Authorization"]}
        elif auth_type == "expired":
            headers = {"Authorization": TokenMutator.expired()["Authorization"]}
        elif auth_type == "missing":
            # Deliberately empty — no Authorization header sent.
            # We store a sentinel so the UI can display what happened.
            headers = {}
        else:
            headers = dict(case.get("custom_headers", {}))

    else:
        if requires_auth:
            headers.update(context.session.auth_headers)
            token_injected = True

    # HARD VALIDATION — abort if token should exist but doesn't
    if requires_auth and not is_auth_failure:
        if "Authorization" not in headers:
            logger.error(
                "[NegEngine] Token NOT injected for authenticated endpoint: %s %s — "
                "session.auth_headers=%s",
                case.get("method"), case.get("endpoint_path"),
                list(getattr(context.session, "auth_headers", {}).keys()),
            )
            return {
                "passed": False,
                "informational": False,
                "failure_reason": "INVALID_SETUP",
                "actual": 0,
                "expected": case.get("expected_status", []),
                "expected_raw": case.get("expected_status", []),
                "response_time_ms": 0,
                "request_headers": headers,
                "request_body": case.get("request_data"),
                "response_body": "",
                "requires_auth": requires_auth,
                "token_used": False,
                "user_id": getattr(context.session, "user_id", None),
                "note": f"Token not injected for {case.get('method')} {case.get('endpoint_path')}",
            }

    # Debug log for execution diagnostics
    logger.info(
        "[NegEngine] Execute | %s %s | requires_auth=%s | mutation=%s | has_token=%s | auth_type=%s",
        case.get("method"), case.get("endpoint_path"),
        requires_auth, case.get("mutation_type"),
        "Authorization" in headers, auth_type,
    )

    # ─────────────────────────────
    # Existing logic (unchanged)
    # ─────────────────────────────

    force_content_type = case.get("force_content_type")
    if force_content_type == "__OMIT__":
        headers.pop("Content-Type", None)
        headers.pop("content-type", None)
    elif force_content_type:
        headers["Content-Type"] = force_content_type

    req_data = case.get("request_data")

    if case.get("send_json_null"):
        content = b"null"  # Send actual JSON null literal
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
    elif isinstance(req_data, str):
        content = req_data.encode("utf-8")
    elif req_data is None:
        content = None
    else:
        content = json.dumps(req_data).encode("utf-8")
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"

    base_url = str(client.base_url).rstrip("/")
    resolved_path = resolve_path_params(case["endpoint_path"], case, context.session)
    url = base_url + resolved_path
    method = case.get("method", "GET")

    start = time.time()
    try:
        resp = await client.request(method, url, content=content, headers=headers, timeout=10.0)
        actual_status = resp.status_code
        response_body = resp.text
    except Exception as e:
        actual_status = 0
        response_body = str(e)

    elapsed_ms = int((time.time() - start) * 1000)

    mutation_type_str = case.get("mutation_type")

    try:
        mutation_type = (
            mutation_type_str
            if isinstance(mutation_type_str, MutationType)
            else MutationType[mutation_type_str]
        )
    except KeyError:
        mutation_type = None

    if not mutation_type:
        expected_display = normalize_expected(_display_expected_status(case, actual_status, []), actual_status)
        return {
            "passed": False,
            "informational": False,
            "failure_reason": "INVALID_SETUP",
            "actual": actual_status,
            "expected": expected_display,
            "expected_raw": [],
            "response_time_ms": elapsed_ms,
            "request_headers": headers,
            "request_body": req_data,
            "response_body": response_body,
            "requires_auth": requires_auth,
            "token_used": token_injected,
            "user_id": getattr(context.session, "user_id", None),
            "note": "Missing mutation_type"
        }

    # Use spec-derived expected_status from the test case (not hardcoded lookup)
    spec_expected = case.get("expected_status", [])
    if isinstance(spec_expected, int):
        spec_expected = [spec_expected]
    res = validate_response_from_spec(spec_expected, actual_status, mutation_type=mutation_type)
    expected_display = normalize_expected(_display_expected_status(case, actual_status, res.allowed_statuses), actual_status)

    # Build descriptive auth display for the UI
    auth_display = None
    if is_auth_failure:
        if auth_type == "missing":
            auth_display = "(deliberately omitted — testing missing auth)"
        elif auth_type == "invalid":
            auth_display = headers.get("Authorization", "(malformed token)")
        elif auth_type == "expired":
            auth_display = headers.get("Authorization", "(expired JWT)")

    return {
        "passed": res.passed,
        "informational": getattr(res, "informational", False),
        "failure_reason": res.failure_reason.value if res.failure_reason else None,
        "actual": actual_status,
        "expected": expected_display,
        "expected_raw": res.allowed_statuses,
        "response_time_ms": elapsed_ms,
        "request_headers": headers,
        "request_body": req_data,
        "response_body": response_body,
        "requires_auth": requires_auth,
        "token_used": token_injected,
        "user_id": getattr(context.session, "user_id", None),
        "auth_display": auth_display,
    }


async def _execute_sequence_case(case: dict, context: TestContextWrapper, client: httpx.AsyncClient) -> dict:
    steps_out = []
    failure_reason = None
    passed = True

    # ── Sequence-scoped ID storage — isolated from other sequences ────────
    local_ids: dict[str, str] = {}

    # Track created resources for compensating cleanup
    created_resources: list[dict] = []  # [{"url": ..., "headers": ...}]

    # Collect ALL path param tokens from ALL steps upfront
    import re as _re
    all_step_params: set[str] = set()
    for s in case.get("steps", []):
        tokens = _re.findall(r'\{([^}]+)\}', s.get("endpoint_path", ""))
        all_step_params.update(tokens)

    overall_actual = 0
    overall_expected = case.get("expected_status")

    # Track the fresh payload generated for this sequence.
    # First step with _body_schema regenerates; subsequent steps reuse it.
    # This is critical for duplicate-create: both POSTs must send identical data
    # that was freshly generated in THIS run, not frozen at generation time.
    sequence_fresh_payload: dict | list | None = None

    for step_idx, step in enumerate(case.get("steps", [])):
        step_endpoint = step["endpoint_path"]

        # ── Payload regeneration ──────────────────────────────────────────
        # Trigger: any step with _body_schema, not just capture_resource steps.
        # This ensures duplicate-create steps also get fresh payloads.
        req_data = step.get("request_data")
        if step.get("_body_schema"):
            if sequence_fresh_payload is None:
                # First step with a schema → regenerate with fresh unique values
                try:
                    from .payload_generator import generate_from_schema
                    fresh = generate_from_schema(step["_body_schema"], context.spec)
                    if fresh:
                        sequence_fresh_payload = fresh
                        req_data = fresh
                        logger.debug("[NegEngine] Regenerated fresh payload for step '%s'", step["name"])
                except Exception as regen_exc:
                    logger.debug("[NegEngine] Payload regeneration failed for step '%s': %s", step["name"], regen_exc)
            else:
                # Subsequent step with schema → reuse the same fresh payload.
                # For duplicate-create this ensures the 409 comes from THIS run's
                # duplicate, not debris from a previous run.
                req_data = sequence_fresh_payload
                logger.debug("[NegEngine] Reusing sequence payload for step '%s'", step["name"])

        # ── Path param resolution — local_ids first, then session globals ──
        # Build a step-level context so the resolver sees step.mutation_type
        # (if present) instead of the case-level "STATEFUL_SEQUENCE" label.
        step_context = {
            "mutation_type": step.get("mutation_type", case.get("mutation_type", "")),
            "method": step["method"],
            "endpoint_path": step_endpoint,
        }
        path = resolve_path_params(step_endpoint, step_context, context.session, local_ids=local_ids)
        if "{" in path:
            passed = False
            failure_reason = "INVALID_SETUP"
            steps_out.append({
                "step": step["name"],
                "passed": False,
                "actual": 0,
                "expected": step.get("expected_status"),
                "failure_reason": "INVALID_SETUP",
                "note": f"Unresolved path params in '{step_endpoint}' — local_ids: {local_ids}",
            })
            break

        # ── Auth injection — spec-driven, not generation-time flag ────────
        headers = {}
        step_requires_auth = context.requires_auth_for(step["method"], step_endpoint)
        if step_requires_auth and context.session.is_authenticated:
            headers.update(context.session.auth_headers)

        # ── Build request content ─────────────────────────────────────────
        content = None
        if step.get("send_json_null"):
            content = b"null"
            headers["Content-Type"] = "application/json"
        elif isinstance(req_data, str):
            content = req_data.encode("utf-8")
        elif req_data is None:
            content = None
        else:
            content = json.dumps(req_data).encode("utf-8")
            headers["Content-Type"] = "application/json"

        url = str(client.base_url).rstrip("/") + path
        try:
            resp = await client.request(step["method"], url, content=content, headers=headers, timeout=10.0)
            actual_status = resp.status_code
            response_body = resp.text
            response_json = {}
            if resp.text:
                try:
                    response_json = resp.json()
                except Exception:
                    response_json = {}
        except Exception as e:
            actual_status = 0
            response_body = str(e)
            response_json = {}

        # Track first meaningful status as overall
        if step_idx == 0:
            overall_actual = actual_status

        # ── Step validation — proper failure classification ────────────────
        exp = step.get("expected_status")
        if actual_status == 0:
            step_passed = False
            step_failure_reason = "INFRA_ERROR"
        elif actual_status >= 500:
            step_passed = False
            step_failure_reason = "SERVER_ERROR"
        elif isinstance(exp, list):
            step_passed = actual_status in exp
            if not step_passed:
                step_failure_reason = ("ACCEPTED_INVALID_INPUT"
                    if actual_status in (200, 201) and 200 not in exp and 201 not in exp
                    else "WRONG_REJECTION_CODE")
            else:
                step_failure_reason = None
        else:
            step_passed = actual_status == exp
            if not step_passed:
                step_failure_reason = ("ACCEPTED_INVALID_INPUT"
                    if actual_status in (200, 201) and exp not in (200, 201)
                    else "WRONG_REJECTION_CODE")
            else:
                step_failure_reason = None

        steps_out.append({
            "step": step["name"],
            "passed": step_passed,
            "actual": actual_status,
            "expected": normalize_expected(exp, actual_status),
            "expected_raw": exp,
            "failure_reason": step_failure_reason,
            "request_headers": headers,
            "request_body": req_data,
            "response_body": response_body,
        })

        # ── If step failed, abort — but still run cleanup ─────────────────
        if not step_passed:
            passed = False
            failure_reason = step_failure_reason
            overall_actual = actual_status
            overall_expected = normalize_expected(exp, actual_status)
            break

        # ── ID capture — store under ALL param names from ALL remaining steps
        if step.get("capture_resource"):
            capture_fields = step.get("capture_field", ["id", "_id", "uuid", "resourceId"])
            if isinstance(capture_fields, str):
                capture_fields = [capture_fields]

            stored_id = _extract_resource_id(response_json, capture_fields)

            if stored_id is None:
                passed = False
                failure_reason = "INVALID_SETUP"
                steps_out.append({
                    "step": step["name"] + " [ID_CAPTURE]",
                    "passed": False,
                    "actual": actual_status,
                    "expected": exp,
                    "failure_reason": "INVALID_SETUP",
                    "note": (
                        f"Step passed (status {actual_status}) but no ID found in response. "
                        f"Searched fields: {capture_fields}. "
                        f"Response body: {response_body[:200]}"
                    ),
                })
                break

            # Store under ALL path param tokens from ALL remaining steps
            for param_name in all_step_params:
                local_ids[param_name] = str(stored_id)
            # Also store type-specific keys for resource-type-aware resolution
            path_segments = [p for p in step_endpoint.strip("/").split("/") if p and not p.startswith("{")]
            if path_segments:
                rtype = path_segments[-1].rstrip("s")
                local_ids[f"{rtype}_id"] = str(stored_id)
                local_ids[f"{rtype}Id"] = str(stored_id)

            # Track for cleanup
            delete_url = url.rsplit("/", 1)[0] + "/" + str(stored_id) if "{" not in step_endpoint else None
            if delete_url is None:
                delete_url = str(client.base_url).rstrip("/") + step_endpoint.rstrip("/") + "/" + str(stored_id)
            created_resources.append({"url": delete_url, "headers": headers, "id": stored_id})

            logger.info(
                "[NegEngine] Sequence '%s' captured ID=%s — local_ids keys: %s",
                case.get("name", "?"), stored_id, list(local_ids.keys()),
            )

    # ── Compensating cleanup — DELETE created resources ────────────────────
    for res_info in reversed(created_resources):
        try:
            cleanup_headers = dict(res_info["headers"])
            await client.request("DELETE", res_info["url"], headers=cleanup_headers, timeout=5.0)
            logger.debug("[NegEngine] Cleanup: DELETE %s", res_info["url"])
        except Exception:
            pass  # Best-effort cleanup

    # ── Normalized result schema (matches single-case format) ─────────────
    # Find the last step's actual/expected for top-level reporting
    last_step = steps_out[-1] if steps_out else {}
    if overall_expected is None:
        overall_expected = last_step.get("expected")
    if overall_actual == 0 and last_step:
        overall_actual = last_step.get("actual", 0)

    return {
        "steps_out": steps_out,
        "passed": passed,
        "failure_reason": failure_reason,
        "actual": overall_actual,
        "expected": overall_expected,
        "expected_raw": case.get("expected_status", []),
        "sequence_type": case.get("sequence_type"),
        "informational": False,
        "user_id": getattr(context.session, "user_id", None),
        "requires_auth": case.get("requires_auth"),
        "token_used": context.session.is_authenticated,
        "response_time_ms": 0,
        "request_headers": last_step.get("request_headers", {}),
        "request_body": last_step.get("request_body"),
        "response_body": last_step.get("response_body", ""),
    }


async def _execute_rate_limit_case(
    case: dict,
    context: "TestContextWrapper",
    client: httpx.AsyncClient,
    *,
    acknowledge_burst_tests: bool = False,
    _outbound_counter: list | None = None,
) -> dict:
    """
    Execute a rate-limit burst test.

    Args:
        acknowledge_burst_tests: Must be True for burst tests to run.
                                 If False, the test is skipped with a clear reason.
        _outbound_counter:       Mutable list[int] — element [0] is incremented
                                 by the number of real HTTP requests made so callers
                                 can track total_outbound_requests for the run.
    """
    # ── Hard cap: clamp burst_count to settings.max_burst_count ──────────
    raw_burst = int(case.get("burst_count", 10))
    try:
        from src.config.settings import settings as _s
        max_burst = _s.max_burst_count
    except Exception:
        max_burst = 10
    burst_count = min(raw_burst, max_burst)

    # ── Acknowledgment gate ───────────────────────────────────────────────
    if not acknowledge_burst_tests:
        return {
            "skipped": True,
            "skip_reason": "burst_test_requires_acknowledgment",
            "passed": True,   # skipped ≠ failed
            "informational": True,
            "attempts": 0,
            "actual": None,
            "expected": None,
            "rate_limit_enforced": None,
            "response_time_ms": 0,
            "note": (
                f"Burst test skipped — requires acknowledge_burst_tests=true. "
                f"This test would fire {burst_count} rapid requests."
            ),
            "request_headers": {},
            "requires_auth": case.get("requires_auth"),
            "token_used": False,
            "user_id": None,
        }

    resolved_path = resolve_path_params(case["endpoint_path"], case, context.session)
    url = str(client.base_url).rstrip("/") + resolved_path
    method = case.get("method", "GET")
    requires_auth = context.requires_auth()

    headers = {"User-Agent": "Cognitest-Security-Scanner/2.0"}
    token_injected = False
    if requires_auth:
        headers.update(context.session.auth_headers)
        token_injected = True

    logger.debug(
        "[NegEngine] Rate Limit %s %s | burst=%d (cap=%d) | requires_auth=%s",
        method, case.get("endpoint_path"), burst_count, max_burst, requires_auth,
    )

    # ── Sequential semaphore: only ONE burst runs at a time across all
    # concurrent test cases so worst-case simultaneous load = max_burst_count.
    # The semaphore is shared via the context (set by the caller).
    burst_sem: asyncio.Semaphore = getattr(context, "_burst_semaphore", None) or asyncio.Semaphore(1)

    async def _make_req() -> int:
        try:
            resp = await client.request(method, url, headers=headers, timeout=5.0)
            return resp.status_code
        except Exception:
            return 0

    start = time.time()
    async with burst_sem:
        statuses = []
        for _ in range(burst_count):
            statuses.append(await _make_req())
    elapsed_ms = int((time.time() - start) * 1000)

    # Track outbound request count
    if _outbound_counter is not None:
        _outbound_counter[0] += burst_count

    got_429 = 429 in statuses
    non_zero = [s for s in statuses if s != 0]
    actual_status = 0
    if non_zero:
        counts = Counter(non_zero)
        actual_status = counts.most_common(1)[0][0]
    if got_429:
        actual_status = 429

    res = validate_response(MutationType.RATE_LIMIT_INFORMATIONAL, actual_status)
    expected_display = normalize_expected(_display_expected_status(case, actual_status, res.allowed_statuses), actual_status)

    return {
        "informational": getattr(res, "informational", False),
        "all_statuses": sorted(set(statuses)),
        "rate_limit_enforced": got_429,
        "attempts": burst_count,
        "burst_capped": burst_count < raw_burst,
        "passed": res.passed,
        "failure_reason": res.failure_reason.value if res.failure_reason else None,
        "actual": actual_status,
        "expected": expected_display,
        "expected_raw": res.allowed_statuses,
        "response_time_ms": elapsed_ms,
        "request_headers": headers,
        "requires_auth": requires_auth,
        "token_used": token_injected,
        "user_id": getattr(context.session, "user_id", None),
        "note": res.note,
    }


async def _auto_seed_resource_ids(
    session, endpoints: list, client: httpx.AsyncClient, spec: dict
) -> None:
    """
    Auto-create resources for path-param endpoints that have matching
    POST endpoints, so dynamic IDs are available for all test cases.

    Only runs once per session. Skips endpoints that already have IDs
    in stored_ids/resource_context. Uses spec security declarations
    (not keyword matching) to identify auth-only endpoints.
    """
    if getattr(session, "_auto_seeded", False):
        return
    session._auto_seeded = True

    if not session.is_authenticated:
        logger.info("[NegEngine] Skipping auto-seed — not authenticated")
        return

    from .payload_generator import generate_valid_payload

    # Build set of paths that are purely auth endpoints (from the spec)
    _auth_tag_keywords = {"auth", "authentication", "authorization"}
    auth_paths: set[str] = set()
    for path, path_item in (spec.get("paths") or {}).items():
        for method_key, operation in path_item.items():
            if method_key in ("parameters", "summary", "description"):
                continue
            tags = [t.lower() for t in (operation.get("tags") or [])]
            if any(k in t for t in tags for k in _auth_tag_keywords):
                auth_paths.add(path)
                break

    # Find all path-param bases that need real IDs
    needs_id: dict[str, list[str]] = {}  # base_path -> [param_names]
    for ep in endpoints:
        if not ep.path_params:
            continue
        if ep.method in ("GET", "DELETE", "PUT", "PATCH"):
            base = ep.path.split("{")[0].rstrip("/")
            # Skip auth endpoints using spec tags (not keyword matching)
            if ep.path in auth_paths:
                continue
            if base not in needs_id:
                needs_id[base] = []
            needs_id[base].extend(ep.path_params)

    if not needs_id:
        return

    logger.info("[NegEngine] Auto-seeding IDs for %d path-param bases: %s",
                len(needs_id), list(needs_id.keys()))

    # Merge existing IDs from both stored_ids and resource_context
    existing_ids = {}
    existing_ids.update(getattr(session, "resource_context", {}) or {})
    existing_ids.update(getattr(session, "stored_ids", {}) or {})

    headers = {**session.auth_headers, "Content-Type": "application/json"}

    for base, param_names in needs_id.items():
        # Check if we already have IDs for these params (in either dict)
        all_resolved = all(p in existing_ids for p in param_names)
        if all_resolved:
            continue

        # Find matching POST endpoint (the "create" endpoint)
        post_ep = None
        for ep in endpoints:
            if ep.method != "POST":
                continue
            ep_clean = ep.path.rstrip("/")
            if ep_clean == base or ep_clean == base + "/":
                post_ep = ep
                break

        if not post_ep or not post_ep.body_schema:
            continue

        payload = generate_valid_payload(post_ep, spec=spec)
        if not payload:
            continue

        try:
            resp = await client.request(
                "POST",
                str(client.base_url).rstrip("/") + post_ep.path,
                content=json.dumps(payload).encode(),
                headers=headers,
                timeout=10.0,
            )
            if resp.status_code not in (200, 201):
                logger.debug("[NegEngine] Auto-seed POST %s → %d (skipped)",
                             post_ep.path, resp.status_code)
                continue

            try:
                data = resp.json()
            except Exception:
                continue

            rid = _extract_resource_id(
                data, ["id", "_id", "uuid", "resourceId"]
            )
            if not rid:
                continue

            # Store under EVERY param name that depends on this base
            unique_params = list(set(param_names))
            for param in unique_params:
                session.stored_ids[param] = rid
            # Also store type-specific keys (from path segment)
            path_segments = [p for p in base.strip("/").split("/") if p]
            if path_segments:
                rtype = path_segments[-1].rstrip("s")
                session.stored_ids[f"{rtype}_id"] = rid
                session.stored_ids[f"{rtype}Id"] = rid
            # NOTE: Intentionally NOT storing under generic "resource_id"
            # to prevent cross-resource collision

            logger.info(
                "[NegEngine] Auto-seeded %s → id=%s (params: %s)",
                post_ep.path, rid, unique_params,
            )
        except Exception as exc:
            logger.debug("[NegEngine] Auto-seed failed for %s: %s", base, exc)


@pytest.mark.asyncio
async def test_negative_suite(auth_session, negative_test_client):
    spec = await _load_spec(negative_test_client)
    endpoints = extract_endpoints(spec)

    # Bridge stored_ids from seed phase so path-param resolution works
    if not hasattr(auth_session, "stored_ids"):
        auth_session.stored_ids = {}
    # Merge any resource_context IDs that were seeded during setup
    if hasattr(auth_session, "resource_context") and auth_session.resource_context:
        auth_session.stored_ids.update(auth_session.resource_context)
        logger.info(
            "[NegEngine] Bridged %d resource IDs into stored_ids: %s",
            len(auth_session.resource_context),
            list(auth_session.resource_context.keys()),
        )

    # Auto-seed resource IDs for path-param endpoints that are missing IDs
    await _auto_seed_resource_ids(auth_session, endpoints, negative_test_client, spec)

    logger.info(
        "[NegEngine] stored_ids before execution: %s",
        list((auth_session.stored_ids or {}).keys()),
    )
    
    cases = []
    
    for _, module_name, _ in pkgutil.iter_modules(neg_pkg.__path__):
        mod = importlib.import_module(f"src.modules.generator.engines.negative.{module_name}")
        for attr_name in dir(mod):
            if attr_name.startswith("generate_") and callable(getattr(mod, attr_name)):
                func = getattr(mod, attr_name)
                try:
                    sig = inspect.signature(func)
                    kwargs = {}
                    if "endpoints" in sig.parameters: kwargs["endpoints"] = endpoints
                    if "spec" in sig.parameters: kwargs["spec"] = spec
                    
                    # Note: Functions like generate_invalid_method_tests have sig (spec, endpoints)
                    # as positional params — Python correctly binds them when called via kwargs.
                    if "endpoints" in sig.parameters and "endpoint" not in sig.parameters:
                        res = func(**kwargs)
                        if isinstance(res, list): cases.extend(res)
                    elif "endpoint" in sig.parameters:
                        for ep in endpoints:
                            kw = dict(kwargs)
                            kw["endpoint"] = ep
                            if "all_endpoints" in sig.parameters: kw["all_endpoints"] = endpoints
                            res = func(**kw)
                            if isinstance(res, list): cases.extend(res)
                except Exception as e:
                    logger.warning(f"[NegEngine] Generator '{attr_name}' in '{module_name}' failed and produced no cases",exc_info=True,)


    results = []
    client = negative_test_client
    
    for case in cases:
        ctx = TestContextWrapper(auth_session, case, endpoints, spec=spec)
        if case.get("type") == "SEQUENCE":
            res = await _execute_sequence_case(case, ctx, client)
        elif case.get("sub_category") == "RATE_LIMIT":
            res = await _execute_rate_limit_case(case, ctx, client)
        else:
            res = await _execute_single_case(case, ctx, client)
            
        res["case"] = case
        results.append(res)
        
    failures = [r for r in results if not r.get("passed") and not r.get("informational")]
    
    if failures:
        import sys
        lines = ["\n=== NEGATIVE TEST FAILURES ==="]
        for f in failures:
            c = f["case"]
            actual = f.get("actual", 0)
            expected = normalize_expected(f.get("expected"), actual)
            # For sequences, show the failing step detail
            step_detail = ""
            if f.get("steps_out"):
                failed_steps = [s for s in f["steps_out"] if not s.get("passed")]
                if failed_steps:
                    fs = failed_steps[0]
                    step_detail = f"\n       Step: {fs.get('step')} (got {fs.get('actual')}, expected {fs.get('expected')})"
            lines.append(
                f"  FAIL [{c.get('sub_category', '?')}] {c.get('name')}\n"
                f"       Expected: {expected}  Got: {actual}\n"
                f"       Reason: {f.get('failure_reason')}  Note: {f.get('note', '')}"
                f"{step_detail}\n"
                f"       Endpoint: {c.get('method')} {c.get('endpoint_path')}"
            )
        summary = "\n".join(lines)
        sys.stderr.write(summary + "\n")
        assert len(failures) == 0, f"{len(failures)} negative test failures:\n{summary}"
