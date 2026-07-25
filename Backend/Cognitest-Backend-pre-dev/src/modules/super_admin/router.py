"""Super Admin API endpoints.

Thin controller layer — all business logic is in `service.py`.
"""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from src.config import prisma
from src.middleware.auth_middleware import get_current_user
from . import service
from .schema import CreateTenantRequest, UpdateTenantRequest, UpdateStatusRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/super-admin", tags=["Super Admin"])


def _require_super_admin(current_user: dict) -> None:
    """Raise 403 if the caller is not a SUPER_ADMIN."""
    if current_user.get("systemRole") != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Not authorized")


# ─── Dashboard Stats ─────────────────────────────────────────────────────────

@router.get("/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """Global statistics for the Super Admin dashboard."""
    _require_super_admin(current_user)
    return await service.get_dashboard_stats()


# ─── Tenants List ────────────────────────────────────────────────────────────

@router.get("/tenants")
async def get_all_tenants(current_user: dict = Depends(get_current_user)):
    """Fetch all tenants with their details."""
    _require_super_admin(current_user)
    try:
        return await service.get_all_tenants()
    except Exception:
        logger.exception("Failed to fetch tenants")
        raise


# ─── Test System Stats ───────────────────────────────────────────────────────

@router.get("/test-stats")
async def get_test_system_stats(current_user: dict = Depends(get_current_user)):
    """Aggregate test statistics across all tenants for the Test System page."""
    _require_super_admin(current_user)
    return await service.get_test_system_stats()


# ─── Billing Stats ───────────────────────────────────────────────────────────

@router.get("/billing-stats")
async def get_billing_stats(current_user: dict = Depends(get_current_user)):
    """Aggregate billing/subscription statistics."""
    _require_super_admin(current_user)
    return await service.get_billing_stats()


# ─── Create Tenant ───────────────────────────────────────────────────────────

@router.post("/tenants")
async def create_tenant(
    data: CreateTenantRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    try:
        return await service.create_tenant(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── Update Tenant ───────────────────────────────────────────────────────────

@router.patch("/tenants/{id}")
async def update_tenant(
    id: str,
    data: UpdateTenantRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    return await service.update_tenant(id, data)


# ─── Toggle Tenant Status ────────────────────────────────────────────────────

@router.patch("/tenants/{id}/status")
async def update_tenant_status(
    id: str,
    data: UpdateStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    if not data.status:
        raise HTTPException(status_code=400, detail="Status is required")
    return await service.update_tenant_status(id, data.status)


# ─── Delete Tenant ───────────────────────────────────────────────────────────

@router.delete("/tenants/{id}")
async def delete_tenant(id: str, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    try:
        return await service.delete_tenant(id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete tenant: {str(e)}"
        )


# ─── Toggle User Status ──────────────────────────────────────────────────────

@router.patch("/users/{id}/status")
async def update_user_status(
    id: str,
    data: UpdateStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    _require_super_admin(current_user)
    if not data.status:
        raise HTTPException(status_code=400, detail="Status is required")

    result = await service.update_user_status(id, data.status)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ─── Delete Project ──────────────────────────────────────────────────────────

@router.delete("/projects/{id}")
async def delete_project(id: str, current_user: dict = Depends(get_current_user)):
    _require_super_admin(current_user)
    try:
        return await service.delete_project(id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete project: {str(e)}"
        )


# ─── Token Usage Analytics ───────────────────────────────────────────────────

def _token_log_path() -> Path:
    """Resolve the JSONL token usage log file path."""
    backend_root = Path(__file__).resolve().parents[3]  # …/Cognitest-Backend
    return backend_root / "logs" / "ai_token_usage.jsonl"


@router.get("/token-usage")
async def get_token_usage(current_user: dict = Depends(get_current_user)):
    """
    Read and return all AI token usage entries from the JSONL log file.
    Returns an empty list if the file does not exist yet.
    """
    _require_super_admin(current_user)

    log_path = _token_log_path()
    if not log_path.exists():
        return {"entries": [], "total": 0}

    entries = []
    try:
        with log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("[TokenUsage] Skipping malformed line: %s", line[:120])
    except Exception as exc:
        logger.exception("[TokenUsage] Failed to read log file: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to read token usage log")

    return {"entries": entries, "total": len(entries)}
