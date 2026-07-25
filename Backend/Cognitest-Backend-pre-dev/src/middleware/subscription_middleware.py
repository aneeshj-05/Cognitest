from fastapi import Depends, HTTPException, status
from .auth_middleware import get_current_user
from src.config import prisma

async def check_subscription(payload: dict = Depends(get_current_user)):
    """
    Dependency to check if tenant has an ACTIVE subscription.
    """
    tenant_id = payload.get("tenantId")
    system_role = payload.get("systemRole")

    # Super Admins bypass subscription checks
    if system_role == "SUPER_ADMIN":
        return None  # Or return a dummy object if needed, but None usually signals "skip" or "all access"

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant ID missing in token")

    tenant = await prisma.tenant.find_unique(where={"id": tenant_id})
    if not tenant or tenant.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tenant account is not active")

    subscription = await prisma.subscription.find_first(
        where={"tenantId": tenant_id},
        include={"plan": True}
    )
    
    if not subscription or subscription.status != "ACTIVE":
        raise HTTPException(status_code=403, detail="No active subscription found")

    return subscription

async def check_plan_limits(limit_type: str, workspace_id: str = None):
    """
    Dependency factory to check specific plan limits.
    """
    async def limit_checker(subscription = Depends(check_subscription), payload: dict = Depends(get_current_user)):
        # Super Admins bypass plan limit checks
        if payload.get("systemRole") == "SUPER_ADMIN":
            return True

        plan = subscription.plan
        tenant_id = subscription.tenantId
        
        if limit_type == "maxProjects":
            count = await prisma.project.count(where={"tenantId": tenant_id})
            if count >= plan.maxProjects:
                raise HTTPException(status_code=403, detail="Project limit reached for your plan")
        
        elif limit_type == "maxUsers":
            count = await prisma.user.count(where={"tenantId": tenant_id})
            if count >= plan.maxUsers:
                raise HTTPException(status_code=403, detail="User limit reached for your plan")
                
        # Add other limits as needed
        return True
        
    return limit_checker
