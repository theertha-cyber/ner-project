"""Verification for durable Azure Blob synchronization (CAP-3).

Maps to `openspec/changes/cap-3-durable-azure-blob-synchronization-and-source-reconciliation/verification.md`
Section 1 rows 1-17.

Live Azure verification is deferred per run provisioning (no approved test
storage account), so the provider seam runs `FixtureBlobProvider` instances --
exactly the seam production uses for the SDK-backed runtime. Every other layer
(ledger, ingestion, retrieval, telemetry) runs against the real test database.

Teardown removes exactly what each test created: connection rows, profile rows
(via the shared fixture), tenant schemas, and provider registrations. Nothing
leaks into the shared dataset.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from src.document_service.blob_sync import ledger
from src.document_service.blob_sync import scheduler as sched
from src.document_service.blob_sync import sync as blob_sync
from src.document_service.blob_sync.provider import (
    BlobObject,
    FixtureBlobProvider,
    get_provider,
    register_provider,
    reset_providers,
)
from src.document_service.blob_sync.scheduler import evaluate_connection
from src.document_service.ingestion import (
    DocumentIngestionService,
    RecordingDispatcher,
)
from src.document_service.services import ocr_worker
from src.shared import observability as _obs  # noqa: F401
from src.shared.data_sources import lifecycle as lc
from src.shared.data_sources.store import CONNECTIONS_TABLE
from src.shared.integration_profile.store import PROFILE_TABLE
from src.shared.observability import domain_metrics as dm
from src.shared.retrieval.retriever import DenseRetriever

import src.document_service.blob_sync.reopen as _reopen  # noqa: F401

from tests.test_ingestion_boundary import (  # noqa: F401
    PDF_CONTENT,
    FakeStore,
    session_factory,
    set_retention,
    tenant,
)

pytestmark = [pytest.mark.verification]

CONNECTION_ID = str(uuid.uuid4())


@pytest.fixture(autouse=True)
def _clean_providers():
    reset_providers()
    yield
    reset_providers()


@pytest.fixture
async def connections(session_factory):
    """Connection rows this test creates, removed afterwards."""
    created = []

    async def _make(tenant_id, status=lc.STATUS_ACTIVE, provider="azure_blob",
                    configuration=None):
        cid = str(uuid.uuid4())
        async with session_factory() as session:
            await session.execute(
                text(
                    f"INSERT INTO {CONNECTIONS_TABLE} "
                    "(id, tenant_id, provider, configuration, secret_references, status) "
                    "VALUES (CAST(:id AS UUID), :tid, :prov, "
                    "CAST(:cfg AS JSONB), CAST(:sec AS JSONB), :status)"
                ),
                {
                    "id": cid,
                    "tid": tenant_id,
                    "prov": provider,
                    "cfg": json.dumps(configuration or {"account": "a", "container": "c"}),
                    "sec": json.dumps({"connection_string_ref": "env://CAP3_TEST_CONN_STR"}),
                    "status": status,
                },
            )
            await session.commit()
        created.append(cid)
        return cid

    yield _make

    async with session_factory() as session:
        for cid in created:
            await session.execute(
                text(f"DELETE FROM {CONNECTIONS_TABLE} WHERE id = CAST(:id AS UUID)"),
                {"id": cid},
            )
        await session.commit()


def _blob(filename="report.pdf", identity=None, version="etag-1", size=None,
           metadata=None):
    data = PDF_CONTENT + (identity or filename).encode()
    return (
        BlobObject(
            identity=identity or f"docs/{filename}",
            version=version,
            filename=filename,
            size=size if size is not None else len(data),
            metadata=metadata,
        ),
        data,
    )


def _provider(*items):
    objects = [o for o, _ in items]
    blobs = {o.identity: d for o, d in items}
    return FixtureBlobProvider(objects=objects, blobs=blobs)


def _services():
    durable = FakeStore()
    working = FakeStore()
    temp = FakeStore()
    factory = lambda: DocumentIngestionService(  # noqa: E731
        dispatcher=RecordingDispatcher(),
        durable_store=durable,
        working_store=working,
    )
    return factory, durable, working, temp


async def _run(session_factory, schema, tenant_id, connection_id, trigger,
               provider, factory, temp):
    async with session_factory() as session:
        await ledger.ensure_sync_tables(session, schema)
        await session.commit()
    return await blob_sync.run_sync(
        session_factory, tenant_id, connection_id, trigger,
        provider=provider, make_ingestion_service=factory, temp_store=temp,
    )


async def _documents(session_factory, schema, connection_id=None):
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(f"SELECT * FROM {schema}.documents"),
            )
        ).fetchall()
        return rows


async def _counts(session_factory, schema, document_id):
    async with session_factory() as session:
        spans = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_text_spans "
                     "WHERE document_id = :id"),
                {"id": document_id},
            )
        ).scalar()
        chunks = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_chunks "
                     "WHERE document_id = :id"),
                {"id": document_id},
            )
        ).scalar()
    return spans, chunks


# --- Rows 1-2: new objects synchronize through the common pipeline ---------------------


async def test_new_object_synchronizes_through_common_ingestion(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)

    assert result.outcome == "succeeded"
    assert result.ingested == 1 and result.seen == 1
    rows = await _documents(session_factory, schema)
    assert len(rows) == 1
    row = rows[0]._mapping
    assert row["source_type"] == "azure_blob"
    assert row["source_id"] == cid
    assert row["external_id"] == obj.identity
    assert row["source_version"] == "etag-1"
    assert row["origin"] == "pull"
    assert row["retention_mode"] == "source_only"
    assert row["blob_path"] is None
    # No durable original anywhere: the durable store never saw the bytes.
    assert durable.puts == []


async def test_manual_trigger_enqueues_the_same_durable_job(
    tenant, session_factory, connections
):
    tid = tenant["tenant_id"]
    cid = await connections(tid)
    descriptor = blob_sync.trigger_manual_sync(tid, cid)
    assert descriptor["task"] == "blob_sync_run"
    assert descriptor["args"] == [tid, cid, blob_sync.TRIGGER_MANUAL]
    # Identity-only: no bytes, references, or versions travel in the payload.
    assert all(isinstance(a, str) for a in descriptor["args"])


# --- Row 3: scheduled cadence and one missed-schedule catch-up -------------------------


def test_scheduler_cadence_and_catchup_decisions():
    now = datetime.now(timezone.utc)
    assert evaluate_connection(active=False, last_success_at=None).decision == "inactive"
    assert evaluate_connection(
        active=True, last_success_at=None
    ).decision == "due"
    assert evaluate_connection(
        active=True, last_success_at=now - timedelta(minutes=20)
    ).decision == "due"
    catchup = evaluate_connection(
        active=True, last_success_at=now - timedelta(minutes=45)
    )
    assert catchup.decision == "catchup" and catchup.trigger == "catchup"
    assert evaluate_connection(
        active=True, last_success_at=now - timedelta(minutes=5)
    ).decision == "not_due"
    stale_new = evaluate_connection(
        active=True, last_success_at=None,
        connected_at=now - timedelta(hours=2), now=now,
    )
    assert stale_new.decision == "catchup"


async def test_stale_connection_gets_one_catchup_run(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    async with session_factory() as session:
        await ledger.ensure_sync_tables(session, schema)
        await session.execute(
            text(
                f"INSERT INTO {schema}.azure_blob_sync_runs "
                "(id, tenant_id, connection_id, trigger, outcome, reason, "
                "started_at, completed_at) "
                "VALUES ('old', :tid, :cid, 'scheduled', 'succeeded', 'none', "
                "NOW() - INTERVAL '2 hours', NOW() - INTERVAL '2 hours')"
            ),
            {"tid": tid, "cid": cid},
        )
        await session.commit()
        last = await ledger.last_successful_run_at(session, schema, cid)
    decision = evaluate_connection(active=True, last_success_at=last)
    assert decision.decision == "catchup"

    result = await blob_sync.run_sync(
        session_factory, tid, cid, decision.trigger,
        provider=get_provider(cid), make_ingestion_service=factory,
        temp_store=temp,
    )
    assert result.outcome == "succeeded" and result.ingested == 1


# --- Row 4: inactive connections and retention preconditions never sync ----------------


async def test_inactive_connection_never_syncs(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid, status=lc.STATUS_DRAFT)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, provider, factory, temp)

    assert result.outcome == "blocked"
    assert result.reason == "inactive_connection"
    assert provider.acquisitions == []
    assert (await _documents(session_factory, schema)) == []


async def test_platform_blob_profile_blocks_the_run(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "platform_blob")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)

    # platform_blob would durably persist the original through common
    # ingestion, so the run is blocked rather than half-compliant.
    assert result.outcome == "blocked"
    assert result.reason == "prerequisite_missing"
    assert (await _documents(session_factory, schema)) == []
    assert durable.puts == []


# --- Row 5: the durable lease prevents overlapping work --------------------------------


@pytest.mark.parametrize(
    "trigger", [blob_sync.TRIGGER_SCHEDULED, blob_sync.TRIGGER_MANUAL]
)
async def test_overlapping_run_records_lease_held_without_ingesting(
    tenant, session_factory, connections, trigger
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    async with session_factory() as session:
        await ledger.ensure_sync_tables(session, schema)
        assert await ledger.acquire_lease(session, schema, cid, "other-run")
        await session.commit()

    result = await blob_sync.run_sync(
        session_factory, tid, cid, trigger,
        provider=provider, make_ingestion_service=factory, temp_store=temp,
    )

    assert result.outcome == "lease_held"
    assert result.reason == "lease_held"
    assert provider.enumerations == 0
    assert (await _documents(session_factory, schema)) == []


async def test_lease_is_released_after_success(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)
    assert result.outcome == "succeeded"
    async with session_factory() as session:
        remaining = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.azure_blob_sync_leases "
                     "WHERE connection_id = :cid"),
                {"cid": cid},
            )
        ).scalar()
    assert remaining == 0


# --- Row 6: retries and unchanged versions create nothing duplicate --------------------


async def test_retry_or_unchanged_version_creates_no_duplicates(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    first = await _run(session_factory, schema, tid, cid,
                       blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)
    assert first.ingested == 1
    doc_id = (await _documents(session_factory, schema))[0]._mapping["id"]
    # Simulate derived outputs the common pipeline produced for that document.
    async with session_factory() as session:
        await session.execute(
            text(f"INSERT INTO {schema}.document_chunks "
                 "(id, document_id, chunk_index, chunk_text, purpose) "
                 "VALUES ('c1', :doc, 0, 'derived', 'query')"),
            {"doc": doc_id},
        )
        await session.commit()

    retry = await _run(session_factory, schema, tid, cid,
                       blob_sync.TRIGGER_RETRY, get_provider(cid), factory, temp)

    assert retry.outcome == "succeeded"
    assert retry.ingested == 0 and retry.skipped == 1
    assert len(await _documents(session_factory, schema)) == 1
    assert await _counts(session_factory, schema, doc_id) == (0, 1)


# --- Row 7: changed versions are atomically replaced -----------------------------------


async def test_changed_version_replaces_prior_derived_outputs(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj_v1, data_v1 = _blob(version="etag-1")
    provider = _provider((obj_v1, data_v1))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    old_id = (await _documents(session_factory, schema))[0]._mapping["id"]
    async with session_factory() as session:
        await session.execute(
            text(f"INSERT INTO {schema}.document_text_spans "
                 "(id, document_id, span_index, text) "
                 "VALUES ('s1', :doc, 0, 'old text')"),
            {"doc": old_id},
        )
        await session.execute(
            text(f"INSERT INTO {schema}.document_chunks "
                 "(id, document_id, chunk_index, chunk_text, purpose) "
                 "VALUES ('c1', :doc, 0, 'old chunk', 'query')"),
            {"doc": old_id},
        )
        await session.commit()

    obj_v2, data_v2 = _blob(version="etag-2")
    provider.put(obj_v2, data_v2 + b" revised")
    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)

    assert result.outcome == "succeeded" and result.ingested == 1
    rows = await _documents(session_factory, schema)
    assert len(rows) == 2
    new_id = [r._mapping["id"] for r in rows if r._mapping["id"] != old_id][0]
    # Prior derived outputs are gone in the same step that relinked the ledger.
    assert await _counts(session_factory, schema, old_id) == (0, 0)
    async with session_factory() as session:
        hidden = await ledger.hidden_document_ids(session, schema)
        known = await ledger.get_source(session, schema, cid, obj_v2.identity)
    assert old_id in hidden
    assert known[1] == new_id and known[0] == "etag-2"


# --- Rows 8-9: missing objects hide only on confirmation -------------------------------


async def test_missing_object_hides_only_on_second_confirmation(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    doc_id = (await _documents(session_factory, schema))[0]._mapping["id"]

    provider.remove(obj.identity)
    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    async with session_factory() as session:
        assert await ledger.hidden_document_ids(session, schema) == []

    second = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    assert second.outcome == "succeeded"
    async with session_factory() as session:
        assert await ledger.hidden_document_ids(session, schema) == [doc_id]
        # Provenance is retained: the document row still exists.
        remaining = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.documents WHERE id = :id"),
                {"id": doc_id},
            )
        ).scalar()
    assert remaining == 1


# --- Row 12: a failed listing marks nothing missing ------------------------------------


async def test_failed_listing_records_distinct_outcome_and_marks_nothing(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()
    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)

    provider.fail_listing = True
    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)

    assert result.outcome == "failed"
    assert result.reason == "listing_failed"
    async with session_factory() as session:
        assert await ledger.hidden_document_ids(session, schema) == []
        sightings = (
            await session.execute(
                text(f"SELECT missing_sightings FROM {schema}.azure_blob_source_objects "
                     "WHERE connection_id = :cid"),
                {"cid": cid},
            )
        ).fetchall()
    assert [r[0] for r in sightings] == [0]


# --- Row 10: temporary bytes are deleted on every terminal path ------------------------


async def test_temporary_bytes_deleted_on_success(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)

    assert result.outcome == "succeeded"
    assert temp.puts, "the run never staged bytes in temporary storage"
    assert sorted(temp.deletes) == sorted(temp.puts)
    assert temp.objects == {}


async def test_temporary_bytes_deleted_on_object_failure(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    _, _, _, temp = _services()

    def _raising_factory():
        service = DocumentIngestionService(
            dispatcher=RecordingDispatcher(),
            durable_store=FakeStore(),
            working_store=FakeStore(),
        )

        async def _boom(session, document):
            raise RuntimeError("ingestion backend exploded")

        service.ingest = _boom
        return service

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, provider, _raising_factory, temp)

    assert result.outcome == "succeeded" and result.failed == 1
    assert sorted(temp.deletes) == sorted(temp.puts)
    assert temp.objects == {}


# --- Row 11: safe sync status ----------------------------------------------------------


async def test_sync_status_exposes_only_safe_classes(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)

    assert await blob_sync.read_sync_status(session_factory, schema, "nope") == {
        "connection_id": "nope", "outcome": "never_run", "completed_at": None,
    }

    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()
    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)

    status = await blob_sync.read_sync_status(session_factory, schema, cid)
    assert status["run_id"] == result.run_id
    assert status["trigger"] == "manual"
    assert status["outcome"] == "succeeded"
    assert status["objects_ingested"] == 1
    assert set(status) == {
        "run_id", "connection_id", "trigger", "outcome", "reason",
        "objects_seen", "objects_ingested", "objects_skipped",
        "started_at", "completed_at",
    }


# --- Rows 13-14: the common ingestion boundary -----------------------------------------


async def test_sync_documents_cannot_assert_tenant_identity(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob(metadata={"tenant_id": "attacker-tenant"})
    register_provider(cid, _provider((obj, data)))
    factory, durable, working, temp = _services()

    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_MANUAL, get_provider(cid), factory, temp)

    rows = await _documents(session_factory, schema)
    assert len(rows) == 1
    assert rows[0]._mapping["tenant_id"] == tid


# --- Rows 15-16: retrieval excludes hidden documents -----------------------------------


class _StubEmbeddings:
    async def embed(self, query: str):
        return [1.0, 0.0, 0.0, 0.0]


async def test_retrievers_exclude_hidden_documents(tenant, session_factory):
    tid, schema = tenant["tenant_id"], tenant["schema"]

    async def _vec(values):
        return "[" + ",".join(str(v) for v in values) + "]"

    async with session_factory() as session:
        await ledger.ensure_sync_tables(session, schema)
        for doc_id, vec in (("visible-doc", [1.0, 0.0, 0.0, 0.0]),
                            ("hidden-doc", [0.99, 0.01, 0.0, 0.0])):
            await session.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename, status) "
                     "VALUES (:id, :tid, 'f.pdf', 'processed')"),
                {"id": doc_id, "tid": tid},
            )
            await session.execute(
                text(f"INSERT INTO {schema}.document_chunks "
                     "(id, document_id, chunk_index, chunk_text, embedding, purpose) "
                     "VALUES (:id, :doc, 0, :txt, CAST(:emb AS vector), 'query')"),
                {"id": f"c-{doc_id}", "doc": doc_id,
                 "txt": f"text of {doc_id}", "emb": await _vec(vec)},
            )
        await ledger.hide_document(session, schema, document_id="hidden-doc",
                                   connection_id="cid", cause="source_missing")
        await session.commit()

    retriever = DenseRetriever(embedding_service=_StubEmbeddings())
    async with session_factory() as session:
        results = await retriever.retrieve("query", session, schema, top_k=5)

    assert [r.document_id for r in results] == ["visible-doc"]


# --- Row 17: touched OCR failure paths emit safe structured classes --------------------


def test_classify_processing_error_uses_finite_classes():
    assert ocr_worker.classify_processing_error(
        ocr_worker.ContentUnresolvable("gone")) == "content_unresolvable"
    assert ocr_worker.classify_processing_error(
        ocr_worker.UnsupportedMediaType("nope")) == "unsupported_media"
    assert ocr_worker.classify_processing_error(
        RuntimeError("driver quoted 'secret literal'")) == "processing_failed"
    assert ocr_worker.classify_processing_error(
        ValueError("plain value error")) == "processing_failed"


def test_ocr_worker_source_contains_no_unsafe_telemetry():
    import pathlib

    source = pathlib.Path(ocr_worker.__file__).read_text()
    assert "traceback.print_exc" not in source
    assert "traceback" not in source


async def test_failed_processing_stores_class_without_traceback(
    tenant, session_factory, monkeypatch, capsys
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "platform_blob")

    def _boom(data):
        raise ValueError("driver quoted '658-32-1188' back")

    monkeypatch.setattr(ocr_worker, "extract_text_pdf", _boom)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf_as_image", _boom)

    async def _no_embed(texts):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(ocr_worker, "_embed_chunks", _no_embed)

    durable = FakeStore()
    # The worker resolves content through the module store lookup, not the
    # ingestion service's stores: point it at the fake like the retention
    # suite does, so no real MinIO is touched.
    monkeypatch.setattr(ocr_worker, "_store_for", lambda mode: durable)
    service = DocumentIngestionService(
        dispatcher=RecordingDispatcher(), durable_store=durable,
        working_store=FakeStore(),
    )
    from tests.test_ingestion_boundary import normalized as _normalized

    async with session_factory() as session:
        result = await service.ingest(session, _normalized(tid))
    await ocr_worker.process_document(result.document_id, tid)

    async with session_factory() as session:
        row = (
            await session.execute(
                text(f"SELECT status, error_message FROM {schema}.documents "
                     "WHERE id = :id"),
                {"id": result.document_id},
            )
        ).fetchone()
    assert row[0] == "failed"
    assert row[1] == "processing_failed"
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err


async def test_source_only_document_reopens_through_registered_provider(
    tenant, session_factory, monkeypatch, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    register_provider(cid, _provider((obj, data)))

    async with session_factory() as session:
        await session.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, "
                "retention_mode, source_type, source_id, external_id, purpose) "
                "VALUES ('reopen-doc', :tid, 'report.pdf', 'pending', 'source_only', "
                "'azure_blob', :cid, :ext, 'query')"
            ),
            {"tid": tid, "cid": cid, "ext": obj.identity},
        )
        await session.commit()

    def _extract(bytez):
        return [{"span_index": 0, "text": "reopened content here",
                 "char_start": 0, "char_end": 22, "page_number": 0}]

    monkeypatch.setattr(ocr_worker, "extract_text_pdf", _extract)
    monkeypatch.setattr(ocr_worker, "extract_text_pdf_as_image", _extract)

    async def _no_embed(texts):
        return [[0.0] * 4 for _ in texts]

    monkeypatch.setattr(ocr_worker, "_embed_chunks", _no_embed)

    await ocr_worker.process_document("reopen-doc", tid)

    async with session_factory() as session:
        row = (
            await session.execute(
                text(f"SELECT status FROM {schema}.documents WHERE id = 'reopen-doc'")
            )
        ).fetchone()
        spans = (
            await session.execute(
                text(f"SELECT COUNT(*) FROM {schema}.document_text_spans "
                     "WHERE document_id = 'reopen-doc'")
            )
        ).scalar()
    assert row[0] == "processed"
    assert spans == 1


# --- Metric contract: label sets mirror the sync module ---------------------------------


def test_blob_sync_label_sets_mirror_sync_module():
    from src.shared.observability.domain_metrics import OTHER

    assert dm.BLOB_SYNC_TRIGGERS - {OTHER} == blob_sync.TRIGGERS
    assert dm.BLOB_SYNC_OUTCOMES - {OTHER} == blob_sync.OUTCOMES


def test_blob_sync_families_carry_no_tenant_label():
    assert dm.allowlist_violations() == []
    assert "tenant_id" not in {
        label.name for label in dm.BLOB_SYNC.labels
    }


# --- Deferred live provider: the capability stays inactive ------------------------------


async def test_deferred_live_provider_blocks_the_run(tenant, session_factory, connections):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    # No provider registered: the shipped default refuses with
    # prerequisite_missing and the run blocks instead of half-syncing.
    factory, durable, working, temp = _services()

    result = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, get_provider(cid),
                        factory, temp)

    assert result.outcome == "blocked"
    assert result.reason == "prerequisite_missing"
    assert (await _documents(session_factory, schema)) == []


# --- Row 9: one absence adjacent to a listing failure stays visible --------------------


async def test_single_absence_adjacent_to_listing_failure_stays_visible(
    tenant, session_factory, connections
):
    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    provider = _provider((obj, data))
    register_provider(cid, provider)
    factory, durable, working, temp = _services()

    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    doc_id = (await _documents(session_factory, schema))[0]._mapping["id"]

    # A listing failure first: it records a distinct outcome and confirms nothing.
    provider.fail_listing = True
    failed = await _run(session_factory, schema, tid, cid,
                        blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)
    assert failed.outcome == "failed"
    assert failed.reason == "listing_failed"

    # Then the single absence that follows the failure: still only the first
    # consecutive confirmation, so the content stays retrievable.
    provider.fail_listing = False
    provider.remove(obj.identity)
    await _run(session_factory, schema, tid, cid,
               blob_sync.TRIGGER_SCHEDULED, provider, factory, temp)

    async with session_factory() as session:
        # A failure is not a confirmation, so this absence is the first one:
        # the content stays visible until a second consecutive successful
        # enumeration confirms it.
        assert await ledger.hidden_document_ids(session, schema) == []
        sightings = (
            await session.execute(
                text(f"SELECT missing_sightings FROM {schema}.azure_blob_source_objects "
                     "WHERE connection_id = :cid"),
                {"cid": cid},
            )
        ).fetchall()
    assert [r[0] for r in sightings] == [1]
    assert (await _documents(session_factory, schema))[0]._mapping["id"] == doc_id


# --- Tenant isolation: a connection never serves another tenant ------------------------


async def test_cross_tenant_connection_use_is_blocked_without_enumeration(
    tenant, session_factory, connections
):
    from src.shared.tenant_schema import schema_for_tenant

    tid, schema = tenant["tenant_id"], tenant["schema"]
    await set_retention(session_factory, tid, "source_only")
    cid = await connections(tid)
    obj, data = _blob()
    victim_provider = _provider((obj, data))
    register_provider(cid, victim_provider)
    factory, durable, working, temp = _services()

    first = await _run(session_factory, schema, tid, cid,
                       blob_sync.TRIGGER_SCHEDULED, victim_provider, factory, temp)
    assert first.ingested == 1

    attacker_id = "attacker-tenant"
    attacker_schema = schema_for_tenant(attacker_id)
    async with session_factory() as session:
        await session.execute(text(f"CREATE SCHEMA IF NOT EXISTS {attacker_schema}"))
        await session.commit()
    try:
        probe = _provider((obj, data))
        async with session_factory() as session:
            await ledger.ensure_sync_tables(session, attacker_schema)
            await session.commit()
        result = await blob_sync.run_sync(
            session_factory, attacker_id, cid, blob_sync.TRIGGER_MANUAL,
            provider=probe, make_ingestion_service=factory, temp_store=temp,
        )

        assert result.outcome == "blocked"
        assert result.reason == "inactive_connection"
        assert probe.enumerations == 0
        assert probe.acquisitions == []
        # The victim tenant's documents and ledger are untouched.
        assert len(await _documents(session_factory, schema)) == 1
        async with session_factory() as session:
            assert await ledger.hidden_document_ids(session, schema) == []
    finally:
        async with session_factory() as session:
            await session.execute(
                text(f"DROP SCHEMA IF EXISTS {attacker_schema} CASCADE")
            )
            await session.commit()
