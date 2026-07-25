from typing import List
from fastapi import APIRouter, Depends, HTTPException
from src.middleware.auth_middleware import require_permission, get_current_user
from src.config import prisma
from ..schema import (
    ProjectResponse,
    ProjectMetaResponse,
    CreateProjectRequest,
    UpdateProjectRequest,
)
from ..services import project_service

router = APIRouter(prefix="/projects", tags=["Projects"])

# In-memory stores (shared across project routers)
# In a real app, these should be in a shared state or DB
from ..state import _spec_store, _base_url_store, _spec_name_store

@router.get("/check-limit")
async def check_project_limit(user: dict = Depends(get_current_user)):
    tenant_id = user["tenantId"]
    subscription = await prisma.subscription.find_first(
        where={"tenantId": tenant_id},
        include={"plan": True}
    )

    if not subscription or not subscription.plan:
        return {
            "canCreate": False,
            "currentCount": 0,
            "maxProjects": 0,
            "planName": "None",
            "message": "No active subscription found"
        }

    current_count = await prisma.project.count(where={"tenantId": tenant_id})
    max_projects = subscription.plan.maxProjects
    can_create = current_count < max_projects

    return {
        "canCreate": can_create,
        "currentCount": current_count,
        "maxProjects": max_projects,
        "planName": subscription.plan.name,
        "message": (
            f"You can create {max_projects - current_count} more project(s)"
            if can_create
            else f"Project limit reached. Upgrade to create more projects."
        )
    }

@router.post("/", response_model=ProjectResponse)
async def create_project_endpoint(data: CreateProjectRequest, user: dict = Depends(get_current_user)):
    if user.get("systemRole") != "SUPER_ADMIN":
        perms = (user.get("workspacePermissions") or {}).get(data.workspaceId, [])
        if "PROJECT.CREATE" not in perms:
            raise HTTPException(status_code=403, detail="Missing required permission: PROJECT.CREATE for this workspace.")
            
    try:
        return await project_service.create_project(user["tenantId"], data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/workspace/{workspace_id}", response_model=List[ProjectResponse])
async def get_workspace_projects_endpoint(workspace_id: str, user: dict = Depends(get_current_user)):
    system_role = user.get("systemRole")
    tenant_id = user.get("tenantId")
    is_admin = system_role in ["TENANT_ADMIN", "SUPER_ADMIN"]

    return await project_service.get_workspace_projects(
        tenant_id if system_role != "SUPER_ADMIN" else None,
        workspace_id,
        user_id=user["userId"],
        is_admin=is_admin,
    )

@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(project_id: str, data: UpdateProjectRequest, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        project = await prisma.project.find_unique(where={"id": project_id})
        return ProjectResponse(**project.dict())

    updated = await prisma.project.update(
        where={"id": project_id},
        data=update_data,
    )
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        workspaceId=updated.workspaceId,
        tenantId=updated.tenantId,
        createdAt=updated.createdAt,
        updatedAt=updated.updatedAt,
    )

@router.get("/{project_id}", response_model=ProjectMetaResponse)
async def get_project_meta(project_id: str, user: dict = Depends(get_current_user)):
    return await project_service.get_project_meta_service(
        project_id, user, _spec_store, _base_url_store, _spec_name_store
    )

@router.delete("/{project_id}", status_code=204)
async def delete_project_endpoint(project_id: str, user: dict = Depends(get_current_user)):
    await project_service.verify_project_access(project_id, user)
    system_role = user.get("systemRole")
    if system_role not in {"SUPER_ADMIN", "TENANT_ADMIN"}:
        raise HTTPException(status_code=403, detail="Only administrators can delete projects")

    try:
        await prisma.project.delete(where={"id": project_id})
    except Exception as exc:
        err = str(exc).lower()
        if "foreign key" in err or "violates" in err or "restrict" in err or "constraint" in err:
            raise HTTPException(
                status_code=409,
                detail="Unable to delete project — it still has associated data. Please remove all test runs and suites first, or contact support.",
            )
        raise HTTPException(status_code=500, detail="Unable to delete project — please try again or contact support.")
    return None
