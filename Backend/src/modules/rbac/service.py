from typing import Dict, List
from src.config import prisma

async def get_user_workspace_permissions(user_id: str) -> Dict[str, List[str]]:
    """
    Compute all workspace-scoped permissions for a user.
    Returns: { workspace_id: ["resource.action", ...] }
    """
    # Fetch workspace memberships join roles join permissions
    memberships = await prisma.workspacemember.find_many(
        where={"userId": user_id},
        include={
            "role": {
                "include": {
                    "permissions": {
                        "include": {
                            "permission": True
                        }
                    }
                }
            }
        }
    )

    workspace_permissions = {}
    for member in memberships:
        ws_id = member.workspaceId
        role = member.role
        
        if ws_id not in workspace_permissions:
            workspace_permissions[ws_id] = []
            
        for rp in role.permissions:
            perm = rp.permission
            perm_string = f"{perm.resource}.{perm.action}"
            if perm_string not in workspace_permissions[ws_id]:
                workspace_permissions[ws_id].append(perm_string)
                
    return workspace_permissions

async def check_permission(user_id: str, workspace_id: str, required_permission: str) -> bool:
    """
    Helper to check permission directly from DB (if not using JWT cache)
    """
    permissions = await get_user_workspace_permissions(user_id)
    ws_perms = permissions.get(workspace_id, [])
    return required_permission in ws_perms
