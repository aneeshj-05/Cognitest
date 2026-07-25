from __future__ import annotations

import os
import uuid
from typing import Optional


# NOTE: This file is intentionally small and constant-driven.
# It exists to keep the 3 core modules focused and deterministic.

SUPPORTED_FORMATS: set[str] = {
    "email",
    "uuid",
    "date-time",
    "date",
    "uri",
    "ipv4",
    "ipv6",
    "hostname",
}


def _truthy_env(name: str, default: str = "0") -> bool:
    raw = os.getenv(name, default)
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


# When disabled (default), format-negative values are replaced with valid values.
# This prevents many real backends from crashing/hanging during "normal" runs.
STRICT_NEGATIVE_MODE: bool = _truthy_env("COGNITEST_STRICT_NEGATIVE_MODE", "0")

# Optional: allow unique values for formats that commonly hit uniqueness constraints
# (e.g., signup email). On by default for production-like runs.
#
# To preserve determinism, set:
#   COGNITEST_UNIQUE_FORMAT_VALUES=0
# Or to make unique values reproducible across runs, set:
#   COGNITEST_UNIQUE_SEED=<fixed-seed>
UNIQUE_FORMAT_VALUES: bool = _truthy_env("COGNITEST_UNIQUE_FORMAT_VALUES", "1")

# Optional deterministic seed for unique values. When set, values are stable across
# runs (useful for reproducibility). When unset, values are stable within the
# current process only.
UNIQUE_SEED: str = str(os.getenv("COGNITEST_UNIQUE_SEED", "") or "").strip()

_UNIQUE_CACHE: dict[str, str] = {}


def reset_unique_cache() -> None:
    """Clear cached unique values.

    Useful for long-lived worker processes where multiple contract runs happen
    in the same Python process.

    Note: this cache is module-global and not designed for parallel execution.
    If you later run contract generation/execution concurrently (threads/async
    workers), prefer a context-local cache (e.g., ContextVar/thread-local) so
    parallel runs cannot share values.
    """
    _UNIQUE_CACHE.clear()


def _unique_value(key: str, *, prefix: str, suffix: str) -> str:
    """Return a stable-per-process unique value (and optionally stable-per-seed)."""
    cache_key = str(key or "").strip().lower()
    if cache_key in _UNIQUE_CACHE:
        return _UNIQUE_CACHE[cache_key]

    if UNIQUE_SEED:
        u = uuid.uuid5(uuid.NAMESPACE_DNS, f"{UNIQUE_SEED}:{cache_key}")
    else:
        u = uuid.uuid4()

    value = f"{prefix}{u.hex[:8]}{suffix}"
    _UNIQUE_CACHE[cache_key] = value
    return value

# Safe invalid values: invalid enough to violate the intended format, but mild
# enough to avoid triggering pathological backend behavior.
SAFE_INVALID_VALUES: dict[str, str] = {
    "email": "invalid_email",
    "uuid": "not-a-uuid",
    "date-time": "not-a-datetime",
    "date": "not-a-date",
    "uri": "not-a-uri",
    "ipv4": "256.256.256.256",
    "ipv6": "invalid-ipv6",
    "hostname": "invalid_host!",
}


def normalize_content_type(content_type: Optional[str]) -> Optional[str]:
    """
    Normalize media type:
    - strip charset parameters
    - treat vendor JSON types as application/json
    """

    if not content_type:
        return None

    ct = content_type.split(";", 1)[0].strip().lower()

    # Normalize vendor JSON types
    if "+json" in ct:
        return "application/json"

    return ct or None


def valid_value_for_format(fmt: str) -> str:

    fmt = (fmt or "").strip()

    if fmt == "email":
        if UNIQUE_FORMAT_VALUES:
            return _unique_value("email", prefix="user_", suffix="@example.com")
        return "user@example.com"

    if fmt == "uuid":
        # Avoid all-zero UUIDs; some APIs treat them as reserved/invalid.
        return "123e4567-e89b-12d3-a456-426614174000"

    if fmt == "date-time":
        return "2020-01-01T00:00:00Z"

    if fmt == "date":
        return "2020-01-01"

    if fmt == "uri":
        return "https://example.com"

    if fmt == "ipv4":
        return "192.168.1.1"

    if fmt == "ipv6":
        return "2001:db8::1"

    if fmt == "hostname":
        return "api.example.com"

    # Runtime-safe generic fallback.
    return "test"


def invalid_value_for_format(fmt: str) -> str:
    # In safe mode, return a "safe invalid" instead of a valid value.
    # This keeps negative tests meaningful without being overly destructive.
    if not STRICT_NEGATIVE_MODE:
        fmt = (fmt or "").strip()
        return SAFE_INVALID_VALUES.get(fmt, "__invalid__")

    fmt = (fmt or "").strip()

    if fmt == "email":
        return "not-an-email"

    if fmt == "uuid":
        return "invalid-uuid"

    if fmt == "date-time":
        return "2020-99-99T99:99:99Z"

    if fmt == "date":
        return "2020-99-99"

    if fmt == "uri":
        return "not-a-uri"

    if fmt == "ipv4":
        return "999.999.999.999"

    if fmt == "ipv6":
        return "invalid-ipv6"

    if fmt == "hostname":
        return "invalid_host!"

    return "__invalid__"