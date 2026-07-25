import sys
sys.path.append('.')
import asyncio
from src.config import prisma

async def main():
    await prisma.connect()
    tc = await prisma.testcase.find_first(where={'category': 'NEGATIVE'})
    if tc:
        d = tc.model_dump()
        print('DB Keys:', [k for k in d.keys() if 'req' in k.lower() or 'body' in k.lower()])
        print('Body:', d.get('request_body'))
    await prisma.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
