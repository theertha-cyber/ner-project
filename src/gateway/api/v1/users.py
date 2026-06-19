from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.user_service import UserService
from src.gateway.dependencies import get_db, resolve_tenant_from_jwt, require_tenant_admin


class CreateUserRequest(BaseModel):
    email: str
    password: str
    role: str = "business_user"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    status: str | None = None


router = APIRouter(prefix="/api/v1/users", tags=["tenant-users"])


@router.post("", status_code=201)
async def create_user(
    payload: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = UserService(db)
    return await service.create_user(tenant_id, payload.model_dump())


@router.get("")
async def list_users(
    role: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = UserService(db)
    return await service.list_users(tenant_id, role=role)


@router.get("/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = UserService(db)
    return await service.get_user(tenant_id, user_id)


@router.put("/{user_id}")
async def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = UserService(db)
    return await service.update_user(tenant_id, user_id, payload.model_dump(exclude_none=True))


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = UserService(db)
    return await service.deactivate_user(tenant_id, user_id)
