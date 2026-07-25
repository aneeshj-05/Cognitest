import sys
sys.path.append('.')
import asyncio
from src.config import prisma

async def main():
    await prisma.connect()
    tc = await prisma.testcase.find_first(
        where={
            'name': 'Missing required field \'email\' - POST /login',
            'isActive': True
        },
        order={'createdAt': 'desc'}
    )
    dumped = tc.model_dump()
    print("KEYS:", dumped.keys())
    print("Metadata key in dump:", dumped.get("metadata"))
    await prisma.disconnect()

asyncio.run(main())
