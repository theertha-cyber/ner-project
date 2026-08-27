from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.entity_service import EntityService
from src.gateway.dependencies import get_db, resolve_tenant_from_jwt, require_tenant_role

router = APIRouter(prefix="/api/v1/tenants/{tenant_slug}/entity-types", tags=["entity-types"])

# `single` | `multi`, declared here so an invalid value is a 422 from FastAPI naming both
# permitted values rather than a 500 from migration `037`'s CHECK constraint. The service
# validates it again before the write — this is the request contract, that is the invariant.
Cardinality = Literal["single", "multi"]


class EntityTypeCreate(BaseModel):
    """The create contract.

    `sql_identifier` is deliberately absent: it is system-assigned at create and never changed.
    A client that sends one anyway is ignored rather than rejected — extra fields are dropped
    by the default model config — so an older portal build echoing back a read response keeps
    working."""

    name: str
    description: str | None = None
    examples: list[str] | None = None
    validation_rule: str | None = None
    target_table: str | None = None
    base_label_mapping: dict | None = None
    required_flag: bool | None = None
    value_kind: str | None = None
    value_unit: str | None = None
    cardinality: Cardinality | None = None


class EntityTypeUpdate(BaseModel):
    """Every field optional: the service only writes the keys actually present, so an update
    that omits a field leaves it alone rather than nulling it. `name` is not updatable — it is
    the path segment — and neither is `sql_identifier`."""

    description: str | None = None
    examples: list[str] | None = None
    validation_rule: str | None = None
    target_table: str | None = None
    base_label_mapping: dict | None = None
    required_flag: bool | None = None
    value_kind: str | None = None
    value_unit: str | None = None
    cardinality: Cardinality | None = None


class EntityTypeToggle(BaseModel):
    """`is_active` is required. Reading it off an untyped dict raised `KeyError` on an empty
    body, which surfaced as a 500 for what is plainly a malformed request."""

    is_active: bool


@router.post("", status_code=201)
async def create_entity_type(
    tenant_slug: str,
    payload: EntityTypeCreate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.create_entity_type(tenant_id, payload.model_dump(exclude_unset=True))


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
    payload: EntityTypeUpdate,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.update_entity_type(
        tenant_id, name, payload.model_dump(exclude_unset=True)
    )


@router.patch("/{name}")
async def toggle_entity_type(
    tenant_slug: str,
    name: str,
    payload: EntityTypeToggle,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_role),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    service = EntityService(db)
    return await service.toggle_entity_type(tenant_id, name, payload.is_active)


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
