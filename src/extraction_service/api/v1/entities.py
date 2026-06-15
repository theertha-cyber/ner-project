from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from src.extraction_service.api.v1.schemas import (
    EntityItem,
    EntityListResponse,
    EntityPatchRequest,
)
from src.extraction_service.services.entity_store import (
    query_entities,
    update_entity_review,
)
from src.extraction_service.dependencies import get_db

router = APIRouter(prefix="/api/v1/tenants/{tid}", tags=["entities"])


def _get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


def _get_user_id(request: Request) -> str:
    uid = getattr(request.state, "user_id", None)
    if uid is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return uid


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    tid: str,
    request: Request,
    document_id: str | None = Query(None, alias="documentId"),
    entity_type: str | None = Query(None, alias="type"),
    min_confidence: float | None = Query(None, alias="minConfidence"),
    review_status: str | None = Query(None, alias="reviewStatus"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    rows, total = await query_entities(
        db, tenant_id,
        document_id=document_id,
        entity_type=entity_type,
        min_confidence=min_confidence,
        review_status=review_status,
        page=page,
        per_page=per_page,
    )

    items = [EntityItem(**r) for r in rows]
    return EntityListResponse(items=items, total=total, page=page, per_page=per_page)


@router.patch("/entities/{entity_id}", response_model=EntityItem)
async def patch_entity(
    tid: str,
    entity_id: str,
    body: EntityPatchRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    tenant_id = _get_tenant_id(request)
    if tid != tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")

    user_id = _get_user_id(request)

    result = await update_entity_review(
        db, tenant_id, entity_id,
        review_status=body.review_status,
        corrected_value=body.corrected_value,
        correction_notes=body.correction_notes,
        corrected_by=user_id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Entity not found")

    return EntityItem(**result)
