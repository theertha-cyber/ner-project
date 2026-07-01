from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.entity_service import EntityService
from src.gateway.dependencies import get_db, resolve_tenant_from_jwt, require_tenant_role

router = APIRouter(prefix="/api/v1/tenants/{tenant_slug}/entity-types", tags=["entity-types"])


@router.post("", status_code=201)
async def create_entity_type(
    tenant_slug: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.create_entity_type(tenant_id, payload)


@router.get("")
async def list_entity_types(
    tenant_slug: str,
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.list_entity_types(tenant_id, is_active=is_active)


@router.get("/{name}")
async def get_entity_type(
    tenant_slug: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.get_entity_type(tenant_id, name)


@router.put("/{name}")
async def update_entity_type(
    tenant_slug: str,
    name: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.update_entity_type(tenant_id, name, payload)


@router.patch("/{name}")
async def toggle_entity_type(
    tenant_slug: str,
    name: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.toggle_entity_type(tenant_id, name, payload["is_active"])


@router.delete("/{name}")
async def delete_entity_type(
    tenant_slug: str,
    name: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.soft_delete_entity_type(tenant_id, name)
