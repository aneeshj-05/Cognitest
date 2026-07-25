import asyncio

from src.config.database import prisma


async def main() -> None:
    await prisma.connect()
    try:
        tc = await prisma.testcase.find_first()
        print("find_first TestCase:", tc)

        if tc and getattr(tc, "id", None):
            one = await prisma.testcase.find_unique(where={"id": tc.id})
            print("find_unique TestCase:", one)
        else:
            print("No TestCase rows found; find_unique skipped")
    finally:
        await prisma.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
