"""
Test case generation entry point.

Routes each test_type to the appropriate engine:
  - Security  → OWASP-based security engine (rule-based)
  - Fuzz      → fuzz engine (rule-based)
  - Negative  → negative engine (rule-based)
  - Functional → rule-based engine, optionally AI-enhanced via Claude
  - Full Coverage → all of the above combined
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from src.modules.generator.engines import (
    generate_functional_tests,
    generate_functional_tests_enhanced,
    generate_negative_tests,
    generate_security_tests,
    generate_fuzz_tests,
)
from src.modules.generator.engines.negative.core import TokenMutator

logger = logging.getLogger(__name__)

def _cap(cases: list[dict], max_tests: int | None) -> list[dict]:
    if max_tests and max_tests > 0:
        return cases[:max_tests]
    return cases


def classify_status(code: int) -> str:
    if code == 401:
        return "auth"
    if code == 422:
        return "validation"
    if code == 400:
        return "schema"
    if code == 404:
        return "not_found"
    if code == 429:
        return "rate_limit"
    return "unknown"


def _default_reason_for_status(status: int) -> str:
    return {
        400: "Malformed request body",
        401: "Unauthorized",
        404: "Resource not found",
        422: "Validation failure",
        429: "Rate limit exceeded",
    }.get(status, f"Expected HTTP {status}")


def _derive_failure_category(statuses: list[int], explicit: Any = None) -> str:
    valid = {"validation", "auth", "schema", "rate_limit", "not_found"}
    explicit_val = str(explicit or "").strip().lower()
    if explicit_val in valid:
        return explicit_val
    if not statuses:
        return ""
    if 422 in statuses:
        return "validation"
    if 401 in statuses:
        return "auth"
    if 404 in statuses:
        return "not_found"
    if 429 in statuses:
        return "rate_limit"
    if 400 in statuses:
        return "schema"
    if any(code >= 400 for code in statuses):
        return "schema"
    return ""


def _expected_entries_for_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    raw_expected = case.get("expected")
    entries: list[dict[str, Any]] = []

    if isinstance(raw_expected, list):
        for item in raw_expected:
            if not isinstance(item, dict):
                continue
            try:
                status = int(item.get("status"))
            except (TypeError, ValueError):
                continue
            reason = str(item.get("reason") or _default_reason_for_status(status)).strip()
            entries.append({"status": status, "reason": reason})
    if entries:
        return entries

    raw_statuses = case.get("expected_status")
    if isinstance(raw_statuses, list):
        values = raw_statuses
    else:
        values = [raw_statuses]

    for value in values:
        try:
            status = int(value)
        except (TypeError, ValueError):
            continue
        entries.append({"status": status, "reason": _default_reason_for_status(status)})

    return entries


def _auth_type_for_case(case: dict[str, Any]) -> str:
    auth_type = str(case.get("auth_type") or "").strip().lower()
    if auth_type:
        return auth_type

    auth_marker = (
        str(case.get("sub_category") or case.get("subCategory") or "").upper() == "AUTH_FAILURE"
        or str(case.get("mutation_type") or "").upper() in {"AUTH_MISSING", "AUTH_INVALID"}
        or bool(case.get("auth_negative"))
    )
    if not auth_marker:
        return ""

    name = str(case.get("name") or "").lower()
    description = str(case.get("description") or "").lower()
    if "expired" in name or "expired" in description:
        return "expired"
    if "invalid" in name or "invalid" in description:
        return "invalid"
    return "missing"


def _apply_auth_type_policy(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            normalized.append(case)
            continue

        expected_entries = _expected_entries_for_case(case)
        if expected_entries:
            case["expected"] = expected_entries
            expected_statuses = [int(item["status"]) for item in expected_entries]
            failure_category = _derive_failure_category(
                expected_statuses,
                case.get("failure_category"),
            )
            if failure_category:
                case["failure_category"] = failure_category

        auth_type = _auth_type_for_case(case)
        if auth_type:
            case["auth_type"] = auth_type

        request_headers = dict(case.get("request_headers") or case.get("headers") or {})
        headers = dict(case.get("headers") or request_headers)

        if auth_type == "missing":
            request_headers = {
                k: v for k, v in request_headers.items()
                if str(k).lower() != "authorization"
            }
            headers = {
                k: v for k, v in headers.items()
                if str(k).lower() != "authorization"
            }
        elif auth_type == "invalid":
            invalid_header = TokenMutator.malformed()["Authorization"]
            request_headers["Authorization"] = invalid_header
            headers["Authorization"] = invalid_header
        elif auth_type == "expired":
            expired_header = TokenMutator.expired()["Authorization"]
            request_headers["Authorization"] = expired_header
            headers["Authorization"] = expired_header

        if request_headers or "request_headers" in case:
            case["request_headers"] = request_headers
        if headers or "headers" in case:
            case["headers"] = headers

        normalized.append(case)

    return normalized


# ---------------------------------------------------------------------------
# Mock data templates per test type (for engines not yet implemented)
# ---------------------------------------------------------------------------

_MOCK_CASES: dict[str, list[dict[str, Any]]] = {
    "Functional": [
        {
            "name": "Should return 200 for valid GET request",
            "method": "GET",
            "endpoint_path": "/api/resource",
            "expected_status": 200,
            "description": "Verifies the happy-path GET response.",
        }
    ],
    "Fuzz": [
        {
            "name": "Fuzz: random string in ID field",
            "method": "GET",
            "endpoint_path": "/api/resource/@@RANDOM_STRING@@",
            "expected_status": 400,
            "description": "Sends a random string as the resource ID.",
        }
    ],
}


async def _ai_generate(
    spec: dict[str, Any], test_type: str, max_tests: int = 15
) -> tuple[list[dict], int]:
    """Call Claude to generate enriched test cases. Returns (cases, tokens_used)."""
    from src.modules.generator.ai.client import ai_client
    from src.modules.generator.spec_parser import extract_endpoints

    endpoints = extract_endpoints(spec)
    endpoints_summary = [
        {
            "path": ep.path,
            "method": ep.method,
            **({"request_body_schema": ep.body_schema} if ep.body_schema else {}),
            **({"query_params": ep.query_params} if ep.query_params else {}),
            **({"path_params": ep.path_params} if ep.path_params else {}),
            **({"response_schema": ep.response_schema} if ep.response_schema else {}),
        }
        for ep in endpoints
    ]

    spec_title = spec.get("info", {}).get("title", "API")

    system_prompt = f"""You are an expert API test engineer. Generate {test_type} test cases for the API.

For each test case, provide COMPLETE, EXECUTABLE data:
- A descriptive name
- endpoint_path, method, expected_status
- request_body (if POST/PUT/PATCH) — use realistic sample data
- headers (always include Content-Type)
- query_params (if applicable)
- path_params (if path has {{param}} placeholders)
- description explaining what the test validates
- category (one of: crud, schema, params, workflow, pagination)
- ai_explanation — a short insight about WHY this test is important
- If the test is an auth-failure case, include auth_type: missing, invalid, or expired.

Return a JSON array of test case objects. Each object must have these fields:
id (UUID string), name, test_type, endpoint_path, method, expected_status (int),
description, category, ai_explanation, headers, query_params, request_body, path_params, assertions.

Generate diverse, thorough test cases covering happy paths, edge cases, and
validation scenarios appropriate for {test_type} testing."""

    user_prompt = f"""API: {spec_title}

Endpoints:
{json.dumps(endpoints_summary, indent=2)}

Generate {max_tests} {test_type} test cases. Return ONLY a JSON array."""

    try:
        res = await ai_client.generate_json(prompt=user_prompt, system=system_prompt, temperature=0.6)
        raw = res["data"]
        cases = [
            {
                "id": tc.get("id", str(uuid.uuid4())),
                "name": tc.get("name", "Unnamed test"),
                "test_type": test_type,
                "endpoint_path": tc.get("endpoint_path", "/"),
                "method": tc.get("method", "GET"),
                "expected_status": tc.get("expected_status", 200),
                "description": tc.get("description"),
                "category": tc.get("category"),
                "ai_explanation": tc.get("ai_explanation"),
                "headers": tc.get("headers"),
                "query_params": tc.get("query_params"),
                "request_body": tc.get("request_body") or tc.get("body"),
                "path_params": tc.get("path_params"),
                "assertions": tc.get("assertions"),
            }
            for tc in raw
        ]
        usage = res.get("usage") or {}
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        return cases, tokens
    except Exception as exc:
        logger.error("AI generation failed, falling back to rule-based: %s", exc)
        return [], 0


def generate_test_payload(
    spec: dict[str, Any],
    test_type: str,
    api_key: str = "",
    use_ai: bool = False,
    max_tests: int | None = None,
) -> tuple[list[dict], str, int]:
    """Synchronous test generation (rule-based only)."""
    test_type = test_type.strip().title()


    if test_type == "Security":
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # This is a bit hacky, but for sync context we might need this
            import nest_asyncio
            nest_asyncio.apply()
        cases = loop.run_until_complete(generate_security_tests(spec))
        cases = _apply_auth_type_policy(cases)
        return _cap(cases, max_tests), "rule_based", 0

    if test_type == "Fuzz":
        loop = asyncio.get_event_loop()
        cases_raw = loop.run_until_complete(generate_fuzz_tests(spec))
        cases = cases_raw.get("public_tests", []) + cases_raw.get("protected_tests", [])
        cases = _apply_auth_type_policy(cases)
        return _cap(cases, max_tests), "rule_based", 0

    if test_type == "Negative":
        loop = asyncio.get_event_loop()
        cases = loop.run_until_complete(generate_negative_tests(spec))
        cases = _apply_auth_type_policy(cases)
        return _cap(cases, max_tests), "rule_based", 0

    if test_type == "Functional" and not use_ai:
        cases = generate_functional_tests(spec)
        cases = _apply_auth_type_policy(cases)
        return _cap(cases, max_tests), "rule_based", 0

    if use_ai:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
        cases, tokens = loop.run_until_complete(_ai_generate(spec, test_type, max_tests=max_tests or 25))
        cases = _apply_auth_type_policy(cases)
        if cases:
            return _cap(cases, max_tests), "ai_enhanced", tokens
        logger.warning("AI returned no cases, falling back to rule-based")

    # Rule-based fallback
    templates = _MOCK_CASES.get(test_type, _MOCK_CASES.get("Functional", []))
    cases = [
        {
            **template,
            "id": str(uuid.uuid4()),
            "test_type": test_type,
        }
        for template in templates
    ]
    cases = _apply_auth_type_policy(cases)
    return cases, "rule_based", 0


async def generate_test_payload_async(
    spec: dict[str, Any],
    test_type: str,
    max_tests: int | None = None,
    use_ai: bool = True,
    admin_config: dict | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], str, int, list[dict]]:
    """Async test generation with AI enhancement via Claude.
    
    Returns (cases, method, total_tokens, token_batches).
    token_batches is a list of {cases, input_tokens, output_tokens} — one per AI call.
    For rule-based generation, token_batches is [].
    Supports Anthropic Batch API execution.
    """
    from src.modules.generator.ai.generators.security_generator import generate_security_tests_ai
    from src.modules.generator.ai.generators.negative_generator import generate_negative_tests_ai
    from src.modules.generator.ai.generators.fuzz_generator_ai import generate_fuzz_tests_ai
    from src.modules.generator.ai.generators.contract_generator_ai import generate_contract_tests_ai

    test_type = test_type.strip().title()


    if test_type == "Functional":
        if use_ai:
            try:
                result = await generate_functional_tests_enhanced(
                    spec, admin_config=admin_config, tenant_id=tenant_id,
                    use_batch=use_batch, on_status_update=on_status_update
                )
                if len(result) == 3:
                    cases, tokens, token_batches = result
                else:
                    cases, tokens = result
                    token_batches = []
            except Exception as e:
                logger.error("AI Functional generation failed, falling back to rule-based: %s", e)
                from src.modules.generator.engines.functional_engine import generate_functional_tests
                cases = generate_functional_tests(spec)
                tokens = 0
                token_batches = []
        else:
            from src.modules.generator.engines.functional_engine import generate_functional_tests
            cases = generate_functional_tests(spec)
            tokens = 0
            token_batches = []
        cases = _apply_auth_type_policy(cases)
        method = "ai_enhanced" if tokens > 0 else "rule_based"
        source_tag = "AI" if tokens > 0 else "RULE"
        for tc in cases:
            if isinstance(tc, dict):
                tc.setdefault("generation_source", source_tag)
        return _cap(cases, max_tests), method, tokens, token_batches

    if test_type == "Security":
        if use_ai:
            try:
                cases, tokens = await generate_security_tests_ai(
                    spec, tenant_id=tenant_id,
                    use_batch=use_batch, on_status_update=on_status_update
                )
                if not cases:
                    raise RuntimeError("AI security generation returned no valid test cases")
                token_batches = [{"cases": cases, "input_tokens": tokens // 4, "output_tokens": tokens - (tokens // 4)}]
            except Exception as e:
                logger.error("AI Security generation failed, falling back to rule-based: %s", e)
                cases = await generate_security_tests(spec)
                tokens = 0
                token_batches = []
        else:
            cases = await generate_security_tests(spec)
            tokens = 0
            token_batches = []
        cases = _apply_auth_type_policy(cases)
        method = "ai_enhanced" if tokens > 0 else "rule_based"
        source_tag = "AI" if tokens > 0 else "RULE"
        for tc in cases:
            if isinstance(tc, dict):
                tc.setdefault("generation_source", source_tag)
        return _cap(cases, max_tests), method, tokens, token_batches

    if test_type == "Negative":
        rule_based = await generate_negative_tests(spec, use_ai=False)
        if use_ai:
            try:
                result = await generate_negative_tests_ai(
                    spec, rule_based_cases=rule_based, tenant_id=tenant_id,
                    use_batch=use_batch, on_status_update=on_status_update
                )
                if len(result) == 3:
                    cases, tokens, token_batches = result
                else:
                    cases, tokens = result
                    token_batches = []
                if not cases:
                    cases = rule_based
                    tokens = 0
                    token_batches = []
            except Exception as e:
                logger.error("AI Negative generation failed, falling back to rule-based: %s", e)
                cases = rule_based
                tokens = 0
                token_batches = []
        else:
            cases = rule_based
            tokens = 0
            token_batches = []
        cases = _apply_auth_type_policy(cases)
        method = "ai_enhanced" if tokens > 0 else "rule_based"
        source_tag = "AI" if tokens > 0 else "RULE"
        for tc in cases:
            if isinstance(tc, dict):
                tc.setdefault("generation_source", source_tag)
        return _cap(cases, max_tests), method, tokens, token_batches

    if test_type == "Fuzz":
        plan = await generate_fuzz_tests(spec, use_ai=False)
        rule_based = plan.get("public_tests", []) + plan.get("protected_tests", [])
        if use_ai:
            try:
                result = await generate_fuzz_tests_ai(
                    spec, rule_based_cases=rule_based, admin_config=admin_config,
                    tenant_id=tenant_id, use_batch=use_batch, on_status_update=on_status_update
                )
                if len(result) == 3:
                    cases, tokens, token_batches = result
                else:
                    cases, tokens = result
                    token_batches = []
                if not cases:
                    cases = rule_based
                    tokens = 0
                    token_batches = []
            except Exception as e:
                logger.error("AI Fuzz generation failed, falling back to rule-based: %s", e)
                cases = rule_based
                tokens = 0
                token_batches = []
        else:
            cases = rule_based
            tokens = 0
            token_batches = []
        cases = _apply_auth_type_policy(cases)
        method = "ai_enhanced" if tokens > 0 else "rule_based"
        source_tag = "AI" if tokens > 0 else "RULE"
        for tc in cases:
            if isinstance(tc, dict):
                tc.setdefault("generation_source", source_tag)
        return _cap(cases, max_tests), method, tokens, token_batches

    if test_type == "Contract":
        if use_ai:
            try:
                cases, tokens = await generate_contract_tests_ai(
                    spec, tenant_id=tenant_id,
                    use_batch=use_batch, on_status_update=on_status_update
                )
                logger.info("[CONTRACT] AI returned %d raw cases (tokens=%d)", len(cases), tokens)
                token_batches = [{"cases": cases, "input_tokens": tokens // 4, "output_tokens": tokens - (tokens // 4)}]
            except Exception as e:
                logger.error("AI Contract generation failed, falling back to rule-based: %s", e)
                cases = []
                tokens = 0
                token_batches = []
        else:
            cases = []
            tokens = 0
            token_batches = []
        if not cases:
            # Fallback to rule-based contract generator
            from src.modules.generator.engines.contract.contract_generator import generate_contract_test_cases
            cases = generate_contract_test_cases(spec)
            tokens = 0
            token_batches = []
            logger.info("[CONTRACT] AI empty/unavailable — rule-based fallback: %d cases", len(cases))

        cases = _apply_auth_type_policy(cases)
        method = "ai_enhanced" if tokens > 0 else "rule_based"
        source_tag = "AI" if tokens > 0 else "RULE"
        for tc in cases:
            if isinstance(tc, dict):
                tc["generation_source"] = source_tag
        capped = _cap(cases, max_tests)
        logger.info(
            "[CONTRACT] source=%s total=%d after_cap=%d (max_tests=%s)",
            method, len(cases), len(capped), max_tests,
        )
        return capped, method, tokens, token_batches

    # Fallback
    cases, method, tokens = await asyncio.to_thread(
        generate_test_payload, spec, test_type, "", use_ai, max_tests
    )
    cases = _apply_auth_type_policy(cases)
    source_tag = "AI" if tokens > 0 else "RULE"
    for tc in cases:
        if isinstance(tc, dict):
            tc.setdefault("generation_source", source_tag)
    return _cap(cases, max_tests), method, tokens, []


async def generate_test_payload_async_with_ai(
    spec: dict[str, Any],
    test_type: str,
    max_tests: int | None = None,
) -> tuple[list[dict], str, int]:
    """Async test generation specifically calling AI engine."""
    cases, tokens = await _ai_generate(spec, test_type, max_tests or 25)
    cases = _apply_auth_type_policy(cases)
    return _cap(cases, max_tests), "ai_enhanced", tokens
