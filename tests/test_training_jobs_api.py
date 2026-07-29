"""Integration tests for training-jobs API: submission, run_number assignment, status/list."""
import os
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")

from src.shared.config import settings
from src.shared.auth import create_access_token


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_token(tid: str, role: str = "tenant_admin") -> str:
    return create_access_token(tenant_id=tid, user_id="test-user", role=role)


def _create_tables_sql(schema: str) -> list:
    return [
        f"""
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
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR NOT NULL
            )
        """,
    ]


@pytest_asyncio.fixture(scope="function")
async def engine():
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def setup_schema(engine):
    tid = str(uuid.uuid4())
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        for stmt in _create_tables_sql(schema):
            await conn.execute(text(stmt))
        await conn.execute(
            text("INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) VALUES (:id, :name, :slug, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"),
            {"id": tid, "name": "test-tenant", "slug": f"test-{tid[:8]}"},
        )
    yield tid, schema
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest_asyncio.fixture
async def client(engine):
    from src.training_service.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


VALID_HYPERPARAMS = {"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}


@pytest.mark.asyncio
async def test_submit_valid_job_returns_run_number_and_run_name(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    resp = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert "celery_task_id" not in data
    assert data["run_number"] == 1
    assert data["run_name"].startswith("run-001-")


@pytest.mark.asyncio
async def test_submit_insufficient_entities_422(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "500")
    tid, schema = setup_schema
    token = make_token(tid)
    resp = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_as_non_admin_403(client, engine, setup_schema):
    tid, schema = setup_schema
    token = make_token(tid, role="annotator")
    resp = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_submit_invalid_hyperparams_422(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    body = {**VALID_HYPERPARAMS, "num_epochs": -1}
    resp = await client.post("/api/v1/training-jobs", json=body, headers=auth_header(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sequential_run_numbers_per_tenant(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    run_numbers = []
    for _ in range(3):
        resp = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
        assert resp.status_code == 201
        run_numbers.append(resp.json()["run_number"])
    assert run_numbers == [1, 2, 3]


@pytest.mark.asyncio
async def test_run_number_not_reused_after_cancel(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    first = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = first.json()["id"]
    cancel = await client.post(f"/api/v1/training-jobs/{job_id}/cancel", headers=auth_header(token))
    assert cancel.status_code == 200
    second = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    assert second.json()["run_number"] == 2


@pytest.mark.asyncio
async def test_get_status_queued_job(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = created.json()["id"]
    async with engine.begin() as conn:
        await conn.execute(
            text(f"UPDATE {schema}.training_jobs SET status = 'queued' WHERE id = :id"),
            {"id": job_id},
        )
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["run_number"] == 1
    assert data["run_name"] is not None


@pytest.mark.asyncio
async def test_get_job_as_non_owner_tenant_404(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = created.json()["id"]

    other_tid = str(uuid.uuid4())
    other_token = make_token(other_tid)
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(other_token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_system_admin_get_job_with_correct_tenant_id(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", params={"tenant_id": tid}, headers=auth_header(admin_token))
    assert resp.status_code == 200
    assert resp.json()["tenant_id"] == tid


@pytest.mark.asyncio
async def test_system_admin_get_job_without_tenant_id_400(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_system_admin_get_job_with_wrong_tenant_id_404(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    job_id = created.json()["id"]

    other_tid = str(uuid.uuid4())
    admin_token = make_token(tid, role="system_admin")
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", params={"tenant_id": other_tid}, headers=auth_header(admin_token))
    assert resp.status_code == 404
