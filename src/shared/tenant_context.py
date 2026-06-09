from fastapi import Request, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.database import get_session as _get_session


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


async def get_session(
    request: Request,
) -> AsyncSession:
    db = request.app.state.db_factory()
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            await db.execute(
                text(f"SET search_path TO tenant_{tenant_id}")
            )
        yield db
    finally:
        await db.close()
