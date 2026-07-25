"""
Fuzz Testing Engine — Full Swagger-aware fuzz coverage.
"""

import uuid
import logging
from typing import Any
from ...spec_parser import extract_endpoints, get_expected_status
from ..functional.dependency_orchestrator import build_execution_plan, get_execution_summary

from .random_strings import generate_random_string_tests
from .unicode_input import generate_unicode_tests
from .long_input import generate_long_input_tests
from .xss_fuzz import generate_xss_fuzz_tests
from .path_traversal import generate_path_traversal_tests
from .payload_injection import generate_payload_injection_tests
from .boundary_tests import (
    generate_boundary_value_tests,
    generate_missing_required_tests,
    generate_type_mismatch_tests,
    generate_enum_violation_tests,
    generate_extra_fields_test,
    generate_malformed_json_tests,
)
from ...ai.generators.fuzz_generator_ai import generate_fuzz_tests_ai

logger = logging.getLogger(__name__)


def _base_test(endpoint, name, fuzz_type, **kwargs):
    expected_status = kwargs.get("expected_status", 400)
    resolved_status = get_expected_status(endpoint, expected_status)
    if not resolved_status:
        return None

    # Stateful path params: use placeholders like {{resource_id}} for path variables
    path_params = kwargs.get("path_params", {})
    if not path_params:
        for p in endpoint.path_params:
            # We use 'resource_id' as the generic placeholder for IDs in our system
            path_params[p] = "{{resource_id}}"

    return {
        "id": str(uuid.uuid4()),
        "name": name,
        "test_type": "FUZZ",
        "fuzz_type": fuzz_type,
        "endpoint_path": endpoint.path,
        "path_params": path_params,
        "method": endpoint.method,
        "headers": kwargs.get("headers", {}),
        "body": kwargs.get("body"),
        "query_params": kwargs.get("query_params", {}),
        "expected_status": resolved_status,
        "expected_behavior": "Should not crash",
        "description": name,
        "requires_auth": endpoint.requires_auth,
        "requires_stateful": endpoint.requires_auth or bool(endpoint.path_params),
    }


def _generate_body_fuzz(endpoint):
    tests = []
    if not endpoint.body_schema:
        return tests
    t = _base_test(
            endpoint,
            f"Random body fuzz — {endpoint.method} {endpoint.path}",
            "RANDOM_STRING",
            body={"invalid": "###@@@###"},
            expected_status=400,
        )
    if t: tests.append(t)
    return tests


def _generate_query_fuzz(endpoint):
    tests = []
    for param in endpoint.query_params:
        t = _base_test(
                endpoint,
                f"Query fuzz {param['name']} — {endpoint.path}",
                "QUERY_FUZZ",
                query_params={param["name"]: "%%%INVALID%%%"},
                expected_status=400,
            )
        if t: tests.append(t)
    return tests


def _generate_path_fuzz(endpoint):
    tests = []
    expected_status = get_expected_status(endpoint, 400)
    if not expected_status:
        return tests

    for p in endpoint.path_params:
        tests.append({
            "id": str(uuid.uuid4()),
            "name": f"Path fuzz {p} — {endpoint.method} {endpoint.path}",
            "test_type": "FUZZ",
            "fuzz_type": "PATH_FUZZ",
            "endpoint_path": endpoint.path,
            "path_params": {p: "INVALID_ID_999"}, # Specifically fuzzing THIS param
            "method": endpoint.method,
            "headers": {},
            "body": None,
            "query_params": {},
            "expected_status": expected_status,
            "expected_behavior": "Should not crash",
            "description": "Invalid path parameter",
            "requires_auth": endpoint.requires_auth,
            "requires_stateful": True,
        })
    return tests


def _generate_auth_fuzz(endpoint):
    tests = []
    if endpoint.requires_auth:
        expected_status = get_expected_status(endpoint, 401)
        if expected_status:
            tests.append({
                "id": str(uuid.uuid4()),
                "name": f"Unauthorized access — {endpoint.method} {endpoint.path}",
                "test_type": "FUZZ",
                "fuzz_type": "UNAUTHORIZED",
                "endpoint_path": endpoint.path,
                "method": endpoint.method,
                "headers": {},
                "body": None,
                "query_params": {},
                "expected_status": expected_status,
                "expected_behavior": f"Should reject without token (Expected {expected_status})",
                "description": "Access without authentication",
                "requires_auth": False,
            })
    return tests


def _generate_method_confusion(endpoint):
    alt_method = "POST" if endpoint.method != "POST" else "GET"
    expected_status = get_expected_status(endpoint, 405)
    if not expected_status:
        return []

    return [{
        "id": str(uuid.uuid4()),
        "name": f"Method confusion — {endpoint.path}",
        "test_type": "FUZZ",
        "fuzz_type": "METHOD_CONFUSION",
        "endpoint_path": endpoint.path,
        "method": alt_method,
        "headers": {},
        "body": None,
        "query_params": {},
        "expected_status": expected_status,
        "expected_behavior": f"Should reject invalid method (Expected {expected_status})",
        "description": "Wrong HTTP method",
        "requires_auth": endpoint.requires_auth,
    }]
def _detect_auth_endpoints(endpoints):
    """
    Detect signup (register) and login endpoints from the spec data — NOT path keywords.

    Detection logic (spec-driven):
      - register_ep: POST endpoint whose body schema has a 'password' field AND
        whose response schema does NOT return a token (signup = create account,
        no immediate token in all APIs) OR whose path contains no login-specific
        response signals. We use the first POST with password in body that is
        NOT also the clearest login candidate.
      - login_ep: POST endpoint whose response schema returns a token field
        (access_token, token, jwt, etc.) — the most reliable signal for login.

    Fallback ordering: if both candidates match the same endpoint, login_ep wins.
    """
    _password_fields  = {"password", "passwd", "passphrase", "pass", "secret", "pin"}
    _token_fields     = {"token", "access_token", "accesstoken", "refresh_token",
                         "refreshtoken", "id_token", "jwt", "auth_token", "bearer"}
    _identity_fields  = {"email", "username", "user_name", "phone", "mobile"}

    register_ep = None
    login_ep    = None

    for ep in endpoints:
        if ep.method != "POST":
            continue

        body_props = {}
        if ep.body_schema and isinstance(ep.body_schema, dict):
            body_props = ep.body_schema.get("properties", {}) or {}

        resp_props = {}
        if ep.response_schema and isinstance(ep.response_schema, dict):
            resp_props = ep.response_schema.get("properties", {}) or {}
            # Unwrap common data wrappers like {"data": {"token": ...}}
            if "data" in resp_props and isinstance(resp_props["data"], dict):
                nested = resp_props["data"].get("properties", {})
                if nested:
                    resp_props = {**resp_props, **nested}

        body_keys = {k.lower() for k in body_props}
        resp_keys  = {k.lower() for k in resp_props}

        has_password   = bool(body_keys & _password_fields)
        has_token_resp = bool(resp_keys & _token_fields)
        has_identity   = bool(body_keys & _identity_fields)

        # Login: returns a token in response
        if has_token_resp and login_ep is None:
            login_ep = ep

        # Register: has password in body but response doesn't immediately return token
        # (or it does — both signup and login often share this trait, so we take
        # the first password-having POST that isn't the login_ep)
        if has_password and register_ep is None:
            register_ep = ep

    # If both point to the same endpoint, prefer login_ep assignment and clear register
    if register_ep is not None and login_ep is not None and register_ep is login_ep:
        register_ep = None

    return register_ep, login_ep



def _generate_auth_chain_fuzz(endpoints):
    register_ep, login_ep = _detect_auth_endpoints(endpoints)
    if not register_ep or not login_ep:
        return []

    # Use a "valid" but fuzzed-style payload or just a standard sample
    from ..functional.workflow import _sample_body
    reg_body = _sample_body(register_ep.body_schema) or {}
    
    # Ensure email and password are set for reuse
    for k in reg_body.keys():
        k_lower = k.lower()
        if "email" in k_lower:
            reg_body[k] = f"fuzz_{uuid.uuid4().hex[:6]}@cognitest.io"
        elif "password" in k_lower or "passcode" in k_lower:
            reg_body[k] = "Fuzz@123!"

    login_body = {}
    if login_ep.body_schema:
        login_props = login_ep.body_schema.get("properties", {})
        for k in login_props:
            if k in reg_body:
                login_body[k] = reg_body[k]
        
        if not login_body:
            login_body = _sample_body(login_ep.body_schema) or {}

    return [{
        "id": str(uuid.uuid4()),
        "name": "Fuzz Workflow: Signup → Login with Same Payload",
        "test_type": "FUZZ",
        "fuzz_type": "AUTH_CHAIN",
        "category": "workflow",
        "is_workflow": True,
        "endpoint_path": register_ep.path,
        "method": "POST",
        "expected_status": 201,
        "steps": [
            {
                "step_id": str(uuid.uuid4()),
                "name": f"Signup: POST {register_ep.path}",
                "method": "POST",
                "endpoint_path": register_ep.path,
                "expected_status": 201,
                "request_headers": {"Content-Type": "application/json"},
                "request_body": reg_body,
                "extract": {"auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token"}
            },
            {
                "step_id": str(uuid.uuid4()),
                "name": f"Login: POST {login_ep.path} (same payload)",
                "method": "POST",
                "endpoint_path": login_ep.path,
                "expected_status": 200,
                "request_headers": {"Content-Type": "application/json"},
                "request_body": login_body,
                "extract": {"auth_token": "$.token || $.access_token || $.data.token || $.data.access_token || $.accessToken || $.jwt || $.id_token || $.auth_token"}
            }
        ],
        "description": "Ensures signup credentials work for login even if signup doesn't return a token."
    }]



def _generate_discovery_tests(endpoint):
    """Generate a single valid 'discovery' test to capture IDs for stateful fuzzing."""
    from ..functional.workflow import _sample_body, _sample_path_params
    
    # We want a valid request to get a success response and extract resource_id
    body = _sample_body(endpoint.body_schema) if endpoint.body_schema else None
    path_params = _sample_path_params(endpoint)
    
    # Use 200 or 201 as expected status
    expected_status = get_expected_status(endpoint, 201) or get_expected_status(endpoint, 200) or 200
    
    return [{
        "id": str(uuid.uuid4()),
        "name": f"Discovery: {endpoint.method} {endpoint.path}",
        "test_type": "FUZZ",
        "fuzz_type": "DISCOVERY",
        "endpoint_path": endpoint.path,
        "method": endpoint.method,
        "path_params": path_params,
        "body": body,
        "expected_status": expected_status,
        "requires_auth": endpoint.requires_auth,
        "description": "Valid request to establish state and capture resource IDs.",
    }]


async def generate_fuzz_tests(spec: dict[str, Any], use_ai: bool = False) -> dict[str, Any]:
    endpoints = extract_endpoints(spec)

    logger.info("Extracted %d endpoints for fuzzing", len(endpoints))

    # Log orchestrator plan for debugging
    plan_summary = get_execution_summary(endpoints)
    logger.info(
        "[FuzzEngine] Execution plan: %d endpoints classified",
        plan_summary["total_endpoints"],
    )

    all_fuzz_cases: list[dict] = []

    for endpoint in endpoints:
        endpoint_tests = []
        # Discovery first to capture IDs
        endpoint_tests.extend(_generate_discovery_tests(endpoint))
        
        endpoint_tests.extend(_generate_body_fuzz(endpoint))
        endpoint_tests.extend(_generate_query_fuzz(endpoint))
        endpoint_tests.extend(_generate_path_fuzz(endpoint))
        endpoint_tests.extend(_generate_auth_fuzz(endpoint))
        endpoint_tests.extend(_generate_method_confusion(endpoint))

        # Advanced sub-generators
        endpoint_tests.extend(generate_random_string_tests(endpoint))
        endpoint_tests.extend(generate_unicode_tests(endpoint))
        endpoint_tests.extend(generate_long_input_tests(endpoint))
        endpoint_tests.extend(generate_xss_fuzz_tests(endpoint))
        endpoint_tests.extend(generate_path_traversal_tests(endpoint))
        endpoint_tests.extend(generate_payload_injection_tests(endpoint))
        endpoint_tests.extend(generate_boundary_value_tests(endpoint))
        endpoint_tests.extend(generate_missing_required_tests(endpoint))
        endpoint_tests.extend(generate_type_mismatch_tests(endpoint))
        endpoint_tests.extend(generate_enum_violation_tests(endpoint))
        endpoint_tests.extend(generate_extra_fields_test(endpoint))
        endpoint_tests.extend(generate_malformed_json_tests(endpoint))

        # --- STATEFUL POST-PROCESSING ---
        # Ensures all fuzz tests (including advanced ones) inherit auth and ID context
        for tc in endpoint_tests:
            # 1. Path param injection (use placeholders for stateful chaining)
            if "path_params" not in tc and endpoint.path_params:
                # Use generic resource_id as per orchestrator rules
                tc["path_params"] = {p: "{{resource_id}}" for p in endpoint.path_params}
            
            # 2. Auth propagation
            if "requires_auth" not in tc:
                tc["requires_auth"] = endpoint.requires_auth
            
            # 3. Mark as stateful if it needs auth or specific IDs
            if tc.get("requires_auth") or endpoint.path_params:
                tc["requires_stateful"] = True

        all_fuzz_cases.extend(endpoint_tests)

    # Auth chaining fuzz (Signup -> Login with same payload)
    all_fuzz_cases.extend(_generate_auth_chain_fuzz(endpoints))

    # --- AI ENHANCEMENT ---
    if use_ai:
        try:
            ai_cases, tokens = await generate_fuzz_tests_ai(spec, rule_based_cases=all_fuzz_cases)
            all_fuzz_cases.extend(ai_cases)
            logger.info("Integrated %d AI fuzz cases", len(ai_cases))
        except Exception as e:
            logger.error("AI Fuzz enhancement failed: %s", e)

    # Apply dependency orchestrator — annotates with:
    #   execution_order, depends_on, skip_if_missing, extract, endpoint_roles
    # This ensures:
    #   - Auth-acquiring fuzz (UNAUTHORIZED) runs before protected fuzz
    #   - RESOURCE_WITH_ID fuzz is deprioritized until an ID is known
    annotated = build_execution_plan(endpoints, all_fuzz_cases)

    # --- FUZZ SPECIFIC TIE-BREAKER ---
    # Prioritize Signup/Register over Login/Signin within the same priority bucket
    def _fuzz_tie_breaker(tc: dict):
        order = tc.get("execution_order", 5)
        path = tc.get("endpoint_path", "").lower()
        sub_order = 5
        if any(kw in path for kw in ("register", "signup", "sign-up")):
            sub_order = 0
        elif any(kw in path for kw in ("login", "signin", "sign-in", "auth/token")):
            sub_order = 1
        return (order, sub_order, path, tc.get("method", ""))

    annotated.sort(key=_fuzz_tie_breaker)

    # Split into public/protected for backward-compatible return format
    plan = {
        "public_tests": [],
        "protected_tests": [],
        "annotated_tests": annotated,  # full ordered + annotated list
    }
    for tc in annotated:
        if tc.get("requires_auth"):
            plan["protected_tests"].append(tc)
        else:
            plan["public_tests"].append(tc)

    return plan