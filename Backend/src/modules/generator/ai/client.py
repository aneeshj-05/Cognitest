"""
LLM client wrapper for AI-powered test generation and failure analysis.

Transport: official anthropic Python SDK (AsyncAnthropic).
Structured JSON output: Claude tool-use forces pre-validated JSON responses,
eliminating all regex/fence extraction from generate_json().

Gracefully degrades when ANTHROPIC_API_KEY is not set.
"""
from __future__ import annotations

import json
import logging
import asyncio
import time

import re
from typing import Any, Optional

import anthropic

from src.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis-backed distributed rate limiter (unchanged)
# ---------------------------------------------------------------------------
_RATE_LIMIT_LUA = """
local last     = tonumber(redis.call('GET', KEYS[1])) or 0
local gap      = tonumber(ARGV[1])
local now      = tonumber(ARGV[2])
local earliest = last + gap
local wake_at  = math.max(earliest, now)
local ttl      = math.ceil(gap * 10)
redis.call('SET', KEYS[1], tostring(wake_at), 'EX', ttl)
return tostring(wake_at)
"""

_CLAUDE_RATE_KEY  = "ratelimit:claude:last_call"

_CLAUDE_GAP       = 1.0



async def _redis_claim_slot(key: str, gap: float) -> float | None:
    try:
        from src.worker.redis_client import get_redis_pool
        pool = await get_redis_pool()
        now = time.time()
        result = await pool.eval(_RATE_LIMIT_LUA, 1, key, str(gap), str(now))
        return float(result)
    except Exception as exc:
        logger.debug("[RateLimit] Redis unavailable, using in-process fallback: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Tool-use schema for generate_json()
# ---------------------------------------------------------------------------
# Forcing Claude to call this tool means the response arrives as a pre-parsed
# Python dict from the SDK — no regex or fence stripping needed.
_JSON_TOOL: list[dict[str, Any]] = [
    {
        "name": "return_json",
        "description": (
            "Return the generated test cases as structured JSON. "
            "Always call this tool with your complete response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "result": {
                    "description": "The generated JSON (array or object).",
                    "type": ["array", "object"],
                }
            },
            "required": ["result"],
        },
    }
]


class AIClient:
    """
    LLM client using the official Anthropic SDK (AsyncAnthropic).

    generate()      — plain text response, model fallback, rate limit, budget check.
    generate_json() — same but uses Claude tool-use to force structured JSON output.
                      No regex/fence extraction needed: the SDK returns pre-parsed data.
    """

    MODELS = [
        "claude-sonnet-4-6",
        "claude-haiku-4-5-20251001",
    ]

    def __init__(self) -> None:
        self.api_key = settings.anthropic_api_key or ""
        self._fallback_lock = asyncio.Lock()
        self._fallback_last_call = 0.0
        self.rate_limit_delay = _CLAUDE_GAP

    @property
    def model(self) -> str:
        return self.MODELS[0]

    @property
    def anthropic_version(self) -> str:
        return "2023-06-01"

    @property
    def is_available(self) -> bool:
        self.api_key = settings.anthropic_api_key or self.api_key
        return bool(self.api_key)

    def _sdk(self) -> anthropic.AsyncAnthropic:
        return anthropic.AsyncAnthropic(api_key=self.api_key, timeout=180.0, max_retries=0)

    async def _rate_limit(self) -> None:
        wake_at = await _redis_claim_slot(_CLAUDE_RATE_KEY, self.rate_limit_delay)
        if wake_at is None:
            async with self._fallback_lock:
                now = time.time()
                earliest = self._fallback_last_call + self.rate_limit_delay
                wake_at = max(earliest, now)
                self._fallback_last_call = wake_at
        sleep_for = wake_at - time.time()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)

    def _build_system(self, system: str | list[dict[str, Any]]) -> str | list[dict[str, Any]]:
        """Append spec-enforcement instruction (injection-mitigation boundary)."""
        _e = (
            "\n\nCRITICAL INSTRUCTION: Generate tests ONLY for the paths, methods, "
            "and fields explicitly described in the delimited spec data provided in "
            "the user message. Do NOT invent endpoints, field names, or parameters "
            "that are not present in the <untrusted_spec_data> blocks."
        )
        return list(system) + [{"type": "text", "text": _e}] if isinstance(system, list) else system + _e

    def _to_sdk_system(self, system: str | list[dict[str, Any]]) -> Any:
        """Convert system to SDK-compatible format."""
        if isinstance(system, list):
            out = []
            for block in system:
                if not (isinstance(block, dict) and block.get("type") == "text"):
                    continue
                params: dict[str, Any] = {"type": "text", "text": block["text"]}
                if block.get("cache_control"):
                    params["cache_control"] = {"type": "ephemeral"}
                out.append(params)
            return out or anthropic.NOT_GIVEN
        return str(system) if system else anthropic.NOT_GIVEN

    async def generate(
        self,
        prompt: str | list[dict[str, Any]],
        system: str | list[dict[str, Any]] = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model_override: Optional[str] = None,
        tenant_id: str = "",
    ) -> dict[str, Any]:
        """Plain-text Claude response via official SDK. Signature unchanged."""
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        if tenant_id:
            from src.modules.generator.ai.token_manager import token_manager, BudgetExceededError
            if not await token_manager.has_budget(tenant_id):
                remaining = await token_manager.get_remaining_budget(tenant_id)
                raise BudgetExceededError(tenant_id, used=0, limit=remaining)

        await self._rate_limit()

        sdk_system = self._to_sdk_system(self._build_system(system))
        messages   = [{"role": "user", "content": prompt}]
        models_to_try = [model_override] if model_override else self.MODELS
        last_exception: Exception | None = None

        for current_model in models_to_try:
            try:
                logger.info("AIClient.generate: %s", current_model)
                resp = await self._sdk().messages.create(
                    model=current_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=sdk_system,
                    messages=messages,
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                )

                content     = "".join(b.text for b in resp.content if isinstance(b, anthropic.types.TextBlock))
                in_tok      = resp.usage.input_tokens
                out_tok     = resp.usage.output_tokens
                cache_write = getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
                cache_read  = getattr(resp.usage, "cache_read_input_tokens", 0) or 0

                if cache_write or cache_read:
                    logger.info("[Cache] write=%d read=%d savings≈%d", cache_write, cache_read,
                                int(cache_read * 0.9 - cache_write * 0.25))

                if tenant_id and in_tok + out_tok > 0:
                    from src.modules.generator.ai.token_manager import token_manager
                    await token_manager.record_usage(tenant_id, in_tok, out_tok)

                return {
                    "content": content,
                    "usage": {
                        "input_tokens": in_tok, "output_tokens": out_tok,
                        "cache_creation_input_tokens": cache_write,
                        "cache_read_input_tokens": cache_read,
                    },
                    "model": current_model,
                }

            except anthropic.RateLimitError:
                last_exception = RuntimeError(f"Rate limit on {current_model}")
                continue
            except anthropic.APIStatusError as exc:
                last_exception = RuntimeError(f"API {exc.status_code} on {current_model}")
                if exc.status_code in (429, 500, 502, 503, 504):
                    continue
                raise last_exception
            except anthropic.APIConnectionError as exc:
                last_exception = RuntimeError(f"Connection error: {exc}")
                continue
            except Exception as exc:
                last_exception = RuntimeError(str(exc))
                continue

        raise last_exception or RuntimeError("All models failed.")

    async def generate_json(
        self,
        prompt: str | list[dict[str, Any]],
        system: str | list[dict[str, Any]] = "",
        max_tokens: int = 1500,
        temperature: float = 0.2,
        tenant_id: str = "",
    ) -> dict[str, Any]:
        """
        Structured JSON response via Claude tool-use.

        INJECTION-MITIGATION BOUNDARY: the JSON-output instruction appended to
        the system here is fixed hardcoded text — no spec data is ever included.

        The SDK forces Claude to call the return_json tool, so block.input is
        already a parsed Python dict — no regex/fence extraction needed.
        Signature unchanged; all generators call this without modification.
        """
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        if tenant_id:
            from src.modules.generator.ai.token_manager import token_manager, BudgetExceededError
            if not await token_manager.has_budget(tenant_id):
                remaining = await token_manager.get_remaining_budget(tenant_id)
                raise BudgetExceededError(tenant_id, used=0, limit=remaining)

        await self._rate_limit()

        # Append tool-use instruction (hardcoded, not spec-derived)
        _suffix = (
            "\n\nCRITICAL: You MUST call the return_json tool with your complete response. "
            "Do NOT emit any plain text — only call the tool."
        )
        raw_system = (list(system) + [{"type": "text", "text": _suffix}]
                      if isinstance(system, list) else (system or "") + _suffix)
        sdk_system = self._to_sdk_system(self._build_system(raw_system))
        messages   = [{"role": "user", "content": prompt}]
        last_exception: Exception | None = None

        for current_model in self.MODELS:
            try:
                logger.info("AIClient.generate_json: %s (tool-use)", current_model)
                resp = await self._sdk().messages.create(
                    model=current_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=sdk_system,
                    messages=messages,
                    tools=_JSON_TOOL,                                    # type: ignore[arg-type]
                    tool_choice={"type": "tool", "name": "return_json"},
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                )

                in_tok      = resp.usage.input_tokens
                out_tok     = resp.usage.output_tokens
                cache_write = getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
                cache_read  = getattr(resp.usage, "cache_read_input_tokens", 0) or 0

                # Tool response is pre-parsed by the SDK — no regex needed
                parsed: Any = None
                for block in resp.content:
                    if isinstance(block, anthropic.types.ToolUseBlock) and block.name == "return_json":
                        parsed = block.input.get("result")
                        break

                # Defensive text fallback (should not normally trigger)
                if parsed is None:
                    logger.warning("[AI] Tool block missing; attempting text fallback")
                    for block in resp.content:
                        if isinstance(block, anthropic.types.TextBlock) and block.text.strip():
                            try:
                                parsed = json.loads(block.text.strip())
                            except json.JSONDecodeError:
                                pass
                            break

                if parsed is None:
                    parsed = {"raw_text": ""}

                # Unwrap {"tests": [...]} wrapper dicts if present
                if isinstance(parsed, dict):
                    _ARRAY_KEYS = (
                        "tests", "generated_tests", "data", "cases", "test_cases",
                        "results", "items", "negative_tests", "negative_test_cases",
                        "test_data", "generated", "output", "negative_cases",
                        "testcases", "testCases",
                    )
                    for key in _ARRAY_KEYS:
                        if key in parsed and isinstance(parsed[key], list):
                            parsed = parsed[key]; break
                    else:
                        list_keys = [k for k, v in parsed.items() if isinstance(v, list)]
                        if list_keys:
                            parsed = parsed[list_keys[0]]

                logger.info("[AI] generate_json OK type=%s in=%d out=%d",
                            type(parsed).__name__, in_tok, out_tok)

                if tenant_id and in_tok + out_tok > 0:
                    from src.modules.generator.ai.token_manager import token_manager
                    await token_manager.record_usage(tenant_id, in_tok, out_tok)

                return {
                    "data": parsed,
                    "usage": {
                        "input_tokens": in_tok, "output_tokens": out_tok,
                        "cache_creation_input_tokens": cache_write,
                        "cache_read_input_tokens": cache_read,
                    },
                }

            except anthropic.RateLimitError:
                last_exception = RuntimeError(f"Rate limit on {current_model}")
                continue
            except anthropic.APIStatusError as exc:
                last_exception = RuntimeError(f"API {exc.status_code}: {exc.message}")
                if exc.status_code in (429, 500, 502, 503, 504):
                    continue
                raise last_exception
            except anthropic.APIConnectionError as exc:
                last_exception = RuntimeError(f"Connection error: {exc}")
                continue
            except Exception as exc:
                last_exception = RuntimeError(str(exc))
                continue

        raise last_exception or RuntimeError("All models failed.")

    def prepare_batch_request(
        self,
        custom_id: str,
        prompt: str | list[dict[str, Any]],
        system: str | list[dict[str, Any]] = "",
        max_tokens: int = 4096,
        temperature: float = 0.3,
        model_override: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Prepare a single request item for Anthropic's Batch API.
        Preserves prompt caching structure and strict Swagger rules.
        """
        if isinstance(system, list):
            strict_system = list(system) + [
                {
                    "type": "text",
                    "text": "\n\nCRITICAL: Return ONLY valid JSON. No markdown. No explanations. No code blocks. Start with [ or { and end with ] or }."
                }
            ]
        else:
            strict_system = system + "\n\nCRITICAL: Return ONLY valid JSON. No markdown. No explanations. No code blocks. Start with [ or { and end with ] or }."

        if isinstance(prompt, list):
            messages = [{"role": "user", "content": prompt}]
        else:
            messages = [{"role": "user", "content": prompt}]

        return {
            "custom_id": custom_id,
            "params": {
                "model": model_override or self.model,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": temperature,
                "system": strict_system
            }
        }

    async def create_batch(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        """Submit a batch of requests to Anthropic's Batch API."""
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        url = "https://api.anthropic.com/v1/messages/batches"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "content-type": "application/json",
            "anthropic-beta": "message-batches-2024-09-24,prompt-caching-2024-07-31",
        }
        logger.info("[AI][Batch] Creating batch with %d requests...", len(requests))
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json={"requests": requests})
            if resp.status_code != 200:
                logger.error("[AI][Batch] Create batch failed: status=%d body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.json()

    async def retrieve_batch(self, batch_id: str) -> dict[str, Any]:
        """Poll the status of an existing Anthropic batch."""
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        url = f"https://api.anthropic.com/v1/messages/batches/{batch_id}"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "anthropic-beta": "message-batches-2024-09-24,prompt-caching-2024-07-31",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            return resp.json()

    async def download_batch_results(self, results_url: str) -> list[dict[str, Any]]:
        """Download and parse JSONL results from a completed batch."""
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
            "anthropic-beta": "message-batches-2024-09-24,prompt-caching-2024-07-31",
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.get(results_url, headers=headers)
            resp.raise_for_status()
            results = []
            for line in resp.text.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    logger.warning("[AI][Batch] Failed to decode JSONL line: %s | Error: %s", line[:100], exc)
            return results

    async def run_batch_and_poll(
        self,
        requests: list[dict[str, Any]],
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
        on_status_update: Optional[Any] = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Submit a batch, poll until completion, download results, and compute telemetry/cost savings.
        """
        start_time = time.time()
        batch_meta = await self.create_batch(requests)
        batch_id = batch_meta["id"]
        logger.info("[AI][Batch] Created batch id=%s (requests=%d)", batch_id, len(requests))

        if on_status_update:
            try:
                if asyncio.iscoroutinefunction(on_status_update):
                    await on_status_update(batch_id, "in_progress", batch_meta)
                else:
                    on_status_update(batch_id, "in_progress", batch_meta)
            except Exception as exc:
                logger.warning("[AI][Batch] on_status_update callback failed: %s", exc)

        while True:
            await asyncio.sleep(poll_interval)
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(f"Anthropic Batch {batch_id} timed out after {timeout} seconds.")

            status_meta = await self.retrieve_batch(batch_id)
            status = status_meta.get("processing_status", "in_progress")
            counts = status_meta.get("request_counts", {})
            logger.info("[AI][Batch] Polling batch %s: status=%s counts=%s (elapsed=%.1fs)", batch_id, status, counts, elapsed)

            if on_status_update:
                try:
                    if asyncio.iscoroutinefunction(on_status_update):
                        await on_status_update(batch_id, status, status_meta)
                    else:
                        on_status_update(batch_id, status, status_meta)
                except Exception as exc:
                    logger.warning("[AI][Batch] on_status_update callback failed: %s", exc)

            if status == "ended":
                completion_time = time.time() - start_time
                results_url = status_meta.get("results_url") or f"https://api.anthropic.com/v1/messages/batches/{batch_id}/results"
                raw_results = await self.download_batch_results(results_url)

                total_input_tokens = 0
                total_output_tokens = 0
                total_cache_creation = 0
                total_cache_read = 0
                succeeded_count = 0
                errored_count = 0

                for item in raw_results:
                    if item.get("result", {}).get("type") == "succeeded":
                        succeeded_count += 1
                        msg = item["result"]["message"]
                        usage = msg.get("usage", {})
                        total_input_tokens += usage.get("input_tokens", 0)
                        total_output_tokens += usage.get("output_tokens", 0)
                        total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                        total_cache_read += usage.get("cache_read_input_tokens", 0)
                    else:
                        errored_count += 1

                # Pricing: Batch API is 50% off standard pricing
                batch_cost_usd = (
                    total_input_tokens * 1.50
                    + total_output_tokens * 7.50
                    + total_cache_creation * 1.875
                    + total_cache_read * 0.15
                ) / 1_000_000.0
                standard_cost_usd = (
                    total_input_tokens * 3.00
                    + total_output_tokens * 15.00
                    + total_cache_creation * 3.75
                    + total_cache_read * 0.30
                ) / 1_000_000.0
                cost_savings_usd = standard_cost_usd - batch_cost_usd

                logger.info("[AI][Batch] Batch %s completed in %.2fs! Succeeded: %d, Errored: %d", batch_id, completion_time, succeeded_count, errored_count)
                logger.info("[AI][Batch] Token Usage — Input: %d, Output: %d | Cache Creation: %d, Cache Read: %d | Est. Token Savings: %d tokens", total_input_tokens, total_output_tokens, total_cache_creation, total_cache_read, total_cache_read)
                logger.info("[AI][Batch] Cost Estimation — Total Generation Cost: $%.6f USD (Est. Savings vs Standard API: $%.6f USD / 50%%+ off!)", batch_cost_usd, cost_savings_usd)

                meta_res = {
                    "batch_id": batch_id,
                    "completion_time_s": completion_time,
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "cache_creation_tokens": total_cache_creation,
                    "cache_read_tokens": total_cache_read,
                    "cost_usd": batch_cost_usd,
                    "savings_usd": cost_savings_usd,
                    "succeeded_count": succeeded_count,
                    "errored_count": errored_count,
                }
                return raw_results, meta_res

            elif status in ("canceled", "expired", "archived"):
                raise RuntimeError(f"Anthropic Batch {batch_id} ended with status: {status}")

    async def execute_batch_with_retry(
        self,
        requests: list[dict[str, Any]],
        max_retries: int = 2,
        poll_interval: float = 5.0,
        timeout: float = 3600.0,
        on_status_update: Optional[Any] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Execute a batch of requests with automatic retries for failed or invalid-JSON items.
        Returns (results_by_custom_id, aggregated_metrics).
        """
        if not self.is_available:
            raise RuntimeError("AI client not configured.")

        pending_requests = list(requests)
        results_by_custom_id: dict[str, Any] = {}
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_creation = 0
        total_cache_read = 0
        latest_batch_id = ""
        total_completion_time = 0.0

        for attempt in range(max_retries + 1):
            if not pending_requests:
                break

            if attempt > 0:
                logger.info(
                    "[AI][Batch] Retry attempt %d/%d for %d failed requests...",
                    attempt, max_retries, len(pending_requests)
                )

            raw_results, meta = await self.run_batch_and_poll(
                pending_requests,
                poll_interval=poll_interval,
                timeout=timeout,
                on_status_update=on_status_update,
            )

            latest_batch_id = meta.get("batch_id", latest_batch_id)
            total_input_tokens += meta.get("input_tokens", 0)
            total_output_tokens += meta.get("output_tokens", 0)
            total_cache_creation += meta.get("cache_creation_tokens", 0)
            total_cache_read += meta.get("cache_read_tokens", 0)
            total_completion_time += meta.get("completion_time_s", 0.0)

            next_pending = []
            req_by_id = {r["custom_id"]: r for r in pending_requests}

            for item in raw_results:
                cid = item.get("custom_id")
                if not cid:
                    continue
                res = item.get("result", {})
                if res.get("type") == "succeeded":
                    message = res.get("message", {})
                    content = "".join(
                        b["text"] for b in message.get("content", []) if b.get("type") == "text"
                    ).strip()
                    parsed = self._parse_json_content(content)
                    if parsed is not None and not (isinstance(parsed, dict) and "raw_text" in parsed):
                        results_by_custom_id[cid] = {
                            "data": parsed,
                            "usage": message.get("usage", {}),
                            "model": message.get("model", self.model),
                        }
                    else:
                        logger.warning("[AI][Batch] Item %s succeeded but JSON parsing failed.", cid)
                        if cid in req_by_id:
                            next_pending.append(req_by_id[cid])
                else:
                    err = res.get("error", {})
                    logger.warning("[AI][Batch] Item %s failed: %s", cid, err)
                    if cid in req_by_id:
                        next_pending.append(req_by_id[cid])

            seen_cids = {item.get("custom_id") for item in raw_results}
            for req in pending_requests:
                cid = req["custom_id"]
                if cid not in seen_cids and cid not in results_by_custom_id:
                    next_pending.append(req)

            pending_requests = next_pending
            if not pending_requests:
                break

        if pending_requests:
            logger.warning(
                "[AI][Batch] %d requests still unresolved after batch retries. Performing real-time fallback...",
                len(pending_requests)
            )
            for req in pending_requests:
                cid = req["custom_id"]
                params = req.get("params", {})
                try:
                    res = await self.generate_json(
                        prompt=params.get("messages", [])[0].get("content", ""),
                        system=params.get("system", ""),
                        max_tokens=params.get("max_tokens", 4096),
                        temperature=params.get("temperature", 0.3),
                    )
                    results_by_custom_id[cid] = res
                    usage = res.get("usage", {})
                    total_input_tokens += usage.get("input_tokens", 0)
                    total_output_tokens += usage.get("output_tokens", 0)
                    total_cache_creation += usage.get("cache_creation_input_tokens", 0)
                    total_cache_read += usage.get("cache_read_input_tokens", 0)
                except Exception as exc:
                    logger.error("[AI][Batch] Real-time fallback failed for %s: %s", cid, exc)
                    results_by_custom_id[cid] = {
                        "data": [],
                        "usage": {"input_tokens": 0, "output_tokens": 0},
                        "error": str(exc),
                    }

        batch_cost_usd = (
            total_input_tokens * 1.50
            + total_output_tokens * 7.50
            + total_cache_creation * 1.875
            + total_cache_read * 0.15
        ) / 1_000_000.0
        standard_cost_usd = (
            total_input_tokens * 3.00
            + total_output_tokens * 15.00
            + total_cache_creation * 3.75
            + total_cache_read * 0.30
        ) / 1_000_000.0
        cost_savings_usd = standard_cost_usd - batch_cost_usd

        aggregated_metrics = {
            "batch_id": latest_batch_id,
            "completion_time_s": total_completion_time,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cache_creation_tokens": total_cache_creation,
            "cache_read_tokens": total_cache_read,
            "cost_usd": batch_cost_usd,
            "savings_usd": cost_savings_usd,
            "succeeded_count": len([r for r in results_by_custom_id.values() if "error" not in r]),
            "errored_count": len([r for r in results_by_custom_id.values() if "error" in r]),
        }

        return results_by_custom_id, aggregated_metrics




# Global singleton
ai_client = AIClient()

