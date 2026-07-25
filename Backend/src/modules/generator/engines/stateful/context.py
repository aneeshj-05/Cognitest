"""
TestContext – shared state container for a single stateful security run.

All mutable state lives here; no global variables are used anywhere in the
stateful engine.  The HTTP client is injected so callers control its lifetime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class TestContext:
    """
    Persists all session state across the setup, execution, and reporting
    phases of a stateful security run.

    Attributes:
        base_url:     Root URL of the API-under-test (e.g. "http://localhost:3000").
        http_client:  Injected async HTTP client – caller is responsible for
                      opening/closing it.
        user_a_id:    ID of the first test user created during setup.
        user_b_id:    ID of the second test user created during setup.
        token_a:      JWT returned after logging in as user A.
        token_b:      JWT returned after logging in as user B.
        creds_a:      Login credentials for user A (for token refresh).
        creds_b:      Login credentials for user B (for token refresh).
        resource_ids: Map of resource-type → created resource ID, e.g.
                      {"chirp": "abc-123"}.
        metadata:     Arbitrary key-value bag for extra context data.
    """

    base_url: str
    http_client: httpx.AsyncClient

    # Populated during setup phase
    user_a_id: str | None = None
    user_b_id: str | None = None
    token_a: str | None = None
    token_b: str | None = None
    creds_a: dict[str, str] = field(default_factory=dict)
    creds_b: dict[str, str] = field(default_factory=dict)
    resource_ids: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def auth_header_a(self) -> dict[str, str]:
        """Return the Authorization header for user A, or {} if not logged in."""
        if self.token_a:
            return {"Authorization": f"Bearer {self.token_a}"}
        return {}

    def auth_header_b(self) -> dict[str, str]:
        """Return the Authorization header for user B, or {} if not logged in."""
        if self.token_b:
            return {"Authorization": f"Bearer {self.token_b}"}
        return {}

    def full_url(self, path: str) -> str:
        """Resolve an API path against base_url."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
