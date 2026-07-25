from pydantic import BaseModel, ConfigDict, Field
from typing import Literal, Optional
from datetime import datetime


class SupportTicketCreate(BaseModel):
    subject: str = Field(..., min_length=2, description="Subject of the support ticket")
    category: Literal["bug", "billing", "feature", "account"] = Field(..., description="Category of the ticket")
    description: str = Field(..., min_length=10, description="Detailed description of the issue")
    workspaceId: Optional[str] = Field(None, description="Optional associated workspace ID")


class SupportTicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject: str
    category: str
    description: str
    status: str
    userId: Optional[str] = None
    workspaceId: Optional[str] = None
    createdAt: datetime
    updatedAt: datetime
