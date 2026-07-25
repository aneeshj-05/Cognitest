import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from pathlib import Path
from typing import List, Optional
import bcrypt


def _resolve_env_file() -> str:
    """Find a .env file reliably even when the app is launched from another cwd.

    Priority:
    1) Current working directory
    2) Any parent directory of this settings module (covers repo layouts)
    3) Fallback to ".env" (pydantic-settings default behavior)
    """

    cwd_candidate = Path.cwd() / ".env"
    if cwd_candidate.is_file():
        return str(cwd_candidate)

    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.is_file():
            return str(candidate)

    return ".env"


_ENV_FILE = _resolve_env_file()

# ---------------------------------------------------------------------------
# Known-bad / placeholder values that must never reach production
# ---------------------------------------------------------------------------
# These are the old hardcoded defaults and their bcrypt hashes.
# If ENVIRONMENT=production and the configured values match any of these,
# the app will refuse to start.
_BLOCKED_EMAILS = frozenset({
    "super@gmail.com",
    "admin@cognitest.com",
    "superadmin@cognitest.com",
})

# Pre-compute the hash of the old default password so we can reject it.
# We store it as a constant rather than computing at import time to keep
# startup fast — this is a known fixed value.
_BLOCKED_PASSWORD_PLAINTEXT = "cognitest@123"


def _is_known_bad_hash(password_hash: str) -> bool:
    """Return True if the hash matches any blocked plaintext password."""
    try:
        return bcrypt.checkpw(
            _BLOCKED_PASSWORD_PLAINTEXT.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except Exception:
        return False


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
    )

    # Server Configuration
    port: int = 5000
    node_env: str = "development"
    frontend_url: str = "http://localhost:5173"

    # Database
    database_url: str

    # JWT Configuration
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_days: int = 7

    # CORS
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Proxy/Gateway
    target_service_url: str = "http://localhost:6000"

    # Explicit allowlist of hosts the gateway may proxy to.
    # Comma-separated. Defaults to localhost only.
    # Override via GATEWAY_ALLOWED_HOSTS env var for other co-located services.
    gateway_allowed_hosts: str = "localhost,127.0.0.1,::1"

    # Super Admin credentials — NO defaults, must be set via environment.
    # SUPER_ADMIN_EMAIL        → plain email address
    # SUPER_ADMIN_PASSWORD_HASH → bcrypt hash of the password (see .env.example for
    #                             how to generate: python -c "import bcrypt; print(bcrypt.hashpw(b'yourpw', bcrypt.gensalt()).decode())")
    super_admin_email: str
    super_admin_password_hash: str

    # LLM / AI Configuration
    llm_api_key: str = ""
    anthropic_api_key: str = ""

    # Redis (ARQ task queue)
    redis_url: str = "redis://localhost:6379"

    # Burst test safety cap — no burst test may exceed this regardless of what
    # a test case specifies. Keep low to protect target APIs from unintended DoS.
    max_burst_count: int = 10

    # SMTP Configuration
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""

    # ---------------------------------------------------------------------------
    # Production safety checks
    # ---------------------------------------------------------------------------

    @model_validator(mode="after")
    def _reject_insecure_defaults_in_production(self) -> "Settings":
        """
        In production (node_env == 'production'), refuse to start if:
        - SUPER_ADMIN_EMAIL is missing/empty or is a known placeholder
        - SUPER_ADMIN_PASSWORD_HASH is missing/empty or hashes a known-bad password
        """
        if self.node_env.lower() != "production":
            return self

        errors: list[str] = []

        # Check email
        if not self.super_admin_email or self.super_admin_email.lower() in _BLOCKED_EMAILS:
            errors.append(
                "SUPER_ADMIN_EMAIL is missing, empty, or uses a known placeholder value. "
                "Set a real admin email in your environment."
            )

        # Check password hash
        if not self.super_admin_password_hash:
            errors.append(
                "SUPER_ADMIN_PASSWORD_HASH is missing or empty. "
                "Generate one with: python -c \"import bcrypt; print(bcrypt.hashpw(b'yourpw', bcrypt.gensalt()).decode())\""
            )
        elif _is_known_bad_hash(self.super_admin_password_hash):
            errors.append(
                "SUPER_ADMIN_PASSWORD_HASH matches a known insecure default password. "
                "Generate a new hash for a strong unique password."
            )

        if errors:
            raise ValueError(
                "STARTUP BLOCKED — insecure super-admin configuration detected in production:\n"
                + "\n".join(f"  • {e}" for e in errors)
            )

        # ── Gateway SSRF check ─────────────────────────────────────────────
        # In production, warn loudly if TARGET_SERVICE_URL points outside localhost.
        # We never hard-block this (some deployments use sidecar containers) but
        # any non-localhost address must be intentional and explicitly allowlisted.
        try:
            from urllib.parse import urlparse
            import logging as _log
            _gw_logger = _log.getLogger(__name__)
            parsed = urlparse(self.target_service_url)
            host = (parsed.hostname or "").lower()
            _loopback = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
            if host not in _loopback:
                _gw_logger.warning(
                    "⚠  SECURITY WARNING: TARGET_SERVICE_URL (%s) points to a "
                    "non-localhost host (%s) in production. This proxy is accessible "
                    "to any authenticated user — ensure this is intentional and the "
                    "target is an explicitly allowlisted co-located service. "
                    "Set GATEWAY_ALLOWED_HOSTS to restrict which hosts are permitted.",
                    self.target_service_url, host,
                )
        except Exception:
            pass

        return self

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def gateway_allowed_hosts_list(self) -> List[str]:
        """Parsed list of hosts the gateway proxy is allowed to forward to."""
        return [h.strip().lower() for h in self.gateway_allowed_hosts.split(",") if h.strip()]


# Global settings instance
settings = Settings()

# Prisma (and some other tooling) expects DATABASE_URL to be present in the
# environment. Pydantic Settings reads from .env without exporting values into
# os.environ, so we bridge that here.
os.environ.setdefault("DATABASE_URL", settings.database_url)
os.environ.setdefault("JWT_SECRET", settings.jwt_secret)
