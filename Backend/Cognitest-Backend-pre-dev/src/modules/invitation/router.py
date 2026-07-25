import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.config import prisma, settings
from src.middleware.auth_middleware import get_current_user
from src.services.email_service import send_invitation_email
from .schema import (
    CreateInvitationPayload,
    InvitationResponse,
    ValidationResponse,
    FullInvitationResponse,
    InvitationDetail,
    RoleShort,
    ProjectShort,
    WorkspaceShort,
    InviterShort,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/invitations", tags=["Invitations"])

@router.post("", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    data: CreateInvitationPayload,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new user invitation, and send them an email to sign up/join.
    """
    workspace_id = data.workspaceId
    if not workspace_id:
        raise HTTPException(
            status_code=400,
            detail="workspaceId is required to invite a member."
        )

    # 1. Fetch workspace to make sure it exists
    workspace = await prisma.workspace.find_unique(where={"id": workspace_id})
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # 2. Check if recipient is already a member of this workspace
    # Retrieve user by email
    target_user = await prisma.user.find_first(where={"email": data.email})
    if target_user:
        existing_member = await prisma.workspacemember.find_unique(
            where={
                "workspaceId_userId": {
                    "workspaceId": workspace_id,
                    "userId": target_user.id
                }
            }
        )
        if existing_member:
            raise HTTPException(
                status_code=400,
                detail=f"User with email {data.email} is already a member of this workspace."
            )

    # 3. Create invitation
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(days=7)

    invitation = await prisma.invitation.create(
        data={
            "email": data.email,
            "roleId": data.roleId,
            "workspaceId": workspace_id,
            "projectId": data.projectId,
            "token": token,
            "status": "PENDING",
            "message": data.message,
            "inviterId": current_user["userId"],
            "expiresAt": expires_at,
        }
    )

    # 4. Send email
    inviter = await prisma.user.find_unique(where={"id": current_user["userId"]})
    inviter_name = (inviter.name if inviter else None) or inviter.email or "An Administrator"
    invite_url = f"{settings.frontend_url}/invite?token={token}"

    try:
        send_invitation_email(
            recipient_email=data.email,
            inviter_name=inviter_name,
            workspace_name=workspace.name,
            invite_url=invite_url,
            message=data.message
        )
    except Exception as e:
        logger.error(f"Failed to send invitation email to {data.email}: {e}")

    return InvitationResponse(
        id=invitation.id,
        email=invitation.email,
        roleId=invitation.roleId,
        status=invitation.status,
        token=invitation.token
    )


@router.get("", response_model=List[FullInvitationResponse])
async def list_invitations(
    workspace_id: Optional[str] = Query(None, alias="workspace_id"),
    project_id: Optional[str] = Query(None, alias="project_id"),
    current_user: dict = Depends(get_current_user)
):
    """
    List all invitations. Optionally filter by workspace_id and/or project_id.
    """
    where_filter = {}
    if workspace_id:
        where_filter["workspaceId"] = workspace_id
    if project_id:
        where_filter["projectId"] = project_id

    # If no filters, enforce listing only invitations for workspaces the user has access to
    if not workspace_id and not project_id:
        if current_user.get("systemRole") != "SUPER_ADMIN":
            user_workspaces = list((current_user.get("workspacePermissions") or {}).keys())
            where_filter["workspaceId"] = {"in": user_workspaces}

    invitations = await prisma.invitation.find_many(
        where=where_filter,
        order={"createdAt": "desc"}
    )

    return [
        FullInvitationResponse(
            id=inv.id,
            email=inv.email,
            roleId=inv.roleId,
            status=inv.status,
            token=inv.token,
            createdAt=inv.createdAt,
            expiresAt=inv.expiresAt,
            inviterId=inv.inviterId,
            projectId=inv.projectId,
            workspaceId=inv.workspaceId
        )
        for inv in invitations
    ]


@router.get("/{token}/validate", response_model=ValidationResponse)
async def validate_invitation(token: str):
    """
    Validate an invitation token and return details about the invite.
    """
    inv = await prisma.invitation.find_unique(
        where={"token": token},
        include={
            "workspace": True,
            "project": True,
            "role": True,
            "inviter": True
        }
    )

    if not inv:
        return ValidationResponse(
            valid=False,
            message="Invitation not found."
        )

    if inv.status != "PENDING":
        return ValidationResponse(
            valid=False,
            message=f"Invitation has already been {inv.status.lower()}."
        )

    # Expiry comparison
    now = datetime.utcnow()
    expires_at = inv.expiresAt.replace(tzinfo=None) if inv.expiresAt.tzinfo else inv.expiresAt
    if expires_at < now:
        return ValidationResponse(
            valid=False,
            message="Invitation has expired."
        )

    # Build response detail
    role_info = RoleShort(id=inv.role.id, name=inv.role.name)
    proj_info = ProjectShort(id=inv.project.id, name=inv.project.name) if inv.project else None
    ws_info = WorkspaceShort(id=inv.workspace.id, name=inv.workspace.name) if inv.workspace else None
    inviter_info = InviterShort(id=inv.inviter.id, name=inv.inviter.name, email=inv.inviter.email) if inv.inviter else None

    detail = InvitationDetail(
        email=inv.email,
        role=role_info,
        project=proj_info,
        workspace=ws_info,
        inviter=inviter_info,
        expiresAt=inv.expiresAt
    )

    return ValidationResponse(
        valid=True,
        message="Invitation is valid.",
        invitation=detail
    )


@router.post("/{token}/accept")
async def accept_invitation(
    token: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Accept an invitation, adding the user to the workspace/project.
    """
    inv = await prisma.invitation.find_unique(
        where={"token": token},
        include={"workspace": True}
    )

    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if inv.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Invitation has already been {inv.status.lower()}."
        )

    now = datetime.utcnow()
    expires_at = inv.expiresAt.replace(tzinfo=None) if inv.expiresAt.tzinfo else inv.expiresAt
    if expires_at < now:
        raise HTTPException(status_code=400, detail="Invitation has expired.")

    # Match email
    # Check case-insensitive
    if current_user["email"].lower() != inv.email.lower():
        raise HTTPException(
            status_code=400,
            detail=f"This invitation is for {inv.email}, but you are logged in as {current_user['email']}."
        )

    # 1. Update invitation status
    await prisma.invitation.update(
        where={"id": inv.id},
        data={"status": "ACCEPTED"}
    )

    # 2. Join user to Workspace (if workspaceId is present)
    if inv.workspaceId:
        existing_wm = await prisma.workspacemember.find_unique(
            where={
                "workspaceId_userId": {
                    "workspaceId": inv.workspaceId,
                    "userId": current_user["userId"]
                }
            }
        )
        if not existing_wm:
            await prisma.workspacemember.create(
                data={
                    "workspaceId": inv.workspaceId,
                    "userId": current_user["userId"],
                    "roleId": inv.roleId
                }
            )

    # 3. Join user to Project (if projectId is present)
    if inv.projectId:
        existing_pm = await prisma.projectmember.find_unique(
            where={
                "projectId_userId": {
                    "projectId": inv.projectId,
                    "userId": current_user["userId"]
                }
            }
        )
        if not existing_pm:
            await prisma.projectmember.create(
                data={
                    "projectId": inv.projectId,
                    "userId": current_user["userId"],
                    "roleId": inv.roleId
                }
            )

    # 4. Verify user in database just in case they were unverified
    await prisma.user.update(
        where={"id": current_user["userId"]},
        data={"isVerified": True}
    )

    return {"message": "Invitation accepted successfully", "invitationId": inv.id}


@router.post("/{invitation_id}/revoke", response_model=InvitationResponse)
async def revoke_invitation(
    invitation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Revoke an invitation.
    """
    inv = await prisma.invitation.find_unique(where={"id": invitation_id})
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if inv.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Only pending invitations can be revoked. Current status: {inv.status}"
        )

    updated = await prisma.invitation.update(
        where={"id": invitation_id},
        data={"status": "REVOKED"}
    )

    return InvitationResponse(
        id=updated.id,
        email=updated.email,
        roleId=updated.roleId,
        status=updated.status,
        token=updated.token
    )


@router.post("/{invitation_id}/resend", response_model=InvitationResponse)
async def resend_invitation_endpoint(
    invitation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Resend a pending invitation, renewing its expiry.
    """
    inv = await prisma.invitation.find_unique(
        where={"id": invitation_id},
        include={"workspace": True}
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Invitation not found.")

    if inv.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=f"Only pending invitations can be resent. Current status: {inv.status}"
        )

    # Update expiry
    new_expiry = datetime.utcnow() + timedelta(days=7)
    updated = await prisma.invitation.update(
        where={"id": invitation_id},
        data={"expiresAt": new_expiry}
    )

    # Send email
    inviter = await prisma.user.find_unique(where={"id": current_user["userId"]})
    inviter_name = (inviter.name if inviter else None) or inviter.email or "An Administrator"
    invite_url = f"{settings.frontend_url}/invite?token={updated.token}"

    try:
        send_invitation_email(
            recipient_email=updated.email,
            inviter_name=inviter_name,
            workspace_name=inv.workspace.name if inv.workspace else "Workspace",
            invite_url=invite_url,
            message=updated.message
        )
    except Exception as e:
        logger.error(f"Failed to resend invitation email to {updated.email}: {e}")

    return InvitationResponse(
        id=updated.id,
        email=updated.email,
        roleId=updated.roleId,
        status=updated.status,
        token=updated.token
    )
