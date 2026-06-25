import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.exceptions import NotFoundError, ConflictError

router = APIRouter(tags=["tasks"])


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


def get_tenant_id(request: Request) -> str:
    from fastapi import HTTPException
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


def generate_uuid():
    return str(uuid.uuid4())


@router.post("/api/v1/annotation-tasks", status_code=201)
async def create_task(
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    document_id = body.get("document_id")
    annotator_user_id = body.get("annotator_user_id")

    if not document_id or not annotator_user_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "document_id and annotator_user_id are required"})

    result = await session.execute(
        text(f"""
            SELECT id FROM {schema}.annotation_tasks
            WHERE document_id = :doc_id AND status IN ('unannotated', 'in-progress')
            LIMIT 1
        """),
        {"doc_id": document_id},
    )
    if result.fetchone():
        raise ConflictError("AnnotationTask", "document_id", document_id)

    task_id = generate_uuid()
    await session.execute(
        text(f"""
            INSERT INTO {schema}.annotation_tasks (id, document_id, annotator_user_id, status)
            VALUES (:id, :doc_id, :annotator_id, 'unannotated')
        """),
        {"id": task_id, "doc_id": document_id, "annotator_id": annotator_user_id},
    )
    await session.commit()

    return {
        "id": task_id,
        "document_id": document_id,
        "annotator_user_id": annotator_user_id,
        "status": "unannotated",
    }


@router.get("/api/v1/annotation-tasks")
async def list_tasks(
    status_filter: str | None = Query(None, alias="status"),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    base_query = f"""
        SELECT
            t.id,
            t.document_id,
            t.annotator_user_id,
            t.status,
            t.created_at,
            t.updated_at,
            d.filename,
            d.status AS document_status,
            COUNT(s.id) FILTER (WHERE s.id IS NOT NULL) AS span_count
        FROM {schema}.annotation_tasks t
        LEFT JOIN {schema}.documents d ON d.id = t.document_id
        LEFT JOIN {schema}.spans s ON s.document_id = t.document_id
    """

    if status_filter:
        result = await session.execute(
            text(base_query + " WHERE t.status = :status GROUP BY t.id, d.filename, d.status ORDER BY t.created_at DESC"),
            {"status": status_filter},
        )
    else:
        result = await session.execute(
            text(base_query + " GROUP BY t.id, d.filename, d.status ORDER BY t.created_at DESC"),
        )

    rows = result.fetchall()
    return [
        {
            "id": r[0],
            "document_id": r[1],
            "annotator_user_id": r[2],
            "status": r[3],
            "created_at": str(r[4]),
            "updated_at": str(r[5]) if r[5] else None,
            "filename": r[6],
            "document_status": r[7],
            "span_count": r[8] or 0,
        }
        for r in rows
    ]


@router.patch("/api/v1/annotation-tasks/{task_id}")
async def update_task(
    task_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id, status, document_id FROM {schema}.annotation_tasks WHERE id = :id LIMIT 1"),
        {"id": task_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("AnnotationTask", task_id)

    current_status = row[1]
    doc_id = row[2]
    new_status = body.get("status")

    if not new_status:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "status is required"})

    valid_transitions = {
        "unannotated": ["in-progress"],
        "in-progress": ["completed"],
    }

    allowed = valid_transitions.get(current_status, [])
    if new_status not in allowed:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TRANSITION", "message": f"Cannot transition from '{current_status}' to '{new_status}'"},
        )

    if new_status == "completed":
        span_result = await session.execute(
            text(f"SELECT COUNT(*) FROM {schema}.spans WHERE document_id = :doc_id"),
            {"doc_id": doc_id},
        )
        span_count = span_result.scalar()
        if span_count == 0:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=422,
                detail={"code": "NO_SPANS", "message": "Document must have at least one confirmed span before task can be completed"},
            )

    await session.execute(
        text(f"UPDATE {schema}.annotation_tasks SET status = :status WHERE id = :id"),
        {"status": new_status, "id": task_id},
    )
    await session.commit()

    return {
        "id": task_id,
        "status": new_status,
    }
