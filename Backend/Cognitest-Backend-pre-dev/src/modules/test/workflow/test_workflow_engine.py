"""
Pytest unit tests for the multi-step workflow chaining engine.

Tests are pure unit tests — no live HTTP, no database.
HTTP calls are mocked using unittest.mock.AsyncMock on httpx.AsyncClient.request.

Run with:
    .venv/bin/pytest tests/test_workflow_engine.py -v
"""
from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import sys
from pathlib import Path

# Ensure src/ is importable regardless of where pytest is invoked from
_backend_root = Path(__file__).parent.parent.parent  # tests/workflow/ -> tests/ -> Backend/
sys.path.insert(0, str(_backend_root / "src"))

from src.modules.generator.engines.functional.variable_resolver import resolve_variables
from src.modules.generator.engines.functional.workflow import (
    WorkflowState,
    WorkflowStep,
)
from src.modules.generator.engines.functional.workflow_executor import WorkflowExecutor
from src.modules.generator.spec_parser import extract_endpoints


# ---------------------------------------------------------------------------
# Sample spec — simulates a full order placement API
# ---------------------------------------------------------------------------

ORDER_SPEC: dict[str, Any] = {
    "openapi": "3.0.0",
    "info": {"title": "Order API", "version": "1.0.0"},
    "paths": {
        "/auth/register": {
            "post": {
                "summary": "Register user",
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
                "responses": {"201": {}},
            }
        },
        "/auth/login": {
            "post": {
                "summary": "Login",
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
                "responses": {"200": {}},
            }
        },
        "/cart": {
            "post": {
                "summary": "Add to cart",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "productId": {"type": "string"},
                                    "quantity": {"type": "integer"},
                                },
                            }
                        }
                    }
                },
                "responses": {"201": {}},
            }
        },
        "/checkout": {
            "post": {
                "summary": "Checkout",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {"cartId": {"type": "string"}},
                            }
                        }
                    }
                },
                "responses": {"201": {}},
            }
        },
        "/payment": {
            "post": {
                "summary": "Pay",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "orderId": {"type": "string"},
                                    "amount": {"type": "number"},
                                },
                            }
                        }
                    }
                },
                "responses": {"200": {}},
            }
        },
        "/orders/{id}": {
            "get": {
                "summary": "Get order",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {}},
            }
        },
        "/products": {
            "post": {
                "summary": "Create product",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "price": {"type": "number"},
                                },
                            }
                        }
                    }
                },
                "responses": {"201": {}},
            }
        },
        "/products/{id}": {
            "get": {
                "summary": "Get product",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"200": {}},
            },
            "put": {
                "summary": "Update product",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "price": {"type": "number"},
                                },
                            }
                        }
                    }
                },
                "responses": {"200": {}},
            },
            "delete": {
                "summary": "Delete product",
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                ],
                "responses": {"204": {}},
            },
        },
    },
}


# ---------------------------------------------------------------------------
# Tests: variable_resolver.extract_variables
# ---------------------------------------------------------------------------

class TestExtractVariables:

    def test_simple_field(self):
        body = {"data": {"token": "abc123"}}
        result = extract_variables(body, {"token": "$.data.token"})
        assert result == {"token": "abc123"}

    def test_nested_path(self):
        body = {"data": {"user": {"id": "u-99", "name": "Alice"}}}
        result = extract_variables(body, {"userId": "$.data.user.id"})
        assert result == {"userId": "u-99"}

    def test_array_index(self):
        body = {"items": [{"id": "item-1"}, {"id": "item-2"}]}
        result = extract_variables(body, {"firstItemId": "$.items[0].id"})
        assert result == {"firstItemId": "item-1"}

    def test_missing_path_returns_empty(self):
        body = {"data": {"name": "Alice"}}
        result = extract_variables(body, {"token": "$.data.token"})
        assert "token" not in result

    def test_empty_rules(self):
        body = {"data": {"token": "abc"}}
        assert extract_variables(body, {}) == {}

    def test_none_body(self):
        assert extract_variables(None, {"token": "$.token"}) == {}

    def test_multiple_variables(self):
        body = {"data": {"id": "u-1", "token": "tok-xyz", "role": "admin"}}
        result = extract_variables(body, {
            "userId": "$.data.id",
            "token": "$.data.token",
            "role": "$.data.role",
        })
        assert result == {"userId": "u-1", "token": "tok-xyz", "role": "admin"}

    def test_non_jsonpath_rules_ignored(self):
        body = {"token": "abc"}
        result = extract_variables(body, {"tok": "token"})  # no "$." prefix
        assert "tok" not in result


# ---------------------------------------------------------------------------
# Tests: variable_resolver.resolve_placeholders
# ---------------------------------------------------------------------------

class TestResolvePlaceholders:

    def test_simple_string(self):
        result = resolve_placeholders("Bearer {{token}}", {"token": "abc123"})
        assert result == "Bearer abc123"

    def test_dict_values(self):
        template = {"Authorization": "Bearer {{auth_token}}", "X-User": "{{userId}}"}
        ctx = {"auth_token": "tok1", "userId": "u-42"}
        result = resolve_placeholders(template, ctx)
        assert result == {"Authorization": "Bearer tok1", "X-User": "u-42"}

    def test_list_items(self):
        template = ["{{a}}", "{{b}}", "literal"]
        ctx = {"a": "1", "b": "2"}
        result = resolve_placeholders(template, ctx)
        assert result == ["1", "2", "literal"]

    def test_unknown_placeholder_left_intact(self):
        result = resolve_placeholders("Hello {{unknown}}", {"other": "val"})
        assert result == "Hello {{unknown}}"

    def test_nested_dict(self):
        template = {"outer": {"inner": "{{val}}"}}
        result = resolve_placeholders(template, {"val": "resolved"})
        assert result["outer"]["inner"] == "resolved"

    def test_non_string_types_passed_through(self):
        assert resolve_placeholders(42, {"x": "y"}) == 42
        assert resolve_placeholders(None, {"x": "y"}) is None
        assert resolve_placeholders(True, {"x": "y"}) is True

    def test_empty_context(self):
        result = resolve_placeholders("{{token}}", {})
        assert result == "{{token}}"


# ---------------------------------------------------------------------------
# Tests: get_unresolved_placeholders
# ---------------------------------------------------------------------------

class TestGetUnresolved:

    def test_single_unresolved(self):
        assert "foo" in get_unresolved_placeholders("{{foo}}")

    def test_resolved_after_substitution(self):
        resolved = resolve_placeholders("{{token}}", {"token": "abc"})
        assert get_unresolved_placeholders(resolved) == []

    def test_nested_dict(self):
        template = {"a": "{{x}}", "b": {"c": "{{y}}"}}
        unresolved = get_unresolved_placeholders(template)
        assert set(unresolved) == {"x", "y"}


# ---------------------------------------------------------------------------
# Tests: generate_workflow_tests (structure validation)
# ---------------------------------------------------------------------------

class TestGenerateWorkflowTests:

    def test_returns_list_of_dicts(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        assert isinstance(tests, list)
        assert len(tests) > 0

    def test_each_test_has_required_fields(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        for t in tests:
            assert "id" in t
            assert "name" in t
            assert "steps" in t
            assert "test_type" in t
            assert t["test_type"] == "Functional"
            assert "category" in t
            assert t["category"] == "workflow"
            assert "endpoint_path" in t
            assert "method" in t
            assert "expected_status" in t

    def test_steps_are_populated(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        for t in tests:
            steps = t["steps"]
            assert len(steps) >= 2, f"{t['name']} has fewer than 2 steps"
            for step in steps:
                assert "method" in step
                assert "endpoint_path" in step
                assert "expected_status" in step

    def test_auth_workflow_detected(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        auth_workflows = [t for t in tests if "Login" in t["name"] or "Register" in t["name"]]
        assert len(auth_workflows) >= 1, "Expected at least one auth workflow"

    def test_auth_workflow_has_token_extraction(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        auth_wf = next((t for t in tests if "Login" in t["name"] or "Register" in t["name"]), None)
        assert auth_wf is not None
        # Login step should extract auth_token
        login_step = next(
            (s for s in auth_wf["steps"] if "login" in s["endpoint_path"].lower() or
             "Login" in s.get("name", "")),
            None
        )
        assert login_step is not None
        assert "auth_token" in login_step.get("extract", {}), \
            "Login step should extract auth_token"

    def test_placeholder_in_subsequent_steps(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        for wf in tests:
            steps = wf["steps"]
            # If a step has a depends_on, the previous step must have matching extract key
            for i, step in enumerate(steps):
                for dep in step.get("depends_on", []):
                    # The variable should be extractable from one of the prior steps
                    prior_extracts = set()
                    for prev in steps[:i]:
                        prior_extracts.update(prev.get("extract", {}).keys())
                    assert dep in prior_extracts, (
                        f"Step '{step['name']}' depends on '{dep}' but no prior step extracts it. "
                        f"Prior extracts: {prior_extracts}"
                    )

    def test_order_flow_state_machine(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        order_wfs = [t for t in tests if "Order" in t["name"] or "Cart" in t["name"]]
        if order_wfs:
            wf = order_wfs[0]
            sm = wf.get("state_machine", [])
            assert len(sm) > 0, "Order workflow should have state machine labels"

    def test_create_read_workflow_2_steps(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        create_read = [t for t in tests if "Create → Read" in t["name"]]
        assert len(create_read) >= 1
        for wf in create_read:
            assert len(wf["steps"]) == 2
            assert wf["steps"][0]["method"] == "POST"
            assert wf["steps"][1]["method"] == "GET"

    def test_create_update_read_workflow_3_steps(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        update_wfs = [t for t in tests if "Update" in t["name"]]
        if update_wfs:
            wf = update_wfs[0]
            assert len(wf["steps"]) == 3
            assert wf["steps"][2]["method"] == "GET"

    def test_create_delete_read_workflow_3_steps(self):
        endpoints = extract_endpoints(ORDER_SPEC)
        tests = generate_workflow_tests(endpoints)
        delete_wfs = [t for t in tests if "Delete" in t["name"] and "404" in t["name"]]
        if delete_wfs:
            wf = delete_wfs[0]
            assert len(wf["steps"]) == 3
            assert wf["steps"][2]["expected_status"] == 404


# ---------------------------------------------------------------------------
# Tests: WorkflowExecutor
# ---------------------------------------------------------------------------

def _make_response(status: int, body: dict) -> MagicMock:
    """Build a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status
    resp.text = json.dumps(body)
    resp.headers = {"content-type": "application/json"}
    resp.json = MagicMock(return_value=body)
    return resp


def _make_workflow(steps: list[dict]) -> dict:
    """Build a minimal workflow dict."""
    return {
        "id": "wf-test",
        "name": "Test Workflow",
        "test_type": "Functional",
        "category": "workflow",
        "steps": steps,
        "state_machine": [],
        "endpoint_path": steps[0]["endpoint_path"] if steps else "/",
        "method": steps[0]["method"] if steps else "GET",
        "expected_status": steps[0]["expected_status"] if steps else 200,
    }


class TestWorkflowExecutor:

    @pytest.mark.asyncio
    async def test_single_step_pass(self):
        workflow = _make_workflow([{
            "step_id": "s1",
            "name": "Create",
            "method": "POST",
            "endpoint_path": "/api/users",
            "expected_status": 201,
            "request_body": {"name": "Alice"},
            "extract": {"userId": "$.data.id"},
            "depends_on": [],
        }])
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=_make_response(201, {"data": {"id": "u-123"}}))

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is True
        assert result.final_context.get("userId") == "u-123"
        assert len(result.step_results) == 1
        assert result.step_results[0].passed is True

    @pytest.mark.asyncio
    async def test_variable_propagation_between_steps(self):
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Create",
                "method": "POST",
                "endpoint_path": "/api/items",
                "expected_status": 201,
                "request_body": {"name": "Test"},
                "extract": {"itemId": "$.data.id"},
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "name": "Read",
                "method": "GET",
                "endpoint_path": "/api/items/{id}",
                "expected_status": 200,
                "path_params": {"id": "{{itemId}}"},
                "depends_on": ["itemId"],
                "extract": {},
            },
        ])
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            _make_response(201, {"data": {"id": "item-42"}}),
            _make_response(200, {"data": {"id": "item-42", "name": "Test"}}),
        ])

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is True
        assert len(result.step_results) == 2
        # Second call URL must contain the resolved item ID
        second_call = mock_client.request.call_args_list[1]
        assert "item-42" in second_call[0][1]  # URL arg

    @pytest.mark.asyncio
    async def test_rollback_on_step_failure(self):
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Create",
                "method": "POST",
                "endpoint_path": "/api/orders",
                "expected_status": 201,
                "extract": {"orderId": "$.data.id"},
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "name": "Payment",
                "method": "POST",
                "endpoint_path": "/api/payment",
                "expected_status": 200,
                "request_body": {"orderId": "{{orderId}}", "amount": 99},
                "depends_on": ["orderId"],
                "extract": {},
            },
            {
                "step_id": "s3",
                "name": "Verify Order",
                "method": "GET",
                "endpoint_path": "/api/orders/{{orderId}}",
                "expected_status": 200,
                "depends_on": ["orderId"],
                "extract": {"finalStatus": "$.data.status"},
            },
        ])
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            _make_response(201, {"data": {"id": "order-99"}}),
            _make_response(402, {"error": "Payment declined"}),  # step 2 fails
        ])

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is False
        assert result.rollback_triggered is True
        assert "Payment" in result.rollback_reason

        # Step 3 should be marked as skipped
        step3 = result.step_results[2]
        assert step3.skipped is True
        assert step3.passed is False

    @pytest.mark.asyncio
    async def test_payment_failure_keeps_state_pending(self):
        """Regression: if payment fails, final_state should NOT advance to CONFIRMED."""
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Checkout",
                "method": "POST",
                "endpoint_path": "/checkout",
                "expected_status": 201,
                "extract": {"order_id": "$.data.orderId"},
                "expected_state": "CHECKOUT",
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "name": "Payment",
                "method": "POST",
                "endpoint_path": "/payment",
                "expected_status": 200,
                "request_body": {"orderId": "{{order_id}}", "amount": 50},
                "depends_on": ["order_id"],
                "extract": {},
                "expected_state": "PAYMENT_PENDING",
            },
        ])
        workflow["state_machine"] = ["CHECKOUT", "PAYMENT_PENDING", "CONFIRMED"]

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            _make_response(201, {"data": {"orderId": "ord-1"}}),
            _make_response(500, {"error": "Gateway timeout"}),  # payment fails
        ])

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is False
        # final_state must stay at CHECKOUT (not advance to PAYMENT_PENDING or CONFIRMED)
        assert result.final_state == "CHECKOUT"
        assert result.rollback_triggered is True

    @pytest.mark.asyncio
    async def test_happy_path_state_progression(self):
        """Payment success → order becomes CONFIRMED."""
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Checkout",
                "method": "POST",
                "endpoint_path": "/checkout",
                "expected_status": 201,
                "extract": {"order_id": "$.data.orderId"},
                "expected_state": "CHECKOUT",
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "name": "Payment",
                "method": "POST",
                "endpoint_path": "/payment",
                "expected_status": 200,
                "request_body": {"orderId": "{{order_id}}", "amount": 50},
                "depends_on": ["order_id"],
                "extract": {},
                "expected_state": "PAYMENT_PENDING",
            },
            {
                "step_id": "s3",
                "name": "Verify",
                "method": "GET",
                "endpoint_path": "/orders/{{order_id}}",
                "expected_status": 200,
                "depends_on": ["order_id"],
                "extract": {"finalStatus": "$.data.status"},
                "expected_state": "CONFIRMED",
            },
        ])
        workflow["state_machine"] = ["CHECKOUT", "PAYMENT_PENDING", "CONFIRMED"]

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            _make_response(201, {"data": {"orderId": "ord-2"}}),
            _make_response(200, {"data": {"status": "CONFIRMED"}}),
            _make_response(200, {"data": {"status": "CONFIRMED"}}),
        ])

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is True
        assert result.final_state == "CONFIRMED"
        assert result.rollback_triggered is False
        assert all(s.passed for s in result.step_results)

    @pytest.mark.asyncio
    async def test_missing_dependency_skips_step(self):
        """If a required variable is not in context, step is skipped."""
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Get item",
                "method": "GET",
                "endpoint_path": "/items/{{itemId}}",
                "expected_status": 200,
                "depends_on": ["itemId"],  # never populated
                "extract": {},
            },
        ])

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=_make_response(200, {}))

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is False
        assert result.step_results[0].skipped is True
        # Should NOT have made an HTTP call
        mock_client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_connection_error_triggers_rollback(self):
        workflow = _make_workflow([
            {
                "step_id": "s1",
                "name": "Create",
                "method": "POST",
                "endpoint_path": "/api/items",
                "expected_status": 201,
                "extract": {"itemId": "$.data.id"},
                "depends_on": [],
            },
            {
                "step_id": "s2",
                "name": "Read",
                "method": "GET",
                "endpoint_path": "/api/items/1",
                "expected_status": 200,
                "depends_on": [],
                "extract": {},
            },
        ])

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=[
            Exception("Connection refused"),
        ])

        result = await WorkflowExecutor().run(workflow, "http://localhost:3000", mock_client)

        assert result.passed is False
        assert result.rollback_triggered is True
        assert result.step_results[1].skipped is True
