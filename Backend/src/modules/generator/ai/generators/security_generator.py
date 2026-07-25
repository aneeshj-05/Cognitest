"""
AI-only OWASP API Security Top 10 2023 test generator.

This module intentionally does not merge or fall back to the rule-based
security engine. It follows the contract generator shape: global planning,
per-operation AI calls, strict normalization, validation, dedupe, and ordering.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from src.modules.generator.spec_parser import Endpoint, extract_endpoints
from src.modules.generator.ai.client import ai_client
from src.modules.generator.ai.prompts.security import (
    GLOBAL_SECURITY_PLANNER_SYSTEM,
    OWASP_API_TOP_10_2023,
    SECURITY_OPERATION_SYSTEM,
    build_global_security_planning_prompt,
    build_security_operation_prompt,
)
from src.modules.generator.ai.utils import prune_schema_for_ai

logger = logging.getLogger(__name__)

_AI_CONCURRENCY = 4
_MAX_RETRIES = 3
_GLOBAL_MAX_TOKENS = 8192
_OPERATION_MAX_TOKENS = 8192
_PLANNER_ENDPOINTS_PER_CHUNK = 8

_AUTH_PATH_HINTS = ("auth", "login", "signin", "signup", "register", "token", "session", "otp", "reset")
_ADMIN_PATH_HINTS = ("admin", "internal", "manage", "management", "superuser", "staff", "system", "root")
_BUSINESS_FLOW_HINTS = (
    "checkout", "payment", "pay", "transfer", "booking", "order", "cart",
    "signup", "register", "reset", "otp", "verify", "ticket", "inventory",
)
_SSRF_FIELD_HINTS = ("url", "uri", "callback", "webhook", "redirect", "avatar", "image", "import", "fetch", "source")
_SENSITIVE_FIELD_HINTS = (
    "password", "token", "secret", "key", "ssn", "card", "cvv", "pin",
    "role", "permission", "is_admin", "isadmin", "owner", "tenant",
)


class SecurityAIGenerationError(RuntimeError):
    """Raised when AI-only security generation cannot produce complete coverage."""


def _is_non_retryable_ai_error(exc: Exception) -> bool:
    """Return True for provider failures that another retry cannot fix."""
    msg = str(exc).lower()
    markers = (
        "credit balance is too low",
        "insufficient_quota",
        "billing",
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "invalid api key",
        "api key",
        "not enough credits",
    )
    return any(marker in msg for marker in markers)


def _operation_key(ep: Endpoint) -> str:
    return f"{ep.method.upper()} {ep.path}"


def _schema_field_names(schema: Any) -> list[str]:
    names: list[str] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        props = node.get("properties")
        if isinstance(props, dict):
            for name, child in props.items():
                names.append(str(name))
                walk(child)
        items = node.get("items")
        if isinstance(items, dict):
            walk(items)
        for key in ("allOf", "oneOf", "anyOf"):
            values = node.get(key)
            if isinstance(values, list):
                for child in values:
                    walk(child)

    walk(schema)
    return names


def _matching_fields(fields: list[str], hints: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for field in fields:
        low = field.lower()
        if any(hint in low for hint in hints):
            out.append(field)
    return out


def _endpoint_descriptor(ep: Endpoint) -> dict[str, Any]:
    request_fields = _schema_field_names(ep.body_schema)
    response_fields = _schema_field_names(ep.response_schema)
    all_fields = request_fields + response_fields + [p.get("name", "") for p in ep.query_params]
    path_lower = ep.path.lower()

    return {
        "operation_key": _operation_key(ep),
        "path": ep.path,
        "method": ep.method.upper(),
        "requires_auth": ep.requires_auth,
        "path_params": ep.path_params,
        "query_params": ep.query_params,
        "body_schema": prune_schema_for_ai(ep.body_schema),
        "response_schema": prune_schema_for_ai(ep.response_schema),
        "status_codes": ep.status_codes,
        "content_type": getattr(ep, "content_type", "application/json"),
        "security_hints": {
            "auth_or_session_endpoint": any(h in path_lower for h in _AUTH_PATH_HINTS),
            "admin_or_privileged_endpoint": any(h in path_lower for h in _ADMIN_PATH_HINTS),
            "sensitive_business_flow": any(h in path_lower for h in _BUSINESS_FLOW_HINTS),
            "has_object_identifier": bool(ep.path_params),
            "has_request_body": bool(ep.body_schema),
            "has_query_params": bool(ep.query_params),
            "ssrf_candidate_fields": _matching_fields(all_fields, _SSRF_FIELD_HINTS),
            "sensitive_property_fields": _matching_fields(all_fields, _SENSITIVE_FIELD_HINTS),
        },
    }


def _coerce_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in ("coverage", "coverage_items", "tests", "test_cases", "cases", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _usage_tokens(result: dict[str, Any]) -> int:
    usage = result.get("usage") or {}
    return int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)


def _normalise_owasp_id(value: Any) -> str:
    raw = str(value or "").strip().upper()
    aliases = {
        "A01": "API1:2023",
        "A1": "API1:2023",
        "API1": "API1:2023",
        "API01": "API1:2023",
        "A02": "API2:2023",
        "A2": "API2:2023",
        "API2": "API2:2023",
        "API02": "API2:2023",
        "A03": "API3:2023",
        "A3": "API3:2023",
        "API3": "API3:2023",
        "API03": "API3:2023",
        "A04": "API4:2023",
        "A4": "API4:2023",
        "API4": "API4:2023",
        "API04": "API4:2023",
        "A05": "API5:2023",
        "A5": "API5:2023",
        "API5": "API5:2023",
        "API05": "API5:2023",
        "A06": "API6:2023",
        "A6": "API6:2023",
        "API6": "API6:2023",
        "API06": "API6:2023",
        "A07": "API7:2023",
        "A7": "API7:2023",
        "API7": "API7:2023",
        "API07": "API7:2023",
        "A08": "API8:2023",
        "A8": "API8:2023",
        "API8": "API8:2023",
        "API08": "API8:2023",
        "A09": "API9:2023",
        "A9": "API9:2023",
        "API9": "API9:2023",
        "API09": "API9:2023",
        "A10": "API10:2023",
        "API10": "API10:2023",
    }
    if raw in OWASP_API_TOP_10_2023:
        return raw
    return aliases.get(raw, "")


def _expected_status_for(owasp_id: str, provided: Any) -> int:
    try:
        status = int(provided)
        if 100 <= status <= 599:
            return status
    except (TypeError, ValueError):
        pass
    if owasp_id in ("API1:2023", "API5:2023"):
        return 403
    if owasp_id == "API2:2023":
        return 401
    if owasp_id == "API4:2023":
        return 429
    if owasp_id in ("API3:2023", "API7:2023", "API10:2023"):
        return 400
    if owasp_id in ("API8:2023", "API9:2023"):
        return 404
    return 400


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalise_ai_item(
    item: dict[str, Any],
    descriptor: dict[str, Any],
) -> dict[str, Any] | None:
    expected_path = descriptor["path"]
    expected_method = descriptor["method"]
    path = item.get("endpoint_path") or item.get("path")
    method = str(item.get("method") or "").upper()

    if path != expected_path or method != expected_method:
        logger.warning(
            "[AI][Security] Dropping hallucinated test for %s %s while normalizing %s",
            method, path, descriptor["operation_key"],
        )
        return None

    owasp_id = _normalise_owasp_id(item.get("owasp_id") or item.get("owasp_category"))
    if not owasp_id:
        logger.warning("[AI][Security] Dropping test with unknown OWASP category: %r", item)
        return None

    assertions = item.get("assertions")
    if not isinstance(assertions, list):
        assertions = []

    metadata = _as_dict(item.get("metadata"))
    auth_negative = bool(item.get("auth_negative"))
    auth_type = item.get("auth_type")
    if auth_type is None:
        auth_type = "missing" if auth_negative else None

    mutation_meta = _as_dict(item.get("mutation_meta"))
    if auth_negative:
        mutation_meta["auth_removed"] = True

    requires_stateful = bool(item.get("requires_stateful")) or owasp_id in ("API1:2023", "API5:2023")
    requires_auth = bool(item.get("requires_auth")) or bool(descriptor.get("requires_auth")) or requires_stateful

    return {
        "id": str(item.get("id") or uuid.uuid4()),
        "name": str(item.get("name") or f"{owasp_id}: {expected_method} {expected_path}"),
        "test_type": "Security",
        "category": "SECURITY",
        "owasp_category": owasp_id,
        "owasp_id": owasp_id,
        "endpoint_path": expected_path,
        "method": expected_method,
        "expected_status": _expected_status_for(owasp_id, item.get("expected_status")),
        "description": str(item.get("description") or OWASP_API_TOP_10_2023[owasp_id]),
        "ai_explanation": item.get("ai_explanation"),
        "headers": _as_dict(item.get("headers")),
        "query_params": _as_dict(item.get("query_params") or item.get("request_query")),
        "request_body": _as_dict(item.get("request_body") or item.get("body")),
        "path_params": _as_dict(item.get("path_params")),
        "assertions": assertions,
        "requires_auth": requires_auth,
        "requires_stateful": requires_stateful,
        "auth_negative": auth_negative,
        "generation_source": "AI",
        **({"auth_type": auth_type} if auth_type else {}),
        **({"mutation_meta": mutation_meta} if mutation_meta else {}),
        "metadata": {
            **metadata,
            "owasp_id": owasp_id,
            "owasp_name": OWASP_API_TOP_10_2023[owasp_id],
            "security_intent": item.get("security_intent") or item.get("intent") or "",
            "ai_coverage_rationale": item.get("ai_coverage_rationale") or item.get("rationale") or "",
            "operation_key": descriptor["operation_key"],
        },
    }


def _deduplicate(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for case in cases:
        key = (
            str(case.get("endpoint_path")),
            str(case.get("method")),
            str(case.get("owasp_category")),
            str(case.get("name")),
            json.dumps(case.get("path_params") or {}, sort_keys=True, default=str),
            json.dumps(case.get("query_params") or {}, sort_keys=True, default=str),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(case)
    return unique


def _assign_execution_order(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order = {
        "API2:2023": 1,
        "API3:2023": 2,
        "API7:2023": 3,
        "API4:2023": 4,
        "API6:2023": 5,
        "API8:2023": 6,
        "API9:2023": 7,
        "API10:2023": 8,
        "API1:2023": 20,
        "API5:2023": 21,
    }
    cases.sort(
        key=lambda tc: (
            bool(tc.get("requires_stateful")),
            order.get(str(tc.get("owasp_category")), 99),
            str(tc.get("endpoint_path")),
            str(tc.get("method")),
            str(tc.get("name")),
        )
    )
    for idx, case in enumerate(cases):
        case["execution_order"] = idx
    return cases


async def _call_global_planner(
    descriptors: list[dict[str, Any]],
    spec_title: str,
    tenant_id: str = "",
) -> tuple[dict[str, list[dict[str, Any]]], int]:
    plan: dict[str, list[dict[str, Any]]] = {}
    total_tokens = 0

    async def call_for_chunk(chunk: list[dict[str, Any]], label: str) -> None:
        nonlocal total_tokens
        valid_keys = {d["operation_key"] for d in chunk}
        endpoints_json = json.dumps(chunk, separators=(",", ":"), default=str)
        system_blocks, prompt_blocks = build_global_security_planning_prompt(endpoints_json, spec_title)
        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                result = await ai_client.generate_json(
                    prompt=prompt_blocks,
                    system=system_blocks,
                    max_tokens=_GLOBAL_MAX_TOKENS,
                    temperature=0.0,
                    tenant_id=tenant_id,
                )
                total_tokens += _usage_tokens(result)
                raw_items = _coerce_list(result.get("data"))

                for raw in raw_items:
                    op_key = str(raw.get("operation_key") or "")
                    if op_key not in valid_keys:
                        logger.warning("[AI][Security] Ignoring plan for unknown operation_key=%s", op_key)
                        continue
                    coverage_items: list[dict[str, Any]] = []
                    for item in _coerce_list(raw.get("coverage_items")):
                        owasp_id = _normalise_owasp_id(item.get("owasp_id") or item.get("owasp_category"))
                        if not owasp_id:
                            continue
                        try:
                            min_tests = int(item.get("min_tests") or 1)
                        except (TypeError, ValueError):
                            min_tests = 1
                        coverage_items.append({
                            "owasp_id": owasp_id,
                            "owasp_name": OWASP_API_TOP_10_2023[owasp_id],
                            "min_tests": max(1, min(6, min_tests)),
                            "rationale": str(item.get("rationale") or raw.get("endpoint_rationale") or ""),
                        })
                    if coverage_items:
                        plan[op_key] = coverage_items

                missing_in_chunk = [d["operation_key"] for d in chunk if d["operation_key"] not in plan]
                if not missing_in_chunk:
                    return
                last_error = SecurityAIGenerationError(
                    f"{label} omitted endpoint(s): {', '.join(missing_in_chunk[:10])}"
                )
                logger.warning("[AI][Security] Planner %s attempt %d/%d omitted %d endpoint(s)",
                               label, attempt + 1, _MAX_RETRIES, len(missing_in_chunk))
            except Exception as exc:
                last_error = exc
                if _is_non_retryable_ai_error(exc):
                    raise SecurityAIGenerationError(
                        f"AI security planner cannot continue: {exc}"
                    ) from exc
                logger.warning("[AI][Security] Planner %s attempt %d/%d failed: %s",
                               label, attempt + 1, _MAX_RETRIES, exc)

            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(2.0 ** attempt)

        if last_error:
            logger.warning("[AI][Security] Planner %s exhausted retries: %s", label, last_error)

    chunks = [
        descriptors[i:i + _PLANNER_ENDPOINTS_PER_CHUNK]
        for i in range(0, len(descriptors), _PLANNER_ENDPOINTS_PER_CHUNK)
    ]
    for idx, chunk in enumerate(chunks):
        await call_for_chunk(chunk, f"chunk[{idx}]")

    # A large spec can still cause an LLM to omit an operation inside a chunk.
    # Retry omitted operations one-by-one before failing loudly.
    missing = [d["operation_key"] for d in descriptors if d["operation_key"] not in plan]
    for op_key in list(missing):
        descriptor = next(d for d in descriptors if d["operation_key"] == op_key)
        await call_for_chunk([descriptor], f"single[{op_key}]")

    missing = [d["operation_key"] for d in descriptors if d["operation_key"] not in plan]
    if missing:
        raise SecurityAIGenerationError(
            "AI security planner did not return coverage for endpoint(s): "
            + ", ".join(missing[:10])
        )

    return plan, total_tokens


async def _call_endpoint_generator(
    descriptor: dict[str, Any],
    coverage_items: list[dict[str, Any]],
    spec_title: str,
    semaphore: asyncio.Semaphore,
    tenant_id: str = "",
) -> tuple[list[dict[str, Any]], int]:
    system_blocks, prompt_blocks = build_security_operation_prompt(descriptor, coverage_items, spec_title)
    last_error: Exception | None = None

    async with semaphore:
        for attempt in range(_MAX_RETRIES):
            try:
                result = await ai_client.generate_json(
                    prompt=prompt_blocks,
                    system=system_blocks,
                    max_tokens=_OPERATION_MAX_TOKENS,
                    temperature=0.1,
                    tenant_id=tenant_id,
                )
                tokens = _usage_tokens(result)
                raw_items = _coerce_list(result.get("data"))
                cases = [
                    tc for tc in (
                        _normalise_ai_item(item, descriptor)
                        for item in raw_items
                    )
                    if tc is not None
                ]
                if not cases:
                    raise SecurityAIGenerationError(
                        f"AI returned no valid security tests for {descriptor['operation_key']}"
                    )
                return cases, tokens
            except Exception as exc:
                last_error = exc
                if _is_non_retryable_ai_error(exc):
                    raise SecurityAIGenerationError(
                        f"AI security generation cannot continue for {descriptor['operation_key']}: {exc}"
                    ) from exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(2.0 ** attempt)

    raise SecurityAIGenerationError(
        f"AI security generation failed for {descriptor['operation_key']}: {last_error}"
    )


def _validate_endpoint_coverage(
    descriptors: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> None:
    covered = {(case["method"], case["endpoint_path"]) for case in cases}
    missing = [
        d["operation_key"]
        for d in descriptors
        if (d["method"], d["path"]) not in covered
    ]
    if missing:
        raise SecurityAIGenerationError(
            "AI security generation produced no valid tests for endpoint(s): "
            + ", ".join(missing[:10])
        )


async def generate_security_tests_ai(
    spec: dict[str, Any],
    rule_based_cases: list[dict] | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], int]:
    """
    Generate OWASP API Security Top 10 2023 tests using AI only.
    Supports Anthropic Batch API execution for high throughput and cost savings.
    """
    del rule_based_cases

    if not ai_client.is_available:
        raise SecurityAIGenerationError(
            "AI security generation requires ANTHROPIC_API_KEY; no rule-based fallback is used."
        )

    endpoints = extract_endpoints(spec)
    if not endpoints:
        raise SecurityAIGenerationError("No endpoints found in the OpenAPI/Swagger spec.")

    spec_title = spec.get("info", {}).get("title", "API") if isinstance(spec.get("info"), dict) else "API"
    descriptors = [_endpoint_descriptor(ep) for ep in endpoints]
    descriptors.sort(key=lambda d: d["operation_key"])

    logger.info("[AI][Security] Built %d endpoint descriptors (use_batch=%s)", len(descriptors), use_batch)

    plan, total_tokens = await _call_global_planner(descriptors, spec_title, tenant_id=tenant_id)
    logger.info("[AI][Security] Global planner returned coverage for %d endpoints", len(plan))

    all_cases: list[dict[str, Any]] = []
    failures: list[str] = []

    if use_batch and len(descriptors) > 0:
        batch_requests = []
        for idx, descriptor in enumerate(descriptors):
            system_blocks, prompt_blocks = build_security_operation_prompt(
                descriptor, plan[descriptor["operation_key"]], spec_title
            )
            req = ai_client.prepare_batch_request(
                custom_id=f"sec-{idx}",
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=_OPERATION_MAX_TOKENS,
                temperature=0.1,
            )
            batch_requests.append(req)

        results_by_id, _ = await ai_client.execute_batch_with_retry(
            batch_requests, on_status_update=on_status_update
        )

        for idx, descriptor in enumerate(descriptors):
            res = results_by_id.get(f"sec-{idx}", {})
            if "error" in res:
                failures.append(f"{descriptor['operation_key']}: {res['error']}")
                continue
            usage = res.get("usage", {})
            total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            raw_items = _coerce_list(res.get("data"))
            cases = [
                tc for tc in (
                    _normalise_ai_item(item, descriptor)
                    for item in raw_items
                )
                if tc is not None
            ]
            if not cases:
                failures.append(f"{descriptor['operation_key']}: AI returned no valid security tests")
            else:
                all_cases.extend(cases)

        if failures:
            logger.warning("[AI][Security] Batch had %d failures: %s", len(failures), " | ".join(failures[:5]))
            # If some failed, don't fail the entire suite if we generated valid tests for most endpoints
            if not all_cases and failures:
                raise SecurityAIGenerationError(
                    "AI security generation failed for endpoint(s): " + " | ".join(failures[:5])
                )
    else:
        semaphore = asyncio.Semaphore(_AI_CONCURRENCY)
        tasks = [
            _call_endpoint_generator(
                descriptor,
                plan[descriptor["operation_key"]],
                spec_title,
                semaphore,
            )
            for descriptor in descriptors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for descriptor, result in zip(descriptors, results):
            if isinstance(result, BaseException):
                failures.append(f"{descriptor['operation_key']}: {result}")
                continue
            cases, tokens = result
            total_tokens += tokens
            all_cases.extend(cases)

        if failures:
            raise SecurityAIGenerationError(
                "AI security generation failed for endpoint(s): " + " | ".join(failures[:5])
            )

    all_cases = _deduplicate(all_cases)
    try:
        _validate_endpoint_coverage(descriptors, all_cases)
    except SecurityAIGenerationError as exc:
        if not all_cases:
            raise exc
        logger.warning("[AI][Security] %s — proceeding with partial coverage (%d tests generated)", exc, len(all_cases))
    all_cases = _assign_execution_order(all_cases)

    logger.info("[AI][Security] Final AI-only suite: %d tests (%d tokens)", len(all_cases), total_tokens)
    return all_cases, total_tokens
