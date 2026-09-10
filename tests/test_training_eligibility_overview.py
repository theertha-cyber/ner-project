"""training-eligibility-overview — per-source accumulation split + eligible-units overview
on the retraining decision surface. Report only.
"""

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.annotation_service.main import app
from src.shared.config import settings
from tests.retraining_support import (
    add_document,
    add_model_version,
    add_run,
    auth_header,
    drop_test_schemas,
    make_tenant,
    review_spans,
)


@pytest.fixture
async def engine():
    eng = create_async_engine(settings.database_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest.fixture(autouse=True)
async def cleanup(engine):
    yield
    await drop_test_schemas(engine)


def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _decision(tenant) -> dict:
    async with _client() as client:
        resp = await client.get(
            "/api/v1/retraining-decision", headers=auth_header(tenant["tid"])
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _exec(engine, tenant, sql, params=None):
    async with engine.begin() as conn:
        await conn.execute(text(sql.format(schema=tenant["schema"])), params or {})


@pytest.mark.asyncio
async def test_by_source_sums_to_accumulation(engine):
    tenant = await make_tenant(engine)
    doc_id = await add_document(engine, tenant)
    run_id = await add_run(engine, tenant, doc_id, model_version="3")
    await add_model_version(engine, tenant, 3, status="promoted")
    await review_spans(_client, engine, tenant, doc_id, run_id, 5)

    decision = await _decision(tenant)
    by_source = decision["by_source"]
    assert by_source["manual"] + by_source["automated"] == decision["spans_accumulated"]
    assert by_source["manual"] == 5  # review_spans produces workspace/review spans


@pytest.mark.asyncio
async def test_eligible_overview_counts_per_source(engine):
    tenant = await make_tenant(engine)
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.annotation_tasks (id, status, training_eligible_at) "
        "VALUES (:a, 'completed', NOW()), (:b, 'completed', NOW())",
        {"a": str(uuid.uuid4()), "b": str(uuid.uuid4())},
    )
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.prelabel_batches (id, status, annotator_review_status, training_eligible_at) "
        "VALUES (:x, 'completed', 'approved', NOW())",
        {"x": str(uuid.uuid4())},
    )
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.annotation_imports (source_file, training_eligible_at) "
        "VALUES ('a.jsonl', NOW()), ('b.jsonl', NOW()), ('c.jsonl', NOW())",
    )

    overview = (await _decision(tenant))["eligible_overview"]
    assert overview["manual"]["count"] == 2
    assert overview["automated"]["count"] == 1
    assert overview["import"]["count"] == 3
    assert overview["manual"]["latest_at"] is not None


@pytest.mark.asyncio
async def test_consumed_units_drop_off_overview(engine):
    tenant = await make_tenant(engine)
    # A completed training run 'now'; a task eligible one hour earlier is already consumed.
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.training_jobs (id, tenant_id, status, completed_at) "
        "VALUES (:j, :t, 'completed', NOW())",
        {"j": str(uuid.uuid4()), "t": tenant["tid"]},
    )
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.annotation_tasks (id, status, training_eligible_at) "
        "VALUES (:a, 'completed', NOW() - INTERVAL '1 hour')",
        {"a": str(uuid.uuid4())},
    )

    overview = (await _decision(tenant))["eligible_overview"]
    assert overview["manual"]["count"] == 0


@pytest.mark.asyncio
async def test_overview_is_report_only(engine):
    tenant = await make_tenant(engine)
    await _exec(
        engine, tenant,
        "INSERT INTO {schema}.annotation_imports (source_file, training_eligible_at) VALUES ('x.jsonl', NOW())",
    )
    await _decision(tenant)
    await _decision(tenant)

    async with engine.connect() as conn:
        jobs = (
            await conn.execute(text(f"SELECT COUNT(*) FROM {tenant['schema']}.training_jobs"))
        ).scalar()
    assert jobs == 0
