"""
Pytest configuration for negative test execution.

Provides session-scoped fixtures that handle the full authenticated
lifecycle for negative testing:

  1. Optionally connect to the database (Prisma) — only if the AUT needs OTP
  2. Create a unique test user (signup → [OTP verify if needed] → login)
  3. Capture the JWT token
  4. Share the authenticated session across all test functions
  5. Teardown: disconnect Prisma if connected

Usage in test files::

    async def test_something(auth_session, negative_test_client):
        headers = auth_session.auth_headers
        resp = await negative_test_client.get("/some/endpoint", headers=headers)
        assert resp.status_code == 200
"""
from __future__ import annotations

import logging
import os

import pytest
import httpx

from .core.session_manager import NegativeTestSessionManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment variable reference
# Set these in CI or your local .env before running negative tests:
#
#   NEGATIVE_TEST_BASE_URL        Base URL of the running backend
#                                 Default: http://localhost:5000
#   NEGATIVE_TEST_SPEC_PATH       URL path to the OpenAPI JSON spec
#                                 Default: tries /openapi.json, /docs/openapi.json, /swagger.json
#   NEGATIVE_TEST_STRICT          Set to "1" to hard-fail (not skip) on spec load failure
#                                 Default: 0 (skip)
#   NEGATIVE_TEST_BURST_COUNT     Number of requests in rate limit burst tests
#                                 Default: 30
#   NEGATIVE_TEST_MAX_METHODS_PER_PATH  Max unsupported methods tested per path
#                                       Default: 2
#   NEGATIVE_TEST_EMAIL_PREFIX    Email prefix for generated test users
#                                 Default: cognitest_
#   NEGATIVE_TEST_SKIP_DB         Set to "1" to skip Prisma DB connection entirely
#                                 Default: 0 (connect if needed for OTP)
# ---------------------------------------------------------------------------
_BASE_URL = os.environ.get("NEGATIVE_TEST_BASE_URL", "http://localhost:5000")
_SKIP_DB = os.environ.get("NEGATIVE_TEST_SKIP_DB", "0").strip() == "1"


# ---------------------------------------------------------------------------
# Session-scoped: Database connection (conditional)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def _prisma_connection():
    """
    Ensure Prisma is connected for the entire test session.

    The session manager needs DB access ONLY to read OTP codes.
    If NEGATIVE_TEST_SKIP_DB=1 is set, Prisma is not connected
    (the session manager will detect this and skip OTP automatically).
    """
    if _SKIP_DB:
        logger.info("[NegativeConftest] NEGATIVE_TEST_SKIP_DB=1 — skipping Prisma connection")
        yield None
        return

    try:
        from src.config import prisma

        if not prisma.is_connected():
            logger.info("[NegativeConftest] Connecting to Prisma")
            await prisma.connect()

        yield prisma

        if prisma.is_connected():
            logger.info("[NegativeConftest] Disconnecting Prisma")
            await prisma.disconnect()
    except Exception as exc:
        logger.warning(
            "[NegativeConftest] Prisma connection failed: %s — "
            "OTP verification will be unavailable. Non-OTP AUTs will still work.",
            exc,
        )
        yield None


# ---------------------------------------------------------------------------
# Session-scoped: Authenticated session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def auth_session(_prisma_connection):
    """
    Create and authenticate a test user for the entire session.

    Lifecycle:
      - Generate unique email (UUID-based)
      - POST /auth/signup → create user
      - Detect OTP requirement → verify if needed and possible
      - POST /auth/login → capture JWT
      - Yield the session manager (token, headers, user info)

    Retries up to 3 times with exponential backoff before aborting.
    """
    manager = NegativeTestSessionManager(base_url=_BASE_URL)

    max_retries = 3
    last_error = ""

    for attempt in range(1, max_retries + 1):
        async with httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=False,
            verify=False,
        ) as client:
            # Load the OpenAPI spec and pass it to the session manager
            spec = await _load_spec_for_session(client)
            if spec:
                manager.set_spec(spec)

            try:
                await manager.setup(client)
                break  # Success
            except RuntimeError as exc:
                last_error = str(exc)
                if attempt < max_retries:
                    import asyncio
                    delay = 2 ** attempt  # 2s, 4s
                    logger.warning(
                        "[NegativeConftest] Auth setup attempt %d/%d failed: %s — retrying in %ds",
                        attempt, max_retries, exc, delay,
                    )
                    # Reset manager for fresh attempt (new email/password)
                    manager = NegativeTestSessionManager(base_url=_BASE_URL)
                    if spec:
                        manager.set_spec(spec)
                    await asyncio.sleep(delay)
                else:
                    pytest.exit(
                        f"[NegativeConftest] Auth setup failed after {max_retries} attempts — "
                        f"last error: {last_error}",
                        returncode=1,
                    )

    if not manager.is_authenticated:
        pytest.exit(
            "[NegativeConftest] Session manager is not authenticated after setup",
            returncode=1,
        )

    logger.info(
        f"[NegativeConftest] Session ready — "
        f"email={manager.email}, user_id={manager.user_id}"
    )

    yield manager

    # Teardown: best-effort cleanup of seeded resources
    rc = getattr(manager, "resource_context", {}) or {}
    if rc:
        logger.info("[NegativeConftest] Cleaning up %d seeded resources", len(rc))
        async with httpx.AsyncClient(timeout=10.0, verify=False) as cleanup_client:
            for path, rid in rc.items():
                # Skip non-path keys (type-specific keys like "post_id")
                if not path.startswith("/"):
                    continue
                delete_url = f"{_BASE_URL.rstrip('/')}{path.rstrip('/')}/{rid}"
                try:
                    await cleanup_client.delete(
                        delete_url,
                        headers=manager.auth_headers,
                        timeout=5.0,
                    )
                    logger.debug("[NegativeConftest] Cleanup: DELETE %s", delete_url)
                except Exception:
                    pass  # Best-effort
    logger.info(f"[NegativeConftest] Session teardown for {manager.email} complete")


# ---------------------------------------------------------------------------
# Session-scoped: HTTP client with auth
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def negative_test_client(auth_session):
    """
    Provide an httpx.AsyncClient configured for negative testing.

    The client does NOT have the Authorization header set by default —
    the test runner injects auth per-case based on the test intent.
    """
    async with httpx.AsyncClient(
        base_url=_BASE_URL,
        timeout=10.0,
        follow_redirects=False,
        verify=False,
        headers={
            "User-Agent": "Cognitest-Negative-Tester",
        },
    ) as client:
        yield client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _load_spec_for_session(client: httpx.AsyncClient) -> dict | None:
    """Best-effort load of the OpenAPI spec for session setup."""
    base_url = _BASE_URL.rstrip("/")
    paths_to_try = [
        os.environ.get("NEGATIVE_TEST_SPEC_PATH"),
        "/openapi.json",
        "/docs/openapi.json",
        "/swagger.json",
    ]
    for path in paths_to_try:
        if not path:
            continue
        try:
            resp = await client.get(f"{base_url}{path}", timeout=10.0)
            if resp.status_code == 200:
                spec = resp.json()
                if "paths" in spec:
                    logger.info("[NegativeConftest] Loaded spec from %s for session setup", path)
                    return spec
        except Exception:
            continue
    logger.info("[NegativeConftest] Could not load spec for session setup (non-fatal)")
    return None
