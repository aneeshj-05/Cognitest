"""
Execution guards — decides whether a test case should run or be skipped.

Rules (in order):
  1. If parent endpoint is in the failure registry → SKIP
  2. If auth_token is required but missing → SKIP
  3. If resource_id is required but missing → SKIP
  4. If any skip_if_missing variable is absent → SKIP
  5. Otherwise → RUN
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .exec_context import ExecutionContext


@dataclass(frozen=True)
class GuardResult:
    should_run: bool
    skip_reason: str = ""      # human-readable reason code
    dependency_chain: list[str] = ()  # which variables were missing


def check_guards(tc: dict, ctx: "ExecutionContext") -> GuardResult:
    """
    Evaluate all pre-execution guards for a test case.

    Args:
        tc : annotated test case dict (must have depends_on, endpoint_roles, etc.)
        ctx: live ExecutionContext for this suite run

    Returns:
        GuardResult with should_run=True to proceed, or skip details.
    """
    path   = tc.get("endpoint_path", "")
    method = (tc.get("method") or "GET").upper()

    # --- Guard 1: parent failure propagation ---
    if ctx.is_failed(path, method):
        reason = ctx.failure_reason(path, method) or "parent_failed"
        return GuardResult(False, f"dependency_failed:{reason}", [f"{method}|{path}"])

    roles = tc.get("endpoint_roles") or []
    deps  = list(tc.get("depends_on") or []) + list(tc.get("skip_if_missing") or [])
    missing: list[str] = []

    # --- Guard 2: auth_token required but absent ---
    if "AUTH_REQUIRED" in roles and not ctx.has_token():
        missing.append("auth_token")

    # --- Guard 3: resource_id required but absent ---
    if "RESOURCE_WITH_ID" in roles and "AUTH_REQUIRED" in roles and not ctx.has_resource_id():
        missing.append("resource_id")

    # --- Guard 4: explicit depends_on variables ---
    ctx_dict = ctx.to_dict()
    for var in deps:
        if var not in missing and not ctx_dict.get(var):
            missing.append(var)

    if missing:
        return GuardResult(False, "missing_dependencies", missing)

    return GuardResult(True)


def skip_result(tc: dict, guard: GuardResult, index: int) -> dict:
    """Build a structured SKIP result compatible with the streaming event format."""
    return {
        "event": "result",
        "index": index,
        "id": tc.get("id"),
        "name": tc.get("name"),
        "endpoint_path": tc.get("endpoint_path", ""),
        "method": (tc.get("method") or "GET").upper(),
        "expected_status": tc.get("expected_status", 200),
        "actual_status": 0,
        "passed": False,
        "status": "SKIP",
        "response_time_ms": 0,
        "response_body": "",
        "response_headers": {},
        "error_message": guard.skip_reason,
        "skip_reason": guard.skip_reason,
        "dependency_chain": list(guard.dependency_chain),
        "execution_phase": tc.get("execution_order", 5),
        "endpoint_roles": tc.get("endpoint_roles", []),
        "log": f"[SKIP] {tc.get('name', '')} — {guard.skip_reason}",
    }
