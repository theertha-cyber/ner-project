from fastapi import Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text
from src.shared.database import get_engine
from src.shared.exceptions import TenantNotFoundError, TenantInactiveError, TenantMismatchError


async def get_db() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def require_system_admin(request: Request) -> str:
    role = getattr(request.state, "role", None)
    if role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")
    return role


def require_tenant_role(request: Request) -> str:
    role = getattr(request.state, "role", None)
    if role not in ("tenant_admin", "business_user", "annotator", "system_admin"):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return role


def require_tenant_admin(request: Request) -> str:
    role = getattr(request.state, "role", None)
    if role != "tenant_admin":
        raise HTTPException(status_code=403, detail="Tenant admin access required")
    return role


def get_request_tenant_id(request: Request) -> str:
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tenant_id


async def resolve_tenant(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    tenant_slug = getattr(request.state, "tenant_slug", None)
    if tenant_slug is None:
        raise HTTPException(status_code=400, detail="Tenant slug not resolved")
    token_tenant_id = getattr(request.state, "token_tenant_id", None)
    result = await db.execute(
        text("SELECT id, status FROM public.tenants WHERE slug = :slug"),
        {"slug": tenant_slug},
    )
    row = result.fetchone()
    if not row:
        raise TenantNotFoundError(tenant_slug)
    if row.status == "inactive":
        raise TenantInactiveError(tenant_slug)
    if token_tenant_id != row.id:
        raise TenantMismatchError()
    request.state.tenant_id = token_tenant_id
    return token_tenant_id


async def resolve_tenant_from_jwt(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    tenant_id = getattr(request.state, "token_tenant_id", None)
    if not tenant_id or tenant_id == "system":
        raise TenantNotFoundError(tenant_id or "unknown")
    result = await db.execute(
        text("SELECT id, status FROM public.tenants WHERE id = :id"),
        {"id": tenant_id},
    )
    row = result.fetchone()
    if not row:
        raise TenantNotFoundError(tenant_id)
    if row.status == "inactive":
        raise TenantInactiveError(tenant_id)
    request.state.tenant_id = tenant_id
    return tenant_id
