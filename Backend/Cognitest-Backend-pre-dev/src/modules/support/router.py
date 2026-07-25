from fastapi import APIRouter, Depends, status
from src.middleware.auth_middleware import get_current_user
from .schema import SupportTicketCreate, SupportTicketResponse
from . import service

router = APIRouter(prefix="/support", tags=["Support"])


@router.post(
    "/tickets",
    response_model=SupportTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a support ticket",
)
async def submit_support_ticket_endpoint(
    data: SupportTicketCreate,
    user: dict = Depends(get_current_user),
):
    """
    Submit a support ticket. Persists the ticket in the database.
    """
    user_id = user.get("userId")
    return await service.create_support_ticket(data, user_id=user_id)
