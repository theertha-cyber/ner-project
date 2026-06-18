import uuid
from fastapi import APIRouter, Depends, Query, Request, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from src.shared.database import get_engine
from src.shared.exceptions import NotFoundError
from src.document_service.services.ocr_worker import is_allowed_file, get_extension, trigger_ocr
from src.document_service.services.storage import MinioStorageClient

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


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
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
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
    doc_id = generate_uuid()
    ext = get_extension(file.filename or "").lstrip(".")
    blob_path = f"tenants/{tenant_id}/documents/{doc_id}.{ext}"

    storage = MinioStorageClient()
    storage.upload_file(tenant_id, doc_id, ext, file_data)

    await session.execute(
        text(f"""
            INSERT INTO {_schema(tenant_id)}.documents (id, tenant_id, filename, content_type, file_size, status, blob_path)
            VALUES (:id, :tid, :filename, :content_type, :file_size, 'pending', :blob_path)
        """),
        {
            "id": doc_id,
            "tid": tenant_id,
            "filename": file.filename,
            "content_type": file.content_type or "application/octet-stream",
            "file_size": len(file_data),
            "blob_path": blob_path,
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
    }


@router.get("")
async def list_documents(
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    tenant_id = get_tenant_id(request)
    conditions = ["tenant_id = :tid"]
    params = {"tid": tenant_id}

    if status_filter:
        conditions.append("status = :status")
        params["status"] = status_filter

    where = " AND ".join(conditions)
    offset = (page - 1) * per_page

    result = await session.execute(
        text(f"SELECT id, filename, content_type, file_size, status, error_message, created_at, updated_at FROM {_schema(tenant_id)}.documents WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :offset"),
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
        text(f"SELECT id, filename, content_type, file_size, status, error_message, blob_path, created_at, updated_at FROM {_schema(tenant_id)}.documents WHERE id = :id AND tenant_id = :tid"),
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
        text(f"UPDATE {_schema(tenant_id)}.documents SET status = 'deleted' WHERE id = :id"),
        {"id": doc_id},
    )
    await session.commit()

    return {"status": "deleted", "id": doc_id}
