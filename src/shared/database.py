from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from src.shared.config import settings

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.database_url, poolclass=NullPool)
    return _engine


async def get_session() -> AsyncSession:
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
