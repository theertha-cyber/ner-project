from fastapi import APIRouter, Depends, Query, Request, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from src.shared.exceptions import NotFoundError
from src.document_service.ingestion import (
    PLATFORM_UPLOAD_SOURCE_ID,
    SOURCE_TYPE_PLATFORM_UPLOAD,
    ActorKind,
    ContentAccess,
    ContentAcquisition,
    DocumentIngestionService,
    FileTooLarge,
    IngestingActor,
    IncompatibleRetention,
    NormalizedDocument,
    SourceReference,
    UnsupportedFileType,
)
from src.extraction_service.services.relational_projection import (
    build_relational_delete_statements,
)
from src.shared.entity_views import (
    list_existing_generated_tables,
    load_definition_specs,
)
from src.shared.tenant_schema import schema_for_tenant as _schema

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

VALID_PURPOSES = {"query", "training"}

# Upload purpose is a role capability, not an uploader choice: tenant admins upload
# documents for annotation, business users upload documents for querying. Roles absent
# from this map (system_admin, annotator) keep both purposes.
ROLE_ALLOWED_PURPOSES = {
    "tenant_admin": {"training"},
    "business_user": {"query"},
}


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


async def get_session() -> AsyncSession:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


# The one ingestion operation this route adapts onto. Module-level so a test can swap
# the dispatcher or either content store without reaching into the route body.
ingestion_service = DocumentIngestionService()


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    purpose: str = Form("query"),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    if purpose not in VALID_PURPOSES:
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": "purpose must be 'query' or 'training'"},
        )

    role = getattr(request.state, "role", None) if request is not None else None
    allowed_purposes = ROLE_ALLOWED_PURPOSES.get(role)
    if allowed_purposes is not None and purpose not in allowed_purposes:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PURPOSE_NOT_ALLOWED",
                "message": f"Role '{role}' may only upload documents with purpose {sorted(allowed_purposes)}",
            },
        )

    file_data = await file.read()

    tenant_id = get_tenant_id(request)
    normalized = NormalizedDocument(
        # Trusted: it comes from the JWT the middleware resolved, never from the payload.
        tenant_id=tenant_id,
        filename=file.filename,
        content=ContentAccess.from_bytes(file_data),
        purpose=purpose,
        actor=IngestingActor(
            kind=ActorKind.HUMAN,
            user_id=getattr(request.state, "user_id", None),
        ),
        source=SourceReference(
            source_type=SOURCE_TYPE_PLATFORM_UPLOAD,
            source_id=PLATFORM_UPLOAD_SOURCE_ID,
        ),
        # Once the HTTP request ends the browser cannot be asked for these bytes again.
        acquisition=ContentAcquisition.SINGLE_USE,
        declared_media_type=file.content_type,
        declared_size=file.size,
    )

    try:
        result = await ingestion_service.ingest(session, normalized)
    except UnsupportedFileType as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"File type '{exc.extension}' is not supported. Allowed: .pdf, .jpg, .jpeg, .png, .tif, .tiff",
            },
        )
    except FileTooLarge as exc:
        raise HTTPException(
            status_code=413,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"File exceeds 50MB limit ({exc.size_bytes / 1024 / 1024:.1f}MB)",
            },
        )
    except IncompatibleRetention as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "INCOMPATIBLE_RETENTION", "message": str(exc)},
        )

    return {
        "id": result.document_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "pending",
        "file_size": result.file_size,
        "checksum": result.checksum,
        "duplicate_of": result.duplicate_of,
    }


@router.get("")
async def list_documents(
    status_filter: str | None = Query(None, alias="status"),
    purpose: str | None = Query(None),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    role = getattr(request.state, "role", None)
    user_id = getattr(request.state, "user_id", None)
    # Each condition is a template over the table alias, because the count query names
    # the table bare and the listing query aliases it `d`. Prefixing a rendered string
    # cannot express a condition over two columns.
    conditions = ["{p}tenant_id = :tid"]
    params = {"tid": tenant_id}

    if role != "tenant_admin":
        # Ownership scoping applies only to documents a *person* ingested. A
        # system-ingested document is visible tenant-wide, because retrieval filters on
        # purpose alone (`retriever.py`) and would otherwise cite a document this listing
        # denied existed.
        conditions.append("({p}ingested_by_kind <> 'human' OR {p}uploaded_by = :uploaded_by)")
        params["uploaded_by"] = user_id

    if status_filter:
        conditions.append("{p}status = :status")
        params["status"] = status_filter

    if purpose:
        conditions.append("{p}purpose = :purpose")
        params["purpose"] = purpose

    if search:
        conditions.append("{p}filename ILIKE :search")
        params["search"] = f"%{search}%"

    where = " AND ".join(c.format(p="") for c in conditions)
    offset = (page - 1) * per_page

    # LEFT JOIN so a document whose uploader was deleted (or that predates the
    # uploaded_by column) still lists, with a null email the client renders as unknown.
    document_where = " AND ".join(c.format(p="d.") for c in conditions)
    result = await session.execute(
        text(f"""
            SELECT d.id, d.filename, d.content_type, d.file_size, d.status, d.error_message,
                   d.purpose, d.uploaded_by, u.email AS uploaded_by_email,
                   d.created_at, d.updated_at
            FROM {_schema(tenant_id)}.documents d
            LEFT JOIN public.tenant_users u ON u.id = d.uploaded_by
            WHERE {document_where}
            ORDER BY d.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": per_page, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await session.execute(
        text(f"SELECT COUNT(*) FROM {_schema(tenant_id)}.documents WHERE {where}"),
        params,
    )
    total = count_result.scalar()

    documents_list = [
        {
            "id": r.id,
            "filename": r.filename,
            "content_type": r.content_type,
            "file_size": r.file_size,
            "status": r.status,
            "error_message": r.error_message,
            "purpose": r.purpose,
            "uploaded_by": r.uploaded_by,
            "uploaded_by_email": r.uploaded_by_email,
            "created_at": str(r.created_at),
            "updated_at": str(r.updated_at),
        }
        for r in rows
    ]

    return {"documents": documents_list, "total": total, "page": page, "per_page": per_page}


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    result = await session.execute(
        text(f"SELECT id, filename, content_type, file_size, checksum, status, error_message, blob_path, created_at, updated_at FROM {_schema(tenant_id)}.documents WHERE id = :id AND tenant_id = :tid"),
        {"id": doc_id, "tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("Document", doc_id)

    return {
        "document": {
            "id": row.id,
            "filename": row.filename,
            "content_type": row.content_type,
            "file_size": row.file_size,
            "checksum": row.checksum,
            "status": row.status,
            "error_message": row.error_message,
            "created_at": str(row.created_at),
            "updated_at": str(row.updated_at),
        }
    }


@router.get("/{doc_id}/text")
async def get_document_text(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)

    result = await session.execute(
        text(f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id ORDER BY span_index"),
        {"doc_id": doc_id},
    )
    rows = result.fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"No text found for document {doc_id}"})

    combined_text = "\n".join(r[0] or "" for r in rows)
    return {"text": combined_text}


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    result = await session.execute(
        text(f"SELECT id, status FROM {_schema(tenant_id)}.documents WHERE id = :id AND tenant_id = :tid"),
        {"id": doc_id, "tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("Document", doc_id)

    await session.execute(
        text(f"DELETE FROM {_schema(tenant_id)}.document_chunks WHERE document_id = :id"),
        {"id": doc_id},
    )
    await session.execute(
        text(f"DELETE FROM {_schema(tenant_id)}.document_text_spans WHERE document_id = :id"),
        {"id": doc_id},
    )
    await session.execute(
        text(f"DELETE FROM {_schema(tenant_id)}.extracted_entities WHERE document_id = :id"),
        {"id": doc_id},
    )
    await session.execute(
        text(f"DELETE FROM {_schema(tenant_id)}.document_entities WHERE document_id = :id"),
        {"id": doc_id},
    )
    # The generated relational tables declare no foreign key to `documents`, so this
    # propagation is what maintains referential integrity — without it a deleted document
    # would keep answering generated SQL queries. The statements come from the same pure
    # builder the extraction worker uses, so the sync and async callers cannot diverge into a
    # half-deleted document. Inactive definitions are covered too: their tables are retained,
    # so their rows would otherwise survive.
    specs = await load_definition_specs(session, tenant_id)
    existing = await list_existing_generated_tables(session, _schema(tenant_id))
    for statement, params in build_relational_delete_statements(
        _schema(tenant_id), doc_id, specs, existing
    ):
        await session.execute(text(statement), params)
    await session.execute(
        text(f"UPDATE {_schema(tenant_id)}.documents SET status = 'deleted' WHERE id = :id"),
        {"id": doc_id},
    )
    await session.commit()

    return {"status": "deleted", "id": doc_id}
