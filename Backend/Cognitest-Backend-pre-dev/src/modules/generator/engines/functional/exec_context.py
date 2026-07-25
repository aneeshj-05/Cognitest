"""
Runtime execution context — shared mutable state for a single test-suite run.

Responsibilities:
  - Store extracted variables (auth_token, resource_id, etc.)
  - Track which (path, method) pairs have failed
  - Prevent overwriting valid values with null/empty data
  - Validate extracted IDs before storing them
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# Basic UUID/ObjectId pattern — used to reject obviously-invalid IDs
_VALID_ID_RE = re.compile(
    r"^[a-zA-Z0-9_\-]{3,}$"  # at least 3 printable chars, no spaces
)


def _is_valid_id(value: Any) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    return bool(s) and _VALID_ID_RE.match(s) is not None


class ExecutionContext:
    """
    Thread-safe-ish shared context for one test-suite run.
    All writes go through safe setters that refuse null/empty values.
    """

    def __init__(self) -> None:
        self._vars: dict[str, Any] = {}
        self._failures: dict[str, str] = {}   # (path|method) -> reason
        self._resource_ids: list[str] = []     # ordered; collection IDs preferred

    # --- Variable access ---

    def get(self, key: str, default: Any = None) -> Any:
        return self._vars.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        """Write only if value is non-null and non-empty. Returns True if written."""
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        self._vars[key] = value
        logger.debug("[Context] Set '%s'", key)
        return True

    def set_token(self, token: Any) -> bool:
        """Store auth_token, stripping 'Bearer ' prefix if present."""
        if not token:
            return False
        t = str(token).strip()
        if t.lower().startswith("bearer "):
            t = t[7:].strip()
        return self.set("auth_token", t) if t else False

    def set_resource_id(self, rid: Any, source: str = "creator") -> bool:
        """
        Store a resource ID.  Collection IDs are prepended (higher priority).
        Creator IDs are appended. Invalid IDs are silently rejected.
        """
        if not _is_valid_id(rid):
            logger.debug("[Context] Rejected invalid resource_id: %r", rid)
            return False
        s = str(rid).strip()
        if s not in self._resource_ids:
            if source == "collection":
                self._resource_ids.insert(0, s)   # highest priority
            else:
                self._resource_ids.append(s)
        self._vars["resource_id"] = self._resource_ids[0]
        return True

    def best_resource_id(self) -> str | None:
        return self._resource_ids[0] if self._resource_ids else None

    def has_token(self) -> bool:
        t = self._vars.get("auth_token", "")
        return bool(t and str(t).strip())

    def has_resource_id(self) -> bool:
        return bool(self._resource_ids)

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict suitable for placeholder resolution."""
        d = dict(self._vars)
        if self._resource_ids:
            d["resource_id"] = self._resource_ids[0]
        return d

    # --- Failure tracking ---

    def mark_failure(self, path: str, method: str, reason: str) -> None:
        key = f"{method.upper()}|{path}"
        self._failures[key] = reason
        logger.debug("[Context] Marked failure: %s (%s)", key, reason)

    def is_failed(self, path: str, method: str) -> bool:
        return f"{method.upper()}|{path}" in self._failures

    def failure_reason(self, path: str, method: str) -> str | None:
        return self._failures.get(f"{method.upper()}|{path}")

    @property
    def consecutive_5xx(self) -> int:
        return self._vars.get("_consecutive_5xx", 0)

    def record_5xx(self) -> None:
        self._vars["_consecutive_5xx"] = self.consecutive_5xx + 1

    def reset_5xx_counter(self) -> None:
        self._vars["_consecutive_5xx"] = 0


def make_context(initial: dict[str, Any] | None = None) -> ExecutionContext:
    """Factory — creates a fresh ExecutionContext, optionally seeded from a dict."""
    ctx = ExecutionContext()
    for k, v in (initial or {}).items():
        if k == "auth_token":
            ctx.set_token(v)
        elif k == "resource_id":
            ctx.set_resource_id(v)
        else:
            ctx.set(k, v)
    return ctx
