import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

def rehydrate_security_meta(case: dict) -> dict:
    """
    Ensure a test case has its security metadata hydrated from the 'metadata' field.
    """
    metadata = case.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = None
    if isinstance(metadata, dict):
        for key in ("owasp_category", "requires_stateful", "requires_auth", "auth_negative", "kind", "expected_status", "expected", "failure_category"):
            if key in metadata and key not in case:
                case[key] = metadata[key]

    assertions = case.get("assertions") or []
    if isinstance(assertions, list):
        for a in assertions:
            if isinstance(a, str) and a.startswith("__security_meta__="):
                try:
                    meta = json.loads(a.split("=", 1)[1])
                    case.update(meta)
                except Exception:
                    pass
                break
    return case

def normalize_token(token: str | None) -> str | None:
    """
    Remove 'Bearer ' prefix and whitespace from a token.
    """
    if not token: return None
    t = str(token).strip()
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t or None

def resolve_auth_headers(case: dict, ctx: Any = None, manual_token: str | None = None) -> dict[str, str]:
    """
    Decide exactly what auth headers go into the request.
    SINGLE SOURCE OF TRUTH.
    """
    case = rehydrate_security_meta(case)

    # 1. Explicit negative auth test (Highest priority)
    if case.get("auth_negative") or case.get("kind") in ("negative_auth_missing",):
        return {}

    # 2. Manual override (User provided a token in the UI)
    if manual_token:
        token = normalize_token(manual_token)
        if token:
            return {"Authorization": f"Bearer {token}"}

    # 3. Stateful cases (AuthZ / BOLA)
    requires_stateful = bool(case.get("requires_stateful"))
    if requires_stateful and ctx:
        # BOLA tests typically use Token B (attacker)
        if hasattr(ctx, "auth_header_b"):
            return ctx.auth_header_b()
        if isinstance(ctx, dict) and ctx.get("token_b"):
            return {"Authorization": f"Bearer {ctx['token_b']}"}

    # 4. Normal auth-required case
    if case.get("requires_auth") and ctx:
        if hasattr(ctx, "auth_header_a"):
            return ctx.auth_header_a()
        if isinstance(ctx, dict) and ctx.get("token_a"):
            return {"Authorization": f"Bearer {ctx['token_a']}"}

    return {}
