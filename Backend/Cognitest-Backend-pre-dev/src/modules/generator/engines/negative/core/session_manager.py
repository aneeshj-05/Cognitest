"""
core/session_manager.py — NegativeTestSessionManager

Manages the full auth lifecycle for a negative test session:
  1. Signup (POST /auth/signup)
  2. OTP detection — probe login to see if verification is required
  3. If OTP required AND DB accessible: read OTP + verify
  4. If OTP required but NO DB: raise clear error (user must provide manual token)
  5. Login (POST /auth/login) → capture JWT
  6. Resource seeding — create real resources after login so that
     path-param endpoints get valid IDs instead of 404s

The setup flow is now adaptive:
  - Non-OTP AUT: signup → login → seed (OTP step skipped automatically)
  - OTP AUT with DB:  signup → OTP verify → login → seed
  - OTP AUT without DB: clear error telling user to use manual token
"""
from __future__ import annotations

import base64
import json as _json
import logging
import os
import re
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = os.environ.get("NEGATIVE_TEST_BASE_URL", "http://localhost:5000")


class NegativeTestSessionManager:
    """
    Handles user creation, authentication, and resource seeding for
    a negative test session.
    """

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self.base_url = base_url.rstrip("/")
        self.email: str = f"neg_{uuid.uuid4().hex[:10]}@cognitest.invalid"
        self.password: str = f"TestP@ss{uuid.uuid4().hex[:8]}!"
        self.user_id: str | None = None
        self.token: str | None = None

        # resource_context stores real DB IDs for path-param resolution.
        # Key format: snake_case param name → string ID value.
        # Example: {"post_id": "abc123", "comment_id": "def456"}
        self.resource_context: dict[str, Any] = {}

        # stored_ids is the dict the test runner reads for path-param resolution.
        # It is kept in sync with resource_context after seeding.
        self.stored_ids: dict[str, str] = {}

        # Secondary session (for RBAC / permission tests)
        self._secondary: NegativeTestSessionManager | None = None

        # OpenAPI spec — set via set_spec() so seed_resources can discover endpoints
        self._spec: dict[str, Any] | None = None

    # ── Public properties ────────────────────────────────────────────────

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)

    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.token:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def set_spec(self, spec: dict[str, Any]) -> None:
        """Provide the OpenAPI spec for spec-driven resource seeding."""
        self._spec = spec

    # ── Setup lifecycle ──────────────────────────────────────────────────

    async def setup(self, client: httpx.AsyncClient) -> None:
        """
        Adaptive auth lifecycle:
          signup → detect OTP → (verify if needed) → login → seed_resources

        For non-OTP AUTs the OTP step is automatically skipped.
        Raises RuntimeError with a descriptive message on any failure so
        conftest.py can call pytest.exit() cleanly.
        """
        await self._signup(client)

        # Probe whether the AUT requires OTP/email verification before login
        otp_required = await self._detect_otp_requirement(client)

        if otp_required:
            otp_ok = await self._try_verify_otp(client)
            if not otp_ok:
                raise RuntimeError(
                    f"AUT requires OTP/email verification for {self.email} but "
                    "Cognitest could not complete it (no DB access or OTP not found). "
                    "Use the manual token option in the Run Test modal instead."
                )

        await self._login(client)
        await self.seed_resources(client)

        # Bridge: copy seeded resource IDs into stored_ids so the runner
        # can resolve path parameters like {projectId} at execution time.
        self.stored_ids.update(self.resource_context)
        if self.user_id:
            self.stored_ids.setdefault("user_id", self.user_id)
            self.stored_ids.setdefault("userId", self.user_id)
            self.stored_ids.setdefault("id", self.user_id)
        logger.info(
            "[SessionManager] stored_ids after setup: %s",
            {k: v[:20] + '...' if isinstance(v, str) and len(v) > 20 else v
             for k, v in self.stored_ids.items()},
        )

    async def _signup(self, client: httpx.AsyncClient) -> None:
        """Execute signup. Tries multiple common payload shapes."""
        signup_paths = ["/auth/signup", "/auth/register", "/api/auth/signup",
                        "/api/auth/register", "/register", "/signup"]
        payloads = [
            {"email": self.email, "password": self.password, "confirmPassword": self.password},
            {"email": self.email, "password": self.password, "confirmPassword": self.password, "name": "CogniTest User"},
            {"email": self.email, "password": self.password, "name": "CogniTest User"},
            {"email": self.email, "password": self.password},
        ]

        # Also try spec-derived paths
        if self._spec:
            for path in self._spec.get("paths", {}):
                lower = path.lower()
                if any(k in lower for k in ("signup", "register")) and "verify" not in lower:
                    if path not in signup_paths:
                        signup_paths.insert(0, path)

        last_error = ""
        for path in signup_paths:
            for payload in payloads:
                try:
                    resp = await client.post(
                        f"{self.base_url}{path}",
                        json=payload,
                        timeout=15.0,
                    )
                    if resp.status_code == 404:
                        break  # Wrong path, try next
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        self.user_id = (
                            data.get("id")
                            or data.get("userId")
                            or data.get("user_id")
                            or (data.get("user") or {}).get("id")
                            or (data.get("data") or {}).get("id")
                        )
                        if self.user_id:
                            self.user_id = str(self.user_id)
                        # Some APIs return token directly on signup
                        signup_token = (
                            data.get("token")
                            or data.get("accessToken")
                            or data.get("access_token")
                            or (data.get("data") or {}).get("token")
                        )
                        if signup_token:
                            self.token = signup_token
                        logger.info("[SessionManager] Signup OK — email=%s user_id=%s path=%s",
                                    self.email, self.user_id, path)
                        return
                    if resp.status_code == 409:
                        # User already exists — try to extract user_id from response
                        try:
                            data_409 = resp.json()
                            uid = (
                                data_409.get("id") or data_409.get("userId")
                                or data_409.get("user_id")
                                or (data_409.get("user") or {}).get("id")
                                or (data_409.get("data") or {}).get("id")
                            )
                            if uid:
                                self.user_id = str(uid)
                        except Exception:
                            pass
                        logger.info("[SessionManager] Signup 409 (user exists) — will attempt login. user_id=%s", self.user_id)
                        return
                    last_error = f"HTTP {resp.status_code} — {resp.text[:200]}"
                except Exception as exc:
                    last_error = str(exc)
                    continue

        raise RuntimeError(f"Signup failed for {self.email}: {last_error}")

    async def _detect_otp_requirement(self, client: httpx.AsyncClient) -> bool:
        """
        Probe login to determine if OTP/email verification is required.

        Returns True if the AUT responded with a hint that the account
        needs verification before login is allowed.
        """
        # If signup already gave us a token, no OTP needed
        if self.token:
            return False

        login_paths = ["/auth/login", "/api/auth/login", "/login", "/api/login"]
        if self._spec:
            for path in self._spec.get("paths", {}):
                lower = path.lower()
                if any(k in lower for k in ("login", "signin", "token")) and "logout" not in lower:
                    if path not in login_paths:
                        login_paths.insert(0, path)

        for path in login_paths:
            try:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    json={"email": self.email, "password": self.password},
                    timeout=10.0,
                )
                if resp.status_code == 404:
                    continue  # Wrong path
                if resp.status_code in (200, 201):
                    # Login succeeded without OTP — cache the token to avoid double login
                    try:
                        data = resp.json()
                        token = (
                            data.get("token") or data.get("accessToken")
                            or data.get("access_token")
                            or (data.get("data") or {}).get("token")
                        )
                        if token:
                            self.token = token
                            uid = (
                                data.get("id") or data.get("userId")
                                or (data.get("user") or {}).get("id")
                                or (data.get("data") or {}).get("id")
                            )
                            if uid:
                                self.user_id = str(uid)
                            logger.info("[SessionManager] Token cached from OTP probe — skipping redundant login")
                    except Exception:
                        pass
                    return False

                # Check response body for OTP/verification hints
                body = resp.text.lower()
                otp_hints = {
                    "verify", "verified", "unverified", "not verified",
                    "otp", "confirmation", "activate", "confirm your email",
                    "email verification", "account not active",
                }
                if any(hint in body for hint in otp_hints):
                    logger.info("[SessionManager] OTP/verification detected via login probe: %s", path)
                    return True

                # 401/403 without OTP hints = likely wrong credentials or other issue, not OTP
                # Continue checking other paths
            except Exception:
                continue

        # No OTP hints found — assume no OTP required
        return False

    async def _try_verify_otp(self, client: httpx.AsyncClient) -> bool:
        """
        Attempt OTP verification via Prisma DB access.
        Returns True if verification succeeded, False if not possible.
        This method is NON-FATAL — it catches all errors gracefully.
        """
        try:
            from src.config import prisma  # type: ignore[import]

            if not prisma.is_connected():
                logger.info("[SessionManager] Prisma not connected — cannot verify OTP")
                return False

            otp_record = await prisma.otp.find_first(
                where={"email": self.email},
                order={"createdAt": "desc"},
            )
            if not otp_record:
                logger.warning("[SessionManager] OTP record not found in DB for %s", self.email)
                return False

            resp = await client.post(
                f"{self.base_url}/auth/verify",
                json={"email": self.email, "otp": otp_record.code},
                timeout=15.0,
            )
            if resp.status_code in (200, 201):
                logger.info("[SessionManager] OTP verify OK — email=%s", self.email)
                return True

            logger.warning("[SessionManager] OTP verify failed: HTTP %d — %s",
                           resp.status_code, resp.text[:200])
            return False

        except Exception as exc:
            logger.info("[SessionManager] OTP verify not possible: %s", exc)
            return False

    async def _login(self, client: httpx.AsyncClient) -> None:
        """Execute login. Tries multiple common paths and payload shapes."""
        # If signup already gave us a token, skip login
        if self.token:
            logger.info("[SessionManager] Token already acquired from signup — skipping login")
            self._extract_user_id_from_token()
            return

        login_paths = ["/auth/login", "/api/auth/login", "/login", "/api/login"]
        if self._spec:
            for path in self._spec.get("paths", {}):
                lower = path.lower()
                if any(k in lower for k in ("login", "signin", "token")) and "logout" not in lower:
                    if path not in login_paths:
                        login_paths.insert(0, path)

        payloads = [
            {"email": self.email, "password": self.password},
            {"email": self.email, "password": self.password, "rememberMe": False},
            {"username": self.email, "password": self.password},
        ]

        last_error = ""
        for path in login_paths:
            for payload in payloads:
                try:
                    resp = await client.post(
                        f"{self.base_url}{path}",
                        json=payload,
                        timeout=15.0,
                    )
                    if resp.status_code == 404:
                        break  # Wrong path
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        token = (
                            data.get("token")
                            or data.get("accessToken")
                            or data.get("access_token")
                            or (data.get("data") or {}).get("token")
                            or (data.get("data") or {}).get("access_token")
                        )
                        if not token:
                            last_error = f"Login 200 but no token in response. Keys: {list(data.keys())}"
                            continue
                        self.token = token
                        # Extract user_id from login response too
                        uid = (
                            data.get("id") or data.get("userId") or data.get("user_id")
                            or (data.get("user") or {}).get("id")
                            or (data.get("data") or {}).get("id")
                        )
                        if uid:
                            self.user_id = str(uid)
                        if not self.user_id:
                            self._extract_user_id_from_token()
                        logger.info("[SessionManager] Login OK — email=%s token_len=%d path=%s",
                                    self.email, len(token), path)
                        return
                    last_error = f"HTTP {resp.status_code} — {resp.text[:200]}"
                except Exception as exc:
                    last_error = str(exc)
                    continue

        raise RuntimeError(
            f"Login failed for {self.email}: {last_error}"
        )

    def _extract_user_id_from_token(self) -> None:
        """Best-effort JWT decode to extract user_id."""
        if not self.token or self.user_id:
            return
        try:
            parts = self.token.split(".")
            if len(parts) != 3:
                return
            # Pad base64
            payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
            decoded = _json.loads(base64.urlsafe_b64decode(payload_b64))
            uid = (
                decoded.get("id") or decoded.get("sub")
                or decoded.get("userId") or decoded.get("user_id") or ""
            )
            if uid:
                self.user_id = str(uid)
                logger.info("[SessionManager] Extracted user_id from JWT: %s", self.user_id)
        except Exception:
            pass

    # ── Resource seeding ─────────────────────────────────────────────────

    async def seed_resources(self, client: httpx.AsyncClient) -> None:
        """
        Create real resources in the DB so that path-param endpoints
        receive valid IDs instead of 404 responses.

        Uses spec-driven discovery when a spec is available, otherwise
        falls back to _get_seed_operations().
        """
        ops = self._get_seed_operations()
        if not ops:
            logger.info(
                "[SessionManager] No seed operations discovered. "
                "Path-param endpoints may receive 404. "
            )
            return

        headers = {**self.auth_headers, "Content-Type": "application/json"}

        for op in ops:
            path: str = op["path"]
            payload: dict = op.get("payload", {})
            id_keys: list[str] = op.get("id_keys", ["id", "_id", "resourceId", "resource_id"])
            context_key: str = op.get("context_key", "resource_id")

            try:
                resp = await client.post(
                    f"{self.base_url}{path}",
                    json=payload,
                    headers=headers,
                    timeout=15.0,
                )
            except Exception as exc:
                logger.warning("[SessionManager] Seed POST %s failed: %s", path, exc)
                continue

            if resp.status_code not in (200, 201):
                logger.warning(
                    "[SessionManager] Seed POST %s returned %d — skipping. Body: %s",
                    path, resp.status_code, resp.text[:200],
                )
                continue

            try:
                data = resp.json()
            except Exception:
                logger.warning("[SessionManager] Seed POST %s returned non-JSON", path)
                continue

            rid = _extract_id(data, id_keys)
            if not rid:
                logger.warning(
                    "[SessionManager] Seed POST %s: could not extract ID. "
                    "Response keys: %s. Tried id_keys=%s.",
                    path, list(data.keys()) if isinstance(data, dict) else "non-dict", id_keys,
                )
                continue

            self.resource_context[context_key] = rid
            # Also register under the path so resolve_path() can find it
            self.store_resource_id(path, rid)
            logger.info(
                "[SessionManager] Seeded %s → context_key=%s id=%s",
                path, context_key, rid,
            )

    def _get_seed_operations(self) -> list[dict[str, Any]]:
        """
        Discover seed operations from the OpenAPI spec.

        Finds top-level POST endpoints (no path params) that are NOT auth
        endpoints and generates minimal valid payloads for them.
        Falls back to empty list if no spec is available.
        """
        if not self._spec:
            return []

        _skip_keywords = {
            "auth", "login", "signup", "register", "verify", "reset",
            "logout", "refresh", "password", "otp", "token", "confirm",
        }

        ops: list[dict[str, Any]] = []
        for path, path_item in self._spec.get("paths", {}).items():
            if "post" not in path_item:
                continue
            lower = path.lower()
            # Skip auth and parameterized endpoints
            if any(k in lower for k in _skip_keywords):
                continue
            if "{" in path:
                continue

            operation = path_item["post"]
            schema = _extract_post_body_schema(operation, self._spec)
            if not schema:
                continue

            payload = _generate_minimal_payload(schema)
            context_key = _infer_context_key(path)

            ops.append({
                "path": path,
                "payload": payload,
                "id_keys": ["id", "_id", "resourceId", "uuid"],
                "context_key": context_key,
            })

        return ops

    # ── ID registry ──────────────────────────────────────────────────────

    def store_resource_id(self, path: str, rid: str) -> None:
        """
        Register a resource ID under a normalised path key.

        Called by:
          - seed_resources() during setup
          - _execute_sequence_case() in test_negative_execution.py after
            a successful CREATE step

        The stored value is used by resolve_path() in the runner to
        substitute real IDs into path templates like /api/posts/{postId}.
        """
        # Normalise path → key: "/api/posts" → "post"
        parts = [p for p in path.strip("/").split("/") if p and not p.startswith("{")]
        if parts:
            key = parts[-1].rstrip("s")  # "posts" → "post", "comments" → "comment"
            # Store under type-specific keys (overwrite to keep latest)
            self.resource_context[f"{key}_id"] = rid
            self.resource_context[f"{key}Id"] = rid
        # Always store under the raw path as well
        self.resource_context[path] = rid
        # NOTE: We intentionally do NOT store under generic "resource_id" or "id"
        # to prevent cross-resource collision when multiple resource types are seeded.

    # ── Secondary session (for RBAC tests) ───────────────────────────────

    async def ensure_secondary_session(
        self, client: httpx.AsyncClient
    ) -> "NegativeTestSessionManager | None":
        """
        Create and authenticate a second user for permission / RBAC tests.

        Returns the secondary manager, or None if setup fails.
        The secondary user has no elevated privileges — it can only access
        resources it created itself.
        """
        if self._secondary and self._secondary.is_authenticated:
            return self._secondary

        secondary = NegativeTestSessionManager(base_url=self.base_url)
        secondary._spec = self._spec  # Share spec for seeding
        try:
            await secondary.setup(client)
            self._secondary = secondary
            logger.info(
                "[SessionManager] Secondary session ready — email=%s", secondary.email
            )
        except RuntimeError as exc:
            logger.warning("[SessionManager] Secondary session setup failed: %s", exc)
            return None
        return self._secondary


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _extract_id(data: Any, id_keys: list[str]) -> str | None:
    """
    Try to extract a resource ID from an API response dict.

    Checks:
      1. Top-level keys (id, _id, resourceId, ...)
      2. Nested under data.{key}
      3. Nested under result.{key}
    """
    if not isinstance(data, dict):
        return None
    for key in id_keys:
        if key in data and data[key]:
            return str(data[key])
    for envelope in ("data", "result", "resource"):
        nested = data.get(envelope)
        if isinstance(nested, dict):
            for key in id_keys:
                if key in nested and nested[key]:
                    return str(nested[key])
    return None


def _extract_post_body_schema(operation: dict, spec: dict) -> dict | None:
    """Extract the resolved request body schema from a POST operation."""
    rb = operation.get("requestBody", {})
    content = rb.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema")
    if not schema:
        return None
    # Resolve $ref
    if "$ref" in schema:
        ref_str = schema["$ref"]
        if ref_str.startswith("#/"):
            current = spec
            for part in ref_str[2:].split("/"):
                current = current.get(part, {}) if isinstance(current, dict) else {}
            schema = current if isinstance(current, dict) else None
    return schema


def _generate_minimal_payload(schema: dict) -> dict:
    """Generate a minimal valid payload from a JSON schema."""
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties", {})
    required = schema.get("required", list(properties.keys()))
    payload: dict[str, Any] = {}
    for field in required:
        if field not in properties:
            payload[field] = "test_value"
            continue
        prop = properties[field]
        prop_type = prop.get("type", "string")
        if prop_type == "string":
            fmt = prop.get("format", "")
            if "email" in field.lower():
                payload[field] = f"seed_{uuid.uuid4().hex[:6]}@test.invalid"
            elif fmt == "date-time":
                payload[field] = "2025-01-01T00:00:00Z"
            elif fmt == "uuid":
                payload[field] = str(uuid.uuid4())
            else:
                payload[field] = f"seed_{uuid.uuid4().hex[:6]}"
        elif prop_type == "integer":
            payload[field] = prop.get("minimum", 1)
        elif prop_type == "number":
            payload[field] = prop.get("minimum", 1.0)
        elif prop_type == "boolean":
            payload[field] = True
        elif prop_type == "array":
            payload[field] = []
        elif prop_type == "object":
            payload[field] = {}
        else:
            payload[field] = "test_value"
    return payload


def _infer_context_key(path: str) -> str:
    """Infer a context key from a path like /api/posts → post_id."""
    parts = [p for p in path.strip("/").split("/") if p]
    if not parts:
        return "resource_id"
    last = parts[-1].rstrip("s")  # "posts" → "post"
    return f"{last}_id"
