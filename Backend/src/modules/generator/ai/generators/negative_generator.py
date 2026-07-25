"""
AI-powered negative test generator using Claude (Anthropic).
Covers boundary values, invalid inputs, constraint violations.
Refactored to process one endpoint per call to prevent token truncation limits.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from src.modules.generator.spec_parser import extract_endpoints
from src.modules.generator.ai.client import ai_client
from src.modules.generator.ai.prompts.negative import NEGATIVE_SYSTEM, build_negative_prompt
from src.modules.generator.ai.utils import prune_schema_for_ai

logger = logging.getLogger(__name__)

MAX_OUTPUT_TOKENS = 4000
MAX_RETRIES = 3

def _coerce_to_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict):
        if "raw_text" in data:
            return []
        list_vals = [v for v in data.values() if isinstance(v, list)]
        if list_vals:
            return list_vals[0]
        if "test_type" in data or "endpoint_path" in data:
            return [data]
    return []

async def _process_single_endpoint(
    ep_idx: int,
    total: int,
    ep,
    spec_title: str,
    target_count: int,
    examples_json: str,
    tenant_id: str = "",
) -> tuple[list[dict], int]:
    ep_label = f"[{ep_idx+1}/{total}] {ep.method} {ep.path}"
    
    ep_dict = {
        "path": ep.path,
        "method": ep.method,
        "path_params": ep.path_params,
        "query_params": ep.query_params,
        "body_schema": prune_schema_for_ai(ep.body_schema),
        "status_codes": ep.status_codes,
        "requires_auth": ep.requires_auth,
    }
    endpoint_json = json.dumps([ep_dict], indent=2, default=str)
    
    system_blocks, prompt_blocks = build_negative_prompt(endpoint_json, spec_title, target_count=target_count, rule_based_examples=examples_json)
    
    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                backoff = 2.0 ** attempt
                logger.info("[AI][Negative] %s retry %d/%d — waiting %.1fs", ep_label, attempt + 1, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)

            logger.info("[AI][Negative] %s — calling AI (attempt %d/%d)", ep_label, attempt + 1, MAX_RETRIES)

            result = await ai_client.generate_json(
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
                tenant_id=tenant_id,
            )

            usage = result.get("usage") or {}
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            tokens = tokens_in + tokens_out
            
            raw = result.get("data")
            tests = _coerce_to_list(raw)

            if not tests:
                if attempt == MAX_RETRIES - 1:
                    logger.warning("[AI][Negative] %s — AI returned 0 tests after all retries", ep_label)
                continue

            cases = []
            for tc in tests:
                # STRICT VALIDATION: Ensure path and method match the spec
                path = tc.get("endpoint_path") or tc.get("path")
                method = (tc.get("method") or "").upper()
                
                if path != ep.path or method != ep.method.upper():
                    logger.warning("AI hallucinated negative test for %s %s (expected %s %s), skipping", method, path, ep.method, ep.path)
                    continue

                tc.setdefault("id", str(uuid.uuid4()))
                tc.setdefault("test_type", "Negative")
                tc.setdefault("category", "NEGATIVE")
                tc.setdefault("expected_status", 422)
                tc.setdefault("assertions", [])
                tc.setdefault("headers", {"Content-Type": "application/json"})
                tc["generation_source"] = "AI"
                cases.append(tc)

            logger.info("[AI][Negative] %s — %d tests generated", ep_label, len(cases))
            return cases, tokens_in, tokens_out

        except Exception as exc:
            logger.warning("[AI][Negative] %s attempt %d failed: %s", ep_label, attempt + 1, exc)
            if attempt == MAX_RETRIES - 1:
                return [], 0, 0

    return [], 0, 0

async def generate_negative_tests_ai(
    spec: dict[str, Any],
    rule_based_cases: list[dict] | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], int, list[dict]]:
    """
    Generate negative/boundary test cases using Claude.
    Falls back to empty list if AI unavailable.
    Returns: (test_cases, tokens_used, token_batches)
    """
    if not ai_client.is_available:
        logger.info("AI not available — skipping AI negative generation")
        return [], 0, []

    endpoints = extract_endpoints(spec)
    spec_title = spec.get("info", {}).get("title", "API")

    examples_json = ""
    if rule_based_cases:
        cleaned_examples = []
        for tc in rule_based_cases[:5]:
            if isinstance(tc, dict):
                cleaned_examples.append({k: v for k, v in tc.items() if k not in ("id", "uuid")})
        examples_json = json.dumps(cleaned_examples, indent=2, default=str)

    logger.info("[AI][Negative] Dispatching %d endpoint calls (use_batch=%s)", len(endpoints), use_batch)

    all_cases = []
    total_tokens = 0
    token_batches: list[dict] = []

    if use_batch and len(endpoints) > 0:
        batch_requests = []
        for idx, ep in enumerate(endpoints):
            ep_rule_cases = [
                tc for tc in (rule_based_cases or [])
                if (tc.get("endpoint_path") or tc.get("path")) == ep.path 
                and (tc.get("method") or "").upper() == ep.method.upper()
            ]
            target_count = len(ep_rule_cases)
            if target_count == 0:
                target_count = 2

            ep_dict = {
                "path": ep.path,
                "method": ep.method,
                "path_params": ep.path_params,
                "query_params": ep.query_params,
                "body_schema": prune_schema_for_ai(ep.body_schema),
                "status_codes": ep.status_codes,
                "requires_auth": ep.requires_auth,
            }
            endpoint_json = json.dumps([ep_dict], indent=2, default=str)
            system_blocks, prompt_blocks = build_negative_prompt(
                endpoint_json, spec_title, target_count=target_count, rule_based_examples=examples_json
            )
            req = ai_client.prepare_batch_request(
                custom_id=f"neg-{idx}",
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )
            batch_requests.append(req)

        results_by_id, _ = await ai_client.execute_batch_with_retry(
            batch_requests, on_status_update=on_status_update
        )

        for idx, ep in enumerate(endpoints):
            res = results_by_id.get(f"neg-{idx}", {})
            raw = res.get("data")
            usage = res.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            tests = _coerce_to_list(raw)

            cases = []
            for tc in tests:
                path = tc.get("endpoint_path") or tc.get("path")
                method = (tc.get("method") or "").upper()
                if path != ep.path or method != ep.method.upper():
                    logger.warning("AI hallucinated negative test for %s %s (expected %s %s), skipping", method, path, ep.method, ep.path)
                    continue
                tc.setdefault("id", str(uuid.uuid4()))
                tc.setdefault("test_type", "Negative")
                tc.setdefault("category", "NEGATIVE")
                tc.setdefault("expected_status", 422)
                tc.setdefault("assertions", [])
                tc.setdefault("headers", {"Content-Type": "application/json"})
                tc["generation_source"] = "AI"
                cases.append(tc)

            all_cases.extend(cases)
            total_tokens += tokens_in + tokens_out
            token_batches.append({
                "cases": cases,
                "input_tokens": tokens_in,
                "output_tokens": tokens_out,
            })
        logger.info("[AI][Negative] Batch Complete — %d total tests from %d endpoints", len(all_cases), len(endpoints))
        return all_cases, total_tokens, token_batches

    semaphore = asyncio.Semaphore(2)

    async def _sem_process(idx, ep):
        async with semaphore:
            ep_rule_cases = [
                tc for tc in (rule_based_cases or [])
                if (tc.get("endpoint_path") or tc.get("path")) == ep.path 
                and (tc.get("method") or "").upper() == ep.method.upper()
            ]
            target_count = len(ep_rule_cases)
            if target_count == 0:
                target_count = 2
                
            return await _process_single_endpoint(
                ep_idx=idx,
                total=len(endpoints),
                ep=ep,
                spec_title=spec_title,
                target_count=target_count,
                examples_json=examples_json,
                tenant_id=tenant_id,
            )

    tasks = [_sem_process(idx, ep) for idx, ep in enumerate(endpoints)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for cases, tokens_in, tokens_out in results:
        all_cases.extend(cases)
        total_tokens += tokens_in + tokens_out
        token_batches.append({
            "cases":         cases,
            "input_tokens":  tokens_in,
            "output_tokens": tokens_out,
        })

    logger.info("[AI][Negative] Complete — %d total tests from %d endpoint calls", len(all_cases), len(endpoints))
    return all_cases, total_tokens, token_batches