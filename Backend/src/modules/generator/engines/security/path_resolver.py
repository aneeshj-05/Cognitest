"""
Path parameter resolver for security execution.

Security checks need path substitution to preserve meaning. A user id, org id,
and post id in the same URL must not all collapse to one generic resource id.
"""
from __future__ import annotations

import re
from typing import Any

_PARAM_RE = re.compile(r"\{(\w+)\}")
_SAFE_PLACEHOLDER = "stateless-probe-id"


def singular_resource_key(value: str) -> str:
    v = value.strip().lower().replace("_", "-")
    if v.endswith("ies") and len(v) > 3:
        return f"{v[:-3]}y"
    if v.endswith("s") and len(v) > 1:
        return v[:-1]
    return v


def _context_get(context: Any, key: str, default: Any = None) -> Any:
    if isinstance(context, dict):
        return context.get(key, default)
    return getattr(context, key, default)


def _resource_ids(context: Any) -> dict[str, Any]:
    ids = _context_get(context, "resource_ids", {}) or {}
    return ids if isinstance(ids, dict) else {}


def _resolve_context_ref(ref: Any, context: Any) -> str | None:
    if ref is None:
        return None
    if not isinstance(ref, str):
        return str(ref)

    value = ref.strip()
    if not value:
        return None

    if value.startswith("resource:"):
        resource_key = value.split(":", 1)[1]
        return _lookup_resource_id(resource_key, context)

    direct = _context_get(context, value)
    if direct:
        return str(direct)

    resource = _lookup_resource_id(value, context)
    if resource:
        return resource

    return value


def _lookup_resource_id(resource_key: str, context: Any) -> str | None:
    ids = _resource_ids(context)
    if not ids:
        fallback = _context_get(context, "resource_id")
        return str(fallback) if fallback else None

    # Detect nested structure from TestContext (Explicit Ownership)
    # If BOLA context provides a specific user's slice, use that.
    # If not, and we see "user_a"/"user_b" keys, we are in the main context.
    
    # Priority 1: If we have a direct hit in the current 'ids' level
    candidates = _candidate_resource_keys(resource_key)
    for candidate in candidates:
        if ids.get(candidate) and isinstance(ids[candidate], (str, int)):
            return str(ids[candidate])

    # Priority 2: Dive into user buckets if they exist
    # For BOLA, we typically want the 'victim' (which we map to user_b in our generator)
    for bucket in ("user_b", "user_a"):
        if bucket in ids and isinstance(ids[bucket], dict):
            bucket_ids = ids[bucket]
            for candidate in candidates:
                if bucket_ids.get(candidate):
                    return str(bucket_ids[candidate])

    # Priority 3: Fuzzy match in the current level or buckets
    def fuzzy_find(d: dict, target: str) -> str | None:
        target_norm = singular_resource_key(target)
        for k, v in d.items():
            if not v or not isinstance(v, (str, int)): continue
            normalized = singular_resource_key(str(k))
            if normalized == target_norm or normalized in target_norm or target_norm in normalized:
                return str(v)
        return None

    res = fuzzy_find(ids, resource_key)
    if res: return res

    for bucket in ("user_b", "user_a"):
        if bucket in ids and isinstance(ids[bucket], dict):
            res = fuzzy_find(ids[bucket], resource_key)
            if res: return res

    fallback = _context_get(context, "resource_id")
    return str(fallback) if fallback else None


def _candidate_resource_keys(value: str) -> list[str]:
    raw = value.strip("{}").strip().replace("_", "-")
    lower = raw.lower()
    singular = singular_resource_key(lower)
    candidates = [raw, lower, singular, singular.replace("-", "_")]
    if not lower.endswith("s"):
        candidates.extend([f"{lower}s", f"{singular}s"])
    return list(dict.fromkeys(candidates))


def _segment_before_param(path: str, param_name: str) -> str:
    parts = [p for p in path.strip("/").split("/") if p]
    needle = "{" + param_name + "}"
    for idx, part in enumerate(parts):
        if part == needle and idx > 0:
            return parts[idx - 1]
    return ""


def _semantic_param_value(param_name: str, context: Any) -> str | None:
    lower = param_name.lower()

    if lower in {"userid", "user_id", "ownerid", "owner_id", "accountid", "account_id"}:
        for key in ("owner_user_id", "user_id_a", "user_id", "user_id_b"):
            value = _context_get(context, key)
            if value:
                return str(value)

    if lower in {"attackerid", "attacker_id"}:
        for key in ("attacker_user_id", "user_id_b"):
            value = _context_get(context, key)
            if value:
                return str(value)

    if lower in {"id", "resourceid", "resource_id"}:
        value = _context_get(context, "resource_id")
        if value:
            return str(value)

    if lower.endswith("id"):
        stem = lower[:-2]
        resource = _lookup_resource_id(stem, context)
        if resource:
            return resource

    return None


def resolve_security_path(path: str, case: dict[str, Any] | None = None, context: Any = None) -> str:
    """
    Resolve OpenAPI path params using explicit data and typed context.

    Priority:
      1. case["path_params"]
      2. case["path_param_bindings"] / metadata["path_param_bindings"]
      3. semantic param names, e.g. userId, ownerId, postId
      4. neighboring path segment, e.g. /posts/{postId}
      5. safe placeholder
    """
    case = case or {}
    context = context or {}
    path_params = case.get("path_params") if isinstance(case.get("path_params"), dict) else {}
    metadata = case.get("metadata") if isinstance(case.get("metadata"), dict) else {}
    bindings = case.get("path_param_bindings") or metadata.get("path_param_bindings") or {}
    bindings = bindings if isinstance(bindings, dict) else {}

    def substitute(match: re.Match) -> str:
        param = match.group(1)

        if param in path_params and path_params[param] is not None:
            return str(path_params[param])

        if param in bindings:
            bound = _resolve_context_ref(bindings[param], context)
            if bound:
                return bound

        semantic = _semantic_param_value(param, context)
        if semantic:
            return semantic

        segment = _segment_before_param(path, param)
        if segment:
            by_segment = _lookup_resource_id(segment, context)
            if by_segment:
                return by_segment

        # Priority 5: Speculative Fallback (Better than generic placeholder)
        # If we have no ID but it's a common resource param, try common defaults
        if param.lower() in {"id", "itemid", "item_id", "productid", "product_id"}:
            return "1" 
        if param.lower() in {"orderid", "order_id"}:
             return "101"
             
        return _SAFE_PLACEHOLDER

    return _PARAM_RE.sub(substitute, path or "/")
