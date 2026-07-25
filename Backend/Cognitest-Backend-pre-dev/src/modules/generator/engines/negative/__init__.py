"""
Negative test generators package.

Includes:
  - Test-case generators (one per sub-category)
  - Core execution context and session management
  - Dynamic test runner (OpenAPI-driven)
"""
from .missing_fields import generate_missing_field_tests
from .invalid_types import generate_invalid_type_tests
from .boundary_values import generate_boundary_tests
from .malformed_body import generate_malformed_body_tests
from .invalid_format import generate_invalid_format_tests
from .invalid_methods import generate_invalid_method_tests
from .invalid_enum import generate_invalid_enum_tests
from .auth_failures import generate_auth_failure_tests
from .invalid_headers import generate_invalid_header_tests
from .invalid_query_params import generate_invalid_query_param_tests
from .resource_not_found import generate_resource_not_found_tests
from .rate_limit import generate_rate_limit_tests
from .stateful_sequences import (
    generate_duplicate_tests,
    generate_create_then_delete_then_get_tests,
    generate_create_then_get_tests,
    generate_create_duplicate_tests,
    generate_stateful_sequence_tests,
)
from .sequence_lifecycle import SequenceType, LIFECYCLE_RULES

# Core execution context (new architecture)
from .core import (
    NegativeTestSessionManager,
    ExecutionContext,
    TestIntent,
    build_auth_context,
    build_headers,
    classify_intent,
    safe_merge_headers,
)

# Legacy exports (backward compatibility)
from .core import (
    build_auth_headers,
    inject_auth,
    is_public_route,
    prepare_request_headers,
)

__all__ = [
    # Generators
    "generate_missing_field_tests",
    "generate_invalid_type_tests",
    "generate_boundary_tests",
    "generate_malformed_body_tests",
    "generate_invalid_format_tests",
    "generate_invalid_method_tests",
    "generate_invalid_enum_tests",
    "generate_auth_failure_tests",
    "generate_invalid_header_tests",
    "generate_invalid_query_param_tests",
    "generate_resource_not_found_tests",
    "generate_rate_limit_tests",
    "generate_create_then_get_tests",
    "generate_create_then_delete_then_get_tests",
    "generate_create_duplicate_tests",
    "generate_duplicate_tests",
    "generate_stateful_sequence_tests",
    "SequenceType",
    "LIFECYCLE_RULES",
    # Execution context
    "NegativeTestSessionManager",
    "ExecutionContext",
    "TestIntent",
    "build_auth_context",
    "build_headers",
    "classify_intent",
    "safe_merge_headers",
    # Legacy
    "build_auth_headers",
    "inject_auth",
    "is_public_route",
    "prepare_request_headers",
]
