"""
Async Scenario Executor.

Executes :class:`AuthzScenario` objects against the live API and classifies
each response.  Results are yielded as :class:`StatefulTestResult` objects
so the caller can stream them immediately without waiting for all tests.

Handles:
  - Token expiry retry (re-login if 401 returned on a scenario that expected
    non-401, via a single retry before giving up)
  - Connection / timeout errors (yield CRITICAL result instead of crashing)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx

from .authz_generator import AuthzScenario
from .classifier import ScenarioType, SecurityClassification, Severity, classify_result
from .context import TestContext

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class StatefulTestResult:
    """
    The outcome of executing a single :class:`AuthzScenario`.

    Attributes:
        scenario_id:      Matches the originating AuthzScenario.id.
        endpoint_path:    Resolved API path that was called.
        method:           HTTP method used.
        scenario_type:    Which authorization scenario category.
        request_headers:  Headers sent with the actual token injected.
        expected_status:  Expected HTTP status from the scenario.
        actual_status:    HTTP status returned by the API.
        classification:   Security outcome classification.
        error:            Error message if the request could not be made.
    """

    scenario_id: str
    endpoint_path: str
    method: str
    scenario_type: ScenarioType
    request_headers: dict[str, str]
    expected_status: int
    actual_status: int
    classification: SecurityClassification
    description: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        # Show the real Authorization header — do NOT redact the token.
        return {
            "scenario_id": self.scenario_id,
            "endpoint_path": self.endpoint_path,
            "method": self.method,
            "scenario_type": self.scenario_type.value,
            "request_headers": dict(self.request_headers),
            "expected_status": self.expected_status,
            "actual_status": self.actual_status,
            "passed": self.classification.passed,
            "classification": self.classification.label,
            "severity": self.classification.severity.value,
            "description": self.description,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _error_result(scenario: AuthzScenario, error_msg: str) -> StatefulTestResult:
    """Construct a CRITICAL result for a request that could not be made."""
    classification = SecurityClassification(
        label=f"Request Error – {error_msg}",
        severity=Severity.CRITICAL,
        passed=False,
    )
    return StatefulTestResult(
        scenario_id=scenario.id,
        endpoint_path=scenario.endpoint_path,
        method=scenario.method,
        scenario_type=scenario.scenario_type,
        request_headers=scenario.headers,
        expected_status=scenario.expected_status,
        actual_status=0,
        classification=classification,
        description=scenario.description,
        error=error_msg,
    )


async def _execute_single(
    scenario: AuthzScenario,
    ctx: TestContext,
    login_path: str | None,
) -> StatefulTestResult:
    """
    Execute one scenario and return its classified result.

    Retries once if a 401 is returned on a scenario where the token was
    expected to be valid (i.e., token may have expired).
    """
    url = ctx.full_url(scenario.endpoint_path)
    method = scenario.method.upper()
    headers = {**scenario.headers, "User-Agent": "Cognitest-StatefulSecurityScanner/1.0"}

    # Add Content-Type for mutating methods
    if method in ("POST", "PUT", "PATCH") and scenario.body:
        headers["Content-Type"] = "application/json"

    try:
        if method in ("POST", "PUT", "PATCH"):
            response = await ctx.http_client.request(method, url, headers=headers, json=scenario.body or {})
        else:
            response = await ctx.http_client.request(method, url, headers=headers)

        actual = response.status_code

        # ------------------------------------------------------------------
        # Token refresh retry logic
        # Scenario B and C should have a valid token; if we get 401 back
        # it might be expired — retry once with a refreshed token.
        # ------------------------------------------------------------------
        if (
            actual == 401
            and scenario.scenario_type != ScenarioType.UNAUTHENTICATED
            and login_path
            and "Authorization" in scenario.headers
        ):
            logger.info("Token may be expired for %s %s – attempting refresh", method, url)
            creds = (
                ctx.creds_a
                if scenario.scenario_type == ScenarioType.WRONG_OWNER
                else ctx.creds_b
            )
            try:
                refresh_resp = await ctx.http_client.post(ctx.full_url(login_path), json=creds)
                if refresh_resp.status_code in (200, 201):
                    from .setup_orchestrator import _extract_token  # local import to avoid circular

                    new_token = _extract_token(refresh_resp.json())
                    if new_token:
                        # Update context tokens for subsequent scenarios
                        if scenario.scenario_type == ScenarioType.WRONG_OWNER:
                            ctx.token_a = new_token
                            headers["Authorization"] = f"Bearer {new_token}"
                        else:
                            ctx.token_b = new_token
                            headers["Authorization"] = f"Bearer {new_token}"

                        # Retry the original request
                        if method in ("POST", "PUT", "PATCH"):
                            response = await ctx.http_client.request(
                                method, url, headers=headers, json=scenario.body or {}
                            )
                        else:
                            response = await ctx.http_client.request(method, url, headers=headers)
                        actual = response.status_code
                        logger.info("Retry after token refresh: %s %s → %d", method, url, actual)
            except Exception as refresh_err:  # noqa: BLE001
                logger.warning("Token refresh failed during retry: %s", refresh_err)

        classification = classify_result(scenario.scenario_type, actual)
        logger.info(
            "[Executor] %s %s → %d | %s (%s)",
            method,
            scenario.endpoint_path,
            actual,
            classification.label,
            classification.severity.value,
        )
        return StatefulTestResult(
            scenario_id=scenario.id,
            endpoint_path=scenario.endpoint_path,
            method=method,
            scenario_type=scenario.scenario_type,
            request_headers=scenario.headers,
            expected_status=scenario.expected_status,
            actual_status=actual,
            classification=classification,
            description=scenario.description,
        )

    except httpx.TimeoutException:
        return _error_result(scenario, "Request timed out")
    except httpx.ConnectError:
        return _error_result(scenario, "Could not connect to target API")
    except Exception as exc:  # noqa: BLE001
        return _error_result(scenario, f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def execute_scenarios(
    scenarios: list[AuthzScenario],
    ctx: TestContext,
    login_path: str | None = None,
) -> AsyncIterator[StatefulTestResult]:
    """
    Asynchronously execute *scenarios* and yield results one-by-one.

    Args:
        scenarios:   List of :class:`AuthzScenario` objects to execute.
        ctx:         Populated :class:`TestContext` with valid tokens.
        login_path:  API login path for token refresh retries (optional).

    Yields:
        :class:`StatefulTestResult` for each executed scenario.
    """
    for scenario in scenarios:
        result = await _execute_single(scenario, ctx, login_path)
        yield result


async def run_stateful_security_scenarios(
    spec: dict,
    base_url: str,
    http_client: httpx.AsyncClient,
) -> AsyncIterator[dict]:
    """
    Full stateful security run pipeline.  This is the single public entry
    point consumed by the FastAPI streaming endpoint.

    Pipeline:
        1. Analyze spec → discover endpoints
        2. Initialize TestContext
        3. Run setup phase (create users, login, create resource)
        4. Generate authorization scenarios
        5. Execute scenarios and yield result dicts

    Yields dicts with ``event`` keys:
        - ``{"event": "setup_start"}``
        - ``{"event": "setup_done", "success": bool, "steps": [...], "error": str | null}``
        - ``{"event": "result", ...StatefulTestResult fields}``
        - ``{"event": "done", "summary": {...}}``

    Args:
        spec:        Parsed OpenAPI spec dict.
        base_url:    Root URL of the API under test.
        http_client: Injected async HTTP client.
    """
    from .spec_analyzer import analyze_spec
    from .setup_orchestrator import run_setup_phase
    from .authz_generator import generate_authz_scenarios

    # ---------------------------------------------------------------
    # Phase 1: Analyze spec
    # ---------------------------------------------------------------
    spec_endpoints = analyze_spec(spec)

    # ---------------------------------------------------------------
    # Phase 2: Setup
    # ---------------------------------------------------------------
    ctx = TestContext(base_url=base_url, http_client=http_client)

    yield {"event": "setup_start"}

    setup_result = await run_setup_phase(ctx, spec_endpoints)

    yield {
        "event": "setup_done",
        **setup_result.to_dict(),
    }

    if not setup_result.success:
        yield {
            "event": "done",
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "critical": 0,
                "high": 0,
                "warning": 0,
                "info": 0,
                "setup_error": str(setup_result.error),
            },
        }
        return

    # ---------------------------------------------------------------
    # Phase 3: Generate scenarios
    # ---------------------------------------------------------------
    scenarios = generate_authz_scenarios(spec_endpoints.secured_endpoints, ctx)

    if not scenarios:
        yield {
            "event": "done",
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "critical": 0,
                "high": 0,
                "warning": 0,
                "info": 0,
                "note": "No secured endpoints found in spec",
            },
        }
        return

    # ---------------------------------------------------------------
    # Phase 4: Execute and yield results
    # ---------------------------------------------------------------
    results: list[StatefulTestResult] = []

    async for result in execute_scenarios(scenarios, ctx, spec_endpoints.login_path):
        results.append(result)
        yield {"event": "result", **result.to_dict()}

    # ---------------------------------------------------------------
    # Phase 5: Summary
    # ---------------------------------------------------------------
    severity_counts: dict[str, int] = {s.value: 0 for s in Severity}
    passed = sum(1 for r in results if r.classification.passed)
    for r in results:
        severity_counts[r.classification.severity.value] += 1

    yield {
        "event": "done",
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": len(results) - passed,
            **severity_counts,
        },
    }
