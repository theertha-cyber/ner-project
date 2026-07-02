import uuid
from datetime import datetime, timezone
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


async def create_extraction_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    document_id: str,
    model_version: str,
    status: str = "queued",
):
    schema = _schema(tenant_id)
    await db.execute(
        text(f"""
            INSERT INTO {schema}.extraction_runs (id, tenant_id, document_id, model_version, status, started_at)
            VALUES (:id, :tenant_id, :document_id, :model_version, :status, :started_at)
        """),
        {
            "id": run_id,
            "tenant_id": tenant_id,
            "document_id": document_id,
            "model_version": model_version,
            "status": status,
            "started_at": datetime.now(timezone.utc),
        },
    )
    await db.commit()


async def get_extraction_run(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
) -> dict | None:
    schema = _schema(tenant_id)
    result = await db.execute(
        text(f"SELECT * FROM {schema}.extraction_runs WHERE id = :id"),
        {"id": run_id},
    )
    row = result.fetchone()
    if row is None:
        return None
    return dict(row._mapping)


async def list_extraction_runs(
    db: AsyncSession,
    tenant_id: str,
    limit: int = 50,
) -> list[dict]:
    schema = _schema(tenant_id)
    result = await db.execute(
        text(f"""
            SELECT * FROM {schema}.extraction_runs
            ORDER BY started_at DESC
            LIMIT :limit
        """),
        {"limit": limit},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def find_existing_run(
    db: AsyncSession,
    tenant_id: str,
    document_id: str,
    model_version: str,
) -> dict | None:
    schema = _schema(tenant_id)
    result = await db.execute(
        text(f"""
            SELECT id FROM {schema}.extraction_runs
            WHERE document_id = :document_id AND model_version = :model_version AND status = 'completed'
            LIMIT 1
        """),
        {"document_id": document_id, "model_version": model_version},
    )
    row = result.fetchone()
    if row is None:
        return None
    return dict(row._mapping)


async def insert_entity(
    db: AsyncSession,
    tenant_id: str,
    run_id: str,
    entity_id: str,
    value: str,
    confidence: float,
    normalized_value: str | None = None,
    source_span_id: str | None = None,
):
    schema = _schema(tenant_id)
    await db.execute(
        text(f"""
            INSERT INTO {schema}.extracted_entities
                (id, run_id, entity_id, value, confidence, normalized_value, source_span_id, review_status)
            VALUES (:id, :run_id, :entity_id, :value, :confidence, :normalized_value, :source_span_id, 'unreviewed')
        """),
        {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "entity_id": entity_id,
            "value": value,
            "confidence": confidence,
            "normalized_value": normalized_value,
            "source_span_id": source_span_id,
        },
    )


async def query_entities(
    db: AsyncSession,
    tenant_id: str,
    document_id: str | None = None,
    entity_type: str | None = None,
    min_confidence: float | None = None,
    review_status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict], int]:
    schema = _schema(tenant_id)
    conditions = []
    params = {}

    if document_id:
        conditions.append("e.document_id = :document_id")
        params["document_id"] = document_id
    if entity_type:
        conditions.append("e.entity_id = :entity_type")
        params["entity_type"] = entity_type
    if min_confidence is not None:
        conditions.append("e.confidence >= :min_confidence")
        params["min_confidence"] = min_confidence
    if review_status:
        conditions.append("e.review_status = :review_status")
        params["review_status"] = review_status

    where_clause = " AND ".join(conditions) if conditions else "TRUE"
    where_clause = where_clause.replace("{schema}", schema)

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM {schema}.extracted_entities e WHERE {where_clause}"),
        params,
    )
    total = count_result.scalar() or 0

    offset = (page - 1) * per_page
    result = await db.execute(
        text(f"""
            SELECT e.* FROM {schema}.extracted_entities e
            WHERE {where_clause}
            ORDER BY e.confidence DESC
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": per_page, "offset": offset},
    )
    rows = [dict(r._mapping) for r in result.fetchall()]
    return rows, total


async def update_entity_review(
    db: AsyncSession,
    tenant_id: str,
    entity_id: str,
    review_status: str,
    corrected_value: str | None = None,
    correction_notes: str | None = None,
    corrected_by: str | None = None,
) -> dict | None:
    schema = _schema(tenant_id)
    result = await db.execute(
        text(f"SELECT * FROM {schema}.extracted_entities WHERE id = :id"),
        {"id": entity_id},
    )
    row = result.fetchone()
    if row is None:
        return None

    await db.execute(
        text(f"""
            UPDATE {schema}.extracted_entities
            SET review_status = :review_status,
                corrected_value = :corrected_value,
                corrected_by = :corrected_by,
                correction_notes = :correction_notes
            WHERE id = :id
        """),
        {
            "review_status": review_status,
            "corrected_value": corrected_value,
            "corrected_by": corrected_by,
            "correction_notes": correction_notes,
            "id": entity_id,
        },
    )
    await db.commit()

    result = await db.execute(
        text(f"SELECT * FROM {schema}.extracted_entities WHERE id = :id"),
        {"id": entity_id},
    )
    return dict(result.fetchone()._mapping)
