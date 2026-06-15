from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.entity_service import EntityService
from src.gateway.dependencies import get_db, resolve_tenant_from_jwt, require_tenant_role

router = APIRouter(prefix="/api/v1/entity-types", tags=["entity-types"])


@router.post("", status_code=201)
async def create_entity_type(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.create_entity_type(tenant_id, payload)


@router.get("")
async def list_entity_types(
    is_active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.list_entity_types(tenant_id, is_active=is_active)


@router.get("/{entity_id}")
async def get_entity_type(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.get_entity_type(tenant_id, entity_id)


@router.put("/{entity_id}")
async def update_entity_type(
    entity_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.update_entity_type(tenant_id, entity_id, payload)


@router.delete("/{entity_id}")
async def delete_entity_type(
    entity_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.soft_delete_entity_type(tenant_id, entity_id)
