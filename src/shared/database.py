from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool
from tenacity import retry, retry_if_exception_type, stop_after_delay, wait_exponential
from src.shared.config import settings

_engine = None


class EngineResolver:
    """The single place an engine is chosen.

    Today there is exactly one engine for every tenant, and this resolver returns it —
    `tenant_id` is accepted and deliberately ignored. It exists so that the named
    `tenant-postgresql-data-plane` change, which routes a tenant to its own PostgreSQL,
    is a substitution here rather than a sweep of every `get_engine()` call site.
    Nothing may branch on the tenant until that change lands.
    """

    def resolve(self, tenant_id: str | None = None):
        global _engine
        if _engine is None:
            _engine = create_async_engine(settings.database_url, poolclass=NullPool)
        return _engine


_resolver = EngineResolver()


def set_engine_resolver(resolver: EngineResolver) -> None:
    """Replace the resolver. For tests and for the later data-plane change."""
    global _resolver
    _resolver = resolver


def _retrying():
    return retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(multiplier=settings.retry_initial_delay_seconds, max=settings.retry_max_delay_seconds),
        stop=stop_after_delay(settings.retry_max_total_seconds),
        reraise=True,
    )


def get_engine(tenant_id: str | None = None):
    return _resolver.resolve(tenant_id)


@_retrying()
async def wait_for_database() -> None:
    """Retry the first connection attempt with bounded exponential backoff so the
    service tolerates Postgres starting later than the service process itself."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def get_session() -> AsyncSession:
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        yield session
