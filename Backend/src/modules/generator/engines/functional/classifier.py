"""
Endpoint role classifier — infers roles from OpenAPI schema without hardcoding.

Roles:
  AUTH_PROVIDER       — POST returning token-like fields
  AUTH_REQUIRED       — Has security scheme
  COLLECTION_PROVIDER — GET returning an array
  RESOURCE_WITH_ID    — Has {id}-style path parameters
  CREATOR             — POST creating a resource
  GENERAL             — Anything else
"""
from __future__ import annotations

import re
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...spec_parser import Endpoint


class EndpointRole(str, Enum):
    AUTH_PROVIDER       = "AUTH_PROVIDER"
    AUTH_REQUIRED       = "AUTH_REQUIRED"
    COLLECTION_PROVIDER = "COLLECTION_PROVIDER"
    RESOURCE_WITH_ID    = "RESOURCE_WITH_ID"
    CREATOR             = "CREATOR"
    GENERAL             = "GENERAL"


# --- Generic heuristic sets (no hardcoded paths) ---

_TOKEN_FIELDS = frozenset({
    "token", "access_token", "accessToken", "jwt", "id_token",
    "auth_token", "bearer", "sessionToken", "session_token",
})

_ID_FIELD_RE = re.compile(r"^(_id|id|[a-z_]+Id|[a-z_]+_id)$", re.IGNORECASE)

_AUTH_KEYWORDS    = frozenset({"login", "signin", "sign-in", "sign_in", "auth", "token", "authenticate", "session"})
_REGISTER_KEYWORDS = frozenset({"register", "signup", "sign-up", "sign_up", "create-account", "create_account", "enroll"})


# --- Schema inspection helpers ---

def _top_props(endpoint: "Endpoint") -> set[str]:
    rs = endpoint.response_schema or {}
    props = rs.get("properties") or {}
    if not props:
        data = (rs.get("properties") or {}).get("data") or {}
        props = (data.get("properties") or {}) if isinstance(data, dict) else {}
    return set(props.keys())


def _returns_token(endpoint: "Endpoint") -> bool:
    if _top_props(endpoint) & _TOKEN_FIELDS:
        return True
    rs = endpoint.response_schema or {}
    data = (rs.get("properties") or {}).get("data") or {}
    nested = set((data.get("properties") or {}).keys()) if isinstance(data, dict) else set()
    return bool(nested & _TOKEN_FIELDS)


def _returns_array(endpoint: "Endpoint") -> bool:
    rs = endpoint.response_schema or {}
    if rs.get("type") == "array":
        return True
    data = (rs.get("properties") or {}).get("data") or {}
    return isinstance(data, dict) and data.get("type") == "array"


def _path_has(path: str, keywords: frozenset[str]) -> bool:
    lp = path.lower()
    return any(kw in lp for kw in keywords)


# --- Public classifier ---

def classify_endpoint(endpoint: "Endpoint") -> list[EndpointRole]:
    """Return all roles for an endpoint (may be multiple)."""
    roles: list[EndpointRole] = []
    m = endpoint.method.upper()

    # AUTH_PROVIDER: POST matching auth/register keywords or returning a token
    # Guard against password reset / verification paths
    is_reset_path = _path_has(endpoint.path, frozenset({"reset", "forgot", "verify", "password", "otp", "email"}))
    
    if m == "POST" and not is_reset_path and (
        _path_has(endpoint.path, _AUTH_KEYWORDS)
        or _path_has(endpoint.path, _REGISTER_KEYWORDS)
        or _returns_token(endpoint)
    ):
        roles.append(EndpointRole.AUTH_PROVIDER)

    # CREATOR: POST that is not an auth endpoint
    if m == "POST" and EndpointRole.AUTH_PROVIDER not in roles:
        roles.append(EndpointRole.CREATOR)

    # COLLECTION_PROVIDER: GET, no path params, returns array
    if m == "GET" and not endpoint.path_params and _returns_array(endpoint):
        roles.append(EndpointRole.COLLECTION_PROVIDER)

    # RESOURCE_WITH_ID: any method with path params
    if endpoint.path_params:
        roles.append(EndpointRole.RESOURCE_WITH_ID)

    # AUTH_REQUIRED: OpenAPI security scheme present
    if endpoint.requires_auth:
        roles.append(EndpointRole.AUTH_REQUIRED)

    return roles or [EndpointRole.GENERAL]


def priority_of(roles: list[EndpointRole]) -> int:
    """Execution bucket: lower = runs first."""
    if EndpointRole.AUTH_PROVIDER in roles:       return 0
    if EndpointRole.COLLECTION_PROVIDER in roles: return 1
    if EndpointRole.CREATOR in roles:             return 2
    if EndpointRole.RESOURCE_WITH_ID in roles:    return 3
    if EndpointRole.AUTH_REQUIRED in roles:       return 4
    return 5
