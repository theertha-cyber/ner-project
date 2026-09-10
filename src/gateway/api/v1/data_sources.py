"""Tenant-admin Azure connection lifecycle API (CAP-2, ADR-011).

`POST/GET/PATCH /api/v1/data-sources` plus `test`, `activate`, `pause`,
`replace`, and confirmed `retire` actions. Every route requires a valid JWT,
`resolve_tenant_from_jwt`, and `require_tenant_admin`. There is no tenant ID in
a path, query, or body — the service uses only the authenticated tenant ID for
every lookup, write, idempotency entry, lifecycle constraint, and audit record.

All errors use exactly
`{"error": {"code": <FINITE_SAFE_CODE>, "message": <safe text>, "request_id": ...}}`.
Messages name field names and finite classes only: never configuration values,
secret references, endpoints, connection strings, provider diagnostics, tenant
content, SQL, prompts, answers, or raw exceptions.
"""

import hashlib
import json
import logging
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.gateway.dependencies import (
    get_db,
    require_tenant_admin,
    resolve_tenant_from_jwt,
)
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.providers import ConnectionValidationError
from src.shared.data_sources.service import (
    activate_connection,
    check_replay,
    create_connection,
    get_connection,
    list_connections,
    pause_connection,
    replace_connection,
    retire_connection,
    store_replay,
    test_connection,
    update_connection,
)
from src.shared.data_sources.store import to_connection_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-sources", tags=["tenant-data-sources"])

_IDEMPOTENCY_KEY_RE = re.compile(r"^[\x20-\x7E]{1,128}$")

_ALLOWED_LIST_PARAMS = frozenset(
    {"q", "provider", "status", "sort", "order", "page", "page_size"}
)

# Fixed safe messages per finite code. The detail a caller needs to act is the
# code and the field name in `message`; nothing else is quoted back.
_CODE_STATUS = {
    "CONNECTION_NOT_FOUND": 404,
    "IDEMPOTENCY_KEY_REQUIRED": 400,
    "IDEMPOTENCY_KEY_REUSED": 409,
    "INVALID_REQUEST": 422,
    "INVALID_LIFECYCLE_TRANSITION": 409,
    "TEST_REQUIRED": 409,
    "TEST_FAILED": 409,
    "ACTIVATION_PREREQUISITE_MISSING": 409,
    "ACTIVE_PROVIDER_EXISTS": 409,
    "RETIRED_CONNECTION": 409,
    "RETIRE_CONFIRMATION_REQUIRED": 422,
    "CONNECTION_TEST_UNAVAILABLE": 503,
    "INTERNAL_ERROR": 500,
}

_CODE_HINTS = {
    "CONNECTION_NOT_FOUND": "No connection with that identifier exists for your tenant.",
    "IDEMPOTENCY_KEY_REQUIRED": "Send a unique Idempotency-Key header (1-128 printable ASCII).",
    "IDEMPOTENCY_KEY_REUSED": "That Idempotency-Key was already used with a different request body.",
    "TEST_REQUIRED": "Run a successful connection test before activation.",
    "TEST_FAILED": "The latest connection test failed; fix the cause and re-test.",
    "ACTIVATION_PREREQUISITE_MISSING": "Provide the required activation evidence and a resolvable secret reference.",
    "ACTIVE_PROVIDER_EXISTS": "Your tenant already has an active connection of this provider type.",
    "RETIRED_CONNECTION": "Pause an active connection before retiring it; retired connections stay retired.",
    "RETIRE_CONFIRMATION_REQUIRED": "Confirm retirement explicitly before proceeding.",
}


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or ""


def _error(request: Request, code: str, message: str | None = None):
    return JSONResponse(
        status_code=_CODE_STATUS.get(code, 500),
        content={
            "error": {
                "code": code,
                "message": message or _CODE_HINTS.get(code, "Request failed."),
                "request_id": _request_id(request),
            }
        },
    )


def _created(body: dict, replayed: bool = False):
    return JSONResponse(
        status_code=201,
        content=body,
        headers={"Idempotent-Replay": "true"} if replayed else {},
    )


def _ok(body: dict, replayed: bool = False):
    return JSONResponse(
        status_code=200,
        content=body,
        headers={"Idempotent-Replay": "true"} if replayed else {},
    )


async def _parse_body(request: Request):
    try:
        raw = await request.body()
    except Exception:
        return None, b""
    if not raw:
        return {}, raw
    try:
        return json.loads(raw.decode("utf-8")), raw
    except (ValueError, UnicodeDecodeError):
        return None, raw


def _body_digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _idempotency_key(request: Request) -> str | None:
    key = request.headers.get("Idempotency-Key")
    if key is None or not _IDEMPOTENCY_KEY_RE.match(key):
        return None
    return key


async def _mutate(request: Request, session, tenant_id: str, action):
    """Idempotent mutation wrapper.

    The key is scoped to authenticated tenant, method, and path; the digest pins
    the body. Same scope and body replays the original status and body with
    `Idempotent-Replay: true`; the same key with a different body is a 409; a
    missing or malformed key is a 400. Only the digest and the replayable safe
    response are persisted — never secret values.
    """
    key = _idempotency_key(request)
    if key is None:
        return _error(request, "IDEMPOTENCY_KEY_REQUIRED")
    body, raw = await _parse_body(request)
    if body is None:
        return _error(request, "INVALID_REQUEST", "Request body must be valid JSON.")
    digest = _body_digest(raw)
    path = request.url.path
    try:
        seen = await check_replay(
            session, tenant_id, request.method, path, key, digest
        )
    except Exception:
        logger.exception("idempotency_lookup_failed", extra={"action": action.__name__})
        return _error(request, "INTERNAL_ERROR")
    if seen is not None:
        kind, status, stored = seen
        if kind == "reused":
            return _error(request, "IDEMPOTENCY_KEY_REUSED")
        return JSONResponse(
            status_code=status, content=stored, headers={"Idempotent-Replay": "true"}
        )
    try:
        outcome = await action(body)
    except ConnectionValidationError as exc:
        return _error(request, "INVALID_REQUEST", str(exc))
    except lc.LifecycleRejected as exc:
        return _error(request, exc.code, f"{exc} {_CODE_HINTS.get(exc.code, '')}".strip())
    except Exception:
        logger.exception("data_source_mutation_failed", extra={"action": action.__name__})
        return _error(request, "INTERNAL_ERROR")
    status_code, response_body = outcome
    try:
        await store_replay(
            session, tenant_id, request.method, path, key, digest,
            status_code, response_body,
        )
    except Exception:
        logger.exception("idempotency_store_failed", extra={"action": action.__name__})
    return JSONResponse(status_code=status_code, content=response_body)


def _require_keys(body: dict, allowed: set, required: set) -> None:
    if not isinstance(body, dict):
        raise ConnectionValidationError(None, "Request body must be a JSON object.")
    unknown = set(body) - allowed
    if unknown:
        raise ConnectionValidationError(
            sorted(unknown)[0], f"'{sorted(unknown)[0]}' is not an accepted field."
        )
    missing = required - set(body)
    if missing:
        raise ConnectionValidationError(
            sorted(missing)[0], f"'{sorted(missing)[0]}' is required."
        )


@router.post("", status_code=201)
async def create_data_source(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(
            body,
            {"provider", "configuration", "secret_references"},
            {"provider", "configuration", "secret_references"},
        )
        if not isinstance(body["configuration"], dict):
            raise ConnectionValidationError(
                "configuration", "'configuration' must be an object."
            )
        if not isinstance(body["secret_references"], dict):
            raise ConnectionValidationError(
                "secret_references", "'secret_references' must be an object."
            )
        row = await create_connection(
            db,
            tenant_id,
            body["provider"],
            body["configuration"],
            body["secret_references"],
        )
        return 201, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.get("")
async def list_data_sources(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    params = dict(request.query_params)
    unknown = set(params) - _ALLOWED_LIST_PARAMS
    if unknown:
        return _error(
            request, "INVALID_REQUEST",
            f"'{sorted(unknown)[0]}' is not an accepted query parameter.",
        )
    try:
        page = int(params.get("page", "1"))
        page_size = int(params.get("page_size", "20"))
    except (TypeError, ValueError):
        return _error(
            request, "INVALID_REQUEST", "'page' and 'page_size' must be integers."
        )
    try:
        rows, total = await list_connections(
            db,
            tenant_id,
            q=params.get("q"),
            provider=params.get("provider"),
            status=params.get("status"),
            sort=params.get("sort", "last_activity"),
            order=params.get("order", "desc"),
            page=page,
            page_size=page_size,
        )
    except ConnectionValidationError as exc:
        return _error(request, "INVALID_REQUEST", str(exc))
    except Exception:
        logger.exception("data_source_list_failed")
        return _error(request, "INTERNAL_ERROR")
    total_pages = (total + page_size - 1) // page_size if total else 0
    return _ok({
        "items": [to_connection_dict(row) for row in rows],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "sort": params.get("sort", "last_activity"),
        "order": params.get("order", "desc"),
    })


@router.get("/{connection_id}")
async def read_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    try:
        row = await get_connection(db, tenant_id, connection_id)
    except Exception:
        logger.exception("data_source_read_failed")
        return _error(request, "INTERNAL_ERROR")
    if row is None:
        return _error(request, "CONNECTION_NOT_FOUND")
    return _ok(to_connection_dict(row))


@router.patch("/{connection_id}")
async def update_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(body, {"configuration", "secret_references"}, set())
        if "configuration" not in body and "secret_references" not in body:
            raise ConnectionValidationError(
                None, "One of 'configuration' or 'secret_references' is required."
            )
        row = await update_connection(db, tenant_id, connection_id, body)
        return 200, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.post("/{connection_id}/test")
async def test_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(body, set(), set())
        row = await test_connection(db, tenant_id, connection_id)
        return 200, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.post("/{connection_id}/activate")
async def activate_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(body, {"activation_evidence"}, {"activation_evidence"})
        row = await activate_connection(
            db, tenant_id, connection_id, body["activation_evidence"]
        )
        return 200, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.post("/{connection_id}/pause")
async def pause_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(body, set(), set())
        row = await pause_connection(db, tenant_id, connection_id)
        return 200, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.post("/{connection_id}/replace", status_code=201)
async def replace_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(
            body,
            {"provider", "configuration", "secret_references"},
            {"provider", "configuration", "secret_references"},
        )
        if not isinstance(body["configuration"], dict):
            raise ConnectionValidationError(
                "configuration", "'configuration' must be an object."
            )
        if not isinstance(body["secret_references"], dict):
            raise ConnectionValidationError(
                "secret_references", "'secret_references' must be an object."
            )
        row = await replace_connection(
            db,
            tenant_id,
            connection_id,
            body["provider"],
            body["configuration"],
            body["secret_references"],
        )
        return 201, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)


@router.post("/{connection_id}/retire")
async def retire_data_source(
    connection_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    async def _action(body: dict):
        _require_keys(body, {"confirm"}, set())
        row = await retire_connection(db, tenant_id, connection_id, body.get("confirm"))
        return 200, to_connection_dict(row)

    return await _mutate(request, db, tenant_id, _action)
