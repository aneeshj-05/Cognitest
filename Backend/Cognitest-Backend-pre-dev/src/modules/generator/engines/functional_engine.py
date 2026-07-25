"""
Functional Testing Engine — orchestrates all functional sub-generators.

Generates comprehensive functional tests by combining results from:
- CRUD operation validation
- JSON/XML schema validation
- Query/path/header parameter tests
- Multi-step workflow/chaining tests
- Pagination, filtering, and sorting tests

When an AI client is available (ANTHROPIC_API_KEY set), test cases are
enhanced with realistic payloads, domain-aware assertions, and
explanations. Without AI, rule-based tests are returned as-is.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from ..spec_parser import extract_endpoints
from .functional import (
    generate_crud_tests,
    generate_schema_validation_tests,
    generate_param_tests,
    generate_workflow_tests,
    generate_pagination_tests,
    build_execution_plan,
    get_execution_summary,
)
from ..ai.utils import prune_schema_for_ai

logger = logging.getLogger(__name__)


def deduplicate_test_cases(test_cases: list[dict]) -> list[dict]:
    """
    Remove truly redundant test cases — tests that are byte-for-byte identical
    in their key dimensions: method, endpoint_path, name, and expected_status.

    IMPORTANT: For AI-generated tests, we use a strict signature so that
    tests with the same endpoint but different scenarios (e.g. 'Valid login
    with email' vs 'Valid login with username') are NOT collapsed together.
    The old 'BASIC-SUCCESS' heuristic was removing most AI tests incorrectly.
    """
    seen: set[str] = set()
    unique_tests: list[dict] = []

    for test in test_cases:
        method = test.get("method", "").upper()
        path   = test.get("endpoint_path", "")
        name   = (test.get("name") or "").strip()
        status = test.get("expected_status", "")

        # Strict signature: only drop if ALL four dimensions are identical
        sig = f"{method}:{path}:{name}:{status}"

        if sig not in seen:
            unique_tests.append(test)
            seen.add(sig)
        else:
            logger.debug("[Dedup] Removed exact duplicate: %s %s — %s", method, path, name)

    original_count = len(test_cases)
    removed_count  = original_count - len(unique_tests)
    if removed_count:
        logger.info("[Dedup] %d → %d tests (%d exact duplicates removed)",
                    original_count, len(unique_tests), removed_count)

    return unique_tests


def _order_tests_for_execution(
    workflow_tests: list[dict],
    crud_tests: list[dict],
    schema_tests: list[dict],
    param_tests: list[dict],
    pagination_tests: list[dict],
) -> list[dict]:
    """
    Order all test cases so they can be executed sequentially against a real AUT.

    Execution order:
    1. Auth workflow  (Register → Login → extract token)  — MUST run first
    2. Other workflow chains  (Create→Read, Create→Update→Read, order flow, …)
    3. Per-resource CRUD tests, sorted:
       a) Public endpoints first (no auth required)
       b) Auth-required endpoints second (token should be available by now)
       c) Within each group: POST → GET (list) → GET (by id) → PUT/PATCH → DELETE
    4. Schema validation, parameter, and pagination tests last (read-only, no side effects)
    """
    # --- Split workflow tests into auth vs others ---
    auth_workflows = [t for t in workflow_tests if
                      any(kw in t.get("name", "").lower()
                          for kw in ("login", "register", "auth", "token", "session"))]
    other_workflows = [t for t in workflow_tests if t not in auth_workflows]

    # --- Sort CRUD tests ---
    method_priority = {"POST": 0, "GET": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

    # Protected path heuristics (same as workflow.py _endpoint_needs_auth)
    _protected_patterns = (
        "/cart", "/orders", "/checkout", "/profile",
        "/account", "/wishlist", "/favorites", "/settings",
        "/admin", "/dashboard", "/payments", "/subscriptions",
    )

    def _looks_protected(path: str) -> bool:
        pl = path.lower()
        return any(p in pl for p in _protected_patterns)

    def crud_sort_key(t: dict) -> tuple:
        path = t.get("endpoint_path", "")
        # Auth-required tests sort after public ones (0=public, 1=protected)
        needs_auth = int(
            t.get("requires_auth", False)
            or _looks_protected(path)
        )
        # Resources with path params come after the collection-level path
        has_path_param = "{" in path
        method = t.get("method", "GET").upper()
        return (needs_auth, path.split("{")[0], int(has_path_param), method_priority.get(method, 5))

    sorted_crud = sorted(crud_tests, key=crud_sort_key)

    return (
        auth_workflows
        + other_workflows
        + sorted_crud
        + schema_tests
        + param_tests
        + pagination_tests
    )


def generate_functional_tests(spec: dict[str, Any]) -> list[dict]:
    """
    Generate comprehensive functional tests based on OpenAPI/Swagger spec.
    Rule-based only — synchronous entry point.

    Tests are annotated and sorted by the dependency orchestrator:
      0. Auth workflows (Register → Login → token)
      1. Collection providers (GET lists → extract IDs)
      2. Creator endpoints (POST resource → extract new IDs)
      3. Resource-with-ID endpoints (use token + extracted IDs)
      4. Auth-required general endpoints
      5. Schema / param / pagination tests (read-only)

    Args:
        spec: OpenAPI/Swagger specification dictionary

    Returns:
        List of test case dicts sorted for safe sequential execution.
    """
    endpoints = extract_endpoints(spec)

    # Log execution plan summary for debugging
    plan_summary = get_execution_summary(endpoints)
    logger.info(
        "[FunctionalEngine] Execution plan: %d endpoints classified",
        plan_summary["total_endpoints"],
    )

    crud_tests: list[dict] = []
    schema_tests: list[dict] = []
    param_tests: list[dict] = []
    pagination_tests: list[dict] = []

    for endpoint in endpoints:
        crud_tests.extend(generate_crud_tests(endpoint))
        schema_tests.extend(generate_schema_validation_tests(endpoint))
        param_tests.extend(generate_param_tests(endpoint))
        pagination_tests.extend(generate_pagination_tests(endpoint))

    workflow_tests = generate_workflow_tests(endpoints)

    all_tests = workflow_tests + crud_tests + schema_tests + param_tests + pagination_tests

    # Apply dependency orchestrator — sorts and annotates with roles/deps
    ordered = build_execution_plan(endpoints, all_tests)
    return deduplicate_test_cases(ordered)



async def generate_functional_tests_enhanced(
    spec: dict[str, Any],
    admin_config: dict | None = None,
    tenant_id: str = "",
    use_batch: bool = True,
    on_status_update: Any = None,
) -> tuple[list[dict], int]:
    """
    Generate functional tests — AI-driven when available, rule-based fallback otherwise.

    When AI is available:
      - Skips the rule-based pre-step entirely.
      - Sends raw spec endpoints to the AI in parallel resource-grouped chunks.
      - AI generates all tests from scratch following the lifecycle:
          signup → login → create → read → update → delete.
      - Dependency orchestrator orders the final list.

    When AI is NOT available:
      - Falls back to the existing rule-based generators.

    Args:
        spec:         OpenAPI/Swagger specification dictionary.
        admin_config: Optional dict with admin credentials for admin routes.

    Returns:
        Tuple of (test_cases, total_ai_tokens_used)
    """
    from ..ai.client import ai_client
    from ..ai.generators.functional_generator_ai import (
        generate_functional_tests_enhanced as generate_functional_tests_ai_gen,
    )

    endpoints = extract_endpoints(spec)

    # ── Fallback: no AI available → rule-based only ──────────────────────────
    if not ai_client.is_available:
        logger.info("[FunctionalEngine] AI not available — using rule-based generators")
        crud_tests       = generate_crud_tests_all(endpoints)
        schema_tests     = generate_schema_tests_all(endpoints)
        param_tests      = generate_param_tests_all(endpoints)
        pagination_tests = generate_pagination_tests_all(endpoints)
        workflow_tests   = generate_workflow_tests(endpoints)
        all_tests = workflow_tests + crud_tests + schema_tests + param_tests + pagination_tests
        ordered = build_execution_plan(endpoints, all_tests)
        return deduplicate_test_cases(ordered), 0, []

    # ── AI path: generate directly from spec (no rule-based pre-step) ────────
    logger.info("[FunctionalEngine] AI available — generating tests directly from spec "
                "(%d endpoints, parallel chunk dispatch)", len(endpoints))

    result = await generate_functional_tests_ai_gen(
        spec=spec,
        endpoints=endpoints,
        admin_config=admin_config,
        tenant_id=tenant_id,
        use_batch=use_batch,
        on_status_update=on_status_update,
    )
    # generate_functional_tests_ai now returns (cases, total_tokens, token_batches)
    if len(result) == 3:
        all_tests, total_tokens, token_batches = result
    else:
        all_tests, total_tokens = result
        token_batches = []

    if not all_tests:
        # AI returned nothing (e.g. all chunks failed) — fall back to rule-based
        logger.warning("[FunctionalEngine] AI returned 0 tests — falling back to rule-based")
        crud_tests       = generate_crud_tests_all(endpoints)
        schema_tests     = generate_schema_tests_all(endpoints)
        param_tests      = generate_param_tests_all(endpoints)
        pagination_tests = generate_pagination_tests_all(endpoints)
        workflow_tests   = generate_workflow_tests(endpoints)
        all_tests = workflow_tests + crud_tests + schema_tests + param_tests + pagination_tests
        token_batches = []
        total_tokens = 0

    # Apply dependency orchestrator — sorts and annotates with roles/deps
    ordered = build_execution_plan(endpoints, all_tests)
    return deduplicate_test_cases(ordered), total_tokens, token_batches


def generate_crud_tests_all(endpoints):
    tests = []
    for ep in endpoints:
        tests.extend(generate_crud_tests(ep))
    return tests

def generate_schema_tests_all(endpoints):
    tests = []
    for ep in endpoints:
        tests.extend(generate_schema_validation_tests(ep))
    return tests

def generate_param_tests_all(endpoints):
    tests = []
    for ep in endpoints:
        tests.extend(generate_param_tests(ep))
    return tests

def generate_pagination_tests_all(endpoints):
    tests = []
    for ep in endpoints:
        tests.extend(generate_pagination_tests(ep))
    return tests
