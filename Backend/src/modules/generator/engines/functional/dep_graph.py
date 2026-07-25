"""
Dependency graph builder — maps endpoints to EndpointNode objects with
extraction rules and dependency requirements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .classifier import EndpointRole, classify_endpoint, priority_of, _TOKEN_FIELDS, _ID_FIELD_RE

if TYPE_CHECKING:
    from ...spec_parser import Endpoint


@dataclass
class EndpointNode:
    endpoint: "Endpoint"
    roles: list[EndpointRole]
    priority: int = 99
    provides: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    extract_rules: dict[str, str] = field(default_factory=dict)


def _extract_rules(endpoint: "Endpoint", roles: list[EndpointRole]) -> dict[str, str]:
    """Build generic JSONPath extraction rules from response schema."""
    rules: dict[str, str] = {}
    rs = endpoint.response_schema or {}
    props = set((rs.get("properties") or {}).keys())

    # Token extraction
    if EndpointRole.AUTH_PROVIDER in roles:
        tok = list(props & _TOKEN_FIELDS)
        if tok:
            paths = " || ".join(f"$.{f}" for f in tok)
            data_paths = " || ".join(f"$.data.{f}" for f in tok)
            rules["auth_token"] = f"{paths} || {data_paths}"
        else:
            rules["auth_token"] = (
                "$.token || $.access_token || $.accessToken || $.jwt"
                " || $.data.token || $.data.access_token || $.data.accessToken"
            )

    # Collection ID extraction (first-item approach)
    if EndpointRole.COLLECTION_PROVIDER in roles:
        rules["resource_id"] = (
            "$.data[0].id || $.data[0]._id || $.items[0].id"
            " || $.results[0].id || $[0].id || $[0]._id"
        )
        return rules

    # Creator / auth-provider ID extraction
    id_fields = [f for f in props if _ID_FIELD_RE.match(f)]
    if id_fields:
        f = id_fields[0]
        rules["resource_id"] = f"$.{f} || $.data.{f} || $.data.id || $.id"
    elif EndpointRole.CREATOR in roles or EndpointRole.AUTH_PROVIDER in roles:
        rules["resource_id"] = "$.id || $.data.id || $._id || $.data._id"

    return rules


def _requires(roles: list[EndpointRole]) -> list[str]:
    req: list[str] = []
    if EndpointRole.AUTH_REQUIRED in roles:
        req.append("auth_token")
    if EndpointRole.RESOURCE_WITH_ID in roles and EndpointRole.AUTH_REQUIRED in roles:
        req.append("resource_id")
    return req


def build_dependency_graph(endpoints: list["Endpoint"]) -> list[EndpointNode]:
    """Classify endpoints and return priority-sorted EndpointNode list."""
    nodes: list[EndpointNode] = []
    for ep in endpoints:
        roles = classify_endpoint(ep)
        p = priority_of(roles)
        extract = _extract_rules(ep, roles)
        reqs = _requires(roles)
        nodes.append(EndpointNode(
            endpoint=ep,
            roles=roles,
            priority=p,
            provides=list(extract.keys()),
            requires=reqs,
            extract_rules=extract,
        ))
    nodes.sort(key=lambda n: (n.priority, n.endpoint.path, n.endpoint.method))
    return nodes
