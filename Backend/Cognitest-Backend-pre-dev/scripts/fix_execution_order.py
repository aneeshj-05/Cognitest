from prisma import Prisma
import asyncio


async def main():
    db = Prisma()
    await db.connect()

    # 🔥 Proper rebuild of execution_order (deterministic order)
    await db.query_raw(
        '''
        UPDATE "TestCase" t
        SET execution_order = sub.row_num
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (ORDER BY "createdAt") - 1 AS row_num
            FROM "TestCase"
        ) sub
        WHERE t.id = sub.id;
        '''
    )

    print("✅ execution_order rebuilt successfully (0,1,2,...)")

    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())