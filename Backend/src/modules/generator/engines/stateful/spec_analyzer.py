"""
Spec Analyzer – discovers auth-related endpoints from an OpenAPI spec.

No endpoint paths are hardcoded.  Discovery uses heuristics based on:
  - HTTP method
  - Path segment keywords
  - Request body field names
  - Response status codes
  - Security scheme presence
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ...spec_parser import Endpoint, extract_endpoints


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class SpecEndpoints:
    """
    Endpoints discovered from the OpenAPI spec that the stateful engine needs.

    Attributes:
        user_create_path:    Path for creating a new user account (POST).
        login_path:          Path for obtaining a JWT (POST).
        resource_endpoints:  POST endpoints that create a resource owned by the
                             authenticated user (used to seed test resources).
        secured_endpoints:   All endpoints requiring bearer authentication –
                             these become authorization test targets.
        all_endpoints:       Every parsed endpoint (for stateless pass-through).
    """

    user_create_path: str | None = None
    login_path: str | None = None
    resource_endpoints: list[Endpoint] = field(default_factory=list)
    secured_endpoints: list[Endpoint] = field(default_factory=list)
    all_endpoints: list[Endpoint] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Heuristic keyword sets
# ---------------------------------------------------------------------------

_LOGIN_KEYWORDS = {
    "login", "signin", "sign-in", "authenticate", "session", "authorize"
}
_TOKEN_KEYWORDS = {"token", "jwt", "access-token"}
_USER_CREATE_KEYWORDS = {
    "register", "signup", "sign-up", "users", "user", "account", 
    "accounts", "create-user", "join", "enroll"
}

# Body fields that strongly suggest a user-creation or login endpoint
_USER_BODY_FIELDS = {"email", "username", "password", "user", "pass", "login", "credential"}


def _path_contains(path: str, keywords: set[str]) -> bool:
    """Return True if any segment of *path* matches one of *keywords*."""
    # Split by common separators and also handle camelCase by splitting on caps
    segments = re.findall(r'[a-z]+|[A-Z][a-z]*', path)
    segments = {s.lower() for s in segments}
    return bool(segments & keywords)


def _body_has_user_fields(schema: dict[str, Any] | None) -> bool:
    """Return True if the request body schema has typical user fields (even nested)."""
    if not schema:
        return False
    
    props = schema.get("properties", {})
    field_names = {k.lower() for k in props}
    if bool(field_names & _USER_BODY_FIELDS):
        return True
        
    # Check one level deeper for common wrappers like "user", "profile", "data"
    for wrapper in ("user", "profile", "data", "account"):
        if wrapper in props:
            nested = props[wrapper].get("properties", {}) if isinstance(props[wrapper], dict) else {}
            nested_names = {k.lower() for k in nested}
            if bool(nested_names & _USER_BODY_FIELDS):
                return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def analyze_spec(spec: dict[str, Any]) -> SpecEndpoints:
    """
    Parse *spec* and categorize endpoints for stateful security testing.

    Args:
        spec: Parsed OpenAPI / Swagger specification dict.

    Returns:
        :class:`SpecEndpoints` with discovered paths and endpoint lists.
    """
    all_endpoints = extract_endpoints(spec)
    result = SpecEndpoints(all_endpoints=all_endpoints)

    login_candidates: list[tuple[int, Endpoint]] = []   # (score, endpoint)
    user_create_candidates: list[tuple[int, Endpoint]] = []

    for ep in all_endpoints:
        # Only POST endpoints are candidates for login/signup
        if ep.method != "POST":
            # Still record secured endpoints for later use
            if ep.requires_auth:
                result.secured_endpoints.append(ep)
            continue

        # ---------------------------------------------------------------
        # Secured endpoints (authorization test targets)
        # ---------------------------------------------------------------
        if ep.requires_auth:
            result.secured_endpoints.append(ep)
            # Resource-creation endpoints
            result.resource_endpoints.append(ep)
            # Secured endpoints are generally NOT login/signup candidates
            continue

        # ---------------------------------------------------------------
        # Login endpoint heuristics
        # ---------------------------------------------------------------
        l_score = 0
        if _path_contains(ep.path, _LOGIN_KEYWORDS):
            l_score += 4
        if _path_contains(ep.path, _TOKEN_KEYWORDS):
            l_score += 3
        if _path_contains(ep.path, {"auth"}):
            l_score += 2
        
        if _body_has_user_fields(ep.body_schema):
            l_score += 2
            
        # Check for "token" in response schema if it exists
        resp_schema = ep.response_schema or {}
        if "token" in str(resp_schema).lower():
            l_score += 2
        
        if l_score >= 3:
            login_candidates.append((l_score, ep))

        # ---------------------------------------------------------------
        # User-creation endpoint heuristics
        # ---------------------------------------------------------------
        c_score = 0
        if _path_contains(ep.path, _USER_CREATE_KEYWORDS):
            c_score += 4
        if _path_contains(ep.path, _LOGIN_KEYWORDS):
            c_score -= 4 # Penalize strong login keywords
            
        if _body_has_user_fields(ep.body_schema):
            c_score += 3
        
        if c_score >= 3:
            user_create_candidates.append((c_score, ep))

    # Pick highest-scoring candidates
    if login_candidates:
        login_candidates.sort(key=lambda t: t[0], reverse=True)
        result.login_path = login_candidates[0][1].path

    if user_create_candidates:
        user_create_candidates.sort(key=lambda t: t[0], reverse=True)
        result.user_create_path = user_create_candidates[0][1].path

    return result
