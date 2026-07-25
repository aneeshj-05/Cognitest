from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List, Dict

class SignupRequest(BaseModel):
    email: EmailStr
    name: str
    passcode: str = Field(..., min_length=6)
    company: Optional[str] = None  # Optional if inviteToken is present
    contactNumber: Optional[str] = None
    inviteToken: Optional[str] = None

    @field_validator('name')
    @classmethod
    def name_must_be_alpha(cls, v: str) -> str:
        import re
        if not re.match(r'^[A-Za-z0-9\s]+$', v.strip()):
            raise ValueError('Name must contain only letters, numbers and spaces')
        return v

    @field_validator('passcode')
    @classmethod
    def truncate_password(cls, v: str) -> str:
        password_bytes = v.encode('utf-8')
        if len(password_bytes) > 72:
            return password_bytes[:72].decode('utf-8', errors='ignore')
        return v

class TenantResponse(BaseModel):
    id: str
    name: str
    status: str

class ProjectShortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str

class RoleShortResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str

class UserProjectMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    projectId: str
    roleId: Optional[str] = None
    project: Optional[ProjectShortResponse] = None
    role: Optional[RoleShortResponse] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tenantId: Optional[str] = None
    email: str
    name: Optional[str] = None
    systemRole: str
    company: Optional[str] = None
    contactNumber: Optional[str] = None
    projectMembers: List[UserProjectMemberResponse] = []

class WorkspaceResponse(BaseModel):
    id: str
    tenantId: str
    name: str
    createdBy: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    tenantId: str
    workspaceId: str
    name: str
    description: Optional[str] = None

class SubscriptionResponse(BaseModel):
    id: str
    planId: str
    status: str
    expiryDate: str

class SignupResponse(BaseModel):
    token: str
    user: UserResponse
    tenant: TenantResponse
    workspace: Optional[WorkspaceResponse] = None
    project: Optional[ProjectResponse] = None
    subscription: Optional[SubscriptionResponse] = None

class LoginRequest(BaseModel):
    email: EmailStr
    passcode: str
    inviteToken: Optional[str] = None

class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    tenant: Optional[TenantResponse] = None
    workspace: Optional[WorkspaceResponse] = None
    subscription: Optional[SubscriptionResponse] = None

class ChangePasswordRequest(BaseModel):
    currentPassword: str
    newPassword: str = Field(..., min_length=6)

class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6)
    inviteToken: Optional[str] = None

class SignupInitialResponse(BaseModel):
    message: str
    email: str
