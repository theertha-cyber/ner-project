import uuid
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from src.shared.exceptions import NotFoundError

router = APIRouter(tags=["spans"])


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


def _compute_bio_tags(doc_text: str, char_start: int, char_end: int, entity_type: str) -> list[str]:
    """Return BIO tag sequence for tokens in [char_start, char_end) using whitespace tokenization."""
    tags: list[str] = []
    char_offset = 0
    for token in doc_text.split():
        token_start = char_offset
        token_end = char_offset + len(token)
        # Advance past the token, then skip one space separator if present
        char_offset = token_end
        if char_offset < len(doc_text) and doc_text[char_offset] == " ":
            char_offset += 1
        if token_start >= char_end:
            break
        if token_end > char_start and token_start < char_end:
            tags.append(f"B-{entity_type}" if not tags else f"I-{entity_type}")
    return tags


async def validate_entity_type(session: AsyncSession, tenant_id: str, entity_type: str) -> None:
    from fastapi import HTTPException
    result = await session.execute(
        text("SELECT id FROM public.entity_definitions WHERE tenant_id = :tenant_id AND name = :name LIMIT 1"),
        {"tenant_id": tenant_id, "name": entity_type},
    )
    if not result.fetchone():
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": f"Entity type '{entity_type}' is not configured for this tenant"},
        )


@router.post("/api/v1/documents/{doc_id}/spans", status_code=201)
async def create_span(
    doc_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id FROM {schema}.documents WHERE id = :id AND status = 'processed' LIMIT 1"),
        {"id": doc_id},
    )
    if not result.fetchone():
        raise NotFoundError("Document", doc_id)

    entity_type = body.get("entity_type")
    if not entity_type:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "entity_type is required"})

    await validate_entity_type(session, tenant_id, entity_type)

    span_id = generate_uuid()
    char_start = body.get("char_start")
    char_end = body.get("char_end")
    text_val = body.get("text", "")

    if char_start is None or char_end is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": "char_start and char_end are required"})

    # Fetch document text to compute BIO tags
    text_row = await session.execute(
        text(f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id LIMIT 1"),
        {"doc_id": doc_id},
    )
    doc_text_row = text_row.fetchone()
    bio_tags = _compute_bio_tags(doc_text_row[0] or "", char_start, char_end, entity_type) if doc_text_row else []

    await session.execute(
        text(f"""
            INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence, bio_tags)
            VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, :confidence, :bio_tags)
        """),
        {
            "id": span_id,
            "doc_id": doc_id,
            "entity_type": entity_type,
            "char_start": char_start,
            "char_end": char_end,
            "text_val": text_val,
            "confidence": body.get("confidence", 1.0),
            "bio_tags": bio_tags,
        },
    )
    await session.commit()

    return {
        "id": span_id,
        "entity_type": entity_type,
        "char_start": char_start,
        "char_end": char_end,
        "text": text_val,
        "confidence": body.get("confidence", 1.0),
        "bio_tags": bio_tags,
    }


@router.get("/api/v1/documents/{doc_id}/spans")
async def list_spans(
    doc_id: str,
    type_filter: str | None = Query(None, alias="type"),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    if type_filter == "suggested":
        result = await session.execute(
            text(f"SELECT id, entity_type, char_start, char_end, text_content, confidence, created_at FROM {schema}.suggested_spans WHERE document_id = :doc_id ORDER BY char_start"),
            {"doc_id": doc_id},
        )
    else:
        result = await session.execute(
            text(f"SELECT id, entity_type, char_start, char_end, text_content, confidence, created_at FROM {schema}.spans WHERE document_id = :doc_id ORDER BY char_start"),
            {"doc_id": doc_id},
        )

    rows = result.fetchall()
    return [
        {
            "id": r[0],
            "entity_type": r[1],
            "char_start": r[2],
            "char_end": r[3],
            "text": r[4],
            "confidence": float(r[5]),
            "created_at": str(r[6]),
        }
        for r in rows
    ]


@router.patch("/api/v1/documents/{doc_id}/spans/{span_id}")
async def update_span(
    doc_id: str,
    span_id: str,
    body: dict,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id, char_start, char_end FROM {schema}.spans WHERE id = :id AND document_id = :doc_id LIMIT 1"),
        {"id": span_id, "doc_id": doc_id},
    )
    existing = result.fetchone()
    if not existing:
        raise NotFoundError("Span", span_id)

    if "entity_type" in body:
        await validate_entity_type(session, tenant_id, body["entity_type"])

    updates = []
    params = {"id": span_id, "doc_id": doc_id}
    field_map = {"text": "text_content"}
    for api_field, db_field in field_map.items():
        if api_field in body:
            updates.append(f"{db_field} = :{api_field}_val")
            params[f"{api_field}_val"] = body[api_field]
    for field in ("entity_type", "char_start", "char_end", "confidence"):
        if field in body:
            updates.append(f"{field} = :{field}")
            params[field] = body[field]

    # Recompute bio_tags when entity_type changes
    if "entity_type" in body:
        char_start = body.get("char_start", existing[1])
        char_end = body.get("char_end", existing[2])
        text_row = await session.execute(
            text(f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id LIMIT 1"),
            {"doc_id": doc_id},
        )
        doc_text_row = text_row.fetchone()
        bio_tags = _compute_bio_tags(doc_text_row[0] or "", char_start, char_end, body["entity_type"]) if doc_text_row else []
        updates.append("bio_tags = :bio_tags")
        params["bio_tags"] = bio_tags

    if updates:
        await session.execute(
            text(f"UPDATE {schema}.spans SET {', '.join(updates)} WHERE id = :id AND document_id = :doc_id"),
            params,
        )
        await session.commit()

    result = await session.execute(
        text(f"SELECT id, entity_type, char_start, char_end, text_content, confidence, bio_tags FROM {schema}.spans WHERE id = :id"),
        {"id": span_id},
    )
    r = result.fetchone()
    return {
        "id": r[0],
        "entity_type": r[1],
        "char_start": r[2],
        "char_end": r[3],
        "text": r[4],
        "confidence": float(r[5]),
        "bio_tags": r[6],
    }


@router.delete("/api/v1/documents/{doc_id}/spans/{span_id}", status_code=204)
async def delete_span(
    doc_id: str,
    span_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id FROM {schema}.spans WHERE id = :id AND document_id = :doc_id LIMIT 1"),
        {"id": span_id, "doc_id": doc_id},
    )
    if not result.fetchone():
        raise NotFoundError("Span", span_id)

    await session.execute(
        text(f"DELETE FROM {schema}.spans WHERE id = :id AND document_id = :doc_id"),
        {"id": span_id, "doc_id": doc_id},
    )
    await session.commit()
    return None


@router.post("/api/v1/documents/{doc_id}/prelabel")
async def prelabel_document(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id, text FROM {schema}.document_text_spans WHERE document_id = :doc_id ORDER BY span_index LIMIT 1"),
        {"doc_id": doc_id},
    )
    row = result.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail={"code": "NO_TEXT", "message": "Document has no extracted text"})

    doc_text = row[1] or ""

    result = await session.execute(
        text("SELECT name, base_label_mapping FROM public.entity_definitions WHERE tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
    entity_rows = result.fetchall()

    label_mapping = {}
    for er in entity_rows:
        mapping = er[1]
        if mapping and isinstance(mapping, dict):
            for model_label, tenant_labels in mapping.items():
                if isinstance(tenant_labels, list):
                    for tl in tenant_labels:
                        label_mapping[tl] = er[0]
                elif isinstance(tenant_labels, str):
                    label_mapping[tenant_labels] = er[0]

    import re
    suggested = []
    seen_positions = set()
    for keyword, ent_type in label_mapping.items():
        for match in re.finditer(re.escape(keyword), doc_text):
            start = match.start()
            end = match.end()
            if (start, end, ent_type) in seen_positions:
                continue
            seen_positions.add((start, end, ent_type))
            suggested.append({
                "id": generate_uuid(),
                "entity_type": ent_type,
                "char_start": start,
                "char_end": end,
                "text": match.group(),
                "confidence": 0.85,
            })

    await session.execute(
        text(f"DELETE FROM {schema}.suggested_spans WHERE document_id = :doc_id"),
        {"doc_id": doc_id},
    )

    for s in suggested:
        await session.execute(
            text(f"""
                INSERT INTO {schema}.suggested_spans (id, document_id, entity_type, char_start, char_end, text_content, confidence)
                VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, :confidence)
            """),
            {
                "id": s["id"],
                "doc_id": doc_id,
                "entity_type": s["entity_type"],
                "char_start": s["char_start"],
                "char_end": s["char_end"],
                "text_val": s["text"],
                "confidence": s["confidence"],
            },
        )

    await session.commit()
    return suggested


@router.post("/api/v1/documents/{doc_id}/spans/promote/{suggest_id}", status_code=201)
async def promote_suggested_span(
    doc_id: str,
    suggest_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT id, entity_type, char_start, char_end, text_content, confidence FROM {schema}.suggested_spans WHERE id = :id AND document_id = :doc_id LIMIT 1"),
        {"id": suggest_id, "doc_id": doc_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("SuggestedSpan", suggest_id)

    span_id = generate_uuid()
    await session.execute(
        text(f"""
            INSERT INTO {schema}.spans (id, document_id, entity_type, char_start, char_end, text_content, confidence)
            VALUES (:id, :doc_id, :entity_type, :char_start, :char_end, :text_val, :confidence)
        """),
        {
            "id": span_id,
            "doc_id": doc_id,
            "entity_type": row[1],
            "char_start": row[2],
            "char_end": row[3],
            "text_val": row[4],
            "confidence": float(row[5]),
        },
    )

    await session.execute(
        text(f"DELETE FROM {schema}.suggested_spans WHERE id = :id"),
        {"id": suggest_id},
    )

    await session.commit()

    return {
        "id": span_id,
        "entity_type": row[1],
        "char_start": row[2],
        "char_end": row[3],
        "text": row[4],
        "confidence": float(row[5]),
    }
