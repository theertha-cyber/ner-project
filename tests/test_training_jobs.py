import os
import uuid
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone

os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_DATABASE_URL_SYNC", "postgresql://ner:ner@localhost:5432/ner_test")
os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_MIN_TRAINING_ENTITIES", "500")

from src.shared.config import settings
from src.shared.auth import create_access_token
from src.training_service.main import app


@pytest.fixture(autouse=True)
def mock_celery(monkeypatch):
    mock_task = MagicMock()
    mock_task.id = str(uuid.uuid4())
    mock_control = MagicMock()
    send_task_calls = []

    def _send_task(name, args=None, kwargs=None, **kw):
        send_task_calls.append((name, args, kwargs))
        return mock_task

    monkeypatch.setattr("src.training_service.api.v1.training_jobs.celery_app.send_task", _send_task)
    monkeypatch.setattr("src.training_service.api.v1.training_jobs.celery_app.control", mock_control)
    return send_task_calls


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
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                hyperparams JSONB NOT NULL DEFAULT '{{}}',
                current_epoch INTEGER,
                current_loss FLOAT,
                metrics JSONB,
                error_message TEXT,
                model_version_id VARCHAR,
                celery_task_id VARCHAR,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                failed_at TIMESTAMPTZ
            )
        """,
        f"""
            CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant_status
                ON {schema}.training_jobs (tenant_id, status)
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.spans (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                entity_type VARCHAR(255) NOT NULL
            )
        """,
        f"""
            CREATE TABLE IF NOT EXISTS {schema}.documents (
                id VARCHAR PRIMARY KEY
            )
        """,
    ]


async def _seed_spans(engine, schema: str, entity_count: int = 500):
    doc_rows = []
    span_rows = []
    for i in range(entity_count):
        doc_id = str(uuid.uuid4())
        doc_rows.append(f"('{doc_id}')")
        span_rows.append(f"('{str(uuid.uuid4())}', '{doc_id}', 'PER')")
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id) VALUES {', '.join(doc_rows)}"),
        )
        await conn.execute(
            text(f"INSERT INTO {schema}.spans (id, document_id, entity_type) VALUES {', '.join(span_rows)}"),
        )


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
    async with engine.begin() as conn:
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_submit_valid(client, setup_schema, engine, mock_celery):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    token = make_token(tid)
    resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(token),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert "id" in data
    assert data.get("celery_task_id") is None
    assert len(mock_celery) == 0


@pytest.mark.asyncio
async def test_submit_insufficient_entities(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 10)
    token = make_token(tid)
    resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_submit_non_admin(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    token = make_token(tid, role="annotator")
    resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_submit_invalid_hyperparams(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    token = make_token(tid)
    resp = await client.post(
        "/api/v1/training-jobs",
        json={"num_epochs": -1},
        headers=auth_header(token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_status_pending_approval(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(token),
    )
    job_id = create_resp.json()["id"]
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_approval"


@pytest.mark.asyncio
async def test_status_running(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs
                    (id, tenant_id, status, hyperparams, current_epoch, current_loss, started_at, created_at)
                VALUES (:id, :tid, 'running', '{{}}'::jsonb, 2, 0.35, :now, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    token = make_token(tid)
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "running"
    assert data["current_epoch"] == 2
    assert data["current_loss"] == 0.35


@pytest.mark.asyncio
async def test_status_completed(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, metrics, created_at, completed_at)
                VALUES (:id, :tid, 'completed', '{{}}'::jsonb, '{{"eval_f1": 0.85}}'::jsonb, :now, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    token = make_token(tid)
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert resp.json()["metrics"]["eval_f1"] == 0.85


@pytest.mark.asyncio
async def test_status_failed(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, error_message, created_at, failed_at)
                VALUES (:id, :tid, 'failed', '{{}}'::jsonb, 'OOM error', :now, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    token = make_token(tid)
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "failed"
    assert resp.json()["error_message"] == "OOM error"


@pytest.mark.asyncio
async def test_status_cross_tenant_404(client, setup_schema, engine):
    tid_a, schema_a = setup_schema
    tid_b = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema_a}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                VALUES (:id, :tid, 'queued', '{{}}'::jsonb, :now)
            """),
            {"id": job_id, "tid": tid_a, "now": datetime.now(timezone.utc)},
        )
    token_b = make_token(tid_b)
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(token_b))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_filter_by_status(client, setup_schema, engine):
    tid, schema = setup_schema
    job_ids = [str(uuid.uuid4()) for _ in range(3)]
    statuses = ["running", "completed", "running"]
    async with engine.begin() as conn:
        for jid, st in zip(job_ids, statuses):
            await conn.execute(
                text(f"""
                    INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                    VALUES (:id, :tid, :st, '{{}}'::jsonb, :now)
                """),
                {"id": jid, "tid": tid, "st": st, "now": datetime.now(timezone.utc)},
            )
    token = make_token(tid)
    resp = await client.get("/api/v1/training-jobs?status=running", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


@pytest.mark.asyncio
async def test_list_pagination(client, setup_schema, engine):
    tid, schema = setup_schema
    async with engine.begin() as conn:
        for i in range(5):
            await conn.execute(
                text(f"""
                    INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                    VALUES (:id, :tid, 'queued', '{{}}'::jsonb, :now)
                """),
                {"id": str(uuid.uuid4()), "tid": tid, "now": datetime.now(timezone.utc)},
            )
    token = make_token(tid)
    resp = await client.get("/api/v1/training-jobs?page=1&per_page=3", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["per_page"] == 3


@pytest.mark.asyncio
async def test_cancel_pending_approval(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(token),
    )
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_approval"
    resp = await client.post(f"/api/v1/training-jobs/{job_id}/cancel", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_completed_422(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                VALUES (:id, :tid, 'completed', '{{}}'::jsonb, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    token = make_token(tid)
    resp = await client.post(f"/api/v1/training-jobs/{job_id}/cancel", headers=auth_header(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approve_pending_job(client, setup_schema, engine, mock_celery):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    tenant_token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(tenant_token),
    )
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_approval"

    sysadmin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tid}",
        headers=auth_header(sysadmin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "queued"
    assert len(mock_celery) == 1


@pytest.mark.asyncio
async def test_approve_non_pending(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                VALUES (:id, :tid, 'queued', '{{}}'::jsonb, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    sysadmin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tid}",
        headers=auth_header(sysadmin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approve_as_tenant_admin(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    tenant_token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(tenant_token),
    )
    job_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve?tenant_id={tid}",
        headers=auth_header(tenant_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_reject_pending_job(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    tenant_token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(tenant_token),
    )
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_approval"

    sysadmin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tid}",
        json={"reason": "GPU cluster at capacity"},
        headers=auth_header(sysadmin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["error_message"] == "GPU cluster at capacity"


@pytest.mark.asyncio
async def test_reject_pending_job_no_reason(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    tenant_token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(tenant_token),
    )
    job_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == "pending_approval"

    sysadmin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tid}",
        json={},
        headers=auth_header(sysadmin_token),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["error_message"] is None


@pytest.mark.asyncio
async def test_reject_non_pending(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, created_at)
                VALUES (:id, :tid, 'completed', '{{}}'::jsonb, :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    sysadmin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tid}",
        json={},
        headers=auth_header(sysadmin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_reject_as_tenant_admin(client, setup_schema, engine):
    tid, schema = setup_schema
    await _seed_spans(engine, schema, 500)
    tenant_token = make_token(tid)
    create_resp = await client.post(
        "/api/v1/training-jobs",
        json={"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128},
        headers=auth_header(tenant_token),
    )
    job_id = create_resp.json()["id"]
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/reject?tenant_id={tid}",
        json={},
        headers=auth_header(tenant_token),
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_cancel_queued(client, setup_schema, engine):
    tid, schema = setup_schema
    job_id = str(uuid.uuid4())
    async with engine.begin() as conn:
        await conn.execute(
            text(f"""
                INSERT INTO {schema}.training_jobs (id, tenant_id, status, hyperparams, celery_task_id, created_at)
                VALUES (:id, :tid, 'queued', '{{}}'::jsonb, 'mock-task-id', :now)
            """),
            {"id": job_id, "tid": tid, "now": datetime.now(timezone.utc)},
        )
    token = make_token(tid)
    resp = await client.post(f"/api/v1/training-jobs/{job_id}/cancel", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"
