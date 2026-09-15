"""The content-route readiness gate and typed-error → HTTP mapping (ADR-017, Design D9,
D8). Two pieces every service wires in:

- `require_data_plane_ready`: a FastAPI dependency for content routers (documents,
  extraction, annotation, training, analytics, chat, widget chat, blob-sync execution).
  Raises `DataPlaneNotReady` unless the tenant's data plane is `ready`; a `platform`
  tenant is always ready. Tenant-admin, data-source settings, and data-plane status
  routes are exempt — never add this dependency to those routers.
- `install_data_plane_exception_handlers`: registers the handlers that turn
  `DataPlaneNotReady` into 409 `TENANT_DATA_PLANE_NOT_READY` and `DataPlaneUnavailable`
  into 503 `TENANT_DATA_PLANE_UNAVAILABLE` — finite safe bodies only, never a driver
  message, endpoint, or credential.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.shared.data_plane import (
    HEALTH_AUTH_FAILED,
    HEALTH_TIMEOUT,
    HEALTH_UNREACHABLE,
    DataPlaneNotReady,
    DataPlaneUnavailable,
    get_data_plane_record,
)

_UNHEALTHY_OUTCOMES = frozenset({HEALTH_UNREACHABLE, HEALTH_AUTH_FAILED, HEALTH_TIMEOUT})
from src.shared.database import get_engine


def _error_body(code: str, detail_key: str, detail_value: str, request: Request) -> dict:
    request_id = getattr(request.state, "request_id", None)
    return {
        "error": {
            "code": code,
            detail_key: detail_value,
            "request_id": request_id,
        }
    }


async def _not_ready_handler(request: Request, exc: DataPlaneNotReady) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content=_error_body("TENANT_DATA_PLANE_NOT_READY", "status_class", exc.status_class, request),
    )


async def _unavailable_handler(request: Request, exc: DataPlaneUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content=_error_body("TENANT_DATA_PLANE_UNAVAILABLE", "reason_class", exc.reason_class, request),
    )


def install_data_plane_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DataPlaneNotReady, _not_ready_handler)
    app.add_exception_handler(DataPlaneUnavailable, _unavailable_handler)


async def require_data_plane_ready(request: Request) -> None:
    """FastAPI dependency for content routers. Add it once per router:

        router = APIRouter(prefix=..., dependencies=[Depends(require_data_plane_ready)])

    A request with no resolved tenant (should not reach a content router at all —
    the tenant-context middleware rejects it first) is let through here; that 401/403
    is the middleware's job, not this dependency's.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    if tenant_id is None:
        return
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        record = await get_data_plane_record(tenant_id, session)
    if not record.is_ready:
        raise DataPlaneNotReady(record.status)
    # Circuit breaker (task 11.3): a `tenant_owned` tenant already recorded
    # unhealthy — by the last resolver failure or the periodic probe, whichever
    # is more recent — is refused here without spending a real connection
    # attempt on this request. Correctness does not depend on this: a request
    # that slips through on stale cached health still fails closed via the
    # resolver's own connect attempt. This only saves the wasted attempt
    # against a store already known to be down.
    if not record.is_platform and record.health_outcome in _UNHEALTHY_OUTCOMES:
        raise DataPlaneUnavailable(record.health_outcome)
