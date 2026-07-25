"""
Variable resolution engine for multi-step workflow tests.

Provides two core functions:

1. extract_variables(response_body, extract_rules)
   - Applies lightweight JSONPath-style rules to pull values from a response
   - Supports: $.field, $.nested.field, $.data.items[0].id
   - Falls back gracefully if a path is not resolvable

2. resolve_placeholders(template, context)
   - Recursively replaces {{variable}} tokens in strings, dicts, and lists
   - Leaves unknown placeholders untouched (does not raise)
   - Returns a deep copy of the template with substitutions applied

Both functions are pure (no side effects) and require no extra dependencies.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSONPath-style extraction
# ---------------------------------------------------------------------------

_ARRAY_INDEX_RE = re.compile(r"^(.+)\[(\d+)\]$")


def _resolve_path(obj: Any, path_parts: list[str]) -> tuple[Any, bool]:
    """
    Recursively walk an object along the given path parts.

    Returns (value, found).
    """
    if not path_parts:
        return obj, True

    part = path_parts[0]
    rest = path_parts[1:]

    # Handle array indexing: items[0]
    m = _ARRAY_INDEX_RE.match(part)
    if m:
        key = m.group(1)
        idx = int(m.group(2))
        if not isinstance(obj, dict) or key not in obj:
            return None, False
        arr = obj[key]
        if not isinstance(arr, list) or idx >= len(arr):
            return None, False
        return _resolve_path(arr[idx], rest)

    # Normal dict key
    if isinstance(obj, dict) and part in obj:
        return _resolve_path(obj[part], rest)

    # Try list item traversal (returns first match)
    if isinstance(obj, list):
        for item in obj:
            if isinstance(item, dict) and part in item:
                value, found = _resolve_path(item[part], rest)
                if found:
                    return value, True

    return None, False


def extract_variables(
    response_body: dict | list | str | None,
    extract_rules: dict[str, str],
) -> dict[str, Any]:
    """
    Extract variables from a response body using JSONPath-style rules.

    Args:
        response_body: Parsed JSON response (dict or list).
        extract_rules: Mapping of variable_name → JSONPath expression.
                       Example: {"token": "$.data.token", "userId": "$.data.id"}
                       Rules starting with "$." are resolved against the body.
                       Rules starting with "$.data." resolve from body["data"] etc.

    Returns:
        Dict of extracted variables.  Missing/unresolvable paths are omitted.

    Example::

        body = {"data": {"token": "abc123", "user": {"id": "u1"}}}
        rules = {
            "token": "$.data.token",
            "userId": "$.data.user.id",
        }
        result = extract_variables(body, rules)
        # {"token": "abc123", "userId": "u1"}
    """
    if not extract_rules or response_body is None:
        return {}

    result: dict[str, Any] = {}

    for var_name, path_expr in extract_rules.items():
        # Split on "||" to support fallback JSONPaths
        expressions = [p.strip() for p in path_expr.split("||")]

        for expr in expressions:
            if not expr.startswith("$."):
                continue  # skip non-JSONPath expressions

            # Strip leading "$." and split on "."
            raw_path = expr[2:]
            if not raw_path:
                result[var_name] = response_body
                break

            path_parts = raw_path.split(".")
            value, found = _resolve_path(response_body, path_parts)
            if found and value is not None:
                result[var_name] = value
                logger.debug(
                    "[VarResolver] Extracted '%s' via path '%s'",
                    var_name, expr,
                )
                break
        else:
            logger.debug(
                "[VarResolver] Could not resolve '%s' from any path in '%s'",
                var_name, path_expr,
            )

    if result:
        logger.info(
            "[VarResolver] Extracted %d variables: %s",
            len(result), list(result.keys()),
        )

    return result


# ---------------------------------------------------------------------------
# Placeholder substitution
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _substitute(value: str, context: dict[str, Any]) -> str:
    """Replace all {{var}} tokens in a string using context."""
    def replacer(m: re.Match) -> str:
        key = m.group(1)
        if key in context:
            return str(context[key])
        return m.group(0)  # leave unknown placeholders untouched

    return _PLACEHOLDER_RE.sub(replacer, value)


def resolve_placeholders(template: Any, context: dict[str, Any]) -> Any:
    """
    Recursively replace {{variable}} placeholders in a template using context.

    Handles:
    - str  → substitutes in-place
    - dict → recurses into both keys and values
    - list → recurses into each element
    - Other types → returned as-is

    Unknown placeholders are left untouched (no exception is raised).

    Args:
        template: Any JSON-compatible value (str, dict, list, int, bool, None).
        context:  Dict of variable_name → value (values are coerced to str).

    Returns:
        A new object (same structure) with placeholders substituted.

    Example::

        body = {"userId": "{{userId}}", "token": "Bearer {{token}}"}
        ctx  = {"userId": "u1", "token": "abc123"}
        result = resolve_placeholders(body, ctx)
        # {"userId": "u1", "token": "Bearer abc123"}
    """
    if not context:
        return template

    if isinstance(template, str):
        return _substitute(template, context)

    if isinstance(template, dict):
        return {
            _substitute(k, context) if isinstance(k, str) else k: resolve_placeholders(v, context)
            for k, v in template.items()
        }

    if isinstance(template, list):
        return [resolve_placeholders(item, context) for item in template]

    return template


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def get_unresolved_placeholders(template: Any) -> list[str]:
    """
    Return a list of {{variable}} names that were NOT substituted.
    Useful for detecting missing variables before executing a step.
    """
    found: list[str] = []

    if isinstance(template, str):
        found.extend(_PLACEHOLDER_RE.findall(template))
    elif isinstance(template, dict):
        for v in template.values():
            found.extend(get_unresolved_placeholders(v))
    elif isinstance(template, list):
        for item in template:
            found.extend(get_unresolved_placeholders(item))

    return found
