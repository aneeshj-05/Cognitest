"""
Unit tests for super-admin authentication security hardening.

Covers:
  (a) Settings refuse to load in production when SUPER_ADMIN_* vars are
      missing, empty, or match known insecure defaults.
  (b) Login with correct email but wrong password is rejected.
  (c) Login with the old hardcoded plaintext default password is rejected
      even when it happens to be configured in the environment.
  (d) Login with correct email + correct hashed password succeeds.
"""
from __future__ import annotations

import os
import bcrypt
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hash(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


OLD_DEFAULT_EMAIL    = "super@gmail.com"
OLD_DEFAULT_PASSWORD = "cognitest@123"
SAFE_EMAIL           = "admin@mycompany.com"
SAFE_PASSWORD        = "Str0ng!UniqueP@ssw0rd"
SAFE_HASH            = _make_hash(SAFE_PASSWORD)


# ---------------------------------------------------------------------------
# (a) Settings validation in production
# ---------------------------------------------------------------------------

class TestSettingsProductionValidation:
    """Settings must reject insecure super-admin config in production mode."""

    def _load_settings(self, env_overrides: dict):
        """Instantiate Settings with specific env vars, ignoring the real .env file."""
        from src.config.settings import Settings
        from pydantic_settings import SettingsConfigDict

        base = {
            "DATABASE_URL":              "postgresql://x:x@localhost/x",
            "JWT_SECRET":                "test-secret",
            "NODE_ENV":                  "production",
            "SUPER_ADMIN_EMAIL":         SAFE_EMAIL,
            "SUPER_ADMIN_PASSWORD_HASH": SAFE_HASH,
        }
        base.update(env_overrides)

        # Patch os.environ so pydantic-settings picks them up, and disable
        # .env file reading by pointing model_config at a non-existent file.
        with patch.dict(os.environ, base, clear=True):
            # Subclass to override env-file path so the real .env isn't read
            class _TestSettings(Settings):
                model_config = SettingsConfigDict(
                    env_file=None,
                    case_sensitive=False,
                    extra="ignore",
                    populate_by_name=True,
                )
            return _TestSettings()

    def test_missing_email_raises_in_production(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            self._load_settings({"SUPER_ADMIN_EMAIL": ""})

    def test_placeholder_email_raises_in_production(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            self._load_settings({"SUPER_ADMIN_EMAIL": "super@gmail.com"})

    def test_another_blocked_email_raises_in_production(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            self._load_settings({"SUPER_ADMIN_EMAIL": "admin@cognitest.com"})

    def test_missing_hash_raises_in_production(self):
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            self._load_settings({"SUPER_ADMIN_PASSWORD_HASH": ""})

    def test_known_bad_hash_raises_in_production(self):
        """Hash of the old default password 'cognitest@123' must be rejected."""
        from pydantic import ValidationError
        bad_hash = _make_hash(OLD_DEFAULT_PASSWORD)
        with pytest.raises((ValidationError, ValueError)):
            self._load_settings({
                "SUPER_ADMIN_EMAIL":         SAFE_EMAIL,
                "SUPER_ADMIN_PASSWORD_HASH": bad_hash,
            })

    def test_valid_config_passes_in_production(self):
        """Well-configured production settings must load without error."""
        settings = self._load_settings({
            "SUPER_ADMIN_EMAIL":         SAFE_EMAIL,
            "SUPER_ADMIN_PASSWORD_HASH": SAFE_HASH,
            "NODE_ENV":                  "production",
        })
        assert settings.super_admin_email == SAFE_EMAIL

    def test_insecure_defaults_allowed_in_development(self):
        """Dev mode must NOT block placeholder values (devs need to iterate quickly)."""
        settings = self._load_settings({
            "SUPER_ADMIN_EMAIL":         OLD_DEFAULT_EMAIL,
            "SUPER_ADMIN_PASSWORD_HASH": _make_hash(OLD_DEFAULT_PASSWORD),
            "NODE_ENV":                  "development",
        })
        assert settings.super_admin_email == OLD_DEFAULT_EMAIL


# ---------------------------------------------------------------------------
# (b) & (c) & (d)  Login endpoint security
# ---------------------------------------------------------------------------

class TestSuperAdminLogin:
    """HTTP-level login tests using the FastAPI test client."""

    @pytest.mark.asyncio
    async def test_wrong_password_rejected(self, client: AsyncClient):
        """Correct email, wrong password → 400 Invalid credentials."""
        response = await client.post("/api/v1/auth/login", json={
            "email":    OLD_DEFAULT_EMAIL,
            "passcode": "definitelyWrong!999",
        })
        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_old_plaintext_default_rejected(self, client: AsyncClient):
        """
        The old hardcoded plaintext password 'cognitest@123' must be rejected
        when the configured hash does NOT correspond to it.
        We temporarily swap the hash to one for a different password, then
        confirm the old default plaintext is rejected.
        """
        from src.config.settings import settings

        # Temporarily set hash to a DIFFERENT password so old default fails
        different_password = "TotallyDifferentPw!99"
        settings.super_admin_password_hash = _make_hash(different_password)
        original_email = settings.super_admin_email

        try:
            response = await client.post("/api/v1/auth/login", json={
                "email":    original_email,
                "passcode": OLD_DEFAULT_PASSWORD,   # the old hardcoded default
            })
            assert response.status_code in (400, 401), (
                f"Expected 400/401 but got {response.status_code} — "
                "old default password should not work against a different hash"
            )
        finally:
            # Restore the original hash (re-hash from the known dev default)
            settings.super_admin_password_hash = _make_hash(OLD_DEFAULT_PASSWORD)

    @pytest.mark.asyncio
    async def test_correct_credentials_succeed(self, client: AsyncClient):
        """
        Login with the configured SUPER_ADMIN_EMAIL and correct password
        must return a valid SUPER_ADMIN JWT.
        """
        from src.config.settings import settings

        # Patch settings to use a known safe password for this test
        test_password = "TestSuperAdminPw!42"
        test_hash     = _make_hash(test_password)
        test_email    = "sa_test@cognitest-internal.com"

        original_email = settings.super_admin_email
        original_hash  = settings.super_admin_password_hash

        # Temporarily replace settings values
        settings.super_admin_email         = test_email
        settings.super_admin_password_hash = test_hash

        try:
            response = await client.post("/api/v1/auth/login", json={
                "email":    test_email,
                "passcode": test_password,
            })
            assert response.status_code == 200, response.text
            data = response.json()
            assert "token" in data
            assert data["user"]["systemRole"] == "SUPER_ADMIN"
            assert data["user"]["email"] == test_email
        finally:
            # Always restore original settings regardless of test outcome
            settings.super_admin_email         = original_email
            settings.super_admin_password_hash = original_hash

    @pytest.mark.asyncio
    async def test_wrong_email_falls_through_to_normal_auth(self, client: AsyncClient):
        """An unknown email (not the super-admin email) returns Invalid credentials."""
        response = await client.post("/api/v1/auth/login", json={
            "email":    "notanadmin@example.com",
            "passcode": "whatever",
        })
        assert response.status_code == 400
        assert "Invalid credentials" in response.json()["detail"]
