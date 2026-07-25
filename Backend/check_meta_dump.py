import sys
sys.path.append('.')
import asyncio
from src.config import prisma

async def main():
    await prisma.connect()
    tcs = await prisma.testcase.find_many(where={'category': 'NEGATIVE', 'test_type': 'Negative'}, order={'createdAt': 'desc'}, take=1)
    
    cases = [c.model_dump() for c in tcs]
    for case in cases:
        print("Type:", type(case["metadata"]))
        print("Value:", case["metadata"])
    await prisma.disconnect()

asyncio.run(main())
