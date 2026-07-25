import pytest
from src.modules.project.service import (
    contract_allowed_status,
    substitute_path_params,
    extract_contract_meta
)

def test_contract_allowed_status():
    # Positive tests
    assert contract_allowed_status("200,201", 200, "positive") is True
    assert contract_allowed_status("200,201", 201, "positive") is True
    assert contract_allowed_status("200,201", 400, "positive") is False
    
    # Negative tests
    assert contract_allowed_status("200", 400, "negative") is True
    assert contract_allowed_status("200", 404, "negative") is True
    assert contract_allowed_status("200", 200, "negative") is False
    
    # Negative auth missing
    assert contract_allowed_status("200", 401, "negative_auth_missing") is True
    assert contract_allowed_status("200", 403, "negative_auth_missing") is True
    assert contract_allowed_status("200", 404, "negative_auth_missing") is False
    
    # 2xx shorthand
    assert contract_allowed_status("2xx", 200, "positive") is True
    assert contract_allowed_status("2xx", 204, "positive") is True
    assert contract_allowed_status("2xx", 404, "positive") is False

def test_substitute_path_params():
    assert substitute_path_params("/users/{id}", {"id": 123}) == "/users/123"
    assert substitute_path_params("/users/{id}/profile", {"id": "abc"}) == "/users/abc/profile"
    # Fallback for remaining braces
    assert substitute_path_params("/users/{id}/{other}", {"id": 123}) == "/users/123/{{other}}"

def test_extract_contract_meta():
    case = {
        "expected_statuses": [200, 201],
        "kind": "positive",
        "assertions": ["__contract_meta__={\"security_required\": true}"]
    }
    meta = extract_contract_meta(case)
    assert meta["expected_statuses"] == [200, 201]
    assert meta["kind"] == "positive"
    assert meta["security_required"] is True

from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_generate_functional_tests_ai_classification_and_tokens():
    class MockEndpoint:
        def __init__(self, path, method, requires_auth=False):
            self.path = path
            self.method = method
            self.requires_auth = requires_auth
            self.path_params = []
            self.query_params = []
            self.status_codes = [200]
            self.body_schema = None
            self.response_schema = None

    mock_ep = MockEndpoint("/test-endpoint", "GET")
    
    mock_ai_response = {
        "data": [
            {
                "name": "Should return 200",
                "method": "GET",
                "endpoint_path": "/test-endpoint",
                "expected_status": 200,
                "description": "Checks 200",
            }
        ],
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50
        }
    }

    # Patch the AI client in the generator module
    with patch("src.modules.generator.ai.generators.functional_generator_ai.ai_client") as mock_ai_client:
        mock_ai_client.is_available = True
        mock_ai_client.generate_json = AsyncMock(return_value=mock_ai_response)
        mock_ai_client.execute_batch_with_retry = AsyncMock(return_value=({"func-0": mock_ai_response}, mock_ai_response["usage"]))
        
        from src.modules.generator.ai.generators.functional_generator_ai import generate_functional_tests_enhanced
        
        spec = {"info": {"title": "Test API"}}
        cases, tokens, *_ = await generate_functional_tests_enhanced(
            spec=spec,
            endpoints=[mock_ep],
            admin_config=None
        )
        
        # Verify tokens sum up correctly (100 + 50 = 150)
        assert tokens == 150
        
        # Verify generation_source is correctly annotated as "AI"
        assert len(cases) == 1
        assert cases[0]["generation_source"] == "AI"
        assert cases[0]["method"] == "GET"
        assert cases[0]["endpoint_path"] == "/test-endpoint"

@pytest.mark.asyncio
async def test_generate_negative_tests_ai_classification_and_tokens():
    class MockEndpoint:
        def __init__(self, path, method, requires_auth=False):
            self.path = path
            self.method = method
            self.requires_auth = requires_auth
            self.path_params = []
            self.query_params = []
            self.status_codes = [200]
            self.body_schema = None
            self.response_schema = None

    mock_ep = MockEndpoint("/test-endpoint", "GET")
    
    mock_ai_response = {
        "data": [
            {
                "name": "Negative Test 1",
                "method": "GET",
                "endpoint_path": "/test-endpoint",
                "expected_status": 422,
                "description": "Checks 422",
            }
        ],
        "usage": {
            "input_tokens": 80,
            "output_tokens": 40
        }
    }

    with patch("src.modules.generator.ai.generators.negative_generator.ai_client") as mock_ai_client:
        mock_ai_client.is_available = True
        mock_ai_client.generate_json = AsyncMock(return_value=mock_ai_response)
        mock_ai_client.execute_batch_with_retry = AsyncMock(return_value=({"neg-0": mock_ai_response}, mock_ai_response["usage"]))
        
        with patch("src.modules.generator.ai.generators.negative_generator.extract_endpoints", return_value=[mock_ep]):
            from src.modules.generator.ai.generators.negative_generator import generate_negative_tests_ai
            
            spec = {"info": {"title": "Test API"}, "paths": {"/test-endpoint": {"get": {}}}}
            cases, tokens, *_ = await generate_negative_tests_ai(spec)
            
            assert tokens == 120
            assert len(cases) == 1
            assert cases[0]["generation_source"] == "AI"

@pytest.mark.asyncio
async def test_generate_security_tests_ai_classification_and_tokens():
    class MockEndpoint:
        def __init__(self, path, method, requires_auth=False):
            self.path = path
            self.method = method
            self.requires_auth = requires_auth
            self.path_params = []
            self.query_params = []
            self.status_codes = [200]
            self.body_schema = None
            self.response_schema = None

    mock_ep = MockEndpoint("/test-endpoint", "GET")
    
    mock_plan_response = {
        "data": [
            {
                "operation_key": "GET /test-endpoint",
                "coverage_items": [
                    {"owasp_category": "API2:2023", "min_tests": 1}
                ]
            }
        ],
        "usage": {"input_tokens": 50, "output_tokens": 50}
    }
    
    mock_op_response = {
        "data": [
            {
                "name": "Security Test 1",
                "method": "GET",
                "endpoint_path": "/test-endpoint",
                "owasp_category": "API2:2023",
                "expected_status": 401,
                "description": "Checks Auth",
            }
        ],
        "usage": {"input_tokens": 100, "output_tokens": 50}
    }

    with patch("src.modules.generator.ai.generators.security_generator.ai_client") as mock_ai_client:
        mock_ai_client.is_available = True
        mock_ai_client.generate_json = AsyncMock(return_value=mock_plan_response)
        mock_ai_client.execute_batch_with_retry = AsyncMock(return_value=({"sec-0": mock_op_response}, mock_op_response["usage"]))
        
        with patch("src.modules.generator.ai.generators.security_generator.extract_endpoints", return_value=[mock_ep]):
            from src.modules.generator.ai.generators.security_generator import generate_security_tests_ai
            
            spec = {"info": {"title": "Test API"}, "paths": {"/test-endpoint": {"get": {}}}}
            cases, tokens = await generate_security_tests_ai(spec)
            
            # total tokens = planner (50+50) + op generator (100+50) = 250
            assert tokens == 250
            assert len(cases) == 1
            assert cases[0]["generation_source"] == "AI"

@pytest.mark.asyncio
async def test_generate_fuzz_tests_ai_classification_and_tokens():
    class MockEndpoint:
        def __init__(self, path, method, requires_auth=False):
            self.path = path
            self.method = method
            self.requires_auth = requires_auth
            self.path_params = []
            self.query_params = []
            self.status_codes = [200]
            self.body_schema = None
            self.response_schema = None

    mock_ep = MockEndpoint("/test-endpoint", "GET")
    
    mock_ai_response = {
        "data": [
            {
                "name": "Fuzz Test 1",
                "method": "GET",
                "endpoint_path": "/test-endpoint",
                "expected_status": 400,
                "description": "Checks Fuzz",
            }
        ],
        "usage": {
            "input_tokens": 200,
            "output_tokens": 100
        }
    }

    with patch("src.modules.generator.ai.generators.fuzz_generator_ai.ai_client") as mock_ai_client:
        mock_ai_client.is_available = True
        mock_ai_client.generate_json = AsyncMock(return_value=mock_ai_response)
        mock_ai_client.execute_batch_with_retry = AsyncMock(return_value=({"fuzz-0": mock_ai_response}, mock_ai_response["usage"]))
        
        with patch("src.modules.generator.ai.generators.fuzz_generator_ai.extract_endpoints", return_value=[mock_ep]):
            from src.modules.generator.ai.generators.fuzz_generator_ai import generate_fuzz_tests_ai
            
            spec = {"info": {"title": "Test API"}, "paths": {"/test-endpoint": {"get": {}}}}
            cases, tokens, *_ = await generate_fuzz_tests_ai(spec)
            
            assert tokens == 300
            assert len(cases) == 1
            assert cases[0]["generation_source"] == "AI"

@pytest.mark.asyncio
async def test_generate_test_payload_async_fallback_and_tagging():
    from src.modules.project.generate import generate_test_payload_async
    
    spec = {"info": {"title": "Test API"}, "paths": {"/test-endpoint": {"get": {}}}}
    
    # 1. Test fallback when use_ai is True but AI generator raises exception
    with patch("src.modules.project.generate.generate_functional_tests_enhanced", side_effect=RuntimeError("AI Failed")):
        with patch("src.modules.generator.engines.functional_engine.generate_functional_tests", return_value=[{"name": "Rule Test", "method": "GET", "endpoint_path": "/test-endpoint", "expected_status": 200}]):
            cases, method, tokens, *_ = await generate_test_payload_async(spec, "Functional", use_ai=True)
            assert tokens == 0
            assert method == "rule_based"
            assert len(cases) == 1
            assert cases[0]["generation_source"] == "RULE"

    # 2. Test fallback for Negative generator when AI fails
    with patch("src.modules.generator.ai.generators.negative_generator.generate_negative_tests_ai", side_effect=RuntimeError("AI Failed")):
        with patch("src.modules.project.generate.generate_negative_tests", return_value=[{"name": "Rule Neg Test", "method": "GET", "endpoint_path": "/test-endpoint", "expected_status": 400}]):
            cases, method, tokens, *_ = await generate_test_payload_async(spec, "Negative", use_ai=True)
            assert tokens == 0
            assert method == "rule_based"
            assert len(cases) == 1
            assert cases[0]["generation_source"] == "RULE"

    # 3. Test annotation is "AI" when AI succeeds (use_ai=True)
    with patch("src.modules.project.generate.generate_functional_tests_enhanced", return_value=([{"name": "AI Test", "method": "GET", "endpoint_path": "/test-endpoint", "expected_status": 200}], 500)):
        cases, method, tokens, *_ = await generate_test_payload_async(spec, "Functional", use_ai=True)
        assert tokens == 500
        assert method == "ai_enhanced"
        assert len(cases) == 1
        assert cases[0]["generation_source"] == "AI"

