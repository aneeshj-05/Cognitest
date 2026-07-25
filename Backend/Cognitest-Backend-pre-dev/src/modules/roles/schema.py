from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List
from datetime import datetime


class PermissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    resource: str
    action: str
    description: Optional[str] = None


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: Optional[str] = None
    tenantId: Optional[str] = None
    workspaceId: Optional[str] = None
    createdAt: datetime
    permissions: List[PermissionResponse] = Field(default_factory=list)

    @field_validator("permissions", mode="before")
    @classmethod
    def validate_permissions(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            # Extract actual Permission object if it's wrapped in RolePermission
            resolved = []
            for item in v:
                if isinstance(item, dict):
                    p = item.get("permission")
                    resolved.append(p if p else item)
                elif hasattr(item, "permission"):
                    p = getattr(item, "permission")
                    resolved.append(p if p else item)
                else:
                    resolved.append(item)
            return resolved
        return v


class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None


class RolePermissionUpdate(BaseModel):
    # List of permission IDs to assign to this role (replaces existing)
    permissionIds: List[str]
