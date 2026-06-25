from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.shared.database import get_engine


async def get_db(request: Request) -> AsyncSession:
    engine = get_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                schema = f"tenant_{tenant_id.replace('-', '_')}"
                await session.execute(text(f"SET search_path TO {schema}"))
            yield session
        finally:
            await session.close()
