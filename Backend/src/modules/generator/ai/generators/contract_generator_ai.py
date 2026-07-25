"""
AI-powered contract test generator — per-operation, token-efficient, schema-driven.

Bug fixes in this version (relative to previous)
=================================================

BUG 1 — Producer registry miss for MongoDB-style IDs
    The rule-based ``_is_id_like_name`` matched "id", "_id", "userId", etc.
    but the swagger uses "_id" as the MongoDB primary key with format "ObjectId".
    The registry was not registering ``POST /admin/add-item`` as a producer
    because ``_producer_id_paths_from_responses`` requires the id-like field to
    exist in the 2xx response schema AND the method to be POST/PUT/PATCH.
    Root cause: ``coerce_canonical_spec`` only runs ``_resolve_openapi_schema``
    on the schema objects — but the canonical response's ``json_schema`` was the
    resolved Item schema. The ``_id`` field IS present. The real miss was that
    ``_analyze_operation_dependencies`` for ``/add-to-cart/{id}`` was looking for
    a producer of resource key "add_to_cart" (derived from path) instead of
    "item" (derived from the Item schema $ref). The path-derived resource key
    was overriding the schema-derived one because ``_classify_flow`` had not been
    called before ``_build_ai_endpoint_descriptor`` — so ``op["resource_key"]``
    was None.
    FIX: Run ``_build_producer_registry`` AFTER ``_classify_flow`` has been called
    on every operation and after ``op["resource_key"]`` has been set via
    ``_derive_resource_key``.  We now call ``_derive_resource_key`` explicitly in
    the per-op loop before the registry build.

BUG 2 — path_params not nulled for consumers/cleanup
    The normaliser contained this line:
        for ph in re.findall(r"\{([^}]+)\}", structural["has_placeholders"] and structural.get("_path", "") or ""):
    ``structural["has_placeholders"]`` is a boolean.  ``True and structural.get("_path","")``
    returns the path string (correct), but ``False and ...`` short-circuits to
    False, and ``False or ""`` returns ``""`` — so ``re.findall`` on an empty
    string found no placeholders. Result: path_params was always ``{}``.
    FIX: Store the actual path string in ``_structural["path"]`` and use it
    directly in re.findall.  Also: always null path param values for ALL
    non-404 statuses (not just positives), because the executor must inject
    real IDs even for 401/403/422 consumers so the request reaches the right
    endpoint.

BUG 3a — 403 mutation_meta not set
    The executor reads ``tc["mutation_meta"]["auth_kept"] = True`` to know it
    should swap the auth token to a foreign user's token (403 Forbidden).
    The normaliser was setting ``auth_negative=True`` but not populating
    ``mutation_meta``.
    FIX: Set ``mutation_meta = {"auth_kept": True, "auth_negative": True}``
    when status == 403.

BUG 3b — 404 path_params not populated with nonexistent ID
    For 404 tests the executor expects path_params to contain a non-null value
    (a synthetic non-existent ID) so it can substitute it into the path.  The
    normaliser was setting all path_params to null for every non-2xx status.
    FIX: For status == 404, read path_params values from the AI item (which is
    instructed to provide nonexistent IDs) and fall back to a safe sentinel if
    the AI did not provide them.

BUG 3c — no-body 401 semantic_conflict
    POST /login declares 401 with no response body.  When the AI sends a
    request body for the 401 test the executor classifies it as a
    ``semantic_conflict`` (body sent to an endpoint the spec says returns nothing
    for this status) and SKIPs it.  The body for 401 should be the same valid
    body as the 2xx test, but the executor's semantic check is about the
    RESPONSE body, not the request body.  The real issue: the 401 auth-negative
    test for /login was getting a request body — but the executor's
    ``negative_auth_missing`` kind strips the header, not the body, so the
    body is fine.  The SKIP was because ``kind`` was set to
    ``"negative_auth"`` but the executor expected ``"negative_auth_missing"``
    for 401 when no auth-injection hint was present.
    FIX: Set ``kind = "negative_auth_missing"`` for status == 401 and
    ``kind = "negative_forbidden"`` for status == 403.

BUG 3d — 422 all-fields invalidated (timeout on test 8)
    When the AI mutated multiple fields simultaneously the server received
    a completely malformed body and hung (20s timeout).  The prompt fix
    (EXACTLY ONE field) addresses the root cause.  The normaliser now also
    sets ``mutation_meta = {"body_logically_invalid": True}`` for 400 and
    ``mutation_meta = {"body_invalidated": True}`` for 422 so the executor
    can classify failures correctly.

Architecture (evolved: AI-primary orchestration with rule-based validation)
==========================================================================
    PASS 1  Canonicalise via coerce_canonical_spec.
    PASS 2  Rule-based structural analysis: derive resource_key FIRST,
            then build producer registry, then classify flow, then analyse
            dependencies.  Order matters.  Results stored as RULE BASELINE.
    PASS 3  Build per-operation descriptors.  LIFECYCLE CONTEXT (rule-inferred
            flow_type, phase, depends_on candidates) is now sent to AI so it
            can validate, enrich, or semantically override orchestration.
    PASS 4  Parallel per-operation Claude calls.
    PASS 5  Normalise + merge AI output:
              - AI-proposed suggested_lifecycle_role / suggested_depends_on
                are validated via _validate_ai_orchestration().
              - If valid → AI proposal wins (AI-native orchestration).
              - If invalid → rule-based baseline is restored (safety fallback).
    PASS 6  Sort + stamp execution_order.
    PASS 7  Topological sort + dedup + final validation gate.
    PASS 8  DB persistence (fresh suite, overwrites previous).

Contract with executor (unchanged)
====================================
    tc["resource_key"]    bucket key for entity storage
    tc["dependency_map"]  {param: {source, field, confidence}}
    tc["depends_on"]      [operation_key, ...]
    tc["execution_order"] monotonic integer
    tc["mutation_meta"]   signals for executor mutation strategy

NO HARDCODED RESOURCE NAMES. All resource identity from the schema.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rule-based engine imports
# ---------------------------------------------------------------------------
from ...engines.contract.contract_generator import (
    _analyze_operation_dependencies,
    _build_producer_registry,
    _classify_flow,
    _deduplicate_tests,
    _derive_resource_key,
    _final_validate,
    _normalize_resource_name,
    _topological_order,
    build_placeholder_body,
    coerce_canonical_spec,
)
from ...engines.contract.contract_rules import UNIQUE_FORMAT_VALUES, reset_unique_cache

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
from ..prompts.contract import build_operation_prompt, build_contract_prompt

# ---------------------------------------------------------------------------
# AI client
# ---------------------------------------------------------------------------
from src.modules.generator.ai.client import ai_client
from src.modules.generator.ai.utils import prune_schema_for_ai

# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------
try:
    from ...engines.contract.contract_executor import persist_contract_suite_and_cases
    _PERSIST_AVAILABLE = True
except Exception:
    persist_contract_suite_and_cases = None  # type: ignore
    _PERSIST_AVAILABLE = False


# =============================================================================
# CONFIGURATION
# =============================================================================

_AI_CONCURRENCY:     int   = 3      # parallel Claude calls
_AI_RETRIES:         int   = 1      # retries per operation on empty/invalid response
_AI_MAX_TOKENS_PER_OP: int = 1800   # +300 tokens for AI orchestration fields
_AI_TEMPERATURE:     float = 0.0    # maximum determinism

# Status codes we generate test cases for (mirrors contract_generator filter).
_HANDLED_STATUSES: frozenset[int] = frozenset({200, 201, 400, 401, 403, 404, 422})

# Phase → sort priority (must match contract_generator._classify_flow).
_FLOW_TO_PHASE: dict[str, int] = {
    "auth":           1,   # signup overridden to phase 0 in _sort_key
    "producer":       2,
    "state_provider": 2,   # AI semantic role — same phase as producer
    "independent":    3,
    "consumer":       4,
    "state_consumer": 4,   # AI semantic role — same phase as consumer
    "cleanup":        5,
}

# Valid flow_type values AI is allowed to propose.
_VALID_FLOW_TYPES: frozenset[str] = frozenset(
    {"auth", "producer", "consumer", "independent", "cleanup",
     # AI-native semantic roles — mapped to structural phases during normalisation
     "state_provider", "state_consumer"}
)

# Map AI semantic roles to structural flow_type (producer/consumer) for executor compat
_AI_ROLE_TO_FLOW: dict[str, str] = {
    "state_provider": "producer",
    "state_consumer":  "consumer",
}

# Secondary sort within a phase.
_STATUS_SORT: dict[int, int] = {200: 0, 201: 0, 401: 1, 403: 2, 422: 3, 400: 4, 404: 5}

# Fallback nonexistent-ID values for 404 tests, keyed by param format.
_NONEXISTENT_ID: dict[str, str] = {
    "ObjectId":  "000000000000000000000000",
    "objectid":  "000000000000000000000000",
    "uuid":      "00000000-0000-0000-0000-000000000000",
    "UUID":      "00000000-0000-0000-0000-000000000000",
    "integer":   "0",
    "int":       "0",
    "string":    "nonexistent",
    "default":   "000000000000000000000000",
}


# =============================================================================
# SCHEMA PRUNING
# =============================================================================

def _safe_prune(schema: Any, depth: int = 5) -> Any:
    if schema is None:
        return None
    try:
        pruned = prune_schema_for_ai(schema)
        return pruned if pruned else None
    except Exception:
        return _depth_prune(schema, depth)


def _depth_prune(obj: Any, depth: int) -> Any:
    if depth <= 0:
        return "…" if isinstance(obj, dict) else obj
    if isinstance(obj, dict):
        return {k: _depth_prune(v, depth - 1) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_depth_prune(v, depth - 1) for v in obj[:8]]
    return obj


# =============================================================================
# AI ORCHESTRATION VALIDATION LAYER
# =============================================================================

def _validate_ai_orchestration(
    ai_flow_type: Any,
    ai_depends_on: Any,
    structural: dict[str, Any],
    all_operation_keys: frozenset[str],
) -> dict[str, Any]:
    """Validate AI-proposed orchestration fields and return safe values.

    The AI proposes ``suggested_lifecycle_role`` and ``suggested_depends_on``.
    This function is the SAFETY LAYER only — it corrects structurally impossible
    graphs (cycles, hallucinated keys, auth mis-classifications) but preserves
    all semantically valid AI proposals, including state_provider/state_consumer
    roles for GET endpoints and schema-inferred dependency chains.

    AI semantic roles ``state_provider`` and ``state_consumer`` are mapped to
    the structural ``producer``/``consumer`` roles for executor compatibility,
    but this mapping is transparent — the original AI role is preserved in the
    ``ai_role`` field of the returned dict.

    Fallback to rule baseline ONLY when the AI proposal is structurally
    impossible (hallucinated operation_keys, invalid role string, auth override).
    Empty dependency lists from the AI are respected as semantic statements.

    Returns a dict with keys ``flow_type``, ``phase``, ``depends_on``,
    ``orchestration_source``, and ``ai_role``.
    """
    rule_flow   = str(structural.get("flow_type") or "independent")
    rule_phase  = int(structural.get("phase") or _FLOW_TO_PHASE.get(rule_flow, 3))
    rule_deps   = list(structural.get("depends_on") or [])

    # ── Normalise and validate AI flow_type ──────────────────────────────
    raw_flow = str(ai_flow_type).strip().lower() if isinstance(ai_flow_type, str) else ""
    if raw_flow not in _VALID_FLOW_TYPES:
        # Unrecognised role → safety fallback (do not reject valid AI dep chains)
        logger.debug("[AI-ORCH] Unknown flow type %r — rule fallback for role only", raw_flow)
        return {
            "flow_type":            rule_flow,
            "phase":                rule_phase,
            "depends_on":           rule_deps,
            "orchestration_source": "rule",
            "ai_role":              raw_flow,
        }

    # Map AI semantic roles to structural executor-compatible roles
    proposed_flow = _AI_ROLE_TO_FLOW.get(raw_flow, raw_flow)

    # ── Safety guard: auth endpoint identity is structurally determined ──
    # Auth endpoints issue tokens — they cannot be reclassified by the AI.
    if structural.get("is_auth_endpoint") and proposed_flow != "auth":
        logger.debug(
            "[AI-ORCH] Auth endpoint cannot be reclassified as %r — keeping auth",
            proposed_flow,
        )
        proposed_flow = "auth"
        raw_flow = "auth"

    # ── Validate and normalise AI depends_on ─────────────────────────────
    # Build a case-normalised lookup: lowercase(op_key) → canonical op_key
    # This handles minor case mismatches (e.g. "GET:/items" vs "get:/items")
    op_key_canonical: dict[str, str] = {k.lower(): k for k in all_operation_keys}

    proposed_deps: list[str] = []
    proposed_edges: dict[str, float] = {}
    hallucinated: list[str] = []

    if isinstance(ai_depends_on, list):
        for raw_dep in ai_depends_on:
            conf = 1.0
            if isinstance(raw_dep, str):
                d = raw_dep.strip()
            elif isinstance(raw_dep, dict):
                d = str(raw_dep.get("operation_key", "")).strip()
                try:
                    conf = float(raw_dep.get("confidence", 0.9))
                except (ValueError, TypeError):
                    conf = 0.9
            else:
                continue

            if d in all_operation_keys:
                canonical_d = d
            elif d.lower() in op_key_canonical:
                canonical_d = op_key_canonical[d.lower()]
            else:
                hallucinated.append(d)
                continue

            if canonical_d not in proposed_deps:
                proposed_deps.append(canonical_d)
                proposed_edges[canonical_d] = conf

        if hallucinated:
            logger.warning(
                "[AI-ORCH] Dropped %d hallucinated dep key(s) for %s: %s",
                len(hallucinated),
                structural.get("operation_key", "?"),
                hallucinated,
            )

        if len(ai_depends_on) > 0 and len(proposed_deps) == 0:
            logger.warning(
                "[AI-ORCH] All AI deps were hallucinated for %s — rule fallback for deps only",
                structural.get("operation_key", "?"),
            )
            proposed_deps = rule_deps
            proposed_edges = {d: 1.0 for d in rule_deps}
    else:
        # AI did not return a depends_on field → preserve rule baseline
        proposed_deps = rule_deps
        proposed_edges = {d: 1.0 for d in rule_deps}

    proposed_phase = _FLOW_TO_PHASE.get(proposed_flow, 3)

    # Signup (phase 0) is detected structurally; AI cannot override it
    if rule_phase == 0:
        proposed_phase = 0
        proposed_flow  = "auth"
        raw_flow       = "auth"

    ai_changed_flow = proposed_flow != rule_flow
    ai_changed_deps = set(proposed_deps) != set(rule_deps)
    ai_won = ai_changed_flow or ai_changed_deps
    source = "ai" if ai_won else "rule"

    if ai_won:
        logger.info(
            "[AI-ORCH] AI orchestration accepted: flow=%s→%s deps=%s→%s (role=%s)",
            rule_flow, proposed_flow, rule_deps, proposed_deps, raw_flow,
        )

    return {
        "flow_type":            proposed_flow,
        "phase":                proposed_phase,
        "depends_on":           proposed_deps,
        "dependency_edges":     proposed_edges,
        "orchestration_source": source,
        "ai_role":              raw_flow,
    }

# =============================================================================
# PASS 2: STRUCTURAL ANALYSIS  (run before registry build)
# =============================================================================

def _prepare_operations(
    operations: list[dict[str, Any]],
    doc_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Run the full rule-based structural analysis pipeline in the correct order.

    Order matters:
      1. Derive resource_key for every operation (schema-first).
      2. Build the producer registry (needs resource_key on every op).
      3. Classify flow type + phase (needs registry for auth detection).
      4. Analyse dependencies (needs registry + flow classification).

    Returns (operations_with_metadata, registry).
    """
    # Step 1: derive resource_key for every operation FIRST
    for op in operations:
        rk = _derive_resource_key(op)
        op["resource_key"] = rk
        op["doc_id"] = doc_id

    # Step 2: build producer registry (now that resource_key is set)
    registry = _build_producer_registry(operations)

    # Step 3: classify flow + phase (sets security_required, produced_auth_field, is_signup)
    for op in operations:
        flow_type, phase = _classify_flow(op)
        op["flow_type"] = flow_type
        op["phase"] = phase

    return operations, registry


# =============================================================================
# PASS 3: PER-OPERATION DESCRIPTOR BUILDER
# =============================================================================

def _extract_path_param_names(path: str) -> list[str]:
    """Extract parameter names from a path template like /items/{id}/sub/{subId}."""
    return re.findall(r"\{([^}]+)\}", path)


def _param_format(parameters: list[dict[str, Any]], param_name: str) -> str:
    """Look up the format of a path parameter from the parameters list."""
    for p in parameters:
        if isinstance(p, dict) and p.get("name") == param_name and p.get("location") == "path":
            s = p.get("schema") or {}
            return s.get("format") or s.get("type") or "default"
    return "default"



def _extract_reusable_state_fields(
    response_schemas: dict[str, Any],
) -> list[dict[str, str]]:
    """Extract a field-level inventory of reusable execution-state fields from 2xx
    response schemas.

    Returns a list of ``{"field": <dot-path>, "type": <type>, "format": <format>}``
    dicts for every field whose name or format suggests it carries reusable state
    (IDs, tokens, keys, refs, etc.).  The list is used by the global orchestration
    AI to perform field-level cross-endpoint overlap matching instead of having to
    re-parse full pruned schemas in its context window.

    HTTP-method-agnostic: GET, POST, PUT, PATCH responses are all analysed equally.
    """
    _ID_LIKE_NAMES: frozenset[str] = frozenset({
        "id", "_id", "uuid", "token", "key", "ref", "reference",
        "identifier", "objectid", "sessionid", "accesstoken", "refreshtoken",
    })
    _ID_LIKE_FORMATS: frozenset[str] = frozenset({
        "objectid", "uuid", "uri", "email",
    })

    found: list[dict[str, str]] = []
    seen_paths: set[str] = set()

    def _walk(schema: Any, prefix: str, depth: int) -> None:
        if depth <= 0 or not isinstance(schema, dict):
            return
        # Scalar schema at this level (e.g. array items is a primitive)
        fmt  = str(schema.get("format") or "").lower()
        typ  = str(schema.get("type") or "")
        
        def _infer_field_type(n: str, f: str, t: str) -> str:
            if t == "array": return "collection_state"
            if "token" in n or f in ("jwt", "token"): return "auth_state"
            if f in ("email", "password") or n in ("email", "username", "password"): return "identity_state"
            return "lifecycle_state"
            
        if fmt in _ID_LIKE_FORMATS and prefix and prefix not in seen_paths:
            seen_paths.add(prefix)
            found.append({"field": prefix, "type": typ, "format": fmt, "semantic_state_type": _infer_field_type(prefix.lower(), fmt, typ)})
            return  # no need to descend further for a scalar ID

        # Descend into properties
        for prop_name, prop_schema in (schema.get("properties") or {}).items():
            if not isinstance(prop_schema, dict):
                continue
            fp = f"{prefix}.{prop_name}" if prefix else prop_name
            pname_norm = prop_name.lower().rstrip("s")
            pfmt  = str(prop_schema.get("format") or "").lower()
            ptype = str(prop_schema.get("type") or "")
            
            is_collection = (ptype == "array")
            
            if (pname_norm in _ID_LIKE_NAMES or pfmt in _ID_LIKE_FORMATS or is_collection) and fp not in seen_paths:
                seen_paths.add(fp)
                found.append({"field": fp, "type": ptype, "format": pfmt, "semantic_state_type": _infer_field_type(pname_norm, pfmt, ptype)})
            # Always recurse so we catch nested objects
            _walk(prop_schema, fp, depth - 1)

        # Array items
        items = schema.get("items")
        if isinstance(items, dict):
            item_prefix = f"{prefix}[]" if prefix else "[]"
            arr_field = prefix if prefix else "[]"
            if arr_field not in seen_paths:
                seen_paths.add(arr_field)
                found.append({"field": arr_field, "type": "array", "format": "", "semantic_state_type": "collection_state"})
            _walk(items, item_prefix, depth - 1)

        # Combinators
        for combinator in ("allOf", "anyOf", "oneOf"):
            for i, sub in enumerate(schema.get(combinator) or []):
                _walk(sub, prefix, depth - 1)

    for sc_str, rschema in (response_schemas or {}).items():
        try:
            sc = int(sc_str)
        except (ValueError, TypeError):
            continue
        if sc in (200, 201) and isinstance(rschema, dict):
            _walk(rschema, "", 5)

    return found


def _response_provides_reusable_state(response_schemas: dict[str, Any]) -> bool:
    """Return True when the endpoint's 2xx response schema contains at least one
    field that could serve as reusable execution state for other endpoints.

    Delegates to ``_extract_reusable_state_fields`` so both functions share
    identical detection logic without duplication.
    """
    return bool(_extract_reusable_state_fields(response_schemas))

def _build_ai_endpoint_descriptor(
    op: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    shared_data: dict[str, Any],
) -> dict[str, Any]:
    """Build a single per-operation descriptor.

    Two layers:
      top-level keys — sent to AI in the prompt
      _structural     — rule-based facts stamped by the normaliser (AI never sees)
    """
    method       = str(op.get("method") or "GET").upper()
    path         = str(op.get("path") or "/")
    op_key       = str(op.get("operation_key") or f"{method.lower()}:{path}")
    resource_key = _normalize_resource_name(op.get("resource_key") or "")
    flow_type    = str(op.get("flow_type") or "independent")
    phase        = int(
        op.get("phase") if op.get("phase") is not None
        else _FLOW_TO_PHASE.get(flow_type, 3)
    )

    # Dependency analysis (registry must already be built)
    dep_map, depends_on_keys, dep_errors, confidence = \
        _analyze_operation_dependencies(op, registry)

    # Status codes: only what the swagger declares, filtered to handled set
    responses_raw = op.get("responses") or {}
    if not isinstance(responses_raw, dict):
        responses_raw = {}
    status_codes: list[int] = []
    for sk in sorted(
        responses_raw.keys(), key=lambda x: int(x) if str(x).isdigit() else 9999
    ):
        if str(sk).isdigit():
            si = int(sk)
            if si in _HANDLED_STATUSES:
                status_codes.append(si)
    # Guarantee at least one positive
    if not any(s in (200, 201) for s in status_codes):
        status_codes.insert(0, 201 if method == "POST" else 200)
    # Stable order: positives first
    status_codes = sorted(
        list(dict.fromkeys(status_codes)),
        key=lambda s: (0 if s in (200, 201) else 1, s),
    )

    # Pruned response schemas (positive first, errors only if schema exists)
    response_schemas: dict[str, Any] = {}
    for sk, resp in responses_raw.items():
        if not str(sk).isdigit():
            continue
        si = int(sk)
        if si not in _HANDLED_STATUSES:
            continue
        if isinstance(resp, dict) and isinstance(resp.get("json_schema"), dict):
            response_schemas[str(si)] = _safe_prune(resp["json_schema"])
        else:
            response_schemas[str(si)] = None

    # Request body
    rb = op.get("request_body")
    has_request_body = isinstance(rb, dict) and bool(rb.get("json_schema"))
    request_schema = (
        _safe_prune(rb["json_schema"])
        if has_request_body
        else None
    )

    # Parameters (path + query only)
    parameters = [
        {
            "name":     p.get("name") or "",
            "location": p.get("location") or "",
            "required": bool(p.get("required")),
            "schema":   _safe_prune(p.get("json_schema")) or {},
        }
        for p in (op.get("parameters") or [])
        if isinstance(p, dict) and p.get("location") in ("path", "query")
    ]

    # Path param names and their formats (for 404 fallback ID generation)
    path_param_names = _extract_path_param_names(path)
    path_param_formats = {
        pn: _param_format(parameters, pn)
        for pn in path_param_names
    }

    # Rule-based placeholder body (fallback when AI body is null for 2xx)
    rule_body: Any = None
    if request_schema:
        try:
            rule_body = build_placeholder_body(request_schema, shared_data)
        except Exception:
            rule_body = None

    # Compute provides_reusable_state from response schema (method-agnostic)
    reusable_state_fields = _extract_reusable_state_fields(response_schemas)
    provides_reusable_state = bool(reusable_state_fields)
    
    # Infer semantic state types dynamically from schema structure and OpenAPI lifecycle semantics
    semantic_state_types: list[str] = []
    if op.get("is_auth_endpoint") or op.get("produced_auth_field"):
        semantic_state_types.append("auth_state")
    if method == "DELETE" or (204 in status_codes and not response_schemas.get("204")):
        semantic_state_types.append("cleanup_state")
    if any(f.get("semantic_state_type") == "collection_state" for f in reusable_state_fields):
        semantic_state_types.append("collection_state")
    if method in ("PUT", "PATCH") or (method == "POST" and len(path_param_names) > 0):
        semantic_state_types.append("mutation_state")
        
    req_str = str(request_schema).lower()
    if method == "POST" and ("'format': 'email'" in req_str or "'format': 'password'" in req_str):
        semantic_state_types.append("identity_state")
        
    if (has_request_body or path_param_names) and not provides_reusable_state and "cleanup_state" not in semantic_state_types and "mutation_state" not in semantic_state_types:
        semantic_state_types.append("transactional_state")
        
    if provides_reusable_state and "collection_state" not in semantic_state_types:
        semantic_state_types.append("lifecycle_state")
        
    semantic_state_types = sorted(list(set(semantic_state_types)))

    return {
        # ── Sent to AI ────────────────────────────────────────────────────
        "method":               method,
        "path":                 path,
        "semantic_state_types": semantic_state_types,
        "status_codes":         status_codes,
        "request_schema":       request_schema,
        "response_schemas":     response_schemas,
        "parameters":           parameters,
        "security_required":    bool(op.get("security_required")),
        "has_request_body":     has_request_body,
        "path_param_names":     path_param_names,

        # ── Lifecycle context sent to Stage 2 AI ──────────────────────────
        # Contains the RESOLVED orchestration (post-Stage-1 AI or rule baseline).
        # Does NOT expose raw rule_flow_type / rule_depends_on to avoid biasing
        # the per-operation AI toward CRUD assumptions.
        "lifecycle_context": {
            # These are populated with resolved AI values in the main pipeline
            # after Stage 1 global orchestration runs.  At descriptor-build time
            # they hold the rule baseline; the pipeline overwrites them.
            "flow_type":             flow_type,
            "depends_on":            sorted(depends_on_keys),
            "dependency_map":        {k: dict(v) for k, v in dep_map.items()},
            "is_auth_endpoint":      bool(op.get("produced_auth_field")) or flow_type == "auth",
            "provides_reusable_state": provides_reusable_state,
            "has_path_params":       bool(path_param_names),
            "orchestration_source":  "rule",   # overwritten by Stage 1 AI
        },

        # ── Structural facts (rule-based; safety fallback only) ───────────
        "_structural": {
            "operation_key":          op_key,
            "doc_id":                 op.get("doc_id") or "",
            "method":                 method,
            "path":                   path,
            "path_param_names":       path_param_names,
            "path_param_formats":     path_param_formats,
            "resource_key":           resource_key,
            "resource_prefix":        resource_key,
            "resource":               resource_key,
            "flow_type":              flow_type,
            "phase":                  phase,
            # produces_entity: True for POST/PUT/PATCH that return an id-like field
            # OR any endpoint whose response schema provides reusable state.
            # This broader definition enables GET state-providers to propagate
            # their entity IDs into the executor's entity bucket.
            "produces_entity":        bool(op.get("produces_entity")) or provides_reusable_state,
            "is_producer_endpoint":   bool(op.get("produces_entity")) or provides_reusable_state,
            "produced_id_paths":      list(op.get("produced_id_paths") or []),
            "expects_entity":         bool(op.get("produced_id_paths")),
            "provides_reusable_state": provides_reusable_state,
            "reusable_state_fields":   reusable_state_fields,
            "depends_on":             sorted(depends_on_keys),
            "security_required":      bool(op.get("security_required")),
            "is_auth_endpoint":       bool(op.get("produced_auth_field")) or flow_type == "auth",
            "confidence":             confidence,
            "generation_errors":      list(dep_errors),
            "generation_error":       "; ".join(dep_errors) if dep_errors else None,
            "has_request_body":       has_request_body,
            "rule_body":              rule_body,
            "request_schema":         request_schema,
            "orchestration_source":   "rule",
        },
    }


# =============================================================================
# PASS 4: SINGLE-OPERATION CLAUDE CALL
# =============================================================================

async def _call_ai_for_operation(
    descriptor: dict[str, Any],
    *,
    semaphore: asyncio.Semaphore,
    tenant_id: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """Call Claude for one operation. Returns (raw_ai_items, tokens_used).

    Retried _AI_RETRIES times on non-JSON / empty responses.
    Never raises — returns ([], 0) on unrecoverable failure.
    """
    system_blocks, prompt_blocks = build_operation_prompt(descriptor)
    tokens_total = 0

    for attempt in range(_AI_RETRIES + 1):
        async with semaphore:
            try:
                result = await ai_client.generate_json(
                    prompt=prompt_blocks,
                    system=system_blocks,
                    max_tokens=_AI_MAX_TOKENS_PER_OP,
                    temperature=_AI_TEMPERATURE,
                    tenant_id=tenant_id,
                )
            except Exception as exc:
                logger.warning(
                    "[AI-GEN] %s %s attempt %d error: %s",
                    descriptor["method"], descriptor["path"], attempt + 1, exc,
                )
                continue

        raw  = result.get("data")
        usage = result.get("usage") or {}
        tok  = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        tokens_total += tok

        if isinstance(raw, list) and raw:
            return raw, tokens_total

        logger.warning(
            "[AI-GEN] %s %s attempt %d returned invalid/empty: %r",
            descriptor["method"], descriptor["path"], attempt + 1, raw,
        )

    logger.error("[AI-GEN] %s %s: all attempts failed", descriptor["method"], descriptor["path"])
    return [], tokens_total


# =============================================================================
# PASS 5: NORMALISE ONE AI ITEM → FULL TEST CASE
# =============================================================================

def _build_path_params(
    status: int,
    path_param_names: list[str],
    path_param_formats: dict[str, str],
    dep_map: dict[str, Any],
    ai_path_params: dict[str, Any],
) -> dict[str, Any]:
    """Compute the path_params dict for one test case.

    Rules:
      404            → nonexistent ID values (from AI or format-derived fallback)
      all other 4xx  → null (executor injects real IDs so request reaches the
                        right endpoint and the error is about auth/validation,
                        not "resource not found")
      2xx (positive) → null (executor injects from producer bucket)
    """
    result: dict[str, Any] = {}
    for pn in path_param_names:
        if status == 404:
            # Use AI-provided value if it looks non-null and non-empty
            ai_val = ai_path_params.get(pn)
            if ai_val is not None and str(ai_val).strip():
                result[pn] = str(ai_val)
            else:
                # Fall back to format-derived sentinel
                fmt = path_param_formats.get(pn, "default")
                result[pn] = _NONEXISTENT_ID.get(fmt, _NONEXISTENT_ID["default"])
        else:
            # All other statuses: null so executor injects real ID from dep_map
            result[pn] = None

    # Ensure every dep_map top-level (non-dotted) key is also present as null
    # (handles body-level id-like fields that appear as path params)
    for pn in dep_map:
        if "." not in pn and pn not in result:
            result[pn] = None if status != 404 else result.get(pn)

    return result


def _build_mutation_meta(status: int) -> dict[str, Any]:
    """Return the mutation_meta dict the executor needs to apply its strategy."""
    if status == 401:
        return {"no_auth": True, "auth_negative": True}
    if status == 403:
        return {"auth_kept": True, "auth_negative": True}    # FIX BUG 3a
    if status == 404:
        return {"path_params_invalidated": True, "use_fallback_invalid_id": True}
    if status == 422:
        return {"body_invalidated": True}                    # FIX BUG 3d
    if status == 400:
        return {"body_logically_invalid": True}              # FIX BUG 3d
    return {}


def _normalise_ai_item(
    item: dict[str, Any],
    structural: dict[str, Any],
    *,
    valid_status_codes: set[int],
) -> Optional[dict[str, Any]]:
    """Merge one AI-generated item with its structural skeleton.

    Orchestration fields (flow_type, depends_on, etc.) are taken from the
    structural skeleton, which has already been resolved by STAGE 1 Global AI.

    Returns None if the item is fatally malformed (unknown status code).
    """
    if not isinstance(item, dict):
        return None

    # ── 1. Resolve + validate status code ─────────────────────────────────
    sc_raw = item.get("status_code")
    try:
        status = int(sc_raw)
    except (TypeError, ValueError):
        logger.warning("[AI-GEN] item missing/invalid status_code: %r", sc_raw)
        return None

    if status not in valid_status_codes:
        logger.warning("[AI-GEN] AI returned status %d not in swagger — skipping", status)
        return None

    # ── 2. Classify test properties ────────────────────────────────────────
    is_positive = status in (200, 201)
    is_auth_neg = status in (401, 403)
    # NOTE: is_cleanup is computed later (line 766) after AI orchestration is
    # resolved, because AI may legitimately reclassify DELETE endpoints.

    # Auth endpoints (login/signup) issue tokens — they don't consume them.
    # A 401/403 test on an auth endpoint carries no semantic value: there is
    # no token requirement to strip or swap.  The executor's semantic_conflict
    # guard would skip these anyway; filter here to keep the suite clean.
    if is_auth_neg and structural["is_auth_endpoint"]:
        return None

    kind = (
        "positive"               if is_positive   else
        "negative_auth_missing"  if status == 401 else   # strips auth header
        "negative_forbidden"     if status == 403 else   # swaps to foreign token
        "negative_not_found"     if status == 404 else
        "negative_validation"
    )
    test_type = (
        "positive"       if is_positive  else
        "auth_negative"  if is_auth_neg  else
        "negative"
    )

    # ── 3. Request body ────────────────────────────────────────────────────
    has_request_body = bool(structural.get("has_request_body"))

    if not has_request_body:
        # Endpoint has no requestBody — always null regardless of AI output
        ai_body: Any = None
    else:
        ai_body = item.get("request_body")
        if not isinstance(ai_body, (dict, type(None))):
            ai_body = structural.get("rule_body")
        # For positive tests: fall back to rule-based body if AI returned null
        if is_positive and ai_body is None:
            ai_body = structural.get("rule_body")

    # ── 4. Path params  (FIX BUG 2 + BUG 3b) ─────────────────────────────
    path_param_names   = structural.get("path_param_names") or []
    path_param_formats = structural.get("path_param_formats") or {}
    dep_map            = structural.get("dependency_map") or {}

    ai_path_params_raw = item.get("path_params")
    ai_path_params     = ai_path_params_raw if isinstance(ai_path_params_raw, dict) else {}

    base_path_params = _build_path_params(
        status            = status,
        path_param_names  = path_param_names,
        path_param_formats= path_param_formats,
        dep_map           = dep_map,
        ai_path_params    = ai_path_params,
    )

    # ── 5. Mutation meta  (FIX BUG 3a, 3b, 3d) ───────────────────────────
    mutation_meta = _build_mutation_meta(status)

    # ── 6. Assertions ──────────────────────────────────────────────────────
    ai_assertions = item.get("assertions")
    if not isinstance(ai_assertions, list) or not ai_assertions:
        ai_assertions = [f"Status is {status}", "Response matches schema"]
    status_assert = f"Status is {status}"
    if not any(status_assert in a for a in ai_assertions):
        ai_assertions = [status_assert, *ai_assertions]

    # ── 7. Auth fields ─────────────────────────────────────────────────────
    security_required = structural["security_required"]
    auth_required     = security_required and is_positive
    auth_type         = "bearer" if security_required else None
    auth_field_val    = "token" if security_required else None
    missing_auth      = status == 401

    # ── 8. Orchestration (Already resolved by STAGE 1 Global AI) ───────────
    eff_flow_type  = structural.get("flow_type") or "independent"
    eff_phase      = structural.get("phase") or 3
    eff_depends_on = structural.get("depends_on") or []
    orch_source    = structural.get("orchestration_source") or "rule"

    # ── 9. Stable UUID ─────────────────────────────────────────────────────
    tc_id = str(uuid.uuid4())

    # ── 10. Assemble full test case dict ───────────────────────────────────
    method  = structural["method"]
    path    = structural["path"]
    op_key  = structural["operation_key"]
    dep_errors = list(structural["generation_errors"])

    # is_cleanup uses effective flow_type so AI can reclassify DELETE as cleanup
    is_cleanup = eff_flow_type == "cleanup" and is_positive

    tc: dict[str, Any] = {
        # Identity
        "id":            tc_id,
        "test_id":       f"ct_{tc_id[:8]}",
        "doc_id":        structural.get("doc_id") or "",
        "operation_key": op_key,
        "method":        method,
        "endpoint_path": path,
        "path":          path,

        # Display
        "name":          item.get("name") or f"{method} {path} — ({status})",
        "title":         item.get("name") or f"{method} {path} — ({status})",
        "description":   item.get("description") or "",
        "ai_explanation":item.get("ai_explanation") or "",

        # Classification
        "category":      "CONTRACT",
        "sub_category":  "OPENAPI_CONFORMANCE",
        "test_type":     test_type,
        "kind":          kind,
        "positive":      is_positive,
        "cleanup":       is_cleanup,

        # Structural — resource/entity fields always from rule engine (safe)
        "resource_key":          structural["resource_key"],
        "resource_prefix":       structural["resource_key"],
        "resource":              structural["resource_key"],
        "produces_entity":       (structural["produces_entity"]
                                  or structural.get("provides_reusable_state")
                                  or eff_flow_type in ("producer", "state_provider")) and is_positive,
        "is_producer_endpoint":  (structural["produces_entity"]
                                  or structural.get("provides_reusable_state")
                                  or eff_flow_type in ("producer", "state_provider")) and is_positive,
        "produced_id_paths":     structural["produced_id_paths"],
        "expects_entity":        structural["expects_entity"] and is_positive,
        "dependency_map":        dep_map,
        "confidence":            structural["confidence"],

        # Orchestration — AI-proposed values (validated) or rule baseline
        "flow_type":             eff_flow_type,
        "phase":                 eff_phase,
        "depends_on":            eff_depends_on,
        "orchestration_source":  orch_source,

        # Auth
        "security_required": security_required,
        "auth_required":     auth_required,
        "auth_type":         auth_type,
        "auth_field":        auth_field_val,
        "auth_negative":     is_auth_neg,
        "missing_auth":      missing_auth,
        "is_auth_endpoint":  structural["is_auth_endpoint"],
        "produces_auth":     structural["is_auth_endpoint"] and is_positive,

        # Request payload
        "path_params":     base_path_params,
        "request_query":   item.get("request_query") or {},
        "request_headers": {"Content-Type": "application/json"},
        "request_body":    ai_body,
        "request_type":    "json",

        # Assertions
        "assertions": ai_assertions,

        # Expected response
        "expected_status":   status,
        "expected_statuses": [status],
        "expected_schema":   None,
        "failure_category": (
            "auth"       if status in (401, 403) else
            "validation" if status in (400, 422) else
            "not_found"  if status == 404        else
            "other"
        ),

        # Executor mutation / hint signals
        "mutation_meta": mutation_meta,
        "execution_hints": {
            "requires_auth": security_required,
            "is_stateful":   bool(dep_map),
            "is_producer":   (structural["produces_entity"] or structural.get("provides_reusable_state")) and is_positive,
        },
        "auth_metadata": {
            "requires_auth": (
                False if status == 401 else
                True  if status == 403 else
                security_required
            ),
            "negative_type": (
                None           if is_positive  else
                "auth_missing" if status == 401 else
                "forbidden"    if status == 403 else
                "validation"   if status in (400, 422) else
                "not_found"    if status == 404 else
                "other"
            ),
        },

        # Back-compat
        **({"auth_injection": {"type": "bearer", "source": "auth", "field": "token"}}
           if security_required else {}),
        "metadata":      {},
        "preconditions": [],

        # Pass-through spec identifiers
        "spec_id":     structural.get("doc_id") or "",
        "endpoint_id": None,

        # Errors + source tag
        "generation_errors":  sorted(set(dep_errors)),
        "generation_error":   "; ".join(sorted(set(dep_errors))) if dep_errors else None,
        "has_placeholders":   "{" in path,
        "generation_source":  "AI",
    }

    return tc


# =============================================================================
# PASS 6: EXECUTION ORDER ASSIGNMENT
# =============================================================================

def _assign_execution_order(test_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort by topological dependencies, applying semantic density graph optimization.
    
    This acts as a Semantic Lifecycle Execution Planner by performing a weighted
    DFS topological sort. Downstream lifecycle continuity is maximized by computing
    a confidence-weighted depth score. Nodes unlocked by high-confidence edges
    receive stronger continuity prioritization than those unlocked by weak edges.
    """
    from collections import defaultdict

    def _phase_priority(tc: dict[str, Any]) -> int:
        ft    = str(tc.get("flow_type") or "")
        phase = int(tc.get("phase") or _FLOW_TO_PHASE.get(ft, 3))
        if ft == "auth" and phase == 0:
            return 0
        if ft == "auth":
            return 1
        return phase

    def _macro_phase(phase: int) -> int:
        if phase <= 1: return 0  # Auth setup
        if phase <= 4: return 1  # Standard operations (producers, consumers, independent)
        return 2                 # Cleanup / teardown

    def _tie_breaker(tc: dict[str, Any], soft_in: int, d: float) -> tuple:
        p = _phase_priority(tc)
        return (
            _macro_phase(p),
            soft_in,
            -d,                                                    # <--- Maximize confidence-weighted depth
            str(tc.get("resource_key") or tc.get("resource") or ""),
            p,
            _STATUS_SORT.get(int(tc.get("expected_status") or 0), 9),
            str(tc.get("endpoint_path") or ""),
            str(tc.get("method") or ""),
            int(tc.get("expected_status") or 0),
        )

    n = len(test_cases)
    in_degree = {i: 0 for i in range(n)}
    soft_in_degree = {i: 0 for i in range(n)}
    depth = {i: 0.0 for i in range(n)}  # Semantic continuity density
    
    adj = defaultdict(list)
    soft_adj = defaultdict(list)
    
    op_keys_all = defaultdict(list)
    for i, tc in enumerate(test_cases):
        op_keys_all[tc.get("operation_key")].append(i)
        
    for i, tc in enumerate(test_cases):
        deps = tc.get("depends_on") or []
        edges = tc.get("dependency_edges") or {}
        for dep_key in deps:
            conf = edges.get(dep_key, 1.0)
            for j in op_keys_all.get(dep_key, []):
                if i != j:
                    if conf >= 0.7:
                        adj[j].append((i, conf))
                        in_degree[i] += 1
                    else:
                        soft_adj[j].append((i, conf))
                        soft_in_degree[i] += 1
                    
    ready_set = set()
    for i in range(n):
        if in_degree[i] == 0:
            ready_set.add(i)
            
    ordered = []
    while ready_set:
        best_i = None
        best_tb = None
        for i in ready_set:
            tb = _tie_breaker(test_cases[i], soft_in_degree[i], depth[i])
            if best_tb is None or tb < best_tb:
                best_tb = tb
                best_i = i
                
        ready_set.remove(best_i)
        ordered.append(test_cases[best_i])
        
        current_depth = depth[best_i]
        
        for j, conf in adj[best_i]:
            # Propagate graph density heavily weighting strong semantic corridors
            depth[j] = round(max(depth[j], current_depth + conf), 3)
            in_degree[j] -= 1
            if in_degree[j] == 0:
                ready_set.add(j)
                
        for j, conf in soft_adj[best_i]:
            depth[j] = round(max(depth[j], current_depth + conf), 3)
            soft_in_degree[j] -= 1
                
    if len(ordered) < n:
        remaining = [i for i in range(n) if in_degree[i] > 0]
        remaining.sort(key=lambda i: _tie_breaker(test_cases[i], soft_in_degree[i], depth[i]))
        for i in remaining:
            ordered.append(test_cases[i])
            
    for i, tc in enumerate(ordered):
        tc["execution_order"] = i
    return ordered


# =============================================================================
# STAGE 1: GLOBAL ORCHESTRATION CALL
# =============================================================================

def _propagate_transitive_deps(descriptors: list[dict[str, Any]]) -> None:
    """Propagate multi-hop dependency edges in-place on _structural.

    If A depends_on B, and B depends_on C (and so on), then A's resolved
    depends_on should contain ALL ancestors, not just direct parents.  This
    ensures that ``_topological_order`` can correctly sequence the full chain
    even when the AI only expressed direct-parent edges.

    This is a pure graph-closure operation: no domain knowledge, no heuristics.
    It operates solely on the ``depends_on`` lists already present in each
    descriptor's ``_structural`` block.

    The transitive closure is computed via iterative BFS from each node.
    Cycles are silently broken (they should not exist after
    ``_validate_ai_orchestration`` guards, but if they do, we skip the cycle).
    """
    # Build op_key → descriptor index for fast lookup
    op_key_to_idx: dict[str, int] = {}
    for i, d in enumerate(descriptors):
        ok = d["_structural"].get("operation_key", "")
        if ok:
            op_key_to_idx[ok] = i

    def _closure(start_key: str, direct_deps: list[str]) -> tuple[list[str], dict[str, float]]:
        """BFS transitive closure from start_key via its dependency edges."""
        visited: set[str] = set()
        edges_conf: dict[str, float] = {}
        
        start_edges = descriptors[op_key_to_idx[start_key]]["_structural"].get("dependency_edges", {})
        queue = [(d, start_edges.get(d, 1.0)) for d in direct_deps]

        while queue:
            dep_key, current_conf = queue.pop(0)
            if dep_key in visited or dep_key == start_key:
                if dep_key in edges_conf and current_conf > edges_conf[dep_key]:
                    edges_conf[dep_key] = current_conf
                continue
            
            visited.add(dep_key)
            edges_conf[dep_key] = current_conf
            
            idx = op_key_to_idx.get(dep_key)
            if idx is not None:
                dep_struct = descriptors[idx]["_structural"]
                for transitive in (dep_struct.get("depends_on") or []):
                    if transitive != start_key:
                        trans_conf = dep_struct.get("dependency_edges", {}).get(transitive, 1.0)
                        queue.append((transitive, min(current_conf, trans_conf)))
                        
        return sorted(visited), edges_conf

    for d in descriptors:
        struct = d["_structural"]
        op_key = struct.get("operation_key", "")
        direct = list(struct.get("depends_on") or [])
        if not direct:
            continue
        
        full_closure, full_edges = _closure(op_key, direct)
        
        if set(full_closure) != set(direct) or struct.get("dependency_edges") != full_edges:
            logger.debug(
                "[AI-ORCH] Transitive closure updated deps/edges for %s",
                op_key,
            )
            struct["depends_on"] = full_closure
            struct["dependency_edges"] = full_edges
            lc = d.get("lifecycle_context")
            if isinstance(lc, dict):
                lc["depends_on"] = full_closure



def _apply_ai_global_plan(
    descriptors: list[dict[str, Any]],
    global_plan: dict[str, Any],
    all_op_keys: frozenset[str],
    all_resource_keys: frozenset[str],
) -> None:
    """Apply Stage 1 AI orchestration plan to descriptors in-place.

    This is the single authoritative point where AI-proposed orchestration
    is merged into the descriptor._structural and lifecycle_context dicts.

    dep_map validation: the AI is now instructed to use operation_key as
    the source value (not resource_key), so we validate against the union
    of all_op_keys and all_resource_keys.  This prevents the silent drop
    that occurred when the AI correctly identified a GET endpoint as a
    state-provider but the resource_key validator rejected it.

    Source translation: if the AI provides an operation_key as the dep_map
    source, we translate it to the corresponding resource_key so the executor
    can resolve it against its entity bucket (the executor uses resource_key,
    not operation_key, as the entity store key).
    """
    # Build case-normalised lookup for dep_map source validation
    valid_sources: frozenset[str] = all_op_keys | all_resource_keys
    src_lower_to_canonical: dict[str, str] = {s.lower(): s for s in valid_sources}

    # Build operation_key → resource_key translation map for dep_map source normalisation
    op_key_to_resource_key: dict[str, str] = {
        d["_structural"]["operation_key"]: d["_structural"]["resource_key"]
        for d in descriptors
        if isinstance(d.get("_structural"), dict) and d["_structural"].get("resource_key")
    }

    for desc in descriptors:
        op_key = desc["_structural"]["operation_key"]
        ai_orch = global_plan.get(op_key)
        if not ai_orch:
            continue

        ai_flow_raw    = ai_orch.get("suggested_lifecycle_role")
        ai_depends_raw = ai_orch.get("suggested_depends_on")
        ai_dep_map_raw = ai_orch.get("dependency_map")
        ai_role        = ai_orch.get("suggested_lifecycle_role", "")

        orch = _validate_ai_orchestration(
            ai_flow_type       = ai_flow_raw,
            ai_depends_on      = ai_depends_raw,
            structural         = desc["_structural"],
            all_operation_keys = all_op_keys,
        )

        # Apply validated flow/phase/depends_on to _structural
        desc["_structural"]["flow_type"]           = orch["flow_type"]
        desc["_structural"]["phase"]               = orch["phase"]
        desc["_structural"]["depends_on"]          = orch["depends_on"]
        desc["_structural"]["dependency_edges"]    = orch.get("dependency_edges", {})
        desc["_structural"]["orchestration_source"] = orch["orchestration_source"]
        desc["_structural"]["ai_role"]             = orch.get("ai_role", "")

        # Promote state_provider endpoints: they provide reusable execution state
        # regardless of HTTP method, so mark them as producer-equivalent.
        if ai_role in ("state_provider", "producer") or orch["flow_type"] == "producer":
            desc["_structural"]["provides_reusable_state"] = True
            desc["_structural"]["produces_entity"]         = True
            desc["_structural"]["is_producer_endpoint"]    = True

        # Validate and apply dependency map.
        # Accept sources that are either operation_keys or resource_keys (case-normalised).
        if isinstance(ai_dep_map_raw, dict):
            valid_dep_map: dict[str, Any] = {}
            dropped: list[str] = []
            for param_name, dep_info in ai_dep_map_raw.items():
                if not (isinstance(dep_info, dict) and "source" in dep_info and "field" in dep_info):
                    continue
                raw_src = str(dep_info["source"]).strip()
                # Accept exact match or case-normalised match
                if raw_src in valid_sources:
                    canonical_src = raw_src
                elif raw_src.lower() in src_lower_to_canonical:
                    canonical_src = src_lower_to_canonical[raw_src.lower()]
                else:
                    dropped.append(raw_src)
                    continue
                # Translate operation_key → resource_key for executor compatibility.
                # The executor resolves dep_map.source against its entity bucket,
                # which is keyed by resource_key (not operation_key).
                resolved_src = op_key_to_resource_key.get(canonical_src, canonical_src)
                valid_dep_map[str(param_name)] = {
                    "source":        resolved_src,
                    "source_op_key": canonical_src,   # preserved for depends_on chain
                    "field":         str(dep_info["field"]),
                    "confidence":    "high",
                }

            if dropped:
                logger.warning(
                    "[AI-ORCH] %s: dropped %d unrecognised dep_map source(s): %s",
                    op_key, len(dropped), dropped,
                )

            # Apply if AI provided any valid entries OR explicitly sent an empty map
            if valid_dep_map or ai_dep_map_raw == {}:
                desc["_structural"]["dependency_map"] = valid_dep_map
                desc["_structural"]["orchestration_source"] = "ai"

        # Update lifecycle_context so Stage 2 per-operation AI sees resolved values
        lc = desc["lifecycle_context"]
        lc["flow_type"]              = desc["_structural"]["flow_type"]
        lc["depends_on"]             = desc["_structural"]["depends_on"]
        lc["dependency_map"]         = desc["_structural"]["dependency_map"]
        lc["orchestration_source"]   = desc["_structural"]["orchestration_source"]
        lc["provides_reusable_state"]= desc["_structural"].get("provides_reusable_state", False)


async def _call_ai_global_orchestration(
    descriptors: list[dict[str, Any]],
    spec_title: str,
    tenant_id: str = "",
) -> tuple[dict[str, Any], int]:
    """STAGE 1: Global API Graph Analysis.
    Sends a compact summary of all endpoints to Claude to infer the
    global dependency graph and lifecycle orchestration.
    """
    if not descriptors:
        return {}, 0
        
    global_payload = []
    for d in descriptors:
        # Include operation_key as the canonical source anchor (not resource_key).
        # The AI uses operation_key values in dependency_map.source so that the
        # dep_map validator can accept them directly without a resource-key lookup.
        #
        # NEW — three pre-computed structural hints reduce the AI's reasoning burden:
        #
        # 1. reusable_state_fields: field-level inventory of every reusable-state
        #    field detected in this endpoint's 2xx response schema.  The AI can match
        #    these directly against other endpoints' path_param_names and request
        #    schema fields without re-parsing full schemas.
        #
        # 2. rule_depends_on: the rule engine's baseline dependency list for this
        #    endpoint.  The AI uses this as a starting graph it can validate, extend,
        #    or override — not as a hard constraint.  Providing it prevents the AI
        #    from starting with a blank slate and missing obvious edges.
        #
        # 3. rule_flow_type: the rule engine's baseline lifecycle classification.
        #    The AI can accept, override, or refine this classification.
        struct = d["_structural"]
        global_payload.append({
            "operation_key":           struct["operation_key"],
            "method":                  d["method"],
            "path":                    d["path"],
            "path_param_names":        d["path_param_names"],
            "security_required":       d["security_required"],
            "request_schema":          d["request_schema"],
            "response_schemas":        d["response_schemas"],
            "provides_reusable_state": struct.get("provides_reusable_state", False),
            # Pre-computed field inventory for cross-endpoint overlap matching
            "reusable_state_fields":   struct.get("reusable_state_fields") or [],
            # Rule-engine baseline — AI uses as hints, not hard constraints
            "rule_flow_type":          struct.get("flow_type", "independent"),
            "rule_depends_on":         struct.get("depends_on") or [],
        })
        
    from ..prompts.contract import build_global_orchestration_prompt
    system_blocks, prompt_blocks = build_global_orchestration_prompt(
        json.dumps(global_payload, separators=(",", ":")),
        spec_title
    )
    
    try:
        result = await ai_client.generate_json(
            prompt=prompt_blocks,
            system=system_blocks,
            max_tokens=8192,
            temperature=0.0,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("[AI-ORCH-GLOBAL] Claude call failed: %s", exc)
        return {}, 0
        
    raw = result.get("data")
    usage = result.get("usage") or {}
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    
    if not isinstance(raw, list):
        logger.error("[AI-ORCH-GLOBAL] Claude did not return a list")
        return {}, tokens
        
    plan = {}
    for item in raw:
        if isinstance(item, dict) and "operation_key" in item:
            plan[item["operation_key"]] = item
            
    return plan, tokens


# =============================================================================
# MAIN PUBLIC FUNCTION
# =============================================================================

async def generate_contract_tests_ai(
    spec: dict[str, Any],
    *,
    project_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
    suite_name: Optional[str] = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict[str, Any]], int]:
    """Generate AI-powered contract test cases using Claude.

    One Claude call per operation.  Structural fields (resource_key,
    dependency_map, execution_order, flow_type, phase) come entirely from the
    rule-based engine.  The AI contributes assertions, request bodies, and
    human-readable descriptions only.
    Supports Anthropic Batch API execution for high throughput and cost savings.

    Returns
    -------
    (test_cases, total_tokens_used)
    """
    if not ai_client.is_available:
        logger.info("[AI-GEN] AI client not available — returning empty list")
        return [], 0

    # ── PASS 1: Canonicalise ──────────────────────────────────────────────
    if UNIQUE_FORMAT_VALUES:
        reset_unique_cache()

    canonical  = coerce_canonical_spec(spec)
    doc_id     = str(canonical.get("doc_id") or "")
    operations = [op for op in (canonical.get("operations") or []) if isinstance(op, dict)]
    # Sort by operation_key for deterministic processing order
    operations.sort(key=lambda o: str(o.get("operation_key") or ""))
    spec_title = (
        spec.get("info", {}).get("title", "API")
        if isinstance(spec, dict) and isinstance(spec.get("info"), dict)
        else "API"
    )

    if not operations:
        logger.warning("[AI-GEN] No operations found in spec")
        return [], 0

    # ── PASS 2: Full structural analysis (correct order — see BUG 1 fix) ──
    operations, registry = _prepare_operations(operations, doc_id)
    shared_data: dict[str, Any] = {}

    # ── PASS 3: Build per-operation descriptors ───────────────────────────
    descriptors: list[dict[str, Any]] = []
    for op in operations:
        try:
            desc = _build_ai_endpoint_descriptor(op, registry, shared_data)
            descriptors.append(desc)
        except Exception as exc:
            logger.warning(
                "[AI-GEN] descriptor build failed for %s %s: %s",
                op.get("method"), op.get("path"), exc,
            )

    logger.info("[AI-GEN] Built %d operation descriptors (use_batch=%s)", len(descriptors), use_batch)

    # Build the sets of all known operation_keys and resource_keys
    all_op_keys: frozenset[str] = frozenset(
        str(d["_structural"]["operation_key"])
        for d in descriptors
        if isinstance(d.get("_structural"), dict)
    )
    all_resource_keys: frozenset[str] = frozenset(
        str(d["_structural"]["resource_key"])
        for d in descriptors
        if isinstance(d.get("_structural"), dict) and d["_structural"].get("resource_key")
    )

    # ── STAGE 1: Global Orchestration Analysis ────────────────────────────
    global_plan, global_tokens = await _call_ai_global_orchestration(descriptors, spec_title, tenant_id=tenant_id)
    total_tokens = global_tokens

    # ── Apply STAGE 1 global orchestration to descriptors ─────────────────
    _apply_ai_global_plan(descriptors, global_plan, all_op_keys, all_resource_keys)

    # ── Propagate transitive dependency edges ─────────────────────────────
    _propagate_transitive_deps(descriptors)

    all_test_cases: list[dict[str, Any]] = []

    if use_batch and len(descriptors) > 0:
        batch_requests = []
        for idx, desc in enumerate(descriptors):
            system_blocks, prompt_blocks = build_operation_prompt(desc)
            req = ai_client.prepare_batch_request(
                custom_id=f"cont-{idx}",
                prompt=prompt_blocks,
                system=system_blocks,
                max_tokens=_AI_MAX_TOKENS_PER_OP,
                temperature=_AI_TEMPERATURE,
            )
            batch_requests.append(req)

        results_by_id, _ = await ai_client.execute_batch_with_retry(
            batch_requests, on_status_update=on_status_update
        )

        for idx, desc in enumerate(descriptors):
            res = results_by_id.get(f"cont-{idx}", {})
            ai_items = res.get("data")
            if not isinstance(ai_items, list):
                ai_items = []
            usage = res.get("usage", {})
            total_tokens += usage.get("input_tokens", 0) + usage.get("output_tokens", 0)

            structural       = desc["_structural"]
            valid_status_set = set(desc["status_codes"])

            for item in ai_items:
                tc = _normalise_ai_item(
                    item,
                    structural,
                    valid_status_codes  = valid_status_set,
                )
                if tc is not None:
                    all_test_cases.append(tc)
    else:
        # ── STAGE 2: Parallel per-operation Claude calls ──────────────────────
        semaphore = asyncio.Semaphore(_AI_CONCURRENCY)
        tasks = [
            _call_ai_for_operation(desc, semaphore=semaphore)
            for desc in descriptors
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # ── PASS 5: Normalise AI output → full test cases ─────────────────────
        for desc, result in zip(descriptors, results):
            if isinstance(result, BaseException):
                logger.error("[AI-GEN] task raised exception: %s", result)
                continue

            if not (isinstance(result, tuple) and len(result) == 2):
                logger.error("[AI-GEN] task returned unexpected result: %r", result)
                continue

            ai_items, tokens = result
            total_tokens += tokens

            structural       = desc["_structural"]
            valid_status_set = set(desc["status_codes"])

            for item in ai_items:
                tc = _normalise_ai_item(
                    item,
                    structural,
                    valid_status_codes  = valid_status_set,
                )
                if tc is not None:
                    all_test_cases.append(tc)

    logger.info(
        "[AI-GEN] %d test cases normalised (%d tokens used)",
        len(all_test_cases), total_tokens,
    )

    # ── PASS 6: Sort + stamp execution_order ─────────────────────────────
    all_test_cases = _assign_execution_order(all_test_cases)

    # ── PASS 7: Topological sort + dedup + validation gate ───────────────
    # _topological_order uses tc["depends_on"] (operation_key list) to
    # guarantee producers precede consumers; this was already computed
    # correctly in PASS 2 by _analyze_operation_dependencies.
    all_test_cases = _deduplicate_tests(all_test_cases)
    all_test_cases = _topological_order(all_test_cases)  # re-stamps execution_order
    all_test_cases = _final_validate(all_test_cases)

    # Re-stamp after possible drops by _final_validate
    for i, tc in enumerate(all_test_cases):
        tc["execution_order"] = i

    logger.info("[AI-GEN] Final suite: %d test cases", len(all_test_cases))

    # ── PASS 8: DB persistence (fresh suite each run → overwrites previous) ─
    if _PERSIST_AVAILABLE and project_id and triggered_by and persist_contract_suite_and_cases is not None:
        try:
            suite_id = await persist_contract_suite_and_cases(
                project_id   = project_id,
                triggered_by = triggered_by,
                test_cases   = all_test_cases,
                suite_name   = suite_name or f"AI Contract Suite — {spec_title}",
            )
            logger.info(
                "[AI-GEN] Persisted suite %s (%d cases)", suite_id, len(all_test_cases)
            )
        except Exception as exc:
            logger.warning("[AI-GEN] DB persistence failed (non-fatal): %s", exc)

    return all_test_cases, total_tokens


# =============================================================================
# BULK FALLBACK  (single call, used when concurrency is unavailable)
# =============================================================================

async def generate_contract_tests_ai_bulk(
    spec: dict[str, Any],
    *,
    project_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
    suite_name: Optional[str] = None,
    tenant_id: str = "",
) -> tuple[list[dict[str, Any]], int]:
    """Single-call fallback. Lower accuracy than per-operation path."""
    if not ai_client.is_available:
        return [], 0

    if UNIQUE_FORMAT_VALUES:
        reset_unique_cache()

    canonical  = coerce_canonical_spec(spec)
    doc_id     = str(canonical.get("doc_id") or "")
    operations = [op for op in (canonical.get("operations") or []) if isinstance(op, dict)]
    operations.sort(key=lambda o: str(o.get("operation_key") or ""))
    spec_title = (
        spec.get("info", {}).get("title", "API")
        if isinstance(spec, dict) and isinstance(spec.get("info"), dict)
        else "API"
    )

    if not operations:
        return [], 0

    operations, registry = _prepare_operations(operations, doc_id)
    shared_data: dict[str, Any] = {}

    descriptors: list[dict[str, Any]] = []
    for op in operations:
        try:
            desc = _build_ai_endpoint_descriptor(op, registry, shared_data)
            descriptors.append(desc)
        except Exception:
            pass

    # Build the sets of all known operation_keys and resource_keys
    all_op_keys: frozenset[str] = frozenset(
        str(d["_structural"]["operation_key"])
        for d in descriptors
        if isinstance(d.get("_structural"), dict)
    )
    all_resource_keys: frozenset[str] = frozenset(
        str(d["_structural"]["resource_key"])
        for d in descriptors
        if isinstance(d.get("_structural"), dict) and d["_structural"].get("resource_key")
    )

    # ── STAGE 1: Global Orchestration Analysis ────────────────────────────
    global_plan, global_tokens = await _call_ai_global_orchestration(descriptors, spec_title, tenant_id=tenant_id)
    
    # ── Apply STAGE 1 global orchestration to descriptors ─────────────────
    _apply_ai_global_plan(descriptors, global_plan, all_op_keys, all_resource_keys)

    # ── Propagate transitive dependency edges ─────────────────────────────
    _propagate_transitive_deps(descriptors)

    bulk_payload = [
        {
            "method":            d["method"],
            "path":              d["path"],
            "status_codes":      d["status_codes"],
            "request_schema":    d["request_schema"],
            "response_schemas":  d["response_schemas"],
            "parameters":        d["parameters"],
            "security_required": d["security_required"],
            "has_request_body":  d["has_request_body"],
            "path_param_names":  d["path_param_names"],
            "lifecycle_context": d["lifecycle_context"],
        }
        for d in descriptors
    ]

    prompt = build_contract_prompt(
        json.dumps(bulk_payload, separators=(",", ":")),
        spec_title,
    )

    try:
        result = await ai_client.generate_json(
            prompt=prompt,
            system=CONTRACT_SYSTEM,
            max_tokens=8192,
            temperature=_AI_TEMPERATURE,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.error("[AI-GEN-BULK] Claude call failed: %s", exc)
        return [], 0

    raw   = result.get("data")
    usage = result.get("usage") or {}
    tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
    tokens += global_tokens

    if not isinstance(raw, list):
        return [], tokens

    # Build lookup: (method, path) → descriptor
    desc_lookup: dict[tuple[str, str], dict[str, Any]] = {
        (d["method"], d["path"]): d for d in descriptors
    }

    all_test_cases: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        m = (item.get("method") or "").upper()
        p = item.get("endpoint_path") or item.get("path") or ""
        desc = desc_lookup.get((m, p))
        if desc is None:
            logger.warning("[AI-GEN-BULK] Hallucinated endpoint %s %s — skipping", m, p)
            continue
        tc = _normalise_ai_item(
            item,
            desc["_structural"],
            valid_status_codes=set(desc["status_codes"]),
        )
        if tc is not None:
            all_test_cases.append(tc)

    all_test_cases = _assign_execution_order(all_test_cases)
    all_test_cases = _deduplicate_tests(all_test_cases)
    all_test_cases = _topological_order(all_test_cases)
    all_test_cases = _final_validate(all_test_cases)
    for i, tc in enumerate(all_test_cases):
        tc["execution_order"] = i

    if _PERSIST_AVAILABLE and project_id and triggered_by and persist_contract_suite_and_cases is not None:
        try:
            await persist_contract_suite_and_cases(
                project_id   = project_id,
                triggered_by = triggered_by,
                test_cases   = all_test_cases,
                suite_name   = suite_name or f"AI Contract Suite — {spec_title}",
            )
        except Exception as exc:
            logger.warning("[AI-GEN-BULK] DB persistence failed: %s", exc)

    return all_test_cases, tokens