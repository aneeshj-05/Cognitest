"""
Native Fuzz testing execution runner using httpx.
Replaces Newman to utilize seamless zero-config auth, dummy file handling, and chained capabilities.
"""

import time
import httpx
import logging
import json
from typing import Any

from src.modules.generator.engines.functional.variable_resolver import resolve_placeholders

logger = logging.getLogger(__name__)

def _get_allowed_status_codes(spec: dict, path: str, method: str):
    paths = spec.get("paths", {})
    op = paths.get(path, {}).get(method.lower(), {})
    responses = op.get("responses", {})
    return {int(code) for code in responses.keys() if str(code).isdigit()}


async def run_fuzz_native(
    test_cases: list[dict],
    base_url: str,
    spec: dict,
    context: Any,  # ExecutionContext from auth_handler
) -> dict[str, Any]:
    """
    Executes fuzz test cases sequentially via httpx.
    Returns Newman-compatible raw results dict.
    """
    logger.info(f"Running Native Fuzz Engine on {len(test_cases)} cases...")

    # Build the execution context state dictionary
    execution_state: dict[str, Any] = {}
    if getattr(context, "bearer_token", None):
        execution_state["auth_token"] = context.bearer_token

    findings = []
    from src.utils.egress_guard import validate_egress_url, build_pinned_transport
    _guard = validate_egress_url(base_url)
    async with httpx.AsyncClient(
        transport=build_pinned_transport(_guard),
        timeout=60.0,
        follow_redirects=False,
    ) as client:
        for i, tc in enumerate(test_cases):
            start_time = time.time()
            
            # Resolve placeholders in URL path
            endpoint_path_template = tc.get("endpoint_path", "/").split("#")[0]
            endpoint_path_template = resolve_placeholders(endpoint_path_template, execution_state)
            
            # STATEFUL: Substitute path parameters (e.g., {id} -> 123)
            path_params = resolve_placeholders(tc.get("path_params") or {}, execution_state)
            for param, val in path_params.items():
                endpoint_path_template = endpoint_path_template.replace(f"{{{param}}}", str(val)).replace(f"{{{{{param}}}}}", str(val))

            # Dependency Guard: If we still have unresolved {{vars}} in the path, skip this test
            # (Unless we are specifically fuzzing the path via PATH_FUZZ)
            if "{{" in endpoint_path_template and tc.get("fuzz_type") != "PATH_FUZZ":
                logger.warning(f"Fuzz Runner: Skipping '{tc.get('name')}' due to unresolved dependencies in path: {endpoint_path_template}")
                continue

            url = f"{base_url.rstrip('/')}{endpoint_path_template}"
            method = tc.get("method", "GET").upper()
            
            # Extract headers and body
            raw_body = tc.get("body")
            case_headers = dict(tc.get("headers") or {})
            
            requires_auth = bool(tc.get("requires_auth") or tc.get("security_required") or tc.get("requires_stateful"))
            
            # 1. Base auth injection (identical to functional engine zero-config logic)
            if "auth_token" in execution_state and execution_state["auth_token"]:
                clean_token = str(execution_state["auth_token"])
                if not clean_token.lower().startswith("bearer "):
                    clean_token = f"Bearer {clean_token}"
                
                case_headers["Authorization"] = clean_token
                
                # Generic fallbacks
                case_headers["x-auth-token"] = clean_token.replace("Bearer ", "")
                case_headers["x-api-key"] = clean_token.replace("Bearer ", "")
                
            elif requires_auth:
                 logger.debug(f"Fuzz Runner: Warning - '{tc.get('name')}' requires auth but no token is available in context.")

            logger.debug(f"Fuzz Runner Executing: {method} {url} (Stateful: {tc.get('requires_stateful', False)})")
                
            # 2. Custom headers overriding (useful for fuzzy inputs specifically overriding Auth!)
            custom_headers = tc.get("custom_headers")
            if custom_headers:
                case_headers.update(custom_headers)
                
            # Resolve placeholders in payload/headers
            case_headers = resolve_placeholders(case_headers, execution_state)
            body = resolve_placeholders(raw_body, execution_state)
            case_query = resolve_placeholders(tc.get("query_params") or {}, execution_state)
            
            kwargs: dict[str, Any] = {}
            if case_query:
                kwargs["params"] = case_query
                
            if body is not None:
                if isinstance(body, dict) and "multipart/form-data" in case_headers.get("Content-Type", "").lower():
                    # Handle multipart forms explicitly to prevent backend hangs
                    _file_fields = {
                        "image", "file", "avatar", "photo", "picture",
                        "thumbnail", "attachment", "document", "upload",
                        "media", "cover", "banner", "icon", "logo", "video",
                    }
                    files_dict: dict = {}
                    for fn, fv in body.items():
                        if fn.lower() in _file_fields:
                            files_dict[fn] = ("test_upload.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64, "image/png")
                        else:
                            files_dict[fn] = (None, str(fv))
                    kwargs["files"] = files_dict
                    case_headers.pop("Content-Type", None)
                elif isinstance(body, str):
                    kwargs["content"] = body
                    if "Content-Type" not in case_headers:
                        case_headers["Content-Type"] = "application/json"
                else:
                    kwargs["json"] = body
                    
            # Set headers safely into kwargs
            kwargs["headers"] = case_headers
            
            # Execute natively
            status_code = 0
            response_time_ms = 0
            request_error = None
            response_body = ""
            
            try:
                response = await client.request(method, url, **kwargs)
                status_code = response.status_code
                response_time_ms = int((time.time() - start_time) * 1000)
                response_body = response.text[:2048] if response.text else ""
                
                # 🚨 STATEFUL EXTRACTION: Capture IDs/tokens from response
                extract_rules = tc.get("extract")
                if extract_rules and status_code < 300:
                    try:
                        resp_json = response.json()
                        from src.modules.generator.engines.functional.variable_resolver import extract_variables
                        extracted = extract_variables(resp_json, extract_rules)
                        if extracted:
                            execution_state.update(extracted)
                            logger.debug(f"Fuzz Runner: Extracted state: {extracted}")
                    except Exception as ex:
                        logger.debug(f"Fuzz Runner: Extraction failed: {ex}")

            except Exception as e:
                status_code = 0
                response_time_ms = int((time.time() - start_time) * 1000)
                request_error = str(e)
                
            # Mock Newman raw execution structure for the anomaly detector to parse seamlessly
            allowed_status = _get_allowed_status_codes(spec, tc.get("endpoint_path", ""), method)
            
            crashed = False
            anomaly_detected = False
            anomaly_details = None
            
            # 🚨 Server crash
            if status_code >= 500:
                crashed = True
                anomaly_detected = True
                anomaly_details = f"Server returned {status_code}"

            # 🚨 Request error
            if request_error:
                crashed = True
                anomaly_detected = True
                anomaly_details = f"Request error: {request_error}"

            # 🚨 Unexpected status
            # Fuzz tests naturally produce 4xx client errors (e.g., 400 Bad Request, 422 Unprocessable Entity).
            # If the server correctly rejected the bad payload with a 4xx, it is NOT an anomaly,
            # even if the developer forgot to document the 4xx in their Swagger spec.
            safe_fuzz_status = {400, 401, 403, 404, 405, 406, 413, 415, 422, 429}
            
            if allowed_status and status_code not in allowed_status and status_code < 500:
                if status_code not in safe_fuzz_status:
                    anomaly_detected = True
                    anomaly_details = f"Unexpected status {status_code}. Allowed: {sorted(allowed_status)}"

            # 🚨 Slow response
            if response_time_ms > 15000:
                anomaly_detected = True
                anomaly_details = ((anomaly_details or "") + f" | Slow response: {response_time_ms}ms").strip(" | ")

            findings.append({
                "test_case_id": tc.get("id"),
                "test_name": tc.get("name", f"Test {i}"),
                "fuzz_type": tc.get("fuzz_type", "UNKNOWN"),
                "method": method,
                "endpoint_path": tc.get("endpoint_path", ""),
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "request_error": request_error,
                "response_body": response_body,
                "expected_status": tc.get("expected_status", 400),
                "crashed": crashed,
                "anomaly_detected": anomaly_detected,
                "anomaly_details": anomaly_details,
            })
            
    summary = {
        "total": len(findings),
        "passed": sum(1 for f in findings if not f["anomaly_detected"]),
        "failed": sum(1 for f in findings if f["anomaly_detected"]),
        "crashed": sum(1 for f in findings if f["crashed"]),
        "anomalies_detected": sum(1 for f in findings if f["anomaly_detected"]),
    }
            
    return {
        "findings": findings,
        "summary": summary
    }
