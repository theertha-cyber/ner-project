from contextlib import asynccontextmanager, contextmanager

from fastapi import Request, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from src.shared.data_plane import DataPlaneNotReady, DataPlaneUnavailable, record_health, record_health_sync
from src.shared.database import get_engine, get_resolver
from src.shared.observability.domain_metrics import assert_tenant_schema


async def get_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tenant_id


async def get_current_user_id(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


async def get_current_role(request: Request) -> str:
    role = getattr(request.state, "role", None)
    if role is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return role


def _tenant_schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def classify_driver_error(exc: Exception) -> str:
    """Map a driver/connection failure to a finite, safe reason class (Design D8). The
    original exception (host names, driver messages, sometimes SQL) is never logged or
    returned from here — only this class name is."""
    message = str(exc).lower()
    if "timeout" in message or "timed out" in message:
        return "timeout"
    if "password" in message or "authentication" in message or "auth" in message:
        return "auth_failed"
    return "unreachable"


async def record_health_best_effort(tenant_id: str, outcome: str) -> None:
    """Writes the resolver-proven health outcome on a fresh platform connection —
    `engine`/`session` above may themselves be the broken resource, so this never
    reuses them. Best-effort: a failure here must never mask the real
    `DataPlaneUnavailable` this is called alongside, so it is swallowed."""
    try:
        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as platform_session:
            await record_health(platform_session, tenant_id, outcome)
            await platform_session.commit()
    except Exception:
        pass


def record_health_best_effort_sync(tenant_id: str, outcome: str) -> None:
    try:
        with sessionmaker(get_resolver().resolve_sync(None), expire_on_commit=False)() as platform_session:
            record_health_sync(platform_session, tenant_id, outcome)
            platform_session.commit()
    except Exception:
        pass


@asynccontextmanager
async def tenant_session(tenant_id: str):
    """The one way to get an `AsyncSession` scoped to a tenant's schema, on whichever
    engine `EngineResolver` resolves for that tenant (ADR-017, Design D4).

    Raises `DataPlaneNotReady` for a `tenant_owned` tenant whose data plane is not
    `ready`, and `DataPlaneUnavailable` if resolution or the connection itself fails.
    Never falls back to the platform engine for a `tenant_owned` tenant.
    """
    try:
        engine = await get_resolver().resolve(tenant_id)
    except (DataPlaneNotReady, DataPlaneUnavailable):
        raise
    except Exception as exc:
        raise DataPlaneUnavailable(classify_driver_error(exc)) from exc

    schema = _tenant_schema(tenant_id)
    assert_tenant_schema(schema, "shared.tenant_context.tenant_session")
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        try:
            await session.execute(text(f"SET search_path TO {schema}"))
        except (DBAPIError, OperationalError, OSError) as exc:
            reason = classify_driver_error(exc)
            await record_health_best_effort(tenant_id, reason)
            raise DataPlaneUnavailable(reason) from exc
        yield session
    finally:
        await session.close()


@contextmanager
def tenant_sync_session(tenant_id: str):
    """The sync counterpart of `tenant_session`, for Celery workers."""
    try:
        engine = get_resolver().resolve_sync(tenant_id)
    except (DataPlaneNotReady, DataPlaneUnavailable):
        raise
    except Exception as exc:
        raise DataPlaneUnavailable(classify_driver_error(exc)) from exc

    schema = _tenant_schema(tenant_id)
    assert_tenant_schema(schema, "shared.tenant_context.tenant_sync_session")
    session = sessionmaker(engine, expire_on_commit=False)()
    try:
        try:
            session.execute(text(f"SET search_path TO {schema}"))
        except (DBAPIError, OperationalError, OSError) as exc:
            reason = classify_driver_error(exc)
            record_health_best_effort_sync(tenant_id, reason)
            raise DataPlaneUnavailable(reason) from exc
        yield session
    finally:
        session.close()


async def get_session(
    request: Request,
) -> AsyncSession:
    """Deprecated direct-engine session dependency, kept only for call sites not yet
    migrated to `tenant_session` (task group 5). Always resolves the platform engine —
    never routes a `tenant_owned` tenant to its own store."""
    db = async_sessionmaker(get_engine(), expire_on_commit=False)()
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            schema = _tenant_schema(tenant_id)
            assert_tenant_schema(schema, "shared.tenant_context.get_session")
            await db.execute(text(f"SET search_path TO {schema}"))
        yield db
    finally:
        await db.close()
