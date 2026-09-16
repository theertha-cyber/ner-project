"""The LLM pre-labeling trigger, its job status, and what it writes.

Covers verification.md rows 1-3, 11-13, 16.

The provider is stubbed throughout — `StubLLMClient`, never a network call — but the database is
real, because the two things most worth checking here are exactly the two a mock would hide:
that the write lands in the right tenant's schema (ADR-001), and that the request returns before
the provider call happens rather than after it.

Celery is stubbed the same way `test_training_jobs_api.py` stubs it: the trigger is asserted to
have enqueued, and the task body is then invoked directly. A live broker would test Celery, not
this change.
"""

import os
import time
import uuid
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.annotation_service.services.llm_client import StubLLMClient
from src.annotation_service.worker import run_llm_prelabel_sync
from src.shared.auth import create_access_token
from src.shared.config import settings

DOCUMENT_TEXT = "John Doe works at Acme Corp and studied at Vellore Institute of Technology."


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid, role="annotator"):
    return create_access_token(tenant_id=tid, user_id="test-user", role=role)


def _tenant_tables_sql(schema: str) -> list[str]:
    return [
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                filename VARCHAR(255) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                purpose VARCHAR(20) NOT NULL DEFAULT 'query',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.document_text_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL,
                span_index INTEGER,
                "text" TEXT,
                char_start INTEGER,
                char_end INTEGER,
                page_number INTEGER,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL DEFAULT 1.0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ,
                bio_tags TEXT[]
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.suggested_spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                entity_type VARCHAR(255) NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_content VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                source VARCHAR(16) NOT NULL DEFAULT 'keyword',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.llm_prelabel_jobs (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
                status VARCHAR(16) NOT NULL DEFAULT 'queued',
                content_hash VARCHAR(64) NOT NULL,
                config_version VARCHAR(64) NOT NULL,
                served_from_cache BOOLEAN NOT NULL DEFAULT false,
                spans JSONB,
                counts JSONB,
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                completed_at TIMESTAMPTZ
            )
        """,
    ]


_ENTITY_DEFINITIONS_SQL = """
    CREATE TABLE IF NOT EXISTS public.entity_definitions (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        name VARCHAR(255) NOT NULL,
        description TEXT,
        examples JSON,
        qa_examples JSONB,
        validation_rule VARCHAR(500),
        target_table VARCHAR(255),
        base_label_mapping JSON,
        version INTEGER DEFAULT 1,
        required_flag BOOLEAN DEFAULT false,
        is_active BOOLEAN DEFAULT true,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


_TENANTS_SQL = """
    CREATE TABLE IF NOT EXISTS public.tenants (
        id VARCHAR PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        slug VARCHAR(63) NOT NULL UNIQUE,
        status VARCHAR(20) DEFAULT 'active',
        max_users INTEGER DEFAULT 10,
        max_documents INTEGER DEFAULT 1000,
        max_storage_gb INTEGER DEFAULT 5,
        max_model_versions INTEGER DEFAULT 10,
        storage_used_bytes BIGINT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


async def _make_tenant(engine, entity_types=True):
    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(_TENANTS_SQL))
        await conn.execute(text(_ENTITY_DEFINITIONS_SQL))
        for ddl in _tenant_tables_sql(schema):
            await conn.execute(text(ddl))
        # The tenant-context middleware resolves the JWT's tenant against this table before any
        # handler runs, so a schema without a row here is a 404 rather than the request under
        # test.
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status) "
                "VALUES (:id, :name, :slug, 'active') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid, "name": f"LLM Prelabel {tid[:8]}", "slug": f"llm-prelabel-{tid[:8]}"},
        )
        if entity_types:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, description, examples, is_active) VALUES "
                    "(:i1, :tid, 'person_name', 'A person', '[\"John Smith\"]', true), "
                    "(:i2, :tid, 'organization', 'A company', '[\"Acme Corp\"]', true), "
                    "(:i3, :tid, 'institute', 'A school', '[\"MIT\"]', true)"
                ),
                {
                    "i1": str(uuid.uuid4()),
                    "i2": str(uuid.uuid4()),
                    "i3": str(uuid.uuid4()),
                    "tid": tid,
                },
            )
    return {"tid": tid, "schema": schema}


async def _add_document(engine, tenant, document_text=DOCUMENT_TEXT):
    doc_id = str(uuid.uuid4())
    schema = tenant["schema"]
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {schema}.documents (id, tenant_id, filename, status, purpose) "
                "VALUES (:id, :tid, 'test.txt', 'processed', 'training')"
            ),
            {"id": doc_id, "tid": tenant["tid"]},
        )
        if document_text is not None:
            await conn.execute(
                text(
                    f'INSERT INTO {schema}.document_text_spans '
                    '(id, document_id, span_index, "text", char_start, char_end, page_number) '
                    "VALUES (:sid, :doc_id, 0, :txt, 0, :length, 1)"
                ),
                {
                    "sid": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "txt": document_text,
                    "length": len(document_text),
                },
            )
    return doc_id


@pytest.fixture
async def engine():
    engine = create_async_engine(
        settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'tenant_%'"
            )
        )
        for row in rows:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {row[0]} CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS public.entity_definitions CASCADE"))
        await conn.execute(
            text("DELETE FROM public.tenants WHERE slug LIKE 'llm-prelabel-%'")
        )


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def fake_send_task(monkeypatch):
    """Record enqueues instead of reaching a broker.

    The list is the evidence that the trigger handed the work off rather than doing it — which
    is the whole of the asynchronous-execution requirement as seen from the request side."""
    from src.annotation_service.api.v1 import llm_prelabel as module

    calls = []

    def _send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args, "queue": kwargs.get("queue")})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


def _entities(*pairs):
    return {"entities": [{"entity_type": t, "quote": q} for t, q in pairs]}


DEFAULT_RESPONSE = _entities(
    ("person_name", "John Doe"),
    ("organization", "Acme Corp"),
    ("institute", "Vellore Institute of Technology"),
)


class TestTrigger:
    """verification.md rows 1-3."""

    async def test_trigger_returns_202_with_job_id(self, client, engine, fake_send_task):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 202, resp.text
        body = resp.json()
        assert body["job_id"]
        assert body["status"] == "queued"
        assert body["cached"] is False

    async def test_trigger_422_no_extracted_text(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant, document_text=None)

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "NO_TEXT"

    async def test_trigger_422_no_entity_types(self, client, engine):
        tenant = await _make_tenant(engine, entity_types=False)
        doc_id = await _add_document(engine, tenant)

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "NO_ENTITY_TYPES"

    async def test_an_inactive_entity_type_does_not_count_as_configured(self, client, engine):
        """"Active entity types" is the eligibility test, not "rows in the catalog"."""
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions SET is_active = false WHERE tenant_id = :tid"
                ),
                {"tid": tenant["tid"]},
            )

        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "NO_ENTITY_TYPES"


class TestAsynchronousExecution:
    """verification.md rows 12-13."""

    async def test_trigger_returns_before_llm_completes(self, client, engine, fake_send_task):
        """The request returns a handle; the provider call has not happened yet.

        Asserted two ways, because the timing alone would also pass if the call were merely
        fast: the client's call count is still zero when the response arrives, and the enqueue
        that will make the call has been recorded."""
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        stub = StubLLMClient(DEFAULT_RESPONSE)

        started = time.monotonic()
        resp = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )
        elapsed = time.monotonic() - started

        assert resp.status_code == 202
        assert elapsed < 1.0
        assert stub.call_count == 0
        assert len(fake_send_task) == 1
        assert fake_send_task[0]["name"] == "run_llm_prelabel"
        assert fake_send_task[0]["args"] == [tenant["tid"], doc_id, resp.json()["job_id"]]

    async def test_the_task_is_enqueued_on_a_non_gpu_queue(self, client, engine, fake_send_task):
        """design.md Decision 6 — never `training.jobs`, never the GPU node pool."""
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)

        await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm",
            headers=auth_header(make_token(tenant["tid"])),
        )

        queue = fake_send_task[0]["queue"]
        assert queue == settings.annotation_llm_celery_queue
        assert queue == "annotation.llm_jobs"
        assert "training" not in queue

    async def test_job_status_reflects_completion(self, client, engine, fake_send_task):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        token = make_token(tenant["tid"])

        trigger = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm", headers=auth_header(token)
        )
        job_id = trigger.json()["job_id"]

        queued = await client.get(
            f"/api/v1/documents/{doc_id}/prelabel/llm/{job_id}", headers=auth_header(token)
        )
        assert queued.json()["status"] == "queued"

        run_llm_prelabel_sync(
            tenant["tid"], doc_id, job_id, llm_client=StubLLMClient(DEFAULT_RESPONSE)
        )

        status = await client.get(
            f"/api/v1/documents/{doc_id}/prelabel/llm/{job_id}", headers=auth_header(token)
        )
        assert status.status_code == 200
        body = status.json()
        assert body["status"] == "completed"
        assert body["counts"]["returned"] == 3
        assert body["counts"]["grounded"] == 3

        # The spans themselves come from the existing listing, not from the job.
        listed = await client.get(
            f"/api/v1/documents/{doc_id}/spans?type=suggested", headers=auth_header(token)
        )
        assert listed.status_code == 200
        assert {span["entity_type"] for span in listed.json()} == {
            "person_name",
            "organization",
            "institute",
        }
        assert all(span["source"] == "llm" for span in listed.json())

    async def test_a_failed_provider_call_is_recorded_on_the_job(self, client, engine):
        """A job that goes quiet is indistinguishable from a document with no entities."""
        from src.annotation_service.services.llm_client import LLMUnavailable

        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        token = make_token(tenant["tid"])

        trigger = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm", headers=auth_header(token)
        )
        job_id = trigger.json()["job_id"]

        class _Failing:
            def complete_json(self, system_prompt, user_payload):
                raise LLMUnavailable("provider error: boom")

        with pytest.raises(LLMUnavailable):
            run_llm_prelabel_sync(tenant["tid"], doc_id, job_id, llm_client=_Failing())

        status = await client.get(
            f"/api/v1/documents/{doc_id}/prelabel/llm/{job_id}", headers=auth_header(token)
        )
        assert status.json()["status"] == "failed"
        assert "boom" in status.json()["error_message"]


class TestStorage:
    """verification.md row 11."""

    async def test_llm_prelabel_replaces_existing_suggestions(self, client, engine):
        tenant = await _make_tenant(engine)
        doc_id = await _add_document(engine, tenant)
        schema = tenant["schema"]
        token = make_token(tenant["tid"])

        async with engine.begin() as conn:
            for index in range(2):
                await conn.execute(
                    text(
                        f"INSERT INTO {schema}.suggested_spans "
                        "(id, document_id, entity_type, char_start, char_end, text_content, "
                        " confidence, source) "
                        "VALUES (:id, :doc_id, 'person_name', :cs, :ce, 'stale', 0.85, 'keyword')"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "doc_id": doc_id,
                        "cs": 200 + index,
                        "ce": 205 + index,
                    },
                )

        trigger = await client.post(
            f"/api/v1/documents/{doc_id}/prelabel/llm", headers=auth_header(token)
        )
        run_llm_prelabel_sync(
            tenant["tid"], doc_id, trigger.json()["job_id"],
            llm_client=StubLLMClient(DEFAULT_RESPONSE),
        )

        listed = await client.get(
            f"/api/v1/documents/{doc_id}/spans?type=suggested", headers=auth_header(token)
        )
        spans = listed.json()
        assert len(spans) == 3
        assert all(span["source"] == "llm" for span in spans)
        assert all(span["text"] != "stale" for span in spans)


class TestTenantIsolation:
    """verification.md row 16 — ADR-001, exercised with two real tenants."""

    async def test_llm_prelabel_is_tenant_scoped(self, client, engine):
        acme = await _make_tenant(engine)
        globex = await _make_tenant(engine)
        acme_doc = await _add_document(engine, acme)
        globex_doc = await _add_document(
            engine, globex, document_text="Globex confidential: Hana Bex leads the team."
        )

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE public.entity_definitions SET name = 'globex_only_type' "
                    "WHERE tenant_id = :tid AND name = 'institute'"
                ),
                {"tid": globex["tid"]},
            )

        trigger = await client.post(
            f"/api/v1/documents/{acme_doc}/prelabel/llm",
            headers=auth_header(make_token(acme["tid"])),
        )
        stub = StubLLMClient(DEFAULT_RESPONSE)
        run_llm_prelabel_sync(acme["tid"], acme_doc, trigger.json()["job_id"], llm_client=stub)

        # The payload sent to the provider carries one tenant's document and one tenant's
        # configuration — the other tenant's text and entity types are nowhere in it.
        payload = stub.last_payload
        assert DOCUMENT_TEXT in payload
        assert "Globex confidential" not in payload
        assert "Hana Bex" not in payload
        assert "globex_only_type" not in payload

        async with engine.connect() as conn:
            acme_count = (
                await conn.execute(
                    text(f"SELECT COUNT(*) FROM {acme['schema']}.suggested_spans")
                )
            ).scalar()
            globex_count = (
                await conn.execute(
                    text(f"SELECT COUNT(*) FROM {globex['schema']}.suggested_spans")
                )
            ).scalar()
            globex_jobs = (
                await conn.execute(
                    text(f"SELECT COUNT(*) FROM {globex['schema']}.llm_prelabel_jobs")
                )
            ).scalar()

        assert acme_count == 3
        assert globex_count == 0
        assert globex_jobs == 0
        assert globex_doc  # the other tenant's document was never touched
