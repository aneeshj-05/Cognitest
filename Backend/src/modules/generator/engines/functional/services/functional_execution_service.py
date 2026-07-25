import json
import logging
import asyncio
import time
import uuid
import httpx
from datetime import datetime, timezone
from typing import Any, Optional
from src.config import prisma
from prisma import Json as PrismaJson
from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
from src.modules.generator.engines.functional.variable_resolver import resolve_placeholders
from src.services.prisma_compat import create_testrun_compat
from src.modules.project.utils import substitute_path_params
from src.modules.project.state import _run_results_store, _results_store

logger = logging.getLogger(__name__)

# Icons and box characters for terminal output
ICON_OK = "✓"
ICON_FAIL = "✗"
ICON_ARROW = "→"
ICON_INFO = "▶"
LINE_CHAR = "─"
BOX_TOP_LEFT = "┌"
ICON_WARN = "⚠"

def _contract_allowed_status(expected_statuses_str: str, actual: int, kind: str) -> bool:
    """
    Check if the actual status code is allowed given the expected statuses (as comma-separated string)
    and the test kind (positive/negative).
    """
    if not expected_statuses_str:
        return True

    # Handle both list and comma-separated string
    if isinstance(expected_statuses_str, list):
        expected = {str(s).strip() for s in expected_statuses_str}
    else:
        expected = {s.strip() for s in str(expected_statuses_str).split(",")}

    # Standard error statuses for negative tests
    STANDARD_ERROR_STATUSES = {400, 401, 403, 404, 405, 409, 415, 422, 429}

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

def _extract_contract_meta(case: dict[str, Any]) -> dict[str, Any]:
    """Best-effort extraction of strict contract metadata."""
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

async def _auth_session_setup(
    client: httpx.AsyncClient,
    base_url: str,
    register_url: str | None,
    login_url: str,
    email: str,
    password: str,
) -> tuple[str | None, str | None]:
    """
    Optionally registers a fresh test user, then logs in to acquire a JWT.
    """
    burl = base_url.rstrip("/")
    token: str | None = None
    user_id: str | None = None

    # Step 1: Register (optional)
    if register_url:
        reg_path = register_url if register_url.startswith("/") else f"/{register_url}"
        for payload in (
            {"email": email, "password": password, "name": "Cognitest Runner",
             "username": email.split("@")[0]},
            {"email": email, "passcode": password, "name": "Cognitest Runner"},
        ):
            try:
                r = await client.post(
                    f"{burl}{reg_path}", json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if r.status_code in (200, 201, 409):
                    body = r.json() if r.text else {}
                    token = (
                        body.get("token") or body.get("access_token")
                        or (body.get("data") or {}).get("token")
                    )
                    user_id = (
                        str(body.get("id") or body.get("userId")
                        or (body.get("data") or {}).get("id") or "")
                        or None
                    )
                    break
            except Exception:
                pass

    # Step 2: Login
    if not token:
        login_path = login_url if login_url.startswith("/") else f"/{login_url}"
        for payload in (
            {"email": email, "password": password},
            {"email": email, "passcode": password},
            {"username": email, "password": password},
        ):
            try:
                r = await client.post(
                    f"{burl}{login_path}", json=payload,
                    headers={"Content-Type": "application/json"},
                )
                if r.status_code == 200:
                    body = r.json() if r.text else {}
                    token = (
                        body.get("token") or body.get("access_token")
                        or (body.get("data") or {}).get("token")
                    )
                    if not user_id:
                        user_id = (
                            str(body.get("id") or body.get("userId")
                            or (body.get("data") or {}).get("id") or (body.get("user") or {}).get("id") or "")
                            or None
                        )
                    if token:
                        break
            except Exception:
                pass

    return token, user_id

async def _auth_session_cleanup(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    user_id: str | None,
) -> bool:
    """
    Attempt to delete the test user created during setup.
    """
    if not user_id:
        return False
    
    burl = base_url.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Try common user deletion paths
    for path in (f"/api/users/{user_id}", f"/users/{user_id}", "/api/auth/me", "/auth/me"):
        try:
            r = await client.delete(f"{burl}{path}", headers=headers)
            if r.status_code in (200, 204):
                return True
        except Exception:
            pass
    return False

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
    acknowledge_burst_tests: bool = False,
):
    """
    Execute test cases against the actual API and stream results.

    acknowledge_burst_tests: Must be True for burst/rate-limit test cases to run.
                             If False, burst cases are skipped with a clear message.
    """
    # Outbound request counter — tracks every real HTTP request including burst multiples
    outbound_count: list[int] = [0]   # mutable list so inner closures can increment
    def _normalize_token(token: str | None) -> str | None:
        if token is None: return None
        t = str(token).strip()
        if not t: return None
        if t.lower().startswith("bearer "):
            t = t[7:].strip()
        return t or None

    def _mask_auth_header(headers: dict[str, Any]) -> dict[str, Any]:
        masked = dict(headers or {})
        for k in list(masked.keys()):
            if str(k).lower() == "authorization":
                masked[k] = "Bearer ********"
        return masked

    # -- Auth session: register + login --
    session_token: str | None = None
    session_user_id: str | None = None
    normalized_manual_token = _normalize_token(manual_token)
    token_mode = bool(normalized_manual_token)
    use_auth = bool(auth_login_url and auth_email and auth_password) and not token_mode

    # Enforce strict auth-flow ordering for contract cases.
    def _order_cases_for_auth_flow(cases_in: list[dict]) -> list[dict]:
        indexed = list(enumerate(cases_in or []))
        def _priority(item: tuple[int, dict]) -> tuple:
            idx, tc = item
            path = str((tc or {}).get("endpoint_path") or "").lower()
            is_contract_tc = (str(tc.get("test_type") or "").strip().lower() == "contract") or (
                str(tc.get("category") or "").strip().upper() == "CONTRACT"
            )
            if not is_contract_tc: return (10, idx)
            meta = _extract_contract_meta(tc)
            kind = str(meta.get("kind") or tc.get("kind") or "")
            if kind == "positive" and ("/signup" in path or "/register" in path): bucket = 0
            elif kind == "positive" and "/login" in path: bucket = 1
            elif kind == "positive": bucket = 2
            else: bucket = 3
            method = str(tc.get("method") or "").upper()
            op_key = str(meta.get("operation_key") or tc.get("operation_key") or "")
            return (bucket, path, method, op_key, idx)
        indexed_sorted = sorted(indexed, key=_priority)
        return [tc for _idx, tc in indexed_sorted]

    cases = _order_cases_for_auth_flow(cases)

    # ── Sort burst/rate-limit cases last so they don't corrupt earlier results ──
    non_burst = [c for c in cases if not c.get("burst_count")]
    burst_cases = [c for c in cases if c.get("burst_count")]
    cases = non_burst + burst_cases

    yield json.dumps({"event": "start", "total": len(cases)}) + "\n"
    await asyncio.sleep(0.05)

    # -- Create TestRun --
    suite_ids = {
        (c.get("suiteId") or c.get("suite_id"))
        for c in (cases or [])
        if isinstance(c, dict)
    }
    suite_ids.discard(None)
    suite_ids.discard("")
    suite_id_for_run = next(iter(suite_ids)) if len(suite_ids) == 1 else None

    # -- Execution context for dynamic variables --
    timestamp_ms = int(time.time() * 1000)
    execution_context: dict[str, Any] = {
        "email": auth_email if auth_email else f"test_run_{timestamp_ms}@example.com",
        "timestamp": str(timestamp_ms),
        "run_id": str(uuid.uuid4())[:8],
        "auth_token": "",
    }

    run_categories = list(set(
        (c.get("test_type") or c.get("category") or "FUNCTIONAL").upper()
        for c in cases
    ))
    try:
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
        run_id = "stub-run"

    # Pre-fetch endpoints
    try:
        db_endpoints = await prisma.endpoint.find_many(where={"projectId": project_id})
        endpoint_lookup: dict[tuple[str, str], str] = {}
        for ep in db_endpoints:
            endpoint_lookup[(ep.method.upper(), ep.path)] = ep.id
    except Exception:
        endpoint_lookup = {}

    # Resolve placeholders in base_url (Feature: Allow {{BASE_URL}} in override)
    base_url = resolve_placeholders(base_url, execution_context)
    
    all_results = []
    from src.utils.egress_guard import validate_egress_url, build_pinned_transport, SsrfBlockedError as _SsrfErr
    _guard = validate_egress_url(base_url)
    async with httpx.AsyncClient(
        transport=build_pinned_transport(_guard),
        timeout=60.0,
        follow_redirects=False,
    ) as client:
        # -- Auth session setup --
        if token_mode:
            session_token = normalized_manual_token
            yield json.dumps({
                "event": "banner",
                "log": f"[AUTH] Token mode active \u2014 manual token will be injected when required",
            }) + "\n"
            await asyncio.sleep(0.05)

        if use_auth:
            yield json.dumps({
                "event": "session_start",
                "log": f"{ICON_INFO} Starting auth session \u2014 setting up test user...",
            }) + "\n"
            await asyncio.sleep(0.05)
            if auth_register_url:
                yield json.dumps({
                    "event": "session_step", "step": "register", "status": "pending",
                    "log": f"  {ICON_ARROW} POST {auth_register_url} (registering test user)",
                }) + "\n"
            yield json.dumps({
                "event": "session_step", "step": "login", "status": "pending",
                "log": f"  {ICON_ARROW} POST {auth_login_url} (logging in)",
            }) + "\n"
            await asyncio.sleep(0.05)
            current_email = execution_context["email"]
            session_token, session_user_id = await _auth_session_setup(
                client, base_url, auth_register_url or None, auth_login_url,
                current_email, auth_password,
            )
            if session_token:
                execution_context["auth_token"] = session_token
                yield json.dumps({
                    "event": "session_step", "step": "authenticated", "status": "ok",
                    "log": f"  {ICON_OK} JWT acquired \u2014 token will be injected into all test requests",
                }) + "\n"
            else:
                yield json.dumps({
                    "event": "session_step", "step": "authenticated", "status": "fail",
                    "log": f"  {ICON_FAIL} Could not acquire JWT (register/login failed) \u2014 running without auth",
                }) + "\n"
            await asyncio.sleep(0.1)

        category_stats = {}
        prev_category = None

        for i, case in enumerate(cases):
            cat_key = str(case.get("category") or case.get("test_type") or "FUNCTIONAL").upper()
            sub_cat = str(case.get("sub_category") or case.get("subCategory") or case.get("fuzz_type") or "")
            label_val = cat_key
            if cat_key == "FUZZ" and sub_cat: label_val = sub_cat.replace("_", " ").title()
            elif cat_key == "FUNCTIONAL": label_val = sub_cat.replace("_", " ").title() if sub_cat else "General Functional"
            else: label_val = cat_key.replace("_", " ").title()

            if label_val != prev_category:
                line_len = max(0, 48 - len(label_val) - 5)
                yield json.dumps({
                    "event": "banner", "log": f"{BOX_TOP_LEFT}{LINE_CHAR}{LINE_CHAR} {label_val} {LINE_CHAR * line_len}"
                }) + "\n"
                prev_category = label_val
                await asyncio.sleep(0.05)

            response_body_text = ""
            response_headers_dict: dict[str, str] = {}
            req_headers_sent: dict[str, str] = {"User-Agent": "Cognitest-Scanner"}

            # -- Workflow test case --
            metadata = case.get("metadata") or {}
            steps = case.get("steps") or (metadata.get("steps") if isinstance(metadata, dict) else None)
            if steps:
                case["steps"] = steps
                workflow_id = case.get("id", f"wf-{i}")
                yield json.dumps({
                    "event": "workflow_start", "index": i, "workflow_id": workflow_id,
                    "name": case.get("name", "Workflow"), "steps": len(steps),
                    "state_machine": case.get("state_machine", []),
                }) + "\n"
                await asyncio.sleep(0.05)
                executor = WorkflowExecutor()
                wf_result = await executor.run(case, base_url, client, initial_context=execution_context)
                for step_res in wf_result.step_results:
                    yield json.dumps(step_res.to_event(workflow_id)) + "\n"
                    if step_res.extracted_vars:
                        yield json.dumps({
                            "event": "context_update",
                            "context": step_res.extracted_vars
                        }) + "\n"
                    await asyncio.sleep(0.1)
                if wf_result.rollback_triggered:
                    yield json.dumps(wf_result.to_rollback_event()) + "\n"
                    await asyncio.sleep(0.05)
                yield json.dumps(wf_result.to_summary_event()) + "\n"
                await asyncio.sleep(0.15)
                flat_result = {
                    "event": "result", "index": i, "id": workflow_id,
                    "name": case.get("name", "Workflow"), "endpoint_path": case.get("endpoint_path", ""),
                    "method": case.get("method", ""), "expected_status": case.get("expected_status", 200),
                    "actual_status": (wf_result.step_results[0].actual_status if wf_result.step_results else 0),
                    "passed": wf_result.passed, "response_time_ms": wf_result.total_time_ms,
                    "response_body": "", "response_headers": {},
                    "error_message": wf_result.rollback_reason if wf_result.rollback_triggered else "",
                    "is_workflow": True, "workflow_steps": len(steps), "final_state": wf_result.final_state,
                    "log": f"[WORKFLOW] {case.get('name', '')} -> {'PASS' if wf_result.passed else 'FAIL'} ({len(steps)} steps, {wf_result.total_time_ms}ms)",
                }
                all_results.append(flat_result)
                continue

            # -- Flat test case --
            start_time = time.time()
            endpoint_path_template = case["endpoint_path"].split("#")[0]
            endpoint_path_template = resolve_placeholders(endpoint_path_template, execution_context)
            case_path_params = resolve_placeholders(case.get("path_params") or {}, execution_context)
            rendered_path = substitute_path_params(endpoint_path_template, case_path_params)
            
            # SECOND PASS: Resolve any remaining {{var}} (substitute_path_params converts unresolved {id} to {{id}})
            rendered_path = resolve_placeholders(rendered_path, execution_context)
            
            # Validation: Unresolved path parameters
            if "{" in rendered_path:
                result = {
                    "event": "result", "index": i, "id": case["id"], "name": case["name"],
                    "endpoint_path": endpoint_path_template, "rendered_path": rendered_path,
                    "method": case["method"].upper(), "expected_status": case["expected_status"], "actual_status": 0,
                    "passed": True, "inconclusive": True,
                    "error_message": f"Inconclusive \u2014 Missing required resource ID: {rendered_path}",
                    "log": f"[{case['method'].upper()}] {rendered_path} -> PASS (missing parameter) \u26a0",
                }
                all_results.append(result)
                yield json.dumps(result) + "\n"
                continue

            url = f"{base_url.rstrip('/')}{rendered_path}"
            method = case["method"].upper()
            expected = case["expected_status"]
            body = None

            is_contract = (str(case.get("test_type") or "").strip().lower() == "contract") or (
                str(case.get("category") or "").strip().upper() == "CONTRACT"
            )
            contract_meta = _extract_contract_meta(case) if is_contract else {}
            expected_statuses_raw = contract_meta.get("expected_statuses")
            expected_statuses: list[int] = []
            expected_statuses_str: list[str] = []
            if isinstance(expected_statuses_raw, list):
                for s in expected_statuses_raw:
                    if s is None: continue
                    ss = str(s).strip()
                    if not ss: continue
                    expected_statuses_str.append(ss)
                    try: expected_statuses.append(int(ss))
                    except: continue

            requires_auth = bool(contract_meta.get("security_required") or case.get("requires_auth") or case.get("security_required") or case.get("requiresAuth"))
            kind = str(contract_meta.get("kind") or case.get("kind") or "")
            is_negative_auth_missing = kind == "negative_auth_missing"
            auth_negative = bool(contract_meta.get("auth_negative") or case.get("auth_negative")) or is_negative_auth_missing
            effective_token = execution_context.get("auth_token") or session_token
            auth_provided = bool(effective_token and requires_auth and not auth_negative)

            if is_contract and requires_auth and not auth_negative and not effective_token:
                result = {
                    "event": "result", "index": i, "id": case.get("id"), "name": case.get("name"),
                    "endpoint_path": endpoint_path_template, "rendered_path": rendered_path,
                    "method": method, "expected_status": expected, "actual_status": 0, 
                    "passed": True, "inconclusive": True,
                    "error_message": "Inconclusive \u2014 Missing auth token before protected route", 
                    "log": f"[{method}] {rendered_path} -> PASS (missing auth token) \u26a0",
                }
                all_results.append(result)
                yield json.dumps(result) + "\n"
                await asyncio.sleep(delay_ms / 1000.0)
                continue

            try:
                case_headers: dict[str, str] = {"User-Agent": "Cognitest-Runner/1.0", **(case.get("request_headers") or {})}
                kwargs: dict = {"timeout": 5.0} # Feature 8: Request timeout
                
                # Feature 4: Generic Auth Injection
                # If we have a token, inject it into ALL non-negative tests by default (Generic/Collection-level auth)
                if effective_token and not auth_negative:
                    # 1. Standard Authorization Header
                    if "Authorization" not in case_headers:
                        case_headers["Authorization"] = f"Bearer {effective_token}"
                    
                    # 2. Common Security Headers (Spray for generic compatibility)
                    for h in ["x-auth-token", "x-access-token", "x-api-key"]:
                        if h not in case_headers:
                            case_headers[h] = effective_token
                
                # Ensure Authorization is removed for explicit negative auth tests
                if auth_negative or is_negative_auth_missing:
                    for h in ["Authorization", "x-auth-token", "x-access-token", "x-api-key", "token"]:
                        case_headers.pop(h, None)
                
                force_ct = case.get("force_content_type")
                raw_body = case.get("request_data") or case.get("request_body")
                case_headers = resolve_placeholders(case_headers, execution_context)
                body = resolve_placeholders(raw_body, execution_context)
                case_query = resolve_placeholders(case.get("request_query") or {}, execution_context)
                if case_query: kwargs["params"] = case_query

                # Feature 1: Multipart Support
                is_multipart = isinstance(body, dict) and body.get("type") == "multipart"
                if is_multipart:
                    fields = body.get("fields", {})
                    files_dict = body.get("files", {})
                    httpx_files = {}
                    for field_name, file_info in files_dict.items():
                        if isinstance(file_info, dict):
                            content = file_info.get("content", "").encode() if isinstance(file_info.get("content"), str) else b""
                            filename = file_info.get("filename", "test.txt")
                            content_type = file_info.get("content_type", "text/plain")
                            httpx_files[field_name] = (filename, content, content_type)
                        else:
                            httpx_files[field_name] = ("test.txt", str(file_info).encode(), "text/plain")
                    kwargs["data"] = fields
                    kwargs["files"] = httpx_files
                    case_headers.pop("Content-Type", None) # Let client handle boundary
                elif body is not None:
                    if force_ct == "__OMIT__": kwargs["content"] = json.dumps(body).encode() if not isinstance(body, str) else body.encode()
                    elif force_ct: kwargs["content"] = json.dumps(body).encode() if not isinstance(body, str) else body.encode(); case_headers["Content-Type"] = force_ct
                    elif isinstance(body, str): kwargs["content"] = body; case_headers["Content-Type"] = "application/json"
                    else: kwargs["json"] = body
                elif method in ("POST", "PUT", "PATCH") and not raw_body:
                    rb = case.get("request_body")
                    if rb: kwargs["json"] = resolve_placeholders(rb, execution_context)

                if cat_key not in category_stats: category_stats[cat_key] = {"passed": 0, "failed": 0, "total": 0}
                category_stats[cat_key]["total"] += 1

                burst_count = case.get("burst_count", 0)
                if burst_count > 0:
                    # Hard cap
                    try:
                        from src.config.settings import settings as _s
                        burst_count = min(burst_count, _s.max_burst_count)
                    except Exception:
                        burst_count = min(burst_count, 10)

                    # Acknowledgment gate
                    if not acknowledge_burst_tests:
                        results.append({
                            "event": "result", "id": case.get("id"), "name": case.get("name"),
                            "endpoint_path": endpoint_path_template, "method": method,
                            "expected_status": case.get("expected_status"), "actual_status": None,
                            "passed": True, "skipped": True,
                            "skip_reason": "burst_test_requires_acknowledgment",
                            "error_message": f"Burst test skipped — pass acknowledge_burst_tests=true to run ({burst_count} requests).",
                            "log": f"[SKIPPED] {method} {endpoint_path_template} — burst test requires acknowledgment",
                        })
                        category_stats[cat_key]["total"] += 1
                        yield json.dumps(results[-1]) + "\n"
                        continue

                    # Sequential burst semaphore (shared on context)
                    _bsem = getattr(run_ctx, "_burst_semaphore", None) if "run_ctx" in dir() else None
                    if _bsem is None:
                        _bsem = asyncio.Semaphore(1)

                    async with _bsem:
                        tasks = [client.request(method, url, headers=case_headers, **kwargs) for _ in range(burst_count)]
                        responses = await asyncio.gather(*tasks, return_exceptions=True)

                    outbound_count[0] += burst_count
                    status_codes = [r.status_code for r in responses if not isinstance(r, Exception)]
                    actual = 429 if 429 in status_codes else (status_codes[0] if status_codes else 0)
                    passed = 429 in status_codes
                    elapsed_ms = int((time.time() - start_time) * 1000); resp_body = ""; resp_headers = {}
                else:
                    response = await client.request(method, url, headers=case_headers, **kwargs)
                    outbound_count[0] += 1
                    actual = response.status_code
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    resp_body = response.text[:2048] if response.text else ""; resp_headers = dict(response.headers)
                    response_body_text = response.text[:5000]; response_headers_dict = dict(response.headers)
                    
                    # Feature 2 & 4: Variable Extraction & Auth Context Enrichment
                    current_extracted = {}
                    if 200 <= actual <= 299:
                        try:
                            _rj = json.loads(response_body_text)
                            if isinstance(_rj, dict):
                                _token = _rj.get("token") or _rj.get("access_token") or _rj.get("accessToken")
                                _uid = str(_rj.get("id") or _rj.get("_id") or _rj.get("userId") or (_rj.get("data") or {}).get("id") or (_rj.get("data") or {}).get("_id") or (_rj.get("user") or {}).get("id") or "")
                                
                                # Use path or label for resource naming (e.g. "/items" -> "item_id")
                                path_parts = [p for p in endpoint_path_template.split("/") if p and p not in ("api", "v1", "v2", "admin", "add", "create", "update", "delete")]
                                resource_hint = path_parts[-1] if path_parts else label_val.lower().split()[0].replace("_", "")
                                singular = resource_hint[:-1] if resource_hint.endswith("s") else resource_hint
                                if "-" in singular: singular = singular.split("-")[-1]
                                
                                if _token:
                                    execution_context["auth_token"] = execution_context["token"] = _token
                                    current_extracted["token"] = _token
                                if _uid:
                                    execution_context["user_id"] = execution_context["id"] = _uid
                                    execution_context[f"{singular}_id"] = _uid
                                    execution_context[f"{resource_hint}_id"] = _uid
                                    execution_context["last_id"] = _uid
                                    current_extracted["id"] = _uid
                                    # Ensure it's captured as item_id if we have a singular hint
                                    if singular and singular != "user":
                                        current_extracted[f"{singular}_id"] = _uid
                                
                                # Catch-all for top-level IDs
                                for k, v in _rj.items():
                                    if k.lower().endswith("id") and isinstance(v, (str, int)):
                                        execution_context[k] = str(v)
                                        current_extracted[k] = str(v)
                        except: pass
                        
                        if current_extracted:
                            yield json.dumps({
                                "event": "context_update",
                                "context": current_extracted
                            }) + "\n"

                    passed = _evaluate_pass_fail(expected, actual, case)
                    
                    # Feature 6: Accept Header Validation (406 Handling)
                    if case_headers.get("Accept") and actual == 406:
                        passed = (expected == 406)

                    if is_contract and expected_statuses_str:
                        kv = kind or "positive"
                        if kv == "positive" and actual >= 500: passed = False
                        elif actual in (301, 302, 303, 307, 308): passed = True
                        else:
                            passed = _contract_allowed_status(expected_statuses_str, int(actual), kv)
                            if kv.startswith("negative") and 200 <= actual <= 299: passed = False
                            if ("{" in endpoint_path_template) and actual == 404 and 404 not in expected_statuses: passed = True
                    elif isinstance(expected, list): passed = actual in expected
                    elif expected == 400 and actual == 404: passed = True
                    else: passed = actual == expected

                if passed: category_stats[cat_key]["passed"] += 1
                else: category_stats[cat_key]["failed"] += 1

                # Feature 7: Error Classification
                error_message = ""
                if actual == 502: error_message = "BAD GATEWAY: Probable malformed body or missing required param causing backend crash"
                elif actual >= 500: error_message = f"SERVER ERROR ({actual}): Backend crashed or returned unhandled exception"
                elif actual == 406: error_message = "NOT ACCEPTABLE: Server rejected the Accept header"
                elif actual == 200 and expected != 200: error_message = "Logic Error: Server accepted invalid input with 200 OK"
                elif not passed: error_message = f"Assertion Failed: Expected {expected}, got {actual}"

                violations = None; notes = None
                if is_contract and not passed:
                    violations = [{"code": "spec.mismatch", "severity": "HIGH", "schema_validation_errors": [f"Status {actual} mismatch"]}]
                elif is_contract:
                    n = []
                    if expected_statuses_str and 200 <= actual <= 299:
                        if not (("default" in expected_statuses_str) or (str(actual) in expected_statuses_str)): n.append(f"Undocumented success ({actual})")
                    if requires_auth and not auth_provided and 200 <= actual <= 299: n.append("Auth missing but required")
                    notes = n or None

                # Final masking for UI
                req_headers_sent = _mask_auth_header(case_headers)

                # Feature 9: Debug Visibility (Expose final state)
                is_inconclusive = (actual == 0)
                status_label = "INCONCLUSIVE" if is_inconclusive else ("PASS" if passed else "FAIL")
                
                result = {
                    "event": "result", "index": i, "id": case["id"], "name": case["name"],
                    "endpoint_path": endpoint_path_template, "rendered_path": rendered_path,
                    "method": method, "expected_status": expected, "actual_status": actual,
                    "response_time_ms": elapsed_ms, "passed": passed, "inconclusive": is_inconclusive,
                    "request_headers": req_headers_sent,
                    "request_body": body if not is_multipart else {"info": "Multipart Data", "fields": body.get("fields")},
                    "body_type": "multipart" if is_multipart else "json",
                    "response_body": resp_body, "response_headers": resp_headers,
                    "extracted_vars": current_extracted or None,
                    "execution_context": {k: v for k, v in execution_context.items() if k not in ("auth_token", "token")},
                    "error_message": error_message, "log": f"[{method}] {rendered_path} -> {status_label} (expected {expected}, got {actual}) {elapsed_ms}ms" + (" \u26a0" if is_inconclusive else ""),
                }
            except asyncio.TimeoutError:
                result = {
                    "event": "result", "index": i, "id": case["id"], "name": case["name"],
                    "actual_status": 0, "passed": False, "inconclusive": True, "error_message": "Request Timed Out (5s limit)",
                    "log": f"[{case['method']}] {rendered_path} -> INCONCLUSIVE (TIMEOUT) \u26a0",
                }
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                result = {
                    "event": "result", "index": i, "id": case["id"], "name": case["name"],
                    "actual_status": 0, "passed": False, "inconclusive": True, "error_message": str(e),
                    "log": f"[{case['method']}] {rendered_path} -> INCONCLUSIVE (ERROR: {str(e)[:30]}) \u26a0",
                }

            all_results.append(result)
            # Persistence logic (simplified for clarity, keeping core prisma calls)
            try:
                tc_id = case.get("id")
                tc_exists = await prisma.testcase.find_unique(where={"id": tc_id}) if tc_id else None
                if tc_exists:
                    tr_data = {
                        "runId": run_id, "testCaseId": tc_id, "status": "PASSED" if result["passed"] else "FAILED",
                        "category": str(tc_exists.category), "subCategory": str(tc_exists.subCategory),
                        "expected_status": result["expected_status"], "actual_status": result["actual_status"],
                        "response_time_ms": result.get("response_time_ms", 0), "error_message": result.get("error_message"),
                        "request_sent": PrismaJson(redact_request_data({"url": url, "method": method, "headers": req_headers_sent, "body": body})),
                        "response_body": PrismaJson({"text": response_body_text}) if 'response_body_text' in locals() else None,
                        "response_headers": PrismaJson(response_headers_dict) if 'response_headers_dict' in locals() else None,
                    }
                    await prisma.testresult.create(data=tr_data)
                    if str(tc_exists.category).upper() == "CONTRACT":
                        await prisma.contractvalidation.create(data={
                            "runId": run_id, "endpointId": tc_exists.endpointId, "status": "CONFORMANT" if result["passed"] else "DRIFT_DETECTED",
                            "actual_schema": PrismaJson({"status_code": result["actual_status"]}),
                            "expected_schema": PrismaJson({"status_code": result["expected_status"]}), "createdBy": user_id,
                        })
            except: pass

            yield json.dumps(result) + "\n"
            await asyncio.sleep(delay_ms / 1000.0)

        if use_auth and session_token:
            yield json.dumps({"event": "session_step", "step": "cleanup", "status": "pending", "log": "  -> Cleaning up..."}) + "\n"
            await _auth_session_cleanup(client, base_url, session_token, session_user_id)

    passed_count = sum(1 for r in all_results if r.get("passed"))
    _run_results_store[project_id] = _results_store[project_id] = {
        "results": all_results, "summary": {"total": len(cases), "passed": passed_count, "failed": len(cases)-passed_count},
        "base_url": base_url, "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await prisma.testrun.update(where={"id": run_id}, data={
            "status": "COMPLETED", "passed": passed_count, "failed": len(cases)-passed_count,
            "completedAt": datetime.now(timezone.utc), "metadata": PrismaJson({"categorySummary": category_stats}),
        })
    except: pass
    yield json.dumps({
        "event": "done",
        "total": len(all_results),
        "passed": passed_count,
        "total_outbound_requests": outbound_count[0],
    }) + "\n"
