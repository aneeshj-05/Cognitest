"""
Unit tests for the stateful security testing engine.

These tests do NOT require a live server — the HTTP client is mocked.

Run with:
    cd /home/aneeshj/Downloads/Enmaz-Cognitest/backend
    python -m pytest tests/test_stateful_engine.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Override session fixtures from conftest.py that require a real DB.
# Our tests are pure unit tests — no database or HTTP server is needed.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_db():
    """Override conftest's autouse DB fixture – these tests don't need the DB."""
    yield


@pytest.fixture(scope="session")
def manage_db_connection():
    """Override conftest's session-scoped DB connection fixture."""
    yield


# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.modules.generator.engines.stateful.classifier import (
    ScenarioType,
    SecurityClassification,
    Severity,
    classify_result,
)
from src.modules.generator.engines.stateful.context import TestContext
from src.modules.generator.engines.stateful.spec_analyzer import SpecEndpoints, analyze_spec
from src.modules.generator.engines.stateful.authz_generator import (
    AuthzScenario,
    generate_authz_scenarios,
)
from src.modules.generator.engines.stateful.reporter import build_report, StatefulRunReport
from src.modules.generator.engines.stateful.setup_orchestrator import SetupResult
from src.modules.generator.engines.stateful.executor import StatefulTestResult
from src.modules.project.router import _evaluate_pass_fail


# ============================================================================
# Classifier tests
# ============================================================================


class TestClassifier:
    """Pure unit tests for classify_result – no I/O."""

    def test_scenario_a_correct_401(self):
        """Unauthenticated request returning 401 → INFO / passed."""
        result = classify_result(ScenarioType.UNAUTHENTICATED, 401)
        assert result.severity == Severity.INFO
        assert result.passed is True

    def test_scenario_a_200_is_critical(self):
        """Unauthenticated request returning 200 means no auth check → CRITICAL."""
        result = classify_result(ScenarioType.UNAUTHENTICATED, 200)
        assert result.severity == Severity.CRITICAL
        assert result.passed is False

    def test_scenario_b_correct_403(self):
        """Wrong-owner request returning 403 → INFO / passed."""
        result = classify_result(ScenarioType.WRONG_OWNER, 403)
        assert result.severity == Severity.INFO
        assert result.passed is True

    def test_scenario_b_200_is_authz_vulnerability(self):
        """Wrong-owner request returning 200 → CRITICAL authorization vulnerability."""
        result = classify_result(ScenarioType.WRONG_OWNER, 200)
        assert result.severity == Severity.CRITICAL
        assert result.passed is False
        assert "AUTHORIZATION VULNERABILITY" in result.label.upper() or "Vulnerability" in result.label

    def test_scenario_b_401_is_high(self):
        """Wrong-owner with valid token getting 401 → HIGH (middleware issue)."""
        result = classify_result(ScenarioType.WRONG_OWNER, 401)
        assert result.severity == Severity.HIGH
        assert result.passed is False

    def test_scenario_c_200_is_info(self):
        """Correct-owner request returning 200 → INFO / passed."""
        result = classify_result(ScenarioType.CORRECT_OWNER, 200)
        assert result.severity == Severity.INFO
        assert result.passed is True

    def test_scenario_c_204_is_info(self):
        """204 No Content is a valid success for correct-owner."""
        result = classify_result(ScenarioType.CORRECT_OWNER, 204)
        assert result.severity == Severity.INFO
        assert result.passed is True

    def test_scenario_c_403_is_warning(self):
        """Correct-owner getting 403 → over-restriction WARNING."""
        result = classify_result(ScenarioType.CORRECT_OWNER, 403)
        assert result.severity == Severity.WARNING
        assert result.passed is False

    def test_server_error_is_always_critical(self):
        """500 errors are CRITICAL regardless of scenario type."""
        for scenario in ScenarioType:
            result = classify_result(scenario, 500)
            assert result.severity == Severity.CRITICAL
            assert result.passed is False

    def test_503_is_also_critical(self):
        """503 is also a server error → CRITICAL."""
        result = classify_result(ScenarioType.UNAUTHENTICATED, 503)
        assert result.severity == Severity.CRITICAL

    def test_result_to_dict(self):
        """SecurityClassification.to_dict returns expected keys."""
        result = classify_result(ScenarioType.WRONG_OWNER, 403)
        d = result.to_dict()
        assert "label" in d
        assert "severity" in d
        assert "passed" in d


class TestSecurityPassFailEvaluator:
    """Regression tests for router security pass/fail rules."""

    def test_injection_200_is_failure_even_when_server_did_not_crash(self):
        case = {"name": "Injection attacks test", "owasp_category": "Injection"}
        assert _evaluate_pass_fail(400, 200, case) is False

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 415, 422])
    def test_injection_rejection_statuses_are_passes(self, status):
        case = {"name": "Injection attacks test", "owasp_category": "Injection"}
        assert _evaluate_pass_fail(400, status, case) is True

    @pytest.mark.parametrize("status", [500, 502, 503])
    def test_injection_server_errors_are_failures(self, status):
        case = {"name": "Injection attacks test", "owasp_category": "Injection"}
        assert _evaluate_pass_fail(400, status, case) is False


# ============================================================================
# TestContext tests
# ============================================================================


class TestContextIsolation:
    """Verify that TestContext instances are fully isolated."""

    def _make_ctx(self, base_url: str) -> TestContext:
        mock_client = MagicMock()
        return TestContext(base_url=base_url, http_client=mock_client)

    def test_two_contexts_do_not_share_state(self):
        ctx_a = self._make_ctx("http://api-a.test")
        ctx_b = self._make_ctx("http://api-b.test")

        ctx_a.token_a = "token-for-a"
        ctx_a.resource_ids["chirp"] = "chirp-001"

        assert ctx_b.token_a is None
        assert "chirp" not in ctx_b.resource_ids

    def test_auth_header_a_includes_bearer(self):
        ctx = self._make_ctx("http://api.test")
        ctx.token_a = "jwt.abc.def"
        header = ctx.auth_header_a()
        assert header == {"Authorization": "Bearer jwt.abc.def"}

    def test_auth_header_b_empty_without_token(self):
        ctx = self._make_ctx("http://api.test")
        assert ctx.auth_header_b() == {}

    def test_full_url_resolves_correctly(self):
        ctx = self._make_ctx("http://api.example.com/v1")
        assert ctx.full_url("/users") == "http://api.example.com/v1/users"
        assert ctx.full_url("users") == "http://api.example.com/v1/users"


# ============================================================================
# Spec Analyzer tests
# ============================================================================


class TestSpecAnalyzer:
    """Validate heuristic endpoint discovery from OpenAPI specs."""

    _SAMPLE_SPEC = {
        "openapi": "3.0.0",
        "info": {"title": "Test API", "version": "1.0"},
        "paths": {
            "/api/users": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "User created"}},
                }
            },
            "/api/login": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "email": {"type": "string"},
                                        "password": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Token returned"}},
                }
            },
            "/api/chirps": {
                "post": {
                    "security": [{"bearerAuth": []}],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"body": {"type": "string"}},
                                    "required": ["body"],
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "Chirp created"}},
                }
            },
            "/api/chirps/{chirpId}": {
                "get": {
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {"in": "path", "name": "chirpId", "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "Chirp returned"}},
                },
                "delete": {
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {"in": "path", "name": "chirpId", "schema": {"type": "string"}}
                    ],
                    "responses": {"204": {"description": "Deleted"}},
                },
            },
        },
    }

    def test_finds_login_endpoint(self):
        endpoints = analyze_spec(self._SAMPLE_SPEC)
        assert endpoints.login_path is not None
        assert "login" in endpoints.login_path.lower()

    def test_finds_user_create_endpoint(self):
        endpoints = analyze_spec(self._SAMPLE_SPEC)
        assert endpoints.user_create_path is not None
        assert "user" in endpoints.user_create_path.lower()

    def test_finds_secured_endpoints(self):
        endpoints = analyze_spec(self._SAMPLE_SPEC)
        assert len(endpoints.secured_endpoints) == 3  # POST chirps, GET chirpId, DELETE chirpId

    def test_finds_resource_endpoints(self):
        endpoints = analyze_spec(self._SAMPLE_SPEC)
        # Resource endpoints = POST + secured
        assert len(endpoints.resource_endpoints) == 1
        assert endpoints.resource_endpoints[0].method == "POST"


# ============================================================================
# AuthZ Generator tests
# ============================================================================


class TestAuthzGenerator:
    """Validate scenario generation for a secured endpoint."""

    def _make_ctx(self) -> TestContext:
        mock_client = MagicMock()
        ctx = TestContext(base_url="http://api.test", http_client=mock_client)
        ctx.token_a = "token-a"
        ctx.token_b = "token-b"
        ctx.resource_ids["chirps"] = "chirp-abc"
        return ctx

    def _make_endpoint(self):
        from src.modules.generator.engines.stateful.spec_analyzer import analyze_spec
        spec = {
            "paths": {
                "/api/chirps/{chirpId}": {
                    "get": {
                        "security": [{"bearerAuth": []}],
                        "parameters": [{"in": "path", "name": "chirpId"}],
                        "responses": {"200": {}},
                    }
                }
            }
        }
        return analyze_spec(spec).secured_endpoints

    def test_generates_exactly_3_scenarios_per_endpoint(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        # 1 endpoint × 3 scenarios
        assert len(scenarios) == 3

    def test_scenario_types_are_all_three(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        types = {s.scenario_type for s in scenarios}
        assert types == {
            ScenarioType.UNAUTHENTICATED,
            ScenarioType.WRONG_OWNER,
            ScenarioType.CORRECT_OWNER,
        }

    def test_unauthenticated_scenario_has_no_auth_header(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        unauth = next(s for s in scenarios if s.scenario_type == ScenarioType.UNAUTHENTICATED)
        assert "Authorization" not in unauth.headers

    def test_wrong_owner_uses_token_a(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        wrong = next(s for s in scenarios if s.scenario_type == ScenarioType.WRONG_OWNER)
        assert wrong.headers.get("Authorization") == "Bearer token-a"

    def test_correct_owner_uses_token_b(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        correct = next(s for s in scenarios if s.scenario_type == ScenarioType.CORRECT_OWNER)
        assert correct.headers.get("Authorization") == "Bearer token-b"

    def test_resource_id_substituted_in_path(self):
        ctx = self._make_ctx()
        endpoints = self._make_endpoint()
        scenarios = generate_authz_scenarios(endpoints, ctx)
        for s in scenarios:
            # {chirpId} should be replaced with "chirp-abc"
            assert "{" not in s.endpoint_path


# ============================================================================
# Reporter tests
# ============================================================================


class TestReporter:
    """Validate report aggregation logic."""

    def _make_result(self, scenario_type: ScenarioType, actual_status: int) -> StatefulTestResult:
        classification = classify_result(scenario_type, actual_status)
        return StatefulTestResult(
            scenario_id="test-id",
            endpoint_path="/api/chirps/1",
            method="GET",
            scenario_type=scenario_type,
            request_headers={},
            expected_status=401 if scenario_type == ScenarioType.UNAUTHENTICATED else 403,
            actual_status=actual_status,
            classification=classification,
            description="test",
        )

    def test_report_counts_match(self):
        setup = SetupResult(success=True, steps=[])
        results = [
            self._make_result(ScenarioType.UNAUTHENTICATED, 401),   # pass / INFO
            self._make_result(ScenarioType.WRONG_OWNER, 200),        # fail / CRITICAL
            self._make_result(ScenarioType.CORRECT_OWNER, 200),      # pass / INFO
        ]
        report = build_report(setup, results)
        assert report.total == 3
        assert report.passed == 2
        assert report.failed == 1
        assert report.severity.critical == 1
        assert report.severity.info == 2

    def test_vulnerabilities_only_contains_failures(self):
        setup = SetupResult(success=True, steps=[])
        results = [
            self._make_result(ScenarioType.UNAUTHENTICATED, 200),   # fail / CRITICAL
            self._make_result(ScenarioType.WRONG_OWNER, 403),        # pass / INFO
        ]
        report = build_report(setup, results)
        assert len(report.vulnerabilities) == 1
        assert report.vulnerabilities[0]["passed"] is False

    def test_report_to_dict_has_required_keys(self):
        setup = SetupResult(success=True, steps=[])
        report = build_report(setup, [])
        d = report.to_dict()
        assert "setup" in d
        assert "total" in d
        assert "severity_summary" in d
        assert "vulnerabilities" in d
        assert "all_results" in d
