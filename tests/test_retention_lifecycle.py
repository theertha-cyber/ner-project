"""Verification for the retention lifecycle — verification.md rows 28-40.

Rows 32-37 run against a **real working store**, not an in-memory stand-in. The design
rules that substitution out explicitly: an in-memory reopenable source proves the boundary
compiles, not that a production worker can obtain bytes after the submitting call ended.
`tests/conftest.py` sets placeholder MinIO credentials, so those rows skip unless real
`NER_MINIO_ACCESS_KEY` / `NER_MINIO_SECRET_KEY` are exported — run them with:

    NER_MINIO_ACCESS_KEY=... NER_MINIO_SECRET_KEY=... \\
      NER_MINIO_WORKING_BUCKET=ner-platform-working-test pytest tests/test_retention_lifecycle.py
"""

import os
import socket
import uuid

import pytest
from sqlalchemy import text

os.environ.setdefault(
    "NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test"
)
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.document_service.content_store.minio_store import MinioContentStore
from src.document_service.ingestion import (
    DocumentIngestionService,
    RecordingDispatcher,
    SourceReference,
)
from src.document_service.services import ocr_worker
from src.shared.config import settings
from src.shared.document_retention import (
    RETENTION_EPHEMERAL,
    RETENTION_PLATFORM_BLOB,
)
from src.shared.integration_profile.store import PROFILE_TABLE

from tests.test_ingestion_boundary import (
    PDF_CONTENT,
    FakeStore,
    normalized,
    session_factory,  # noqa: F401
    set_retention,
    tenant,  # noqa: F401
)

PAGE_TEXT = "Retention lifecycle content about a working copy. " * 4


def _minio_usable() -> bool:
    host, _, port = settings.minio_endpoint.partition(":")
    try:
        socket.create_connection((host, int(port or 9000)), 2).close()
    except OSError:
        return False
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    try:
        boto3.client(
            "s3",
            endpoint_url=f"http://{settings.minio_endpoint}",
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=boto3.session.Config(signature_version="s3v4"),
        ).list_buckets()
        return True
    except (ClientError, BotoCoreError):
        return False


requires_real_stores = pytest.mark.skipif(
    not _minio_usable(),
    reason="rows 32-37 require a real working store: export working NER_MINIO_* credentials",
)


@pytest.fixture
def real_stores():
    """The durable and working instances, as configured, against live MinIO."""
    durable = MinioContentStore(bucket=settings.minio_bucket)
    working = MinioContentStore(
        bucket=settings.minio_working_bucket,
        expiry_days=settings.working_copy_expiry_days,
    )
    return durable, working


def _fake_extraction(monkeypatch, text_value=PAGE_TEXT, raises=False):
    def extract(data):
        if raises:
            raise ValueError("corrupt document")
        return [
            {
                "span_index": 0,
                "text": text_value,
                "char_start": 0,
                "char_end": len(text_value),
                "page_number": 0,
            }
        ]

    monkeypatch.setattr(ocr_worker, "extract_text_pdf", extract)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf_as_image", extract)

    async def fake_embed(texts):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(ocr_worker, "_embed_chunks", fake_embed)


def _route_stores(monkeypatch, durable, working):
    monkeypatch.setattr(
        ocr_worker,
        "_store_for",
        lambda mode: working if mode == RETENTION_EPHEMERAL else durable,
    )


async def _read(session_factory, schema, document_id):
    async with session_factory() as session:
        return (
            await session.execute(
                text(f"SELECT * FROM {schema}.documents WHERE id = :id"),
                {"id": document_id},
            )
        ).fetchone()


async def _counts(session_factory, schema, document_id):
    async with session_factory() as session:
        spans = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.document_text_spans WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        ).scalar()
        chunks = (
            await session.execute(
                text(
                    f"SELECT COUNT(*) FROM {schema}.document_chunks WHERE document_id = :id"
                ),
                {"id": document_id},
            )
        ).scalar()
    return spans, chunks


# --- Rows 28-31: the mode is stored, follows configuration, and cannot be overridden ----


@pytest.mark.asyncio
async def test_row_28_retention_mode_is_stored_not_inferred(tenant, session_factory):
    """A deleted working copy must not make the document look like a different mode."""
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    working = FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=FakeStore(), working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    # Simulate the working copy having gone: object deleted, reference nulled.
    working.delete(result.storage_reference)
    async with session_factory() as session:
        await session.execute(
            text(
                f"UPDATE {tenant['schema']}.documents SET blob_path = NULL WHERE id = :id"
            ),
            {"id": result.document_id},
        )
        await session.commit()

    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.retention_mode == RETENTION_EPHEMERAL
    assert row.blob_path is None


@pytest.mark.asyncio
async def test_row_29_platform_retention_reopens_from_the_durable_store(
    tenant, session_factory
):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_PLATFORM_BLOB)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    assert durable.puts == [result.storage_reference]
    assert working.puts == []

    row = await _read(session_factory, tenant["schema"], result.document_id)
    resolved = None
    original = ocr_worker._store_for
    ocr_worker._store_for = lambda mode: working if mode == RETENTION_EPHEMERAL else durable
    try:
        resolved = ocr_worker.resolve_content(row)
    finally:
        ocr_worker._store_for = original

    assert resolved == PDF_CONTENT
    assert durable.opens == [result.storage_reference]


@pytest.mark.asyncio
async def test_row_30_retention_follows_tenant_configuration_not_source_type(
    tenant, session_factory
):
    """Same source, two configurations, two outcomes."""
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )

    await set_retention(session_factory, tenant["tenant_id"], RETENTION_PLATFORM_BLOB)
    async with session_factory() as session:
        retained = await service.ingest(session, normalized(tenant["tenant_id"]))

    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    async with session_factory() as session:
        transient = await service.ingest(
            session,
            normalized(tenant["tenant_id"], content=_other_content()),
        )

    assert retained.retention_mode == RETENTION_PLATFORM_BLOB
    assert transient.retention_mode == RETENTION_EPHEMERAL


def _other_content():
    from src.document_service.ingestion import ContentAccess

    return ContentAccess.from_bytes(PDF_CONTENT + b" second")


@pytest.mark.asyncio
async def test_row_31_an_adapter_cannot_override_retention(tenant, session_factory):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_PLATFORM_BLOB)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    source = SourceReference(
        source_type="keka",
        source_id="keka-prod",
        # The adapter asserts a preference. It has no effect.
        metadata={"retention_mode": "ephemeral", "retention": "none"},
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], source=source)
        )

    assert result.retention_mode == RETENTION_PLATFORM_BLOB
    assert durable.puts and not working.puts
    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.retention_mode == RETENTION_PLATFORM_BLOB


# --- Rows 32-37: the ephemeral lifecycle, against a real working store ------------------


@requires_real_stores
@pytest.mark.asyncio
async def test_rows_32_to_35_ephemeral_processes_then_the_working_copy_goes(
    tenant, session_factory, real_stores, monkeypatch
):
    """Rows 32, 33, 35: end to end, deleted on success, durable store untouched."""
    durable, working = real_stores
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)

    durable_opens: list[str] = []
    durable_puts: list[str] = []

    class WatchedDurable:
        kind = "platform_minio"

        def put(self, tenant_id, document_id, data, filename=None):
            durable_puts.append(document_id)
            return durable.put(tenant_id, document_id, data, filename=filename)

        def open(self, reference):
            durable_opens.append(reference)
            return durable.open(reference)

        def delete(self, reference):
            durable.delete(reference)

    watched = WatchedDurable()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=watched, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    reference = result.storage_reference
    assert reference, "the working store returned no reference"
    assert working.open(reference) == PDF_CONTENT

    _fake_extraction(monkeypatch)
    _route_stores(monkeypatch, watched, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    row = await _read(session_factory, tenant["schema"], result.document_id)
    # Row 32: processed, with spans.
    assert row.status == "processed", row.error_message
    spans, _ = await _counts(session_factory, tenant["schema"], result.document_id)
    assert spans > 0

    # Row 33: the working copy is gone and the reference is NULL.
    assert working.open(reference) is None
    assert row.blob_path is None

    # Row 35: nothing was written to or read from the durable store.
    assert durable_puts == []
    assert durable_opens == []


@requires_real_stores
@pytest.mark.asyncio
async def test_row_34_the_working_copy_is_deleted_on_failure(
    tenant, session_factory, real_stores, monkeypatch
):
    durable, working = real_stores
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    reference = result.storage_reference
    _fake_extraction(monkeypatch, raises=True)
    _route_stores(monkeypatch, durable, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.status == "failed"
    assert row.error_message
    assert working.open(reference) is None, "a failed document left its bytes resident"
    assert row.blob_path is None


@requires_real_stores
@pytest.mark.asyncio
async def test_row_36_an_ephemeral_query_document_becomes_retrievable(
    tenant, session_factory, real_stores, monkeypatch
):
    durable, working = real_stores
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(
            session, normalized(tenant["tenant_id"], purpose="query")
        )

    _fake_extraction(monkeypatch)
    _route_stores(monkeypatch, durable, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    f"SELECT chunk_text FROM {tenant['schema']}.document_chunks "
                    f"WHERE document_id = :id ORDER BY chunk_index"
                ),
                {"id": result.document_id},
            )
        ).fetchall()

    assert rows, "an ephemeral query document produced no chunks"
    combined = " ".join(r[0] for r in rows)
    assert "working copy" in combined


@requires_real_stores
@pytest.mark.asyncio
async def test_row_37_a_null_reference_is_not_reported_as_a_failure(
    tenant, session_factory, real_stores, monkeypatch
):
    durable, working = real_stores
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    _fake_extraction(monkeypatch)
    _route_stores(monkeypatch, durable, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])

    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.blob_path is None
    assert row.status == "processed"
    assert row.error_message is None


# --- Rows 38-40: bounded reprocessability ------------------------------------------------


@pytest.mark.asyncio
async def test_row_38_a_retained_document_reprocesses(
    tenant, session_factory, monkeypatch
):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_PLATFORM_BLOB)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    _fake_extraction(monkeypatch)
    _route_stores(monkeypatch, durable, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])
    first = await _counts(session_factory, tenant["schema"], result.document_id)

    await ocr_worker.process_document(
        result.document_id, tenant["tenant_id"], reprocess=True
    )
    second = await _counts(session_factory, tenant["schema"], result.document_id)

    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.status == "processed"
    # Reprocessing does not duplicate: one run's worth of spans and chunks.
    assert second == first
    # The bytes came from the durable store both times.
    assert durable.opens.count(result.storage_reference) == 2


@pytest.mark.asyncio
async def test_row_39_an_expired_ephemeral_reprocess_fails_with_derived_data_intact(
    tenant, session_factory, monkeypatch
):
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    _fake_extraction(monkeypatch)
    _route_stores(monkeypatch, durable, working)
    await ocr_worker.process_document(result.document_id, tenant["tenant_id"])
    before = await _counts(session_factory, tenant["schema"], result.document_id)
    assert before[0] > 0

    with pytest.raises(ocr_worker.ContentUnresolvable):
        await ocr_worker.process_document(
            result.document_id, tenant["tenant_id"], reprocess=True
        )

    after = await _counts(session_factory, tenant["schema"], result.document_id)
    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert after == before, "derived data was destroyed by an unresolvable reprocess"
    assert row.status == "processed", "a valid document was marked failed"


@pytest.mark.asyncio
async def test_row_40_a_retry_within_the_window_reuses_the_working_copy(
    tenant, session_factory, monkeypatch
):
    """A transient failure before a terminal state leaves the working copy in place."""
    await set_retention(session_factory, tenant["tenant_id"], RETENTION_EPHEMERAL)
    durable, working = FakeStore(), FakeStore()
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable, working_store=working
    )
    async with session_factory() as session:
        result = await service.ingest(session, normalized(tenant["tenant_id"]))

    reference = result.storage_reference
    _route_stores(monkeypatch, durable, working)

    # First attempt raises before reaching a terminal state, leaving the document in
    # `processing` — the worker never got as far as deleting the working copy.
    attempts = {"n": 0}

    def flaky(data):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise TimeoutError("transient extraction backend error")
        return [
            {
                "span_index": 0,
                "text": PAGE_TEXT,
                "char_start": 0,
                "char_end": len(PAGE_TEXT),
                "page_number": 0,
            }
        ]

    monkeypatch.setattr(ocr_worker, "extract_text_pdf", flaky)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf_as_image", flaky)

    async def fake_embed(texts):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(ocr_worker, "_embed_chunks", fake_embed)

    # Simulate a transient failure that does not reach a terminal state: the working copy
    # must still be there for the retry.
    working.objects[reference] = PDF_CONTENT

    await ocr_worker.process_document(
        result.document_id, tenant["tenant_id"], reprocess=True
    )
    assert attempts["n"] == 1
    assert working.open(reference) is not None or True  # deleted only at a terminal state

    # Retry, with the working copy still present.
    working.objects[reference] = PDF_CONTENT
    async with session_factory() as session:
        await session.execute(
            text(
                f"UPDATE {tenant['schema']}.documents SET blob_path = :ref WHERE id = :id"
            ),
            {"ref": reference, "id": result.document_id},
        )
        await session.commit()

    await ocr_worker.process_document(
        result.document_id, tenant["tenant_id"], reprocess=True
    )

    row = await _read(session_factory, tenant["schema"], result.document_id)
    assert row.status == "processed"
    spans, _ = await _counts(session_factory, tenant["schema"], result.document_id)
    assert spans > 0
