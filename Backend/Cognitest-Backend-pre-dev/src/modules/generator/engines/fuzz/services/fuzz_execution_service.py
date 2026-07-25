import json
import logging
import asyncio
import time
import random
import string
import re
import httpx
from datetime import datetime, timezone
from typing import Any, Optional
from src.config import prisma
from prisma import Json as PrismaJson

from src.modules.generator.spec_parser import extract_endpoints
from src.modules.generator.services.data_provider import DataProviderService
from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
from src.modules.generator.engines.functional.variable_resolver import resolve_placeholders

logger = logging.getLogger(__name__)

# Icons and box characters for terminal output
ICON_OK = "✓"
ICON_FAIL = "✗"
ICON_ARROW = "→"
ICON_INFO = "▶"
LINE_CHAR = "─"
BOX_TOP_LEFT = "┌"
ICON_WARN = "⚠"

# OWASP category display labels
_CATEGORY_LABEL = {
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

def _evaluate_pass_fail(expected: Any, actual: int, case: dict) -> bool:
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

async def _run_one(client: httpx.AsyncClient, case: dict, base_url: str, extra_headers: dict | None = None) -> dict:
    endpoint = case["endpoint_path"]
    
    # Feature 3: Path Parameter Injection Check
    if "{" in endpoint:
        return {
            "event": "result", "id": case["id"], "name": case["name"],
            "endpoint_path": endpoint, "method": case["method"].upper(), "expected_status": case["expected_status"],
            "actual_status": 0, "passed": True, "inconclusive": True, "response_time_ms": 0,
            "owasp_category": case.get("owasp_category"), "error_message": f"Inconclusive \u2014 Missing required resource ID: {endpoint}",
            "log": f"[{case['method'].upper()}] {endpoint} -> PASS (missing parameter) \u26a0",
        }

    url = f"{base_url.rstrip('/')}{endpoint}"
    method = case["method"].upper()
    expected = case["expected_status"]

    headers = {"User-Agent": "Cognitest-Security-Scanner/2.0"}
    if method in ("POST", "PUT", "PATCH"):
        headers["Content-Type"] = "application/json"
    
    # Generic Auth Injection for Security Tests
    auth_neg = case.get("auth_negative") or case.get("kind") == "negative_auth_missing"
    if extra_headers:
        headers.update(extra_headers)
    
    if "Authorization" in headers and not auth_neg:
        token = headers["Authorization"]
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        for h in ["x-auth-token", "x-access-token", "x-api-key"]:
            if h not in headers:
                headers[h] = token
    
    if auth_neg:
        for h in ["Authorization", "x-auth-token", "x-access-token", "x-api-key"]:
            headers.pop(h, None)

    body = case.get("request_body") or case.get("request_data")
    kwargs: dict = {"timeout": 10.0}

    is_multipart = isinstance(body, dict) and body.get("type") == "multipart"
    if is_multipart:
        kwargs["data"] = body.get("fields", {})
        httpx_files = {}
        for k, v in body.get("files", {}).items():
            if isinstance(v, dict):
                httpx_files[k] = (v.get("filename", "test.txt"), v.get("content", "").encode() if isinstance(v.get("content"), str) else b"", v.get("content_type", "text/plain"))
            else:
                httpx_files[k] = ("test.txt", str(v).encode(), "text/plain")
        kwargs["files"] = httpx_files
        headers.pop("Content-Type", None)
    elif body and method in ("POST", "PUT", "PATCH"):
        kwargs["json"] = body

    query = case.get("request_query") or case.get("query_params")
    if query:
        kwargs["params"] = query

    t0 = time.time()
    try:
        response = await client.request(method, url, headers=headers, **kwargs)
        actual = response.status_code
        elapsed_ms = int((time.time() - t0) * 1000)
        resp_body = response.text[:2048] if response.text else ""
        resp_headers = dict(response.headers)
    except asyncio.TimeoutError:
        return {
            "event": "result", "id": case["id"], "name": case["name"],
            "endpoint_path": endpoint, "method": method, "expected_status": expected,
            "actual_status": 0, "passed": False, "inconclusive": True, "response_time_ms": int((time.time() - t0) * 1000),
            "owasp_category": case.get("owasp_category"), "error_message": "Request Timed Out (10s)",
            "log": f"[{method}] {url} -> INCONCLUSIVE (TIMEOUT) \u26a0",
        }
    except Exception as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {
            "event": "result", "id": case["id"], "name": case["name"],
            "endpoint_path": endpoint, "method": method, "expected_status": expected,
            "actual_status": 0, "passed": False, "inconclusive": True, "response_time_ms": elapsed_ms,
            "owasp_category": case.get("owasp_category"), "error_message": str(exc),
            "log": f"[{method}] {url} -> INCONCLUSIVE (ERROR: {str(exc)[:30]}) \u26a0",
        }

    passed = _evaluate_pass_fail(expected, actual, case)
    error_message = ""
    if not passed:
        if actual == 502: error_message = "BAD GATEWAY: Potential backend crash due to fuzz payload"
        elif actual >= 500: error_message = f"SERVER ERROR ({actual}): Backend failed to handle security payload"
        else: error_message = f"Expected {expected}, got {actual}"

    is_inconclusive = (actual == 0)
    status_label = "INCONCLUSIVE" if is_inconclusive else ("PASS" if passed else "FAIL")

    return {
        "event": "result", "id": case["id"], "name": case["name"],
        "endpoint_path": endpoint, "method": method, "expected_status": expected,
        "actual_status": actual, "passed": passed, "inconclusive": is_inconclusive, "response_time_ms": elapsed_ms,
        "response_body": resp_body, "response_headers": resp_headers,
        "request_headers": headers,
        "request_body": body if not is_multipart else {"info": "Multipart Data", "fields": kwargs.get("data")},
        "body_type": "multipart" if is_multipart else "json",
        "owasp_category": case.get("owasp_category"),
        "error_message": error_message,
        "log": f"[{method}] {url} -> {status_label} (expected {expected}, got {actual}) {elapsed_ms}ms" + (" \u26a0" if is_inconclusive else ""),
    }

async def _stateful_setup(client: httpx.AsyncClient, base_url: str, spec: dict | None = None):
    def rand_suffix() -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=6))

    burl = base_url.rstrip("/")
    ctx: dict[str, str | None] = {
        "token_a": None, "token_b": None, "user_id_a": None, "user_id_b": None,
        "resource_id": None, "email_a": None, "email_b": None,
    }

    try: await client.get(burl, timeout=10.0)
    except: pass
    await asyncio.sleep(1.0)

    spec_signup, spec_login, spec_resource = [], [], []
    if spec and isinstance(spec, dict):
        for raw_path, path_item in (spec.get("paths") or {}).items():
            clean = raw_path.lower()
            if "post" not in (path_item or {}): continue
            actual_path = raw_path.split("#")[0]
            if any(k in clean for k in ("register", "signup")) and "{" not in clean: spec_signup.append(actual_path)
            elif any(k in clean for k in ("login", "signin", "token")) and "{" not in clean: spec_login.append(actual_path)
            elif any(k in clean for k in ("item", "product", "post")) and "{" not in clean: spec_resource.append(actual_path)

    signup_candidates = spec_signup + ["/api/auth/signup", "/api/auth/register", "/api/register", "/register", "/signup"]
    login_candidates = spec_login + ["/api/auth/login", "/api/login", "/auth/login", "/login"]
    resource_candidates = spec_resource or ["/api/items", "/api/products", "/api/posts", "/items", "/products"]

    password = "CogniTest123!"
    data_provider = DataProviderService()
    all_endpoints = extract_endpoints(spec) if spec else []

    email_a = f"cogni{rand_suffix()}@test.com"; email_b = f"cogni{rand_suffix()}@test.com"
    ctx["email_a"] = email_a; ctx["email_b"] = email_b

    def _get_auth_body(path: str, email: str):
        target = next((e for e in all_endpoints if e.path == path), None)
        if not target or not target.body_schema:
            return {"email": email, "password": password}
        props = target.body_schema.get("properties", {})
        body = {}
        for k, s in props.items():
            kl = k.lower()
            if "email" in kl: body[k] = email
            elif "user" in kl and "name" not in kl: body[k] = email
            elif "pass" in kl: body[k] = password
            elif "name" in kl: body[k] = "Cogni Test"
            else: body[k] = data_provider.get_sample_value(k, s.get("type", "string"), s)
        return body

    async def _try_login(email: str):
        for path in login_candidates:
            payload = _get_auth_body(path, email)
            try:
                r = await client.post(f"{burl}{path}", json=payload, timeout=10.0)
                if r.status_code in (200, 201):
                    body = r.json()
                    token = body.get("token") or body.get("access_token") or body.get("accessToken") or (body.get("data") or {}).get("token")
                    uid = str(body.get("id") or body.get("userId") or body.get("_id") or (body.get("user") or {}).get("id") or "")
                    if token: return token, uid
            except: continue
        return None, None

    async def _try_signup(email: str, label: str):
        for path in signup_candidates:
            payload = _get_auth_body(path, email)
            try:
                r = await client.post(f"{burl}{path}", json=payload, timeout=10.0)
                if r.status_code in (200, 201, 409):
                    if r.status_code == 409: return await _try_login(email) + (path,)
                    body = r.json()
                    token = body.get("token") or body.get("access_token") or body.get("accessToken")
                    uid = str(body.get("id") or body.get("userId") or body.get("_id") or "")
                    if token: return token, uid, path
                    tok, u = await _try_login(email)
                    return tok, u or uid, path
            except: continue
        return None, None, None

    yield json.dumps({"event": "setup_step", "step": "User A Signup", "status": "pending", "log": f"  {ICON_ARROW} Creating User A ({email_a})..."}) + "\n"
    token_a, uid_a, _ = await _try_signup(email_a, "UserA")
    ctx["token_a"] = token_a; ctx["user_id_a"] = uid_a
    yield json.dumps({"event": "setup_step", "step": "User A Ready", "status": "ok" if token_a else "fail", "log": f"  {ICON_OK if token_a else ICON_FAIL} User A ready"}) + "\n"

    if token_a:
        for rpath in resource_candidates:
            payload = _get_auth_body(rpath, email_a) # Reuse helper for generic body
            try:
                r = await client.post(f"{burl}{rpath}", json=payload, headers={"Authorization": f"Bearer {token_a}"}, timeout=10.0)
                if r.status_code in (200, 201):
                    ctx["resource_id"] = str(r.json().get("id") or "")
                    yield json.dumps({"event": "setup_step", "step": "Create Resource", "status": "ok", "log": "  \u2713 Resource created"}) + "\n"
                    break
            except: continue

    yield json.dumps({"event": "setup_step", "step": "User B Signup", "status": "pending", "log": f"  {ICON_ARROW} Creating User B ({email_b})..."}) + "\n"
    token_b, uid_b, _ = await _try_signup(email_b, "UserB")
    ctx["token_b"] = token_b; ctx["user_id_b"] = uid_b
    yield json.dumps({"event": "setup_step", "step": "User B Ready", "status": "ok" if token_b else "fail", "log": f"  {ICON_OK if token_b else ICON_FAIL} User B ready"}) + "\n"

    yield json.dumps({"event": "_setup_ctx", "ctx": ctx}) + "\n"

async def stream_security_suite(
    cases: list[dict], base_url: str, project_id: str = "", user_id: str = "system", spec: dict | None = None,
    pre_user_a_token: str | None = None, pre_user_b_token: str | None = None, pre_resource_id: str | None = None, admin_token: str | None = None,
    manual_token: str | None = None, auth_register_url: str | None = None, auth_login_url: str | None = None, auth_email: str | None = None, auth_password: str | None = None
):
    from src.modules.generator.engines.functional.services.functional_execution_service import _auth_session_setup
    executor = WorkflowExecutor()
    results = []
    category_stats = {}

    yield json.dumps({"event": "start", "total": len(cases)}) + "\n"
    
    base_url = resolve_placeholders(base_url, {"token_a": pre_user_a_token, "token_b": pre_user_b_token, "resource_id": pre_resource_id})
    
    def _normalize_token(t: str | None) -> str | None:
        if not t: return None
        t = str(t).strip()
        if t.lower().startswith("bearer "): return t[7:].strip()
        return t or None

    normalized_manual_token = _normalize_token(manual_token) or _normalize_token(admin_token)
    token_mode = bool(normalized_manual_token)
    use_auth = bool(auth_login_url and auth_email and auth_password) and not token_mode

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=False) as client:
        setup_ctx = {}
        
        if token_mode:
            setup_ctx["token_a"] = normalized_manual_token
            yield json.dumps({"event": "banner", "log": "[AUTH] Token mode active — manual token will be injected into Fuzz tests"}) + "\n"
        elif use_auth:
            yield json.dumps({"event": "session_start", "log": f"{ICON_INFO} Starting auth session for Fuzz tests..."}) + "\n"
            t_a, _ = await _auth_session_setup(client, base_url, auth_register_url or None, auth_login_url, auth_email, auth_password)
            if t_a:
                setup_ctx["token_a"] = t_a
                yield json.dumps({"event": "session_step", "step": "authenticated", "status": "ok", "log": "  [OK] JWT acquired for Fuzz testing"}) + "\n"
                yield json.dumps({"event": "context_update", "context": {"token": t_a, "auth_token": t_a}}) + "\n"
            else:
                yield json.dumps({"event": "session_step", "step": "authenticated", "status": "fail", "log": "  [FAIL] Could not acquire JWT"}) + "\n"

        if "token_a" not in setup_ctx:
            if pre_user_a_token and pre_user_b_token:
                setup_ctx = {"token_a": pre_user_a_token, "token_b": pre_user_b_token, "resource_id": pre_resource_id}
            else:
                yield json.dumps({"event": "setup_start", "log": f"{ICON_INFO} [Security Setup] Creating test users..."}) + "\n"
                async for raw_event in _stateful_setup(client, base_url, spec):
                    parsed = json.loads(raw_event)
                    if parsed.get("event") == "_setup_ctx": setup_ctx = parsed.get("ctx", {})
                    else: yield raw_event

        execution_context = setup_ctx.copy()
        def _fuzz_exec_sort(tc: dict):
            order = tc.get("execution_order", 99)
            path = tc.get("endpoint_path", "").lower()
            sub_order = 5
            if any(kw in path for kw in ("register", "signup", "sign-up")): sub_order = 0
            elif any(kw in path for kw in ("login", "signin", "sign-in")): sub_order = 1
            return (order, sub_order, path, tc.get("method", ""))
        
        cases.sort(key=_fuzz_exec_sort)

        # Banners removed for Fuzz testing as per user request
        # yield json.dumps({"event": "banner", "log": "━━━━━━━━━━━━━━━━━━━━  OWASP Security Tests Execution  ━━━━━━━━━━━━━━━━━━━━"}) + "\n"
        
        prev_category = None
        for i, case in enumerate(cases):
            cat = case.get("owasp_category", "")
            if cat != prev_category:
                # Banners removed for Fuzz testing as per user request
                # label = _CATEGORY_LABEL.get(cat, cat or "Security")
                # yield json.dumps({"event": "banner", "log": f"  {BOX_TOP_LEFT}{LINE_CHAR}{LINE_CHAR} {label} {LINE_CHAR * 40}"}) + "\n"
                prev_category = cat

            body = case.get("request_body") or case.get("body")
            if body: body = resolve_placeholders(body, execution_context)
            query = case.get("request_query") or case.get("query_params")
            if query: query = resolve_placeholders(query, execution_context)
            
            is_auth_neg = case.get("auth_negative") or case.get("kind") == "negative_auth_missing"
            is_attacker_test = case.get("owasp_category") in ("BOLA", "WrongRole")
            
            current_token = execution_context.get("token_b") if is_attacker_test else execution_context.get("token_a")
            extra_hdrs = {"Authorization": f"Bearer {current_token}"} if (current_token and not is_auth_neg) else {}

            raw_path = case.get("endpoint_path", "")
            resolved_path = resolve_placeholders(raw_path, execution_context)
            if "{" in resolved_path:
                res_id = execution_context.get("resource_id") or "00000000-0000-0000-0000-000000000001"
                resolved_path = re.sub(r"\{\w+\}", str(res_id), resolved_path)

            resolved_case = {**case, "endpoint_path": resolved_path, "request_body": body, "request_query": query}
            result = await _run_one(client, resolved_case, base_url, extra_hdrs)
            results.append(result)
            
            current_extracted = {}
            if result.get("passed") or result.get("actual_status") in (200, 201):
                try:
                    resp_data = json.loads(result.get("response_body", "{}"))
                    if isinstance(resp_data, dict):
                        token_keys = {"token", "access_token", "accessToken", "jwt", "auth_token"}
                        found_tokens = executor._deep_scan(resp_data, token_keys)
                        if found_tokens:
                            new_token = next(iter(found_tokens.values()))
                            if not is_attacker_test:
                                execution_context["token_a"] = new_token
                                current_extracted["token"] = new_token
                                current_extracted["auth_token"] = new_token
                            else:
                                execution_context["token_b"] = new_token
                                current_extracted["attacker_token"] = new_token
                        
                        for k, v in resp_data.items():
                            if (k.lower().endswith("id") or k.lower() == "_id") and isinstance(v, (str, int)):
                                execution_context[k] = str(v)
                                current_extracted[k] = str(v)
                                if k.lower() in ("id", "itemid", "_id", "resourceid"):
                                    execution_context["resource_id"] = str(v)
                except: pass

            yield json.dumps(result) + "\n"
            if current_extracted:
                yield json.dumps({"event": "context_update", "context": current_extracted}) + "\n"

            cat_key = cat or "SECURITY"
            if cat_key not in category_stats: category_stats[cat_key] = {"passed": 0, "failed": 0, "total": 0}
            category_stats[cat_key]["total"] += 1
            if result.get("passed"): category_stats[cat_key]["passed"] += 1
            else: category_stats[cat_key]["failed"] += 1

            await asyncio.sleep(0.05)

    if project_id:
        try:
            from src.services.prisma_compat import create_testrun_compat
            test_run = await create_testrun_compat(
                prisma=prisma, project_id=project_id, environment="security-scan",
                status="RUNNING", categories=["SECURITY"], total_tests=len(cases), user_id=user_id,
            )
            run_id = test_run.id
            for res in results:
                try:
                    tc_id = res.get("id")
                    if not tc_id: continue
                    tc_exists = await prisma.testcase.find_unique(where={"id": tc_id})
                    if not tc_exists:
                        tc_exists = await prisma.testcase.find_first(where={"projectId": project_id, "name": res.get("name", "")})
                    if not tc_exists: continue
                    
                    await prisma.testresult.create(data={
                        "runId": run_id, "testCaseId": tc_exists.id, "status": "PASSED" if res.get("passed") else "FAILED",
                        "category": str(tc_exists.category), "subCategory": str(tc_exists.subCategory),
                        "expected_status": res.get("expected_status", 0), "actual_status": res.get("actual_status", 0),
                        "response_time_ms": res.get("response_time_ms", 0), "error_message": res.get("error_message"),
                        "request_sent": PrismaJson(redact_request_data({"url": f"{base_url.rstrip('/')}{res.get('endpoint_path', '')}", "method": res.get("method", "")})),
                    })
                except: pass
            
            passed_count = sum(1 for r in results if r.get("passed"))
            await prisma.testrun.update(where={"id": run_id}, data={
                "status": "COMPLETED", "passed": passed_count, "failed": len(results) - passed_count,
                "completedAt": datetime.now(timezone.utc), "metadata": PrismaJson({"categorySummary": category_stats}),
            })
        except: pass

    yield json.dumps({"event": "done", "total": len(cases), "passed": sum(1 for r in results if r.get("passed"))}) + "\n"
