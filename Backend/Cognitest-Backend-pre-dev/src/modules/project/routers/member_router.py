from fastapi import APIRouter, Depends
from src.middleware.auth_middleware import get_current_user
from ..services import member_service, project_service

router = APIRouter(prefix="/projects", tags=["Members"])

@router.get("/{project_id}/members")
async def get_project_members(project_id: str, user: dict = Depends(get_current_user)):
    """Return all members assigned to a specific project with their per-project role."""
    await project_service.verify_project_access(project_id, user)
    return await member_service.get_project_members_list(project_id)
