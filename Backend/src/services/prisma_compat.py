from __future__ import annotations

from typing import Any, Optional


_ALLOWED_TEST_CATEGORIES = {"FUNCTIONAL", "NEGATIVE", "SECURITY", "CONTRACT", "FUZZ"}


def normalize_test_category(value: str | None, *, default: str = "FUNCTIONAL") -> str:
    v = (value or "").strip().upper()
    return v if v in _ALLOWED_TEST_CATEGORIES else default


def _looks_like_unknown_field_error(exc: BaseException) -> bool:
    msg = str(exc)
    return "Field does not exist in enclosing type" in msg


async def create_testsuite_compat(
    *,
    prisma: Any,
    project_id: str,
    suite_name: str,
    category: str,
    created_by_user_id: Optional[str] = None,
    test_type: Optional[str] = None,
    generation_method: Optional[str] = None,
    ai_tokens_used: Optional[int] = None,
    spec_id: Optional[str] = None,
    spec_version: Optional[str] = None,
) -> Any:
    """Create TestSuite in a way that works across Prisma schema/client variants.

    Prisma's create input often requires nested relation `connect` instead of setting
    relation scalar fields like `projectId` / `createdBy` directly.

    Some environments may not yet expose newer optional fields (e.g. `test_type`).
    In that case we retry with a minimal payload.
    """

    base_data: dict[str, Any] = {
        "name": suite_name,
        "category": category,
        "project": {"connect": {"id": project_id}},
        **({"spec": {"connect": {"id": spec_id}}} if spec_id is not None else {}),
        **({"specVersion": spec_version} if spec_version is not None else {}),
    }


    if created_by_user_id:
        # Relation field name in schema is `user` (SuiteCreatedBy).
        base_data["user"] = {"connect": {"id": created_by_user_id}}

    rich_data = {
        **base_data,
        **({"test_type": test_type} if test_type is not None else {}),
        **({"generation_method": generation_method} if generation_method is not None else {}),
        **({"ai_tokens_used": int(ai_tokens_used)} if ai_tokens_used is not None else {}),
    }

    try:
        return await prisma.testsuite.create(data=rich_data)
    except Exception as exc:
        # If the Prisma engine rejects fields (older schema), fall back.
        if _looks_like_unknown_field_error(exc):
            return await prisma.testsuite.create(data=base_data)
        raise


async def create_testrun_compat(
    *,
    prisma: Any,
    project_id: str,
    suite_id: Optional[str] = None,
    environment: str,
    status: str,
    categories: list[str],
    total_tests: int,
    user_id: str,
) -> Any:
    """Create TestRun in a way that works across Prisma schema/client variants.

    Prisma requires nested `connect` for relations like `project` and `user`
    in some client generations, instead of direct scalar assignments.
    """
    from datetime import datetime, timezone

    base_data = {
        "project": {"connect": {"id": project_id}},
        "environment": environment,
        "status": status,
        "categories": categories,
        "total_tests": total_tests,
        "user": {"connect": {"id": user_id}},
        "startedAt": datetime.now(timezone.utc),
    }

    rich_data = {**base_data}
    if suite_id:
        rich_data["suite"] = {"connect": {"id": suite_id}}

    try:
        return await prisma.testrun.create(data=rich_data)
    except Exception as exc:
        if _looks_like_unknown_field_error(exc) or "A value is required" in str(exc):
            # Fallback avoids connecting relation objects that might trigger errors
            return await prisma.testrun.create(data=base_data)
        raise

