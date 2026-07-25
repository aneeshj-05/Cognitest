from fastapi import APIRouter, Depends, HTTPException
from typing import List
from src.middleware.auth_middleware import get_current_user
from src.config import prisma
from .schema import RoleCreate, RolePermissionUpdate, RoleResponse, PermissionResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roles", tags=["Roles"])


def _map_role(role) -> RoleResponse:
    perms = []
    for rp in (role.permissions or []):
        p = rp.permission
        if p:
            perms.append(PermissionResponse(
                id=p.id,
                name=p.name,
                resource=p.resource,
                action=p.action,
                description=p.description,
            ))
    return RoleResponse(
        id=role.id,
        name=role.name,
        description=role.description,
        tenantId=role.tenantId,
        workspaceId=role.workspaceId,
        createdAt=role.createdAt,
        permissions=perms,
    )


@router.get("/", response_model=List[RoleResponse])
async def list_roles(user: dict = Depends(get_current_user)):
    """
    List all roles for the current user's tenant, including attached permissions.
    """
    tenant_id = user.get("tenantId")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")

    roles = await prisma.role.find_many(
        where={"tenantId": tenant_id},
        include={
            "permissions": {
                "include": {"permission": True}
            }
        },
        order={"createdAt": "asc"},
    )
    return [_map_role(r) for r in roles]


@router.post("/", response_model=RoleResponse)
async def create_role(data: RoleCreate, user: dict = Depends(get_current_user)):
    """
    Create a new role for the current tenant.
    """
    tenant_id = user.get("tenantId")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")

    role = await prisma.role.create(
        data={
            "tenantId": tenant_id,
            "name": data.name,
            "description": data.description,
        },
        include={
            "permissions": {
                "include": {"permission": True}
            }
        },
    )
    return _map_role(role)


@router.delete("/{role_id}", status_code=204)
async def delete_role(role_id: str, user: dict = Depends(get_current_user)):
    """
    Delete a role by ID. Validates it belongs to the current tenant.
    """
    tenant_id = user.get("tenantId")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")

    role = await prisma.role.find_first(
        where={"id": role_id, "tenantId": tenant_id}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    # Remove all RolePermission mappings first
    await prisma.rolepermission.delete_many(where={"roleId": role_id})

    # Delete workspace members that use this role to avoid FK constraint error
    await prisma.workspacemember.delete_many(where={"roleId": role_id})

    await prisma.role.delete(where={"id": role_id})


@router.patch("/{role_id}/permissions", response_model=RoleResponse)
async def update_role_permissions(
    role_id: str,
    data: RolePermissionUpdate,
    user: dict = Depends(get_current_user),
):
    """
    Replace all permissions on a role with the supplied list of permission IDs.
    """
    tenant_id = user.get("tenantId")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="User is not associated with a tenant")

    role = await prisma.role.find_first(
        where={"id": role_id, "tenantId": tenant_id}
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    async with prisma.tx() as tx:
        # Remove existing permissions for this role
        await tx.rolepermission.delete_many(where={"roleId": role_id})

        # Add new permissions
        for perm_id in data.permissionIds:
            await tx.rolepermission.create(
                data={"roleId": role_id, "permissionId": perm_id}
            )

    # Return updated role with permissions
    updated = await prisma.role.find_unique(
        where={"id": role_id},
        include={
            "permissions": {
                "include": {"permission": True}
            }
        },
    )
    return _map_role(updated)


@router.get("/permissions", response_model=list)
async def list_all_permissions(user: dict = Depends(get_current_user)):
    """
    List all available system permissions.
    """
    perms = await prisma.permission.find_many(order={"resource": "asc"})
    return [
        {
            "id": p.id,
            "name": p.name,
            "resource": p.resource,
            "action": p.action,
            "description": p.description,
        }
        for p in perms
    ]
