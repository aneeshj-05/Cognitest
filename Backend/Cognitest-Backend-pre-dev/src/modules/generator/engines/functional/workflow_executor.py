"""
Workflow execution engine for multi-step chained API tests.

Executes a WorkflowTest step-by-step:
1. Resolves {{variable}} placeholders in each step's request using accumulated context.
2. Sends the HTTP request.
3. Extracts variables from the response using JSONPath rules.
4. Validates status code and state assertions.
5. On step failure: marks remaining steps SKIPPED and emits a rollback event.

Returns a WorkflowRunResult with:
- Per-step results (status, variables, pass/fail, timing)
- Variable snapshots at each step boundary
- Final state label
- Rollback information if a step failed mid-workflow
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, List, Dict, Optional

import httpx

from .variable_resolver import (
    extract_variables,
    resolve_placeholders,
    get_unresolved_placeholders,
)
from src.modules.generator.services.data_provider import data_provider

logger = logging.getLogger(__name__)

# Field names that are likely file uploads
_FILE_FIELD_NAMES = frozenset({
    "image", "file", "avatar", "photo", "picture", "thumbnail",
    "attachment", "document", "upload", "media", "cover",
    "banner", "icon", "logo", "video",
})


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    step_id: str
    step_index: int          # 0-based
    name: str
    method: str
    endpoint_path: str
    expected_status: int
    actual_status: int
    passed: bool
    skipped: bool = False
    response_time_ms: int = 0
    response_body: str = ""
    response_headers: dict = field(default_factory=dict)
    error_message: str = ""
    # Variables extracted from this step's response
    extracted_vars: dict = field(default_factory=dict)
    # Variables that were injected INTO this step (snapshot before execution)
    injected_vars: dict = field(default_factory=dict)
    expected_state: str | None = None
    effective_url: str = ""
    # Resolved request parts (for UI reporting)
    resolved_body: Any = None
    resolved_headers: dict = field(default_factory=dict)

    def to_event(self, workflow_id: str) -> dict:
        return {
            "event": "workflow_step",
            "workflow_id": workflow_id,
            "step": self.step_index + 1,
            "step_id": self.step_id,
            "name": self.name,
            "method": self.method,
            "endpoint_path": self.endpoint_path,
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "passed": self.passed,
            "skipped": self.skipped,
            "response_time_ms": self.response_time_ms,
            "response_body": self.response_body,
            "error_message": self.error_message,
            "extracted_vars": self.extracted_vars,
            "injected_vars": self.injected_vars,
            "expected_state": self.expected_state,
            "effective_url": self.effective_url,
            "resolved_body": self.resolved_body,
            "resolved_headers": self.resolved_headers,
        }


@dataclass
class WorkflowRunResult:
    workflow_id: str
    workflow_name: str
    passed: bool
    step_results: list[StepResult]
    final_state: str | None = None
    rollback_triggered: bool = False
    rollback_reason: str = ""
    # Variable context at the end of all steps
    final_context: dict = field(default_factory=dict)
    total_time_ms: int = 0

    def to_summary_event(self) -> dict:
        return {
            "event": "workflow_done",
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "passed": self.passed,
            "steps_total": len(self.step_results),
            "steps_passed": sum(1 for s in self.step_results if s.passed),
            "steps_failed": sum(1 for s in self.step_results if not s.passed and not s.skipped),
            "steps_skipped": sum(1 for s in self.step_results if s.skipped),
            "final_state": self.final_state,
            "rollback_triggered": self.rollback_triggered,
            "rollback_reason": self.rollback_reason,
            "total_time_ms": self.total_time_ms,
        }

    def to_rollback_event(self) -> dict:
        return {
            "event": "workflow_rollback",
            "workflow_id": self.workflow_id,
            "reason": self.rollback_reason,
            "state": self.final_state,
        }


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class WorkflowExecutor:
    """
    Executes a serialised WorkflowTest dict step-by-step.
    """

    async def run(
        self,
        workflow: dict,
        base_url: str,
        client: httpx.AsyncClient,
        initial_context: dict[str, Any] | None = None,
    ) -> WorkflowRunResult:
        workflow_id = workflow.get("id", "unknown")
        workflow_name = workflow.get("name", "Unnamed Workflow")
        steps = workflow.get("steps", [])
        state_machine = workflow.get("state_machine", [])

        step_results: list[StepResult] = []
        context = self._prepare_context(workflow, initial_context)
        
        overall_passed = True
        rollback_triggered = False
        rollback_reason = ""
        final_state: str | None = state_machine[0] if state_machine else None
        total_start = time.time()

        # Track created resources for automatic cleanup
        created_resources: list[dict[str, str]] = []

        for i, step in enumerate(steps):
            step_id = step.get("step_id", f"step-{i}")
            name = step.get("name", f"Step {i+1}")
            method = step.get("method", "GET").upper()
            endpoint_path = step.get("endpoint_path", "/")
            expected_status = step.get("expected_status", 200)
            expected_state: str | None = step.get("expected_state")

            # 1. Check declared dependencies
            missing_deps, error_msg = self._check_dependencies(step, context)
            if missing_deps:
                # Pre-resolve what we can so the UI still shows a payload
                _pre = self._resolve_step_request(step, context, base_url)
                step_results.append(StepResult(
                    step_id=step_id, step_index=i, name=name, method=method,
                    endpoint_path=endpoint_path, expected_status=expected_status,
                    actual_status=0, passed=False, skipped=False if "auth_token" in missing_deps else True,
                    error_message=error_msg, expected_state=expected_state,
                    resolved_body=_pre["body"], resolved_headers=_pre["headers"],
                    effective_url=_pre["full_url"],
                ))
                overall_passed = False
                continue

            # 1b. Guard: check for unresolved placeholders in the FINAL resolved path
            #     (after path_params substitution) - catches both {id} and {{id}} formats
            _resolved_path_check = resolve_placeholders(step.get("endpoint_path", "/"), context)
            # Substitute path_params to get the truly final path
            _path_params_check = resolve_placeholders(step.get("path_params") or {}, context)
            if _path_params_check:
                for _pk, _pv in _path_params_check.items():
                    _resolved_path_check = (
                        _resolved_path_check
                        .replace(f"{{{_pk}}}", str(_pv))
                        .replace(f"{{{{{_pk}}}}}", str(_pv))
                    )
            _unresolved = get_unresolved_placeholders(_resolved_path_check)
            # Also catch remaining single-brace {param} that weren't substituted
            import re as _re
            _single_brace = _re.findall(r"\{([^{}]+)\}", _resolved_path_check)
            _all_unresolved = list(set(_unresolved + _single_brace))
            if _all_unresolved:
                _pre = self._resolve_step_request(step, context, base_url)
                skip_msg = f"Skipped: path variable(s) {_all_unresolved} not yet available in context"
                step_results.append(StepResult(
                    step_id=step_id, step_index=i, name=name, method=method,
                    endpoint_path=endpoint_path, expected_status=expected_status,
                    actual_status=0, passed=False, skipped=True,
                    error_message=skip_msg, expected_state=expected_state,
                    resolved_body=_pre["body"], resolved_headers=_pre["headers"],
                    effective_url=_pre["full_url"],
                ))
                overall_passed = False
                continue

            # 2. Resolve request
            resolved = self._resolve_step_request(step, context, base_url)
            
            # 3. Execute (10s per-step timeout to prevent hangs)
            step_start = time.time()
            try:
                req_kwargs, final_headers = self._prepare_http_request(method, resolved, context)
                req_kwargs["timeout"] = 10.0
                
                # Perform request with retry logic for 502/503/504
                max_retries = 3
                retry_count = 0
                while retry_count < max_retries:
                    resp = await client.request(method, resolved["full_url"], **req_kwargs)
                    actual_status = resp.status_code
                    if actual_status in (502, 503, 504) and retry_count < max_retries - 1:
                        retry_count += 1
                        backoff = 1.0 * retry_count
                        await asyncio.sleep(backoff)
                        continue
                    break

                elapsed_ms = int((time.time() - step_start) * 1000)
                resp_text = resp.text[:2048] if resp.text else ""
                
                # 4. Extract variables
                extracted = self._extract_and_update_context(step, resp, context)
                
                # Heuristic: If we just POSTed and got a created_id, track it for cleanup
                if method == "POST" and actual_status in (200, 201) and "created_id" in extracted:
                    created_resources.append({
                        "base_path": resolved["path"],
                        "resource_id": str(extracted["created_id"])
                    })
                
                # 5. Evaluate
                passed, error_msg = self._evaluate_step_result(step, actual_status, resp_text, resolved["path"])
                
                if expected_state and passed:
                    final_state = expected_state

                step_result = StepResult(
                    step_id=step_id, step_index=i, name=name, method=method,
                    endpoint_path=resolved["path"], expected_status=expected_status,
                    actual_status=actual_status, passed=passed, response_time_ms=elapsed_ms,
                    response_body=resp_text, response_headers=dict(resp.headers),
                    error_message=error_msg, extracted_vars=extracted,
                    injected_vars={k: v for k, v in context.items() if k not in extracted},
                    expected_state=expected_state, effective_url=resolved["full_url"],
                    resolved_body=resolved["body"], resolved_headers=final_headers,
                )
                step_results.append(step_result)

                if not passed:
                    overall_passed = False
                    rollback_triggered = True
                    rollback_reason = f"Step {i+1} '{name}' failed: {error_msg}"
                    self._handle_step_failure(steps[i+1:], i+1, step_results, rollback_reason)
                    break
                
                # Small delay between steps to prevent overwhelming the server
                await asyncio.sleep(0.3)

            except Exception as exc:
                elapsed_ms = int((time.time() - step_start) * 1000)
                overall_passed = False
                rollback_triggered = True
                rollback_reason = f"Step {i+1} '{name}' raised exception: {exc}"
                step_results.append(StepResult(
                    step_id=step_id, step_index=i, name=name, method=method,
                    endpoint_path=resolved["path"], expected_status=expected_status,
                    actual_status=0, passed=False, response_time_ms=elapsed_ms,
                    error_message=f"Connection error: {exc}", expected_state=expected_state,
                    effective_url=resolved["full_url"], resolved_body=resolved["body"],
                    resolved_headers=resolved["headers"],
                ))
                self._handle_step_failure(steps[i+1:], i+1, step_results, rollback_reason)
                break

        # -- Mandatory Cleanup Phase --
        if created_resources:
            await self._perform_cleanup(created_resources, base_url, client, context)

        return WorkflowRunResult(
            workflow_id=workflow_id, workflow_name=workflow_name, passed=overall_passed,
            step_results=step_results, final_state=final_state, rollback_triggered=rollback_triggered,
            rollback_reason=rollback_reason, final_context=dict(context),
            total_time_ms=int((time.time() - total_start) * 1000),
        )

    async def _perform_cleanup(
        self, 
        resources: list[dict[str, str]], 
        base_url: str, 
        client: httpx.AsyncClient, 
        context: dict
    ):
        """
        Attempts to delete created resources in reverse order of creation.
        Verifies cleanup by checking for 404/401 on the resource path.
        """
        logger.info(f"Starting cleanup for {len(resources)} resources...")
        
        # Resolve placeholders in base_url once
        base_url = resolve_placeholders(base_url, context)
        
        # Prepare auth headers if available
        auth_token = context.get("auth_token")
        headers = {"User-Agent": "Cognitest-WorkflowCleanup/1.0"}
        if auth_token and str(auth_token).strip():
            token = str(auth_token).strip()
            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"

        # Delete in reverse order (e.g., delete order before deleting user)
        for res in reversed(resources):
            base_path = res["base_path"].rstrip("/")
            rid = res["resource_id"]
            
            # Heuristic: If base_path already looks like it has an ID, don't append
            # But usually it's the collection path from the POST.
            # Example: POST /api/users -> DELETE /api/users/{id}
            delete_url = f"{base_url.rstrip('/')}{base_path}/{rid}"
            
            try:
                # 1. Attempt DELETE
                logger.debug(f"Cleanup: DELETE {delete_url}")
                del_resp = await client.delete(delete_url, headers=headers, timeout=5.0)
                
                if del_resp.status_code in (200, 204, 404):
                    logger.info(f"Cleanup: Successfully deleted {delete_url} (Status: {del_resp.status_code})")
                    
                    # 2. Verification: GET should return 404/401
                    # Give the DB a tiny moment to settle if needed
                    await asyncio.sleep(0.1)
                    verify_resp = await client.get(delete_url, headers=headers, timeout=5.0)
                    if verify_resp.status_code in (404, 401, 403):
                        logger.info(f"Cleanup Verified: {delete_url} is no longer accessible (Status: {verify_resp.status_code})")
                    else:
                        logger.warning(f"Cleanup Warning: {delete_url} still returns {verify_resp.status_code} after DELETE")
                else:
                    logger.warning(f"Cleanup Failed: DELETE {delete_url} returned {del_resp.status_code}")
            except Exception as e:
                logger.error(f"Cleanup Error: Failed to delete {delete_url}: {e}")

    def _prepare_context(self, workflow: dict, initial_context: dict | None) -> dict:
        if initial_context is not None:
            if "email" not in initial_context:
                initial_context["email"] = data_provider.generate_email()
            return initial_context
        
        category = workflow.get("category", "Functional").capitalize()
        return {
            "email": data_provider.generate_email(prefix=f"test{category}"),
            "category": category,
            "timestamp": str(int(time.time() * 1000)),
            "run_id": str(uuid.uuid4())[:8],
            "auth_token": "",
        }

    def _check_dependencies(self, step: dict, context: dict) -> tuple[list[str], str]:
        depends_on = step.get("depends_on") or []
        missing = [d for d in depends_on if d not in context or not context[d]]
        if missing:
            is_auth = "auth_token" in missing
            msg = "Authentication required. Ensure a login step runs first." if is_auth else f"Missing variables: {missing}"
            return missing, msg
        return [], ""

    def _resolve_step_request(self, step: dict, context: dict, base_url: str) -> dict:
        path = resolve_placeholders(step.get("endpoint_path", "/"), context)
        body = resolve_placeholders(step.get("request_body"), context)
        headers = resolve_placeholders(step.get("request_headers") or {}, context)
        query = resolve_placeholders(step.get("request_query") or {}, context)
        path_params = resolve_placeholders(step.get("path_params") or {}, context)

        if path_params:
            for param, val in path_params.items():
                path = path.replace(f"{{{param}}}", str(val)).replace(f"{{{{{param}}}}}", str(val))

        # Resolve placeholders in base_url
        base_url = resolve_placeholders(base_url, context)

        return {
            "path": path, "body": body, "headers": headers, "query": query,
            "full_url": f"{base_url.rstrip('/')}{path}"
        }

    def _prepare_http_request(self, method: str, resolved: dict, context: dict) -> tuple[dict, dict]:
        headers = {**resolved["headers"]}
        if "User-Agent" not in headers:
            headers["User-Agent"] = "Cognitest-WorkflowRunner/1.0"
        
        auth_token = context.get("auth_token")
        if auth_token and str(auth_token).strip():
            token = str(auth_token).strip()
            headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"

        req_kwargs: dict[str, Any] = {"headers": headers}
        if resolved["query"]:
            req_kwargs["params"] = resolved["query"]

        if resolved["body"] and method in ("POST", "PUT", "PATCH"):
            content_type = headers.get("Content-Type", "").lower()
            if "multipart/form-data" in content_type:
                headers.pop("Content-Type", None)
                files = {}
                for k, v in resolved["body"].items():
                    if k.lower() in _FILE_FIELD_NAMES:
                        files[k] = ("test_upload.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")
                    else:
                        files[k] = (None, str(v))
                req_kwargs["files"] = files
            else:
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
                req_kwargs["json"] = resolved["body"]
        
        return req_kwargs, headers

    def _extract_and_update_context(self, step: dict, resp: httpx.Response, context: dict) -> dict:
        extract_rules = step.get("extract") or {}
        try:
            resp_json = resp.json()
        except Exception:
            resp_json = None

        extracted = {}
        if resp_json is not None:
            if extract_rules:
                extracted = extract_variables(resp_json, extract_rules)

            # Always deep-scan for auth_token if not yet in context
            if not context.get("auth_token"):
                deep_tokens = self._deep_scan(resp_json, {
                    "token", "access_token", "accessToken", "jwt",
                    "auth_token", "id_token", "session_token", "bearer",
                })
                if deep_tokens:
                    extracted["auth_token"] = next(iter(deep_tokens.values()))

            # Always deep-scan for a resource ID if created_id not yet set
            if not context.get("created_id"):
                deep_ids = self._deep_scan(resp_json, {
                    "id", "_id", "userId", "user_id", "productId",
                    "product_id", "orderId", "order_id", "cartId", "cart_id",
                    "itemId", "item_id",
                })
                if deep_ids:
                    # Prefer the most specific match available
                    for k in ("id", "_id", "userId", "productId", "orderId"):
                        if k in deep_ids:
                            extracted["created_id"] = deep_ids[k]
                            break

            context.update(extracted)
        return extracted

    def _evaluate_step_result(self, step: dict, actual: int, resp_text: str, path: str) -> tuple[bool, str]:
        expected = step.get("expected_status", 200)
        method = step.get("method", "GET").upper()
        
        is_auth = any(kw in path.lower() for kw in ("signup", "register", "users", "auth"))
        
        passed = False
        if expected == 204 and actual in (200, 204): passed = True
        elif expected == 400 and actual == 404: passed = True
        elif expected == 201 and actual in (409, 422) and method == "POST" and is_auth: passed = True
        else: passed = actual == expected

        error_msg = ""
        if not passed:
            error_msg = f"Expected {expected}, got {actual}"
            try:
                body = json.loads(resp_text)
                detail = body.get("detail") or body.get("message") or body.get("error")
                if detail: error_msg += f": {detail}"
            except:
                if len(resp_text) < 200: error_msg += f": {resp_text}"
        
        return passed, error_msg

    def _handle_step_failure(self, remaining_steps: list, start_idx: int, results: list, reason: str):
        for i, step in enumerate(remaining_steps):
            results.append(StepResult(
                step_id=step.get("step_id", f"step-{start_idx+i}"),
                step_index=start_idx+i, name=step.get("name", f"Step {start_idx+i+1}"),
                method=step.get("method", "GET").upper(), endpoint_path=step.get("endpoint_path", "/"),
                expected_status=step.get("expected_status", 200), actual_status=0,
                passed=False, skipped=True, error_message=f"Skipped: {reason}",
                expected_state=step.get("expected_state"),
            ))

    def _deep_scan(self, obj: Any, keys: set[str]) -> dict[str, Any]:
        found = {}
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in keys and v: found[k] = v
                if isinstance(v, (dict, list)): found.update(self._deep_scan(v, keys))
        elif isinstance(obj, list):
            for item in obj: found.update(self._deep_scan(item, keys))
        return found
