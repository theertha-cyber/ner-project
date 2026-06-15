import os
import uuid
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.training_service.api.v1.schemas import TrainingJobCreate, TrainingJobResponse, TrainingJobListResponse, RejectJobRequest
from src.training_service.infra.repository import TrainingJobRepository, ModelVersionRepository
from src.training_service.celery_app import celery_app

router = APIRouter(prefix="/api/v1/training-jobs", tags=["training-jobs"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


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


def require_system_admin(request: Request) -> None:
    role = getattr(request.state, "role", None)
    if role != "system_admin":
        raise HTTPException(status_code=403, detail="System admin access required")


def _row_to_response(row: dict) -> TrainingJobResponse:
    return TrainingJobResponse(
        id=row["id"],
        status=row["status"],
        hyperparams=row.get("hyperparams"),
        current_epoch=row.get("current_epoch"),
        current_loss=row.get("current_loss"),
        metrics=row.get("metrics"),
        error_message=row.get("error_message"),
        model_version_id=row.get("model_version_id"),
        mlflow_run_id=row.get("mlflow_run_id"),
        mlflow_run_url=row.get("mlflow_run_url"),
        created_at=row.get("created_at"),
        started_at=row.get("started_at"),
        completed_at=row.get("completed_at"),
        failed_at=row.get("failed_at"),
    )


@router.post("", status_code=201, response_model=TrainingJobResponse)
async def create_training_job(
    body: TrainingJobCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    count_result = await session.execute(
        text(f"""
            SELECT COUNT(sp.id)
            FROM {schema}.spans sp
            JOIN {schema}.documents d ON d.id = sp.document_id
        """),
    )
    entity_count = count_result.scalar() or 0
    min_entities = int(os.environ.get("NER_MIN_TRAINING_ENTITIES", "0"))
    if entity_count < min_entities:
        raise HTTPException(
            status_code=422,
            detail=f"Insufficient annotated entities: {entity_count}. Minimum {min_entities} required.",
        )

    job_id = str(uuid.uuid4())

    await TrainingJobRepository.create(session, tenant_id, job_id, body.model_dump(), celery_task_id=None)
    created = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    return _row_to_response(created)


@router.get("", response_model=TrainingJobListResponse)
async def list_training_jobs(
    request: Request,
    session: AsyncSession = Depends(get_session),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    tenant_id: str | None = Query(None, description="Tenant ID (system admin only — overrides JWT tenant)"),
):
    role = getattr(request.state, "role", None)
    if role == "system_admin":
        if not tenant_id:
            return TrainingJobListResponse(items=[], total=0, page=page, per_page=per_page)
    else:
        tenant_id = get_tenant_id(request)

    rows, total = await TrainingJobRepository.list_by_tenant(session, tenant_id, status, page, per_page)
    return TrainingJobListResponse(
        items=[_row_to_response(r) for r in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{job_id}", response_model=TrainingJobResponse)
async def get_training_job(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str | None = Query(None, description="Tenant ID (system admin only — overrides JWT tenant)"),
):
    role = getattr(request.state, "role", None)
    if role == "system_admin":
        if not tenant_id:
            raise HTTPException(status_code=400, detail="System admin must provide tenant_id query parameter")
    else:
        tenant_id = get_tenant_id(request)

    row = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Training job not found")
    return _row_to_response(row)


@router.post("/{job_id}/approve", response_model=TrainingJobResponse)
async def approve_training_job(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Query(..., description="Tenant ID that owns the job"),
):
    require_system_admin(request)
    row = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Training job not found")

    if row["status"] != "pending_approval":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot approve job in '{row['status']}' status",
        )

    task = celery_app.send_task("fine_tune_model", args=[tenant_id, job_id, row.get("hyperparams") or {}])
    await TrainingJobRepository.update_status(
        session, tenant_id, job_id, "queued",
        celery_task_id=task.id,
    )
    updated = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    return _row_to_response(updated)


@router.post("/{job_id}/reject", response_model=TrainingJobResponse)
async def reject_training_job(
    job_id: str,
    body: RejectJobRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Query(..., description="Tenant ID that owns the job"),
):
    require_system_admin(request)
    row = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Training job not found")

    if row["status"] != "pending_approval":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot reject job in '{row['status']}' status",
        )

    await TrainingJobRepository.update_status(
        session, tenant_id, job_id, "rejected",
        error_message=body.reason,
    )
    updated = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    return _row_to_response(updated)


@router.post("/{job_id}/cancel", response_model=TrainingJobResponse)
async def cancel_training_job(
    job_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    require_tenant_admin(request)
    tenant_id = get_tenant_id(request)
    row = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Training job not found")

    if row["status"] not in ("pending_approval", "queued", "running"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot cancel job in '{row['status']}' status",
        )

    celery_task_id = row.get("celery_task_id")
    if celery_task_id:
        celery_app.control.revoke(celery_task_id, terminate=True)

    await TrainingJobRepository.update_status(
        session, tenant_id, job_id, "cancelled",
        failed_at=None,
    )
    updated = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    return _row_to_response(updated)
