"""
Dependency Orchestrator — thin coordinator (planning only).

Composes classifier + dep_graph + annotation into two public functions:
  build_execution_plan()   — annotate & sort test cases
  get_execution_summary()  — human-readable plan (for logging)

Runtime execution (guards, health, context) lives in:
  exec_context.py, exec_guards.py, health_monitor.py
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ...spec_parser import Endpoint
from .dep_graph import build_dependency_graph, EndpointNode
from .classifier import EndpointRole, classify_endpoint

logger = logging.getLogger(__name__)

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


# ---------------------------------------------------------------------------
# Annotation helpers
# ---------------------------------------------------------------------------

def _find_placeholders(tc: dict) -> list[str]:
    found: set[str] = set()

    def _scan(obj: Any) -> None:
        if isinstance(obj, str):
            found.update(_PLACEHOLDER_RE.findall(obj))
        elif isinstance(obj, dict):
            for v in obj.values(): _scan(v)
        elif isinstance(obj, list):
            for item in obj: _scan(item)

    _scan(tc)
    return list(found)


def _annotate(test_cases: list[dict], nodes: list[EndpointNode]) -> list[dict]:
    """Add execution metadata to each test case dict (additive, non-destructive)."""
    node_map = {
        (n.endpoint.path, n.endpoint.method.upper()): n
        for n in nodes
    }

    annotated: list[dict] = []
    for idx, tc in enumerate(test_cases):
        path   = tc.get("endpoint_path", "")
        method = (tc.get("method") or "GET").upper()
        node   = node_map.get((path, method))

        if node is None:
            annotated.append({**tc, "execution_order": 5})
            continue

        annotated.append({
            **tc,
            "execution_order": node.priority,
            "depends_on":      node.requires,
            "skip_if_missing": node.requires,
            "extract":         {**node.extract_rules, **(tc.get("extract") or {})},
            "dynamic_vars":    _find_placeholders(tc),
            "endpoint_roles":  [r.value for r in node.roles],
        })

    annotated.sort(key=lambda t: (t.get("execution_order", 5), 0))
    return annotated


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_execution_plan(
    endpoints: list[Endpoint],
    test_cases: list[dict],
) -> list[dict]:
    """
    Classify endpoints, build dependency graph, annotate and sort test cases.

    Returns:
        Annotated test cases sorted by execution phase.
    """
    if not endpoints or not test_cases:
        return test_cases

    nodes = build_dependency_graph(endpoints)

    role_counts = {r.value: sum(1 for n in nodes if r in n.roles) for r in EndpointRole}
    logger.info("[Orchestrator] %d endpoints classified: %s", len(nodes), role_counts)

    annotated = _annotate(test_cases, nodes)
    logger.info("[Orchestrator] %d test cases annotated.", len(annotated))
    return annotated


def get_execution_summary(endpoints: list[Endpoint]) -> dict[str, Any]:
    """Return a structured summary of the execution plan (for logging/debug)."""
    nodes = build_dependency_graph(endpoints)
    plan = [
        {
            "order":          i + 1,
            "path":           n.endpoint.path,
            "method":         n.endpoint.method,
            "roles":          [r.value for r in n.roles],
            "provides":       n.provides,
            "requires":       n.requires,
            "priority_bucket": n.priority,
        }
        for i, n in enumerate(nodes)
    ]
    return {"total_endpoints": len(nodes), "execution_plan": plan}
