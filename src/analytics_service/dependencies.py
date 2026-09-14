from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.shared.database import get_engine
from src.shared.observability.domain_metrics import assert_tenant_schema


async def get_db(request: Request) -> AsyncSession:
    engine = get_engine()
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            tenant_id = getattr(request.state, "tenant_id", None)
            if tenant_id:
                schema = f"tenant_{tenant_id.replace('-', '_')}"
                assert_tenant_schema(schema, "analytics_service.dependencies.get_session")
                await session.execute(text(f"SET search_path TO {schema}"))
            yield session
        finally:
            await session.close()
