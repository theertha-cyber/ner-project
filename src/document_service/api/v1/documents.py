import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from src.shared.data_plane import DataPlaneUnavailable
from src.shared.data_plane_gate import require_data_plane_ready
from src.shared.database import get_engine, get_resolver
from src.shared.document_visibility import RequestingUser, visibility_predicate
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)
from src.document_service.content_resolution import (
    has_source_reopener,
    reopen_source_content,
    resolve_content,
)
from src.document_service.media_types import render_mode, servable_media_type
from src.shared.observability.domain_metrics import (
    content_class,
    record_document_content_request,
)
from src.shared.tenant_context import classify_driver_error, record_health_best_effort
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

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
    dependencies=[Depends(require_data_plane_ready)],
)

VALID_PURPOSES = {"query", "training", "qa_pair"}

# Upload purpose is a role capability, not an uploader choice: tenant admins upload
# documents for annotation (and optional Q&A-pair guidance for schema proposal), business
# users upload documents for querying. Roles absent from this map (system_admin, annotator)
# keep every purpose.
ROLE_ALLOWED_PURPOSES = {
    "tenant_admin": {"training", "qa_pair"},
    "business_user": {"query"},
}


async def has_column(session: AsyncSession, schema: str, table_name: str, column_name: str) -> bool:
    column_check = await session.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table_name
              AND column_name = :column_name
            LIMIT 1
        """),
        {"schema": schema, "table_name": table_name, "column_name": column_name},
    )
    return bool(column_check.fetchone())


async def has_table(session: AsyncSession, schema: str, table_name: str) -> bool:
    table_check = await session.execute(
        text("""
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = :schema
              AND table_name = :table_name
            LIMIT 1
        """),
        {"schema": schema, "table_name": table_name},
    )
    return bool(table_check.fetchone())


def get_tenant_id(request: Request) -> str:
    tid = getattr(request.state, "tenant_id", None)
    if tid is None:
        raise HTTPException(status_code=403, detail="Tenant context not available")
    return tid


async def get_session(request: Request) -> AsyncSession:
    """Routed through EngineResolver (ADR-017): a `tenant_owned` tenant's documents
    live wherever its data plane resolves, never the platform database.

    Unlike `tenant_context.tenant_session`, this never narrows `search_path` — every
    query on this session names its schema explicitly (tenant-schema tables via
    `_schema`, control-plane tables via `public.`), and routes in this module rely
    on being able to do both on one session.

    A body-carrying request pre-probes with `SELECT 1`, because proving the store
    reachable *before* bytes are accepted is the point (tenant-data-plane-failure-
    isolation spec's "Uploads are rejected before bytes are accepted when the store
    is unavailable" — this dependency resolves, and so runs, before the route body
    ever reads upload bytes off the wire). A read has no bytes to refuse and its own
    first query proves the same thing one round trip later, so it skips the probe;
    against a remote store that round trip is a third of the request. Either way a
    driver failure classifies into `DataPlaneUnavailable` the same way
    `tenant_session` does, without adopting its search_path narrowing."""
    tenant_id = getattr(request.state, "tenant_id", None)
    engine = await get_resolver().resolve(tenant_id)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        try:
            if request.method in ("POST", "PUT", "PATCH"):
                await session.execute(text("SELECT 1"))
            yield session
        except (DBAPIError, OperationalError, OSError) as exc:
            reason = classify_driver_error(exc)
            await record_health_best_effort(tenant_id, reason)
            raise DataPlaneUnavailable(reason) from exc
        finally:
            await session.close()


async def _platform_session() -> AsyncSession:
    """A session on the platform database, for control-plane reads that must never run
    on a tenant session (Design D10) — e.g. resolving an uploader's email from
    `public.tenant_users`, which does not exist in a `tenant_owned` store."""
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
            detail={"code": "VALIDATION_ERROR", "message": "purpose must be 'query', 'training', or 'qa_pair'"},
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
        allowed_msg = (
            ".pdf, .txt, .docx" if purpose == "qa_pair"
            # `.csv` is in the general allow-list (CAP-4 / ADR-012); the message has to
            # name it or the rejection tells the user the wrong thing.
            else ".pdf, .jpg, .jpeg, .png, .tif, .tiff, .doc, .docx, .csv"
        )
        raise HTTPException(
            status_code=422,
            detail={
                "code": "VALIDATION_ERROR",
                "message": f"File type '{exc.extension}' is not supported. Allowed: {allowed_msg}",
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
    # Ceiling is high because the annotation console's batch and schema-proposal document
    # pickers pull the whole processed set in one page rather than paginating a checkbox list.
    per_page: int = Query(20, ge=1, le=1000),
    request: Request = None,
    session: AsyncSession = Depends(get_session),
    platform_session: AsyncSession = Depends(_platform_session),
):
    tenant_id = get_tenant_id(request)
    role = getattr(request.state, "role", None)
    user_id = getattr(request.state, "user_id", None)
    # Each condition is a template over the table alias, because the count query names
    # the table bare and the listing query aliases it `d`. Prefixing a rendered string
    # cannot express a condition over two columns.
    conditions = ["{p}tenant_id = :tid"]
    params = {"tid": tenant_id}

    column_check = await session.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'documents'
              AND column_name = 'conversation_id'
            LIMIT 1
        """),
        {"schema": _schema(tenant_id)},
    )
    if column_check.fetchone():
        conditions.append("{p}conversation_id IS NULL")

    if role != "tenant_admin":
        if await has_column(session, _schema(tenant_id), "documents", "uploaded_by") and await has_column(session, _schema(tenant_id), "documents", "ingested_by_kind"):
            # Ownership scoping applies only to documents a *person* ingested. A
            # system-ingested document is visible tenant-wide.
            #
            # The predicate comes from `src/shared/document_visibility.py` rather than
            # being written here, because every chat answer channel now applies the same
            # rule and this listing is where it originally lived. Two copies of it is
            # exactly the defect the uploader-scoping change existed to remove: listing
            # enforced the rule, retrieval did not, and an answer could cite a document
            # this listing denied existed.
            predicate, visibility_params = visibility_predicate(
                RequestingUser(user_id=user_id, role=role), prefix="{p}"
            )
            if predicate is not None:
                conditions.append(predicate)
                params.update(visibility_params)

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

    # No cross-schema join to `public.tenant_users` (Design D10): that table does not
    # exist in a `tenant_owned` store. The tenant session reads documents alone; the
    # uploader email is a second, control-plane lookup on the platform session.
    document_where = " AND ".join(c.format(p="d.") for c in conditions)
    # `COUNT(*) OVER ()` carries the unpaginated total on each row, so the listing and
    # its total are one round trip rather than two — the difference is a whole query's
    # latency when the store is remote.
    result = await session.execute(
        text(f"""
            SELECT d.id, d.filename, d.content_type, d.file_size, d.status, d.error_message,
                   d.purpose, d.uploaded_by, d.created_at, d.updated_at,
                   COUNT(*) OVER () AS total
            FROM {_schema(tenant_id)}.documents d
            WHERE {document_where}
            ORDER BY d.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": per_page, "offset": offset},
    )
    rows = result.fetchall()

    if rows:
        total = rows[0].total
    elif page > 1:
        # A page past the end returns no rows, so the windowed count has nothing to
        # report — the standalone count still has to answer how many there really are.
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM {_schema(tenant_id)}.documents WHERE {where}"),
            params,
        )
        total = count_result.scalar()
    else:
        total = 0

    uploader_ids = {r.uploaded_by for r in rows if r.uploaded_by}
    uploader_emails: dict[str, str] = {}
    if uploader_ids:
        uploader_rows = await platform_session.execute(
            text("SELECT id, email FROM public.tenant_users WHERE id = ANY(:ids)"),
            {"ids": list(uploader_ids)},
        )
        uploader_emails = {u.id: u.email for u in uploader_rows.fetchall()}

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
            "uploaded_by_email": uploader_emails.get(r.uploaded_by),
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
    schema = _schema(tenant_id)
    
    use_content_type = await has_column(session, schema, "documents", "content_type")
    use_file_size = await has_column(session, schema, "documents", "file_size")
    use_blob_path = await has_column(session, schema, "documents", "blob_path")
    
    use_updated_at = await has_column(session, schema, "documents", "updated_at")
    
    content_type_col = "content_type" if use_content_type else "mime_type AS content_type"
    file_size_col = "file_size" if use_file_size else "file_size_bytes AS file_size"
    blob_path_col = "blob_path" if use_blob_path else "storage_uri AS blob_path"
    updated_at_col = "updated_at" if use_updated_at else "created_at AS updated_at"
    
    query = f"SELECT id, filename, {content_type_col}, {file_size_col}, checksum, status, error_message, {blob_path_col}, created_at, {updated_at_col} FROM {schema}.documents WHERE id = :id AND tenant_id = :tid"
    if await has_column(session, schema, "documents", "conversation_id"):
        query += " AND conversation_id IS NULL"
    result = await session.execute(
        text(query),
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

    query = f"SELECT id FROM {schema}.documents WHERE id = :id AND tenant_id = :tid"
    if await has_column(session, schema, "documents", "conversation_id"):
        query += " AND conversation_id IS NULL"
    doc_result = await session.execute(
        text(query),
        {"id": doc_id, "tid": tenant_id},
    )
    doc_row = doc_result.fetchone()
    if not doc_row:
        raise NotFoundError("Document", doc_id)

    spans_query = f"SELECT text FROM {schema}.document_text_spans WHERE document_id = :doc_id"
    span_index_check = await session.execute(
        text("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = 'document_text_spans'
              AND column_name = 'span_index'
            LIMIT 1
        """),
        {"schema": schema},
    )
    if span_index_check.fetchone():
        spans_query += " ORDER BY span_index"

    result = await session.execute(
        text(spans_query),
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
    schema = _schema(tenant_id)
    query = f"SELECT id, status FROM {schema}.documents WHERE id = :id AND tenant_id = :tid"
    if await has_column(session, schema, "documents", "conversation_id"):
        query += " AND conversation_id IS NULL"
    result = await session.execute(
        text(query),
        {"id": doc_id, "tid": tenant_id},
    )
    row = result.fetchone()
    if not row:
        raise NotFoundError("Document", doc_id)

    for table in ["document_chunks", "document_text_spans", "extracted_entities", "document_entities"]:
        if await has_table(session, schema, table):
            await session.execute(
                text(f"DELETE FROM {schema}.{table} WHERE document_id = :id"),
                {"id": doc_id},
            )
    # The generated relational tables declare no foreign key to `documents`, so this
    # propagation is what maintains referential integrity — without it a deleted document
    # would keep answering generated SQL queries. The statements come from the same pure
    # builder the extraction worker uses, so the sync and async callers cannot diverge into a
    # half-deleted document. Inactive definitions are covered too: their tables are retained,
    # so their rows would otherwise survive.
    #
    # `entity_definitions` is a control-plane table (Design D10) — read on a fresh
    # *platform* session, never `session` (which for a `tenant_owned` tenant is
    # resolved to their own store, where `public.entity_definitions` does not exist).
    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as platform_session:
        specs = await load_definition_specs(platform_session, tenant_id)
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

    from src.shared import tenant_document_registry as registry

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as platform_session:
        await registry.update_status(
            platform_session, tenant_id=tenant_id, document_id=doc_id, status="deleted"
        )

    return {"status": "deleted", "id": doc_id}


# --- Original document content (cited-document-viewer) ----------------------------------
#
# Two routes: a probe that says whether the original can be produced and how to render
# it, and the bytes themselves. The probe exists so the portal does not download up to
# 50MB to discover the original was released or the format needs converting.
#
# Both reach conversation-owned rows, unlike every other route in this module. That is
# deliberate: a chat attachment is exactly the kind of document a reader wants to open
# from the thread, and the blanket `conversation_id IS NULL` clause elsewhere is what
# keeps attachments out of the tenant-wide *library*, not out of their own conversation.

# Machine-readable outcomes. The viewer renders each differently, so they must not be
# collapsed: a released original is permanent and a consequence of the tenant's own
# retention policy, while an unreachable source is worth retrying.
CONTENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
CONTENT_NOT_PERMITTED = "DOCUMENT_NOT_PERMITTED"
CONTENT_ORIGINAL_RELEASED = "ORIGINAL_RELEASED"
CONTENT_ORIGINAL_MISSING = "ORIGINAL_MISSING"
CONTENT_SOURCE_NOT_REOPENABLE = "SOURCE_NOT_REOPENABLE"
CONTENT_SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
CONTENT_CONVERSION_FAILED = "CONVERSION_FAILED"
CONTENT_TOO_LARGE = "ORIGINAL_TOO_LARGE"

# Outcome -> (HTTP status, metric outcome). 410 for a released original because it is
# gone and will not come back; 503 for an unreachable source because it may.
_CONTENT_STATUS = {
    CONTENT_NOT_FOUND: (404, "not_found"),
    CONTENT_NOT_PERMITTED: (403, "not_permitted"),
    CONTENT_ORIGINAL_RELEASED: (410, "original_released"),
    CONTENT_ORIGINAL_MISSING: (410, "original_missing"),
    CONTENT_SOURCE_NOT_REOPENABLE: (409, "source_not_reopenable"),
    CONTENT_SOURCE_UNAVAILABLE: (503, "source_unavailable"),
    CONTENT_CONVERSION_FAILED: (422, "conversion_failed"),
    CONTENT_TOO_LARGE: (413, "too_large"),
}

_CONTENT_MESSAGES = {
    CONTENT_NOT_FOUND: "This document no longer exists.",
    CONTENT_NOT_PERMITTED: "You do not have access to this document.",
    CONTENT_ORIGINAL_RELEASED: (
        "The original was not retained after processing, under this tenant's retention "
        "policy."
    ),
    CONTENT_ORIGINAL_MISSING: "The stored original could not be found.",
    CONTENT_SOURCE_NOT_REOPENABLE: "This document's source cannot be re-read.",
    CONTENT_SOURCE_UNAVAILABLE: "The source system could not be reached.",
    CONTENT_CONVERSION_FAILED: "This document could not be prepared for display.",
    CONTENT_TOO_LARGE: "This document is too large to preview.",
}


class _ContentUnavailable(Exception):
    """A document whose bytes cannot be produced, carrying which of the enumerated
    reasons applies."""

    def __init__(self, code: str, retention_mode: str | None = None):
        super().__init__(code)
        self.code = code
        self.retention_mode = retention_mode


def _content_error(exc: "_ContentUnavailable") -> HTTPException:
    status, outcome = _CONTENT_STATUS[exc.code]
    record_document_content_request(exc.retention_mode, outcome)
    logger.info(
        "document_content_unavailable",
        extra={"retention_mode": exc.retention_mode, "reason": outcome},
    )
    return HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": _CONTENT_MESSAGES[exc.code]},
    )


_CONTENT_COLUMNS = (
    "id, filename, content_type, file_size, status, retention_mode, "
    "blob_path, source_type, source_id, external_id, uploaded_by, ingested_by_kind, "
    "conversation_id"
)


async def _load_document_for_content(session, request, doc_id: str):
    """The document row, if this caller may see its content.

    Three checks, all expressible inside the tenant's own schema:

    - the tenant predicate every route in this module applies;
    - the uploader-visibility rule, imported from `src.shared.document_visibility` rather
      than restated, so the content boundary cannot drift from the listing and the chat
      answer channels that apply the same rule;
    - for a conversation-owned row, that this caller is the one who attached it.

    The attachment check reads `uploaded_by` on the document row rather than joining
    `conversations`. ADR-017 allows `documents` to resolve to a tenant-owned database
    where that table is not present, and ingestion writes the uploader and the
    conversation in the same insert, so the row already knows. It is also stricter than a
    conversation-ownership check, since a conversation has exactly one owner.
    """
    tenant_id = get_tenant_id(request)
    schema = _schema(tenant_id)
    role = getattr(request.state, "role", None)
    user_id = getattr(request.state, "user_id", None)
    user = RequestingUser(user_id=user_id, role=role)

    has_conversation = await has_column(session, schema, "documents", "conversation_id")
    has_actor = await has_column(session, schema, "documents", "ingested_by_kind")

    columns = _CONTENT_COLUMNS
    if not has_conversation:
        columns = columns.replace(", conversation_id", ", NULL AS conversation_id")
    if not has_actor:
        columns = columns.replace(", ingested_by_kind", ", NULL AS ingested_by_kind")

    result = await session.execute(
        text(f"SELECT {columns} FROM {schema}.documents WHERE id = :id AND tid_match"
             .replace("tid_match", "tenant_id = :tid")),
        {"id": doc_id, "tid": tenant_id},
    )
    row = result.fetchone()
    if row is None:
        # Not found and forbidden are different outcomes, but a document belonging to
        # another tenant is genuinely not found from inside this one.
        raise _ContentUnavailable(CONTENT_NOT_FOUND)

    if has_actor:
        predicate, params = visibility_predicate(user)
        if predicate is not None:
            visible = await session.execute(
                text(
                    f"SELECT 1 FROM {schema}.documents "
                    f"WHERE id = :id AND tenant_id = :tid AND {predicate}"
                ),
                {"id": doc_id, "tid": tenant_id, **params},
            )
            if visible.fetchone() is None:
                raise _ContentUnavailable(CONTENT_NOT_PERMITTED, row.retention_mode)

    conversation_id = getattr(row, "conversation_id", None)
    if conversation_id is not None:
        # A conversation-owned attachment belongs to whoever attached it, and this check
        # is deliberately *not* relaxed for a tenant admin: an admin sees the tenant's
        # library, but a colleague's private chat attachment is not library content.
        # (The uploader predicate above does exempt admins, which is why this has to be
        # its own check rather than a stricter version of that one.)
        if row.uploaded_by is None or row.uploaded_by != user_id:
            raise _ContentUnavailable(CONTENT_NOT_PERMITTED, row.retention_mode)

    return row


async def _resolve_original(row, tenant_id: str) -> bytes:
    """The document's bytes, or the enumerated reason they cannot be produced."""
    retention_mode = row.retention_mode or RETENTION_PLATFORM_BLOB

    if retention_mode == RETENTION_SOURCE_ONLY:
        if not has_source_reopener(row.source_type):
            raise _ContentUnavailable(CONTENT_SOURCE_NOT_REOPENABLE, retention_mode)
        data = await reopen_source_content(row, tenant_id)
        if data is None:
            # The adapter exists and did not answer. Transient, and distinct from having
            # no adapter at all.
            raise _ContentUnavailable(CONTENT_SOURCE_UNAVAILABLE, retention_mode)
        return data

    if not row.blob_path:
        # An ephemeral document past its terminal state: its working copy was released
        # and the reference nulled. Permanent, and a consequence of the tenant's own
        # retention policy rather than a fault.
        raise _ContentUnavailable(
            CONTENT_ORIGINAL_RELEASED
            if retention_mode == RETENTION_EPHEMERAL
            else CONTENT_ORIGINAL_MISSING,
            retention_mode,
        )

    data = resolve_content(row)
    if data is None:
        # A reference exists but the store no longer holds the object. An operational
        # fault, not a retention outcome.
        raise _ContentUnavailable(CONTENT_ORIGINAL_MISSING, retention_mode)
    return data


@router.get("/{doc_id}/content/status")
async def get_document_content_status(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """Whether this document's original can be produced, and how to render it.

    Answers from the document row alone — the content store is never opened — so a
    client can decide before committing to a transfer. Authorization is enforced here as
    well as on the bytes route; the probe is not a way to learn a document exists.
    """
    tenant_id = get_tenant_id(request)
    try:
        row = await _load_document_for_content(session, request, doc_id)
    except _ContentUnavailable as exc:
        raise _content_error(exc) from None

    retention_mode = row.retention_mode or RETENTION_PLATFORM_BLOB
    media_type = servable_media_type(row.filename, row.content_type)

    reason = None
    if retention_mode == RETENTION_SOURCE_ONLY:
        if not has_source_reopener(row.source_type):
            reason = CONTENT_SOURCE_NOT_REOPENABLE
    elif not row.blob_path:
        reason = (
            CONTENT_ORIGINAL_RELEASED
            if retention_mode == RETENTION_EPHEMERAL
            else CONTENT_ORIGINAL_MISSING
        )

    return {
        "document_id": row.id,
        "filename": row.filename,
        "media_type": media_type,
        "render_mode": render_mode(media_type),
        "file_size": row.file_size,
        "retention_mode": retention_mode,
        "available": reason is None,
        "reason": reason,
        "message": _CONTENT_MESSAGES[reason] if reason else None,
    }


@router.get("/{doc_id}/content")
async def get_document_content(
    doc_id: str,
    request: Request = None,
    session: AsyncSession = Depends(get_session),
):
    """The document's original bytes, for display.

    The bytes pass through this application; no storage URL, bucket, endpoint or
    credential reaches the client, and the response is never a redirect. That is not a
    stylistic choice — the content-store boundary permits exactly three operations, and a
    pre-authorized URL is unimplementable for a document whose bytes live in no platform
    store at all.
    """
    tenant_id = get_tenant_id(request)
    try:
        row = await _load_document_for_content(session, request, doc_id)
        data = await _resolve_original(row, tenant_id)
    except _ContentUnavailable as exc:
        raise _content_error(exc) from None

    retention_mode = row.retention_mode or RETENTION_PLATFORM_BLOB

    # The served type is decided here, from the extension ingestion validated -- never
    # echoed from `documents.content_type`, which is whatever the uploading client
    # declared. A blob URL inherits the portal's origin, where the access token lives, so
    # serving a stored `text/html` would run script beside it.
    media_type = servable_media_type(row.filename, row.content_type)

    record_document_content_request(
        retention_mode, "served", media_type=media_type, byte_count=len(data)
    )
    logger.info(
        "document_content_served",
        extra={
            "retention_mode": retention_mode,
            "media_class": content_class(media_type),
            "byte_count": len(data),
        },
    )

    return Response(
        content=data,
        media_type=media_type,
        headers={
            # Inline: the point is to display it, not to download it.
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(row.filename or 'document')}",
            # The browser must not second-guess the type just decided above.
            "X-Content-Type-Options": "nosniff",
            # Neuters script in anything that reaches a renderer despite the allow-list.
            "Content-Security-Policy": "sandbox; default-src 'none'; img-src 'self' data:; object-src 'none'",
            "Cache-Control": "private, no-store",
        },
    )
