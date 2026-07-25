import asyncio
import httpx
import json
import logging
from src.modules.project.services.execution_service import _auth_session_cleanup
from src.config.database import prisma

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_cleanup():
    await prisma.connect()
    async with httpx.AsyncClient() as client:
        # This will likely fail if we don't have a real token/user, 
        # but we can at least check if it handles missing info gracefully.
        print("Testing cleanup with mock data...")
        res = await _auth_session_cleanup(client, "http://localhost:5000", "mock_token", "mock_uid")
        print(f"Cleanup result (expected False/Failure): {res}")
    await prisma.disconnect()

if __name__ == "__main__":
    asyncio.run(test_cleanup())
