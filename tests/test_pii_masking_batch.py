"""Batch-level coverage for the Local-Only Type Coverage Requirement and Fail-Closed on Local
Detection Failure requirements — the single-document versions of both are covered in
`test_pii_masking_wiring.py`; this file confirms the batch trigger and batch worker enforce the
same two rules independently, per design.md ("a business rule stated only in one endpoint is not
a rule").
"""

import os
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
from src.annotation_service.services.pii_masking import StubLocalModelClient
from src.annotation_service.worker import run_prelabel_batch_sync
from src.shared.config import settings
from tests.seed_bootstrap_support import add_document, auth_header, drop_test_schemas


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
    await drop_test_schemas(engine)


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def fake_send_task(monkeypatch):
    from src.annotation_service.api.v1 import seed_bootstrap as module

    calls = []

    def _send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args, "queue": kwargs.get("queue")})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


async def _make_batch_tenant(engine, *, local_only_mapped: bool):
    """A throwaway tenant with one `open` type and one `local_only` type — mapped or not,
    per the scenario under test. Mirrors `seed_bootstrap_support.make_tenant`, built by hand
    here since that helper only accepts entity type *names*, not custom sensitivity/mapping."""
    from tests.seed_bootstrap_support import (
        _ADD_SENSITIVITY_IF_MISSING,
        _ENTITY_DEFINITIONS_SQL,
        _TENANTS_SQL,
        tenant_tables_sql,
    )

    tid = uuid.uuid4().hex
    schema = f"tenant_{tid}"
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        await conn.execute(text(_TENANTS_SQL))
        await conn.execute(text(_ENTITY_DEFINITIONS_SQL))
        await conn.execute(text(_ADD_SENSITIVITY_IF_MISSING))
        for ddl in tenant_tables_sql(schema):
            await conn.execute(text(ddl))
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status) "
                "VALUES (:id, :name, :slug, 'active') ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid, "name": f"Masking Batch {tid[:8]}", "slug": f"seed-bootstrap-{tid[:8]}"},
        )
        mapping = '{"PER": ["child_name"]}' if local_only_mapped else "{}"
        await conn.execute(
            text(
                "INSERT INTO public.entity_definitions "
                "(id, tenant_id, name, description, examples, version, is_active, sensitivity, "
                " base_label_mapping) VALUES "
                "(:i1, :tid, 'organization', 'A company', '[]', 1, true, 'open', NULL), "
                "(:i2, :tid, 'child_name', 'A child''s name', '[]', 1, true, 'local_only', "
                "   CAST(:mapping AS JSON))"
            ),
            {"i1": str(uuid.uuid4()), "i2": str(uuid.uuid4()), "tid": tid, "mapping": mapping},
        )
    return {"tid": tid, "schema": schema}


class TestBatchLocalOnlyCoverageRequirement:
    async def test_batch_trigger_refused_when_local_only_type_has_no_mapping(self, client, engine):
        tenant = await _make_batch_tenant(engine, local_only_mapped=False)
        doc_id = await add_document(engine, tenant)

        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": [doc_id], "batch_kind": "initial"},
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "LOCAL_ONLY_TYPE_NOT_COVERED"

    async def test_batch_trigger_allowed_when_local_only_type_is_mapped(self, client, engine):
        tenant = await _make_batch_tenant(engine, local_only_mapped=True)
        doc_id = await add_document(engine, tenant)

        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": [doc_id], "batch_kind": "initial"},
            headers=auth_header(tenant["tid"]),
        )

        assert resp.status_code == 202


class TestBatchFailClosed:
    async def test_one_documents_local_detection_failure_does_not_abort_the_batch(
        self, client, engine
    ):
        tenant = await _make_batch_tenant(engine, local_only_mapped=True)
        doc_ids = [await add_document(engine, tenant) for _ in range(3)]

        resp = await client.post(
            "/api/v1/prelabel-batches",
            json={"document_ids": doc_ids, "batch_kind": "initial"},
            headers=auth_header(tenant["tid"]),
        )
        assert resp.status_code == 202
        batch_id = resp.json()["batch_id"]

        llm_client = StubLLMClient({"entities": [{"entity_type": "organization", "quote": "x"}]})
        # Fails on the 2nd call to the local model — i.e. the 2nd document processed —
        # succeeding for the other two, modeling an intermittent failure rather than an outage.
        local_model_client = StubLocalModelClient(predictions=[], fail_on=2)

        run_prelabel_batch_sync(
            tenant["tid"], batch_id, llm_client=llm_client, local_model_client=local_model_client,
        )

        resp = await client.get(
            f"/api/v1/prelabel-batches/{batch_id}", headers=auth_header(tenant["tid"])
        )
        body = resp.json()
        assert body["succeeded"] == 2
        assert body["failed"] == 1

        failed = [d for d in body["documents"] if d["status"] == "failed"]
        assert len(failed) == 1
        assert "local detection failed" in failed[0]["error_message"]

        # The failed document's local-detection call never reached the external LLM for that
        # document — only the 2 successful documents did.
        assert llm_client.call_count == 2
