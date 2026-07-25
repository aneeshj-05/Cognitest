"""
Gateway proxy router.

Security hardening:
- Requires authentication (get_current_user) — no anonymous access.
- Validates the resolved target host via the shared egress guard
  (IP range check + DNS rebinding prevention) before forwarding any request.
- Strips hop-by-hop headers before forwarding.
"""
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.config import settings
from src.middleware.auth_middleware import get_current_user
from src.utils.egress_guard import validate_egress_url, SsrfBlockedError, build_pinned_transport

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gateway", tags=["Gateway"])


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_request(
    request: Request,
    path: str,
    _user: dict = Depends(get_current_user),   # authentication required
) -> Response:
    """
    Authenticated proxy to TARGET_SERVICE_URL.

    Only forwards requests when:
    1. The caller presents a valid JWT (Depends(get_current_user)).
    2. The resolved target host is in GATEWAY_ALLOWED_HOSTS.
    """
    # ── SSRF guard: validate target URL (IP range + DNS rebinding) ───────
    try:
        guard = validate_egress_url(settings.target_service_url)
        # Use original URL (not IP-substituted) for correct TLS/vhost behaviour.
        # The pinned transport connects TCP to guard.pinned_ip without re-resolving.
        target_url = f"{guard.url.rstrip('/')}/{path}"
    except SsrfBlockedError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    body: Optional[bytes] = None
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()

    # Strip hop-by-hop / host headers
    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "connection", "transfer-encoding")
    }

    try:
        transport = build_pinned_transport(guard)
        async with httpx.AsyncClient(transport=transport, timeout=2.0) as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type"),
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gateway timeout — target service too slow")
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Bad gateway — could not connect to target service")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[Gateway] Proxy error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Bad gateway")
