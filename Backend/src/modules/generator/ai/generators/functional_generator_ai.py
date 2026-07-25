"""
AI-powered functional test generator — spec-driven, one-endpoint-per-call parallelism.

Design:
- Each endpoint gets its OWN AI call (1 endpoint per chunk).
- All calls fire in parallel via asyncio.gather().
- ai_client._lock serializes actual HTTP calls, preventing 429s.
- MAX_OUTPUT_TOKENS = 8000 → enough for 20-30 rich test cases per endpoint.
- Auth endpoints (detected from spec schema, not keywords) always sorted first.
- Results merged and ordered by dependency orchestrator.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Any

from src.modules.generator.ai.client import ai_client
from src.modules.generator.ai.prompts.functional import (
    FUNCTIONAL_SYSTEM,
    build_functional_chunk_prompt,
)
from src.modules.generator.ai.utils import prune_schema_for_ai

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────────────
MAX_OUTPUT_TOKENS = 4000   # Claude max allowed before TPM errors
MAX_RETRIES       = 3

# Admin route patterns
_ADMIN_PATTERNS = ("/admin", "/management", "/superuser", "/backoffice", "/system/")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_admin_route(path: str) -> bool:
    pl = path.lower()
    return any(p in pl for p in _ADMIN_PATTERNS)


def _is_auth_endpoint(ep) -> bool:
    """
    Detect auth endpoints (signup/login/token) from spec schema — NOT path keywords.

    Signals:
      1. Body schema has a password/passwd/pin/secret field  → signup or login
      2. Response schema has a token/access_token/jwt field  → login/token endpoint
      3. POST with no auth required + identity field (email/username) → public auth endpoint
    """
    if ep.method != "POST":
        return False

    body_props: dict = {}
    if ep.body_schema and isinstance(ep.body_schema, dict):
        body_props = ep.body_schema.get("properties", {}) or {}

    response_props: dict = {}
    if ep.response_schema and isinstance(ep.response_schema, dict):
        response_props = ep.response_schema.get("properties", {}) or {}
        if "data" in response_props and isinstance(response_props["data"], dict):
            nested = response_props["data"].get("properties", {})
            if nested:
                response_props = {**response_props, **nested}

    body_keys = {k.lower() for k in body_props}
    resp_keys  = {k.lower() for k in response_props}

    _password_fields = {"password", "passwd", "passphrase", "pass", "secret", "pin"}
    _token_fields    = {"token", "access_token", "accesstoken", "refresh_token",
                        "refreshtoken", "id_token", "jwt", "auth_token", "bearer"}
    _identity_fields = {"email", "username", "user_name", "phone", "mobile",
                        "userid", "user_id", "login", "account"}

    if bool(body_keys & _password_fields):
        return True
    if bool(resp_keys & _token_fields):
        return True
    if bool(body_keys & _identity_fields) and not ep.requires_auth:
        return True

    return False


def _extract_admin_credentials(admin_config: dict | None) -> tuple[str, str] | None:
    if not admin_config:
        return None
    email    = admin_config.get("email")    or admin_config.get("admin_email")    or ""
    password = admin_config.get("password") or admin_config.get("admin_password") or ""
    return (email, password) if (email and password) else None


def _extract_schema_fields(schema: dict | None) -> dict:
    """
    Pre-parse a body/response schema into explicit field metadata.
    This gives the AI unambiguous field names, types, and required status
    so it cannot hallucinate field names.

    Returns a dict with:
      required_fields: list of required field names
      optional_fields: list of optional field names
      field_details:   {field_name: {type, format, enum, minLength, maxLength, min, max}}
    """
    if not schema or not isinstance(schema, dict):
        return {}

    properties: dict = schema.get("properties", {}) or {}
    required_list: list = schema.get("required", []) or []

    # Handle allOf/anyOf by merging properties
    for combiner in ("allOf", "anyOf", "oneOf"):
        for sub in schema.get(combiner, []) or []:
            if isinstance(sub, dict):
                sub_props = sub.get("properties", {})
                if sub_props:
                    properties.update(sub_props)
                sub_req = sub.get("required", [])
                if sub_req:
                    required_list.extend(sub_req)

    if not properties:
        return {}

    required_set = set(required_list)
    required_fields = []
    optional_fields = []
    field_details: dict[str, dict] = {}

    for field_name, field_schema in properties.items():
        if not isinstance(field_schema, dict):
            field_schema = {}
        details: dict[str, Any] = {}
        if field_schema.get("type"):
            details["type"] = field_schema["type"]
        if field_schema.get("format"):
            details["format"] = field_schema["format"]
        if field_schema.get("enum"):
            details["enum"] = field_schema["enum"]
        if field_schema.get("minLength") is not None:
            details["minLength"] = field_schema["minLength"]
        if field_schema.get("maxLength") is not None:
            details["maxLength"] = field_schema["maxLength"]
        if field_schema.get("minimum") is not None:
            details["min"] = field_schema["minimum"]
        if field_schema.get("maximum") is not None:
            details["max"] = field_schema["maximum"]
        if field_schema.get("pattern"):
            details["pattern"] = field_schema["pattern"]
        if field_schema.get("description"):
            details["description"] = field_schema["description"]
        if field_schema.get("example") is not None:
            details["example"] = field_schema["example"]

        field_details[field_name] = details
        if field_name in required_set:
            required_fields.append(field_name)
        else:
            optional_fields.append(field_name)

    return {
        "required_fields": required_fields,
        "optional_fields": optional_fields,
        "field_details":   field_details,
    }


def _endpoint_to_dict(ep, *, admin_creds: tuple | None = None) -> dict:
    """
    Serialize one endpoint into a rich dict for the AI prompt.
    Pre-parses body_schema into explicit field lists so AI cannot
    hallucinate field names.
    """
    body_fields   = _extract_schema_fields(ep.body_schema)
    response_info = _extract_schema_fields(ep.response_schema)

    d: dict[str, Any] = {
        "path":          ep.path,
        "method":        ep.method,
        "requires_auth": ep.requires_auth,
        "path_params":   ep.path_params,
        "query_params":  ep.query_params,
        "status_codes":  ep.status_codes,
    }

    # Explicit field breakdown — AI MUST use these exact names in request_body
    if body_fields:
        d["request_body_fields"] = body_fields   # required_fields, optional_fields, field_details
    else:
        d["request_body_fields"] = {"note": "No request body for this endpoint"}

    # Response field summary for assertion writing
    if response_info:
        d["response_fields"] = {
            "fields": list(response_info.get("field_details", {}).keys())
        }

    if ep.path_params:
        d["path_param_names"] = ep.path_params  # e.g. ["id", "userId"]

    if _is_admin_route(ep.path):
        d["admin_note"] = (
            f"Admin route — use credentials: {admin_creds[0]}"
            if admin_creds else "Admin route — credentials required"
        )
    return d


def _sort_endpoints_for_generation(endpoints: list) -> list:
    """
    Sort endpoints so auth endpoints come first in the generation order.
    Within non-auth, sort by method priority: POST → GET → PUT/PATCH → DELETE.
    This affects the parallel dispatch order only (all still run in parallel).
    """
    method_order = {"POST": 0, "GET": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

    def _key(ep):
        is_auth  = _is_auth_endpoint(ep)
        is_admin = _is_admin_route(ep.path)
        return (
            0 if is_auth else (2 if is_admin else 1),   # auth first, admin last
            method_order.get(ep.method.upper(), 5),
            ep.path,
        )

    return sorted(endpoints, key=_key)


def _coerce_to_list(data: Any) -> list[dict]:
    """Coerce AI response data to a list of test dicts."""
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict):
        if "raw_text" in data:
            logger.warning("[AI][Functional] Raw-text response — JSON parse failed upstream")
            return []
        for key in ("tests", "generated_tests", "cases", "test_cases", "results", "items"):
            if key in data and isinstance(data[key], list):
                return [t for t in data[key] if isinstance(t, dict)]
        if "name" in data or "endpoint_path" in data or "method" in data:
            return [data]
    return []


# ── Per-endpoint AI call ─────────────────────────────────────────────────────

async def _process_single_endpoint(
    ep_idx: int,
    total: int,
    ep,
    admin_creds: tuple | None,
    all_endpoints_context: str,
) -> tuple[list[dict], int, int]:
    """
    Call the AI once for a single endpoint.
    Returns all generated test cases for that endpoint.

    Passing `all_endpoints_context` lets the AI understand dependency chains
    (e.g. which endpoints provide tokens or IDs) even within a single-endpoint call.
    """
    ep_label = f"[{ep_idx+1}/{total}] {ep.method} {ep.path}"

    # Build the endpoint dict (full schema detail)
    ep_dict = _endpoint_to_dict(ep, admin_creds=admin_creds)
    endpoint_json = json.dumps(ep_dict, separators=(",", ":"), default=str)

    # Admin hint
    admin_hint = ""
    if admin_creds and _is_admin_route(ep.path):
        admin_hint = f"Admin credentials available — email: {admin_creds[0]}"

    # We pass ALL endpoint paths as context so AI can write correct depends_on
    system_blocks, prompt_blocks = build_functional_chunk_prompt(
        endpoints_json=endpoint_json,
        admin_hint=admin_hint,
        all_endpoints_context=all_endpoints_context,
    )

    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                # If it's a rate limit error, wait much longer to let the rolling minute clear
                if getattr(ep, "_last_error_was_429", False):
                    backoff = 35.0
                    logger.info("[AI][Functional] %s rate limit retry %d/%d — waiting %.1fs for token bucket to replenish",
                                ep_label, attempt + 1, MAX_RETRIES, backoff)
                else:
                    backoff = 2.0 ** attempt
                    logger.info("[AI][Functional] %s retry %d/%d — waiting %.1fs",
                                ep_label, attempt + 1, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)

            ep._last_error_was_429 = False
            logger.info("[AI][Functional] %s — calling AI (attempt %d/%d)",
                        ep_label, attempt + 1, MAX_RETRIES)

            result = await ai_client.generate_json(
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
                tenant_id=getattr(ep, "_tenant_id", ""),
            )

            usage   = result.get("usage") or {}
            in_tok  = usage.get("input_tokens",  0) if isinstance(usage, dict) else 0
            out_tok = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0
            logger.info("[AI][Functional] %s → tokens in=%d out=%d", ep_label, in_tok, out_tok)

            tests = _coerce_to_list(result.get("data"))

            if not tests:
                logger.warning("[AI][Functional] %s — AI returned 0 tests", ep_label)
                return [], in_tok, out_tok

            # Normalize and annotate
            normalized: list[dict] = []
            for t in tests:
                t.setdefault("id", str(uuid.uuid4()))
                t.setdefault("test_type", "Functional")
                t.setdefault("expected_status", 200)
                t.setdefault("requires_auth", ep.requires_auth)
                t.setdefault("depends_on", [])
                t["generation_source"] = "AI"

                # Normalize: ensure endpoint_path is set
                if not t.get("endpoint_path"):
                    t["endpoint_path"] = t.pop("path", ep.path)

                # Only force-correct completely missing path; if AI returned a *different*
                # path (e.g. a depends_on setup test for login while processing signup),
                # keep it so the test is filed under the correct endpoint.
                # This preserves signup tests that reference /login as a prerequisite.
                if not t.get("endpoint_path"):
                    t["endpoint_path"] = ep.path

                # Force correct method
                if t.get("method", "").upper() != ep.method.upper():
                    t["method"] = ep.method.upper()

                # Admin annotation
                if _is_admin_route(ep.path):
                    t["requires_admin_credentials"] = True
                    if admin_creds:
                        t.setdefault("_admin_email",    admin_creds[0])
                        t.setdefault("_admin_password", admin_creds[1])
                    else:
                        t.setdefault("requires_manual_credentials", True)

                normalized.append(t)

            logger.info("[AI][Functional] %s — %d tests generated", ep_label, len(normalized))
            return normalized, in_tok, out_tok

        except RuntimeError as exc:
            err_str = str(exc).lower()
            if "rate_limit_error" in err_str or "429" in err_str:
                ep._last_error_was_429 = True
                
            logger.warning("[AI][Functional] %s attempt %d/%d — API error: %s",
                           ep_label, attempt + 1, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES - 1:
                logger.error("[AI][Functional] %s — all retries exhausted", ep_label)

        except (ConnectionError, TimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("[AI][Functional] %s attempt %d/%d — network error: %s",
                           ep_label, attempt + 1, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES - 1:
                logger.error("[AI][Functional] %s — all retries exhausted", ep_label)

        except (ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
            logger.error("[AI][Functional] Internal error for %s: %s — not retrying", ep_label, exc)
            break

        except Exception as exc:
            logger.exception("[AI][Functional] Unexpected error for %s: %s", ep_label, exc)
            break

    return [], 0, 0


# ── Public API ───────────────────────────────────────────────────────────────

async def generate_functional_tests_enhanced(
    spec: dict[str, Any],
    endpoints: list | None = None,
    admin_config: dict | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], int, list[dict]]:
    """
    Generate functional test cases directly from OpenAPI spec — one AI request per endpoint.
    Supports Anthropic Batch API execution for high throughput and cost savings.
    """
    if not ai_client.is_available:
        logger.info("[AI][Functional] AI not available — returning empty list")
        return [], 0, []

    if endpoints is None:
        from src.modules.generator.spec_parser import extract_endpoints
        endpoints = extract_endpoints(spec)

    if not endpoints:
        logger.warning("[AI][Functional] No endpoints provided")
        return [], 0, []

    admin_creds = _extract_admin_credentials(admin_config)
    if admin_creds:
        logger.info("[AI][Functional] Admin credentials provided")
    else:
        logger.info("[AI][Functional] No admin credentials")

    sorted_eps = _sort_endpoints_for_generation(endpoints)

    # Stamp tenant_id on each endpoint so the per-call budget check can use it
    for ep in sorted_eps:
        ep._tenant_id = tenant_id

    all_endpoints_context = json.dumps(
        [{"path": ep.path, "method": ep.method, "requires_auth": ep.requires_auth}
         for ep in sorted_eps],
        separators=(",", ":"),
    )

    logger.info("[AI][Functional] Dispatching %d endpoint calls (use_batch=%s)", len(sorted_eps), use_batch)

    all_tests: list[dict] = []
    token_batches: list[dict] = []

    if use_batch and len(sorted_eps) > 0:
        batch_requests = []
        for idx, ep in enumerate(sorted_eps):
            ep_dict = _endpoint_to_dict(ep, admin_creds=admin_creds)
            endpoint_json = json.dumps(ep_dict, separators=(",", ":"), default=str)
            admin_hint = ""
            if admin_creds and _is_admin_route(ep.path):
                admin_hint = f"Admin credentials available — email: {admin_creds[0]}"
            system_blocks, prompt_blocks = build_functional_chunk_prompt(
                endpoints_json=endpoint_json,
                admin_hint=admin_hint,
                all_endpoints_context=all_endpoints_context,
            )
            req = ai_client.prepare_batch_request(
                custom_id=f"func-{idx}",
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )
            batch_requests.append(req)

        results_by_id, _ = await ai_client.execute_batch_with_retry(
            batch_requests, on_status_update=on_status_update
        )

        for idx, ep in enumerate(sorted_eps):
            res = results_by_id.get(f"func-{idx}", {})
            tests = _coerce_to_list(res.get("data"))
            usage = res.get("usage", {})
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)

            normalized: list[dict] = []
            for t in tests:
                t.setdefault("id", str(uuid.uuid4()))
                t.setdefault("test_type", "Functional")
                t.setdefault("expected_status", 200)
                t.setdefault("requires_auth", ep.requires_auth)
                t.setdefault("depends_on", [])
                t["generation_source"] = "AI"

                if not t.get("endpoint_path"):
                    t["endpoint_path"] = t.pop("path", ep.path)
                if not t.get("endpoint_path"):
                    t["endpoint_path"] = ep.path
                if t.get("method", "").upper() != ep.method.upper():
                    t["method"] = ep.method.upper()

                if _is_admin_route(ep.path):
                    t["requires_admin_credentials"] = True
                    if admin_creds:
                        t.setdefault("_admin_email",    admin_creds[0])
                        t.setdefault("_admin_password", admin_creds[1])
                    else:
                        t.setdefault("requires_manual_credentials", True)

                normalized.append(t)

            all_tests.extend(normalized)
            token_batches.append({
                "cases": normalized,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
            })

        total_tokens = sum(b["input_tokens"] + b["output_tokens"] for b in token_batches)
        logger.info("[AI][Functional] Batch Complete — %d total tests from %d endpoints", len(all_tests), len(sorted_eps))
        return all_tests, total_tokens, token_batches

    semaphore = asyncio.Semaphore(2)

    async def _sem_process(idx, ep):
        async with semaphore:
            return await _process_single_endpoint(
                ep_idx=idx,
                total=len(sorted_eps),
                ep=ep,
                admin_creds=admin_creds,
                all_endpoints_context=all_endpoints_context,
            )

    tasks = [_sem_process(idx, ep) for idx, ep in enumerate(sorted_eps)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for ep_result in results:
        if isinstance(ep_result, tuple) and len(ep_result) == 3:
            cases, in_tok, out_tok = ep_result
            all_tests.extend(cases)
            token_batches.append({
                "cases":         cases,
                "input_tokens":  in_tok,
                "output_tokens": out_tok,
            })
        elif isinstance(ep_result, list):
            # Safety fallback — old callers returning bare list
            all_tests.extend(ep_result)

    total_tokens = sum(b["input_tokens"] + b["output_tokens"] for b in token_batches)
    logger.info("[AI][Functional] Complete — %d total tests from %d endpoint calls, %d tokens",
                len(all_tests), len(sorted_eps), total_tokens)
    return all_tests, total_tokens, token_batches


# ── Backward-compat alias ─────────────────────────────────────────────────────
async def enhance_functional_tests_ai(
    endpoints_json: str,
    category_data: list,
    admin_config: dict | None = None,
) -> tuple[list[dict], int]:
    """Deprecated shim — kept for backward compatibility only."""
    logger.warning("[AI][Functional] enhance_functional_tests_ai() is deprecated")
    return [], 0
