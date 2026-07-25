# tests/workflow/conftest.py
# Isolated conftest for workflow engine tests — no Prisma, no DB, no network.
# We override the parent conftest.py autouse fixtures with no-ops so the
# session-scoped Prisma event loop does not interfere with the per-test asyncio
# loop used by pytest-asyncio.
import pytest


@pytest.fixture(scope="session", autouse=True)
def manage_db_connection():
    """No-op override — workflow tests don't need a DB connection."""
    yield


@pytest.fixture(autouse=True)
def setup_db():
    """No-op override — workflow tests are pure unit tests."""
    yield
