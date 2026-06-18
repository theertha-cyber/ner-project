import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine("postgresql+asyncpg://ner:ner@localhost:5432/ner_dev")
    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'tenant_template' AND table_name = 'extraction_runs'
            ORDER BY ordinal_position
        """))
        for row in result:
            print(f"{row.column_name:25s} {row.data_type:15s} nullable={row.is_nullable}")
    await engine.dispose()

asyncio.run(main())
