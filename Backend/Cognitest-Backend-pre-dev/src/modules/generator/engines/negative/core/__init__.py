"""
Core utilities for negative test execution.

Provides:
  - NegativeTestSessionManager: Full auth lifecycle (signup → verify → login)
  - ExecutionContext: Runtime intelligence for auth injection
  - build_headers / classify_intent / build_auth_context: Execution helpers
  - Legacy auth_helper: Deprecated, kept for backward compatibility
"""
from .session_manager import NegativeTestSessionManager
from .execution_context import (
    ExecutionContext,
    TestIntent,
    TokenMutator,
    build_auth_context,
    build_headers,
    classify_intent,
    safe_merge_headers,
    mask_token,
)

# Legacy exports (deprecated — use execution_context instead)
from .auth_helper import (
    build_auth_headers,
    inject_auth,
    is_public_route,
    prepare_request_headers,
)

__all__ = [
    # Session
    "NegativeTestSessionManager",
    # Execution context (new)
    "ExecutionContext",
    "TestIntent",
    "TokenMutator",
    "build_auth_context",
    "build_headers",
    "classify_intent",
    "safe_merge_headers",
    "mask_token",
    # Legacy (deprecated)
    "build_auth_headers",
    "inject_auth",
    "is_public_route",
    "prepare_request_headers",
]
