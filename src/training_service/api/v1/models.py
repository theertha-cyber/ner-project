from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.database import get_engine
from src.shared.config import settings
from src.training_service.api.v1.schemas import ModelVersionResponse, ModelVersionListResponse
from src.training_service.infra.mlflow_registry import (
    list_model_versions as mlflow_list,
    get_active_model as mlflow_get_active,
    promote_model_version as mlflow_promote,
    demote_model_version as mlflow_demote,
    _read_cache_model_versions,
)
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/models", tags=["model-registry"])

CONLL_LABELS = ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"]


def _base_model_metadata() -> dict:
    return {
        "id": "0",
        "version_number": 0,
        "training_job_id": None,
        "status": "promoted",
        "metrics": {"label_list": CONLL_LABELS},
        "artifact_path": "base",
        "mlflow_run_id": None,
        "mlflow_run_url": None,
        "created_at": None,
        "promoted_at": None,
        "archived_at": None,
        "label_list": CONLL_LABELS,
    }


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def require_tenant_admin(request: Request) -> None:
    role = getattr(request.state, "role", None)
    if role != "tenant_admin":
        raise HTTPException(status_code=403, detail="Tenant admin access required")


def _row_to_response(row: dict) -> ModelVersionResponse:
    return ModelVersionResponse(
        id=str(row["version_number"]),
        version_number=row["version_number"],
        training_job_id=row.get("training_job_id"),
        status=row["status"],
        metrics=row.get("metrics"),
        artifact_path=row.get("artifact_path"),
        mlflow_run_id=row.get("mlflow_run_id"),
        mlflow_run_url=row.get("mlflow_run_url"),
        created_at=row.get("created_at"),
        promoted_at=row.get("promoted_at"),
        archived_at=row.get("archived_at"),
        label_list=row.get("label_list"),
    )


@router.get("", response_model=ModelVersionListResponse)
async def list_model_versions(
    request: Request,
):
    tenant_id = get_tenant_id(request)
    rows, warning = mlflow_list(tenant_id)
    result = ModelVersionListResponse(items=[_row_to_response(r) for r in rows])
    if warning:
        return JSONResponse(
            status_code=200,
            content=result.model_dump(),
            headers={"X-Info": "mlflow-unavailable"},
        )
    return result


@router.get("/active", response_model=ModelVersionResponse)
async def get_active_model(
    request: Request,
):
    tenant_id = get_tenant_id(request)
    row, warning = mlflow_get_active(tenant_id)
    if not row:
        base = _base_model_metadata()
        return JSONResponse(
            status_code=200,
            content=ModelVersionResponse(**base).model_dump(),
            headers={"X-Model-Source": "base", "X-Info": "no-promoted-model"},
        )
    result = _row_to_response(row)
    if warning:
        return JSONResponse(
            status_code=200,
            content=result.model_dump(),
            headers={"X-Info": "mlflow-unavailable"},
        )
    return result


def _get_version_or_404(tenant_id: str, version_number: int) -> dict:
    versions = _read_cache_model_versions(tenant_id)
    matching = [v for v in versions if v["version_number"] == version_number]
    if not matching:
        raise HTTPException(status_code=404, detail="Model version not found")
    return matching[0]


@router.post("/{version_id}/promote", response_model=ModelVersionResponse)
async def promote_model(
    version_id: str,
    request: Request,
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)

    version_number = int(version_id)
    version = _get_version_or_404(tenant_id, version_number)
    if version["status"] != "completed":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot promote model in '{version['status']}' status",
        )

    result = mlflow_promote(tenant_id, version_number)
    if not result:
        raise HTTPException(status_code=404, detail="Model version not found in MLflow Registry")

    await _warmup_model(tenant_id, version_number, request)

    return _row_to_response(result)


async def _warmup_model(tenant_id: str, version_number: int, request: Request | None = None):
    if not settings.model_serving_url:
        return
    url = f"{settings.model_serving_url.rstrip('/')}/internal/v1/warmup"
    headers = {}
    if request is not None:
        auth = request.headers.get("Authorization")
        if auth:
            headers["Authorization"] = auth
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json={"version_number": version_number}, headers=headers)
            if resp.status_code == 200:
                logger.info("Model warmup succeeded for tenant=%s version=%d", tenant_id, version_number)
            else:
                logger.warning("Model warmup returned %d for tenant=%s version=%d", resp.status_code, tenant_id, version_number)
    except httpx.RequestError as exc:
        logger.warning("Model warmup failed for tenant=%s version=%d: %s", tenant_id, version_number, exc)


@router.post("/{version_id}/warmup")
async def warmup_model(
    version_id: str,
    request: Request,
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    version_number = int(version_id)
    _get_version_or_404(tenant_id, version_number)
    await _warmup_model(tenant_id, version_number, request)
    return {"status": "ok", "version_number": version_number}


@router.post("/{version_id}/demote", response_model=ModelVersionResponse)
async def demote_model(
    version_id: str,
    request: Request,
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    version_number = int(version_id)

    version = _get_version_or_404(tenant_id, version_number)
    if version["status"] != "promoted":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot demote model in '{version['status']}' status",
        )

    result = mlflow_demote(tenant_id, version_number)
    if not result:
        raise HTTPException(status_code=404, detail="Model version not found in MLflow Registry")
    return _row_to_response(result)
