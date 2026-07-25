"""
Execution Context — Production-grade intelligence layer for negative test execution.

This module is the brain of the negative testing engine. It provides:

  - ``TestIntent``      — classifies test behavior
  - ``ExecutionContext`` — wraps endpoint + session for runtime decisions
  - ``classify_intent``  — maps sub_category → intent with context awareness
  - ``build_headers``    — central header builder (no token leakage)
  - ``build_auth_context`` — builds masked auth info for UI rendering
  - ``TokenMutator``     — generates broken tokens for auth tests

Generators are **pure mutation engines** — they produce test data.
This module provides the execution intelligence.
"""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.modules.generator.engines.negative.core.session_manager import NegativeTestSessionManager
    from src.modules.generator.spec_parser import Endpoint


# ---------------------------------------------------------------------------
# Test Intent Classification
# ---------------------------------------------------------------------------

class TestIntent(Enum):
    """Classify the execution intent of a negative test case."""

    AUTH_FAILURE = "auth_failure"
    """Authentication boundary: missing/invalid/expired tokens. NEVER inject session token."""

    VALIDATION = "validation"
    """Input validation on protected endpoints: inject session token."""

    PROTOCOL = "protocol"
    """Protocol-level tests: wrong headers, content-types. No token injection."""

    DISCOVERY = "discovery"
    """API discovery: unsupported methods, rate-limit probing. No token injection."""


# Map sub_category → TestIntent (priority order matters)
_INTENT_MAP: dict[str, TestIntent] = {
    # AUTH — highest priority, NEVER receives session token
    "AUTH_FAILURE": TestIntent.AUTH_FAILURE,
    # DISCOVERY — spec-level / behavioral probes
    "UNSUPPORTED_METHOD": TestIntent.DISCOVERY,
    "RATE_LIMIT": TestIntent.DISCOVERY,
    # PROTOCOL — header / content-type misconfiguration
    "INVALID_HEADERS": TestIntent.PROTOCOL,
    # Everything else falls through to context-based classification
}


def classify_intent(case: dict, context: "ExecutionContext") -> TestIntent:
    """
    Classify the execution intent of a test case.

    Priority:
      1. AUTH_FAILURE sub_category → always AUTH_FAILURE (highest priority)
      2. UNSUPPORTED_METHOD / RATE_LIMIT → DISCOVERY
      3. Endpoint requires auth → VALIDATION (token will be injected)
      4. Default → PROTOCOL (no token)

    Args:
        case: A negative test case dict from any generator.
        context: The ExecutionContext with endpoint + session info.

    Returns:
        The classified TestIntent.
    """
    sub_cat = case.get("sub_category", "")

    # Direct mapping takes priority
    mapped = _INTENT_MAP.get(sub_cat)
    if mapped is not None:
        return mapped

    # Context-based: if endpoint requires auth → VALIDATION (inject token)
    if context.requires_auth():
        return TestIntent.VALIDATION

    # Default: PROTOCOL (no auth)
    return TestIntent.PROTOCOL


# ---------------------------------------------------------------------------
# Token Mutator — generates broken tokens for auth tests
# ---------------------------------------------------------------------------

class TokenMutator:
    """
    Generate intentionally broken JWT tokens for auth failure tests.

    Used ONLY by AUTH-intent cases. The session's real token is
    never passed to these tests.
    """

    @staticmethod
    def missing() -> dict[str, str]:
        """No Authorization header at all."""
        return {}

    @staticmethod
    def corrupt(token: str) -> dict[str, str]:
        """Corrupt the last character of a real token."""
        if token:
            corrupted = token[:-1] + ("X" if not token.endswith("X") else "Y")
        else:
            corrupted = "invalid-token-xyz"
        return {"Authorization": f"Bearer {corrupted}"}

    @staticmethod
    def expired() -> dict[str, str]:
        """A structurally valid but expired JWT."""
        expired_jwt = (
            "eyJhbGciOiJIUzI1NiJ9"
            ".eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ"
            ".INVALID_SIGNATURE_XYZ"
        )
        return {"Authorization": f"Bearer {expired_jwt}"}

    @staticmethod
    def malformed() -> dict[str, str]:
        """A clearly non-JWT string."""
        return {"Authorization": "Bearer invalid-token-xyz"}


# ---------------------------------------------------------------------------
# Execution Context
# ---------------------------------------------------------------------------

class ExecutionContext:
    """
    Runtime context for executing a negative test case.

    Wraps the target endpoint metadata and the current auth session,
    providing a clean interface for the runner to query auth state
    without generators needing auth awareness.
    """

    def __init__(
        self,
        endpoint: "Endpoint",
        session: "NegativeTestSessionManager",
    ) -> None:
        self.endpoint = endpoint
        self.session = session

    def requires_auth(self) -> bool:
        """Whether the target endpoint requires authentication."""
        return bool(self.endpoint.requires_auth)

    def get_auth_headers(self) -> dict[str, str]:
        """Build Authorization headers from the session token."""
        if not self.requires_auth() or not self.session.token:
            return {}
        return {"Authorization": f"Bearer {self.session.token}"}

    @property
    def token(self) -> str | None:
        """The raw session token."""
        return self.session.token

    @property
    def user_id(self) -> str | None:
        """The session user ID."""
        return self.session.user_id


# ---------------------------------------------------------------------------
# Central Header Builder
# ---------------------------------------------------------------------------

def build_headers(
    case: dict,
    context: ExecutionContext,
    intent: TestIntent,
) -> dict[str, str]:
    headers = {}
    auth_type = str(case.get("auth_type") or "").strip().lower()

    # AUTH FAILURE → only custom headers
    if intent == TestIntent.AUTH_FAILURE:
        if auth_type == "missing" or not auth_type:
            return case.get("custom_headers", {}) or {}
        if auth_type == "invalid":
            return {"Authorization": TokenMutator.malformed()["Authorization"]}
        if auth_type == "expired":
            return {"Authorization": TokenMutator.expired()["Authorization"]}
        return case.get("custom_headers", {}) or {}

    # Inject token ONLY if endpoint requires auth
    if auth_type == "missing":
        pass
    elif auth_type == "invalid":
        headers["Authorization"] = TokenMutator.malformed()["Authorization"]
    elif auth_type == "expired":
        headers["Authorization"] = TokenMutator.expired()["Authorization"]
    elif context.requires_auth() and context.session.token:
        headers["Authorization"] = f"Bearer {context.session.token}"

    # Content-Type handling
    force_ct = case.get("force_content_type")

    if force_ct == "__OMIT__":
        pass
    elif force_ct:
        headers["Content-Type"] = force_ct
    else:
        headers["Content-Type"] = "application/json"

    # Default User Agent
    headers["User-Agent"] = "Cognitest-Negative-Tester"

    # Apply custom header overrides last
    custom = case.get("custom_headers")
    if custom and intent != TestIntent.AUTH_FAILURE:
        headers.update(custom)

    return headers


# ---------------------------------------------------------------------------
# Safe Header Merge (for httpx client)
# ---------------------------------------------------------------------------

def safe_merge_headers(
    client_headers: Any,
    request_headers: dict[str, str],
    intent: TestIntent,
) -> dict[str, str]:
    merged_headers = {
        k: v for k, v in dict(client_headers or {}).items()
        if k.lower() != "authorization"
    }

    merged_headers.update(request_headers)

    return merged_headers


# ---------------------------------------------------------------------------
# Auth Context Builder (for result payloads / UI)
# ---------------------------------------------------------------------------

def mask_token(token: str | None) -> str | None:
    """Mask a JWT token for safe display: first 20 chars + '...'."""
    if not token:
        return None
    return token[:20] + "..." if len(token) > 20 else token


def build_auth_context(
    context: ExecutionContext,
    intent: TestIntent,
) -> dict[str, Any]:
    """
    Build the auth_context dict for a test result.

    The frontend uses this to render the SESSION AUTH CONTEXT panel.

    Args:
        context: The ExecutionContext.
        intent: The classified test intent.

    Returns:
        Dict with token_acquired, masked token, user_id, intent, display_message.
    """
    # AUTH tests explicitly DON'T get session context
    if intent == TestIntent.AUTH_FAILURE:
        return {
            "token": None,
            "user_id": None,
            "token_acquired": False,
            "intent": intent.value,
            "display_message": "Auth bypassed — testing authentication boundary",
        }

    should_show = context.requires_auth() and bool(context.token)
    return {
        "token": context.token if should_show else None,
        "user_id": context.user_id if should_show else None,
        "token_acquired": should_show,
        "intent": intent.value,
        "display_message": (
            "Token injected for protected endpoint"
            if should_show
            else "Public endpoint — no auth required"
        ),
    }
