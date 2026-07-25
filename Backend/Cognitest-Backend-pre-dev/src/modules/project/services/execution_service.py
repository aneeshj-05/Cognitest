"""
Execution Service — delegating to respective engine services while maintaining local logic for Security, Contract, and Negative suites.
"""
import logging
import re
import json
import asyncio
import uuid
import time
try:
    import httpx
except ImportError:
    # Minimal stub for static analysis / fallback
    class _DummyResponse:
        def __init__(self, *args, **kwargs):
            self.status_code = 0
            self.text = ''
            self.headers = {}
            self.content = b''
        async def json(self):
            return {}
    class AsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def request(self, *args, **kwargs):
            return _DummyResponse()
        async def get(self, *args, **kwargs):
            return _DummyResponse()
        async def post(self, *args, **kwargs):
            return _DummyResponse()
    httpx = type('httpx', (), {'AsyncClient': AsyncClient, 'TimeoutException': Exception, 'ConnectError': Exception})
import random
import string
try:
    from pydantic import BaseModel
except ImportError:
    BaseModel = object
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict
from fastapi import APIRouter, Request, HTTPException, Response

from src.utils.redact import redact_request_data

from src.config import prisma
from prisma import Json as PrismaJson
from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
from src.modules.generator.engines.functional.variable_resolver import resolve_placeholders
from src.modules.generator.engines.negative.core import TokenMutator
from src.modules.generator.engines.negative.stateful_execution import (
    _auth_session_setup as _neg_auth_session_setup,
    _stateful_setup,
    _auth_session_cleanup,
)
from src.services.prisma_compat import create_testrun_compat
from ..utils import substitute_path_params
from ..state import _run_results_store, _results_store
from src.modules.generator.engines.contract.contract_executor import execute_contract_test_cases

# Import functional execution logic
from src.modules.generator.engines.functional.services.functional_execution_service import (
    stream_run_suite as functional_stream_run_suite
)

# Import fuzz execution logic
from src.modules.generator.engines.fuzz.services.fuzz_execution_service import (
    stream_security_suite as fuzz_stream_security_suite
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Disconnect / cancellation helpers
# ---------------------------------------------------------------------------

async def _is_disconnected(request) -> bool:
    """Safely check client disconnect — returns False if request is None."""
    if request is None:
        return False
    try:
        return await request.is_disconnected()
    except Exception:
        return False


async def _mark_run_status(run_id: str, status: str, results: list) -> None:
    """Persist final TestRun status to DB. Status must be COMPLETED/FAILED/CANCELLED."""
    if run_id == "stub-run":
        return
    try:
        passed = sum(1 for r in results if r.get("passed"))
        await prisma.testrun.update(
            where={"id": run_id},
            data={
                "status":       status,
                "totalTests":   len(results),
                "passed":       passed,
                "failed":       len(results) - passed,
                "completedAt":  datetime.now(timezone.utc),
            },
        )
    except Exception as e:
        logger.error("Failed to update TestRun %s to %s: %s", run_id, status, e)

# OWASP category display labels
_CATEGORY_LABEL = {
    "API1:2023": "API1:2023  Broken Object Level Authorization",
    "API2:2023": "API2:2023  Broken Authentication",
    "API3:2023": "API3:2023  Broken Object Property Level Authorization",
    "API4:2023": "API4:2023  Unrestricted Resource Consumption",
    "API5:2023": "API5:2023  Broken Function Level Authorization",
    "API6:2023": "API6:2023  Sensitive Business Flows",
    "API7:2023": "API7:2023  Server Side Request Forgery",
    "API8:2023": "API8:2023  Security Misconfiguration",
    "API9:2023": "API9:2023  Improper Inventory Management",
    "API10:2023": "API10:2023  Unsafe Consumption of APIs",
    "Injection": "4.1  Injection",
    "Auth": "4.2  Authentication",
    "BOLA": "4.3  BOLA / IDOR",
    "Exposure": "4.4  Excessive Data Exposure",
    "RateLimit": "4.5  Rate Limiting",
    "VerbTamper": "4.6  Verb Tampering",
    "TLS": "4.7  TLS / SSL",
    "Misconfiguration": "4.8  Misconfiguration",
    "WrongRole": "Privilege Escalation",
    "FunctionAuth": "API5 Function-Level AuthZ",
}

def _substitute_path_params(path_template: str, path_params: dict[str, Any] | None, fallback_id: str | None = None) -> str:
    rendered = (path_template or "/")
    for k, v in (path_params or {}).items():
        rendered = rendered.replace("{" + str(k) + "}", str(v))

    if fallback_id:
        rendered = rendered.replace("{id}", fallback_id).replace("{userId}", fallback_id).replace("{user_id}", fallback_id)

    # Final safety: resolve any remaining {param} tokens with a plausible
    # fallback ID so the request reaches the handler instead of 404-ing.
    if "{" in rendered:
        rendered = rendered.replace("{", "").replace("}", "")

    return rendered


def _rehydrate_security_meta(case: dict) -> dict:
    assertions = case.get("assertions") or []
    if isinstance(assertions, list):
        for a in assertions:
            if isinstance(a, str) and a.startswith("__security_meta__="):
                try:
                    meta = json.loads(a.split("=", 1)[1])
                    case.update(meta)
                except Exception:
                    pass
                break
    return case

def _evaluate_pass_fail(expected: Any, actual: int, case: dict, body: str | None = None, headers: dict | None = None) -> bool:
    if isinstance(expected, list):
        return actual in expected
    if actual == expected:
        return True
    test_name = case.get("name", "").lower()
    owasp = case.get("owasp_category", "")
    if owasp in ("API1:2023", "BOLA") or "bola" in test_name:
        return actual in (403, 404)
    if owasp in ("API5:2023", "WrongRole") or "privilege" in test_name:
        return actual in (403, 401)
    if owasp in ("API3:2023", "API7:2023", "API10:2023", "Injection") or any(k in test_name for k in ("injection", "xss", "sql", "command", "ssrf", "mass assignment")):
        return actual in (400, 401, 403, 404, 409, 415, 422)
    if owasp == "API2:2023":
        return actual in (401, 403)
    if owasp == "API4:2023":
        return actual in (200, 202, 400, 409, 422, 429)
    if owasp == "API6:2023":
        return actual in (200, 201, 202, 400, 401, 403, 409, 422, 429)
    if owasp in ("API9:2023", "VerbTamper"):
        return actual in (404, 405, 410)
    if owasp == "TLS" and expected == 301:
        return actual in (200, 301, 302, 404)
    if owasp in ("API8:2023", "Misconfiguration") and expected == 200:
        return actual in (200, 404)
    return False

def _normalize_token(token: str | None) -> str | None:
    if not token: return None
    t = str(token).strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t or None

def _remove_header_case_insensitive(headers: dict[str, Any], name: str) -> None:
    for k in list(headers.keys()):
        if str(k).lower() == name.lower():
            headers.pop(k, None)

def _auth_header_present(headers: dict[str, Any]) -> bool:
    return any(str(k).lower() == "authorization" for k in headers.keys())

def _mask_auth_header(headers: dict[str, Any]) -> dict[str, Any]:
    # Do NOT mask — show the real token and user_id in payload cards 
    # to ensure payload transparency during negative/security testing.
    return dict(headers or {})

def _resolve_auth_type(case: dict[str, Any]) -> str:
    raw = str(case.get("auth_type") or "").strip().lower()
    if raw and raw != "none": return raw
    
    meta = case.get("metadata") or {}
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            meta = {}
    if isinstance(meta, dict):
        raw = str(meta.get("auth_type") or "").strip().lower()
        if raw and raw != "none": return raw

    kind = case.get("kind")
    if kind == "negative_auth_missing": return "missing"
    if kind == "negative_auth_invalid": return "invalid"
    if kind == "negative_auth_expired": return "expired"
    return "normal"

async def _run_one(
    client: httpx.AsyncClient, 
    case: dict, 
    base_url: str, 
    extra_headers: dict | None = None,
    execution_context: dict | None = None
) -> dict:
    """Robust single test runner with full result capture and logging."""
    case = _rehydrate_security_meta(case)
    # Resolve placeholders in base_url
    base_url = resolve_placeholders(base_url, execution_context or {})
    
    endpoint = case.get("endpoint_path", "/")
    if "{" in endpoint:
        # Fallback to a valid BSON ObjectId so Mongo doesn't crash on parse
        endpoint = _substitute_path_params(endpoint, case.get("path_params") or {}, "000000000000000000000001")
    url = f"{base_url.rstrip('/')}{endpoint}"
    method = case.get("method", "GET").upper()
    expected = case.get("expected_status", 200)
    owasp_cat = case.get("owasp_category", "")

    headers = {"User-Agent": "Cognitest-Security-Scanner/2.0"}
    if method in ("POST", "PUT", "PATCH"):
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    mutation_meta = case.get("mutation_meta") or {}
    if not mutation_meta and isinstance(case.get("metadata"), dict):
        mutation_meta = case.get("metadata").get("mutation_meta") or {}

    is_auth_negative = bool(mutation_meta.get("auth_removed"))
    auth_type = _resolve_auth_type(case)
    
    if is_auth_negative:
        _remove_header_case_insensitive(headers, "Authorization")

    auth_applied = _auth_header_present(headers)
    auth_warning = "Authorization header missing in outgoing request" if is_auth_negative or not auth_applied else None
    
    display_headers = dict(headers) if is_auth_negative else _mask_auth_header(headers)
    
    body = case.get("request_body") or case.get("request_data")
    is_multipart = case.get("request_type") == "multipart"
    
    kwargs: dict = {}
    if body and method in ("POST", "PUT", "PATCH"):
        if is_multipart:
            kwargs["data"] = body
        else:
            kwargs["json"] = body
    query = case.get("request_query") or case.get("query_params")
    if query:
        kwargs["params"] = query
        
    final_request_sent = redact_request_data({
        "url": url,
        "method": method,
        "headers": display_headers,
        "body": body,
    })

    if owasp_cat in ("TLS", "Misconfiguration"):
        kwargs["timeout"] = 5.0

    t0 = time.time()
    try:
        response = await client.request(method, url, headers=headers, **kwargs)
        actual = response.status_code
        elapsed_ms = int((time.time() - t0) * 1000)
        resp_body = response.text[:2048] if response.text else ""
        resp_headers = dict(response.headers)
    except Exception as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "event": "result", "id": case.get("id"), "name": case.get("name"), "endpoint_path": endpoint, "method": method,
            "expected_status": expected, "actual_status": 0, "passed": False, "response_time_ms": elapsed_ms,
            "request_headers": final_request_sent["headers"], "final_request_sent": final_request_sent,
            "auth_applied": auth_applied, "auth_status": "YES" if auth_applied else "NO",
            "auth_warning": auth_warning, "auth_type": auth_type if is_auth_negative else None,
            "owasp_category": case.get("owasp_category"), "error_message": str(exc),
            "log": f"[{method}] {url} -> ERROR: {exc}",
            "final_url": url, "resolved_headers": display_headers, "body_type": "multipart" if is_multipart else "json",
            "context_snapshot": {k: v for k, v in (execution_context or {}).items() if k not in ["token"]},
        }

    owasp = case.get("owasp_category", "")
    burst_all_200 = False
    if owasp == "RateLimit" and actual != 429:
        burst_statuses = [actual]
        for _ in range(10):
            await asyncio.sleep(0.02)
            try:
                r2 = await client.request(method, url, headers=headers, **kwargs)
                burst_statuses.append(r2.status_code)
                if r2.status_code == 429:
                    actual = 429
                    resp_body = r2.text[:2048]
                    resp_headers = dict(r2.headers)
                    break
            except Exception: break
        if actual != 429:
            burst_all_200 = all(s == 200 for s in burst_statuses)

    passed = _evaluate_pass_fail(expected, actual, case, body=resp_body, headers=resp_headers)
    inconclusive = (
        (actual == 0 and owasp_cat in ("TLS", "Misconfiguration"))
        or (actual == 401 and owasp_cat == "Injection")
        or (owasp_cat == "RateLimit" and actual != 429 and not burst_all_200)
    )

    error_msg = ""
    if owasp_cat == "RateLimit" and actual != 429:
        error_msg = "Rate limiting not enforced" if burst_all_200 else "Rate limiting not implemented"
    elif inconclusive:
        error_msg = "Inconclusive — endpoint timed out"
    elif not passed:
        error_msg = f"Expected {expected}, got {actual}"

    return {
        "event": "result", "id": case.get("id"), "name": case.get("name"), "endpoint_path": endpoint, "method": method,
        "expected_status": expected, "actual_status": actual, "passed": passed, "inconclusive": inconclusive,
        "response_time_ms": elapsed_ms, "response_body": resp_body, "response_headers": resp_headers,
        "request_headers": final_request_sent["headers"], "final_request_sent": final_request_sent,
        "auth_applied": auth_applied, "auth_status": "YES" if auth_applied else "NO",
        "auth_warning": auth_warning, "auth_type": auth_type if is_auth_negative else None,
        "injected_vars": (
            {
                k: v for k, v in (execution_context or {}).items()
                if k in ("user_id", "userId", "session_user_id", "email") and v
            }
        ),
        "owasp_category": case.get("owasp_category"), "error_message": error_msg,
        "log": f"[{method}] {url} -> {'PASS' if passed else 'FAIL'} (expected {expected}, got {actual}) {elapsed_ms}ms" + (" \u26a0" if inconclusive else ""),
        "final_url": url, "resolved_headers": display_headers, "body_type": "multipart" if is_multipart else "json",
        "context_snapshot": {k: v for k, v in (execution_context or {}).items() if k not in ["token"]},
    }



async def stream_run_suite(
    cases: list[dict],
    base_url: str,
    project_id: str,
    user_id: str = "system",
    delay_ms: int = 300,
    manual_token: str | None = None,
    auth_register_url: str | None = None,
    auth_login_url: str | None = None,
    auth_email: str | None = None,
    auth_password: str | None = None,
    request=None,  # fastapi.Request — used for disconnect detection
):
    """Router for test execution: Contract/Negative tests run locally, Functional tests are delegated."""
    is_contract = any((str(tc.get("test_type") or "").strip().lower() == "contract") or (str(tc.get("category") or "").strip().upper() == "CONTRACT") for tc in cases)
    is_negative = any((str(tc.get("category") or "").strip().upper() == "NEGATIVE") for tc in cases)

    if is_contract:
        # ── Build operations_by_key from the stored spec ──────────────────────
        # The executor needs the full canonical operation metadata (responses,
        # schemas, security) to run the validator.  Without it every test case
        # gets execution_status=CONFIG_ERROR because op is None.
        operations_by_key: dict[str, dict] = {}
        try:
            from src.modules.generator.engines.contract.contract_generator import coerce_canonical_spec as _coerce
            api_spec_row = await prisma.apispec.find_first(
                where={"projectId": project_id},
                order={"createdAt": "desc"},
            )
            if api_spec_row and api_spec_row.parsed_spec:
                raw_spec = (
                    api_spec_row.parsed_spec
                    if isinstance(api_spec_row.parsed_spec, dict)
                    else json.loads(api_spec_row.parsed_spec)
                )
                canonical = _coerce(raw_spec)
                for op in (canonical.get("operations") or []):
                    if isinstance(op, dict) and isinstance(op.get("operation_key"), str):
                        operations_by_key[op["operation_key"]] = op
                logger.info("[CONTRACT] loaded %d operations from spec", len(operations_by_key))
        except Exception as _e:
            logger.warning("[CONTRACT] could not load spec for validation: %s", _e)

        # ── Restore contract-executor fields from DB storage ──────────────────
        # Two persistence paths exist:
        #   A. persist_contract_suite_and_cases → stores fields in assertions (dict)
        #   B. generation_service.py            → stores fields in metadata (dict)
        # Both paths are checked; operation_key is always re-derived from
        # method + endpoint_path as a deterministic fallback so it is never
        # missing regardless of which path wrote the DB row.
        _CONTRACT_KEYS = (
            "operation_key", "kind", "expected_statuses", "security_required",
            "auth_negative", "missing_field", "format_field", "format",
            "resource_key", "dependency_map", "depends_on",
            "produces_entity", "produced_id_paths", "is_producer_endpoint",
            "mutation_meta",
        )
        normalized_cases: list[dict] = []
        for tc in cases:
            merged = dict(tc)

            # Path A: assertions column stored as dict (persist_contract_suite_and_cases)
            assertions = merged.get("assertions") or {}
            if isinstance(assertions, str):
                try:
                    assertions = json.loads(assertions)
                except Exception:
                    assertions = {}
            if not isinstance(assertions, dict):
                assertions = {}

            # Path B: metadata column (generation_service.py)
            metadata = merged.get("metadata") or {}
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except Exception:
                    metadata = {}
            if not isinstance(metadata, dict):
                metadata = {}

            for _k in _CONTRACT_KEYS:
                if merged.get(_k) is None:
                    if _k in assertions and assertions[_k] is not None:
                        merged[_k] = assertions[_k]
                    elif _k in metadata and metadata[_k] is not None:
                        merged[_k] = metadata[_k]

            # Always derive operation_key from method + path — it is deterministic
            # and guaranteed to match what coerce_canonical_spec generates.
            if not merged.get("operation_key"):
                _m = str(merged.get("method") or "GET").lower()
                _p = str(merged.get("endpoint_path") or "/")
                merged["operation_key"] = f"{_m}:{_p}"

            # security_required fallback from requires_auth
            if merged.get("security_required") is None:
                merged["security_required"] = bool(merged.get("requires_auth"))

            normalized_cases.append(merged)

        # ── Stream results ────────────────────────────────────────────────────
        yield json.dumps({"event": "start", "total": len(normalized_cases)}) + "\n"

        _failed_count = 0
        async for res in execute_contract_test_cases(
            test_cases=normalized_cases,
            base_url=base_url,
            auth_enabled=True,
            timeout_seconds=20.0,
            concurrency=1,
            operations_by_key=operations_by_key,
        ):
            _fs = res.get("final_status") or ""
            if _fs not in ("PASS", "WARNING", "SKIPPED"):
                _failed_count += 1
            yield json.dumps(res, default=str) + "\n"

        yield json.dumps({
            "event": "done",
            "total": len(normalized_cases),
            "failed": _failed_count,
        }) + "\n"

    elif is_negative:
        # 🔥 NEGATIVE TESTS → RUN LOCALLY with full auth + stateful support

        yield json.dumps({"event": "start", "total": len(cases)}) + "\n"
        await asyncio.sleep(0.05)

        # ── Execution context for dynamic variables ──
        timestamp_ms = int(time.time() * 1000)
        execution_context: dict[str, Any] = {
            "token": None,
            "entities": {},
            "email": f"test_run_{timestamp_ms}@example.com",
            "timestamp": str(timestamp_ms),
            "run_id": str(uuid.uuid4())[:8],
        }

        # ── TestRun DB persistence ──
        run_id = "stub-run"
        run_categories = list(set(
            (c.get("test_type") or c.get("category") or "NEGATIVE").upper()
            for c in cases
        ))
        try:
            suite_ids = {
                (c.get("suiteId") or c.get("suite_id"))
                for c in cases if isinstance(c, dict)
            }
            suite_ids.discard(None)
            suite_ids.discard("")
            suite_id_for_run = next(iter(suite_ids)) if len(suite_ids) == 1 else None

            test_run = await create_testrun_compat(
                prisma=prisma,
                project_id=project_id,
                suite_id=suite_id_for_run,
                environment="streaming-execution",
                status="RUNNING",
                categories=run_categories,
                total_tests=len(cases),
                user_id=user_id,
            )
            run_id = test_run.id
            yield json.dumps({"event": "run_created", "run_id": run_id}) + "\n"
        except Exception as e:
            logger.error("Failed to create TestRun: %s", e)

        results = []
        category_stats = {}

        from src.utils.egress_guard import validate_egress_url as _veg, build_pinned_transport as _bpt
        _neg_guard = _veg(base_url)
        async with httpx.AsyncClient(
            transport=_bpt(_neg_guard),
            timeout=60.0,
            follow_redirects=False,
        ) as client:
            # ── Auth session: manual token, explicit auth, or auto-discovery ──
            session_token: str | None = None
            session_user_id: str | None = None
            normalized_manual_token = _normalize_token(manual_token)
            token_mode = bool(normalized_manual_token)
            use_auth = bool(auth_login_url and auth_email and auth_password) and not token_mode

            if token_mode:
                session_token = normalized_manual_token
                execution_context["token"] = session_token
                yield json.dumps({
                    "event": "banner",
                    "log": "[AUTH] Token mode active — manual token will be injected when required",
                }) + "\n"
                await asyncio.sleep(0.05)

            if use_auth:
                yield json.dumps({
                    "event": "session_start",
                    "log": "▶ Starting auth session — setting up test user...",
                }) + "\n"
                await asyncio.sleep(0.05)

                current_email = execution_context["email"]
                session_token, session_user_id = await _neg_auth_session_setup(
                    client, base_url,
                    auth_register_url or None,
                    auth_login_url,
                    current_email,
                    auth_password,
                )

                if session_token:
                    execution_context["token"] = session_token
                    yield json.dumps({
                        "event": "session_step", "step": "authenticated", "status": "ok",
                        "log": "  ✓ JWT acquired — token will be injected into all test requests",
                    }) + "\n"
                else:
                    yield json.dumps({
                        "event": "session_step", "step": "authenticated", "status": "fail",
                        "log": "  ✗ Could not acquire JWT (register/login failed) — running without auth",
                    }) + "\n"
                await asyncio.sleep(0.1)

            # ── Auto-discovery auth: when no manual token AND no auth config ──
            if not token_mode and not use_auth and not session_token:
                yield json.dumps({
                    "event": "session_start",
                    "log": "▶ [Auto-Auth] No token or auth config provided — auto-discovering auth endpoints...",
                }) + "\n"
                await asyncio.sleep(0.05)

                _auto_spec: dict | None = None
                try:
                    api_spec_row = await prisma.apispec.find_first(
                        where={"projectId": project_id},
                        order={"createdAt": "desc"},
                    )
                    if api_spec_row and api_spec_row.parsed_spec:
                        _auto_spec = (
                            api_spec_row.parsed_spec
                            if isinstance(api_spec_row.parsed_spec, dict)
                            else json.loads(api_spec_row.parsed_spec)
                        )
                except Exception:
                    pass

                _auto_login_url: str | None = None
                _auto_register_url: str | None = None
                _login_kw = {"login", "signin", "sign-in", "sign_in", "token", "authenticate"}
                _signup_kw = {"register", "signup", "sign-up", "sign_up"}
                _skip_kw = {"logout", "refresh", "verify", "confirm", "password", "reset", "otp"}

                if _auto_spec and isinstance(_auto_spec.get("paths"), dict):
                    for path_key, path_item in _auto_spec["paths"].items():
                        clean = path_key.lower()
                        if any(k in clean for k in _skip_kw):
                            continue
                        has_post = "post" in (path_item or {})
                        if not has_post:
                            continue
                        if not _auto_login_url and any(k in clean for k in _login_kw):
                            _auto_login_url = path_key
                        if not _auto_register_url and any(k in clean for k in _signup_kw):
                            _auto_register_url = path_key

                if _auto_login_url:
                    yield json.dumps({
                        "event": "session_step", "step": "spec_discovery", "status": "ok",
                        "log": f"  ✓ Discovered: register={_auto_register_url or '(none)'}, login={_auto_login_url}",
                    }) + "\n"
                    await asyncio.sleep(0.05)

                    _auto_email = execution_context["email"]
                    _auto_password = "CogniTest@2024!"
                    session_token, session_user_id = await _neg_auth_session_setup(
                        client, base_url,
                        _auto_register_url,
                        _auto_login_url,
                        _auto_email,
                        _auto_password,
                        spec=_auto_spec,
                    )

                if not _auto_login_url:
                    # Fallback: brute-force probe common paths
                    _burl = base_url.rstrip("/")
                    _probe_login_paths = ["/api/auth/login", "/api/login", "/auth/login", "/login"]
                    _probe_register_paths = ["/api/auth/signup", "/api/auth/register", "/api/register", "/auth/signup", "/signup", "/register"]
                    _probed_login: str | None = None
                    _probed_register: str | None = None

                    for p in _probe_login_paths:
                        try:
                            r = await client.post(f"{_burl}{p}", json={}, timeout=5.0)
                            if r.status_code not in (404, 405, 503):
                                _probed_login = p
                                break
                        except Exception:
                            pass

                    if _probed_login:
                        for p in _probe_register_paths:
                            try:
                                r = await client.post(f"{_burl}{p}", json={}, timeout=5.0)
                                if r.status_code not in (404, 405, 503):
                                    _probed_register = p
                                    break
                            except Exception:
                                pass

                        yield json.dumps({
                            "event": "session_step", "step": "brute_probe", "status": "ok",
                            "log": f"  ✓ Probed: register={_probed_register or '(none)'}, login={_probed_login}",
                        }) + "\n"
                        await asyncio.sleep(0.05)

                        _auto_email = execution_context["email"]
                        _auto_password = "CogniTest@2024!"
                        session_token, session_user_id = await _neg_auth_session_setup(
                            client, base_url,
                            _probed_register,
                            _probed_login,
                            _auto_email,
                            _auto_password,
                            spec=_auto_spec,
                        )

                # Final result
                if session_token:
                    execution_context["token"] = session_token
                    if session_user_id:
                        execution_context["user_id"] = session_user_id
                    yield json.dumps({
                        "event": "session_step", "step": "authenticated", "status": "ok",
                        "log": "  ✓ Auto-auth JWT acquired — token will be injected into all test requests",
                    }) + "\n"
                else:
                    yield json.dumps({
                        "event": "session_step", "step": "authenticated", "status": "fail",
                        "log": "  ✗ Auto-auth could not acquire JWT — running without auth",
                    }) + "\n"

                await asyncio.sleep(0.1)

            # ── Sort: burst/rate-limit cases last so they don't corrupt earlier results ──
            _non_burst = [c for c in cases if not c.get("burst_count")]
            _burst = [c for c in cases if c.get("burst_count")]
            cases = _non_burst + _burst

            # ── Outbound request counter ──
            _outbound_count = [0]

            # ── Shared sequential semaphore for burst cases ──
            _burst_semaphore = asyncio.Semaphore(1)

            # ── Category tracking + test execution ──
            _cancelled = False
            try:
                for i, case in enumerate(cases):
                    # Disconnect check — break before starting next test case
                    if await _is_disconnected(request):
                        logger.info("[stream_run_suite] Client disconnected at case %d/%d", i, len(cases))
                        _cancelled = True
                        break

                    cat_key = str(case.get("category") or case.get("test_type") or "NEGATIVE").upper()

                    # ── Workflow / stateful sequence test case ──
                    metadata = case.get("metadata") or {}
                    if isinstance(metadata, str):
                        try:
                            metadata = json.loads(metadata)
                        except Exception:
                            metadata = {}
                    steps = case.get("steps") or (metadata.get("steps") if isinstance(metadata, dict) else None)

                    if steps:
                        case["steps"] = steps
                        workflow_id = case.get("id", f"wf-{i}")

                        yield json.dumps({
                            "event": "workflow_start",
                            "index": i,
                            "workflow_id": workflow_id,
                            "name": case.get("name", "Workflow"),
                            "steps": len(steps),
                            "state_machine": case.get("state_machine", []),
                        }) + "\n"
                        await asyncio.sleep(0.05)

                        executor = WorkflowExecutor()
                        wf_result = await executor.run(case, base_url, client, initial_context=execution_context)

                        for step_res in wf_result.step_results:
                            yield json.dumps(step_res.to_event(workflow_id)) + "\n"
                            await asyncio.sleep(0.1)

                        if wf_result.rollback_triggered:
                            yield json.dumps(wf_result.to_rollback_event()) + "\n"
                            await asyncio.sleep(0.05)

                        summary_event = wf_result.to_summary_event()
                        yield json.dumps(summary_event) + "\n"
                        await asyncio.sleep(0.15)

                        flat_result = {
                            "event": "result",
                            "index": i,
                            "id": workflow_id,
                            "name": case.get("name", "Workflow"),
                            "endpoint_path": case.get("endpoint_path", ""),
                            "method": case.get("method", ""),
                            "expected_status": case.get("expected_status", 200),
                            "actual_status": (wf_result.step_results[0].actual_status
                                              if wf_result.step_results else 0),
                            "passed": wf_result.passed,
                            "response_time_ms": wf_result.total_time_ms,
                            "response_body": "",
                            "response_headers": {},
                            "error_message": wf_result.rollback_reason if wf_result.rollback_triggered else "",
                            "is_workflow": True,
                            "workflow_steps": len(steps),
                            "final_state": wf_result.final_state,
                            "log": (
                                f"[WORKFLOW] {case.get('name', '')} -> "
                                f"{'PASS' if wf_result.passed else 'FAIL'} "
                                f"({len(steps)} steps, {wf_result.total_time_ms}ms, "
                                f"state={wf_result.final_state})"
                            ),
                        }
                        results.append(flat_result)

                        # Persist TestResult for workflow-style negative test case
                        try:
                            tc_id = case.get("id")
                            tc_exists = await prisma.testcase.find_unique(where={"id": tc_id}) if tc_id else None
                            if tc_exists and run_id != "stub-run":
                                await prisma.testresult.create(data={
                                    "runId": run_id,
                                    "testCaseId": tc_id,
                                    "status": "PASSED" if wf_result.passed else "FAILED",
                                    "category": str(tc_exists.category),
                                    "subCategory": str(tc_exists.subCategory),
                                    "expected_status": case.get("expected_status", 200),
                                    "actual_status": flat_result["actual_status"],
                                    "response_time_ms": wf_result.total_time_ms,
                                    "error_message": flat_result.get("error_message") or None,
                                })
                        except Exception as _tr_exc:
                            logger.warning("[negative] Failed to persist TestResult (workflow): %s", _tr_exc)

                        if cat_key not in category_stats:
                            category_stats[cat_key] = {"passed": 0, "failed": 0, "total": 0}
                        category_stats[cat_key]["total"] += 1
                        if wf_result.passed:
                            category_stats[cat_key]["passed"] += 1
                        else:
                            category_stats[cat_key]["failed"] += 1
                        continue

                    # ── Flat (non-workflow) test case ──
                    endpoint_path_template = case.get("endpoint_path", "/").split("#")[0]
                    endpoint_path_template = resolve_placeholders(endpoint_path_template, execution_context)
                    case_path_params = resolve_placeholders(case.get("path_params") or {}, execution_context)
                    if "**INVALID_ID**" in str(list((case_path_params or {}).values())):
                        fallback_uid = None
                    else:
                        fallback_uid = execution_context.get("user_id") or execution_context.get("session_user_id")
                    try:
                        rendered_path = _substitute_path_params(
                            endpoint_path_template,
                            case_path_params,
                            fallback_id=str(fallback_uid) if fallback_uid else None,
                        )
                    except ValueError as e:
                        logger.warning(f"Skipping test case: {e}")
                        continue

                    hdrs = {}
                    auth_type = _resolve_auth_type(case)
                    is_auth_negative = case.get("kind") in ["negative_auth", "negative_auth_missing"]

                    if session_token and not is_auth_negative:
                        hdrs["Authorization"] = f"Bearer {session_token}"
                    elif normalized_manual_token and not is_auth_negative:
                        hdrs["Authorization"] = f"Bearer {normalized_manual_token}"

                    resolved_case = {**case, "endpoint_path": rendered_path}
                    res = await _run_one(client, resolved_case, base_url, extra_headers=hdrs, execution_context=execution_context)
                    _outbound_count[0] += 1
                    results.append(res)
                    yield json.dumps(res) + "\n"

                    # Persist TestResult for flat negative test case
                    try:
                        tc_id = case.get("id")
                        tc_exists = await prisma.testcase.find_unique(where={"id": tc_id}) if tc_id else None
                        if tc_exists and run_id != "stub-run":
                            await prisma.testresult.create(data={
                                "runId": run_id,
                                "testCaseId": tc_id,
                                "status": "PASSED" if res.get("passed") else "FAILED",
                                "category": str(tc_exists.category),
                                "subCategory": str(tc_exists.subCategory),
                                "expected_status": res.get("expected_status", case.get("expected_status", 200)),
                                "actual_status": res.get("actual_status", 0),
                                "response_time_ms": res.get("response_time_ms", 0),
                                "error_message": res.get("error_message") or None,
                                "response_body": PrismaJson({"text": str(res.get("response_body", ""))}) if res.get("response_body") else None,
                                "response_headers": PrismaJson(res.get("response_headers", {})) if res.get("response_headers") else None,
                            })
                    except Exception as _tr_exc:
                        logger.warning("[negative] Failed to persist TestResult (flat): %s", _tr_exc)

                    if cat_key not in category_stats:
                        category_stats[cat_key] = {"passed": 0, "failed": 0, "total": 0}
                    category_stats[cat_key]["total"] += 1
                    if res.get("passed"):
                        category_stats[cat_key]["passed"] += 1
                    else:
                        category_stats[cat_key]["failed"] += 1

                    await asyncio.sleep(delay_ms / 1000.0)

            except asyncio.CancelledError:
                logger.info("[stream_run_suite] CancelledError caught — marking run cancelled")
                _cancelled = True
            except Exception as _exc:
                logger.exception("[stream_run_suite] Unhandled exception in test loop: %s", _exc)
                await _mark_run_status(run_id, "FAILED", results)
                _run_results_store[project_id] = {
                    "results": results,
                    "summary": {"total": len(results), "passed": sum(1 for r in results if r.get("passed")), "failed": len(results) - sum(1 for r in results if r.get("passed"))},
                }
                raise
            finally:
                # Persist whichever terminal status applies
                final_status = "CANCELLED" if _cancelled else "COMPLETED"
                await _mark_run_status(run_id, final_status, results)
                _run_results_store[project_id] = {
                    "results": results,
                    "summary": {"total": len(results), "passed": sum(1 for r in results if r.get("passed")), "failed": len(results) - sum(1 for r in results if r.get("passed"))},
                }

        if _cancelled:
            yield json.dumps({"event": "cancelled", "total": len(results), "run_id": run_id}) + "\n"
        else:
            yield json.dumps({
                "event": "done",
                "total": len(results),
                "passed": sum(1 for r in results if r.get("passed")),
                "categorySummary": category_stats,
                "run_id": run_id,
                "total_outbound_requests": _outbound_count[0],
            }) + "\n"

    else:
        # 🔥 FUNCTIONAL TESTS → DELEGATE TO OWN FOLDER
        async for event in functional_stream_run_suite(
            cases=cases, base_url=base_url, project_id=project_id, user_id=user_id, delay_ms=delay_ms,
            manual_token=manual_token, auth_register_url=auth_register_url, auth_login_url=auth_login_url,
            auth_email=auth_email, auth_password=auth_password,
        ):
            yield event

async def stream_security_suite(
    cases: list[dict],
    base_url: str,
    project_id: str = "",
    user_id: str = "system",
    spec: dict | None = None,
    pre_user_a_token: str | None = None,
    pre_user_b_token: str | None = None,
    pre_resource_id: str | None = None,
    admin_token: str | None = None,
    manual_token: str | None = None,
    auth_register_url: str | None = None,
    auth_login_url: str | None = None,
    auth_email: str | None = None,
    auth_password: str | None = None,
    request=None,  # fastapi.Request — used for disconnect detection
):
    """Security/Fuzz router: BOLA/OWASP runs locally, Payload Fuzzing is delegated."""
    # Check if this is a stateless Fuzz scan vs a stateful Security scan
    is_fuzz = any(str(tc.get("test_type") or "").strip().lower() == "fuzz" for tc in cases)
    
    if is_fuzz:
        # 🔥 FUZZ TESTS → DELEGATE TO OWN FOLDER
        async for event in fuzz_stream_security_suite(
            cases=cases, base_url=base_url, project_id=project_id, user_id=user_id, spec=spec,
            pre_user_a_token=pre_user_a_token, pre_user_b_token=pre_user_b_token,
            pre_resource_id=pre_resource_id, admin_token=admin_token,
            manual_token=manual_token, auth_register_url=auth_register_url,
            auth_login_url=auth_login_url, auth_email=auth_email, auth_password=auth_password,
        ):
            yield event
    else:
        # 🔥 SECURITY TESTS → ORCHESTRATE REAL STATEFUL EXECUTION
        yield json.dumps({"event": "start", "total": len(cases)}) + "\n"
        results = []
        category_stats = {}
        
        normalized_manual_token = _normalize_token(manual_token) or _normalize_token(admin_token)
        token_mode = bool(normalized_manual_token)
        use_auth = bool(auth_login_url and auth_email and auth_password) and not token_mode

        # 1. Segregate tests
        stateless_cases = []
        stateful_cases = []
        for tc in cases:
            # Rehydrate from DB storage before categorizing
            tc = _rehydrate_security_meta(tc)
            
            # Check requires_stateful boolean or specific OWASP categories
            is_stateful = (
                tc.get("requires_stateful") is True 
                or str(tc.get("requires_stateful")).lower() == "true"
                or tc.get("owasp_category") in ("API1:2023", "API5:2023", "BOLA", "WrongRole", "Privilege Escalation")
            )
            if is_stateful:
                stateful_cases.append(tc)
            else:
                stateless_cases.append(tc)
        
        from src.utils.egress_guard import validate_egress_url as _veg2, build_pinned_transport as _bpt2
        _sec_guard = _veg2(base_url)
        async with httpx.AsyncClient(
            transport=_bpt2(_sec_guard),
            timeout=60.0,
        ) as client:
            setup_ctx = {}
            owner_headers = {}
            attacker_headers = {}

            # ==========================================
            # PHASE 1: STATEFUL ENVIRONMENT SETUP
            # ==========================================
            yield json.dumps({"event": "banner", "log": "───────── Stateful Environment Setup ─────────"}) + "\n"
            
            if pre_user_a_token and pre_user_b_token:
                setup_ctx = {"token_a": pre_user_a_token, "token_b": pre_user_b_token, "resource_id": pre_resource_id}
                yield json.dumps({"event": "setup_step", "step": "Pre-configured", "status": "ok", "log": "  ✓ Using pre-configured stateful credentials"}) + "\n"
            elif token_mode:
                setup_ctx = {"token_a": normalized_manual_token}
                yield json.dumps({"event": "setup_step", "step": "Token Auth", "status": "ok", "log": "  ✓ Using provided token for secured requests"}) + "\n"
            elif use_auth and not stateful_cases:
                # If there are no stateful cases, but user provided custom auth, fall back to simple session setup
                yield json.dumps({"event": "session_start", "log": "▶ Starting auth session for Security tests..."}) + "\n"
                t_a, _ = await _neg_auth_session_setup(
                    client,
                    base_url,
                    auth_register_url or None,
                    auth_login_url,
                    auth_email,
                    auth_password,
                    spec=spec,
                    admin_token=admin_token,
                )
                if t_a:
                    setup_ctx["token_a"] = t_a
                else:
                    yield json.dumps({"event": "setup_step", "step": "Auth Session", "status": "fail", "log": "  ✗ Could not acquire auth token from the configured register/login endpoints"}) + "\n"
            elif not stateful_cases:
                yield json.dumps({
                    "event": "setup_step",
                    "step": "Auth Setup",
                    "status": "warn",
                    "log": "  ℹ No token/session configured; secured stateless endpoints may return 401",
                }) + "\n"
            else:
                # Run full stateful setup (User A, Resource, User B)
                async for event in _stateful_setup(client, base_url, spec, admin_token=admin_token):
                    if event.startswith('{"event": "_setup_ctx"'):
                        setup_ctx = json.loads(event)["ctx"]
                    else:
                        yield event

            token_a = setup_ctx.get("token_a")
            token_b = setup_ctx.get("token_b")
            resource_id = setup_ctx.get("resource_id")
            
            owner_headers = {"Authorization": f"Bearer {token_a}"} if token_a else ({"Authorization": f"Bearer {normalized_manual_token}"} if token_mode else {})
            attacker_headers = {"Authorization": f"Bearer {token_b}"} if token_b else {}

            # ── Outbound request counter for the security suite ───────────
            _sec_outbound_count = [0]

            # ==========================================
            # PHASE 2: STATELESS TESTS
            # ==========================================
            _sec_cancelled = False
            try:
                if stateless_cases:
                    grouped_stateless = {}
                    for tc in stateless_cases:
                        cat = tc.get("owasp_category", "General")
                        grouped_stateless.setdefault(cat, []).append(tc)

                    for cat, cat_cases in grouped_stateless.items():
                        banner_label = _CATEGORY_LABEL.get(cat, f"4.X  {cat}")
                        yield json.dumps({"event": "banner", "log": f"───────── {banner_label} ─────────"}) + "\n"
                        for case in cat_cases:
                            if await _is_disconnected(request):
                                logger.info("[stream_security_suite] Client disconnected (stateless phase)")
                                _sec_cancelled = True
                                break
                            path = case.get("endpoint_path", "")
                            if resource_id:
                                path = re.sub(r"\{\w+\}", str(resource_id), path)

                            res = await _run_one(client, {**case, "endpoint_path": path}, base_url, owner_headers, execution_context=setup_ctx)
                            _sec_outbound_count[0] += 1
                            results.append(res)
                            yield json.dumps(res) + "\n"

                            if cat not in category_stats: category_stats[cat] = {"passed": 0, "failed": 0, "total": 0}
                            category_stats[cat]["total"] += 1
                            if res.get("passed"): category_stats[cat]["passed"] += 1
                            else: category_stats[cat]["failed"] += 1
                        if _sec_cancelled:
                            break

                # ==========================================
                # PHASE 3: STATEFUL TESTS EXECUTION
                # ==========================================
                if stateful_cases and not _sec_cancelled:
                    yield json.dumps({"event": "banner", "log": "───────── 4.3  BOLA / Privilege Escalation ─────────"}) + "\n"
                    for case in stateful_cases:
                        if await _is_disconnected(request):
                            logger.info("[stream_security_suite] Client disconnected (stateful phase)")
                            _sec_cancelled = True
                            break
                        cat = case.get("owasp_category", "BOLA")

                        path = case.get("endpoint_path", "")
                        if resource_id:
                            path = re.sub(r"\{\w+\}", str(resource_id), path)

                        res = await _run_one(client, {**case, "endpoint_path": path}, base_url, attacker_headers, execution_context=setup_ctx)
                        _sec_outbound_count[0] += 1
                        results.append(res)
                        yield json.dumps(res) + "\n"

                        if cat not in category_stats: category_stats[cat] = {"passed": 0, "failed": 0, "total": 0}
                        category_stats[cat]["total"] += 1
                        if res.get("passed"): category_stats[cat]["passed"] += 1
                        else: category_stats[cat]["failed"] += 1

            except asyncio.CancelledError:
                logger.info("[stream_security_suite] CancelledError caught")
                _sec_cancelled = True

                # ==========================================
                # PHASE 4: CLEANUP (always runs)
                # ==========================================
            if stateful_cases:
                yield json.dumps({"event": "banner", "log": "───────── Stateful Environment Cleanup ─────────"}) + "\n"
                uid_a = setup_ctx.get("user_id_a")
                uid_b = setup_ctx.get("user_id_b")

                if token_a and uid_a:
                    yield json.dumps({"event": "setup_step", "log": "  → Deleting User A..."}) + "\n"
                    ok_a = await _auth_session_cleanup(client, base_url, token_a, uid_a)
                    if ok_a:
                        yield json.dumps({"event": "setup_step", "log": "  ✓ User A deleted"}) + "\n"
                    else:
                        yield json.dumps({"event": "setup_step", "log": "  ℹ Could not delete User A (no cleanup endpoint found)"}) + "\n"

                if token_b and uid_b:
                    yield json.dumps({"event": "setup_step", "log": "  → Deleting User B..."}) + "\n"
                    ok_b = await _auth_session_cleanup(client, base_url, token_b, uid_b)
                    if ok_b:
                        yield json.dumps({"event": "setup_step", "log": "  ✓ User B deleted"}) + "\n"

        if _sec_cancelled:
            yield json.dumps({"event": "cancelled", "total": len(results)}) + "\n"
        else:
            yield json.dumps({
                "event": "done",
                "total": len(results),
                "passed": sum(1 for r in results if r.get("passed")),
                "categorySummary": category_stats,
                "total_outbound_requests": _sec_outbound_count[0],
            }) + "\n"
