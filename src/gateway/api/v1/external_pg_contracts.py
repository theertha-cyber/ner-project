"""Tenant-admin schema-contract administration (CAP-4, ADR-013).

`POST /api/v1/data-sources/{id}/contracts` (upload + validate),
`POST .../contracts/{version}/publish` (accept),
`GET .../contracts` (paginated history). Every route requires a valid JWT,
`resolve_tenant_from_jwt`, and `require_tenant_admin`; the connection lookup
constrains `(id, authenticated tenant_id)` so another tenant's identifier
resolves to `404 CONNECTION_NOT_FOUND` with no metadata.

Contract upload is permitted only for azure_postgresql connections; publish
additionally requires the connection to be active. Publishing replaces the
tenant-isolated schema-index entries for the new version. Errors use the same
finite safe envelope as the CAP-2 lifecycle routes.
"""

import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.gateway.dependencies import (
    get_db,
    require_tenant_admin,
    resolve_tenant_from_jwt,
)
from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL
from src.shared.data_sources.service import get_connection
from src.shared.external_postgres import index as pg_index
from src.shared.external_postgres.contract import (
    ContractRejected,
    list_versions,
    publish_version,
    store_draft,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-sources", tags=["tenant-data-sources"])

_CODE_STATUS = {
    "CONNECTION_NOT_FOUND": 404,
    "INVALID_REQUEST": 422,
    "INVALID_CONTRACT": 422,
    "CONTRACT_VERSION_EXISTS": 409,
    "PUBLISH_PRECONDITION_FAILED": 409,
    "INTERNAL_ERROR": 500,
}

_CODE_HINTS = {
    "CONNECTION_NOT_FOUND": "No connection with that identifier exists for your tenant.",
    "INVALID_CONTRACT": "The contract document is not a valid schema contract; see field errors.",
    "CONTRACT_VERSION_EXISTS": "That contract version already exists for this connection.",
    "PUBLISH_PRECONDITION_FAILED": "Only a validated contract of an active connection can be published.",
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def _error(request: Request, code: str, message: str | None = None, extra: dict | None = None):
    body: dict = {
        "code": code,
        "message": message or _CODE_HINTS.get(code, "Request failed."),
        "request_id": _request_id(request),
    }
    if extra:
        body.update(extra)
    return JSONResponse(
        status_code=_CODE_STATUS.get(code, 500),
        content={"error": body},
    )


def _tenant_schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def _owned_pg_connection(db: AsyncSession, tenant_id: str, connection_id: str):
    row = await get_connection(db, tenant_id, connection_id)
    if row is None:
        return None
    if row.provider != PROVIDER_AZURE_POSTGRESQL:
        return None
    return row


@router.post("/{connection_id}/contracts", status_code=201)
async def upload_contract(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    try:
        raw = await request.body()
        document = json.loads(raw.decode("utf-8")) if raw else None
    except (ValueError, UnicodeDecodeError):
        return _error(request, "INVALID_CONTRACT")
    if not isinstance(document, dict):
        return _error(request, "INVALID_CONTRACT")
    row = await _owned_pg_connection(db, tenant_id, connection_id)
    if row is None:
        return _error(request, "CONNECTION_NOT_FOUND")
    try:
        stored = await store_draft(db, tenant_id, connection_id, document)
    except ContractRejected as rejected:
        if rejected.reason == "duplicate_version":
            return _error(request, "CONTRACT_VERSION_EXISTS")
        return _error(
            request,
            "INVALID_CONTRACT",
            extra={"reason": rejected.reason,
                   "field_errors": list(rejected.field_errors)},
        )
    except Exception:
        logger.warning("external_pg_contract_store_failed", extra={"error_class": "Unexpected"})
        return _error(request, "INTERNAL_ERROR")
    await db.commit()
    return JSONResponse(status_code=201, content=stored)


@router.post("/{connection_id}/contracts/{version}/publish")
async def publish_contract(
    connection_id: str,
    version: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    row = await _owned_pg_connection(db, tenant_id, connection_id)
    if row is None:
        return _error(request, "CONNECTION_NOT_FOUND")
    if row.status != "active":
        return _error(request, "PUBLISH_PRECONDITION_FAILED")
    try:
        published = await publish_version(db, tenant_id, connection_id, version)
    except ContractRejected:
        return _error(request, "PUBLISH_PRECONDITION_FAILED")
    except Exception:
        logger.warning("external_pg_contract_publish_failed", extra={"error_class": "Unexpected"})
        return _error(request, "INTERNAL_ERROR")
    try:
        await pg_index.replace_version_entries(
            db, _tenant_schema(tenant_id), connection_id, version,
            published["canonical"],
        )
    except Exception:
        logger.warning("external_pg_index_replace_failed", extra={"error_class": "Unexpected"})
        return _error(request, "INTERNAL_ERROR")
    await db.commit()
    return JSONResponse(
        status_code=200,
        content={"version": published["version"],
                 "fingerprint": published["fingerprint"],
                 "published": True},
    )


@router.get("/{connection_id}/contracts")
async def contract_history(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    row = await _owned_pg_connection(db, tenant_id, connection_id)
    if row is None:
        return _error(request, "CONNECTION_NOT_FOUND")
    query = request.query_params
    try:
        page = int(query.get("page", "1"))
        page_size = int(query.get("page_size", "20"))
    except ValueError:
        return _error(request, "INVALID_REQUEST")
    history = await list_versions(db, tenant_id, connection_id, page, page_size)
    return JSONResponse(status_code=200, content=history)
