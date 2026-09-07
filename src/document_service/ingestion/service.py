"""The one code path permitted to create a `documents` row.

It owns id generation, validation, checksum, duplicate identification, retention
resolution, the content-store write, the row write, and processing dispatch. It
references no HTTP type, constructs no storage client, and names no provider API — an
adapter translates its source into a `NormalizedDocument` and calls `ingest`.
"""

import logging
import uuid

from sqlalchemy import text

from src.document_service.content_store.contract import ContentStore
from src.document_service.content_store.instances import (
    get_durable_store,
    get_working_store,
)
from src.document_service.ingestion.contract import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
    ContentAcquisition,
    IngestionResult,
    NormalizedDocument,
)
from src.document_service.ingestion.dispatcher import (
    InProcessDispatcher,
    ProcessingDispatcher,
)
from src.document_service.ingestion.errors import (
    FileTooLarge,
    IncompatibleRetention,
    UnsupportedFileType,
)
from src.document_service.services.content_hash import compute_content_hash
from src.document_service.services.ocr_worker import get_extension, is_allowed_file
from src.shared.observability.domain_metrics import record_document_ingestion
from src.shared.integration_profile.store import load_profile
from src.shared.tenant_schema import schema_for_tenant

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def generate_document_id() -> str:
    return str(uuid.uuid4())


class DocumentIngestionService:
    def __init__(
        self,
        dispatcher: ProcessingDispatcher | None = None,
        durable_store: ContentStore | None = None,
        working_store: ContentStore | None = None,
        max_file_size: int = MAX_FILE_SIZE,
    ):
        self._dispatcher = dispatcher or InProcessDispatcher()
        self._durable_store = durable_store
        self._working_store = working_store
        self._max_file_size = max_file_size

    def _durable(self) -> ContentStore:
        return self._durable_store if self._durable_store is not None else get_durable_store()

    def _working(self) -> ContentStore:
        return self._working_store if self._working_store is not None else get_working_store()

    async def ingest(self, session, document: NormalizedDocument) -> IngestionResult:
        if not is_allowed_file(document.filename or ""):
            raise UnsupportedFileType(get_extension(document.filename or ""))

        data = document.content.read()
        if len(data) > self._max_file_size:
            raise FileTooLarge(len(data), self._max_file_size)

        # The tenant is the one the caller authenticated. A tenant identifier appearing
        # in the source's own metadata is data, not an assertion, and is never consulted.
        tenant_id = document.tenant_id
        schema = schema_for_tenant(tenant_id)

        # The checksum is over the bytes the platform actually read. A source-declared
        # version string is stored separately and is never used in its place.
        checksum = compute_content_hash(data)
        document_id = generate_document_id()

        duplicate_of = await self._find_duplicate(session, schema, tenant_id, checksum)

        retention_mode = await self._resolve_retention(session, document)

        store, storage_reference = self._write_content(
            retention_mode, tenant_id, document_id, data, document.filename
        )

        await self._insert_row(
            session,
            schema,
            document=document,
            document_id=document_id,
            checksum=checksum,
            file_size=len(data),
            storage_reference=storage_reference,
            retention_mode=retention_mode,
        )
        await session.commit()

        content_store_kind = getattr(store, "kind", None)
        # Which adapters served this ingestion. Three values, each from a declared set;
        # nothing the tenant configured reaches a label.
        record_document_ingestion(
            source_type=document.source.source_type,
            content_store_kind=content_store_kind,
            retention_mode=retention_mode,
        )
        logger.info(
            "document_ingested",
            extra={
                "source_type": document.source.source_type,
                "content_store_kind": content_store_kind,
                "retention_mode": retention_mode,
                # Shape, never content: a size and a boolean, no filename and no bytes.
                "file_size": len(data),
                "has_external_id": document.source.external_id is not None,
            },
        )

        self._dispatcher.dispatch(document_id, tenant_id)

        return IngestionResult(
            document_id=document_id,
            checksum=checksum,
            file_size=len(data),
            retention_mode=retention_mode,
            storage_reference=storage_reference,
            duplicate_of=duplicate_of,
            content_store_kind=content_store_kind,
        )

    # --- steps ------------------------------------------------------------------------

    async def _find_duplicate(self, session, schema, tenant_id, checksum) -> str | None:
        """Identify — never reject or merge — an earlier upload of byte-identical content.

        Scoped to this tenant's schema and tenant_id, so duplicates never cross tenants,
        and skipping soft-deleted rows the API would no longer serve. Ordered by
        created_at so three copies all point at the original, not at each other.
        """
        result = await session.execute(
            text(
                f"""
                SELECT id FROM {schema}.documents
                WHERE tenant_id = :tid AND checksum = :checksum AND status != 'deleted'
                ORDER BY created_at
                LIMIT 1
                """
            ),
            {"tid": tenant_id, "checksum": checksum},
        )
        row = result.fetchone()
        return row[0] if row else None

    async def _resolve_retention(self, session, document: NormalizedDocument) -> str:
        """Decide once, from the tenant's profile, and record the outcome.

        The one impossible combination is rejected here rather than discovered by a
        worker that finds neither a stored copy nor a source willing to be re-asked.
        """
        profile = await load_profile(session, document.tenant_id)
        retention_mode = profile.retention_mode

        if (
            retention_mode == RETENTION_SOURCE_ONLY
            and document.acquisition == ContentAcquisition.SINGLE_USE
        ):
            raise IncompatibleRetention(document.acquisition.value, retention_mode)

        return retention_mode

    def _write_content(
        self, retention_mode, tenant_id, document_id, data, filename
    ) -> tuple[ContentStore | None, str | None]:
        """The reference is the store's return value. Nothing predicts it.

        Note what is *not* consulted: the profile's `content_store_adapter`. Only the
        platform defaults are executable in this change, so ingestion uses them regardless
        of what a profile records. A recorded selection is a statement of intent, never a
        claim that the adapter exists.
        """
        if retention_mode == RETENTION_PLATFORM_BLOB:
            store = self._durable()
        elif retention_mode == RETENTION_EPHEMERAL:
            store = self._working()
        else:
            # `source_only`: no bytes reach any platform store, and the document carries
            # no reference. The originating adapter is re-asked at processing time.
            return None, None

        reference = store.put(tenant_id, document_id, data, filename=filename)
        return store, reference

    async def _insert_row(
        self,
        session,
        schema,
        *,
        document: NormalizedDocument,
        document_id,
        checksum,
        file_size,
        storage_reference,
        retention_mode,
    ) -> None:
        source = document.source
        await session.execute(
            text(
                f"""
                INSERT INTO {schema}.documents (
                    id, tenant_id, filename, content_type, file_size, checksum, status,
                    blob_path, purpose, uploaded_by,
                    origin, source_type, source_id, external_id, source_version,
                    source_created_at, source_modified_at, origin_metadata,
                    retention_mode, ingested_by_kind
                )
                VALUES (
                    :id, :tid, :filename, :content_type, :file_size, :checksum, 'pending',
                    :blob_path, :purpose, :uploaded_by,
                    :origin, :source_type, :source_id, :external_id, :source_version,
                    :source_created_at, :source_modified_at, CAST(:origin_metadata AS JSONB),
                    :retention_mode, :ingested_by_kind
                )
                """
            ),
            {
                "id": document_id,
                "tid": document.tenant_id,
                "filename": document.filename,
                "content_type": document.declared_media_type or "application/octet-stream",
                "file_size": file_size,
                "checksum": checksum,
                "blob_path": storage_reference,
                "purpose": document.purpose,
                "uploaded_by": document.actor.user_id,
                "origin": source.origin,
                "source_type": source.source_type,
                "source_id": source.source_id,
                "external_id": source.external_id,
                "source_version": source.source_version,
                # Never synthesised: a source that supplies no timestamp stores NULL.
                "source_created_at": source.source_created_at,
                "source_modified_at": source.source_modified_at,
                "origin_metadata": _as_json(source.metadata),
                "retention_mode": retention_mode,
                "ingested_by_kind": document.actor.kind.value,
            },
        )


def _as_json(metadata) -> str | None:
    if metadata is None:
        return None
    import json

    return json.dumps(dict(metadata))
