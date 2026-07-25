import sys
sys.path.append('.')
import asyncio
from src.config import prisma
from src.modules.project.services import execution_service

async def main():
    await prisma.connect()
    tc = await prisma.testcase.find_first(
        where={
            'name': 'Missing required field \'email\' - POST /login',
            'isActive': True
        },
        order={'createdAt': 'desc'}
    )
    if not tc:
        print("Test not found!")
        await prisma.disconnect()
        return

    cases = [tc.model_dump()]
    
    async for event in execution_service.stream_run_suite(
        cases=cases,
        base_url="https://e-commerce-backend-6hox.onrender.com",
        project_id=tc.projectId,
        user_id="fake-user"
    ):
        print("EVENT:", event)
    
    await prisma.disconnect()

asyncio.run(main())
