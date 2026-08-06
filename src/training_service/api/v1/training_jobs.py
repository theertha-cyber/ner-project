import logging
import os
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.training_service.api.v1.schemas import TrainingJobCreate, TrainingJobResponse, TrainingJobListResponse, RejectJobRequest, ApproveJobRequest
from src.training_service.infra.repository import TrainingJobRepository, ModelVersionRepository
from src.training_service.celery_app import celery_app


async def _record_audit(
    session: AsyncSession,
    actor: str,
    role: str,
    action: str,
    target: str,
    kind: str,
    tenant_id: str | None = None,
) -> None:
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await session.execute(
        text("""
            INSERT INTO public.audit_events (id, actor, role, action, target, kind, tenant_id, created_at)
            VALUES (:id, :actor, :role, :action, :target, :kind, :tenant_id, :created_at)
        """),
        {
            "id": event_id,
            "actor": actor,
            "role": role,
            "action": action,
            "target": target,
            "kind": kind,
            "tenant_id": tenant_id,
            "created_at": now,
        },
    )
    await session.commit()

logger = logging.getLogger(__name__)

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


def _compute_run_name(run_number: int | None, created_at) -> str | None:
    if run_number is None or created_at is None:
        return None
    return f"run-{run_number:03d}-{created_at:%Y%m%d}"


def _row_to_response(row: dict) -> TrainingJobResponse:
    run_number = row.get("run_number")
    return TrainingJobResponse(
        id=row["id"],
        tenant_id=row["tenant_id"],
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
        run_number=run_number,
        run_name=_compute_run_name(run_number, row.get("created_at")),
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

    # Per-entity-type minimum, evaluated independently of the total-count gate
    # above. NER quality is bounded by the weakest label, so a corpus dominated
    # by one entity type can clear a large total while leaving other types
    # untrainable. Defaults to 0 (inert) — see ADR-010.
    min_per_type = int(os.environ.get("NER_MIN_ENTITIES_PER_TYPE", "0"))
    if min_per_type > 0:
        per_type_result = await session.execute(
            text(f"""
                WITH counts AS (
                    SELECT entity_type, COUNT(*) AS cnt FROM {schema}.spans GROUP BY entity_type
                ),
                types AS (
                    SELECT name AS entity_type FROM public.entity_definitions
                    WHERE tenant_id = :tid AND is_active = true
                    UNION
                    SELECT entity_type FROM counts
                )
                SELECT t.entity_type, COALESCE(c.cnt, 0) AS cnt
                FROM types t
                LEFT JOIN counts c ON c.entity_type = t.entity_type
                WHERE COALESCE(c.cnt, 0) < :minimum
                ORDER BY cnt ASC, t.entity_type ASC
            """),
            {"tid": tenant_id, "minimum": min_per_type},
        )
        short = [(r.entity_type, int(r.cnt or 0)) for r in per_type_result]
        if short:
            # Name the shortfalls so the caller can act without a second query.
            detail = ", ".join(f"{name} ({cnt})" for name, cnt in short)
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient annotated entities per type. Minimum {min_per_type} required "
                    f"for each entity type; short: {detail}."
                ),
            )

    job_id = str(uuid.uuid4())

    await TrainingJobRepository.create(session, tenant_id, job_id, None, celery_task_id=None)
    await _record_audit(
        session,
        actor=getattr(request.state, "user_email", ""),
        role=getattr(request.state, "role", ""),
        action="training_job.submit",
        target=job_id,
        kind="create",
        tenant_id=tenant_id,
    )
    created = await TrainingJobRepository.get_by_id(session, tenant_id, job_id)
    return _row_to_response(created)


async def _all_active_tenant_ids(session: AsyncSession) -> list[str]:
    result = await session.execute(text("SELECT id FROM public.tenants WHERE status = 'active'"))
    return [str(row[0]) for row in result.fetchall()]


async def _list_aggregated_across_tenants(session: AsyncSession, status_filter: str) -> list[dict]:
    tenant_ids = await _all_active_tenant_ids(session)
    all_rows: list[dict] = []
    for tid in tenant_ids:
        try:
            rows, _ = await TrainingJobRepository.list_by_tenant(session, tid, status_filter, page=1, per_page=1_000_000)
            all_rows.extend(rows)
        except Exception:
            logger.exception("system_admin training-jobs aggregation: query failed for tenant %s", tid)
            await session.rollback()
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    all_rows.sort(key=lambda r: r.get("created_at") or epoch, reverse=True)
    return all_rows


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
        if tenant_id:
            rows, total = await TrainingJobRepository.list_by_tenant(session, tenant_id, status, page, per_page)
        else:
            all_rows = await _list_aggregated_across_tenants(session, status or "pending_approval")
            total = len(all_rows)
            offset = (page - 1) * per_page
            rows = all_rows[offset : offset + per_page]
        return TrainingJobListResponse(
            items=[_row_to_response(r) for r in rows],
            total=total,
            page=page,
            per_page=per_page,
        )

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
    body: ApproveJobRequest,
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

    hyperparams = body.model_dump()
    task = celery_app.send_task("fine_tune_model", args=[tenant_id, job_id, hyperparams])
    await TrainingJobRepository.approve(
        session, tenant_id, job_id, hyperparams, celery_task_id=task.id,
    )
    await _record_audit(
        session,
        actor=getattr(request.state, "user_email", ""),
        role=getattr(request.state, "role", ""),
        action="training_job.approve",
        target=job_id,
        kind="approve",
        tenant_id=tenant_id,
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
    await _record_audit(
        session,
        actor=getattr(request.state, "user_email", ""),
        role=getattr(request.state, "role", ""),
        action="training_job.reject",
        target=job_id,
        kind="reject",
        tenant_id=tenant_id,
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
