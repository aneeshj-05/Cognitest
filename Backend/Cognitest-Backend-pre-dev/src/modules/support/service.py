import logging
from typing import Optional
from src.config import prisma
from src.middleware.error_handler import AppError
from .schema import SupportTicketCreate
from src.services.email_service import send_support_ticket_email

logger = logging.getLogger(__name__)


async def create_support_ticket(
    data: SupportTicketCreate,
    user_id: Optional[str] = None
) -> any:
    """
    Persist the support ticket into the database.
    """
    try:
        ticket = await prisma.supportticket.create(
            data={
                "subject": data.subject,
                "category": data.category,
                "description": data.description,
                "status": "open",
                "userId": user_id,
                "workspaceId": data.workspaceId,
            }
        )
        logger.info(
            "Successfully created support ticket: ID=%s, subject='%s', category='%s', userId=%s, workspaceId=%s",
            ticket.id,
            ticket.subject,
            ticket.category,
            user_id,
            data.workspaceId,
        )

        if user_id:
            user = await prisma.user.find_unique(where={"id": user_id})
            if user and getattr(user, "email", None):
                try:
                    send_support_ticket_email(user.email, ticket)
                except Exception:
                    logger.exception(
                        "Failed to send support ticket confirmation email for ticket %s to user %s",
                        ticket.id,
                        user_id,
                    )
            else:
                logger.warning(
                    "Support ticket %s created but no email found for user ID %s",
                    ticket.id,
                    user_id,
                )

        return ticket
    except Exception as e:
        logger.exception("Failed to create support ticket in the database. Subject: %s", data.subject)
        raise AppError("Failed to submit support ticket due to a database error", status_code=500)
