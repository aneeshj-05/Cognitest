from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class CreateInvitationPayload(BaseModel):
    email: EmailStr
    roleId: str
    workspaceId: Optional[str] = None
    projectId: Optional[str] = None
    message: Optional[str] = None

class InvitationResponse(BaseModel):
    id: str
    email: str
    roleId: str
    status: str
    token: str

class RoleShort(BaseModel):
    id: str
    name: str

class ProjectShort(BaseModel):
    id: str
    name: str

class WorkspaceShort(BaseModel):
    id: str
    name: str

class InviterShort(BaseModel):
    id: str
    name: Optional[str] = None
    email: str

class InvitationDetail(BaseModel):
    email: str
    role: RoleShort
    project: Optional[ProjectShort] = None
    workspace: Optional[WorkspaceShort] = None
    inviter: Optional[InviterShort] = None
    expiresAt: datetime

class ValidationResponse(BaseModel):
    valid: bool
    message: str
    invitation: Optional[InvitationDetail] = None

class FullInvitationResponse(BaseModel):
    id: str
    email: str
    roleId: str
    status: str
    token: str
    createdAt: datetime
    expiresAt: datetime
    inviterId: str
    projectId: Optional[str] = None
    workspaceId: Optional[str] = None
