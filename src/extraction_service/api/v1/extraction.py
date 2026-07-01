import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.extraction_service.api.v1.schemas import (
    ExtractRequest,
    ExtractResponse,
    ExtractedEntity,
    BatchExtractResponse,
    BatchRunStatus,
)
from src.extraction_service.services.extraction_engine import infer
from src.extraction_service.services.entity_store import get_extraction_run
from src.extraction_service.dependencies import get_db
from src.shared.config import settings

router = APIRouter(prefix="/api/v1", tags=["extraction"])


def _get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


def _get_role(request: Request) -> str:
    role = getattr(request.state, "role", None)
    if role is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return role


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def _tokenize_text(text: str) -> list[str]:
    return text.split()


@router.post("/extract", response_model=ExtractResponse)
async def extract_entities(
    body: ExtractRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)

    role = _get_role(request)
    if role not in ("tenant_admin", "business_user"):
        raise HTTPException(status_code=403, detail="Only tenant admins and business users can extract entities")

    tokens = _tokenize_text(body.text)
    result = await infer(tenant_id, tokens, request)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="No active model is available for this tenant",
        )

    predictions = result.get("predictions", result if isinstance(result, list) else [])
    model_version = result.get("model_version", "0")

    char_offset = 0
    entities = []
    for prediction in predictions:
        token_text = prediction["token"]
        start = body.text.find(token_text, char_offset)
        if start == -1:
            start = char_offset
        end = start + len(token_text)
        char_offset = end

        entity = ExtractedEntity(
            entity_type=prediction["label"],
            value=token_text,
            confidence=prediction["confidence"],
            start_offset=start,
            end_offset=end,
        )
        entities.append(entity)

    threshold = settings.confidence_threshold
    entities = [e for e in entities if e.confidence >= threshold]
    entities.sort(key=lambda e: e.confidence, reverse=True)

    return ExtractResponse(entities=entities, model_version=model_version)


@router.post("/extract-batch", response_model=BatchExtractResponse, status_code=202)
async def trigger_batch_extraction(
    request: Request,
    document_ids: str | None = Query(None, alias="documentIds", description="Comma-separated document IDs; omit to process all eligible documents"),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)

    role = _get_role(request)
    if role not in ("tenant_admin", "business_user"):
        raise HTTPException(status_code=403, detail="Only tenant admins and business users can trigger batch extraction")

    if document_ids:
        doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    else:
        schema = _schema(tenant_id)
        result = await db.execute(
            text(f"SELECT id FROM {schema}.documents WHERE status = 'processed'")
        )
        doc_ids = [row[0] for row in result.fetchall()]

    if not doc_ids:
        raise HTTPException(status_code=422, detail="No eligible documents found for batch extraction")

    run_id = str(uuid.uuid4())
    schema = _schema(tenant_id)
    await db.execute(
        text(f"""
            INSERT INTO {schema}.extraction_runs
                (id, tenant_id, document_id, model_version, status, total_documents,
                 processed_count, skipped_count, failed_count, started_at)
            VALUES (:id, :tenant_id, NULL, NULL, 'queued', :total_docs, 0, 0, 0, :started_at)
        """),
        {
            "id": run_id,
            "tenant_id": tenant_id,
            "total_docs": len(doc_ids),
            "started_at": datetime.now(timezone.utc),
        },
    )
    await db.commit()

    from src.extraction_service.celery_app import celery_app

    celery_app.send_task(
        "run_batch_extraction",
        args=[tenant_id, run_id, doc_ids],
        queue=settings.extraction_celery_queue,
    )

    return BatchExtractResponse(run_id=run_id, status="queued")


@router.get("/extract-batch/{run_id}", response_model=BatchRunStatus)
async def get_batch_status(
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)

    run = await get_extraction_run(db, tenant_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Extraction run not found")

    return BatchRunStatus(
        status=run.get("status", "unknown"),
        total_documents=run.get("total_documents"),
        processed_count=run.get("processed_count"),
        skipped_count=run.get("skipped_count"),
        failed_count=run.get("failed_count"),
        completed_at=run.get("completed_at"),
        started_at=run.get("started_at"),
        model_version=run.get("model_version"),
    )
