"""
Tests for DB-backed token budget enforcement.

Covers:
  (a) Under-budget tenant can generate — AI client IS invoked.
  (b) Over-budget tenant is rejected before any Claude call — AI client NOT invoked.
  (c) Usage persists to DB and survives a simulated restart (reads from DB, not memory).
  (d) ENTERPRISE tenant with monthlyTokenLimit=-1 is never blocked.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.generator.ai.token_manager import (
    TokenManager,
    BudgetExceededError,
    _period_start,
    _FREE_DEFAULT_LIMIT,
)
from src.modules.generator.ai.token_logger import calculate_cost


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plan(limit: int):
    plan = MagicMock()
    plan.monthlyTokenLimit = limit
    return plan


def _make_sub(limit: int):
    sub = MagicMock()
    sub.plan = _make_plan(limit)
    return sub


def _make_usage_row(total: int):
    row = MagicMock()
    row.totalTokens  = total
    row.inputTokens  = total // 2
    row.outputTokens = total - total // 2
    row.costUsd      = calculate_cost(total // 2, total - total // 2)
    row.id           = "row-id"
    return row


TENANT = "tenant-abc"
NOW    = datetime.now(timezone.utc)
START  = _period_start(NOW)


# ---------------------------------------------------------------------------
# (a) Under-budget tenant can generate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_budget_returns_true_when_under_limit():
    mgr = TokenManager()
    limit = 100_000
    used  = 50_000

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=limit)), \
         patch("src.modules.generator.ai.token_manager._get_current_usage", AsyncMock(return_value=used)):
        assert await mgr.has_budget(TENANT) is True


# ---------------------------------------------------------------------------
# (b) Over-budget tenant is rejected — AI client never invoked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_has_budget_returns_false_when_at_limit():
    mgr = TokenManager()
    limit = 100_000

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=limit)), \
         patch("src.modules.generator.ai.token_manager._get_current_usage", AsyncMock(return_value=limit)):
        assert await mgr.has_budget(TENANT) is False


@pytest.mark.asyncio
async def test_ai_client_not_invoked_when_over_budget():
    """BudgetExceededError must be raised before any httpx call to Claude."""
    from src.modules.generator.ai.client import AIClient

    client = AIClient()
    client.api_key = "sk-fake"  # make is_available True

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=100)), \
         patch("src.modules.generator.ai.token_manager._get_current_usage", AsyncMock(return_value=100)), \
         patch("httpx.AsyncClient.post") as mock_post:

        with pytest.raises(BudgetExceededError):
            await client.generate(
                prompt="test",
                system="test",
                tenant_id=TENANT,
            )

        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# (c) Usage persists to DB — survives restart (reads DB not memory)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_usage_upserts_db_row():
    """record_usage creates a row if missing, updates it if present."""
    from src.config.database import prisma
    mgr = TokenManager()

    # Simulate no existing row → create path
    mock_find   = AsyncMock(return_value=None)
    mock_create = AsyncMock()

    with patch.object(prisma, "tenanttokenusage", create=True) as mock_table:
        mock_table.find_unique = mock_find
        mock_table.create      = mock_create
        mock_table.update      = AsyncMock()

        await mgr.record_usage(TENANT, input_tokens=200, output_tokens=100)

        mock_create.assert_awaited_once()
        call_data = mock_create.call_args.kwargs["data"]
        assert call_data["tenantId"]    == TENANT
        assert call_data["inputTokens"] == 200
        assert call_data["outputTokens"] == 100
        assert call_data["totalTokens"] == 300


@pytest.mark.asyncio
async def test_get_current_usage_reads_from_db():
    """After a restart, usage is read from DB — no in-memory state."""
    from src.modules.generator.ai.token_manager import _get_current_usage
    from src.config.database import prisma

    mock_row = _make_usage_row(75_000)

    with patch.object(prisma, "tenanttokenusage", create=True) as mock_table:
        mock_table.find_unique = AsyncMock(return_value=mock_row)
        usage = await _get_current_usage(TENANT, START)

    assert usage == 75_000  # from DB, not in-memory


# ---------------------------------------------------------------------------
# (d) ENTERPRISE (limit=-1) is never blocked
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enterprise_unlimited_never_blocked():
    mgr = TokenManager()

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=-1)):
        # Simulate extremely high usage
        with patch("src.modules.generator.ai.token_manager._get_current_usage",
                   AsyncMock(return_value=999_999_999)):
            assert await mgr.has_budget(TENANT) is True


@pytest.mark.asyncio
async def test_enterprise_remaining_budget_is_minus_one():
    mgr = TokenManager()

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=-1)):
        remaining = await mgr.get_remaining_budget(TENANT)

    assert remaining == -1


# ---------------------------------------------------------------------------
# (e) Super-admin tenant always bypasses budget
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_super_admin_tenant_never_blocked():
    mgr = TokenManager()
    # Should return True without any DB calls
    result = await mgr.has_budget("super-admin-tenant")
    assert result is True

    result = await mgr.has_budget("")
    assert result is True


# ---------------------------------------------------------------------------
# (f) get_remaining_budget returns correct value
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_remaining_budget_calculation():
    mgr = TokenManager()
    limit = 500_000
    used  = 123_456

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=limit)), \
         patch("src.modules.generator.ai.token_manager._get_current_usage", AsyncMock(return_value=used)):
        remaining = await mgr.get_remaining_budget(TENANT)

    assert remaining == limit - used


@pytest.mark.asyncio
async def test_remaining_budget_clamps_to_zero():
    mgr = TokenManager()

    with patch("src.modules.generator.ai.token_manager._get_plan_limit", AsyncMock(return_value=100)), \
         patch("src.modules.generator.ai.token_manager._get_current_usage", AsyncMock(return_value=200)):
        remaining = await mgr.get_remaining_budget(TENANT)

    assert remaining == 0
