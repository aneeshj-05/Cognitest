from prisma import Prisma
from typing import AsyncGenerator


# Global Prisma client instance
prisma = Prisma()


async def connect_db() -> None:
    """Connect to the database."""
    if not prisma.is_connected():
        await prisma.connect()


async def disconnect_db() -> None:
    """Disconnect from the database."""
    if prisma.is_connected():
        await prisma.disconnect()


async def get_db() -> AsyncGenerator[Prisma, None]:
    """Dependency to get database session."""
    if not prisma.is_connected():
        await connect_db()
    yield prisma
