import sys
sys.path.append('.')
import asyncio
from src.config import prisma

async def main():
    await prisma.connect()
    tc = await prisma.testcase.find_first(where={'category': 'NEGATIVE'})
    print("TC name:", tc.name)
    print("Meta:", tc.metadata)
    await prisma.disconnect()

asyncio.run(main())
