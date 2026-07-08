import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.annotation_service.api.v1.import_ import get_known_entity_types_lower, strip_bio_prefix

router = APIRouter(tags=["annotation-review"])

ALLOWED_ROLES = {"annotator", "tenant_admin"}


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


def require_annotator_or_admin(request: Request) -> None:
    role = getattr(request.state, "role", None)
    if role not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "Only annotators and tenant admins can access this resource"},
        )


async def get_session() -> AsyncSession:
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


def generate_uuid():
    return str(uuid.uuid4())


def _parse_entity_types(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    types: list[str] = []
    for tag in tags:
        if tag != "O":
            base = strip_bio_prefix(tag)
            if base not in seen:
                seen.add(base)
                types.append(base)
    return types


@router.get("/api/v1/imported-annotations")
async def list_imported_annotations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source_file: str | None = Query(None),
    entity_type: str | None = Query(None),
    reviewed: bool | None = Query(None),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    require_annotator_or_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    conditions: list[str] = []
    params: dict = {}

    if source_file:
        conditions.append("ia.source_file = :source_file")
        params["source_file"] = source_file

    if entity_type:
        conditions.append("EXISTS (SELECT 1 FROM unnest(ia.tags) AS t WHERE t ILIKE :entity_pattern)")
        params["entity_pattern"] = f"B-{entity_type}"

    if reviewed is not None:
        conditions.append("ia.reviewed = :reviewed")
        params["reviewed"] = reviewed

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    count_query = text(f"SELECT COUNT(*) FROM {schema}.imported_annotations ia WHERE {where_clause}")
    count_result = await session.execute(count_query, params)
    total = count_result.scalar()

    offset = (page - 1) * per_page
    data_query = text(f"""
        SELECT ia.id, ia.source_file, ia.row_index, ia.tags, ia.reviewed, ia.reviewed_at, ia.reviewed_by
        FROM {schema}.imported_annotations ia
        WHERE {where_clause}
        ORDER BY ia.source_file, ia.row_index
        LIMIT :limit OFFSET :offset
    """)
    params["limit"] = per_page
    params["offset"] = offset
    data_result = await session.execute(data_query, params)
    rows = data_result.fetchall()

    items = []
    for r in rows:
        items.append({
            "id": r[0],
            "source_file": r[1],
            "row_index": r[2],
            "entity_types": _parse_entity_types(list(r[3])),
            "reviewed": r[4],
            "reviewed_at": r[5].isoformat() if r[5] else None,
            "reviewed_by": r[6],
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/api/v1/imported-annotations/{annotation_id}")
async def get_imported_annotation(
    annotation_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    require_annotator_or_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"""
            SELECT id, tokens, tags, source_file, row_index, reviewed, reviewed_at, reviewed_by, created_at
            FROM {schema}.imported_annotations
            WHERE id = :id
        """),
        {"id": annotation_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Imported annotation not found")

    return {
        "id": row[0],
        "tokens": list(row[1]),
        "tags": list(row[2]),
        "source_file": row[3],
        "row_index": row[4],
        "reviewed": row[5],
        "reviewed_at": row[6].isoformat() if row[6] else None,
        "reviewed_by": row[7],
        "created_at": row[8].isoformat() if row[8] else None,
        "entity_types": _parse_entity_types(list(row[2])),
    }


@router.patch("/api/v1/imported-annotations/{annotation_id}")
async def update_imported_annotation(
    annotation_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    require_annotator_or_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    user_id = getattr(request.state, "user_id", "unknown")

    tags = body.get("tags")
    if tags is None or not isinstance(tags, list):
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "tags must be an array"},
        )

    known_lower = await get_known_entity_types_lower(session, tenant_id)

    for tag in tags:
        if tag != "O":
            base = strip_bio_prefix(tag)
            if base.lower() not in known_lower:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "UNKNOWN_ENTITY_TYPE",
                        "message": f"Unknown entity type: {base}",
                    },
                )

    result = await session.execute(
        text(f"""
            UPDATE {schema}.imported_annotations
            SET tags = :tags,
                reviewed = TRUE,
                reviewed_at = NOW(),
                reviewed_by = :reviewed_by
            WHERE id = :id
            RETURNING id, tokens, tags, source_file, row_index, reviewed, reviewed_at, reviewed_by
        """),
        {
            "id": annotation_id,
            "tags": tags,
            "reviewed_by": user_id,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Imported annotation not found")

    await session.commit()

    return {
        "id": row[0],
        "tokens": list(row[1]),
        "tags": list(row[2]),
        "source_file": row[3],
        "row_index": row[4],
        "reviewed": row[5],
        "reviewed_at": row[6].isoformat() if row[6] else None,
        "reviewed_by": row[7],
    }


@router.post("/api/v1/imported-annotations/{annotation_id}/mark-reviewed")
async def mark_imported_annotation_reviewed(
    annotation_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    require_annotator_or_admin(request)
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    user_id = getattr(request.state, "user_id", "unknown")

    result = await session.execute(
        text(f"""
            UPDATE {schema}.imported_annotations
            SET reviewed = TRUE,
                reviewed_at = NOW(),
                reviewed_by = :reviewed_by
            WHERE id = :id
            RETURNING id, tokens, tags, source_file, row_index, reviewed, reviewed_at, reviewed_by
        """),
        {
            "id": annotation_id,
            "reviewed_by": user_id,
        },
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Imported annotation not found")

    await session.commit()

    return {
        "id": row[0],
        "tokens": list(row[1]),
        "tags": list(row[2]),
        "source_file": row[3],
        "row_index": row[4],
        "reviewed": row[5],
        "reviewed_at": row[6].isoformat() if row[6] else None,
        "reviewed_by": row[7],
    }
