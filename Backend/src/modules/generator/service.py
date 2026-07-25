"""
Generator service — orchestrator that resolves engines, manages flow,
and ties together generation → execution → result storage.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.config import prisma
from prisma import Json as PrismaJson

from .engines import (
    generate_functional_tests, generate_functional_tests_enhanced,
    generate_negative_tests,
    generate_security_tests,
    generate_fuzz_tests,
)
from .constants import SUPPORTED_TEST_TYPES


# ──────────────────────────────────────────────
# Fuzz pipeline logic moved to engines/fuzz/service.py
# ──────────────────────────────────────────────

# ---------------------------------------------------------------------------
# Engine registry — maps test type strings to generator functions
# ---------------------------------------------------------------------------

_ENGINE_REGISTRY: dict[str, Any] = {
    "Security": generate_security_tests,
    "Functional": generate_functional_tests,
    "Negative": generate_negative_tests,
    "Fuzz": generate_fuzz_tests,
}

_AI_ENGINE_REGISTRY: dict[str, Any] = {
    "Functional": generate_functional_tests_enhanced,
    "Fuzz": generate_fuzz_tests, # Fuzz now supports use_ai internally
}


def get_supported_types() -> list[str]:
    """Return the list of supported test generation types."""
    return SUPPORTED_TEST_TYPES


async def generate_tests(
    spec: dict[str, Any],
    test_type: str,
    use_ai: bool = False,
) -> list[dict[str, Any]]:
    """
    Generate test cases for the given spec and test type.

    Args:
        spec:      Parsed OpenAPI/Swagger specification dict.
        test_type: One of SUPPORTED_TEST_TYPES (e.g. "Security", "Functional").
        api_key:   LLM API key (for AI-powered engines; optional).

    Returns:
        List of test case dicts conforming to TestCaseOut schema.

    Raises:
        ValueError: If test_type is not in SUPPORTED_TEST_TYPES.
    """
    if test_type not in _ENGINE_REGISTRY:
        raise ValueError(
            f"Unsupported test type: '{test_type}'. "
            f"Supported types: {SUPPORTED_TEST_TYPES}"
        )

    if test_type == "Security":
        from .ai.generators.security_generator import generate_security_tests_ai
        tests, _tokens = await generate_security_tests_ai(spec)
        return tests

    import inspect
    
    if use_ai and test_type in _AI_ENGINE_REGISTRY:
        engine_fn = _AI_ENGINE_REGISTRY[test_type]
        if test_type == "Fuzz":
            # Fuzz engine returns a plan dict, but generate_tests expects a list
            plan = await engine_fn(spec, use_ai=True)
            return plan.get("annotated_tests", [])

        result = await engine_fn(spec)
        if isinstance(result, tuple):  # (tests, tokens)
            tests = result[0]
            import logging as _svc_log
            _svc_log.getLogger(__name__).info(
                "[Service] AI Functional returned %d test cases", len(tests))
            return tests
        return result


    engine_fn = _ENGINE_REGISTRY[test_type]
    
    if inspect.iscoroutinefunction(engine_fn):
        result = await engine_fn(spec)
    else:
        result = engine_fn(spec)
        
    if isinstance(result, dict) and "annotated_tests" in result:
        return result["annotated_tests"]
    return result
