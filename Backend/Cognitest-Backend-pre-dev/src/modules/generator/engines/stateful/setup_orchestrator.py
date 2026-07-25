"""
Setup Orchestrator – pre-test phase that provisions test users and resources.

Performs (in order):
  1. Create user A  (POST to the user-creation endpoint)
  2. Login user A   (POST to the login endpoint) → store token_a
  3. Create user B
  4. Login user B   → store token_b
  5. Create a resource as user B → store resource ID in ctx.resource_ids

Every step uses fail-fast semantics: an unexpected HTTP status code raises
SetupError so the caller can record the failure and skip stateful tests –
but the overall run does NOT crash.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from ...spec_parser import Endpoint
from .context import TestContext
from .spec_analyzer import SpecEndpoints

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions and result type
# ---------------------------------------------------------------------------


class SetupError(Exception):
    """Raised when a setup step returns an unexpected HTTP status."""

    def __init__(self, step: str, expected: list[int], actual: int, body: str) -> None:
        self.step = step
        self.expected = expected
        self.actual = actual
        self.body = body
        super().__init__(
            f"Setup step '{step}' failed: expected {expected}, got {actual}. Body: {body[:200]}"
        )


@dataclass
class SetupResult:
    """
    Outcome of the pre-test setup phase.

    Attributes:
        success:      True if all steps completed without error.
        steps:        List of step completion records (for the report).
        error:        SetupError if any step failed, else None.
    """

    success: bool
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: SetupError | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "steps": self.steps,
            "error": str(self.error) if self.error else None,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_test_credentials(user_label: str) -> dict[str, str]:
    """Generate unique email/password for a throwaway test user."""
    uid = uuid.uuid4().hex[:8]
    return {
        "email": f"cognitest_{user_label}_{uid}@security-test.invalid",
        "password": f"Ct@{uid}Secure!",
        "name": f"Cognitest {user_label.upper()} {uid}",
        "username": f"ct_{user_label}_{uid}",
    }


def _extract_token(response_body: dict[str, Any]) -> str | None:
    """
    Try common JWT field names in a login response body.

    Returns the token string or None if not found.
    """
    for key in ("token", "access_token", "accessToken", "jwt", "id_token", "idToken"):
        val = response_body.get(key)
        if isinstance(val, str) and val:
            return val
    # Some APIs nest inside 'data' or 'result'
    for wrapper in ("data", "result", "auth"):
        nested = response_body.get(wrapper)
        if isinstance(nested, dict):
            for key in ("token", "access_token", "accessToken", "jwt"):
                val = nested.get(key)
                if isinstance(val, str) and val:
                    return val
    return None


def _extract_user_id(response_body: dict[str, Any]) -> str | None:
    """Try common user-ID field names in a creation response body."""
    for key in ("id", "userId", "user_id", "_id"):
        val = response_body.get(key)
        if isinstance(val, str) and val:
            return val
    nested = response_body.get("data") or response_body.get("user") or {}
    if isinstance(nested, dict):
        for key in ("id", "userId", "user_id", "_id"):
            val = nested.get(key)
            if isinstance(val, str) and val:
                return val
    return None


def _extract_resource_id(response_body: dict[str, Any]) -> str | None:
    """Extract the ID of a newly created resource."""
    for key in ("id", "resourceId", "resource_id", "_id"):
        val = response_body.get(key)
        if isinstance(val, str) and val:
            return val
    # Common nesting patterns
    for wrapper in ("data", "result", "item", "record"):
        nested = response_body.get(wrapper)
        if isinstance(nested, dict):
            val = nested.get("id") or nested.get("_id")
            if isinstance(val, str) and val:
                return val
    return None


async def _try_refresh_token(
    ctx: TestContext, login_path: str, creds: dict[str, str]
) -> str | None:
    """
    Re-attempt login to refresh an expired token.

    Returns the new token string or None on failure.
    """
    try:
        resp = await ctx.http_client.post(ctx.full_url(login_path), json=creds)
        if resp.status_code in (200, 201):
            body = resp.json()
            return _extract_token(body)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Token refresh failed: %s", exc)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def run_setup_phase(
    ctx: TestContext,
    spec_endpoints: SpecEndpoints,
) -> SetupResult:
    """
    Execute the pre-test setup phase and populate *ctx* with user/token data.

    Each step records its outcome in the returned :class:`SetupResult`.
    Any step that returns an unexpected HTTP status short-circuits execution
    and returns ``success=False``.

    Args:
        ctx:            TestContext with injected HTTP client and base URL.
        spec_endpoints: Discovered endpoints from the OpenAPI spec.

    Returns:
        :class:`SetupResult` — caller should check ``success`` before running
        authorization tests.
    """
    steps: list[dict[str, Any]] = []

    user_create_path = spec_endpoints.user_create_path
    login_path = spec_endpoints.login_path

    if not user_create_path or not login_path:
        missing = []
        if not user_create_path:
            missing.append("user-creation endpoint")
        if not login_path:
            missing.append("login endpoint")
        err = SetupError(
            step="endpoint-discovery",
            expected=[],
            actual=0,
            body=f"Could not discover: {', '.join(missing)}",
        )
        return SetupResult(success=False, steps=steps, error=err)

    # Helper to record step outcome
    def _record(step: str, status: int, notes: str) -> None:
        steps.append({"step": step, "status": status, "notes": notes})
        logger.info("[Setup] %s → HTTP %s | %s", step, status, notes)

    # Find the Endpoint objects for create and login to get schema/params
    create_ep = next((ep for ep in spec_endpoints.all_endpoints if ep.path == user_create_path and ep.method == "POST"), None)
    login_ep = next((ep for ep in spec_endpoints.all_endpoints if ep.path == login_path and ep.method == "POST"), None)

    try:
        # ------------------------------------------------------------------
        # Step 1: Create User A
        # ------------------------------------------------------------------
        ctx.creds_a = _generate_test_credentials("a")
        body_a = _build_body_for_user(create_ep, ctx.creds_a) if create_ep else ctx.creds_a
        query_a = _build_query_params(create_ep) if create_ep else {}
        
        resp = await ctx.http_client.post(
            ctx.full_url(user_create_path), 
            json=body_a,
            params=query_a
        )
        _record("Create User A", resp.status_code, f"email={ctx.creds_a['email']}")
        if resp.status_code not in (200, 201):
            raise SetupError("Create User A", [200, 201], resp.status_code, resp.text)
        ctx.user_a_id = _extract_user_id(resp.json()) or "unknown-a"

        # ------------------------------------------------------------------
        # Step 2: Login User A
        # ------------------------------------------------------------------
        body_login_a = _build_body_for_user(login_ep, ctx.creds_a) if login_ep else {
            "email": ctx.creds_a["email"], "password": ctx.creds_a["password"]
        }
        query_login_a = _build_query_params(login_ep) if login_ep else {}
        
        resp = await ctx.http_client.post(
            ctx.full_url(login_path), 
            json=body_login_a,
            params=query_login_a
        )
        _record("Login User A", resp.status_code, "")
        if resp.status_code not in (200, 201):
            raise SetupError("Login User A", [200, 201], resp.status_code, resp.text)
        ctx.token_a = _extract_token(resp.json())
        if not ctx.token_a:
            raise SetupError("Login User A", [200, 201], resp.status_code, "JWT not found in response")

        # ------------------------------------------------------------------
        # Step 3: Create User B
        # ------------------------------------------------------------------
        ctx.creds_b = _generate_test_credentials("b")
        body_b = _build_body_for_user(create_ep, ctx.creds_b) if create_ep else ctx.creds_b
        query_b = _build_query_params(create_ep) if create_ep else {}

        resp = await ctx.http_client.post(
            ctx.full_url(user_create_path), 
            json=body_b,
            params=query_b
        )
        _record("Create User B", resp.status_code, f"email={ctx.creds_b['email']}")
        if resp.status_code not in (200, 201):
            raise SetupError("Create User B", [200, 201], resp.status_code, resp.text)
        ctx.user_b_id = _extract_user_id(resp.json()) or "unknown-b"

        # ------------------------------------------------------------------
        # Step 4: Login User B
        # ------------------------------------------------------------------
        body_login_b = _build_body_for_user(login_ep, ctx.creds_b) if login_ep else {
            "email": ctx.creds_b["email"], "password": ctx.creds_b["password"]
        }
        query_login_b = _build_query_params(login_ep) if login_ep else {}

        resp = await ctx.http_client.post(
            ctx.full_url(login_path), 
            json=body_login_b,
            params=query_login_b
        )
        _record("Login User B", resp.status_code, "")
        if resp.status_code not in (200, 201):
            raise SetupError("Login User B", [200, 201], resp.status_code, resp.text)
        ctx.token_b = _extract_token(resp.json())
        if not ctx.token_b:
            raise SetupError("Login User B", [200, 201], resp.status_code, "JWT not found in response")

        # ------------------------------------------------------------------
        # Step 5: Create resource as User B (use first resource endpoint)
        # ------------------------------------------------------------------
        if spec_endpoints.resource_endpoints:
            res_ep = spec_endpoints.resource_endpoints[0]
            # Build a minimal body from the body schema
            body = _build_minimal_body(res_ep.body_schema)
            resp = await ctx.http_client.post(
                ctx.full_url(res_ep.path),
                json=body,
                headers=ctx.auth_header_b(),
            )
            _record("Create Resource (as User B)", resp.status_code, f"path={res_ep.path}")
            if resp.status_code not in (200, 201):
                # Non-fatal: resource creation failure degrades cross-resource tests
                _record(
                    "Create Resource SKIPPED",
                    resp.status_code,
                    "Resource creation failed – cross-resource auth tests will use placeholder IDs",
                )
            else:
                rid = _extract_resource_id(resp.json())
                if rid:
                    resource_type = res_ep.path.strip("/").split("/")[-1]
                    ctx.resource_ids[resource_type] = rid
                    _record(
                        "Store Resource ID",
                        resp.status_code,
                        f"type={resource_type} id={rid}",
                    )
        else:
            _record("Create Resource", 0, "No resource endpoints found in spec – skipped")

    except SetupError as exc:
        _record(f"FAILED: {exc.step}", exc.actual, str(exc))
        return SetupResult(success=False, steps=steps, error=exc)
    except Exception as exc:  # noqa: BLE001
        err = SetupError("unexpected-error", [], 0, str(exc))
        _record("FAILED: unexpected error", 0, str(exc))
        return SetupResult(success=False, steps=steps, error=err)

    return SetupResult(success=True, steps=steps)


# ---------------------------------------------------------------------------
# Body and Query builders
# ---------------------------------------------------------------------------


def _build_body_for_user(ep: Endpoint, creds: dict[str, str]) -> dict:
    """Build a request body for user creation/login using discovered schema."""
    if not ep.body_schema:
        return creds

    body = _build_minimal_body(ep.body_schema)
    
    # Inject our credentials where they fit best by name heuristics
    for field_name in body.keys():
        name_low = field_name.lower()
        if "email" in name_low:
            body[field_name] = creds["email"]
        elif "pass" in name_low:
            body[field_name] = creds["password"]
        elif "username" in name_low:
            body[field_name] = creds["username"]
        elif "name" in name_low:
            body[field_name] = creds["name"]
            
    return body


def _build_query_params(ep: Endpoint) -> dict[str, Any]:
    """Build placeholder query parameters for required fields."""
    params = {}
    for p in ep.query_params:
        if p.get("required"):
            params[p["name"]] = _placeholder_value(p["name"], p.get("type", "string"))
    return params


def _build_minimal_body(schema: dict | None) -> dict:
    """
    Build a minimal valid request body from an OpenAPI body schema.
    Handles nested objects and required fields recursively.
    """
    if not schema or not isinstance(schema, dict):
        return {}

    # Handle allOf (merge properties)
    if "allOf" in schema:
        merged_props = {}
        required = []
        for sub in schema["allOf"]:
            if isinstance(sub, dict):
                merged_props.update(sub.get("properties", {}))
                required.extend(sub.get("required", []))
        schema = {"type": "object", "properties": merged_props, "required": required}

    body: dict = {}
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))

    for field_name, field_def in properties.items():
        # Only fill required fields to keep the payload minimal
        if field_name not in required_fields and len(required_fields) > 0:
            continue
        
        field_type = field_def.get("type", "string")
        
        # Recursive build for objects
        if field_type == "object":
            body[field_name] = _build_minimal_body(field_def)
        elif field_type == "array":
            items_schema = field_def.get("items", {})
            if items_schema.get("type") == "object":
                body[field_name] = [_build_minimal_body(items_schema)]
            else:
                body[field_name] = [_placeholder_value(field_name, items_schema.get("type", "string"))]
        else:
            body[field_name] = _placeholder_value(field_name, field_type, field_def)

    return body


def _placeholder_value(field_name: str, field_type: str, field_def: dict | None = None) -> Any:
    """Return a safe placeholder value for a schema field."""
    field_def = field_def or {}
    name_lower = field_name.lower()
    
    # 1. Handle Enum
    if "enum" in field_def and field_def["enum"]:
        return field_def["enum"][0]

    # 2. Handle Types
    if field_type == "integer" or field_type == "number":
        return 1
    if field_type == "boolean":
        return True
    if field_type == "array":
        return []
        
    # 3. Handle String Formats and Heuristics
    fmt = field_def.get("format", "")
    if fmt == "email" or "email" in name_lower:
        return "cognitest-resource@security-test.invalid"
    if fmt == "uuid":
        return str(uuid.uuid4())
    if fmt in ("date-time", "date"):
        return "2024-01-01T00:00:00Z" if fmt == "date-time" else "2024-01-01"
    if "url" in name_lower or "link" in name_lower:
        return "https://security-test.invalid"
    if "password" in name_lower or "passphrase" in name_lower:
        return "Ct@TestPass1!"
    if "body" in name_lower or "content" in name_lower or "text" in name_lower:
        return "Cognitest security test resource content"
    if "name" in name_lower:
        return "Cognitest Resource"
        
    return f"ct-{field_name}"
