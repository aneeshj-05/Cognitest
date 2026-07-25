"""
Authorization Test Generator.

Generates the three authorization scenario dicts for every secured endpoint
in the OpenAPI spec.  No HTTP requests are made here — this is pure data
generation.  The executor module consumes these scenario dicts.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from ...spec_parser import Endpoint
from .classifier import ScenarioType
from .context import TestContext


# ---------------------------------------------------------------------------
# Scenario dataclass
# ---------------------------------------------------------------------------


@dataclass
class AuthzScenario:
    """
    A single authorization test scenario ready for execution.

    Attributes:
        id:              Unique identifier for de-duplication in reports.
        endpoint_path:   Resolved API path (path params substituted).
        method:          HTTP method.
        scenario_type:   Which of the three authorization categories.
        headers:         HTTP headers to send (may include Authorization).
        body:            Optional request body dict.
        expected_status: Expected HTTP status for determining pass/fail.
        description:     Human-readable test description.
    """

    id: str
    endpoint_path: str
    method: str
    scenario_type: ScenarioType
    headers: dict[str, str]
    body: dict[str, Any]
    expected_status: int
    description: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "endpoint_path": self.endpoint_path,
            "method": self.method,
            "scenario_type": self.scenario_type.value,
            "headers": self.headers,
            "body": self.body,
            "expected_status": self.expected_status,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Path parameter substitution
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(r"\{(\w+)\}")


def _resolve_path(
    path: str,
    ctx: TestContext,
    resource_type_hint: str = "",
) -> str:
    """
    Replace OpenAPI path parameters with real or placeholder values.

    Uses resource IDs stored in *ctx.resource_ids* where possible.
    """

    def _substitute(match: re.Match) -> str:
        param_name = match.group(1)
        param_lower = param_name.lower()

        # Try exact resource type match first
        if resource_type_hint and resource_type_hint in ctx.resource_ids:
            return ctx.resource_ids[resource_type_hint]

        # Try fuzzy match on param name
        for key, rid in ctx.resource_ids.items():
            if key in param_lower or param_lower in key:
                return rid

        # Fallback placeholder
        return "cognitest-placeholder-id"

    return _PARAM_RE.sub(_substitute, path)


# ---------------------------------------------------------------------------
# Minimal body builder (re-used from setup_orchestrator pattern)
# ---------------------------------------------------------------------------


def _minimal_body(schema: dict | None) -> dict:
    if not schema:
        return {}
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    body: dict = {}
    for name, definition in properties.items():
        if name not in required and required:
            continue
        ftype = definition.get("type", "string")
        if ftype in ("integer", "number"):
            body[name] = 1
        elif ftype == "boolean":
            body[name] = True
        elif ftype == "array":
            body[name] = []
        else:
            body[name] = f"cognitest-{name}"
    return body


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_authz_scenarios(
    secured_endpoints: list[Endpoint],
    ctx: TestContext,
) -> list[AuthzScenario]:
    """
    For each secured endpoint produce three :class:`AuthzScenario` objects.

    Args:
        secured_endpoints: List of endpoints requiring bearer authentication.
        ctx:               TestContext populated after the setup phase.

    Returns:
        Flat list of all scenarios ready for the executor.
    """
    scenarios: list[AuthzScenario] = []

    for ep in secured_endpoints:
        # Derive a resource-type hint from the path for ID substitution
        segments = [s for s in ep.path.strip("/").split("/") if not s.startswith("{")]
        resource_hint = segments[-1] if segments else ""

        resolved_path = _resolve_path(ep.path, ctx, resource_hint)
        body = _minimal_body(ep.body_schema)

        # ------------------------------------------------------------------
        # Scenario A – No Authorization header (expect 401)
        # ------------------------------------------------------------------
        scenarios.append(
            AuthzScenario(
                id=str(uuid.uuid4()),
                endpoint_path=resolved_path,
                method=ep.method,
                scenario_type=ScenarioType.UNAUTHENTICATED,
                headers={},
                body=body,
                expected_status=401,
                description=(
                    f"[A] Unauthenticated: {ep.method} {resolved_path} without any "
                    f"Authorization header → expect 401."
                ),
            )
        )

        # ------------------------------------------------------------------
        # Scenario B – Token A, resource owned by User B (expect 403)
        # ------------------------------------------------------------------
        scenarios.append(
            AuthzScenario(
                id=str(uuid.uuid4()),
                endpoint_path=resolved_path,
                method=ep.method,
                scenario_type=ScenarioType.WRONG_OWNER,
                headers=ctx.auth_header_a(),  # user A's token
                body=body,
                expected_status=403,
                description=(
                    f"[B] Wrong Owner: {ep.method} {resolved_path} with User A's token "
                    f"against a resource owned by User B → expect 403."
                ),
            )
        )

        # ------------------------------------------------------------------
        # Scenario C – Token B, resource owned by User B (expect 2xx)
        # ------------------------------------------------------------------
        scenarios.append(
            AuthzScenario(
                id=str(uuid.uuid4()),
                endpoint_path=resolved_path,
                method=ep.method,
                scenario_type=ScenarioType.CORRECT_OWNER,
                headers=ctx.auth_header_b(),  # user B's token
                body=body,
                expected_status=200,
                description=(
                    f"[C] Correct Owner: {ep.method} {resolved_path} with User B's token "
                    f"against User B's resource → expect 2xx."
                ),
            )
        )

    return scenarios
