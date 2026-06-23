import uuid
import hashlib
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.shared.exceptions import NotFoundError
from src.chat_api.api.v1.schemas import WidgetKeyResponse, WidgetKeyCreateResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/widget-keys", tags=["widget-keys"])


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


@router.post("", response_model=WidgetKeyCreateResponse, status_code=201)
async def create_widget_key(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    role = getattr(request.state, "role", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    raw_key = f"ner_widget_{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_id = str(uuid.uuid4())

    await session.execute(
        text("""
            INSERT INTO public.widget_api_keys (id, tenant_id, key_hash, key_prefix)
            VALUES (:id, :tid, :hash, :prefix)
        """),
        {"id": key_id, "tid": tenant_id, "hash": key_hash, "prefix": raw_key[:8]},
    )
    await session.commit()

    return WidgetKeyCreateResponse(id=key_id, raw_key=raw_key, key_prefix=raw_key[:8])


@router.get("", response_model=list[WidgetKeyResponse])
async def list_widget_keys(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    result = await session.execute(
        text("SELECT id, key_prefix, created_at, last_used_at FROM public.widget_api_keys WHERE tenant_id = :tid AND revoked_at IS NULL ORDER BY created_at DESC"),
        {"tid": tenant_id},
    )
    rows = result.fetchall()
    return [
        WidgetKeyResponse(id=r.id, key_prefix=r.key_prefix, created_at=str(r.created_at), last_used_at=str(r.last_used_at) if r.last_used_at else None)
        for r in rows
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke_widget_key(
    key_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context not available")

    result = await session.execute(
        text("SELECT id FROM public.widget_api_keys WHERE id = :kid AND tenant_id = :tid AND revoked_at IS NULL"),
        {"kid": key_id, "tid": tenant_id},
    )
    if not result.fetchone():
        raise NotFoundError("Widget API key", key_id)

    await session.execute(
        text("UPDATE public.widget_api_keys SET revoked_at = NOW() WHERE id = :kid"),
        {"kid": key_id},
    )
    await session.commit()
