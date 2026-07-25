import logging
from typing import List
from src.config import prisma
from .schema import (
    CreateWorkspaceRequest, WorkspaceResponse,
    MemberResponse, AddMemberRequest, UpdateMemberRoleRequest,
    CreateUserByAdminRequest, CreateUserByAdminResponse, ProjectAssignmentResponse,
    UpdateProjectAssignmentsRequest, ProjectAssignment
)
from src.modules.auth.service import hash_password

logger = logging.getLogger(__name__)

async def create_workspace(tenant_id: str, user_id: str, data: CreateWorkspaceRequest) -> WorkspaceResponse:
    """
    Create a new workspace for a tenant.
    Also adds the creator as an ADMIN member of the workspace.
    """
    async with prisma.tx() as tx:
        # 1. Create the workspace
        workspace = await tx.workspace.create(
            data={
                "tenantId": tenant_id,
                "createdBy": user_id,
                "name": data.name
            }
        )

        # 2. Find the ADMIN role for this tenant/workspace (or any role named ADMIN in this tenant)
        # Roles are created per workspace in the current signup logic, but let's be robust.
        admin_role = await tx.role.find_first(
            where={
                "tenantId": tenant_id,
                "name": "ADMIN"
            }
        )

        if admin_role:
            # 3. Add creator as a member with ADMIN role
            await tx.workspacemember.create(
                data={
                    "workspaceId": workspace.id,
                    "userId": user_id,
                    "roleId": admin_role.id
                }
            )
        else:
            logger.warning(f"ADMIN role not found for tenant {tenant_id}. Membership not created for user {user_id}")

    return WorkspaceResponse(
        id=workspace.id,
        tenantId=workspace.tenantId,
        name=workspace.name,
        createdBy=workspace.createdBy,
        createdAt=workspace.createdAt,
        updatedAt=workspace.updatedAt
    )

async def update_workspace(workspace_id: str, name: str) -> WorkspaceResponse:
    """
    Update a workspace's details.
    """
    workspace = await prisma.workspace.update(
        where={"id": workspace_id},
        data={"name": name}
    )
    
    return WorkspaceResponse(
        id=workspace.id,
        tenantId=workspace.tenantId,
        name=workspace.name,
        createdBy=workspace.createdBy,
        createdAt=workspace.createdAt,
        updatedAt=workspace.updatedAt
    )

async def list_workspace_members(workspace_id: str) -> List[MemberResponse]:
    """
    List all members of a workspace with their roles.
    """
    return await prisma.workspacemember.find_many(
        where={"workspaceId": workspace_id},
        include={
            "user": {
                "include": {
                    "projectMembers": {
                        "include": {
                            "project": True,
                            "role": True
                        }
                    }
                }
            },
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

async def add_workspace_member(workspace_id: str, email: str, role_name: str, tenant_id: str):
    """
    Add a new member to a workspace.
    If user doesn't exist, this might need an invitation system.
    For now, we assume the user exists in the tenant.
    """
    user = await prisma.user.find_first(
        where={
            "email": email,
            "tenantId": tenant_id
        }
    )
    
    if not user:
        raise ValueError(f"User with email {email} not found in this tenant")
        
    role = await prisma.role.find_first(
        where={
            "tenantId": tenant_id,
            "name": role_name
        }
    )
    
    if not role:
        raise ValueError(f"Role {role_name} not found")
        
    return await prisma.workspacemember.create(
        data={
            "workspaceId": workspace_id,
            "userId": user.id,
            "roleId": role.id
        },
        include={
            "user": {
                "include": {
                    "projectMembers": {
                        "include": {
                            "project": True,
                            "role": True
                        }
                    }
                }
            },
            "role": True
        }
    )

async def update_member_role(workspace_id: str, user_id: str, role_name: str, tenant_id: str):
    """
    Update a member's role in the workspace.
    """
    role = await prisma.role.find_first(
        where={
            "tenantId": tenant_id,
            "name": role_name
        }
    )
    
    if not role:
        raise ValueError(f"Role {role_name} not found")
        
    return await prisma.workspacemember.update(
        where={
            "workspaceId_userId": {
                "workspaceId": workspace_id,
                "userId": user_id
            }
        },
        data={"roleId": role.id},
        include={"user": True, "role": True}
    )

async def get_tenant_workspaces(tenant_id: str = None) -> List[WorkspaceResponse]:
    """
    Get all workspaces for a tenant. If tenant_id is None, returns all workspaces (Super Admin).
    """
    where_clause = {}
    if tenant_id:
        where_clause["tenantId"] = tenant_id

    workspaces = await prisma.workspace.find_many(
        where=where_clause,
        order={"createdAt": "desc"}
    )
    return [
        WorkspaceResponse(
            id=w.id,
            tenantId=w.tenantId,
            name=w.name,
            createdBy=w.createdBy,
            createdAt=w.createdAt,
            updatedAt=w.updatedAt
        ) for w in workspaces
    ]


async def update_project_assignments(
    user_id: str,
    assignments: List[ProjectAssignment]
) -> List[ProjectAssignmentResponse]:
    """
    Replace all ProjectMember records for a user with the new set.
    Runs in a transaction: delete all existing, then insert new ones.
    """
    async with prisma.tx() as tx:
        # Remove all existing project memberships for this user
        await tx.projectmember.delete_many(where={"userId": user_id})
        # Insert new assignments
        results: List[ProjectAssignmentResponse] = []
        for a in assignments:
            pm = await tx.projectmember.create(data={
                "projectId": a.projectId,
                "userId": user_id,
                "roleId": a.roleId,
            })
            results.append(ProjectAssignmentResponse(projectId=pm.projectId, roleId=pm.roleId))
    return results


async def create_user_by_admin(
    workspace_id: str,
    tenant_id: str,
    data: CreateUserByAdminRequest,
    inviter_id: str
) -> CreateUserByAdminResponse:
    """
    Admin creates a brand-new user account within their tenant.
    Steps (all in one transaction):
      1. Validate email uniqueness within the tenant
      2. Hash password and create User record with isVerified: False
      3. Find the workspace-level role by name
      4. Create WorkspaceMember record
      5. Create ProjectMember records for each project assignment
      6. Create a PENDING Invitation record and send invitation email
    """
    import secrets
    from datetime import datetime, timedelta
    from src.services.email_service import send_invitation_email
    from src.config.settings import settings

    # Check email uniqueness within tenant
    existing = await prisma.user.find_first(
        where={"email": data.email, "tenantId": tenant_id}
    )
    if existing:
        raise ValueError(f"A user with email '{data.email}' already exists in this organisation.")

    password_hash = hash_password(data.password)
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    async with prisma.tx() as tx:
        # 1. Create the user as unverified (invited state)
        user = await tx.user.create(
            data={
                "tenantId": tenant_id,
                "email": data.email,
                "name": data.name,
                "passwordHash": password_hash,
                "company": data.company,
                "contactNumber": data.contactNumber,
                "systemRole": data.systemRole,
                "isVerified": False,
            }
        )

        # 2. Resolve workspace-level role
        role_to_find = (data.workspaceRoleName or "TESTER").upper()
        workspace_role = await tx.role.find_first(
            where={
                "tenantId": tenant_id,
                "name": role_to_find
            }
        )
        if not workspace_role:
            raise ValueError(f"Workspace role '{data.workspaceRoleName}' not found for this organisation.")

        # 3. Add as workspace member
        ws_member = await tx.workspacemember.create(
            data={
                "workspaceId": workspace_id,
                "userId": user.id,
                "roleId": workspace_role.id,
            }
        )

        # 4. Create per-project memberships
        project_assignment_responses: list[ProjectAssignmentResponse] = []
        for assignment in data.projectAssignments:
            await tx.projectmember.create(
                data={
                    "projectId": assignment.projectId,
                    "userId": user.id,
                    "roleId": assignment.roleId,
                }
            )
            project_assignment_responses.append(
                ProjectAssignmentResponse(
                    projectId=assignment.projectId,
                    roleId=assignment.roleId,
                )
            )

        # 5. Create Invitation record
        await tx.invitation.create(
            data={
                "email": data.email,
                "roleId": workspace_role.id,
                "workspaceId": workspace_id,
                "projectId": data.projectAssignments[0].projectId if data.projectAssignments else None,
                "token": token,
                "status": "PENDING",
                "message": data.inviteMessage or "You have been invited to join the workspace.",
                "inviterId": inviter_id,
                "expiresAt": expires_at,
            }
        )

    # Send invitation email after transaction completes successfully
    inviter = await prisma.user.find_unique(where={"id": inviter_id})
    inviter_name = (inviter.name if inviter else None) or inviter.email or "An Administrator"
    
    workspace = await prisma.workspace.find_unique(where={"id": workspace_id})
    workspace_name = (workspace.name if workspace else None) or "Workspace"

    invite_url = f"{settings.frontend_url}/invite?token={token}"
    try:
        send_invitation_email(
            recipient_email=data.email,
            inviter_name=inviter_name,
            workspace_name=workspace_name,
            invite_url=invite_url,
            message=data.inviteMessage
        )
    except Exception as e:
        logger.error(f"Failed to send invitation email to {data.email}: {e}")

    logger.info(
        f"Admin created new user '{data.email}' in tenant {tenant_id}. "
        f"Workspace member id: {ws_member.id}. "
        f"Project assignments: {len(project_assignment_responses)}"
    )

    return CreateUserByAdminResponse(
        userId=user.id,
        name=user.name,
        email=user.email,
        systemRole=user.systemRole,
        workspaceMemberId=ws_member.id,
        projectAssignments=project_assignment_responses,
    )
