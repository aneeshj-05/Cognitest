import pytest

from src.modules.generator.ai.generators import security_generator as sg
from src.modules.project.generate import generate_test_payload_async


def _spec() -> dict:
    return {
        "openapi": "3.0.0",
        "info": {"title": "Security AI Test API", "version": "1.0.0"},
        "security": [{"bearerAuth": []}],
        "paths": {
            "/items/{id}": {
                "get": {
                    "parameters": [
                        {"name": "id", "in": "path", "required": True, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "OK"}, "403": {"description": "Forbidden"}},
                }
            },
            "/webhooks": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "callbackUrl": {"type": "string", "format": "uri"},
                                        "name": {"type": "string"},
                                    },
                                    "required": ["callbackUrl"],
                                }
                            }
                        }
                    },
                    "responses": {"201": {"description": "Created"}, "400": {"description": "Bad request"}},
                }
            },
            "/admin/users": {
                "get": {
                    "responses": {"200": {"description": "OK"}, "403": {"description": "Forbidden"}},
                }
            },
        },
    }


class FakeAIClient:
    is_available = True

    async def generate_json(self, *, prompt: str, system: str, max_tokens: int, temperature: float):
        if system == sg.GLOBAL_SECURITY_PLANNER_SYSTEM:
            return {
                "data": [
                    {
                        "operation_key": "GET /items/{id}",
                        "coverage_items": [{"owasp_id": "API1:2023", "min_tests": 1, "rationale": "object id"}],
                    },
                    {
                        "operation_key": "POST /webhooks",
                        "coverage_items": [{"owasp_id": "API7:2023", "min_tests": 1, "rationale": "callback URL"}],
                    },
                    {
                        "operation_key": "GET /admin/users",
                        "coverage_items": [{"owasp_id": "API5:2023", "min_tests": 1, "rationale": "admin path"}],
                    },
                ],
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }

        if '"path":"/items/{id}"' in prompt:
            data = [
                {
                    "name": "BOLA foreign item access",
                    "test_type": "Security",
                    "category": "SECURITY",
                    "owasp_id": "API1:2023",
                    "owasp_category": "API1:2023",
                    "endpoint_path": "/items/123",
                    "method": "GET",
                    "expected_status": 403,
                    "path_params": {"id": "123"},
                    "assertions": ["reject foreign object"],
                },
                {
                    "name": "BOLA foreign item access",
                    "test_type": "Security",
                    "category": "SECURITY",
                    "owasp_id": "API1:2023",
                    "owasp_category": "API1:2023",
                    "endpoint_path": "/items/{id}",
                    "method": "GET",
                    "expected_status": 403,
                    "path_params": {"id": "507f1f77bcf86cd799439011"},
                    "assertions": ["reject foreign object"],
                    "requires_stateful": True,
                },
            ]
        elif '"path":"/webhooks"' in prompt:
            data = [
                {
                    "name": "SSRF callback URL",
                    "test_type": "Security",
                    "category": "SECURITY",
                    "owasp_id": "API7:2023",
                    "owasp_category": "API7:2023",
                    "endpoint_path": "/webhooks",
                    "method": "POST",
                    "expected_status": 400,
                    "request_body": {"callbackUrl": "http://169.254.169.254/latest/meta-data", "name": "probe"},
                    "assertions": ["reject internal URL"],
                }
            ]
        else:
            data = [
                {
                    "name": "Regular user cannot list admin users",
                    "test_type": "Security",
                    "category": "SECURITY",
                    "owasp_id": "API5:2023",
                    "owasp_category": "API5:2023",
                    "endpoint_path": "/admin/users",
                    "method": "GET",
                    "expected_status": 403,
                    "assertions": ["reject regular user"],
                    "requires_stateful": True,
                }
            ]

        return {"data": data, "usage": {"input_tokens": 5, "output_tokens": 15}}


@pytest.mark.asyncio
async def test_ai_security_generator_is_per_endpoint_and_strict(monkeypatch):
    monkeypatch.setattr(sg, "ai_client", FakeAIClient())

    cases, tokens = await sg.generate_security_tests_ai(_spec())

    assert tokens > 0
    assert {(c["method"], c["endpoint_path"]) for c in cases} == {
        ("GET", "/items/{id}"),
        ("POST", "/webhooks"),
        ("GET", "/admin/users"),
    }
    assert all(c["test_type"] == "Security" for c in cases)
    assert all(c["owasp_category"].startswith("API") for c in cases)
    assert "/items/123" not in {c["endpoint_path"] for c in cases}

    bola = next(c for c in cases if c["endpoint_path"] == "/items/{id}")
    assert bola["path_params"] == {"id": "507f1f77bcf86cd799439011"}
    assert bola["requires_stateful"] is True


@pytest.mark.asyncio
async def test_ai_security_generator_fails_when_ai_unavailable(monkeypatch):
    class UnavailableAI:
        is_available = False

    monkeypatch.setattr(sg, "ai_client", UnavailableAI())

    with pytest.raises(sg.SecurityAIGenerationError, match="ANTHROPIC_API_KEY"):
        await sg.generate_security_tests_ai(_spec())


@pytest.mark.asyncio
async def test_ai_security_generator_requires_every_endpoint(monkeypatch):
    class HallucinatingAI(FakeAIClient):
        async def generate_json(self, *, prompt: str, system: str, max_tokens: int, temperature: float):
            result = await super().generate_json(
                prompt=prompt,
                system=system,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            if system != sg.GLOBAL_SECURITY_PLANNER_SYSTEM and '"path":"/webhooks"' in prompt:
                result["data"] = [
                    {
                        "name": "wrong endpoint",
                        "owasp_id": "API7:2023",
                        "endpoint_path": "/not-in-spec",
                        "method": "POST",
                    }
                ]
            return result

    monkeypatch.setattr(sg, "ai_client", HallucinatingAI())

    with pytest.raises(sg.SecurityAIGenerationError, match="POST /webhooks"):
        await sg.generate_security_tests_ai(_spec())


@pytest.mark.asyncio
async def test_global_planner_retries_missing_endpoints_one_by_one(monkeypatch):
    class MissingThenSingleAI:
        is_available = True

        async def generate_json(self, *, prompt: str, system: str, max_tokens: int, temperature: float):
            if '"operation_key":"POST /missing"' in prompt and '"operation_key":"GET /ok"' not in prompt:
                data = [
                    {
                        "operation_key": "POST /missing",
                        "coverage_items": [{"owasp_id": "API3:2023", "min_tests": 1}],
                    }
                ]
            else:
                data = [
                    {
                        "operation_key": "GET /ok",
                        "coverage_items": [{"owasp_id": "API2:2023", "min_tests": 1}],
                    }
                ]
            return {"data": data, "usage": {"input_tokens": 1, "output_tokens": 1}}

    monkeypatch.setattr(sg, "ai_client", MissingThenSingleAI())
    monkeypatch.setattr(sg, "_MAX_RETRIES", 1)

    descriptors = [
        {"operation_key": "GET /ok", "path": "/ok", "method": "GET"},
        {"operation_key": "POST /missing", "path": "/missing", "method": "POST"},
    ]

    plan, tokens = await sg._call_global_planner(descriptors, "Retry API")

    assert tokens > 0
    assert set(plan) == {"GET /ok", "POST /missing"}


@pytest.mark.asyncio
async def test_global_planner_fails_fast_on_low_credit(monkeypatch):
    class LowCreditAI:
        is_available = True
        calls = 0

        async def generate_json(self, *, prompt: str, system: str, max_tokens: int, temperature: float):
            self.calls += 1
            raise RuntimeError(
                "Anthropic API call failed for claude-sonnet-4-6: "
                '{"type":"error","error":{"type":"invalid_request_error",'
                '"message":"Your credit balance is too low to access the Anthropic API."}}'
            )

    ai = LowCreditAI()
    monkeypatch.setattr(sg, "ai_client", ai)

    descriptors = [
        {"operation_key": "GET /ok", "path": "/ok", "method": "GET"},
        {"operation_key": "POST /order", "path": "/order", "method": "POST"},
    ]

    with pytest.raises(sg.SecurityAIGenerationError, match="cannot continue"):
        await sg._call_global_planner(descriptors, "Billing API")

    assert ai.calls == 1


@pytest.mark.asyncio
async def test_project_security_generation_does_not_call_rule_engine(monkeypatch):
    async def fail_rule_engine(*args, **kwargs):
        raise AssertionError("rule-based security generator should not be called")

    async def fake_ai_generator(spec, rule_based_cases=None):
        assert rule_based_cases is None
        return [
            {
                "id": "security-ai-case",
                "name": "AI auth test",
                "test_type": "Security",
                "category": "SECURITY",
                "owasp_category": "API2:2023",
                "endpoint_path": "/items/{id}",
                "method": "GET",
                "expected_status": 401,
                "auth_negative": True,
            }
        ], 123

    monkeypatch.setattr("src.modules.project.generate.generate_security_tests", fail_rule_engine)
    monkeypatch.setattr(
        "src.modules.generator.ai.generators.security_generator.generate_security_tests_ai",
        fake_ai_generator,
    )

    cases, method, tokens = await generate_test_payload_async(
        _spec(),
        "Security",
        use_ai=False,
    )

    assert method == "ai_enhanced"
    assert tokens == 123
    assert cases[0]["auth_type"] == "missing"
