from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.tenant_service import TenantService
from src.gateway.services.user_service import UserService
from src.gateway.services.audit_service import AuditService
from src.gateway.dependencies import get_db, require_system_admin
from src.gateway.models import AuditEventKind
from src.gateway.api.v1.users import CreateUserRequest

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


class CreateTenantRequest(BaseModel):
    name: str
    slug: str | None = None
    max_users: int = 10
    max_documents: int = 1000
    max_storage_gb: int = 5
    max_model_versions: int = 10
    admin_email: EmailStr
    admin_password: str


@router.post("/tenants", status_code=201)
async def create_tenant(
    payload: CreateTenantRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    actor_email = getattr(request.state, "user_email", "")
    actor_role = getattr(request.state, "role", "")
    return await service.create_tenant(payload.model_dump(), actor_email=actor_email, actor_role=actor_role)


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
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = TenantService(db)
    actor_email = getattr(request.state, "user_email", "")
    actor_role = getattr(request.state, "role", "")
    return await service.deactivate_tenant(
        tenant_id,
        actor_email=actor_email,
        actor_role=actor_role,
    )


@router.get("/tenants/{tenant_id}/users")
async def list_tenant_users(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    tenant_service = TenantService(db)
    await tenant_service.get_tenant(tenant_id)
    user_service = UserService(db)
    return await user_service.list_users(tenant_id)


@router.post("/tenants/{tenant_id}/users", status_code=201)
async def create_tenant_user(
    tenant_id: str,
    payload: CreateUserRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    tenant_service = TenantService(db)
    await tenant_service.get_tenant(tenant_id)
    user_service = UserService(db)
    actor_email = getattr(request.state, "user_email", "")
    actor_role = getattr(request.state, "role", "")
    return await user_service.create_user(
        tenant_id,
        payload.model_dump(),
        actor_email=actor_email,
        actor_role=actor_role,
    )


@router.get("/audit-log")
async def list_audit_log(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_system_admin),
):
    service = AuditService(db)
    return await service.list_events(page=page, per_page=per_page)

