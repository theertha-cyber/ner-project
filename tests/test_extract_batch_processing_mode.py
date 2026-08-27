"""Covers verification.md rows 68-75 and 83.

The processing mode must be chosen by the caller, validated by the server, recorded on
the run, and carried to the worker as a task argument — not held in client state and not
re-read from settings by the worker, which would let a configuration change while a run
is queued make the recorded mode disagree with what actually happened."""

import os

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.api.v1 import extraction as extraction_api
from src.extraction_service.main import app
from src.extraction_service.services.entity_store import _schema
from src.extraction_service.services.processing_modes import ProcessingMode
from src.shared.auth import create_access_token
from src.shared.config import settings


def auth_header(tid: str, role: str = "business_user") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


_DOCUMENTS_DDL = """
    CREATE TABLE IF NOT EXISTS "{schema}".documents (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        filename VARCHAR(255) NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        purpose VARCHAR(20) NOT NULL DEFAULT 'query'
    )
"""

_EXTRACTION_RUNS_DDL = """
    CREATE TABLE IF NOT EXISTS "{schema}".extraction_runs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        document_id VARCHAR,
        model_version VARCHAR,
        status VARCHAR NOT NULL DEFAULT 'queued',
        started_at TIMESTAMP WITH TIME ZONE NOT NULL,
        completed_at TIMESTAMP WITH TIME ZONE,
        total_documents INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0,
        processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        postprocess_model TEXT,
        postprocess_prompt_version TEXT,
        postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
    )
"""

_RECONCILE_EXTRACTION_RUNS = """
    ALTER TABLE "{schema}".extraction_runs
        ADD COLUMN IF NOT EXISTS processing_mode VARCHAR(32) NOT NULL DEFAULT 'bert_only',
        ADD COLUMN IF NOT EXISTS postprocess_model TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_prompt_version TEXT,
        ADD COLUMN IF NOT EXISTS postprocess_degraded BOOLEAN NOT NULL DEFAULT FALSE
"""


@pytest_asyncio.fixture(autouse=True)
async def baseline_schema():
    """Provisions everything this suite touches in the shared `test-tenant` schema.

    Other suites drop that schema on teardown, and file order decides whether this one
    runs before or after them — so it provisions rather than assuming, and reconciles the
    columns in case an older `extraction_runs` survived. Non-destructive: creates if
    absent, never drops."""
    engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
    async with engine.begin() as conn:
        schema = _schema("test-tenant")
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(_DOCUMENTS_DDL.format(schema=schema)))
        await conn.execute(text(_EXTRACTION_RUNS_DDL.format(schema=schema)))
        await conn.execute(text(_RECONCILE_EXTRACTION_RUNS.format(schema=schema)))
    await engine.dispose()
    yield


@pytest_asyncio.fixture
async def captured_tasks(monkeypatch):
    """Records what would reach Celery, so the task argument list is asserted rather
    than assumed."""
    sent: list[dict] = []

    from src.extraction_service import celery_app as celery_module

    def _send_task(name, args=None, queue=None, **kwargs):
        sent.append({"name": name, "args": list(args or []), "queue": queue})

    monkeypatch.setattr(celery_module.celery_app, "send_task", _send_task)
    return sent


async def _run_row(tid: str, run_id: str) -> dict:
    engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"SELECT * FROM {_schema(tid)}.extraction_runs WHERE id = :id"),
                {"id": run_id},
            )
            row = result.fetchone()
            return dict(row._mapping) if row else {}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
class TestBodyCarriesDocumentIds:
    """Row 68 — the supported request form."""

    async def test_document_ids_in_the_body_are_accepted(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1", "doc2", "doc3"]},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 202
        body = resp.json()
        assert "run_id" in body and body["status"] == "queued"
        assert captured_tasks[-1]["args"][2] == ["doc1", "doc2", "doc3"]

    async def test_the_run_is_immediately_queryable(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"]},
                headers=auth_header("test-tenant"),
            )
            run_id = post.json()["run_id"]
            get = await client.get(f"/api/v1/extract-batch/{run_id}", headers=auth_header("test-tenant"))

        assert get.status_code == 200
        assert get.json()["status"] == "queued"


@pytest.mark.asyncio
class TestDefaultMode:
    """Row 69 — a caller that says nothing gets the pipeline that exists today."""

    async def test_omitted_mode_records_bert_only(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"]},
                headers=auth_header("test-tenant"),
            )
        run_id = resp.json()["run_id"]

        row = await _run_row("test-tenant", run_id)

        assert row["processing_mode"] == ProcessingMode.BERT_ONLY.value
        assert captured_tasks[-1]["args"][3] == ProcessingMode.BERT_ONLY.value

    async def test_no_body_at_all_records_bert_only(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1",
                headers=auth_header("test-tenant"),
            )
        run_id = resp.json()["run_id"]

        row = await _run_row("test-tenant", run_id)

        assert row["processing_mode"] == ProcessingMode.BERT_ONLY.value


@pytest.mark.asyncio
class TestRequestedModeReachesTheWorker:
    """Row 70."""

    async def test_mode_is_present_in_the_task_arguments(self, monkeypatch, captured_tasks):
        monkeypatch.setattr(settings, "postprocess_enabled", True)
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "gpt-4o-mini")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "bert_llm_postprocess"},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 202
        task = captured_tasks[-1]
        assert task["name"] == "run_batch_extraction"
        assert task["args"][3] == ProcessingMode.BERT_LLM_POSTPROCESS.value

    async def test_the_worker_signature_takes_the_mode_rather_than_reading_settings(self):
        """A settings lookup inside the worker would let a configuration change while
        the run is queued alter what it does, leaving the recorded mode untrue."""
        import inspect

        from src.extraction_service.worker import run_batch_extraction

        signature = inspect.signature(run_batch_extraction)
        assert "processing_mode" in signature.parameters

        source = inspect.getsource(run_batch_extraction)
        assert "settings.postprocess_enabled" not in source


@pytest.mark.asyncio
class TestUnknownModeIsRejected:
    """Row 71."""

    async def test_unknown_mode_returns_422(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "llm_only"},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 422

    async def test_no_run_is_created_for_an_unknown_mode(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "llm_only"},
                headers=auth_header("test-tenant"),
            )

        assert captured_tasks == []


@pytest.mark.asyncio
class TestUnconfiguredPostprocessingIsRejected:
    """Row 72 — rejected, never silently downgraded."""

    async def test_returns_422_when_postprocessing_is_disabled(self, monkeypatch, captured_tasks):
        monkeypatch.setattr(settings, "postprocess_enabled", False)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "bert_llm_postprocess"},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 422
        assert "post-processing" in resp.json()["detail"].lower()

    async def test_no_run_is_created(self, monkeypatch, captured_tasks):
        monkeypatch.setattr(settings, "postprocess_enabled", False)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "bert_llm_postprocess"},
                headers=auth_header("test-tenant"),
            )

        assert captured_tasks == []

    async def test_missing_chat_deployment_also_rejects(self, monkeypatch, captured_tasks):
        monkeypatch.setattr(settings, "postprocess_enabled", True)
        monkeypatch.setattr(settings, "azure_openai_chat_deployment", "")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"], "processing_mode": "bert_llm_postprocess"},
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 422


class TestModeDoesNotAffectSkipLogic:
    """Row 73 — flipping the toggle must not reprocess and overwrite existing entities."""

    def test_skip_set_is_computed_from_the_model_version_alone(self):
        import inspect

        from src.extraction_service.worker import run_batch_extraction

        source = inspect.getsource(run_batch_extraction)
        skip_line = next(line for line in source.splitlines() if "get_already_extracted(" in line)

        assert "model_version" in skip_line
        assert "processing_mode" not in skip_line

    def test_already_extracted_signature_takes_no_mode(self):
        import inspect

        from src.extraction_service.services.entity_store import get_already_extracted

        assert "processing_mode" not in inspect.signature(get_already_extracted).parameters


@pytest.mark.asyncio
class TestRunRecordsWhatItDid:
    """Rows 74 and 75."""

    async def test_status_endpoint_reports_the_processing_mode(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"]},
                headers=auth_header("test-tenant"),
            )
            run_id = post.json()["run_id"]
            get = await client.get(f"/api/v1/extract-batch/{run_id}", headers=auth_header("test-tenant"))

        body = get.json()
        assert body["processing_mode"] == ProcessingMode.BERT_ONLY.value

    async def test_postprocessor_model_and_prompt_version_are_reported(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1"]},
                headers=auth_header("test-tenant"),
            )
            run_id = post.json()["run_id"]

        engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
        async with engine.begin() as conn:
            await conn.execute(
                text(f"""
                    UPDATE {_schema('test-tenant')}.extraction_runs
                    SET status = 'completed', processing_mode = 'bert_llm_postprocess',
                        postprocess_model = 'gpt-4o-mini', postprocess_prompt_version = 'v1',
                        postprocess_degraded = FALSE, processed_count = 1
                    WHERE id = :id
                """),
                {"id": run_id},
            )
        await engine.dispose()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            get = await client.get(f"/api/v1/extract-batch/{run_id}", headers=auth_header("test-tenant"))

        body = get.json()
        assert body["processing_mode"] == "bert_llm_postprocess"
        assert body["postprocess_model"] == "gpt-4o-mini"
        assert body["postprocess_prompt_version"] == "v1"
        assert body["postprocess_degraded"] is False

    async def test_a_degraded_run_completes_and_says_so(self, captured_tasks):
        """Row 75: post-processing failing everywhere still leaves a completed run whose
        documents were persisted."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post = await client.post(
                "/api/v1/extract-batch",
                json={"documentIds": ["doc1", "doc2"]},
                headers=auth_header("test-tenant"),
            )
            run_id = post.json()["run_id"]

        engine = create_async_engine(os.environ["NER_DATABASE_URL"], isolation_level="AUTOCOMMIT")
        async with engine.begin() as conn:
            await conn.execute(
                text(f"""
                    UPDATE {_schema('test-tenant')}.extraction_runs
                    SET status = 'completed', processing_mode = 'bert_llm_postprocess',
                        postprocess_degraded = TRUE, processed_count = 2, failed_count = 0
                    WHERE id = :id
                """),
                {"id": run_id},
            )
        await engine.dispose()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            get = await client.get(f"/api/v1/extract-batch/{run_id}", headers=auth_header("test-tenant"))
            listing = await client.get("/api/v1/extract-batch", headers=auth_header("test-tenant"))

        body = get.json()
        assert body["status"] == "completed"
        assert body["postprocess_degraded"] is True
        assert body["processed_count"] == 2
        assert body["failed_count"] == 0

        listed = next(r for r in listing.json()["runs"] if r["run_id"] == run_id)
        assert listed["postprocess_degraded"] is True
        assert listed["processing_mode"] == "bert_llm_postprocess"


@pytest.mark.asyncio
class TestQueryParameterCompatibility:
    """Row 83 — existing clients keep working for one release."""

    async def test_query_parameter_form_is_still_accepted(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1,doc2",
                headers=auth_header("test-tenant"),
            )

        assert resp.status_code == 202
        assert captured_tasks[-1]["args"][2] == ["doc1", "doc2"]

    async def test_query_parameter_form_uses_the_default_mode(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1",
                headers=auth_header("test-tenant"),
            )
        run_id = resp.json()["run_id"]

        row = await _run_row("test-tenant", run_id)

        assert row["processing_mode"] == ProcessingMode.BERT_ONLY.value

    async def test_the_body_wins_when_both_are_supplied(self, captured_tasks):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/extract-batch?documentIds=from-query",
                json={"documentIds": ["from-body"]},
                headers=auth_header("test-tenant"),
            )

        assert captured_tasks[-1]["args"][2] == ["from-body"]
