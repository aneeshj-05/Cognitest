from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class CreateWorkspaceRequest(BaseModel):
    name: str

class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenantId: Optional[str]
    name: str
    createdBy: Optional[str]
    createdAt: datetime
    updatedAt: datetime

from src.modules.auth.schema import UserResponse
from src.modules.roles.schema import RoleResponse

class MemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workspaceId: str
    userId: str
    roleId: str
    user: Optional[UserResponse] = None
    role: Optional[RoleResponse] = None

class AddMemberRequest(BaseModel):
    email: str
    roleName: str

class UpdateMemberRoleRequest(BaseModel):
    roleName: str

# ── Admin: Create a brand-new user account ───────────────────────────────────

class ProjectAssignment(BaseModel):
    """A single project + the role the new user should have on that project."""
    projectId: str
    roleId: str  # DB role id (uuid) for this project assignment

class CreateUserByAdminRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=6)
    company: Optional[str] = None
    contactNumber: Optional[str] = None
    systemRole: str = "USER"            # "USER" | "TENANT_ADMIN"
    workspaceRoleName: Optional[str] = "TESTER"   # workspace-level role name e.g. TESTER, QA, ADMIN
    projectAssignments: List[ProjectAssignment] = []
    inviteMessage: Optional[str] = None
    sendInAppNotification: bool = True

class ProjectAssignmentResponse(BaseModel):
    projectId: str
    roleId: str

class CreateUserByAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    userId: str
    name: Optional[str]
    email: str
    systemRole: str
    workspaceMemberId: str
    projectAssignments: List[ProjectAssignmentResponse] = []

class UpdateProjectAssignmentsRequest(BaseModel):
    """Replace all project assignments for a user with the new list."""
    assignments: List[ProjectAssignment] = []
