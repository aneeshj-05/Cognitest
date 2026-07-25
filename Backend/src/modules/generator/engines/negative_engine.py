"""
Negative Testing Engine — orchestrator.

Generates comprehensive negative test cases from an OpenAPI/Swagger spec
by delegating to specialised sub-modules.

Categories covered:
  1. Missing required fields
  2. Wrong data types
  3. Boundary / edge-case values
  4. Malformed request bodies
  5. Invalid format values
  6. Invalid enum values
  7. Authentication failures
  8. Invalid headers & Content-Type
  9. Invalid query parameters
  10. Resource not found (fake IDs)
  11. Unsupported HTTP methods
  12. Rate limit / abuse probes
"""
from typing import Any
from ..spec_parser import extract_endpoints
from .negative import (
    generate_missing_field_tests,
    generate_invalid_type_tests,
    generate_boundary_tests,
    generate_malformed_body_tests,
    generate_invalid_format_tests,
    generate_invalid_method_tests,
    generate_invalid_enum_tests,
    generate_auth_failure_tests,
    generate_invalid_header_tests,
    generate_invalid_query_param_tests,
    generate_resource_not_found_tests,
    generate_rate_limit_tests,
)
from .negative.core import TokenMutator
from ..ai.generators.negative_generator import generate_negative_tests_ai

import logging
logger = logging.getLogger(__name__)


def _case_auth_type(case: dict[str, Any]) -> str:
    auth_type = str(case.get("auth_type") or "").strip().lower()
    if auth_type:
        return auth_type

    auth_marker = (
        str(case.get("sub_category") or case.get("subCategory") or "").upper() == "AUTH_FAILURE"
        or str(case.get("mutation_type") or "").upper() in {"AUTH_MISSING", "AUTH_INVALID"}
        or bool(case.get("auth_negative"))
    )
    if not auth_marker:
        return ""

    name = str(case.get("name") or "").lower()
    description = str(case.get("description") or "").lower()
    if "expired" in name or "expired" in description:
        return "expired"
    if "invalid" in name or "invalid" in description:
        return "invalid"
    return "missing"


def _set_header(headers: dict[str, Any], key: str, value: str | None) -> None:
    target = key.lower()
    for existing in list(headers.keys()):
        if str(existing).lower() == target:
            if value is None:
                headers.pop(existing, None)
            else:
                headers[existing] = value
            return
    if value is not None:
        headers[key] = value


def _apply_auth_type_policy(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    processed: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue

        auth_type = _case_auth_type(case)
        if auth_type:
            case["auth_type"] = auth_type
        request_headers = dict(case.get("request_headers") or case.get("headers") or {})
        headers = dict(case.get("headers") or request_headers)

        if auth_type == "missing":
            _set_header(request_headers, "Authorization", None)
            _set_header(headers, "Authorization", None)
        elif auth_type == "invalid":
            invalid_header = TokenMutator.malformed()["Authorization"]
            _set_header(request_headers, "Authorization", invalid_header)
            _set_header(headers, "Authorization", invalid_header)
        elif auth_type == "expired":
            expired_header = TokenMutator.expired()["Authorization"]
            _set_header(request_headers, "Authorization", expired_header)
            _set_header(headers, "Authorization", expired_header)

        if request_headers:
            case["request_headers"] = request_headers
        elif "request_headers" in case:
            case["request_headers"] = {}

        if headers:
            case["headers"] = headers
        elif "headers" in case:
            case["headers"] = {}

        processed.append(case)

    return processed


async def generate_negative_tests(spec: dict[str, Any], use_ai: bool = False) -> list[dict]:
    """
    Generate comprehensive negative tests based on OpenAPI spec analysis.

    Args:
        spec: OpenAPI/Swagger specification dictionary

    Returns:
        List of test case dictionaries conforming to TestCaseOut schema
    """
    all_tests: list[dict] = []

    # Parse spec to extract endpoints
    endpoints = extract_endpoints(spec)
    for endpoint in endpoints:
        try:
            setattr(endpoint, "spec", spec)
        except Exception:
            pass

    # Generate tests for each endpoint
    for endpoint in endpoints:
        # 1. Missing required fields
        all_tests.extend(generate_missing_field_tests(endpoint, spec=spec))

        # 2. Wrong data types
        all_tests.extend(generate_invalid_type_tests(endpoint, spec=spec))

        # 3. Boundary / edge-case values
        all_tests.extend(generate_boundary_tests(endpoint, spec=spec))

        # 4. Malformed request bodies
        all_tests.extend(generate_malformed_body_tests(endpoint))

        # 5. Invalid format values (email, date-time, uuid, etc.)
        all_tests.extend(generate_invalid_format_tests(endpoint, spec=spec))

        # 6. Invalid enum values
        all_tests.extend(generate_invalid_enum_tests(endpoint, spec=spec))

        # 7. Authentication failures (missing/invalid/expired tokens)
        all_tests.extend(generate_auth_failure_tests(endpoint))

        # 8. Invalid headers & Content-Type
        all_tests.extend(generate_invalid_header_tests(endpoint, spec=spec))

        # 9. Invalid query parameters
        all_tests.extend(generate_invalid_query_param_tests(endpoint, spec=spec))

        # 10. Resource not found (fake IDs in path params)
        all_tests.extend(generate_resource_not_found_tests(endpoint))

    # 11. Unsupported HTTP methods (spec-level)
    all_tests.extend(generate_invalid_method_tests(spec, endpoints))

    # 12. Rate limit / abuse probes (spec-level)
    all_tests.extend(generate_rate_limit_tests(endpoints, spec=spec))

    all_rules = _apply_auth_type_policy(all_tests)

    if use_ai:
        try:
            ai_cases, tokens = await generate_negative_tests_ai(spec, rule_based_cases=all_rules)
            all_rules.extend(ai_cases)
            logger.info("Integrated %d AI negative cases", len(ai_cases))
        except Exception as e:
            logger.error("AI Negative enhancement failed: %s", e)

    return all_rules
