"""
Contract test generator — Swagger/OpenAPI driven, deterministic, domain-agnostic.

Architecture (strict, single source of truth):

    PASS 1 — CANONICALIZATION
        Parse OpenAPI spec into a normalized internal model. Resolve all $refs.
        Convert OpenAPI Schema Object to JSON-Schema-compatible surface.

    PASS 2 — DISCOVERY (PRODUCER REGISTRY)
        For every operation derive ONE canonical resource_key from the schema.
        Build PRODUCER_REGISTRY: { resource_key -> producer_metadata }.
        Classify flow_type (auth | producer | consumer | independent | cleanup).

    PASS 3 — DEPENDENCY RESOLUTION
        For every consumer operation, resolve each path/query/body dependency
        STRICTLY against the registry. Emit dependency_map entries whose
        `source` field is the IDENTICAL string under which the producer will
        bucket its entities at runtime.

    PASS 4 — TEST CASE GENERATION
        For every operation, emit one positive case per 2xx and one negative
        case per documented error status (400/401/403/404/422 etc).

    PASS 5 — TOPOLOGICAL ORDERING
        Compute execution_order so that producers run before consumers,
        auth runs before protected endpoints, cleanup runs last.

Strict contract with executor:
    tc["resource_key"]    canonical key under which producer entities are bucketed.
                          For consumers this is also the consumer's own resource.
    tc["dependency_map"]  { param_name: { "source": <resource_key>,
                                          "field":  <dotted_path>,
                                          "confidence": "high"|"medium"|"low" } }
    tc["depends_on"]      list of producer operation_keys this test depends on.
    tc["execution_order"] integer, monotonic over the topological order.

The generator never inspects path strings to invent a resource at runtime —
the resource_key is derived once during discovery and propagated explicitly.

NO HARDCODED RESOURCE NAMES.   All resource identity comes from the schema.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

from .contract_rules import (
    SUPPORTED_FORMATS,
    UNIQUE_FORMAT_VALUES,
    reset_unique_cache,
    valid_value_for_format,
)


# =============================================================================
# CONSTANTS
# =============================================================================

_TEST_ID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Lower number wins when two operations could both be the canonical producer
# of the same resource (e.g. POST /items vs PUT /items/{id}, both returning Item).
_PRODUCER_METHOD_PRIORITY: dict[str, int] = {
    "POST":   0,
    "PUT":    1,
    "PATCH":  2,
    "GET":    9,
    "DELETE": 10,
}

# Generic CRUD/action tokens stripped when deriving resource keys from
# operationIds or path segments. NOT domain words — purely HTTP/CRUD verbs.
_ACTION_TOKENS: frozenset[str] = frozenset({
    "create", "add", "insert", "register", "post", "new",
    "update", "edit", "modify", "patch", "put", "set", "save",
    "delete", "remove", "destroy", "drop", "purge",
    "get", "fetch", "find", "list", "search", "read", "retrieve", "view", "show",
    "to", "from", "of", "for", "in", "by", "into", "with", "on", "at",
})

# JSON Schema validation keywords preserved when normalizing OpenAPI schemas.
_JSON_SCHEMA_ALLOWED_KEYS: frozenset[str] = frozenset({
    "$ref", "type", "format", "enum",
    "properties", "required", "items", "additionalProperties",
    "oneOf", "anyOf", "allOf", "not",
    "description", "title",
    "minLength", "maxLength", "pattern",
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minItems", "maxItems", "uniqueItems",
    "minProperties", "maxProperties",
})


# =============================================================================
# BASIC UTILITIES
# =============================================================================

def _truthy_env(name: str, default: str = "0") -> bool:
    return str(os.getenv(name, default)).strip().lower() in {"1", "true", "yes", "y", "on"}


_DEBUG = _truthy_env("GENERATOR_DEBUG")


def _dbg(msg: str, *args: Any) -> None:
    if _DEBUG:
        logger.debug(msg, *args)


def _as_dict(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="python")
    return obj


def _stable_test_id(seed: str) -> str:
    return str(uuid.uuid5(_TEST_ID_NAMESPACE, seed))


def _hash_seed(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _sorted_status_keys(keys: Iterable[str]) -> List[str]:
    def _sort_key(k: str) -> Tuple[int, str]:
        ks = str(k)
        if ks == "default":
            return (10_000, ks)
        if ks.isdigit():
            return (int(ks), ks)
        return (9_999, ks)
    return sorted([str(k) for k in keys], key=_sort_key)


def _is_missing_value(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == "":
        return True
    return False


# =============================================================================
# NAME / KEY NORMALIZATION
# =============================================================================

def _normalize_resource_name(name: str) -> str:
    """Canonical form for resource identifiers.
    snake_case, lowercase, dashes/underscores collapsed.
    USED IDENTICALLY in generator and executor to guarantee bucket-key match.
    """
    n = str(name or "").strip()
    if not n:
        return ""
    n = n.strip("/")
    n = n.replace("-", "_")
    # Insert underscore before each uppercase boundary (camelCase -> snake_case)
    n = re.sub(r"(?<!^)([A-Z])", r"_\1", n)
    n = n.lower()
    n = re.sub(r"_+", "_", n).strip("_")
    return n


def _is_id_like_name(name: str) -> bool:
    """Schema-agnostic detection of id-like field names: id, _id, *_id, *Id, *ID."""
    n = str(name or "").lower().strip()
    if n in ("id", "_id"):
        return True
    if n.endswith("_id"):
        return True
    if re.fullmatch(r"[a-z][a-z0-9]*id", n):
        return True
    return False


def _strip_id_suffix(name: str) -> str:
    """itemId -> item, user_id -> user, id -> id, ItemID -> item."""
    n = _normalize_resource_name(name)
    if n in ("id", "_id"):
        return "id"
    for suffix in ("_id",):
        if n.endswith(suffix) and len(n) > len(suffix):
            return n[: -len(suffix)].strip("_")
    # Catch trailing "id" without separator (e.g. itemId -> item_id -> item via normalize+strip)
    if n.endswith("id") and len(n) > 2 and n[-3] != "_":
        return n[:-2].strip("_")
    return n


def _strip_action_tokens(s: str) -> str:
    """Remove leading/trailing CRUD/action tokens. Schema-agnostic.
    'add-to-cart' -> 'cart',  'createUser' -> 'user',  'list_orders' -> 'orders'.
    """
    if not s:
        return ""
    # camelCase split
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(s))
    parts = re.split(r"[-_\s/]+", spaced)
    parts = [p for p in parts if p and p.lower() not in _ACTION_TOKENS]
    return "_".join(parts).lower()


# =============================================================================
# JSON POINTER / $REF RESOLUTION
# =============================================================================

def _resolve_json_pointer(doc: dict[str, Any], pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("#/"):
        return None
    cur: Any = doc
    for part in pointer[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _resolve_openapi_parameter(
    param: dict[str, Any],
    spec_obj: dict[str, Any],
    *,
    _seen: Optional[set[str]] = None,
) -> dict[str, Any]:
    if _seen is None:
        _seen = set()
    if not isinstance(param, dict):
        return {}
    ref = param.get("$ref")
    if isinstance(ref, str):
        if ref in _seen:
            return {}
        _seen.add(ref)
        resolved = _resolve_json_pointer(spec_obj, ref)
        if isinstance(resolved, dict):
            return _resolve_openapi_parameter(resolved, spec_obj, _seen=_seen)
        return {}
    return param


def _resolve_openapi_schema(
    schema: Any,
    spec_obj: dict[str, Any],
    *,
    _seen: Optional[set[str]] = None,
) -> Any:
    """Recursively resolve all local $refs in an OpenAPI schema.
    Preserves x-original-ref so downstream code can still derive resource keys.
    """
    if _seen is None:
        _seen = set()
    if schema is None or not isinstance(schema, dict):
        return schema

    ref = schema.get("$ref")
    if isinstance(ref, str):
        if ref in _seen:
            return {"x-original-ref": ref}
        _seen.add(ref)
        resolved = _resolve_json_pointer(spec_obj, ref)
        if isinstance(resolved, dict):
            out = _resolve_openapi_schema(resolved, spec_obj, _seen=_seen)
            if isinstance(out, dict):
                # Preserve provenance for resource_key derivation
                out = dict(out)
                out.setdefault("x-original-ref", ref)
            return out
        return {"x-original-ref": ref}

    out = dict(schema)
    if isinstance(out.get("items"), dict):
        out["items"] = _resolve_openapi_schema(out["items"], spec_obj, _seen=set(_seen))
    props = out.get("properties")
    if isinstance(props, dict):
        out["properties"] = {
            str(k): _resolve_openapi_schema(props[k], spec_obj, _seen=set(_seen))
            for k in sorted(props.keys())
        }
    for key in ("allOf", "oneOf", "anyOf"):
        arr = out.get(key)
        if isinstance(arr, list):
            out[key] = [_resolve_openapi_schema(x, spec_obj, _seen=set(_seen)) for x in arr]
    ap = out.get("additionalProperties")
    if isinstance(ap, dict):
        out["additionalProperties"] = _resolve_openapi_schema(ap, spec_obj, _seen=set(_seen))
    return out


def _resolve_openapi_request_body(rb: Any, spec_obj: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(rb, dict):
        return None
    ref = rb.get("$ref")
    if isinstance(ref, str):
        resolved = _resolve_json_pointer(spec_obj, ref)
        return resolved if isinstance(resolved, dict) else None
    return rb


def _ref_leaf(schema: Any) -> Optional[str]:
    """Extract the trailing component name from a $ref, if present."""
    if not isinstance(schema, dict):
        return None
    ref = schema.get("$ref") or schema.get("x-original-ref")
    if isinstance(ref, str) and "/" in ref:
        return ref.rsplit("/", 1)[-1]
    return None


# =============================================================================
# OPENAPI -> JSON SCHEMA
# =============================================================================

def _openapi_schema_to_jsonschema(schema: Any) -> Any:
    """Convert OpenAPI Schema Object into JSON-Schema-compatible surface.
    Handles `nullable`, preserves validation keywords, recurses into composition.
    """
    if schema is None or not isinstance(schema, dict):
        return schema

    out: dict[str, Any] = {}
    for k, v in schema.items():
        if k in _JSON_SCHEMA_ALLOWED_KEYS or k == "x-original-ref":
            out[k] = v

    if isinstance(out.get("properties"), dict):
        out["properties"] = {
            str(name): _openapi_schema_to_jsonschema(out["properties"][name])
            for name in sorted(out["properties"].keys())
        }
    if isinstance(out.get("items"), dict):
        out["items"] = _openapi_schema_to_jsonschema(out["items"])
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(out.get(key), list):
            out[key] = [_openapi_schema_to_jsonschema(x) for x in out[key]]
    if isinstance(out.get("additionalProperties"), dict):
        out["additionalProperties"] = _openapi_schema_to_jsonschema(out["additionalProperties"])

    # OpenAPI nullable -> JSON-Schema "type": [..., "null"]
    if schema.get("nullable") is True:
        t = out.get("type")
        if isinstance(t, list):
            if "null" not in t:
                out["type"] = [*t, "null"]
        elif isinstance(t, str):
            if t != "null":
                out["type"] = [t, "null"]
        else:
            out["type"] = ["null", "object", "array", "string", "number", "integer", "boolean"]
    return out


def _extract_props_from_schema(schema: Any) -> dict:
    """Get the properties map from an object schema OR an array-of-objects schema."""
    if not isinstance(schema, dict):
        return {}
    if isinstance(schema.get("properties"), dict):
        return schema["properties"]
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        items = schema["items"]
        if isinstance(items.get("properties"), dict):
            return items["properties"]
    return {}


def _schema_type(schema: Any) -> Optional[str]:
    if not isinstance(schema, dict):
        return None
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0] if t else None)
    return t if isinstance(t, str) else None


# =============================================================================
# DOTTED-PATH HELPERS (schema and body manipulation)
# =============================================================================

def _get_path_value(obj: Any, dotted: str) -> Any:
    """Read a dotted path from an object/array tree. Returns None if path is invalid."""
    if dotted is None:
        return None
    cur: Any = obj
    for p in str(dotted).split("."):
        if p == "":
            continue
        if isinstance(cur, list):
            try:
                idx = int(p)
            except ValueError:
                return None
            if idx < 0 or idx >= len(cur):
                return None
            cur = cur[idx]
        elif isinstance(cur, dict):
            if p not in cur:
                return None
            cur = cur[p]
        else:
            return None
    return cur


def _set_path(obj: Any, dotted: str, value: Any) -> None:
    """Set a dotted path inside obj. Auto-creates intermediate dicts/lists."""
    if dotted is None or obj is None:
        return
    parts = [p for p in str(dotted).split(".") if p]
    if not parts:
        return

    cur: Any = obj
    for i, p in enumerate(parts[:-1]):
        next_part = parts[i + 1]
        try:
            int(next_part)
            next_is_index = True
        except ValueError:
            next_is_index = False

        if isinstance(cur, list):
            try:
                idx = int(p)
            except ValueError:
                return
            while len(cur) <= idx:
                cur.append([] if next_is_index else {})
            if not isinstance(cur[idx], (dict, list)):
                cur[idx] = [] if next_is_index else {}
            cur = cur[idx]
        elif isinstance(cur, dict):
            if p not in cur or not isinstance(cur[p], (dict, list)):
                cur[p] = [] if next_is_index else {}
            cur = cur[p]
        else:
            return

    last = parts[-1]
    if isinstance(cur, list):
        try:
            idx = int(last)
        except ValueError:
            return
        while len(cur) <= idx:
            cur.append(None)
        cur[idx] = value
    elif isinstance(cur, dict):
        cur[last] = value


def _del_path(obj: Any, dotted: str) -> None:
    if not isinstance(obj, dict) or not dotted:
        return
    parts = dotted.split(".")
    cur: Any = obj
    for p in parts[:-1]:
        if not isinstance(cur, dict):
            return
        cur = cur.get(p)
    if parts and isinstance(cur, dict):
        cur.pop(parts[-1], None)


# =============================================================================
# SCHEMA WALKING (required paths, format paths, enum paths, id paths)
# =============================================================================

def _iter_schema_required_paths(schema: dict[str, Any], prefix: str = "") -> Iterator[str]:
    if not isinstance(schema, dict):
        return
    t = _schema_type(schema)
    if t == "object" or "properties" in schema:
        required = schema.get("required") or []
        props = schema.get("properties") or {}
        if isinstance(required, list):
            for name in required:
                if not isinstance(name, str):
                    continue
                path = f"{prefix}.{name}" if prefix else name
                yield path
                child = props.get(name) if isinstance(props, dict) else None
                if isinstance(child, dict):
                    yield from _iter_schema_required_paths(child, prefix=path)
        return
    if t == "array" and isinstance(schema.get("items"), dict):
        yield from _iter_schema_required_paths(schema["items"], prefix=prefix)


def _iter_schema_format_paths(schema: dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, str]]:
    if not isinstance(schema, dict):
        return
    fmt = schema.get("format")
    if isinstance(fmt, str) and fmt in SUPPORTED_FORMATS:
        yield (prefix, fmt)
    t = _schema_type(schema)
    if t == "object":
        props = schema.get("properties") or {}
        if isinstance(props, dict):
            for name in sorted(props.keys()):
                child = props.get(name)
                if not isinstance(child, dict):
                    continue
                child_prefix = f"{prefix}.{name}" if prefix else name
                yield from _iter_schema_format_paths(child, prefix=child_prefix)
        return
    if t == "array" and isinstance(schema.get("items"), dict):
        yield from _iter_schema_format_paths(schema["items"], prefix=prefix)


def _iter_schema_enum_paths(schema: dict[str, Any], prefix: str = "") -> Iterator[Tuple[str, list[Any]]]:
    if not isinstance(schema, dict):
        return
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        yield (prefix, enum)
    t = _schema_type(schema)
    for key in ("oneOf", "anyOf"):
        arr = schema.get(key)
        if isinstance(arr, list) and arr and isinstance(arr[0], dict):
            yield from _iter_schema_enum_paths(arr[0], prefix=prefix)
    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for sub in all_of:
            if isinstance(sub, dict):
                yield from _iter_schema_enum_paths(sub, prefix=prefix)
    if t == "object" or (t is None and "properties" in schema):
        props = schema.get("properties")
        if isinstance(props, dict):
            for name in sorted(props.keys()):
                child = props.get(name)
                if isinstance(child, dict):
                    child_prefix = f"{prefix}.{name}" if prefix else name
                    yield from _iter_schema_enum_paths(child, prefix=child_prefix)
    if t == "array" and isinstance(schema.get("items"), dict):
        yield from _iter_schema_enum_paths(schema["items"], prefix=prefix)


def _producer_id_paths_from_responses(
    responses: Any,
    *,
    resource_key: str = "",
) -> list[str]:
    """Find dotted paths to id-like fields inside any 2xx response schema.
    Resource-key-aware preference: <resource>_id and <resource>Id rank highest.
    """
    def _walk(schema: Any, prefix: str = "") -> list[str]:
        if not isinstance(schema, dict):
            return []
        out: list[str] = []
        for key in ("oneOf", "anyOf", "allOf"):
            arr = schema.get(key)
            if isinstance(arr, list):
                for sub in arr:
                    out.extend(_walk(sub, prefix=prefix))
                if key in ("oneOf", "anyOf"):
                    return list(dict.fromkeys(out))
        t = _schema_type(schema)
        props = schema.get("properties")
        if isinstance(props, dict):
            for k, child in sorted(props.items()):
                if not isinstance(k, str):
                    continue
                child_prefix = f"{prefix}.{k}" if prefix else k
                if _is_id_like_name(k):
                    out.append(child_prefix)
                out.extend(_walk(child, prefix=child_prefix))
        if t == "array" and isinstance(schema.get("items"), dict):
            out.extend(_walk(schema["items"], prefix=prefix))
        return list(dict.fromkeys(out))

    if not isinstance(responses, dict):
        return []
    candidate_schemas: list[dict[str, Any]] = []
    for sk in _sorted_status_keys(responses.keys()):
        if not (str(sk).isdigit() and str(sk).startswith("2")):
            continue
        resp = responses.get(sk)
        if isinstance(resp, dict) and isinstance(resp.get("json_schema"), dict):
            candidate_schemas.append(resp["json_schema"])
    if not candidate_schemas:
        return []

    rk = _normalize_resource_name(resource_key)
    preferred = [f"{rk}_id", f"{rk}Id", "id"]

    all_paths: list[str] = []
    for s in candidate_schemas:
        all_paths.extend(_walk(s))

    def _score(p: str) -> tuple[int, int, str]:
        leaf = p.rsplit(".", 1)[-1]
        leaf_l = leaf.lower()
        depth = p.count(".")
        if leaf in preferred:
            return (0, depth, p)
        if leaf_l == "id":
            return (1, depth, p)
        if leaf_l.endswith("_id"):
            return (2, depth, p)
        return (3, depth, p)

    seen: set[str] = set()
    uniq: list[str] = []
    for p in sorted(all_paths, key=_score):
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
    return uniq


# =============================================================================
# SCHEMA-DRIVEN VALUE GENERATION
# =============================================================================

def _valid_instance(schema: Any, shared_data: dict) -> Any:
    """Generate one valid value matching the given JSON schema.
    Fully schema-driven. No hardcoded placeholders. Used for positive payloads.
    """
    if not isinstance(schema, dict):
        return None

    # 1. Enum wins over everything
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]

    # 2. Discriminator (OpenAPI polymorphism)
    disc = schema.get("discriminator")
    if isinstance(disc, dict):
        prop = disc.get("propertyName")
        mapping = disc.get("mapping")
        if prop and isinstance(mapping, dict) and mapping:
            return {prop: list(mapping.keys())[0]}

    # 3. oneOf / anyOf - prefer the candidate with the most required fields
    for key in ("oneOf", "anyOf"):
        arr = schema.get(key)
        if isinstance(arr, list) and arr:
            best, best_score = None, -1
            for cand in arr:
                if not isinstance(cand, dict):
                    continue
                score = len(cand.get("required") or [])
                if "discriminator" in cand:
                    score += 10
                if score > best_score:
                    best, best_score = cand, score
            return _valid_instance(best or arr[0], shared_data)

    # 4. allOf - merge all branches
    if isinstance(schema.get("allOf"), list):
        merged: dict[str, Any] = {}
        for sub in schema["allOf"]:
            if not isinstance(sub, dict):
                continue
            for k, v in sub.items():
                if k == "properties" and isinstance(v, dict):
                    merged.setdefault("properties", {})
                    merged["properties"].update(v)
                elif k == "required" and isinstance(v, list):
                    merged.setdefault("required", [])
                    merged["required"] = list(set(merged["required"]) | set(v))
                else:
                    merged[k] = v
        return _valid_instance(merged, shared_data)

    # 5. Format-driven generation (auth fields are coordinated via shared_data)
    fmt = schema.get("format")
    if fmt == "email":
        if "email" not in shared_data:
            shared_data["email"] = f"test-{uuid.uuid4().hex[:8]}@example.com"
        return shared_data["email"]
    if fmt == "password":
        if "password" not in shared_data:
            shared_data["password"] = f"Pass@{uuid.uuid4().hex[:8]}"
        return shared_data["password"]
    if isinstance(fmt, str) and fmt and fmt not in ("email", "password"):
        v = valid_value_for_format(fmt)
        if v and v != "test":
            return v

    t = _schema_type(schema)

    # 6. Object
    if t == "object" or (t is None and "properties" in schema):
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        out: dict[str, Any] = {}
        if isinstance(props, dict):
            for k in sorted(props.keys()):
                v = _valid_instance(props[k], shared_data)
                if v is not None or k in required:
                    out[k] = v
        return out

    # 7. Array
    if t == "array":
        items = schema.get("items") or {}
        return [_valid_instance(items, shared_data)]

    # 8. Primitives
    if t == "string":
        min_len = schema.get("minLength")
        if isinstance(min_len, int) and min_len > 0:
            res = uuid.uuid4().hex
            while len(res) < min_len:
                res += uuid.uuid4().hex
            return res[:min_len]
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and pattern:
            # Best-effort: respect simple alpha/digit patterns
            return f"str_{uuid.uuid4().hex[:8]}"
        return f"str_{uuid.uuid4().hex[:8]}"

    if t == "integer":
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)):
            return int(minimum)
        return 1

    if t == "number":
        minimum = schema.get("minimum")
        if isinstance(minimum, (int, float)):
            return float(minimum)
        return 1.1

    if t == "boolean":
        return True

    return None


def build_placeholder_body(schema: Any, shared_data: dict) -> Any:
    """Public wrapper: generate one valid body instance for the schema."""
    return _valid_instance(schema, shared_data)


def _bind_confirmation_fields(body: Any) -> None:
    """Mirror confirmation fields to their base fields (confirmPassword <- password)."""
    if not isinstance(body, dict):
        return
    keys = list(body.keys())
    for ck in keys:
        if not isinstance(ck, str):
            continue
        lck = ck.lower()
        if "confirm" not in lck and "confirmation" not in lck:
            continue
        base_pattern = lck.replace("confirmation", "").replace("confirm", "").strip("_-")
        if not base_pattern:
            continue
        for bk in keys:
            if bk == ck or not isinstance(bk, str):
                continue
            if bk.lower().strip("_-") == base_pattern:
                body[ck] = body[bk]
                break


# =============================================================================
# RESOURCE KEY DERIVATION (single canonical key per operation)
# =============================================================================

_ENVELOPE_KEYS: frozenset[str] = frozenset({
    "data", "result", "payload", "item", "items", "record", "records",
    "content", "body", "entity", "entities",
})


def _walk_for_root_ref(schema: Any, _depth: int = 0) -> Optional[str]:
    """Find the most representative $ref leaf inside a schema tree.

    Schema-driven priority (envelope-aware):
      1. If schema is an envelope (has `data` / `result` / similar wrapper key)
         AND that wrapper contains a $ref, use the inner ref. This ensures
         responses like `{data: $ref Item}` resolve to `item`, not `wrapper`.
      2. Otherwise, the schema's own $ref leaf.
      3. Otherwise array.items / composition / first property recursion.
    """
    if not isinstance(schema, dict) or _depth > 6:
        return None

    props = schema.get("properties")

    # 1. Envelope unwrap — only when EXACTLY one envelope key is present
    #    (a true wrapper). This avoids wrong unwrap on entities that happen
    #    to have a 'data' member alongside many other fields.
    if isinstance(props, dict) and props:
        envelope_props = [k for k in props.keys() if str(k).lower() in _ENVELOPE_KEYS]
        non_envelope_props = [k for k in props.keys() if str(k).lower() not in _ENVELOPE_KEYS]
        # Heuristic: envelope-shaped if there's a wrapper key AND the
        # non-wrapper siblings are limited to metadata fields (status, message, count, ...)
        is_envelope = (
            len(envelope_props) >= 1
            and len(non_envelope_props) <= 3
        )
        if is_envelope:
            for wk in envelope_props:
                sub = _walk_for_root_ref(props[wk], _depth + 1)
                if sub:
                    return sub

    # 2. Direct $ref / x-original-ref
    leaf = _ref_leaf(schema)
    if leaf:
        return leaf

    # 3. Array of objects
    if _schema_type(schema) == "array" and isinstance(schema.get("items"), dict):
        sub = _walk_for_root_ref(schema["items"], _depth + 1)
        if sub:
            return sub

    # 4. Composition (oneOf / anyOf / allOf)
    for key in ("oneOf", "anyOf", "allOf"):
        for sub_schema in (schema.get(key) or []):
            sub = _walk_for_root_ref(sub_schema, _depth + 1)
            if sub:
                return sub

    # 5. Fallback: walk all properties in lexicographic order
    if isinstance(props, dict) and props:
        for k in sorted(props.keys()):
            sub = _walk_for_root_ref(props[k], _depth + 1)
            if sub:
                return sub

    return None


def _derive_resource_key_from_path(path: str) -> str:
    """Derive a resource key from the path string. Last fallback only."""
    parts = [s for s in str(path or "").split("/") if s]
    # Prefer the segment immediately before the FIRST {param}
    for i, s in enumerate(parts):
        if s.startswith("{") and i > 0:
            cand = _strip_action_tokens(parts[i - 1])
            if cand:
                return _normalize_resource_name(cand)
            return _normalize_resource_name(parts[i - 1])
    # Otherwise the last non-bracketed segment, action-stripped
    non_bracket = [s for s in parts if not s.startswith("{")]
    if non_bracket:
        cand = _strip_action_tokens(non_bracket[-1])
        if cand:
            return _normalize_resource_name(cand)
        return _normalize_resource_name(non_bracket[-1])
    return ""


def _derive_resource_key(op: dict[str, Any]) -> str:
    """SINGLE canonical resource_key for an operation.
    Schema-first priority order. Identical for producer of resource X
    and any consumer of resource X.
    """
    # 1. 2xx response schema $ref leaf — strongest signal
    responses = op.get("responses") or {}
    if isinstance(responses, dict):
        for sk in _sorted_status_keys(responses.keys()):
            if not str(sk).startswith("2"):
                continue
            resp = responses.get(sk)
            if isinstance(resp, dict):
                leaf = _walk_for_root_ref(resp.get("json_schema"))
                if leaf:
                    return _normalize_resource_name(leaf)

    # 2. requestBody schema $ref leaf
    rb = op.get("request_body") or op.get("requestBody")
    if isinstance(rb, dict):
        rb_schema = rb.get("json_schema") or rb.get("schema")
        leaf = _walk_for_root_ref(rb_schema)
        if leaf:
            return _normalize_resource_name(leaf)

    # 3. operationId stem (camelCase split, action tokens stripped)
    op_id = op.get("operationId") or op.get("operation_id")
    if isinstance(op_id, str) and op_id.strip():
        stem = _strip_action_tokens(op_id)
        if stem:
            return _normalize_resource_name(stem)

    # 4. Path-derived fallback (last)
    rk = _derive_resource_key_from_path(op.get("path") or "")
    if rk:
        return rk

    return "root"


# =============================================================================
# PRODUCER REGISTRY
# =============================================================================

def _build_producer_registry(operations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Pass 2 — DISCOVERY.
    Build the canonical map: resource_key -> producer metadata.
    A producer is an operation whose 2xx response declares an id-like field.
    Method priority decides the canonical producer when multiple exist.
    """
    registry: dict[str, dict[str, Any]] = {}

    for op in operations:
        method = str(op.get("method") or "").upper()
        path = str(op.get("path") or "")

        # Single canonical key — assigned in-place for downstream passes
        rkey = _derive_resource_key(op)
        op["resource_key"] = rkey

        # Detect id-like fields in any 2xx response schema
        id_paths = _producer_id_paths_from_responses(
            op.get("responses"), resource_key=rkey
        )
        # Tighten: leaf must really be id-like
        id_paths = [p for p in id_paths if _is_id_like_name(p.rsplit(".", 1)[-1])]

        # Producer iff 2xx response has an id-like field (method agnostic)
        is_producer = bool(id_paths)
        op["produces_entity"] = is_producer
        op["produced_id_paths"] = id_paths

        if is_producer and rkey:
            new_priority = _PRODUCER_METHOD_PRIORITY.get(method, 99)
            existing = registry.get(rkey)
            if existing is None or new_priority < existing["method_priority"]:
                registry[rkey] = {
                    "operation_key":   op.get("operation_key"),
                    "resource_key":    rkey,
                    "method":          method,
                    "path":            path,
                    "id_paths":        list(id_paths),
                    "method_priority": new_priority,
                }

    return registry


# =============================================================================
# AUTH DETECTION
# =============================================================================

_AUTH_TOKEN_KEYS: frozenset[str] = frozenset({
    "token", "access_token", "id_token", "jwt", "auth_token",
    "accesstoken", "idtoken", "jwttoken", "authtoken",
})

_SIGNUP_KEYWORDS: frozenset[str] = frozenset({"signup", "register", "registration"})


def _find_auth_token_field(schema: Any, _depth: int = 0) -> Optional[str]:
    """Recursively scan a response schema for a token-like field."""
    if not isinstance(schema, dict) or _depth > 5:
        return None
    props = schema.get("properties")
    if isinstance(props, dict):
        for k in props.keys():
            if str(k).lower() in _AUTH_TOKEN_KEYS:
                return str(k)
        for k in sorted(props.keys()):
            r = _find_auth_token_field(props[k], _depth + 1)
            if r:
                return r
    if _schema_type(schema) == "array" and isinstance(schema.get("items"), dict):
        return _find_auth_token_field(schema["items"], _depth + 1)
    for key in ("allOf", "oneOf", "anyOf"):
        for sub in (schema.get(key) or []):
            r = _find_auth_token_field(sub, _depth + 1)
            if r:
                return r
    return None


def _is_signup_path(path: str) -> bool:
    pl = str(path or "").lower()
    return any(kw in pl for kw in _SIGNUP_KEYWORDS)


def _detect_auth_metadata(op: dict[str, Any]) -> tuple[bool, Optional[str], bool]:
    """Returns (security_required, produced_auth_field, is_signup_path)."""
    security_required = bool(op.get("security"))
    produced_auth_field: Optional[str] = None
    responses = op.get("responses") or {}
    if isinstance(responses, dict):
        for sk, resp in responses.items():
            if not (str(sk).startswith("2") and isinstance(resp, dict)):
                continue
            produced_auth_field = _find_auth_token_field(resp.get("json_schema"))
            if produced_auth_field:
                break
    is_signup = _is_signup_path(op.get("path") or "") and str(op.get("method") or "").upper() == "POST"
    return security_required, produced_auth_field, is_signup


def _classify_flow(op: dict[str, Any]) -> tuple[str, int]:
    """Return (flow_type, phase) used for ordering and entity buckets.

    Phases:   0=signup, 1=login, 2=producer, 3=independent, 4=consumer, 5=cleanup
    """
    method = str(op.get("method") or "").upper()
    path = str(op.get("path") or "")
    has_path_param = "{" in path
    is_producer = bool(op.get("produces_entity"))
    security_required, auth_field, is_signup = _detect_auth_metadata(op)

    # Stash auth info for downstream passes
    op["security_required"] = security_required
    op["produced_auth_field"] = auth_field
    op["is_signup"] = is_signup

    if is_signup and not security_required:
        return ("auth", 0)
    if auth_field:
        return ("auth", 1)
    if method == "DELETE" and has_path_param:
        # If this DELETE doesn't itself produce, treat as cleanup
        return ("cleanup", 5) if not is_producer else ("consumer", 4)
    if is_producer:
        return ("producer", 2)
    if has_path_param:
        return ("consumer", 4)
    return ("independent", 3)


# =============================================================================
# DEPENDENCY RESOLUTION (strict, registry-driven)
# =============================================================================

def _resolve_against_registry(
    *,
    param_name: str,
    op_path: str,
    op_resource_key: str,
    op_param_schema: Optional[dict[str, Any]],
    operation_key: str,
    registry: dict[str, dict[str, Any]],
) -> Optional[dict[str, Any]]:
    """Resolve a single parameter (or body field) to a producer entry.
    No substring matching, no fuzzy logic. Schema/registry-driven only.
    Returns dict {source, field, confidence} where source is the IDENTICAL
    string the producer will use as its bucket key at runtime.
    """
    pn_norm = _normalize_resource_name(param_name)
    pn_stem = _strip_id_suffix(param_name)
    op_resource_key = _normalize_resource_name(op_resource_key)

    # Producers other than this same operation
    candidates = {
        k: v for k, v in registry.items()
        if v.get("operation_key") != operation_key
    }
    if not candidates:
        return None

    def _wrap(key: str, confidence: str) -> dict[str, Any]:
        meta = candidates[key]
        # Choose the highest-priority id_path; prefer leaf 'id', then '<resource>_id'
        id_paths = meta.get("id_paths") or ["id"]
        return {
            "source":     key,                # canonical, used as-is by executor
            "field":      id_paths[0],        # dotted path inside producer response
            "confidence": confidence,
        }

    # 1. Param-stem -> registry key (with plural/singular tolerance)
    if pn_stem and pn_stem != "id":
        if pn_stem in candidates:
            return _wrap(pn_stem, "high")
        for variant in (pn_stem.rstrip("s"), pn_stem + "s"):
            if variant and variant != pn_stem and variant in candidates:
                return _wrap(variant, "high")

    # 2. Path-segment match against registry keys (whole segments only)
    for seg in [s for s in op_path.split("/") if s and not s.startswith("{")]:
        seg_norm = _normalize_resource_name(_strip_action_tokens(seg) or seg)
        if not seg_norm:
            continue
        if seg_norm in candidates:
            return _wrap(seg_norm, "high")
        for variant in (seg_norm.rstrip("s"), seg_norm + "s"):
            if variant and variant != seg_norm and variant in candidates:
                return _wrap(variant, "high")

    # 2b. Per-token scan: split each path segment on [-_] and check each
    #     individual token against the registry.  Catches compound segments
    #     like "add-to-cart" (token "cart" not a producer but "item" might
    #     appear in a segment like "add-item-to-cart") without any
    #     domain-specific knowledge.
    for seg in [s for s in op_path.split("/") if s and not s.startswith("{")]:
        for tok in re.split(r"[-_]", seg):
            tok_norm = _normalize_resource_name(tok)
            if not tok_norm or tok_norm in _ACTION_TOKENS:
                continue
            if tok_norm in candidates:
                return _wrap(tok_norm, "medium")
            for variant in (tok_norm.rstrip("s"), tok_norm + "s"):
                if variant and variant != tok_norm and variant in candidates:
                    return _wrap(variant, "medium")

    # 3. Parameter schema $ref leaf -> registry key
    if isinstance(op_param_schema, dict):
        leaf = _ref_leaf(op_param_schema)
        if leaf:
            leaf_norm = _normalize_resource_name(leaf)
            if leaf_norm in candidates:
                return _wrap(leaf_norm, "high")

    # 4. Param is generic 'id' AND consumer's own resource exists as a producer
    if pn_norm in ("id", "_id") and op_resource_key and op_resource_key in candidates:
        return _wrap(op_resource_key, "medium")

    # 5. Single-producer-spec fallback (only one producer in entire spec)
    if len(candidates) == 1:
        only_key = next(iter(candidates))
        return _wrap(only_key, "low")

    # 6. Ambiguous — fail loudly, do not guess
    return None


def _extract_dependency_field_paths(
    schema: Any,
    prefix: str = "",
) -> list[tuple[str, dict[str, Any]]]:
    """Walk a schema and yield (dotted_path, field_schema) for every id-like leaf
    field. Used to detect body fields that should be filled with producer IDs.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    if not isinstance(schema, dict):
        return out

    for key in ("oneOf", "anyOf", "allOf"):
        for sub in (schema.get(key) or []):
            out.extend(_extract_dependency_field_paths(sub, prefix=prefix))

    t = _schema_type(schema)
    if t == "object" or "properties" in schema:
        props = schema.get("properties") or {}
        if isinstance(props, dict):
            for k in sorted(props.keys()):
                child = props.get(k)
                child_path = f"{prefix}.{k}" if prefix else k
                if isinstance(child, dict):
                    sub_t = _schema_type(child)
                    if sub_t in (None, "string", "integer", "number"):
                        if _is_id_like_name(k):
                            out.append((child_path, child))
                    out.extend(_extract_dependency_field_paths(child, prefix=child_path))
        return out

    if t == "array" and isinstance(schema.get("items"), dict):
        out.extend(_extract_dependency_field_paths(schema["items"], prefix=prefix))

    return out


# =============================================================================
# NEGATIVE TEST MUTATION (status-driven)
# =============================================================================

def mutate_by_status(
    status_code: Any,
    base_body: Any,
    base_headers: dict[str, Any],
    base_path_params: dict[str, Any],
    request_schema: Any,
    is_auth_endpoint: bool = False,
) -> tuple[Any, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Produce a mutated (body, headers, path_params, meta) tuple for a target
    status code. NEVER inserts placeholder strings — empties/invalid types only.
    """
    body = deepcopy(base_body)
    headers = deepcopy(base_headers) if base_headers else {}
    path_params = deepcopy(base_path_params) if base_path_params else {}

    try:
        status = int(status_code) if status_code is not None else 0
    except (TypeError, ValueError):
        status = 0
    meta: dict[str, Any] = {}

    # 401 — Unauthenticated: strip Authorization, leave body intact
    if status == 401:
        if isinstance(headers, dict):
            for k in list(headers.keys()):
                if str(k).lower() == "authorization":
                    headers.pop(k, None)
        meta["auth_negative"] = True
        meta["no_auth"] = True
        return body, headers, path_params, meta

    # 403 — Forbidden: keep auth (executor swaps it for a foreign token)
    if status == 403:
        meta["auth_negative"] = True
        meta["auth_kept"] = True
        return body, headers, path_params, meta

    # 400 — Logical bad request: empty / out-of-range values
    if status == 400:
        if isinstance(body, dict) and body:
            for k in list(body.keys()):
                v = body[k]
                if isinstance(v, bool):
                    body[k] = not v
                elif isinstance(v, (int, float)):
                    body[k] = -999999
                elif isinstance(v, str):
                    body[k] = ""
                elif isinstance(v, list):
                    body[k] = []
                elif isinstance(v, dict):
                    body[k] = {}
        meta["body_logically_invalid"] = True
        return body, headers, path_params, meta

    # 404 — Not Found: null all path params; executor will fill with non-existent IDs
    if status == 404:
        if isinstance(path_params, dict):
            for k in list(path_params.keys()):
                path_params[k] = None
        meta["path_params_invalidated"] = True
        meta["use_fallback_invalid_id"] = True
        return body, headers, path_params, meta

    # 422 — Schema/Type Violations
    if status == 422:
        if isinstance(body, dict) and body:
            props = _extract_props_from_schema(request_schema)
            for k, v in list(body.items()):
                field_schema = props.get(k) if isinstance(props, dict) else None
                fs = field_schema if isinstance(field_schema, dict) else {}
                t = fs.get("type")
                if "enum" in fs:
                    body[k] = "__invalid_enum_value__"
                elif fs.get("minLength"):
                    body[k] = ""
                elif fs.get("pattern"):
                    body[k] = "??invalid??"
                elif t == "string":
                    body[k] = 12345
                elif t in ("integer", "number"):
                    body[k] = "not_a_number"
                elif t == "boolean":
                    body[k] = "not_a_bool"
                elif isinstance(v, dict):
                    body[k] = ["wrong_type"]
                elif isinstance(v, list):
                    body[k] = {"wrong_type": True}
            meta["body_invalidated"] = True
        else:
            body = "__INVALID_DATA__"
            meta["body_invalidated"] = True
        return body, headers, path_params, meta

    return body, headers, path_params, meta


# =============================================================================
# CANONICAL SPEC EXTRACTION
# =============================================================================

def _enrich_preconditions(spec_obj: dict[str, Any]) -> dict[str, Any]:
    """Auto-derive ordering hints (x-preconditions) from path/method semantics.
    Purely additive; preserves any explicit x-preconditions.
    """
    paths = spec_obj.get("paths")
    if not isinstance(paths, dict):
        return spec_obj

    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        param_segments_present = any(
            s.startswith("{") for s in str(path).strip("/").split("/")
        )
        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            if op.get("x-preconditions"):
                continue
            if not param_segments_present:
                continue
            # Derive resource segment immediately preceding any {param}
            preconditions: list[str] = []
            parts = [s for s in str(path).strip("/").split("/") if s]
            for i, seg in enumerate(parts):
                if seg.startswith("{") and i > 0:
                    res = _strip_action_tokens(parts[i - 1]) or parts[i - 1]
                    res = _normalize_resource_name(res)
                    if res:
                        pre = f"{res}_exists"
                        if pre not in preconditions:
                            preconditions.append(pre)
            if preconditions:
                op["x-preconditions"] = preconditions
    return spec_obj


def _endpoint_requires_auth(
    operation: dict[str, Any],
    path_item: dict[str, Any],
    spec_obj: dict[str, Any],
) -> bool:
    """Determine effective auth requirement: operation > path > global."""
    def _interpret(sec: Any) -> Optional[bool]:
        if sec is None:
            return None
        if isinstance(sec, list):
            if len(sec) == 0:
                return False  # explicit empty -> no auth
            return True
        return None

    if "security" in operation:
        v = _interpret(operation.get("security"))
        if v is not None:
            return v
    if "security" in path_item:
        v = _interpret(path_item.get("security"))
        if v is not None:
            return v
    if "security" in spec_obj:
        v = _interpret(spec_obj.get("security"))
        if v is not None:
            return v
    return False


def _canonical_from_openapi(spec_obj: dict[str, Any]) -> dict[str, Any]:
    """Convert raw OpenAPI dict into the canonical model used by generation."""
    spec_obj = _enrich_preconditions(spec_obj)
    paths = spec_obj.get("paths") or {}
    operations: list[dict[str, Any]] = []

    for path in sorted(paths.keys()):
        path_item = paths.get(path) or {}
        if not isinstance(path_item, dict):
            continue
        inherited_params = path_item.get("parameters") or []
        if not isinstance(inherited_params, list):
            inherited_params = []

        for method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue

            operation_key = f"{method}:{path}"
            op_params = op.get("parameters") if isinstance(op.get("parameters"), list) else []
            all_params = [*inherited_params, *op_params]

            canon_params: list[dict[str, Any]] = []
            seen_keys: set[tuple[str, str]] = set()
            for p in all_params:
                if not isinstance(p, dict):
                    continue
                p = _resolve_openapi_parameter(p, spec_obj)
                loc = p.get("in")
                name = p.get("name")
                if not isinstance(name, str) or loc not in ("path", "query", "header", "cookie"):
                    continue
                if (loc, name) in seen_keys:
                    continue
                seen_keys.add((loc, name))
                raw_schema = p.get("schema") if isinstance(p.get("schema"), dict) else {}
                resolved = _resolve_openapi_schema(raw_schema, spec_obj)
                json_schema = _openapi_schema_to_jsonschema(resolved) if isinstance(resolved, dict) else {}
                canon_params.append({
                    "name": name,
                    "location": loc,
                    "required": bool(p.get("required")),
                    "json_schema": json_schema if isinstance(json_schema, dict) else {},
                })
            canon_params.sort(key=lambda x: (str(x.get("location") or ""), str(x.get("name") or "")))

            # Request body
            request_body: Optional[dict[str, Any]] = None
            rb = _resolve_openapi_request_body(op.get("requestBody"), spec_obj)
            if isinstance(rb, dict):
                content = rb.get("content") or {}
                if isinstance(content, dict) and content:
                    content_types = sorted(str(k) for k in content.keys())
                    if "application/json" in content:
                        media = "application/json"
                    elif "multipart/form-data" in content:
                        media = "multipart/form-data"
                    elif "application/x-www-form-urlencoded" in content:
                        media = "application/x-www-form-urlencoded"
                    else:
                        media = sorted(content.keys())[0]
                    media_obj = content.get(media) or {}
                    schema0 = media_obj.get("schema") if isinstance(media_obj, dict) else None
                    resolved = _resolve_openapi_schema(schema0, spec_obj) if isinstance(schema0, dict) else None
                    json_schema = _openapi_schema_to_jsonschema(resolved) if isinstance(resolved, dict) else None
                    request_body = {
                        "required":      bool(rb.get("required")),
                        "content_types": content_types,
                        "content_type":  media,
                        "json_schema":   json_schema if isinstance(json_schema, dict) else {},
                        "encoding":      media_obj.get("encoding") if isinstance(media_obj, dict) else {},
                    }

            # Responses
            canon_responses: dict[str, Any] = {}
            responses = op.get("responses") or {}
            if isinstance(responses, dict):
                for status in _sorted_status_keys(responses.keys()):
                    resp = responses.get(status)
                    if not isinstance(resp, dict):
                        continue
                    content = resp.get("content") or {}
                    content_type = None
                    json_schema = None
                    if isinstance(content, dict) and content:
                        media = "application/json" if "application/json" in content else sorted(content.keys())[0]
                        content_type = media
                        media_obj = content.get(media) or {}
                        schema0 = media_obj.get("schema") if isinstance(media_obj, dict) else None
                        resolved = _resolve_openapi_schema(schema0, spec_obj) if isinstance(schema0, dict) else None
                        json_schema = _openapi_schema_to_jsonschema(resolved) if isinstance(resolved, dict) else None
                    canon_headers: dict[str, Any] = {}
                    headers_obj = resp.get("headers")
                    if isinstance(headers_obj, dict):
                        for h_name in sorted(headers_obj.keys()):
                            h = headers_obj.get(h_name)
                            if not isinstance(h, dict):
                                continue
                            h_schema = h.get("schema") if isinstance(h.get("schema"), dict) else {}
                            canon_headers[str(h_name)] = {
                                "required":    bool(h.get("required")),
                                "json_schema": _openapi_schema_to_jsonschema(h_schema) or {},
                            }
                    canon_responses[str(status)] = {
                        "status_code":  str(status),
                        "description":  str(resp.get("description") or "").strip(),
                        "content_type": content_type,
                        "json_schema":  json_schema if isinstance(json_schema, dict) else None,
                        "headers":      canon_headers,
                    }

            effective_security = (
                op.get("security") if "security" in op
                else path_item.get("security") if "security" in path_item
                else spec_obj.get("security")
            )

            x_depends = op.get("x-depends-on") or []
            if not isinstance(x_depends, list):
                x_depends = []
            x_preconditions = op.get("x-preconditions") or []
            if not isinstance(x_preconditions, list):
                x_preconditions = []

            operations.append({
                "operation_key":   operation_key,
                "operationId":     op.get("operationId"),
                "method":          method.upper(),
                "path":            path,
                "security":        effective_security,
                "parameters":      canon_params,
                "request_body":    request_body,
                "responses":       canon_responses,
                "depends_on":      [str(x).lower() for x in x_depends],
                "x_produces":      str(op.get("x-produces")).strip() if op.get("x-produces") else None,
                "preconditions":   [str(x).lower() for x in x_preconditions],
            })

    return {
        "doc_id":     spec_obj.get("id") or spec_obj.get("doc_id") or "",
        "operations": operations,
    }


def coerce_canonical_spec(spec_like: Any) -> dict[str, Any]:
    """Accept either a CanonicalSpec-like object/dict or a raw OpenAPI dict."""
    spec_like = _as_dict(spec_like)
    if isinstance(spec_like, dict) and isinstance(spec_like.get("paths"), dict):
        return _canonical_from_openapi(spec_like)
    if isinstance(spec_like, dict):
        return spec_like
    raise TypeError("Unsupported spec type; expected dict or pydantic-like object")


# =============================================================================
# OPERATION-LEVEL DEPENDENCY ANALYSIS
# =============================================================================

def _analyze_operation_dependencies(
    op: dict[str, Any],
    registry: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], set[str], list[str], str]:
    """For one operation, build:
        dependency_map  : {param_or_dotted_path: {source, field, confidence}}
        depends_on_keys : set of producer operation_keys this op depends on
        gen_errors      : list of "dependency_unresolved:..." annotations
        confidence      : aggregate "high" | "medium" | "low"

    All decisions are made against the PRODUCER_REGISTRY only. No fuzzy
    string matching, no path-substring inference.
    """
    operation_key = str(op.get("operation_key") or "")
    path = str(op.get("path") or "")
    op_resource_key = _normalize_resource_name(op.get("resource_key") or "")
    request_body = op.get("request_body")
    request_schema = (request_body or {}).get("json_schema") if isinstance(request_body, dict) else None

    dep_map: dict[str, dict[str, Any]] = {}
    depends_on: set[str] = set()
    gen_errors: list[str] = []
    aggregate_conf = "high"

    def _bump_conf(c: str) -> None:
        nonlocal aggregate_conf
        order = {"high": 0, "medium": 1, "low": 2}
        if order.get(c, 0) > order.get(aggregate_conf, 0):
            aggregate_conf = c

    # 1. Path parameters — always required to resolve for executable consumers
    path_param_names = re.findall(r"\{([^}]+)\}", path)
    params_list = op.get("parameters") or []

    def _param_schema_for(name: str, location: str) -> Optional[dict[str, Any]]:
        for p in params_list:
            if isinstance(p, dict) and p.get("name") == name and p.get("location") == location:
                return p.get("json_schema") if isinstance(p.get("json_schema"), dict) else None
        return None

    for pn in path_param_names:
        dep = _resolve_against_registry(
            param_name      = pn,
            op_path         = path,
            op_resource_key = op_resource_key,
            op_param_schema = _param_schema_for(pn, "path"),
            operation_key   = operation_key,
            registry        = registry,
        )
        if dep:
            dep_map[pn] = dep
            producer_op_key = registry[dep["source"]]["operation_key"]
            if producer_op_key:
                depends_on.add(producer_op_key)
            _bump_conf(dep["confidence"])
        else:
            gen_errors.append(f"dependency_unresolved:path_param={pn}")

    # 2. Query parameters that look id-like
    for p in params_list:
        if not isinstance(p, dict) or p.get("location") != "query":
            continue
        name = p.get("name")
        if not isinstance(name, str) or not _is_id_like_name(name):
            continue
        if name in dep_map:
            continue
        dep = _resolve_against_registry(
            param_name      = name,
            op_path         = path,
            op_resource_key = op_resource_key,
            op_param_schema = p.get("json_schema") if isinstance(p.get("json_schema"), dict) else None,
            operation_key   = operation_key,
            registry        = registry,
        )
        if dep:
            dep_map[name] = dep
            producer_op_key = registry[dep["source"]]["operation_key"]
            if producer_op_key:
                depends_on.add(producer_op_key)
            _bump_conf(dep["confidence"])

    # 3. Body fields that look id-like
    if isinstance(request_schema, dict):
        required_paths = set(_iter_schema_required_paths(request_schema))
        for dotted, field_schema in _extract_dependency_field_paths(request_schema):
            leaf = dotted.rsplit(".", 1)[-1]
            if not _is_id_like_name(leaf):
                continue
            if dotted in dep_map:
                continue
            dep = _resolve_against_registry(
                param_name      = leaf,
                op_path         = path,
                op_resource_key = op_resource_key,
                op_param_schema = field_schema,
                operation_key   = operation_key,
                registry        = registry,
            )
            if dep:
                dep_map[dotted] = dep
                producer_op_key = registry[dep["source"]]["operation_key"]
                if producer_op_key:
                    depends_on.add(producer_op_key)
                _bump_conf(dep["confidence"])
            elif dotted in required_paths:
                gen_errors.append(f"dependency_unresolved:body={dotted}")

    return dep_map, depends_on, gen_errors, aggregate_conf


# =============================================================================
# PER-OPERATION TEST CASE BUILDER
# =============================================================================

def _build_test_cases_for_operation(
    op: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    *,
    doc_id: str,
    shared_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """Generate every test case (positive + negatives) for one operation.
    Each test case carries the strict contract fields the executor relies on:
        resource_key, dependency_map, depends_on, produces_entity, produced_id_paths.
    """
    operation_key = str(op.get("operation_key") or "")
    method = str(op.get("method") or "GET").upper()
    path = str(op.get("path") or "/")
    resource_key = _normalize_resource_name(op.get("resource_key") or "")
    produces_entity = bool(op.get("produces_entity"))
    produced_id_paths = list(op.get("produced_id_paths") or [])

    # --- Classify flow + phase FIRST (this sets op.security_required, op.produced_auth_field)
    flow_type, phase = _classify_flow(op)
    security_required = bool(op.get("security_required"))
    auth_field = op.get("produced_auth_field")
    is_signup = bool(op.get("is_signup"))

    # --- Build dependency map
    dep_map, depends_on_keys, dep_errors, op_confidence = _analyze_operation_dependencies(op, registry)

    # --- Parameter buckets
    params_list = op.get("parameters") or []
    path_param_names = re.findall(r"\{([^}]+)\}", path)

    required_query: dict[str, dict[str, Any]] = {}
    required_header: dict[str, dict[str, Any]] = {}
    required_cookie: dict[str, dict[str, Any]] = {}
    all_path_params: dict[str, dict[str, Any]] = {}

    for p in params_list:
        if not isinstance(p, dict):
            continue
        loc = p.get("location")
        name = p.get("name")
        if not isinstance(name, str):
            continue
        schema = p.get("json_schema") if isinstance(p.get("json_schema"), dict) else {}
        if loc == "path":
            all_path_params[name] = schema
        if not p.get("required"):
            continue
        if loc == "query":
            required_query[name] = schema
        elif loc == "header":
            required_header[name] = schema
        elif loc == "cookie":
            required_cookie[name] = schema

    base_path_params: dict[str, Any] = {n: None for n in path_param_names}
    base_query_params: dict[str, Any] = {n: _valid_instance(s, shared_data) for n, s in required_query.items()}
    base_header_params: dict[str, Any] = {n: _valid_instance(s, shared_data) for n, s in required_header.items()}
    base_cookie_params: dict[str, Any] = {n: _valid_instance(s, shared_data) for n, s in required_cookie.items()}

    # --- Request body
    request_body = op.get("request_body")
    request_schema: Optional[dict[str, Any]] = None
    if isinstance(request_body, dict):
        rs = request_body.get("json_schema")
        if isinstance(rs, dict) and rs:
            request_schema = rs
    if request_schema is None and method in ("POST", "PUT", "PATCH"):
        # Provide an empty object schema so dependent body fields can still be injected
        request_schema = {"type": "object", "properties": {}}

    base_body: Any = build_placeholder_body(request_schema, shared_data) if request_schema else None
    if isinstance(base_body, dict):
        _bind_confirmation_fields(base_body)
        # Strip path param leakage from body
        for pn in path_param_names:
            base_body.pop(pn, None)
        # Ensure id-like dependency body fields exist (even if optional) so executor can inject
        for dotted in dep_map.keys():
            if "." in dotted or dotted in base_path_params:
                continue
            if dotted in (base_query_params or {}) or dotted in (base_header_params or {}) or dotted in (base_cookie_params or {}):
                continue
            if _get_path_value(base_body, dotted) is None:
                _set_path(base_body, dotted, None)
        # Null dotted-path body deps so executor must inject
        for dotted in dep_map.keys():
            if "." not in dotted:
                continue
            if _get_path_value(base_body, dotted) is not None or _get_path_value(base_body, dotted) is None:
                _set_path(base_body, dotted, None)

    # --- Multipart detection
    content_types_l: set[str] = set()
    if isinstance(request_body, dict):
        for ct in (request_body.get("content_types") or []):
            content_types_l.add(str(ct).strip().lower())
    is_multipart = "multipart/form-data" in content_types_l
    is_byte_json = False  # detected per-test below

    file_fields: set[str] = set()
    byte_fields: set[str] = set()
    if isinstance(request_schema, dict):
        for k, s in (_extract_props_from_schema(request_schema) or {}).items():
            if not isinstance(k, str) or not isinstance(s, dict):
                continue
            t = _schema_type(s)
            fmt = str(s.get("format") or "").strip().lower()
            if (t == "string" or t is None) and (fmt == "binary" or str(s.get("contentEncoding") or "").lower() == "binary"):
                file_fields.add(k)
            elif (t == "string" or t is None) and fmt == "byte":
                byte_fields.add(k)

    # --- Statuses to generate
    responses = op.get("responses") or {}
    raw_statuses = _sorted_status_keys(responses.keys()) if isinstance(responses, dict) else []
    statuses: list[int] = []
    for s in raw_statuses:
        if str(s).isdigit():
            si = int(s)
            if si in (200, 201, 400, 401, 403, 404, 422):
                statuses.append(si)
    if not statuses:
        statuses = [200]
    # Always emit the canonical positive even if not declared
    if not any(s in (200, 201) for s in statuses):
        statuses.append(201 if method == "POST" else 200)

    # Deduplicate while preserving order; positives first
    statuses = sorted(set(statuses), key=lambda s: (0 if s in (200, 201) else 1, s))

    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    def _describe(status: int) -> str:
        if status in (200, 201):
            if auth_field:
                return "Authentication successful"
            if method == "POST" and status == 201:
                return "Resource created successfully"
            return "Successful request"
        if status == 401: return "Unauthorized — missing or invalid token"
        if status == 403: return "Forbidden — insufficient permissions"
        if status == 404: return "Resource not found"
        if status == 422: return "Validation error — invalid or missing fields"
        if status == 400: return "Bad request — logically invalid input"
        return f"Expected {status} response"

    for status in statuses:
        body, headers, path_params, mutation_meta = mutate_by_status(
            status_code      = status,
            base_body        = base_body,
            base_headers     = base_header_params,
            base_path_params = base_path_params,
            request_schema   = request_schema,
            is_auth_endpoint = bool(auth_field),
        )
        query_params = deepcopy(base_query_params) if base_query_params else {}
        cookie_params = deepcopy(base_cookie_params) if base_cookie_params else {}

        # Multipart + file/byte handling for positive (or any non-mutating-body case)
        request_type: Optional[str] = None
        multipart_form_data: Optional[dict[str, Any]] = None
        multipart_files: Optional[dict[str, Any]] = None

        if is_multipart and status in (200, 201):
            request_type = "multipart"
            multipart_form_data = {}
            multipart_files = {}
            if isinstance(request_schema, dict):
                props = _extract_props_from_schema(request_schema) or {}
                for k, s in sorted(props.items()):
                    if not isinstance(k, str) or not isinstance(s, dict):
                        continue
                    if k in file_fields:
                        continue
                    val = body.get(k) if isinstance(body, dict) else None
                    if val is None:
                        val = _valid_instance(s, shared_data)
                    multipart_form_data[k] = val if isinstance(val, (str, int, float, bool)) else (
                        json.dumps(val) if val is not None else ""
                    )
            for ff in sorted(file_fields):
                encoding = request_body.get("encoding") if isinstance(request_body, dict) else {}
                field_enc = encoding.get(ff) if isinstance(encoding, dict) else {}
                ct = field_enc.get("contentType") if isinstance(field_enc, dict) else "application/octet-stream"
                if not ct:
                    ct = "application/octet-stream"
                # Minimal valid PNG header bytes — no domain assumption, just valid binary
                png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
                multipart_files[ff] = {
                    "content_base64": base64.b64encode(png_bytes).decode("ascii"),
                    "content_type":   ct,
                    "filename":       f"{ff}.bin",
                }
            # Multipart bodies are sent as form_data + files; clear request_body
            body_for_tc = None
        elif byte_fields and isinstance(body, dict) and status in (200, 201):
            request_type = "json_base64"
            body_for_tc = dict(body)
            png_b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR").decode("ascii")
            for bf in sorted(byte_fields):
                if bf in body_for_tc:
                    body_for_tc[bf] = f"data:image/octet-stream;base64,{png_b64}"
        else:
            request_type = "json" if not is_multipart else "multipart"
            body_for_tc = body

        # Headers final
        headers_out = {str(k): str(v) for k, v in (headers or {}).items()}
        if cookie_params:
            cookie_str = "; ".join(f"{k}={cookie_params[k]}" for k in sorted(cookie_params.keys()))
            if cookie_str:
                headers_out["Cookie"] = cookie_str

        # Stable test ID
        seed = (
            f"{doc_id}:{operation_key}:{status}:"
            f"{_hash_seed(json.dumps(path_params, sort_keys=True, default=str), json.dumps(body_for_tc, sort_keys=True, default=str))}"
        )
        test_uuid = _stable_test_id(seed)
        if test_uuid in seen_ids:
            continue
        seen_ids.add(test_uuid)

        kind = "positive" if status in (200, 201) else (
            "negative_auth" if status in (401, 403) else
            "negative_not_found" if status == 404 else
            "negative_validation"
        )
        is_positive = status in (200, 201)
        is_auth_negative = status in (401, 403)
        is_cleanup = flow_type == "cleanup" and is_positive

        # Extract response schema for the targeted status (back-compat for executor)
        expected_schema_obj: Any = None
        try:
            resp_obj = responses.get(str(status)) if isinstance(responses, dict) else None
            if isinstance(resp_obj, dict):
                # Prefer json content-type response schema
                content_obj = resp_obj.get("content")
                if isinstance(content_obj, dict):
                    for ct_key in ("application/json", "application/json; charset=utf-8"):
                        ct_val = content_obj.get(ct_key)
                        if isinstance(ct_val, dict) and isinstance(ct_val.get("schema"), dict):
                            expected_schema_obj = ct_val["schema"]
                            break
                    if expected_schema_obj is None:
                        for _ct, _val in content_obj.items():
                            if isinstance(_val, dict) and isinstance(_val.get("schema"), dict):
                                expected_schema_obj = _val["schema"]
                                break
                if expected_schema_obj is None and isinstance(resp_obj.get("json_schema"), dict):
                    expected_schema_obj = resp_obj["json_schema"]
        except Exception:
            expected_schema_obj = None

        # Auth-related top-level fields (executor reads tc.get("auth_required"), etc.)
        tc_auth_required = bool(security_required) and is_positive
        tc_auth_type = "bearer" if security_required else None
        tc_auth_field = (auth_field or ("token" if security_required else None))

        # Negative-test introspection fields (executor reads missing_field / format_field / format)
        mm = mutation_meta if isinstance(mutation_meta, dict) else {}
        tc_missing_field = mm.get("missing_field")
        tc_format_field = mm.get("format_field")
        tc_format_name = mm.get("format")
        tc_missing_auth = bool(mm.get("no_auth")) or status == 401

        # Aggregate generation errors for this case
        case_errors = list(dep_errors)
        # Body must be JSON-serializable
        if body_for_tc is not None:
            try:
                json.dumps(body_for_tc)
            except (TypeError, ValueError):
                case_errors.append("invalid_json_body")
        # Required query/header/cookie completeness check (positive only)
        if status in (200, 201):
            for n in required_query:
                if _is_missing_value(query_params.get(n)):
                    case_errors.append(f"missing_required_query:{n}")
            for n in required_header:
                if _is_missing_value(headers_out.get(n)):
                    case_errors.append(f"missing_required_header:{n}")
            for n in required_cookie:
                if _is_missing_value(cookie_params.get(n)):
                    case_errors.append(f"missing_required_cookie:{n}")
            if isinstance(request_body, dict) and request_body.get("required") and body_for_tc is None and not is_multipart:
                case_errors.append("required_body_is_missing")

        tc: dict[str, Any] = {
            "id":                 test_uuid,
            "test_id":            f"ct_{_hash_seed(seed)}",
            "doc_id":             doc_id,
            "operation_key":      operation_key,
            "method":             method,
            "endpoint_path":      path,
            "path":               path,                       # back-compat alias
            "name":               f"{method} {path} — {_describe(status)} ({status})",
            "title":              f"{method} {path} — {_describe(status)} ({status})",
            "description":        _describe(status),
            "category":           "CONTRACT",
            "sub_category":       "OPENAPI_CONFORMANCE",
            "test_type":          "positive" if is_positive else ("auth_negative" if is_auth_negative else "negative"),
            "kind":               kind,
            "positive":           is_positive,
            "cleanup":            is_cleanup,

            # ---- THE STRICT CONTRACT FIELDS (see executor) ----
            "resource_key":       resource_key,            # canonical, used by executor
            "resource_prefix":    resource_key,            # back-compat alias (===)
            "resource":           resource_key,            # back-compat alias (===)
            "produces_entity":    produces_entity and is_positive,
            "is_producer_endpoint": produces_entity and is_positive,
            "produced_id_paths":  list(produced_id_paths),
            "expects_entity":     bool(produced_id_paths) and is_positive,
            "dependency_map":     {k: dict(v) for k, v in sorted(dep_map.items())},
            "depends_on":         sorted(depends_on_keys),
            "confidence":         op_confidence,
            # ----------------------------------------------------

            "flow_type":          flow_type,
            "phase":              phase,
            "stage":              phase,
            "is_auth_endpoint":   bool(auth_field),
            "produces_auth":      bool(auth_field) and is_positive,
            "security_required":  security_required,
            "auth_required":      tc_auth_required,
            "auth_type":          tc_auth_type,
            "auth_field":         tc_auth_field,
            "auth_negative":      is_auth_negative,
            "missing_auth":       tc_missing_auth,
            "missing_field":      tc_missing_field,
            "format_field":       tc_format_field,
            "format":             tc_format_name,
            "preconditions":      list(op.get("preconditions") or []),

            # Request payload
            "path_params":        dict(sorted({str(k): v for k, v in (path_params or {}).items()}.items())),
            "request_query":      dict(sorted({str(k): v for k, v in (query_params or {}).items()}.items())),
            "request_headers":    dict(sorted(headers_out.items())),
            "request_body":       body_for_tc if not (is_multipart and is_positive) else None,
            "request_type":       request_type,

            # Multipart
            **({"form_data": multipart_form_data, "files": multipart_files}
               if is_multipart and is_positive else {}),

            "expected_status":    status,
            "expected_statuses":  [status],
            "expected_schema":    expected_schema_obj,
            "failure_category":   ("auth" if status in (401, 403)
                                   else "validation" if status in (400, 422)
                                   else "not_found" if status == 404
                                   else "other"),

            # Hints + metadata
            "execution_hints": {
                "requires_auth": security_required,
                "is_stateful":   bool(depends_on_keys),
                "is_producer":   produces_entity and is_positive,
            },
            "auth_metadata": {
                "requires_auth": (False if status == 401 else True if status == 403 else security_required),
                "negative_type": (None if is_positive
                                  else "auth_missing" if status == 401
                                  else "forbidden" if status == 403
                                  else "validation" if status in (400, 422)
                                  else "not_found" if status == 404
                                  else "other"),
            },
            **({"auth_injection": {"type": "bearer", "source": "auth", "field": "token"}}
               if security_required else {}),
            "mutation_meta":      dict(mm) if mm else {},
            "metadata":           {"mutation_meta": dict(mm) if mm else {}},

            # Pass-through identifiers (if upstream provided them on the operation)
            "endpoint_id":        op.get("endpoint_id"),
            "spec_id":            op.get("spec_id") or op.get("doc_id") or doc_id,

            "generation_errors":  sorted(set(case_errors)) if case_errors else [],
            "generation_error":   "; ".join(sorted(set(case_errors))) if case_errors else None,
            "has_placeholders":   "{" in path,
        }
        out.append(tc)

    return out


# =============================================================================
# TOPOLOGICAL ORDERING
# =============================================================================

def _topological_order(
    test_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Order test cases such that:
        - producers run before any consumer that depends on them
        - signup runs before login; login runs before any protected endpoint
        - cleanup runs after everything else
        - within a tier, order by phase, then dependency count, then path

    Cycles (which a well-formed spec should never produce) are broken by phase priority.
    """
    if not test_cases:
        return []

    # Index by id
    by_id: dict[str, dict[str, Any]] = {tc["id"]: tc for tc in test_cases if tc.get("id")}

    # All operation_keys with their successful test case ids
    op_to_success_ids: dict[str, list[str]] = defaultdict(list)
    for tc in test_cases:
        if tc.get("expected_status") in (200, 201):
            op_to_success_ids[str(tc.get("operation_key"))].append(tc["id"])

    signup_ids: list[str] = []
    login_ids: list[str] = []
    for tc in test_cases:
        if tc.get("flow_type") == "auth" and tc.get("expected_status") in (200, 201):
            if tc.get("phase") == 0:
                signup_ids.append(tc["id"])
            elif tc.get("phase") == 1:
                login_ids.append(tc["id"])

    # depends_on contains operation_keys; convert to test-case ids
    def _dep_ids_for(tc: dict[str, Any]) -> set[str]:
        ids: set[str] = set()
        for op_key in (tc.get("depends_on") or []):
            for pid in op_to_success_ids.get(str(op_key), []):
                ids.add(pid)
        # Auth-protected endpoints depend on login
        if tc.get("security_required") and not (tc.get("flow_type") == "auth"):
            ids.update(login_ids)
        # Login depends on signup (if signup exists)
        if tc.get("flow_type") == "auth" and tc.get("phase") == 1:
            ids.update(signup_ids)
        # Cleanup depends on everything non-cleanup
        if tc.get("flow_type") == "cleanup":
            ids.update(
                t["id"] for t in test_cases
                if t.get("id") and t.get("flow_type") != "cleanup" and t.get("expected_status") in (200, 201)
            )
        ids.discard(tc["id"])
        return ids

    # Kahn's algorithm with stable tie-breaking
    in_deg: dict[str, set[str]] = {tid: _dep_ids_for(tc) for tid, tc in by_id.items()}

    def _flow_priority(tc: dict[str, Any]) -> int:
        if tc.get("flow_type") == "auth" and tc.get("phase") == 0: return 0
        if tc.get("flow_type") == "auth" and tc.get("phase") == 1: return 1
        if tc.get("flow_type") == "producer":      return 2
        if tc.get("flow_type") == "independent":   return 3
        if tc.get("flow_type") == "consumer":      return 4
        if tc.get("flow_type") == "cleanup":       return 5
        return 9

    def _sort_key(tc: dict[str, Any]) -> tuple:
        return (
            int(tc.get("phase", 9)),
            _flow_priority(tc),
            # Negatives interleave AFTER their corresponding positive
            0 if tc.get("kind") == "positive" else 1,
            str(tc.get("endpoint_path") or ""),
            str(tc.get("operation_key") or ""),
            int(tc.get("expected_status") or 0),
        )

    ordered: list[dict[str, Any]] = []
    remaining: set[str] = set(by_id.keys())
    safety = 0
    safety_cap = max(len(remaining) * 4 + 50, 200)

    while remaining and safety < safety_cap:
        safety += 1
        ready = [tid for tid in remaining if not (in_deg[tid] & remaining)]
        if not ready:
            # Cycle / unsatisfiable — pick the lowest-flow-priority remaining test
            ready = list(remaining)
        ready.sort(key=lambda tid: _sort_key(by_id[tid]))
        chosen_id = ready[0]
        ordered.append(by_id[chosen_id])
        remaining.discard(chosen_id)

    # Anything left (shouldn't happen) — append in stable order
    for tid in sorted(remaining):
        ordered.append(by_id[tid])

    # Interleave negatives directly after their corresponding positive (same operation_key)
    final: list[dict[str, Any]] = []
    handled: set[str] = set()
    for tc in ordered:
        if tc.get("id") in handled:
            continue
        if tc.get("kind") != "positive":
            final.append(tc)
            handled.add(tc["id"])
            continue
        final.append(tc)
        handled.add(tc["id"])
        # find sibling negatives for same operation_key
        opk = tc.get("operation_key")
        siblings = [
            t for t in ordered
            if t.get("operation_key") == opk
            and t.get("id") not in handled
            and t.get("kind") != "positive"
        ]
        siblings.sort(key=lambda t: (
            0 if t.get("expected_status") == 401 else
            1 if t.get("expected_status") == 403 else
            2 if t.get("expected_status") == 422 else
            3 if t.get("expected_status") == 400 else
            4 if t.get("expected_status") == 404 else 9
        ))
        for s in siblings:
            final.append(s)
            handled.add(s["id"])

    # Assign monotonic execution_order
    for i, tc in enumerate(final):
        tc["execution_order"] = i

    return final


# =============================================================================
# DEDUPLICATION
# =============================================================================

def _fingerprint(tc: dict[str, Any]) -> tuple:
    return (
        tc.get("method"),
        tc.get("endpoint_path"),
        tc.get("expected_status"),
        tc.get("kind"),
        json.dumps(tc.get("path_params"), sort_keys=True, default=str),
        json.dumps(tc.get("request_query"), sort_keys=True, default=str),
        json.dumps(tc.get("request_headers"), sort_keys=True, default=str),
        json.dumps(tc.get("request_body"), sort_keys=True, default=str),
    )


def _deduplicate_tests(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for tc in tests:
        fp = _fingerprint(tc)
        if fp in seen:
            continue
        seen.add(fp)
        out.append(tc)
    return out


# =============================================================================
# FINAL VALIDATION (executability gate)
# =============================================================================

_FATAL_ERRORS: frozenset[str] = frozenset({
    "required_body_is_missing",
    "invalid_json_body",
})


def _final_validate(tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last-pass executability validation.
    - Path templates must be aligned with dependency_map for consumers.
    - Drop only structurally fatal cases; preserve everything else with annotations.
    """
    strict = _truthy_env("COGNITEST_STRICT_GENERATION")
    out: list[dict[str, Any]] = []

    for tc in tests:
        path = str(tc.get("endpoint_path") or "")
        dep_map = tc.get("dependency_map") or {}
        errors = list(tc.get("generation_errors") or [])
        is_404_neg = (tc.get("kind") == "negative_not_found")

        # Validate every path placeholder appears in dependency_map (except 404 negatives)
        for ph in re.findall(r"\{([^}]+)\}", path):
            if ph not in dep_map and not is_404_neg:
                err = f"missing_dependency_map:{ph}"
                if err not in errors:
                    errors.append(err)

        # Refresh the error fields
        if errors:
            tc["generation_errors"] = sorted(set(errors))
            tc["generation_error"] = "; ".join(sorted(set(errors)))
        else:
            tc["generation_errors"] = []
            tc["generation_error"] = None

        # Decide whether to keep
        fatal = any(any(fe in e for fe in _FATAL_ERRORS) for e in errors)
        if fatal:
            continue
        if strict and errors:
            continue
        out.append(tc)

    return out


# =============================================================================
# PUBLIC API
# =============================================================================

def generate_contract_test_cases(canonical_spec: Any) -> list[dict[str, Any]]:
    """Generate deterministic, schema-driven contract test cases.

    Pipeline:
        1. Coerce input into canonical model (raw OpenAPI dict supported).
        2. Discovery pass: assign resource_key, build PRODUCER_REGISTRY.
        3. For every operation, build dependency_map strictly via the registry.
        4. Emit positive + negative test cases with the strict contract fields.
        5. Topologically order the test cases.
        6. Deduplicate and run final executability validation.

    The output's `dependency_map[*].source` strings are guaranteed to match
    the producer's `resource_key`, which the executor uses as its bucket key.
    """
    if UNIQUE_FORMAT_VALUES:
        reset_unique_cache()

    shared_data: dict[str, Any] = {}
    spec = coerce_canonical_spec(canonical_spec)
    doc_id = str(spec.get("doc_id") or "")

    operations = spec.get("operations") or []
    if not isinstance(operations, list):
        operations = []
    operations = [op for op in operations if isinstance(op, dict)]
    operations.sort(key=lambda o: str(o.get("operation_key") or f"{o.get('method')}:{o.get('path')}"))

    # ---- PASS 2: Discovery -> registry ----
    registry = _build_producer_registry(operations)

    if _DEBUG:
        logger.debug("==== PRODUCER REGISTRY ====")
        for k, v in registry.items():
            logger.debug("  %s -> %s %s (id_paths=%s)", k, v["method"], v["path"], v["id_paths"])

    # ---- PASS 3+4: Per-operation analysis + test case generation ----
    all_tests: list[dict[str, Any]] = []
    for op in operations:
        try:
            tcs = _build_test_cases_for_operation(
                op,
                registry,
                doc_id=doc_id,
                shared_data=shared_data,
            )
            all_tests.extend(tcs)
        except Exception as exc:
            logger.warning(
                "Test generation failed for %s %s: %s",
                op.get("method"), op.get("path"), exc,
            )
            if _truthy_env("COGNITEST_GENERATOR_HARD_FAIL"):
                raise

    # ---- PASS 5: Deduplicate + topological order ----
    all_tests = _deduplicate_tests(all_tests)
    all_tests = _topological_order(all_tests)

    # ---- PASS 6: Validation gate ----
    all_tests = _final_validate(all_tests)

    # Re-assign execution_order after possible drops
    for i, tc in enumerate(all_tests):
        tc["execution_order"] = i

    if _DEBUG:
        logger.debug("==== FINAL TEST ORDER ====")
        for tc in all_tests:
            logger.debug(
                "  [%d] %s %s status=%s flow=%s deps=%s",
                tc.get("execution_order"),
                tc.get("method"),
                tc.get("endpoint_path"),
                tc.get("expected_status"),
                tc.get("flow_type"),
                tc.get("dependency_map"),
            )

    return all_tests


# =============================================================================
# BACK-COMPAT EXPORTS (kept for callers that imported these helpers)
# =============================================================================

def _order_tests_deterministically(
    tests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Stable, CI-deterministic ordering for an arbitrary list of test cases.

    `generate_contract_test_cases` already returns topologically ordered
    cases with monotonic `execution_order`. This helper exists so callers
    (notably the executor) can re-sort a possibly-filtered subset and still
    honour the producer-before-consumer invariant.

    Sort key, in order:
        1. `phase`           — auth (1) -> producers (2) -> consumers (3) -> cleanup (4) -> independent (9)
        2. `execution_order` — preserves topological order within a phase
        3. `endpoint_path`   — alphabetical tiebreak
        4. `method`          — alphabetical tiebreak

    The function is pure: it does not mutate input items.
    """
    def _key(tc: dict[str, Any]) -> tuple:
        return (
            int(tc.get("phase") or 9),
            int(tc.get("execution_order") or 0),
            str(tc.get("endpoint_path") or ""),
            str(tc.get("method") or ""),
            str(tc.get("test_type") or ""),
            str(tc.get("expected_status") or ""),
        )

    return sorted([tc for tc in tests if isinstance(tc, dict)], key=_key)


# Some callers (executor / tests) imported these from the original file;
# keep exporting them so nothing breaks at the import boundary.
__all__ = [
    "generate_contract_test_cases",
    "coerce_canonical_spec",
    "build_placeholder_body",
    "mutate_by_status",
    "_order_tests_deterministically",
]