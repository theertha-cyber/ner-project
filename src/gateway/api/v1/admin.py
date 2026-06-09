from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.tenant_service import TenantService
from src.gateway.dependencies import get_db, require_system_admin

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/tenants", status_code=201)
async def create_tenant(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    return await service.create_tenant(payload)


@router.get("/tenants")
async def list_tenants(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    return await service.list_tenants(status=status_filter, page=page, per_page=per_page)


@router.get("/tenants/{tenant_id}")
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    return await service.get_tenant(tenant_id)


@router.put("/tenants/{tenant_id}")
async def update_tenant(
    tenant_id: str,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    return await service.update_tenant(tenant_id, payload)


@router.post("/tenants/{tenant_id}/deactivate")
async def deactivate_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    return await service.deactivate_tenant(tenant_id)

