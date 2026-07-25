"""
Fuzz testing pipeline service — isolated for modularity.
"""
import json
import logging
import random
import string
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from src.config import prisma
from prisma import Json as PrismaJson

from ...spec_parser import extract_endpoints
from .runner import run_fuzz_native
from .engine import generate_fuzz_tests

logger = logging.getLogger(__name__)


# ── Minimal execution context (replaces deleted ExecutionContext class) ────────

@dataclass
class _FuzzContext:
    email: Optional[str] = None
    password: Optional[str] = None
    bearer_token: Optional[str] = None
    user_id: Optional[str] = None

    def generate_credentials(self) -> tuple[str, str]:
        from src.modules.generator.services.data_provider import data_provider
        self.email = data_provider.generate_email(prefix="fuzz", domain="example.com")
        self.password = data_provider.generate_password()
        return self.email, self.password


async def _bootstrap_auth(spec: dict, base_url: str) -> _FuzzContext:
    """
    Attempt signup → login against the target API using paths discovered from
    the spec. Returns a context with bearer_token populated on success.
    """
    ctx = _FuzzContext()

    # Only attempt auth if the spec declares bearerAuth
    schemes = spec.get("components", {}).get("securitySchemes", {})
    has_bearer = any(
        s.get("type") == "http" and s.get("scheme") == "bearer"
        for s in schemes.values()
    )
    if not has_bearer:
        return ctx

    signup_kw = {"signup", "register", "create"}
    login_kw = {"login", "signin", "auth", "token"}
    signup_eps, login_eps = [], []

    for path, methods in (spec.get("paths") or {}).items():
        if "post" not in methods:
            continue
        op = methods["post"]
        tags = [t.lower() for t in op.get("tags", [])]
        pl = path.lower()
        is_auth_tag = "authentication" in tags
        if (is_auth_tag or any(k in pl for k in signup_kw)):
            signup_eps.append({"path": path, "operation": op})
        elif (is_auth_tag or any(k in pl for k in login_kw)):
            login_eps.append({"path": path, "operation": op})

    if not login_eps:
        return ctx

    burl = base_url.rstrip("/")
    email, password = ctx.generate_credentials()

    def _build_payload(op: dict) -> dict:
        from src.modules.generator.services.data_provider import data_provider
        props = (
            op.get("requestBody", {})
            .get("content", {})
            .get("application/json", {})
            .get("schema", {})
            .get("properties", {})
        )
        payload: dict = {}
        for name, prop in props.items():
            # Use the robust data provider to generate valid sample data
            val = data_provider.get_sample_value(name, prop.get("type", "string"), prop)
            
            # Ensure our newly generated credentials are used for email/password fields
            nl = name.lower()
            if "email" in nl:
                val = email
            elif "pass" in nl:
                val = password
            elif "user" in nl and "@" not in str(val):
                val = email.split("@")[0]
            
            payload[name] = val
        return payload
    return await _execute_auth_chain(ctx, signup_eps, login_eps, burl, _build_payload)


async def _execute_auth_chain(ctx, signup_eps, login_eps, burl, _build_payload):
    """Helper to execute the signup -> login sequence."""
    from src.utils.egress_guard import validate_egress_url, build_pinned_transport
    _guard = validate_egress_url(burl)
    async with httpx.AsyncClient(
        transport=build_pinned_transport(_guard),
        timeout=15.0,
    ) as client:
        # Signup (best-effort)
        if signup_eps:
            ep = signup_eps[0]
            try:
                payload = _build_payload(ep["operation"])
                r = await client.post(
                    f"{burl}{ep['path']}", json=payload
                )
                logger.info("[Fuzz auth] signup %s -> %d", ep["path"], r.status_code)
                # If signup returns a token, grab it
                if r.status_code in (200, 201):
                    body = r.json()
                    # Recursive search for token
                    from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
                    executor = WorkflowExecutor()
                    found = executor._deep_scan(body, {"token", "access_token", "accessToken", "jwt", "auth_token", "id_token", "bearer"})
                    if found:
                        ctx.bearer_token = next(iter(found.values()))
                        logger.info("[Fuzz auth] token acquired from signup")
            except Exception as exc:
                logger.warning("[Fuzz auth] signup failed: %s", exc)

        # Login (if we don't have a token yet)
        if not ctx.bearer_token and login_eps:
            ep = login_eps[0]
            try:
                payload = _build_payload(ep["operation"])
                r = await client.post(
                    f"{burl}{ep['path']}", json=payload
                )
                logger.info("[Fuzz auth] login %s -> %d", ep["path"], r.status_code)
                if r.status_code == 200:
                    body = r.json()
                    from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
                    executor = WorkflowExecutor()
                    found = executor._deep_scan(body, {"token", "access_token", "accessToken", "jwt", "auth_token", "id_token", "bearer"})
                    if found:
                        ctx.bearer_token = next(iter(found.values()))
                        logger.info("[Fuzz auth] token acquired from login")
            except Exception as exc:
                logger.warning("[Fuzz auth] login failed: %s", exc)

    return ctx


async def _ensure_endpoints_exist(
    project_id: str, spec_id: str, spec_dict: dict
) -> dict[tuple[str, str], str]:
    """
    Ensure Endpoint records exist in DB for this project/spec.
    Returns a lookup dict: (METHOD, path) → endpoint_id.
    """
    existing = await prisma.endpoint.find_many(
        where={"projectId": project_id}
    )
    lookup: dict[tuple[str, str], str] = {}
    for ep in existing:
        lookup[(ep.method.upper(), ep.path)] = ep.id

    if not lookup:
        # Parse spec and create endpoints
        parsed = extract_endpoints(spec_dict)
        for ep in parsed:
            try:
                record = await prisma.endpoint.create(
                    data={
                        "projectId": project_id,
                        "specId": spec_id,
                        "method": ep.method,
                        "path": ep.path,
                        "requiresAuth": ep.requires_auth,
                        "requestSchema": json.dumps(ep.body_schema) if ep.body_schema else None,
                        "responseSchema": json.dumps(ep.response_schema) if ep.response_schema else None,
                    }
                )
                lookup[(ep.method.upper(), ep.path)] = record.id
            except Exception as exc:
                logger.warning("Failed to create endpoint %s %s: %s", ep.method, ep.path, exc)
        logger.info("Created %d Endpoint records for project %s", len(lookup), project_id)

    return lookup


def _find_endpoint_id(
    method: str, path: str, lookup: dict[tuple[str, str], str], fallback_id: str | None
) -> str | None:
    """Find endpoint by method+path, then by path only, then use fallback."""
    ep_id = lookup.get((method.upper(), path))
    if ep_id:
        return ep_id
    # Try path-only match
    for (_, ep_path), eid in lookup.items():
        if ep_path == path:
            return eid
    return fallback_id


async def run_fuzz_pipeline(
    project_id: str,
    spec_id: str,
    triggered_by: str,
    base_url: str | None = None,
    execute: bool = True,
    use_ai: bool = False,
) -> dict[str, Any]:
    """
    Full fuzz testing pipeline:
      1. Fetch spec from DB
      2. Ensure Endpoint records exist
      3. Generate fuzz test cases via AI
      4. Create TestCase records in DB
      5. Create TestRun
      6. (If execute) Run via Newman
      7. Store TestResult + FuzzResult
      8. Return structured response
    """
    # ── 1. Fetch the spec from DB ──
    api_spec = await prisma.apispec.find_unique(where={"id": spec_id})
    if not api_spec:
        raise ValueError(f"API spec {spec_id} not found")

    project = await prisma.project.find_unique(where={"id": project_id})
    if not project:
        raise ValueError(f"Project {project_id} not found")

    target_base_url = base_url or project.baseUrl or "http://localhost:5000"

    # Parse the spec
    spec_dict = None
    if api_spec.parsed_spec:
        spec_dict = api_spec.parsed_spec if isinstance(api_spec.parsed_spec, dict) else json.loads(api_spec.parsed_spec)
    else:
        logger.warning("No parsed_spec cached for spec %s", spec_id)
        spec_dict = {}

    # ── 1.5. Bootstrap auth from spec (acquire JWT if bearerAuth is defined) ──
    context = await _bootstrap_auth(spec_dict, target_base_url)

    # ── 2. Ensure Endpoint records exist ──
    endpoint_lookup = await _ensure_endpoints_exist(project_id, spec_id, spec_dict)
    fallback_ep_id = next(iter(endpoint_lookup.values()), None) if endpoint_lookup else None

    # ── 3. Generate fuzz test cases (organized into TestPlan) ──
    logger.info("Generating fuzz test plan for project %s, spec %s (AI=%s)", project_id, spec_id, use_ai)
    test_plan = await generate_fuzz_tests(spec_dict, use_ai=use_ai) 
    
    all_test_cases = test_plan["public_tests"] + test_plan["protected_tests"]

    if not all_test_cases:
        return {
            "test_cases": [],
            "findings": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "crashed": 0, "anomalies_detected": 0},
            "run_id": None,
            "executed": False,
        }

    # ── 4. Create TestCase records ──
    for tc in all_test_cases:
        try:
            method = tc.get("method", "GET").upper()
            path = tc.get("endpoint_path", "/").replace("{{", "{").replace("}}", "}") # Normalize for DB
            endpoint_id = _find_endpoint_id(method, path, endpoint_lookup, fallback_ep_id)
            if not endpoint_id: continue

            tc_data = {
                    "id": tc["id"],
                    "projectId": project_id,
                    "endpointId": endpoint_id,
                    "name": tc["name"],
                    "description": tc.get("description", ""),
                    "category": "FUZZ",
                    "subCategory": tc.get("fuzz_type", "RANDOM_STRING"),
                    "test_type": "Fuzz",
                    "request_headers": PrismaJson(tc.get("headers", {})),
                    "request_query": PrismaJson(tc.get("query_params", {})),
                    "request_body": PrismaJson(tc.get("body", {})),
                    "expected_status": tc.get("expected_status", 400),
                    "priority": 1,
                    "isActive": True,
                    "createdBy": triggered_by,
                }
            await prisma.testcase.create(data=tc_data)
        except Exception as exc:
            logger.warning("Failed to create fuzz TestCase %s: %s", tc.get("id"), exc)

    # ── 5. Create TestRun ──
    run_id = str(uuid.uuid4())
    await prisma.testrun.create(
        data={
            "id": run_id,
            "projectId": project_id,
            "environment": "fuzz-test",
            "status": "RUNNING",
            "categories": ["FUZZ"],
            "total_tests": len(all_test_cases),
            "triggeredBy": triggered_by,
            "startedAt": datetime.now(timezone.utc),
            "metadata": json.dumps({"spec_id": spec_id, "base_url": target_base_url}),
        }
    )

    # ── 6. Phased Execution ──
    findings = []
    executed = False
    
    # Combined collection maintaining order: Public (Phase 2) then Protected (Phase 3)
    # Discovery tests are already at the top of their respective lists in the engine.
    runnable_cases = []
    runnable_cases.extend(test_plan["public_tests"])
    
    if context.bearer_token:
        logger.info(f"[AUTH] Verified Token: {context.bearer_token[:15]}...")
        runnable_cases.extend(test_plan["protected_tests"])
    else:
        logger.info("[AUTH] Skipping Protected Routes: No Token.")

    if execute and runnable_cases:
        try:
            native_result = await run_fuzz_native(
                test_cases=runnable_cases,
                base_url=target_base_url,
                spec=spec_dict,
                context=context,
            )
            findings = native_result.get("findings", [])
            summary = native_result.get("summary", {"total": len(runnable_cases), "passed": 0, "failed": 0})
            executed = True
        except Exception as exc:
            logger.error("Native fuzz execution failed: %s", exc)
            summary = {"total": len(runnable_cases), "passed": 0, "failed": len(runnable_cases)}
            executed = False

        # ── 7. Store TestResult + FuzzResult ──
        for finding in findings:
            tc_id = finding.get("test_case_id")
            tc_data = next((t for t in all_test_cases if t.get("id") == tc_id), {})
            method = tc_data.get("method", "GET").upper()
            path = tc_data.get("endpoint_path", "/")
            endpoint_id = _find_endpoint_id(method, path, endpoint_lookup, fallback_ep_id)

            sub_cat = finding.get("fuzz_type", "RANDOM_STRING")
            valid_sub_categories = {
                "RANDOM_STRING", "LONG_INPUT", "BOUNDARY", "SQLI", 
                "XSS", "PATH_TRAVERSAL", "UNICODE", "SCHEMA_FUZZ"
            }
            if sub_cat not in valid_sub_categories:
                sub_cat = "RANDOM_STRING"

            # Store TestResult (requires valid testCaseId)
            try:
                tc_exists = await prisma.testcase.find_unique(where={"id": tc_id}) if tc_id else None
                if tc_exists:
                    if finding["anomaly_detected"]:
                        print(f"[ANOMALY] {finding['test_name']} -> {finding['status_code']} ({finding['anomaly_details']})")
                    
                    await prisma.testresult.create(
                        data={
                            "runId": run_id,
                            "testCaseId": tc_id,
                            "status": "FAILED" if finding["anomaly_detected"] else "PASSED",
                            "category": "FUZZ",
                            "subCategory": sub_cat,
                            "expected_status": tc_data.get("expected_status", 400),
                            "actual_status": finding.get("status_code", 0),
                            "response_time_ms": finding.get("response_time_ms"),
                            "error_message": finding.get("anomaly_details"),
                        }
                    )
            except Exception as exc:
                logger.warning("Failed to store TestResult for %s: %s", tc_id, exc)

            # Store FuzzResult (raw metadata)
            try:
                await prisma.fuzzresult.create(
                    data={
                        "runId": run_id,
                        "testCaseId": tc_id if tc_id else None,
                        "endpointId": endpoint_id,
                        "fuzzType": sub_cat,
                        "inputPayload": json.dumps(tc_data.get("body")) if tc_data.get("body") else None,
                        "responseStatus": finding.get("status_code"),
                        "crashed": finding.get("crashed", False),
                        "anomalyDetected": finding.get("anomaly_detected", False),
                        "anomalyDetails": finding.get("anomaly_details"),
                    }
                )
            except Exception as exc:
                logger.warning("Failed to store FuzzResult for %s: %s", tc_id, exc)

    # ── 8. Update TestRun status ──
    await prisma.testrun.update(
        where={"id": run_id},
        data={
            "status": "COMPLETED",
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "completedAt": datetime.now(timezone.utc),
            "durationMs": 0,
        },
    )

    return {
        "test_cases": all_test_cases,
        "findings": findings,
        "summary": summary,
        "run_id": run_id,
        "executed": executed,
    }
