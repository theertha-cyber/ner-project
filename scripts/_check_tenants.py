import asyncio
import sys
sys.path.insert(0, '.')
from sqlalchemy.ext.asyncio import create_async_engine
from src.shared.config import settings

async def main():
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        result = await conn.execute(
            __import__('sqlalchemy').text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%' AND schema_name != 'tenant_template'"
            )
        )
        rows = result.fetchall()
        if rows:
            for r in rows:
                print(f"EXISTS: {r[0]}")
        else:
            print("NO_EXISTING_TENANTS")
    await engine.dispose()

asyncio.run(main())
