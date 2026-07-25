"""Pydantic request schemas for Super Admin endpoints.

Replaces raw `dict` parameters for proper validation and documentation.
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


# Plan name mapping used by create/update tenant endpoints
PLAN_MAPPING = {
    "FREE": "FREE",
    "STARTER": "STARTER",
    "PROFESSIONAL": "PRO",
    "ENTERPRISE": "ENTERPRISE",
}


class CreateTenantRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    password: str = "cognitest@123"
    plan: str = "FREE"


class UpdateTenantRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    plan: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: str
