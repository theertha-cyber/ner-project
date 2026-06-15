import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    engine = create_async_engine("postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id, name, slug FROM public.tenants"))
        rows = result.fetchall()
        print("Tenants in DB:", len(rows))
        for r in rows:
            print(f"  id={r[0]}, name={r[1]}, slug={r[2]}")

        schemas = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'tenant_%'"))
        schema_rows = schemas.fetchall()
        print(f"\nTenant schemas: {len(schema_rows)}")
        for s in schema_rows:
            print(f"  {s[0]}")

    await engine.dispose()

asyncio.run(check())
