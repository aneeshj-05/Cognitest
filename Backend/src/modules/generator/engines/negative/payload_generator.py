"""
payload_generator.py — Generates valid request payloads from OpenAPI schemas
and applies single-field mutations for negative test cases.

Changes from previous version:
  - _FORMAT_DEFAULTS now uses DYNAMIC values:
      email     → uuid-prefixed address (never clashes with real users)
      date-time → UTC now + 1 day (avoids past-date rejections)
      date      → UTC today + 1 day
      uuid      → uuid4() (never clashes with seeded test data)
      uri       → unchanged (https://example.com is always valid)
  - Added logger.warning when generate_valid_payload returns None so
    silent test-skipping is visible in CI logs.
"""
from __future__ import annotations

import os
import logging
import uuid as _uuid_mod
from datetime import datetime, timedelta, timezone
from typing import Any

from src.modules.generator.spec_parser import Endpoint

logger = logging.getLogger(__name__)

REMOVE_FIELD: object = object()

def _build_format_defaults() -> dict[str, Any]:
    now_utc = datetime.now(tz=timezone.utc)
    tomorrow = now_utc + timedelta(days=1)
    unique_prefix = _uuid_mod.uuid4().hex[:8]
    email_prefix = os.environ.get("NEGATIVE_TEST_EMAIL_PREFIX", "cognitest_")
    return {
        "email":     f"{email_prefix}{unique_prefix}@testmail.invalid",
        "date-time": tomorrow.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":      tomorrow.strftime("%Y-%m-%d"),
        "uuid":      str(_uuid_mod.uuid4()),
        "uri":       "https://example.com",
        "ipv4":      "192.0.2.1",
        "ipv6":      "2001:db8::1",
        "hostname":  "example.com",
        "password":  f"Test@{unique_prefix}99!",
        "phone":     "+15550001234",
    }


def _get_format_defaults() -> dict[str, Any]:
    """Return a fresh set of format defaults for each payload generation call.

    This ensures that UUIDs, emails, and timestamps are unique per test run
    rather than frozen at import time for the entire process lifetime.
    """
    return _build_format_defaults()

def resolve_schema_ref(ref: str, spec: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if not spec or not isinstance(ref, str) or not ref.startswith("#/"):
        return None
    current: Any = spec
    for part in ref[2:].split("/"):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, dict) else None

def _merge_required(left: list[Any] | None, right: list[Any] | None) -> list[Any]:
    merged: list[Any] = []
    for value in (left or []) + (right or []):
        if value not in merged:
            merged.append(value)
    return merged

def _merge_schema_dicts(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if key == "properties" and isinstance(merged.get("properties"), dict) and isinstance(value, dict):
            props = dict(merged["properties"])
            props.update(value)
            merged["properties"] = props
            continue
        if key == "required" and isinstance(value, list):
            merged["required"] = _merge_required(
                merged.get("required") if isinstance(merged.get("required"), list) else None,
                value,
            )
            continue
        if key in {"allOf", "oneOf", "anyOf"}:
            continue
        merged[key] = value
    return merged

def _resolve_schema(
    schema: dict[str, Any] | None,
    spec: dict[str, Any] | None,
    seen_refs: set[str] | None = None,
) -> dict[str, Any] | None:
    if schema is None or not isinstance(schema, dict):
        return schema

    seen_refs = set(seen_refs or set())
    working = dict(schema)

    ref = working.pop("$ref", None)
    if ref:
        if ref in seen_refs:
            return None
        resolved = resolve_schema_ref(ref, spec)
        if not resolved:
            return None
        seen_refs.add(ref)
        working = _merge_schema_dicts(resolved, working)

    if isinstance(working.get("allOf"), list) and working["allOf"]:
        merged: dict[str, Any] = {}
        for variant in working["allOf"]:
            resolved_variant = _resolve_schema(variant, spec, seen_refs)
            if isinstance(resolved_variant, dict):
                merged = _merge_schema_dicts(merged, resolved_variant)
        working = _merge_schema_dicts({k: v for k, v in working.items() if k != "allOf"}, merged)

    for key in ("oneOf", "anyOf"):
        variants = working.get(key)
        if isinstance(variants, list) and variants:
            chosen: dict[str, Any] | None = None
            for variant in variants:
                resolved_variant = _resolve_schema(variant, spec, seen_refs)
                if isinstance(resolved_variant, dict):
                    chosen = resolved_variant
                    break
            working = _merge_schema_dicts({k: v for k, v in working.items() if k != key}, chosen or {})
            break

    if isinstance(working.get("properties"), dict):
        working["properties"] = {
            k: _resolve_schema(v, spec, seen_refs)
            for k, v in working["properties"].items()
        }

    if isinstance(working.get("items"), dict):
        working["items"] = _resolve_schema(working["items"], spec, seen_refs)

    if isinstance(working.get("additionalProperties"), dict):
        working["additionalProperties"] = _resolve_schema(working["additionalProperties"], spec, seen_refs)

    return working

def _fallback_value(schema: dict[str, Any] | None) -> Any:
    if not isinstance(schema, dict):
        return "test"
    schema_type = schema.get("type")
    if schema_type is None and "properties" in schema:
        schema_type = "object"
    if schema_type is None and "items" in schema:
        schema_type = "array"
    if schema_type == "string":
        return _get_format_defaults().get(schema.get("format", ""), "test_value")
    if schema_type == "integer":
        minimum = schema.get("minimum")
        return int(minimum) if minimum is not None else 1
    if schema_type == "number":
        minimum = schema.get("minimum")
        return float(minimum) if minimum is not None else 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "array":
        return []
    if schema_type == "object":
        return {}
    if "enum" in schema and isinstance(schema["enum"], list) and schema["enum"]:
        return schema["enum"][0]
    return "test_value"

def generate_from_schema(schema: dict[str, Any] | None, spec: dict[str, Any] | None = None) -> Any:
    resolved = _resolve_schema(schema, spec)
    if resolved is None:
        return None
    if not isinstance(resolved, dict):
        return None

    if "enum" in resolved and isinstance(resolved["enum"], list) and resolved["enum"]:
        return resolved["enum"][0]

    schema_type = resolved.get("type")
    if schema_type is None:
        if "properties" in resolved or "required" in resolved:
            schema_type = "object"
        elif "items" in resolved:
            schema_type = "array"

    if schema_type == "object":
        properties = resolved.get("properties") if isinstance(resolved.get("properties"), dict) else {}
        required_fields: list[str] = resolved.get("required") if isinstance(resolved.get("required"), list) else []

        payload: dict[str, Any] = {}

        for field_name, field_schema in properties.items():
            value = generate_from_schema(field_schema, spec)
            if value is None:
                if field_name in required_fields:
                    value = _fallback_value(field_schema)
                else:
                    continue
            payload[field_name] = value

        for field_name in required_fields:
            if field_name not in payload:
                field_schema = properties.get(field_name) if isinstance(properties, dict) else None
                payload[field_name] = _fallback_value(field_schema)

        return payload

    if schema_type == "array":
        items = resolved.get("items")
        if not isinstance(items, dict):
            return []
        item_value = generate_from_schema(items, spec)
        if item_value is None:
            item_value = _fallback_value(items)
        min_items = resolved.get("minItems", 0)
        count = max(1, int(min_items)) if min_items else 1
        return [item_value] * count

    if schema_type == "string":
        fmt = resolved.get("format")
        defaults = _get_format_defaults()
        if fmt and fmt in defaults:
            value = defaults[fmt]
        else:
            value = "test_value"
        min_len = resolved.get("minLength")
        if min_len and isinstance(min_len, int) and len(str(value)) < min_len:
            value = value + ("x" * (min_len - len(str(value))))
        max_len = resolved.get("maxLength")
        if max_len and isinstance(max_len, int) and len(str(value)) > max_len:
            value = str(value)[:max_len]
        return value

    if schema_type == "integer":
        minimum = resolved.get("minimum")
        maximum = resolved.get("maximum")
        val = int(minimum) if minimum is not None else 1
        if maximum is not None and val > int(maximum):
            val = int(maximum)
        return val

    if schema_type == "number":
        minimum = resolved.get("minimum")
        maximum = resolved.get("maximum")
        val = float(minimum) if minimum is not None else 1.0
        if maximum is not None and val > float(maximum):
            val = float(maximum)
        return val

    if schema_type == "boolean":
        return True

    return None

def generate_valid_payload(
    endpoint: Endpoint,
    spec: dict[str, Any] | None = None,
) -> dict[str, Any] | list[Any] | None:
    schema = endpoint.body_schema
    if not schema:
        return {}

    active_spec = spec if spec is not None else getattr(endpoint, "spec", None)

    result = generate_from_schema(schema, active_spec)
    if result is None:
        logger.warning(
            "[PayloadGenerator] Could not generate valid payload for %s %s "
            "— body_schema may contain unresolvable $refs. "
            "Pass the full spec dict to fix this.",
            endpoint.method,
            endpoint.path,
        )
    return result

def apply_single_mutation(
    payload: dict[str, Any],
    field: str,
    value: Any,
) -> dict[str, Any]:
    if field not in payload:
        raise ValueError(
            f"apply_single_mutation: field '{field}' not found in payload. "
            f"Available keys: {list(payload.keys())}"
        )
    mutated = dict(payload)
    if value is REMOVE_FIELD:
        del mutated[field]
        return mutated
    mutated[field] = value
    return mutated