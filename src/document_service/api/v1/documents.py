import uuid
from fastapi import APIRouter, Depends, Query, Request, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from src.shared.exceptions import NotFoundError
from src.document_service.services.content_hash import compute_content_hash
from src.document_service.services.ocr_worker import is_allowed_file, get_extension, trigger_ocr
from src.document_service.services.storage import MinioStorageClient

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
VALID_PURPOSES = {"query", "training"}

# Upload purpose is a role capability, not an uploader choice: tenant admins upload
# documents for annotation, business users upload documents for querying. Roles absent
# from this map (system_admin, annotator) keep both purposes.
ROLE_ALLOWED_PURPOSES = {
    "tenant_admin": {"training"},
    "business_user": {"query"},
}


def _schema(tenant_id: str) -> str:
    return f"tenant_{tenant_id.replace('-', '_')}"


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


def generate_uuid():
    return str(uuid.uuid4())


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

    if not is_allowed_file(file.filename or ""):
        raise HTTPException(
            status_code=422,
            detail={"code": "VALIDATION_ERROR", "message": f"File type '{get_extension(file.filename or '')}' is not supported. Allowed: .pdf, .jpg, .jpeg, .png, .tif, .tiff"},
        )

    file_data = await file.read()
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={"code": "FILE_TOO_LARGE", "message": f"File exceeds 50MB limit ({len(file_data) / 1024 / 1024:.1f}MB)"},
        )

    tenant_id = get_tenant_id(request)
    uploaded_by = getattr(request.state, "user_id", None)
    doc_id = generate_uuid()
    ext = get_extension(file.filename or "").lstrip(".")
    blob_path = f"tenants/{tenant_id}/documents/{doc_id}.{ext}"
    checksum = compute_content_hash(file_data)

    # Identify (never reject or merge) an earlier upload of byte-identical content.
    # Scoped to this tenant's schema and tenant_id — duplicates never cross tenants —
    # and skips soft-deleted rows the API would no longer serve. Ordered by
    # created_at so three copies all point at the original, not at each other.
    duplicate_result = await session.execute(
        text(f"""
            SELECT id FROM {_schema(tenant_id)}.documents
            WHERE tenant_id = :tid AND checksum = :checksum AND status != 'deleted'
            ORDER BY created_at
            LIMIT 1
        """),
        {"tid": tenant_id, "checksum": checksum},
    )
    duplicate_row = duplicate_result.fetchone()
    duplicate_of = duplicate_row[0] if duplicate_row else None

    storage = MinioStorageClient()
    storage.upload_file(tenant_id, doc_id, ext, file_data)

    await session.execute(
        text(f"""
            INSERT INTO {_schema(tenant_id)}.documents (id, tenant_id, filename, content_type, file_size, checksum, status, blob_path, purpose, uploaded_by)
            VALUES (:id, :tid, :filename, :content_type, :file_size, :checksum, 'pending', :blob_path, :purpose, :uploaded_by)
        """),
        {
            "id": doc_id,
            "tid": tenant_id,
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "file_size": len(file_data),
            "checksum": checksum,
            "blob_path": blob_path,
            "purpose": purpose,
            "uploaded_by": uploaded_by,
        },
    )
    await session.commit()

    trigger_ocr(doc_id, tenant_id, blob_path, file.content_type or "")

    return {
        "id": doc_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "pending",
        "file_size": len(file_data),
        "checksum": checksum,
        "duplicate_of": duplicate_of,
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
    conditions = ["tenant_id = :tid"]
    params = {"tid": tenant_id}

    if role != "tenant_admin":
        conditions.append("uploaded_by = :uploaded_by")
        params["uploaded_by"] = user_id

    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter

    if purpose:
        conditions.append("purpose = :purpose")
        params["purpose"] = purpose

    if search:
        conditions.append("filename ILIKE :search")
        params["search"] = f"%{search}%"

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    # LEFT JOIN so a document whose uploader was deleted (or that predates the
    # uploaded_by column) still lists, with a null email the client renders as unknown.
    document_where = " AND ".join(f"d.{c}" for c in conditions)
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
    await session.execute(
        text(f"UPDATE {_schema(tenant_id)}.documents SET status = 'deleted' WHERE id = :id"),
        {"id": doc_id},
    )
    await session.commit()

    return {"status": "deleted", "id": doc_id}
