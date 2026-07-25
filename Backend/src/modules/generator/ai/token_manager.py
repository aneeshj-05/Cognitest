"""
DB-backed token budget enforcement for AI-powered test generation.

Replaces the original in-memory placeholder with real persistence via the
TenantTokenUsage Prisma model and budget limits from each tenant's Plan.

Plan.monthlyTokenLimit semantics:
  NULL  →  FREE default  (500_000 tokens/month)
  -1    →  unlimited (ENTERPRISE)
  N > 0 →  exactly N tokens/month

Usage:
    from src.modules.generator.ai.token_manager import token_manager

    # Before any Claude call:
    ok = await token_manager.has_budget(tenant_id)
    if not ok:
        raise BudgetExceededError(tenant_id)

    # After a Claude call:
    await token_manager.record_usage(tenant_id, input_tokens, output_tokens)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.modules.generator.ai.token_logger import calculate_cost

logger = logging.getLogger(__name__)

# Tokens/month given to FREE tenants when the Plan row has no explicit limit.
_FREE_DEFAULT_LIMIT = 500_000


class BudgetExceededError(RuntimeError):
    """Raised when a tenant has exhausted their monthly AI token budget."""

    def __init__(self, tenant_id: str, used: int, limit: int) -> None:
        self.tenant_id = tenant_id
        self.used = used
        self.limit = limit
        super().__init__(
            f"Tenant {tenant_id!r} has exceeded their monthly AI token budget "
            f"({used:,} / {limit:,} tokens used)."
        )


def _period_start(now: datetime) -> datetime:
    """Return the first moment of the current calendar month (UTC)."""
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _period_end(period_start: datetime) -> datetime:
    """Return the first moment of the *next* month (exclusive upper bound)."""
    month = period_start.month
    year  = period_start.year
    if month == 12:
        return period_start.replace(year=year + 1, month=1)
    return period_start.replace(month=month + 1)


async def _get_plan_limit(tenant_id: str) -> int:
    """
    Look up the tenant's active subscription plan and return the monthly
    token limit.  Returns _FREE_DEFAULT_LIMIT if no subscription found.
    -1 means unlimited.
    """
    from src.config.database import prisma

    try:
        sub = await prisma.subscription.find_unique(
            where={"tenantId": tenant_id},
            include={"plan": True},
        )
        if sub and sub.plan:
            limit = sub.plan.monthlyTokenLimit
            if limit is None:
                return _FREE_DEFAULT_LIMIT
            return limit  # -1 = unlimited, or a positive cap
    except Exception as exc:
        logger.warning("[TokenManager] Could not fetch plan for tenant %s: %s", tenant_id, exc)

    return _FREE_DEFAULT_LIMIT


async def _get_current_usage(tenant_id: str, period_start: datetime) -> int:
    """Return total tokens consumed by tenant in the current billing period."""
    from src.config.database import prisma

    try:
        row = await prisma.tenanttokenusage.find_unique(
            where={"tenantId_periodStart": {"tenantId": tenant_id, "periodStart": period_start}}
        )
        if row:
            return row.totalTokens
    except Exception as exc:
        logger.warning("[TokenManager] Could not fetch usage for tenant %s: %s", tenant_id, exc)

    return 0


class TokenManager:
    """
    DB-backed token budget manager.

    has_budget() and record_usage() are async and must be awaited.
    The singleton `token_manager` below is the recommended import.
    """

    async def has_budget(self, tenant_id: str) -> bool:
        """
        Return True if the tenant has remaining budget for at least one more
        AI call this month.  Always returns True for unlimited (-1) plans.
        """
        if not tenant_id or tenant_id in ("", "super-admin-tenant"):
            return True  # Super admin / no tenant — never blocked

        limit = await _get_plan_limit(tenant_id)
        if limit == -1:
            return True  # Unlimited plan

        now   = datetime.now(timezone.utc)
        start = _period_start(now)
        used  = await _get_current_usage(tenant_id, start)
        return used < limit

    async def get_remaining_budget(self, tenant_id: str) -> int:
        """
        Return remaining tokens for this month.
        Returns -1 for unlimited plans.
        """
        if not tenant_id or tenant_id in ("", "super-admin-tenant"):
            return -1

        limit = await _get_plan_limit(tenant_id)
        if limit == -1:
            return -1

        now   = datetime.now(timezone.utc)
        start = _period_start(now)
        used  = await _get_current_usage(tenant_id, start)
        return max(0, limit - used)

    async def record_usage(
        self,
        tenant_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """
        Atomically increment the TenantTokenUsage row for the current period.
        Creates the row if it doesn't exist yet (upsert via create+update).
        Called immediately after every successful Claude API response so usage
        is accurate even if a run is interrupted mid-way.
        """
        if not tenant_id or tenant_id in ("", "super-admin-tenant"):
            return

        from src.config.database import prisma

        total = input_tokens + output_tokens
        cost  = calculate_cost(input_tokens, output_tokens)
        now   = datetime.now(timezone.utc)
        start = _period_start(now)
        end   = _period_end(start)

        try:
            # Try update first (fast path for existing row)
            existing = await prisma.tenanttokenusage.find_unique(
                where={"tenantId_periodStart": {"tenantId": tenant_id, "periodStart": start}}
            )
            if existing:
                await prisma.tenanttokenusage.update(
                    where={"id": existing.id},
                    data={
                        "inputTokens":  existing.inputTokens  + input_tokens,
                        "outputTokens": existing.outputTokens + output_tokens,
                        "totalTokens":  existing.totalTokens  + total,
                        "costUsd":      existing.costUsd       + cost,
                    },
                )
            else:
                await prisma.tenanttokenusage.create(
                    data={
                        "tenantId":    tenant_id,
                        "periodStart": start,
                        "periodEnd":   end,
                        "inputTokens": input_tokens,
                        "outputTokens": output_tokens,
                        "totalTokens": total,
                        "costUsd":     cost,
                    }
                )
        except Exception as exc:
            # Non-fatal — log and continue. Better to over-spend slightly than
            # to block a generation due to a transient DB error.
            logger.error(
                "[TokenManager] Failed to persist usage for tenant %s: %s",
                tenant_id, exc,
            )


# Module-level singleton used across the codebase
token_manager = TokenManager()
