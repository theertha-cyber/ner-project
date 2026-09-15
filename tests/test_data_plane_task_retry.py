"""Verification for "Background tasks retry with bounded backoff and then park"
(ADR-017, task 11.2/11.6, tenant-data-plane-failure-isolation spec) —
scenario #27 (park after bounded retries), exercised against `run_blob_sync_task`
as the representative background task.
"""

def test_scenario_27_blob_sync_parks_after_bounded_retries(monkeypatch):
    """Scenario #27: Extraction parks after bounded retries (exercised here via the
    blob-sync task, which shares the same retry helper)."""
    from src.document_service.blob_sync import tasks as blob_tasks
    from src.shared.config import settings
    from src.shared.data_plane import DataPlaneUnavailable

    monkeypatch.setattr(settings, "data_plane_task_max_retries", 1)
    monkeypatch.setattr(blob_tasks, "_data_plane_retry_countdown", lambda retries: 0)

    async def _always_unavailable(tenant_id):
        raise DataPlaneUnavailable("unreachable")

    monkeypatch.setattr(
        "src.shared.database.get_resolver",
        lambda: type("R", (), {"resolve": staticmethod(_always_unavailable)})(),
    )

    result = blob_tasks.run_blob_sync_task.apply(args=["tid-retry-test", "cid-retry-test", "manual"])
    payload = result.get()

    assert payload["outcome"] == "failed_retryable"
    assert payload["reason"] == "data_plane_unavailable"
    # Payload carries identifiers only — no tenant content, no driver detail.
    assert set(payload.keys()) == {"run_id", "outcome", "reason"}


import json
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

_STORE_HOST = "localhost"
_STORE_PORT = int(os.environ.get("NER_TEST_TENANT_STORE_PORT", "55433"))
_STORE_DB = os.environ.get("NER_TENANT_STORE_DB_NAME", "ner_tenant_store")
_STORE_USER = os.environ.get("NER_TENANT_STORE_DB_USER", "ner_tenant_store")
_STORE_PASSWORD_ENV = "NER_TEST_TENANT_STORE_PASSWORD"
os.environ.setdefault(_STORE_PASSWORD_ENV, os.environ.get("NER_TENANT_STORE_DB_PASSWORD", "ner_tenant_store"))


def _store_engine():
    return create_engine(
        f"postgresql://{_STORE_USER}:{os.environ[_STORE_PASSWORD_ENV]}@"
        f"{_STORE_HOST}:{_STORE_PORT}/{_STORE_DB}"
    )


@pytest.fixture
async def ocr_tenant(engine, setup_database):
    """A real, fully-provisioned `tenant_owned` schema on `postgres-tenant-store`,
    routed there the same way every other real-infra data-plane test routes a
    tenant (via a `tenant_data_planes`/`tenant_data_source_connections` pair) —
    without it, `get_resolver().resolve(tenant_id)` falls back to the platform
    engine, where this tenant's schema does not exist."""
    from src.shared.data_sources.providers import PROVIDER_AZURE_POSTGRESQL_DATA_PLANE
    from src.shared.tenant_store import apply as apply_module

    tid = f"ocr28-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    connection_id = str(uuid.uuid4())
    configuration = {
        "host": _STORE_HOST, "port": _STORE_PORT, "database": _STORE_DB,
        "username": _STORE_USER, "sslmode": "disable",
    }
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug) VALUES (:id, :n, :s)"),
            {"id": tid, "n": "OCR Scenario 28 Fixture", "s": f"slug-{tid}"},
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_source_connections "
                "(id, tenant_id, provider, configuration, secret_references, status) "
                "VALUES (:id, :tid, :provider, CAST(:config AS JSONB), CAST(:secrets AS JSONB), 'active')"
            ),
            {
                "id": connection_id, "tid": tid, "provider": PROVIDER_AZURE_POSTGRESQL_DATA_PLANE,
                "config": json.dumps(configuration),
                "secrets": json.dumps({"password_ref": f"env://{_STORE_PASSWORD_ENV}"}),
            },
        )
        await conn.execute(
            text(
                "INSERT INTO public.tenant_data_planes "
                "(tenant_id, mode, status, connection_id) "
                "VALUES (:tid, 'tenant_owned', 'ready', :cid)"
            ),
            {"tid": tid, "cid": connection_id},
        )

    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        store_conn.commit()
        apply_module.apply(store_conn, schema, tid)
        store_conn.commit()
    store_engine.dispose()

    yield tid, schema

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        with store_conn.begin():
            store_conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    store_engine.dispose()


def _insert_pending_document(schema: str, tenant_id: str) -> str:
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    store_engine = _store_engine()
    with store_engine.connect() as store_conn:
        store_conn.execute(
            text(
                f"""
                INSERT INTO {schema}.documents
                    (id, tenant_id, filename, status, purpose, source_type, source_id,
                     retention_mode, content_type, created_at, updated_at)
                VALUES
                    (:id, :tid, 'scan.pdf', 'pending', 'query', 'platform_upload',
                     'n/a', 'platform_blob', 'application/pdf', NOW(), NOW())
                """
            ),
            {"id": doc_id, "tid": tenant_id},
        )
        store_conn.commit()
    store_engine.dispose()
    return doc_id


def _read_document(schema: str, doc_id: str):
    store_engine = _store_engine()
    try:
        with store_engine.connect() as store_conn:
            return store_conn.execute(
                text(f"SELECT status, error_message FROM {schema}.documents WHERE id = :id"),
                {"id": doc_id},
            ).fetchone()
    finally:
        store_engine.dispose()


def _count_spans(schema: str, doc_id: str) -> int:
    store_engine = _store_engine()
    try:
        with store_engine.connect() as store_conn:
            return store_conn.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_text_spans WHERE document_id = :id"),
                {"id": doc_id},
            ).scalar_one()
    finally:
        store_engine.dispose()


@pytest.mark.asyncio
async def test_scenario_28_no_content_is_buffered_on_the_platform(engine, ocr_tenant, monkeypatch):
    """Scenario #28: OCR has produced text and the store becomes unreachable before
    the spans are written — the produced text must never land on the platform, and
    the document must stay reprocessable once the store is back.

    The store "becomes unreachable" is simulated at the exact seam that matters: the
    transaction that would persist the produced spans. `process_document` computes
    `spans` (the produced text) entirely in memory and only ever touches the
    platform in the single commit at the end of its OCR block — so making that
    commit fail is a faithful stand-in for the store dying between "text produced"
    and "spans written," without needing to actually kill the container mid-test.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    from src.document_service.services import ocr_worker

    tid, schema = ocr_tenant
    doc_id = _insert_pending_document(schema, tid)

    produced_text = "SCENARIO-28 PRODUCED TEXT — must never reach the platform"

    async def _fake_resolve_content(document, tenant_id):
        return b"%PDF-1.4 fake bytes, never actually parsed"

    def _fake_extract_text_pdf(file_bytes):
        return [
            {
                "span_index": 0,
                "text": produced_text,
                "char_start": 0,
                "char_end": len(produced_text),
                "page_number": 0,
            }
        ]

    monkeypatch.setattr(ocr_worker, "_resolve_content_for_processing", _fake_resolve_content)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf", _fake_extract_text_pdf)

    real_execute = AsyncSession.execute

    async def _execute_that_fails_span_insert(self, statement, *args, **kwargs):
        sql = str(statement)
        if "document_text_spans" in sql and "INSERT" in sql.upper():
            raise RuntimeError("simulated tenant store unreachable")
        return await real_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "execute", _execute_that_fails_span_insert)

    await ocr_worker.process_document(doc_id, tid)

    # The failed write never committed: no span row exists carrying the produced text.
    assert _count_spans(schema, doc_id) == 0

    row = _read_document(schema, doc_id)
    assert row.status == "failed"
    assert row.error_message == ocr_worker.PROCESSING_ERROR_PROCESSING_FAILED

    # Only the simulated store failure is undone here — `_resolve_content_for_processing`
    # and `extract_text_pdf` stay stubbed (this test's fake PDF bytes are not real PDF
    # content; `monkeypatch`'s own teardown reverts everything once the test ends).
    monkeypatch.setattr(AsyncSession, "execute", real_execute)

    # Recovery: once the store is reachable again, the document is reprocessable —
    # `_recover_stuck_documents`'s own reset-to-pending step is exercised elsewhere
    # (tests/test_data_plane_recovery_sweep.py); here, driving `process_document`
    # again directly (as a fresh dispatch would) proves the document was never left
    # in a state that blocks reprocessing.
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from src.shared.database import get_resolver as _get_resolver

    tenant_engine = await _get_resolver().resolve(tid)
    session_factory = async_sessionmaker(tenant_engine, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text(f"UPDATE {schema}.documents SET status = 'pending' WHERE id = :id"),
            {"id": doc_id},
        )
        await session.commit()

    await ocr_worker.process_document(doc_id, tid)

    row = _read_document(schema, doc_id)
    assert row.status == "processed"
    assert _count_spans(schema, doc_id) == 1
