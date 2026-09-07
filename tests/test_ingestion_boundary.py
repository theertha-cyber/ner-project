"""Verification for the document-ingestion boundary — verification.md rows 1-20.

The scenarios that matter here are the ones an in-process shortcut would pass and a real
deployment would fail, so the ingestion operation is exercised directly, with no FastAPI
request anywhere in sight, alongside the HTTP route it now adapts.
"""

import ast
import inspect
import io
import os
import pathlib
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.api.v1 import documents as documents_route
from src.document_service.ingestion import (
    PLATFORM_UPLOAD_SOURCE_ID,
    SOURCE_TYPE_PLATFORM_UPLOAD,
    ActorKind,
    ContentAccess,
    ContentAcquisition,
    DocumentIngestionService,
    IncompatibleRetention,
    IngestingActor,
    NormalizedDocument,
    RecordingDispatcher,
    ReservedSourceId,
    SourceReference,
)
from src.document_service.ingestion.contract import assert_source_id_available
from src.document_service.ingestion.dispatcher import ProcessingDispatcher
from src.document_service.main import app
from src.document_service.services.content_hash import compute_content_hash
from src.shared.auth import create_access_token
from src.shared.config import settings
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
    RETENTION_SOURCE_ONLY,
)
from src.shared.integration_profile.store import PROFILE_TABLE

PDF_CONTENT = b"%PDF-1.4 ingestion boundary fixture " * 10
SRC_ROOT = pathlib.Path(__file__).resolve().parents[1] / "src"


# --- Fixtures --------------------------------------------------------------------------


class FakeStore:
    """A content store: three operations, real references, nothing else."""

    kind = "platform_minio"

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.puts: list[str] = []
        self.opens: list[str] = []
        self.deletes: list[str] = []

    def put(self, tenant_id, document_id, data, filename=None):
        reference = f"tenants/{tenant_id}/documents/{document_id}"
        self.objects[reference] = data
        self.puts.append(reference)
        return reference

    def open(self, reference):
        self.opens.append(reference)
        return self.objects.get(reference)

    def delete(self, reference):
        self.deletes.append(reference)
        self.objects.pop(reference, None)


DOCUMENTS_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.documents (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(255),
    file_size BIGINT,
    checksum VARCHAR(64),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    blob_path VARCHAR(500),
    purpose VARCHAR(20) NOT NULL DEFAULT 'query',
    uploaded_by VARCHAR,
    origin VARCHAR(32) NOT NULL DEFAULT 'push',
    source_type VARCHAR(64) NOT NULL DEFAULT 'platform_upload',
    source_id VARCHAR(128) NOT NULL DEFAULT 'platform-upload',
    external_id VARCHAR(512),
    source_version VARCHAR(256),
    source_created_at TIMESTAMPTZ,
    source_modified_at TIMESTAMPTZ,
    origin_metadata JSONB,
    retention_mode VARCHAR(32) NOT NULL DEFAULT 'platform_blob'
        CHECK (retention_mode IN ('platform_blob', 'ephemeral', 'source_only')),
    ingested_by_kind VARCHAR(32) NOT NULL DEFAULT 'human',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    span_index INTEGER,
    text TEXT,
    char_start INTEGER,
    char_end INTEGER,
    page_number INTEGER
);
CREATE TABLE IF NOT EXISTS {schema}.document_chunks (
    id VARCHAR PRIMARY KEY,
    document_id VARCHAR NOT NULL,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    embedding vector,
    page_number INTEGER,
    char_start INTEGER,
    char_end INTEGER,
    purpose VARCHAR(20)
);
"""

PROFILE_DDL = f"""
CREATE TABLE IF NOT EXISTS {PROFILE_TABLE} (
    tenant_id VARCHAR(64) PRIMARY KEY,
    source_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_upload',
    content_store_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_minio',
    relational_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_postgresql',
    index_adapter VARCHAR(64) NOT NULL DEFAULT 'platform_pgvector',
    retention_mode VARCHAR(32) NOT NULL DEFAULT 'platform_blob'
        CHECK (retention_mode IN ('platform_blob', 'ephemeral', 'source_only')),
    configuration JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    secret_references JSONB NOT NULL DEFAULT '{{}}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft','validated','active','paused','error','retired')),
    status_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@pytest.fixture
async def tenant():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    async with engine.connect() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS public.tenants ("
                "id VARCHAR PRIMARY KEY, name VARCHAR(255) NOT NULL, "
                "slug VARCHAR(63) NOT NULL UNIQUE, status VARCHAR(20) DEFAULT 'active', "
                "created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())"
            )
        )
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS public.tenant_users ("
                "id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, "
                "email VARCHAR(255) NOT NULL, password_hash VARCHAR(255) DEFAULT '', "
                "role VARCHAR(32) NOT NULL DEFAULT 'business_user', "
                "status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMPTZ DEFAULT NOW())"
            )
        )
        for statement in PROFILE_DDL.strip().split(";\n"):
            if statement.strip():
                await conn.execute(text(statement))
        for statement in DOCUMENTS_DDL.format(schema=schema).strip().split(";\n"):
            if statement.strip():
                await conn.execute(text(statement))
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s) "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid, "n": f"Boundary {tid[:8]}", "s": f"boundary-{tid[:8]}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_users (id, tenant_id, email, role) "
                "VALUES ('test-user', :tid, 'uploader@example.com', 'business_user') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"tid": tid},
        )

    yield {"tenant_id": tid, "schema": schema}

    async with engine.connect() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(
            text(f"DELETE FROM {PROFILE_TABLE} WHERE tenant_id = :id"), {"id": tid}
        )
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    await engine.dispose()


@pytest.fixture
async def session_factory():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def set_retention(session_factory, tenant_id, mode):
    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {PROFILE_TABLE} (tenant_id, retention_mode, status) "
                f"VALUES (:tid, :mode, 'active') "
                f"ON CONFLICT (tenant_id) DO UPDATE SET retention_mode = :mode"
            ),
            {"tid": tenant_id, "mode": mode},
        )
        await session.commit()


def normalized(tenant_id, **overrides):
    kwargs = dict(
        tenant_id=tenant_id,
        filename="report.pdf",
        content=ContentAccess.from_bytes(PDF_CONTENT),
        purpose="query",
        actor=IngestingActor(kind=ActorKind.HUMAN, user_id="test-user"),
        source=SourceReference(
            source_type=SOURCE_TYPE_PLATFORM_UPLOAD,
            source_id=PLATFORM_UPLOAD_SOURCE_ID,
        ),
        acquisition=ContentAcquisition.SINGLE_USE,
        declared_media_type="application/pdf",
    )
    kwargs.update(overrides)
    return NormalizedDocument(**kwargs)


async def read_document(session_factory, schema, document_id):
    async with session_factory() as session:
        result = await session.execute(
            text(f"SELECT * FROM {schema}.documents WHERE id = :id"), {"id": document_id}
        )
        return result.fetchone()


def auth_header(tenant_id, role="business_user"):
    token = create_access_token(tenant_id=tenant_id, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


# --- Row 1: the row is created by the ingestion operation, not the route ---------------


@pytest.mark.asyncio
async def test_row_1_upload_creates_the_row_through_the_ingestion_operation(
    tenant, session_factory, client
):
    store = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=store
    )
    with patch.object(documents_route, "ingestion_service", service):
        response = await client.post(
            "/api/v1/documents",
            files={"file": ("report.pdf", io.BytesIO(PDF_CONTENT), "application/pdf")},
            headers=auth_header(tenant["tenant_id"]),
        )

    assert response.status_code == 201, response.text
    body = response.json()
    # The pre-change body fields, unchanged.
    assert set(body) == {
        "id", "filename", "content_type", "status", "file_size", "checksum", "duplicate_of"
    }
    assert body["status"] == "pending"
    assert body["file_size"] == len(PDF_CONTENT)

    # The write is the ingestion operation's: the store it was constructed with holds the
    # bytes, and the row it created is the one the response names.
    assert store.puts, "the ingestion operation's store was not used"
    row = await read_document(session_factory, tenant["schema"], body["id"])
    assert row is not None


# --- Row 2: exactly one writer of the documents table ----------------------------------


def _documents_insert_sites() -> list[str]:
    """Every INSERT targeting a `documents` relation in application source."""
    sites = []
    for path in SRC_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8", errors="ignore")
        lowered = source.lower()
        index = 0
        while True:
            index = lowered.find("insert into", index)
            if index == -1:
                break
            fragment = lowered[index : index + 200]
            # `.documents (` or `documents (` — not document_chunks, not document_entities.
            if "documents" in fragment.split("(")[0].split("values")[0]:
                target = fragment.split("insert into", 1)[1].strip().split()[0]
                if target.endswith("documents") or target.endswith(".documents"):
                    sites.append(str(path.relative_to(SRC_ROOT)))
            index += len("insert into")
    return sorted(set(sites))


# `gateway/seed.py` is a demo fixture generator, in the same category as tests and
# migrations: it constructs a database state directly — backdated `created_at` values and
# the `002`-shape columns — rather than ingesting a document. It has no bytes to store and
# nothing to dispatch. Named explicitly rather than pattern-excluded, so a genuinely new
# writer still fails this row.
FIXTURE_GENERATORS = {os.path.join("gateway", "seed.py")}


def test_row_2_only_the_ingestion_operation_inserts_documents():
    sites = [s for s in _documents_insert_sites() if s not in FIXTURE_GENERATORS]
    assert sites == [os.path.join("document_service", "ingestion", "service.py")], sites


# --- Row 3: callable with no HTTP context ----------------------------------------------


@pytest.mark.asyncio
async def test_row_3_ingestion_is_callable_without_an_http_request(
    tenant, session_factory
):
    dispatcher = RecordingDispatcher()
    service = DocumentIngestionService(dispatcher=dispatcher, durable_store=FakeStore())

    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert result.document_id
    assert dispatcher.dispatches == [(result.document_id, tenant["tenant_id"])]
    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row is not None


def test_row_3_the_ingestion_module_names_no_http_or_storage_type():
    import src.document_service.ingestion.service as service_module

    source = inspect.getsource(service_module)
    for forbidden in ("fastapi", "UploadFile", "HTTPException", "boto3", "MinioStorageClient", "Request"):
        assert forbidden not in source, f"ingestion operation references {forbidden}"


# --- Row 4: purpose is carried on the contract -----------------------------------------


@pytest.mark.asyncio
async def test_row_4_purpose_is_carried_and_stored(tenant, session_factory):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], purpose="training")
        )

    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row.purpose == "training"

    # A training document is never chunked or embedded.
    async with session_factory() as session:
        chunks = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {tenant['schema']}.document_chunks "
                    f"WHERE document_id = :id"
                ),
                {"id": result.document_id},
            )
        ).scalar()
    assert chunks == 0


# --- Rows 5 and 6: optional source metadata is absent, and never synthesised -----------


@pytest.mark.asyncio
async def test_row_5_absent_optional_source_metadata_is_stored_null(
    tenant, session_factory
):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row.external_id is None
    assert row.source_version is None
    assert row.source_created_at is None
    assert row.source_modified_at is None


@pytest.mark.asyncio
async def test_row_6_source_timestamps_are_never_synthesised(tenant, session_factory):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    source = SourceReference(
        source_type="keka",
        source_id="keka-prod",
        source_created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        # No modified timestamp: the source did not supply one.
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], source=source)
        )

    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row.source_created_at is not None
    assert row.source_modified_at is None, "an absent timestamp was backfilled"


# --- Row 7: an adapter cannot assert a tenant identity ---------------------------------


@pytest.mark.asyncio
async def test_row_7_source_metadata_cannot_redirect_the_tenant(tenant, session_factory):
    other_tenant = uuid.uuid4().hex
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    source = SourceReference(
        source_type=SOURCE_TYPE_PLATFORM_UPLOAD,
        source_id=PLATFORM_UPLOAD_SOURCE_ID,
        metadata={"tenant_id": other_tenant, "tenant": other_tenant},
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], source=source)
        )

    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row is not None, "the document did not land in the authenticated tenant"
    assert row.tenant_id == tenant["tenant_id"]


# --- Row 8: platform upload declares single_use ----------------------------------------


def test_row_8_the_upload_route_declares_single_use_content():
    source = inspect.getsource(documents_route.upload_document)
    assert "ContentAcquisition.SINGLE_USE" in source
    assert "REOPENABLE" not in source


# --- Row 9: single_use with source_only is rejected ------------------------------------


@pytest.mark.asyncio
async def test_row_9_single_use_content_is_never_given_source_only_retention(
    tenant, session_factory
):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_SOURCE_ONLY)
    store = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=store, working_store=store
    )

    async with session_factory() as session:
        with pytest.raises(IncompatibleRetention) as excinfo:
            await service.ingest(session, normalized(tenant["tenant_id"]))

    assert "single_use" in str(excinfo.value)
    assert RETENTION_SOURCE_ONLY in str(excinfo.value)
    assert store.puts == [], "bytes were written for a rejected ingestion"

    async with session_factory() as session:
        count = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.documents")
            )
        ).scalar()
    assert count == 0


# --- Row 10: resolution decided once and recorded --------------------------------------


@pytest.mark.asyncio
async def test_row_10_resolution_is_decided_once_and_recorded(tenant, session_factory):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )

    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert result.retention_mode == RETENTION_EPHEMERAL
    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row.retention_mode == RETENTION_EPHEMERAL
    assert working.puts and not durable.puts

    # Processing reads the recorded value; it does not re-derive it from the profile.
    from src.document_service.services import ocr_worker

    with patch.object(ocr_worker, "_store_for", lambda mode: working) as _:
        resolved = ocr_worker.resolve_content(row)
    assert resolved == PDF_CONTENT


# --- Row 11: the platform computes the checksum ----------------------------------------


@pytest.mark.asyncio
async def test_row_11_checksum_is_the_platform_hash_not_the_source_version(
    tenant, session_factory
):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    source = SourceReference(
        source_type="keka",
        source_id="keka-prod",
        source_version="rev-42-not-a-digest",
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], source=source)
        )

    row = await read_document(session_factory, tenant["schema"], result.document_id)
    assert row.checksum == compute_content_hash(PDF_CONTENT)
    assert row.source_version == "rev-42-not-a-digest"
    assert row.checksum != row.source_version


# --- Rows 13 and 14: the reserved platform source --------------------------------------


@pytest.mark.asyncio
async def test_row_13_and_14_uploads_record_the_stable_reserved_source(
    tenant, session_factory, client
):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    ids = []
    with patch.object(documents_route, "ingestion_service", service):
        for name in ("first.pdf", "second.pdf"):
            response = await client.post(
                "/api/v1/documents",
                files={"file": (name, io.BytesIO(PDF_CONTENT + name.encode()), "application/pdf")},
                headers=auth_header(tenant["tenant_id"]),
            )
            assert response.status_code == 201, response.text
            ids.append(response.json()["id"])

    rows = [await read_document(session_factory, tenant["schema"], i) for i in ids]
    assert [r.source_type for r in rows] == [SOURCE_TYPE_PLATFORM_UPLOAD] * 2
    assert [r.source_id for r in rows] == [PLATFORM_UPLOAD_SOURCE_ID] * 2
    # Stable, and not a generated identifier.
    assert rows[0].source_id == rows[1].source_id == "platform-upload"
    for row in rows:
        with pytest.raises(ValueError):
            uuid.UUID(row.source_id)


# --- Row 15: the reserved identifier cannot be claimed ---------------------------------


def test_row_15_a_configured_source_cannot_claim_the_reserved_identifier():
    with pytest.raises(ReservedSourceId):
        assert_source_id_available(PLATFORM_UPLOAD_SOURCE_ID)
    # A real source identifier is unaffected.
    assert_source_id_available("keka-prod")


# --- Row 16: the role-to-purpose policy stays at the HTTP boundary ---------------------


@pytest.mark.asyncio
async def test_row_16_role_to_purpose_policy_is_enforced_at_the_route(
    tenant, session_factory, client
):
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore()
    )
    with patch.object(documents_route, "ingestion_service", service):
        response = await client.post(
            "/api/v1/documents",
            files={"file": ("report.pdf", io.BytesIO(PDF_CONTENT), "application/pdf")},
            data={"purpose": "training"},
            headers=auth_header(tenant["tenant_id"], role="business_user"),
        )

    assert response.status_code == 403, response.text
    async with session_factory() as session:
        count = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {tenant['schema']}.documents")
            )
        ).scalar()
    assert count == 0

    # The policy lives in the route module, not in the ingestion operation.
    assert "ROLE_ALLOWED_PURPOSES" in inspect.getsource(documents_route)
    import src.document_service.ingestion.service as service_module

    assert "ROLE_ALLOWED_PURPOSES" not in inspect.getsource(service_module)


# --- Row 17: the route references no content store -------------------------------------


def test_row_17_the_route_references_no_storage_client_and_builds_no_key():
    module_path = SRC_ROOT / "document_service" / "api" / "v1" / "documents.py"
    source = module_path.read_text(encoding="utf-8")

    for forbidden in ("MinioStorageClient", "boto3", "get_durable_store", "get_working_store"):
        assert forbidden not in source, f"the route references {forbidden}"

    # No storage key is constructed anywhere in the module.
    assert "tenants/" not in source

    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any("storage" in m for m in imported), imported


# --- Rows 18-20: dispatch ---------------------------------------------------------------


def test_row_18_the_default_dispatcher_is_the_in_process_one():
    from src.document_service.ingestion.dispatcher import InProcessDispatcher

    service = DocumentIngestionService()
    assert isinstance(service._dispatcher, InProcessDispatcher)
    # In-process means an asyncio task, exactly as before this change.
    assert "asyncio.create_task" in inspect.getsource(InProcessDispatcher.dispatch)


def test_row_19_dispatch_carries_only_identity():
    parameters = list(inspect.signature(ProcessingDispatcher.dispatch).parameters)
    assert parameters == ["self", "document_id", "tenant_id"]

    from src.document_service.ingestion.dispatcher import InProcessDispatcher

    assert list(inspect.signature(InProcessDispatcher.dispatch).parameters) == [
        "self",
        "document_id",
        "tenant_id",
    ]
    # And nothing content-shaped reaches the worker call it makes.
    body = inspect.getsource(InProcessDispatcher.dispatch)
    for forbidden in ("blob_path", "content_type", "media_type", "data", "bytes"):
        assert forbidden not in body, f"dispatch carries {forbidden}"


@pytest.mark.asyncio
async def test_row_20_a_recording_dispatcher_observes_without_executing(
    tenant, session_factory
):
    dispatcher = RecordingDispatcher()
    store = FakeStore()
    service = DocumentIngestionService(dispatcher=dispatcher, durable_store=store)

    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert dispatcher.dispatches == [(result.document_id, tenant["tenant_id"])]
    # No OCR ran: nothing opened the stored object and no spans exist.
    assert store.opens == []
    async with session_factory() as session:
        spans = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {tenant['schema']}.document_text_spans "
                    f"WHERE document_id = :id"
                ),
                {"id": result.document_id},
            )
        ).scalar()
    assert spans == 0
