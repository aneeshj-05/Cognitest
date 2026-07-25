from fastapi import APIRouter, Depends, HTTPException
from typing import List
from .schema import (
    CreateWorkspaceRequest, WorkspaceResponse,
    MemberResponse, AddMemberRequest, UpdateMemberRoleRequest,
    CreateUserByAdminRequest, CreateUserByAdminResponse,
    UpdateProjectAssignmentsRequest,
)
from . import service
from src.middleware.auth_middleware import get_current_user, require_permission

router = APIRouter(prefix="/workspaces", tags=["Workspaces"])


@router.post("/", response_model=WorkspaceResponse)
async def create_workspace_endpoint(data: CreateWorkspaceRequest, user: dict = Depends(get_current_user)):
    """
    Create a new workspace.
    """
    if not user.get("tenantId"):
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
    
    return await service.create_workspace(user["tenantId"], user["userId"], data)

@router.get("/", response_model=List[WorkspaceResponse])
async def list_workspaces_endpoint(user: dict = Depends(get_current_user)):
    """
    List all workspaces. If SUPER_ADMIN, lists all workspaces in the system.
    Otherwise, lists all workspaces for the current user's tenant.
    """
    system_role = user.get("systemRole")
    tenant_id = user.get("tenantId")

    if system_role == "SUPER_ADMIN":
        return await service.get_tenant_workspaces(None)

    if not tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
        
    return await service.get_tenant_workspaces(tenant_id)

@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace_endpoint(
    workspace_id: str, 
    data: CreateWorkspaceRequest, 
    user: dict = Depends(get_current_user)
):
    """
    Update a workspace name.
    """
    if not user.get("tenantId"):
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
    
    return await service.update_workspace(workspace_id, data.name)

@router.get("/{workspace_id}/members", response_model=List[MemberResponse])
async def list_members_endpoint(
    workspace_id: str,
    user: dict = Depends(get_current_user)
):
    """
    List all members of a workspace.
    """
    return await service.list_workspace_members(workspace_id)

@router.post("/{workspace_id}/members", response_model=MemberResponse)
async def add_member_endpoint(
    workspace_id: str,
    data: AddMemberRequest,
    user: dict = Depends(get_current_user)
):
    """
    Add an existing user as a member to a workspace.
    """
    try:
        return await service.add_workspace_member(
            workspace_id, 
            data.email, 
            data.roleName, 
            user["tenantId"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberResponse)
async def update_member_role_endpoint(
    workspace_id: str,
    user_id: str,
    data: UpdateMemberRoleRequest,
    user: dict = Depends(get_current_user)
):
    """
    Update a member's role.
    """
    try:
        return await service.update_member_role(
            workspace_id,
            user_id,
            data.roleName,
            user["tenantId"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{workspace_id}/members/create-user", response_model=CreateUserByAdminResponse, status_code=201)
async def create_user_by_admin_endpoint(
    workspace_id: str,
    data: CreateUserByAdminRequest,
    user: dict = Depends(get_current_user)
):
    """
    Admin creates a brand-new user account, assigns a workspace role,
    and optionally assigns per-project roles — all in one request.
    """
    if not user.get("tenantId"):
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")
    try:
        return await service.create_user_by_admin(workspace_id, user["tenantId"], data, user["userId"])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{workspace_id}/members/{user_id}/project-assignments")
async def update_project_assignments_endpoint(
    workspace_id: str,
    user_id: str,
    data: UpdateProjectAssignmentsRequest,
    user: dict = Depends(get_current_user)
):
    """
    Replace all project assignments for a member with the new list.
    Existing ProjectMember records are deleted and replaced atomically.
    """
    try:
        results = await service.update_project_assignments(user_id, data.assignments)
        return {"userId": user_id, "projectAssignments": [r.dict() for r in results]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
