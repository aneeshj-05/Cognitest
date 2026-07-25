"""
AI-powered fuzz test generator — spec-driven, parallel chunk processing.

Design:
- Reads raw OpenAPI/Swagger spec endpoints directly (no rule-based baseline).
- Groups endpoints into resource-aware chunks (same resource family together).
- All chunks dispatched in parallel via asyncio.gather().
- ai_client._lock serializes actual HTTP calls, preventing 429s.
- Results merged and annotated with requires_auth, requires_stateful.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from typing import Any

from src.modules.generator.spec_parser import extract_endpoints
from src.modules.generator.ai.client import ai_client
from src.modules.generator.ai.prompts.fuzz import build_fuzz_chunk_prompt
from src.modules.generator.ai.utils import prune_schema_for_ai

logger = logging.getLogger(__name__)

# ── Tunables ────────────────────────────────────────────────────────────────
MAX_OUTPUT_TOKENS = 3500    # Claude max allowed before TPM errors
MAX_ENDPOINTS_PER_CHUNK = 3  # small chunks → AI covers every endpoint, never skips
MAX_RETRIES = 3

_ADMIN_PATTERNS = ("/admin", "/management", "/superuser", "/backoffice", "/system/")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _is_admin_route(path: str) -> bool:
    return any(p in path.lower() for p in _ADMIN_PATTERNS)


def _extract_admin_credentials(admin_config: dict | None) -> tuple[str, str] | None:
    if not admin_config:
        return None
    email = admin_config.get("email") or admin_config.get("admin_email") or ""
    password = admin_config.get("password") or admin_config.get("admin_password") or ""
    return (email, password) if (email and password) else None


def _endpoint_to_dict(ep, *, admin_creds: tuple | None = None) -> dict:
    """Serialize endpoint for AI prompt — compact but complete."""
    d = {
        "path":          ep.path,
        "method":        ep.method,
        "requires_auth": ep.requires_auth,
        "path_params":   ep.path_params,
        "query_params":  ep.query_params,
        "body_schema":   prune_schema_for_ai(ep.body_schema),
        "status_codes":  ep.status_codes,
    }
    if _is_admin_route(ep.path):
        d["admin_note"] = (
            f"Admin route — use credentials: {admin_creds[0]}"
            if admin_creds else "Admin route — credentials required"
        )
    return d


def _group_endpoints_into_chunks(endpoints: list, max_per_chunk: int) -> list[list]:
    """
    Group endpoints by resource family, then split into max_per_chunk-sized sub-chunks.
    Auth endpoints do NOT get isolated for fuzz (we want to fuzz them too).
    """
    resource_groups: dict[str, list] = defaultdict(list)
    for ep in endpoints:
        parts = [p for p in ep.path.split("/")
                 if p and not p.startswith("{") and p not in ("api", "v1", "v2")]
        segment = parts[0] if parts else "misc"
        resource_groups[segment].append(ep)

    chunks: list[list] = []
    for segment, eps in resource_groups.items():
        for i in range(0, len(eps), max_per_chunk):
            chunks.append(eps[i: i + max_per_chunk])
    return chunks


def _coerce_to_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return [t for t in data if isinstance(t, dict)]
    if isinstance(data, dict):
        if "raw_text" in data:
            return []
        for key in ("tests", "generated_tests", "cases", "test_cases", "results", "items"):
            if key in data and isinstance(data[key], list):
                return [t for t in data[key] if isinstance(t, dict)]
    return []


# ── Core chunk processor ─────────────────────────────────────────────────────

async def _process_fuzz_chunk(
    chunk_idx: int,
    endpoints: list,
    admin_creds: tuple | None,
    tenant_id: str = "",
) -> tuple[list[dict], int, int]:
    """
    Send one endpoint chunk to the AI for fuzz test generation.
    Returns a list of normalized fuzz test case dicts.
    """
    chunk_label = f"fuzz_chunk[{chunk_idx}] ({len(endpoints)} endpoints)"

    eps_data = [_endpoint_to_dict(ep, admin_creds=admin_creds) for ep in endpoints]
    endpoints_json = json.dumps(eps_data, separators=(",", ":"), default=str)

    admin_hint = ""
    if admin_creds and any(_is_admin_route(ep.path) for ep in endpoints):
        admin_hint = f"Admin credentials available — email: {admin_creds[0]}"

    system_blocks, prompt_blocks = build_fuzz_chunk_prompt(endpoints_json, admin_hint=admin_hint)

    last_error_was_429 = False

    for attempt in range(MAX_RETRIES):
        try:
            if attempt > 0:
                if last_error_was_429:
                    backoff = 35.0
                    logger.info("[AI][Fuzz] %s rate limit retry %d/%d — waiting %.1fs for token bucket",
                                chunk_label, attempt + 1, MAX_RETRIES, backoff)
                else:
                    backoff = 2.0 ** attempt
                    logger.info("[AI][Fuzz] %s retry %d/%d — waiting %.1fs",
                                chunk_label, attempt + 1, MAX_RETRIES, backoff)
                await asyncio.sleep(backoff)

            last_error_was_429 = False
            logger.info("[AI][Fuzz] %s — calling AI (attempt %d/%d)",
                        chunk_label, attempt + 1, MAX_RETRIES)

            result = await ai_client.generate_json(
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.4,  # slightly higher for diverse fuzz payloads
                tenant_id=tenant_id,
            )

            usage = result.get("usage") or {}
            in_tok = usage.get("input_tokens", 0) if isinstance(usage, dict) else 0
            out_tok = usage.get("output_tokens", 0) if isinstance(usage, dict) else 0
            logger.info("[AI][Fuzz] %s → tokens in=%d out=%d", chunk_label, in_tok, out_tok)

            raw = _coerce_to_list(result.get("data"))
            if not raw:
                logger.warning("[AI][Fuzz] %s — AI returned 0 fuzz cases", chunk_label)
                return [], in_tok, out_tok
                return [], 0

            # Build a path→endpoint map for annotation
            ep_map = {ep.path: ep for ep in endpoints}

            normalized: list[dict] = []
            for tc in raw:
                # Normalize path field name
                generated_path = tc.get("path") or tc.get("endpoint_path") or ""
                generated_method = (tc.get("method") or "GET").upper()

                # Validate path is in our spec
                if generated_path not in ep_map:
                    # Try to find the closest match
                    for ep in endpoints:
                        if ep.method.upper() == generated_method and ep.path == generated_path:
                            break
                    else:
                        logger.warning("[AI][Fuzz] %s — hallucinated path '%s', skipping",
                                       chunk_label, generated_path)
                        continue

                ep = ep_map.get(generated_path)
                has_path_params = bool(ep.path_params) if ep else ("{" in generated_path)
                needs_auth = ep.requires_auth if ep else False

                case: dict[str, Any] = {
                    "id":               str(uuid.uuid4()),
                    "name":             tc.get("name") or f"AI Fuzz: {generated_path}",
                    "test_type":        "fuzz",
                    "fuzz_type":        tc.get("fuzz_type") or "RANDOM_STRING",
                    "endpoint_path":    generated_path,
                    "method":           generated_method,
                    "headers":          tc.get("headers") or {"Content-Type": "application/json"},
                    "body":             tc.get("body") or tc.get("request_body"),
                    "query_params":     tc.get("query_params") or {},
                    "path_params":      tc.get("path_params") or {},
                    "expected_status":  tc.get("expected_status") or 400,
                    "expected_behavior": tc.get("expected_behavior") or "Should return 400",
                    "description":      tc.get("description") or "AI generated fuzz test",
                    "ai_explanation":   tc.get("ai_explanation") or "",
                    "requires_auth":    needs_auth,
                    "requires_stateful": needs_auth or has_path_params,
                    "generation_source": "AI",
                }

                if _is_admin_route(generated_path):
                    case["requires_admin_credentials"] = True
                    if admin_creds:
                        case["_admin_email"] = admin_creds[0]
                        case["_admin_password"] = admin_creds[1]
                    else:
                        case["requires_manual_credentials"] = True

                normalized.append(case)

            logger.info("[AI][Fuzz] %s — %d fuzz cases generated", chunk_label, len(normalized))
            return normalized, in_tok, out_tok

        except RuntimeError as exc:
            err_str = str(exc).lower()
            if "rate_limit_error" in err_str or "429" in err_str:
                last_error_was_429 = True
            logger.warning("[AI][Fuzz] %s attempt %d/%d — API error: %s",
                           chunk_label, attempt + 1, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES - 1:
                logger.error("[AI][Fuzz] %s — all retries exhausted", chunk_label)

        except (ConnectionError, TimeoutError, asyncio.TimeoutError) as exc:
            logger.warning("[AI][Fuzz] %s attempt %d/%d — network error: %s",
                           chunk_label, attempt + 1, MAX_RETRIES, exc)
            if attempt == MAX_RETRIES - 1:
                logger.error("[AI][Fuzz] %s — all retries exhausted", chunk_label)

        except (ValueError, KeyError, json.JSONDecodeError, TypeError) as exc:
            logger.error("[AI][Fuzz] Internal error in %s: %s — not retrying", chunk_label, exc)
            break

        except Exception as exc:
            logger.exception("[AI][Fuzz] Unexpected error in %s: %s", chunk_label, exc)
            break

    return [], 0, 0


# ── Public API ───────────────────────────────────────────────────────────────

async def generate_fuzz_tests_ai(
    spec: dict[str, Any],
    rule_based_cases: list[dict] | None = None,
    admin_config: dict | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], int, list[dict]]:
    """
    Generate fuzz test cases directly from the OpenAPI spec — no rule-based baseline.
    Supports Anthropic Batch API execution for high throughput and cost savings.
    """
    if not ai_client.is_available:
        logger.info("[AI][Fuzz] AI not available — skipping AI fuzz generation")
        return [], 0, []

    endpoints = extract_endpoints(spec)
    if not endpoints:
        logger.warning("[AI][Fuzz] No endpoints extracted from spec")
        return [], 0, []

    admin_creds = _extract_admin_credentials(admin_config)
    if admin_creds:
        logger.info("[AI][Fuzz] Admin credentials provided")
    else:
        logger.info("[AI][Fuzz] No admin credentials")

    chunks = _group_endpoints_into_chunks(endpoints, MAX_ENDPOINTS_PER_CHUNK)
    logger.info("[AI][Fuzz] %d endpoints → %d chunks (use_batch=%s)", len(endpoints), len(chunks), use_batch)

    all_cases: list[dict] = []
    token_batches: list[dict] = []

    if use_batch and len(chunks) > 0:
        batch_requests = []
        for idx, chunk in enumerate(chunks):
            eps_data = [_endpoint_to_dict(ep, admin_creds=admin_creds) for ep in chunk]
            endpoints_json = json.dumps(eps_data, separators=(",", ":"), default=str)
            admin_hint = ""
            if admin_creds and any(_is_admin_route(ep.path) for ep in chunk):
                admin_hint = f"Admin credentials available — email: {admin_creds[0]}"
            system_blocks, prompt_blocks = build_fuzz_chunk_prompt(endpoints_json, admin_hint=admin_hint)
            req = ai_client.prepare_batch_request(
                custom_id=f"fuzz-{idx}",
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.4,
            )
            batch_requests.append(req)

        results_by_id, _ = await ai_client.execute_batch_with_retry(
            batch_requests, on_status_update=on_status_update
        )

        for idx, chunk in enumerate(chunks):
            res = results_by_id.get(f"fuzz-{idx}", {})
            raw = _coerce_to_list(res.get("data"))
            usage = res.get("usage", {})
            in_tok = usage.get("input_tokens", 0)
            out_tok = usage.get("output_tokens", 0)

            ep_map = {ep.path: ep for ep in chunk}
            normalized: list[dict] = []
            for tc in raw:
                generated_path = tc.get("path") or tc.get("endpoint_path") or ""
                generated_method = (tc.get("method") or "GET").upper()
                if generated_path not in ep_map:
                    for ep in chunk:
                        if ep.method.upper() == generated_method and ep.path == generated_path:
                            break
                    else:
                        continue

                ep = ep_map.get(generated_path)
                has_path_params = bool(ep.path_params) if ep else ("{" in generated_path)
                needs_auth = ep.requires_auth if ep else False

                case: dict[str, Any] = {
                    "id":               str(uuid.uuid4()),
                    "name":             tc.get("name") or f"AI Fuzz: {generated_path}",
                    "test_type":        "fuzz",
                    "fuzz_type":        tc.get("fuzz_type") or "RANDOM_STRING",
                    "endpoint_path":    generated_path,
                    "method":           generated_method,
                    "headers":          tc.get("headers") or {"Content-Type": "application/json"},
                    "body":             tc.get("body") or tc.get("request_body"),
                    "query_params":     tc.get("query_params") or {},
                    "path_params":      tc.get("path_params") or {},
                    "expected_status":  tc.get("expected_status") or 400,
                    "expected_behavior": tc.get("expected_behavior") or "Should return 400",
                    "description":      tc.get("description") or "AI generated fuzz test",
                    "ai_explanation":   tc.get("ai_explanation") or "",
                    "requires_auth":    needs_auth,
                    "requires_stateful": needs_auth or has_path_params,
                    "generation_source": "AI",
                }
                if _is_admin_route(generated_path):
                    case["requires_admin_credentials"] = True
                    if admin_creds:
                        case["_admin_email"] = admin_creds[0]
                        case["_admin_password"] = admin_creds[1]
                    else:
                        case["requires_manual_credentials"] = True
                normalized.append(case)

            all_cases.extend(normalized)
            token_batches.append({
                "cases": normalized,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
            })

        total_tokens = sum(b["input_tokens"] + b["output_tokens"] for b in token_batches)
        logger.info("[AI][Fuzz] Batch Complete — %d fuzz tests generated from %d chunks", len(all_cases), len(chunks))
        return all_cases, total_tokens, token_batches

    semaphore = asyncio.Semaphore(2)

    async def _sem_process(idx, chunk):
        async with semaphore:
            return await _process_fuzz_chunk(idx, chunk, admin_creds, tenant_id)

    tasks = [_sem_process(idx, chunk) for idx, chunk in enumerate(chunks)]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    for chunk_result in results:
        if isinstance(chunk_result, tuple) and len(chunk_result) == 3:
            cases, in_tok, out_tok = chunk_result
            all_cases.extend(cases)
            token_batches.append({
                "cases":         cases,
                "input_tokens":  in_tok,
                "output_tokens": out_tok,
            })
        elif isinstance(chunk_result, list):
            all_cases.extend(chunk_result)

    total_tokens = sum(b["input_tokens"] + b["output_tokens"] for b in token_batches)
    logger.info("[AI][Fuzz] Complete — %d fuzz tests generated from %d chunks, %d tokens",
                len(all_cases), len(chunks), total_tokens)
    return all_cases, total_tokens, token_batches
