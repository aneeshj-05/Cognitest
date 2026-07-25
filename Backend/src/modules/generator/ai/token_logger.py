"""
AI Token Usage Logger — structured per-test-case token and cost tracking.

Writes a JSON-lines log file at logs/ai_token_usage.jsonl and also logs a
human-readable summary to the standard Python logger.

Claude Sonnet 4.6 pricing (as of 2025):
  Input tokens:  $3.00 per 1,000,000 tokens  → $0.000003 per token
  Output tokens: $15.00 per 1,000,000 tokens → $0.000015 per token

Usage:
    from src.modules.generator.ai.token_logger import TokenUsageLogger

    logger_inst = TokenUsageLogger(
        project_id="proj-123",
        project_name="My API",
        test_type="Functional",
        suite_id="suite-456",
        generation_method="ai_enhanced",
    )
    logger_inst.record_test_case(
        test_case_name="Register user with valid email",
        endpoint_path="/api/register",
        method="POST",
        input_tokens=1200,
        output_tokens=350,
    )
    summary = logger_inst.finalize()
    # summary = {
    #   "total_input_tokens": ...,
    #   "total_output_tokens": ...,
    #   "total_tokens": ...,
    #   "total_cost_usd": ...,
    #   "entries": [...],
    # }
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Claude pricing constants (per token)
# ---------------------------------------------------------------------------
# Claude Sonnet 4.6 / Claude Haiku 4.5 (same pricing tier used here as a
# conservative estimate — Haiku is cheaper but we track at Sonnet rate to
# avoid under-reporting).
_COST_PER_INPUT_TOKEN  = 3.00  / 1_000_000   # $3.00 / 1M input tokens
_COST_PER_OUTPUT_TOKEN = 15.00 / 1_000_000   # $15.00 / 1M output tokens
_COST_PER_CACHE_CREATE = 3.75  / 1_000_000   # $3.75 / 1M cache creation tokens
_COST_PER_CACHE_READ   = 0.30  / 1_000_000   # $0.30 / 1M cache read tokens


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    cache_creation_tokens: int = 0,
    cache_read_tokens: int = 0,
    is_batch: bool = False,
) -> float:
    """Return USD cost for the given token counts (Claude Sonnet 4.6 pricing).
    Applies a 50% discount when is_batch=True for Anthropic Batch API calls.
    """
    std_cost = (
        (input_tokens * _COST_PER_INPUT_TOKEN)
        + (output_tokens * _COST_PER_OUTPUT_TOKEN)
        + (cache_creation_tokens * _COST_PER_CACHE_CREATE)
        + (cache_read_tokens * _COST_PER_CACHE_READ)
    )
    return (std_cost * 0.5) if is_batch else std_cost


def _log_file_path() -> Path:
    """Resolve the log file path — creates parent dirs if needed."""
    # Place logs/ next to the backend root (two levels up from this file's package)
    backend_root = Path(__file__).resolve().parents[4]  # …/Cognitest-Backend
    log_dir = backend_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "ai_token_usage.jsonl"


@dataclass
class TokenUsageEntry:
    """Token usage record for a single test case generation."""
    timestamp: str
    project_id: str
    project_name: str
    test_type: str
    suite_id: str
    generation_method: str
    test_case_name: str
    endpoint_path: str
    method: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    is_batch: bool = False
    savings_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":             self.timestamp,
            "project_id":            self.project_id,
            "project_name":          self.project_name,
            "test_type":             self.test_type,
            "suite_id":              self.suite_id,
            "generation_method":     self.generation_method,
            "test_case_name":        self.test_case_name,
            "endpoint_path":         self.endpoint_path,
            "method":                self.method,
            "input_tokens":          self.input_tokens,
            "output_tokens":         self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens":     self.cache_read_tokens,
            "total_tokens":          self.total_tokens,
            "cost_usd":              round(self.cost_usd, 8),
            "is_batch":              self.is_batch,
            "savings_usd":           round(self.savings_usd, 8),
        }


class TokenUsageLogger:
    """
    Accumulates per-test-case token usage during a generation run and writes
    structured log entries to logs/ai_token_usage.jsonl.

    One instance per generation request.
    """

    def __init__(
        self,
        *,
        project_id: str,
        project_name: str,
        test_type: str,
        suite_id: str,
        generation_method: str,
        is_batch: bool = False,
    ) -> None:
        self.project_id        = project_id
        self.project_name      = project_name
        self.test_type         = test_type
        self.suite_id          = suite_id
        self.generation_method = generation_method
        self.is_batch          = is_batch
        self._entries: list[TokenUsageEntry] = []

    def record_test_case(
        self,
        *,
        test_case_name: str,
        endpoint_path: str,
        method: str,
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> TokenUsageEntry:
        """Record token usage for one test case. Returns the entry."""
        total    = input_tokens + output_tokens + cache_creation_tokens + cache_read_tokens
        cost     = calculate_cost(input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, is_batch=self.is_batch)
        std_cost = calculate_cost(input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens, is_batch=False)
        savings  = (std_cost - cost) if self.is_batch else 0.0
        entry    = TokenUsageEntry(
            timestamp             = datetime.now(timezone.utc).isoformat(),
            project_id            = self.project_id,
            project_name          = self.project_name,
            test_type             = self.test_type,
            suite_id              = self.suite_id,
            generation_method     = self.generation_method,
            test_case_name        = test_case_name,
            endpoint_path         = endpoint_path,
            method                = method,
            input_tokens          = input_tokens,
            output_tokens         = output_tokens,
            cache_creation_tokens = cache_creation_tokens,
            cache_read_tokens     = cache_read_tokens,
            total_tokens          = total,
            cost_usd              = cost,
            is_batch              = self.is_batch,
            savings_usd           = savings,
        )
        self._entries.append(entry)
        return entry

    def finalize(self) -> dict[str, Any]:
        """
        Write all accumulated entries to the JSONL log file, log a human-
        readable summary, and return aggregate stats.
        """
        if not self._entries:
            return {
                "total_input_tokens":          0,
                "total_output_tokens":         0,
                "total_cache_creation_tokens": 0,
                "total_cache_read_tokens":     0,
                "total_tokens":                0,
                "total_cost_usd":              0.0,
                "total_savings_usd":           0.0,
                "is_batch":                    self.is_batch,
                "entries":                     [],
            }

        total_input  = sum(e.input_tokens  for e in self._entries)
        total_output = sum(e.output_tokens for e in self._entries)
        total_cc     = sum(e.cache_creation_tokens for e in self._entries)
        total_cr     = sum(e.cache_read_tokens     for e in self._entries)
        total_tokens = total_input + total_output + total_cc + total_cr
        total_cost   = calculate_cost(total_input, total_output, total_cc, total_cr, is_batch=self.is_batch)
        std_cost     = calculate_cost(total_input, total_output, total_cc, total_cr, is_batch=False)
        total_savings = (std_cost - total_cost) if self.is_batch else 0.0

        # Write JSON-lines — one line per test case
        log_path = _log_file_path()
        try:
            with log_path.open("a", encoding="utf-8") as fh:
                for entry in self._entries:
                    fh.write(json.dumps(entry.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("[TokenLogger] Could not write to %s: %s", log_path, exc)

        # Human-readable summary in the server log
        logger.info(
            "[TokenLogger] Generation complete — project=%s type=%s suite=%s (batch=%s) | "
            "test_cases=%d | tokens(in=%d out=%d cc=%d cr=%d total=%d) | cost=$%.6f USD | savings=$%.6f USD",
            self.project_name, self.test_type, self.suite_id, self.is_batch,
            len(self._entries),
            total_input, total_output, total_cc, total_cr, total_tokens,
            total_cost, total_savings,
        )

        return {
            "total_input_tokens":          total_input,
            "total_output_tokens":         total_output,
            "total_cache_creation_tokens": total_cc,
            "total_cache_read_tokens":     total_cr,
            "total_tokens":                total_tokens,
            "total_cost_usd":              round(total_cost, 8),
            "total_savings_usd":           round(total_savings, 8),
            "is_batch":                    self.is_batch,
            "entries":                     [e.to_dict() for e in self._entries],
        }

    # ── Convenience: record a batch of test cases sharing a single AI call ─

    def record_batch(
        self,
        *,
        test_cases: list[dict[str, Any]],
        input_tokens: int,
        output_tokens: int,
        cache_creation_tokens: int = 0,
        cache_read_tokens: int = 0,
    ) -> None:
        """
        Distribute the tokens from one AI call evenly across the test cases
        it produced.  This is used when a single AI call generates multiple
        test cases (e.g. per-endpoint calls in Functional/Negative/Fuzz).

        Each test case receives an equal share of input_tokens, and an equal
        share of output_tokens (proportional distribution).

        If the batch is empty the tokens are logged as a single "empty batch"
        entry so no tokens are silently lost.
        """
        if not test_cases:
            # Still record the call cost so we don't lose tokens
            self.record_test_case(
                test_case_name        = "(empty batch — AI returned no tests)",
                endpoint_path         = "",
                method                = "",
                input_tokens          = input_tokens,
                output_tokens         = output_tokens,
                cache_creation_tokens = cache_creation_tokens,
                cache_read_tokens     = cache_read_tokens,
            )
            return

        n = len(test_cases)
        # Integer division — any remainder is added to the last entry
        per_in  = input_tokens  // n
        per_out = output_tokens // n
        per_cc  = cache_creation_tokens // n
        per_cr  = cache_read_tokens     // n
        rem_in  = input_tokens  - (per_in  * n)
        rem_out = output_tokens - (per_out * n)
        rem_cc  = cache_creation_tokens - (per_cc  * n)
        rem_cr  = cache_read_tokens     - (per_cr  * n)

        for i, tc in enumerate(test_cases):
            extra_in  = rem_in  if i == n - 1 else 0
            extra_out = rem_out if i == n - 1 else 0
            extra_cc  = rem_cc  if i == n - 1 else 0
            extra_cr  = rem_cr  if i == n - 1 else 0
            self.record_test_case(
                test_case_name        = str(tc.get("name") or "Unnamed Test"),
                endpoint_path         = str(tc.get("endpoint_path") or tc.get("path") or ""),
                method                = str(tc.get("method") or "GET"),
                input_tokens          = per_in  + extra_in,
                output_tokens         = per_out + extra_out,
                cache_creation_tokens = per_cc  + extra_cc,
                cache_read_tokens     = per_cr  + extra_cr,
            )
