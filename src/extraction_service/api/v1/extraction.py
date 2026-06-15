import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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

router = APIRouter(prefix="/api/v1/tenants/{tid}", tags=["extraction"])


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


def _tokenize_text(text: str) -> list[str]:
    return text.split()


@router.post("/extract", response_model=ExtractResponse)
async def extract_entities(
    tid: str,
    body: ExtractRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    role = _get_role(request)
    if role not in ("tenant_admin", "business_user"):
        raise HTTPException(status_code=403, detail="Only tenant admins and business users can extract entities")

    tokens = _tokenize_text(body.text)
    result = await infer(tenant_id, tokens)
    if result is None:
        raise HTTPException(
            status_code=400,
            detail="No active model is available for this tenant",
        )

    char_offset = 0
    entities = []
    for prediction in result:
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

    return ExtractResponse(entities=entities)


@router.post("/extract-batch", response_model=BatchExtractResponse)
async def trigger_batch_extraction(
    tid: str,
    request: Request,
    document_ids: str = Query(..., alias="documentIds", description="Comma-separated document IDs"),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    role = _get_role(request)
    if role != "tenant_admin":
        raise HTTPException(status_code=403, detail="Only tenant admins can trigger batch extraction")

    doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    if not doc_ids:
        raise HTTPException(status_code=422, detail="At least one documentId is required")

    tokens = ["test"]
    model_available = await infer(tenant_id, tokens)
    if model_available is None:
        raise HTTPException(
            status_code=400,
            detail="No active model is available for this tenant",
        )

    run_id = str(uuid.uuid4())
    from src.extraction_service.celery_app import celery_app

    celery_app.send_task(
        "run_batch_extraction",
        args=[tenant_id, run_id, doc_ids],
        queue=settings.extraction_celery_queue,
    )

    return BatchExtractResponse(run_id=run_id, status="queued")


@router.get("/extract-batch/{run_id}", response_model=BatchRunStatus)
async def get_batch_status(
    tid: str,
    run_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    run = await get_extraction_run(db, tenant_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Extraction run not found")

    return BatchRunStatus(
        status=run.get("status", "unknown"),
        total_documents=None,
        processed_count=None,
        skipped_count=None,
        failed_count=None,
        completed_at=run.get("completed_at"),
        started_at=run.get("started_at"),
    )
