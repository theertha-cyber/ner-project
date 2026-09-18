"""The pre-submission readiness check: per entity type, advisory, and reading ADR-010's threshold.

Covers verification.md rows 18-21.

Two apps are driven here on purpose. The readiness report is a gateway endpoint; training
submission is a `training_service` endpoint; and row 20 is the claim that the first does not
constrain the second. Asserting that against one app would prove only that the report is
harmless to itself.

`DATASET_READINESS_ENTITIES_PER_TYPE` is imported and used to build the fixtures rather than the
literal 200 being typed here. If someone changes the constant, these tests move with it — which
is what it means for there to be one threshold rather than two (ADR-010, verification.md Risk 5).
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

from src.gateway.api.v1.dashboard import DATASET_READINESS_ENTITIES_PER_TYPE
from src.gateway.main import app as gateway_app
from src.shared.config import settings
from tests.seed_bootstrap_support import (
    add_document,
    auth_header,
    drop_test_schemas,
    make_tenant,
)

THRESHOLD = DATASET_READINESS_ENTITIES_PER_TYPE

_TRAINING_JOBS_SQL = """
    CREATE TABLE IF NOT EXISTS {schema}.training_jobs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        status VARCHAR(20) DEFAULT 'pending_approval',
        hyperparams JSONB,
        run_number INTEGER,
        current_epoch INTEGER,
        current_loss DOUBLE PRECISION,
        metrics JSONB,
        error_message TEXT,
        celery_task_id VARCHAR,
        model_version_id VARCHAR,
        mlflow_run_id VARCHAR,
        mlflow_run_url VARCHAR,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        failed_at TIMESTAMPTZ
    )
"""

_AUDIT_EVENTS_SQL = """
    CREATE TABLE IF NOT EXISTS public.audit_events (
        id VARCHAR PRIMARY KEY,
        actor VARCHAR(255),
        role VARCHAR(50),
        action VARCHAR(255),
        target VARCHAR(255),
        kind VARCHAR(50),
        tenant_id VARCHAR,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
"""


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
    transport = ASGITransport(app=gateway_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def training_client():
    from src.training_service.main import app as training_app

    transport = ASGITransport(app=training_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def fake_training_send_task(monkeypatch):
    from src.training_service.api.v1 import training_jobs as module

    calls = []

    def _send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(module.celery_app, "send_task", _send_task)
    return calls


async def _add_spans(engine, tenant, doc_id, entity_type, count):
    """`count` confirmed spans of one type. Written directly: how they got there is not what
    the readiness check is about."""
    schema = tenant["schema"]
    async with engine.begin() as conn:
        for index in range(count):
            await conn.execute(
                text(
                    f"INSERT INTO {schema}.spans "
                    "(id, document_id, entity_type, char_start, char_end, text_content, "
                    " confidence) "
                    "VALUES (:id, :doc_id, :entity_type, :start, :end, :text_val, 1.0)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "entity_type": entity_type,
                    "start": index,
                    "end": index + 1,
                    "text_val": f"{entity_type}-{index}",
                },
            )


async def _readiness(client, tenant):
    resp = await client.get(
        f"/api/v1/tenants/seed/training-readiness", headers=auth_header(tenant["tid"])
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _by_type(report) -> dict:
    return {row["entity_type"]: row for row in report["entity_types"]}


class TestReadinessReport:
    """verification.md rows 18, 19, 21."""

    async def test_readiness_names_shortfalling_types(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("institute", "person_name"))
        doc_id = await add_document(engine, tenant)
        await _add_spans(engine, tenant, doc_id, "institute", THRESHOLD + 50)
        await _add_spans(engine, tenant, doc_id, "person_name", 40)

        report = await _readiness(client, tenant)

        assert report["threshold_per_entity_type"] == THRESHOLD
        rows = _by_type(report)
        assert rows["institute"]["meets_threshold"] is True
        assert rows["person_name"]["meets_threshold"] is False
        assert rows["person_name"]["count"] == 40
        assert report["shortfalling_entity_types"] == [
            {"entity_type": "person_name", "count": 40}
        ]
        assert report["ready"] is False

    async def test_unannotated_types_are_visible(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("institute", "skill"))
        doc_id = await add_document(engine, tenant)
        await _add_spans(engine, tenant, doc_id, "institute", 10)

        report = await _readiness(client, tenant)

        rows = _by_type(report)
        # A type nobody has annotated is the one most worth naming, and the one an enumeration
        # of `spans` alone would silently omit (ADR-010).
        assert "skill" in rows
        assert rows["skill"]["count"] == 0
        assert rows["skill"]["meets_threshold"] is False

    async def test_readiness_is_per_type_not_total(self, client, engine):
        tenant = await make_tenant(engine, entity_types=("institute", "person_name"))
        doc_id = await add_document(engine, tenant)
        await _add_spans(engine, tenant, doc_id, "institute", 1000)
        await _add_spans(engine, tenant, doc_id, "person_name", 5)

        report = await _readiness(client, tenant)

        rows = _by_type(report)
        assert rows["person_name"]["meets_threshold"] is False
        assert rows["person_name"]["count"] == 5
        # 1005 entities in total, comfortably past any tenant-wide bar, and the report still
        # says not ready. The combined total is not merely unused — it is absent.
        assert report["ready"] is False
        assert "total" not in report
        assert not any("total" in key for key in report)


class TestReadinessIsAdvisory:
    """verification.md row 20."""

    async def test_readiness_does_not_block_submission(
        self, client, training_client, engine, monkeypatch
    ):
        # ADR-010's enforcement knob left inert, which is its default. The readiness check must
        # not become a second gate beside it (design.md Decision 5, verification.md Risk 6).
        monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
        monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "0")

        tenant = await make_tenant(engine, entity_types=("institute", "person_name"))
        async with engine.begin() as conn:
            await conn.execute(text(_AUDIT_EVENTS_SQL))
            await conn.execute(text(_TRAINING_JOBS_SQL.format(schema=tenant["schema"])))
        doc_id = await add_document(engine, tenant)
        await _add_spans(engine, tenant, doc_id, "institute", 12)
        await _add_spans(engine, tenant, doc_id, "person_name", 7)

        report = await _readiness(client, tenant)
        assert len(report["shortfalling_entity_types"]) == 2

        resp = await training_client.post(
            "/api/v1/training-jobs", json={}, headers=auth_header(tenant["tid"])
        )

        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending_approval"
        # And the report says so about itself, so a client cannot read it as a gate by accident.
        assert report["advisory"] is True
        assert report["blocks_submission"] is False
