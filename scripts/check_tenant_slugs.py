import asyncio
import sys
sys.stdout.reconfigure(encoding="utf-8")
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine(
        "postgresql+asyncpg://ner:ner@localhost:54320/ner_test"
    )
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id, slug FROM public.tenants WHERE slug LIKE 'entity-config-%'")
        )
        rows = result.fetchall()
        print(f"Found {len(rows)} entity-config tenants")
        for r in rows:
            print(f"  id={r[0]}, slug={r[1]}")

        result2 = await conn.execute(text("SELECT COUNT(*) FROM public.tenants"))
        count = result2.scalar()
        print(f"Total tenants: {count}")

        result3 = await conn.execute(
            text("SELECT id, slug FROM public.tenants LIMIT 20")
        )
        all_rows = result3.fetchall()
        for r in all_rows:
            print(f"  id={r[0]}, slug={r[1]}")

    await engine.dispose()


asyncio.run(check())
