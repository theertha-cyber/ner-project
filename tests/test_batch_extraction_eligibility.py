import os
import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.main import app
from src.shared.auth import create_access_token
from src.extraction_service.services.entity_store import _schema


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def eligibility_tenant_schema():
    """Provisions a fresh tenant schema with documents, extraction_runs,
    extracted_entities, and model_versions tables — everything the
    eligible-for-extraction endpoint and its underlying lookups need."""
    engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
    created = []
    tenant_ids = []

    async def _make(tid: str) -> str:
        schema = _schema(tid)
        tenant_ids.append(tid)
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                    INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions)
                    VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10)
                    ON CONFLICT (id) DO NOTHING
                """),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{schema}".documents (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending',
                    purpose VARCHAR(20) NOT NULL DEFAULT 'query'
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{schema}".model_versions (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    version INTEGER,
                    version_number INTEGER,
                    status VARCHAR(20) DEFAULT 'candidate'
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{schema}".extraction_runs (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    document_id VARCHAR,
                    model_version VARCHAR,
                    status VARCHAR NOT NULL DEFAULT 'queued',
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ,
                    total_documents INTEGER NOT NULL DEFAULT 0,
                    processed_count INTEGER NOT NULL DEFAULT 0,
                    skipped_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
                    postprocess_model TEXT,
                    postprocess_prompt_version TEXT,
                    postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS "{schema}".extracted_entities (
                    id VARCHAR PRIMARY KEY,
                    run_id VARCHAR NOT NULL REFERENCES "{schema}".extraction_runs(id) ON DELETE CASCADE,
                    document_id VARCHAR,
                    entity_id VARCHAR NOT NULL,
                    value TEXT,
                    confidence FLOAT,
                    review_status VARCHAR(20) DEFAULT 'unreviewed'
                )
            """))
        created.append(schema)
        return schema

    yield _make

    async with engine.begin() as conn:
        for schema in created:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        if tenant_ids:
            await conn.execute(
                text("DELETE FROM public.tenants WHERE id = ANY(:ids)"),
                {"ids": tenant_ids},
            )
    await engine.dispose()


async def _insert_document(engine, schema, doc_id, tid, filename="doc.pdf", status="processed", purpose="query"):
    async with engine.begin() as conn:
        await conn.execute(
            text(f'INSERT INTO "{schema}".documents (id, tenant_id, filename, status, purpose) VALUES (:id, :tid, :fn, :status, :purpose)'),
            {"id": doc_id, "tid": tid, "fn": filename, "status": status, "purpose": purpose},
        )


async def _mark_extracted(engine, schema, doc_id, model_version):
    run_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO "{schema}".extraction_runs (id, tenant_id, model_version, status)
                VALUES (:id, :tid, :model_version, 'completed')
            """),
            {"id": run_id, "tid": "irrelevant", "model_version": model_version},
        )
        await conn.execute(
            text(f"""
                INSERT INTO "{schema}".extracted_entities (id, run_id, document_id, entity_id, value, confidence)
                VALUES (:id, :run_id, :document_id, 'PER', 'x', 0.9)
            """),
            {"id": str(uuid.uuid4()), "run_id": run_id, "document_id": doc_id},
        )


async def _promote_model(engine, schema, tid, version):
    """Mirrors production shape: the legacy `version` column is left NULL and the
    real value lives in `version_number`. A fixture that populated `version` hid the
    `str(None) == "None"` bug that made every document look never-extracted."""
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                UPDATE "{schema}".model_versions SET status = 'completed' WHERE status = 'promoted'
            """)
        )
        await conn.execute(
            text(f"""
                INSERT INTO "{schema}".model_versions (id, tenant_id, version, version_number, status)
                VALUES (:id, :tid, NULL, :version_number, 'promoted')
            """),
            {"id": str(uuid.uuid4()), "tid": tid, "version_number": version},
        )


@pytest.mark.asyncio
class TestEligibleDocumentsMarksAlreadyExtracted:
    async def test_already_extracted_flag(self, eligibility_tenant_schema, engine):
        tid = "eligibility-flag-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _promote_model(engine, schema, tid, 1)
        await _insert_document(engine, schema, "extracted-doc", tid)
        await _insert_document(engine, schema, "fresh-doc", tid)
        await _mark_extracted(engine, schema, "extracted-doc", model_version="1")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/extract-batch/eligible-documents", headers=auth_header(tid))
            assert resp.status_code == 200
            docs = {d["id"]: d for d in resp.json()["documents"]}
            assert docs["extracted-doc"]["already_extracted"] is True
            assert docs["fresh-doc"]["already_extracted"] is False


@pytest.mark.asyncio
class TestEligibleDocumentsExcludesNonProcessed:
    async def test_excludes_pending_documents(self, eligibility_tenant_schema, engine):
        tid = "eligibility-exclude-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _insert_document(engine, schema, "processed-doc", tid, status="processed")
        await _insert_document(engine, schema, "pending-doc", tid, status="pending")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/extract-batch/eligible-documents", headers=auth_header(tid))
            assert resp.status_code == 200
            doc_ids = {d["id"] for d in resp.json()["documents"]}
            assert doc_ids == {"processed-doc"}


@pytest.mark.asyncio
class TestTrainingDocumentsAreNotExtractable:
    """Training documents exist to be annotated and exported as a training corpus.
    They keep their document_text_spans rows, but no extraction path may reach them."""

    async def test_eligible_documents_excludes_training_purpose(self, eligibility_tenant_schema, engine):
        tid = "eligibility-purpose-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _insert_document(engine, schema, "query-doc", tid, purpose="query")
        await _insert_document(engine, schema, "training-doc", tid, purpose="training")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/extract-batch/eligible-documents", headers=auth_header(tid))
            assert resp.status_code == 200
            doc_ids = {d["id"] for d in resp.json()["documents"]}
            assert doc_ids == {"query-doc"}

    async def test_explicit_training_document_id_is_rejected(self, eligibility_tenant_schema, engine):
        tid = "batch-explicit-training-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _insert_document(engine, schema, "query-doc", tid, purpose="query")
        await _insert_document(engine, schema, "training-doc", tid, purpose="training")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=query-doc,training-doc",
                headers=auth_header(tid),
            )
        assert resp.status_code == 422
        assert "training-doc" in resp.json()["detail"]

    async def test_batch_without_ids_skips_training_documents(self, eligibility_tenant_schema, engine, monkeypatch):
        tid = "batch-all-purpose-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _insert_document(engine, schema, "query-doc", tid, purpose="query")
        await _insert_document(engine, schema, "training-doc", tid, purpose="training")

        sent = {}

        def fake_send_task(name, args=None, queue=None):
            sent["doc_ids"] = args[2]

        from src.extraction_service.celery_app import celery_app
        monkeypatch.setattr(celery_app, "send_task", fake_send_task)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/extract-batch", headers=auth_header(tid))
        assert resp.status_code == 202
        assert sent["doc_ids"] == ["query-doc"]

    async def test_worker_document_filter_drops_training_documents(self, eligibility_tenant_schema, engine, monkeypatch):
        """Defense in depth: even a task queued with a training id (stale queue entry,
        direct celery call) must not reach the model."""
        tid = "worker-purpose-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _insert_document(engine, schema, "query-doc", tid, purpose="query")
        await _insert_document(engine, schema, "training-doc", tid, purpose="training")

        from sqlalchemy import create_engine as create_sync_engine
        from src.extraction_service import worker

        sync_url = os.environ["NER_DATABASE_URL"].replace("+asyncpg", "")
        sync_engine = create_sync_engine(sync_url)
        monkeypatch.setattr(worker, "_get_sync_engine", lambda: sync_engine)

        try:
            assert worker._get_documents_to_process(tid, ["query-doc", "training-doc"]) == ["query-doc"]
        finally:
            sync_engine.dispose()


@pytest.mark.asyncio
class TestEligibleDocumentsNonAdmin:
    async def test_business_user_allowed(self, eligibility_tenant_schema):
        tid = "eligibility-nonadmin-tenant"
        await eligibility_tenant_schema(tid)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/extract-batch/eligible-documents",
                headers=auth_header(tid, role="business_user"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestEligibleDocumentsReeligibleAfterPromotion:
    async def test_document_reeligible_after_new_model_promoted(self, eligibility_tenant_schema, engine):
        tid = "eligibility-repromote-tenant"
        schema = await eligibility_tenant_schema(tid)
        await _promote_model(engine, schema, tid, 1)
        await _insert_document(engine, schema, "superseded-doc", tid)
        await _mark_extracted(engine, schema, "superseded-doc", model_version="1")

        await _promote_model(engine, schema, tid, 2)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/extract-batch/eligible-documents", headers=auth_header(tid))
            assert resp.status_code == 200
            docs = {d["id"]: d for d in resp.json()["documents"]}
            assert docs["superseded-doc"]["already_extracted"] is False
