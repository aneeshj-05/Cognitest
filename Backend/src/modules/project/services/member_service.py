import logging
from src.config import prisma

logger = logging.getLogger(__name__)

async def get_project_members_list(project_id: str):
    records = await prisma.projectmember.find_many(
        where={"projectId": project_id},
        include={"user": True, "role": True},
    )
    return [
        {
            "userId": r.userId,
            "name": r.user.name if r.user else None,
            "email": r.user.email if r.user else "",
            "role": r.role.name if r.role else "—",
        }
        for r in records
    ]
