"""Integration tests for training-jobs API: submission, approval, run_number assignment, status/list."""
import os
import uuid
from types import SimpleNamespace

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
                document_id VARCHAR NOT NULL,
                entity_type VARCHAR(255)
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
        await conn.execute(text("DELETE FROM public.audit_events WHERE tenant_id = :id"), {"id": tid})
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


@pytest_asyncio.fixture
async def client(engine):
    from src.training_service.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def fake_celery_send_task(monkeypatch):
    """Approval enqueues a Celery task; tests don't depend on a live broker."""
    from src.training_service.api.v1 import training_jobs as training_jobs_module

    calls = []

    def _fake_send_task(name, args=None, **kwargs):
        calls.append({"name": name, "args": args})
        return SimpleNamespace(id=f"fake-task-{len(calls)}")

    monkeypatch.setattr(training_jobs_module.celery_app, "send_task", _fake_send_task)
    return calls


VALID_HYPERPARAMS = {"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}


@pytest.mark.asyncio
async def test_submit_valid_job_returns_run_number_and_run_name(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "pending_approval"
    assert data["hyperparams"] is None
    assert "celery_task_id" not in data
    assert data["run_number"] == 1
    assert data["run_name"].startswith("run-001-")


@pytest.mark.asyncio
async def test_submit_insufficient_entities_422(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "500")
    tid, schema = setup_schema
    token = make_token(tid)
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    assert resp.status_code == 422


async def _seed_per_type_spans(engine, tid, schema, counts: dict, define: bool = True):
    """Documents + spans per entity type, and matching active entity
    definitions, so the per-type gate has something to evaluate."""
    async with engine.begin() as conn:
        await conn.execute(
            text(f"INSERT INTO {schema}.documents (id, tenant_id) VALUES ('gate-doc', :tid) ON CONFLICT (id) DO NOTHING"),
            {"tid": tid},
        )
        for entity_type, n in counts.items():
            if define:
                await conn.execute(
                    text(
                        "INSERT INTO public.entity_definitions (id, tenant_id, name, is_active, version) "
                        "VALUES (:id, :tid, :name, true, 1)"
                    ),
                    {"id": str(uuid.uuid4()), "tid": tid, "name": entity_type},
                )
            for _ in range(n):
                await conn.execute(
                    text(f"INSERT INTO {schema}.spans (id, document_id, entity_type) VALUES (:id, 'gate-doc', :et)"),
                    {"id": str(uuid.uuid4()), "et": entity_type},
                )


@pytest.mark.asyncio
async def test_per_type_gate_inert_by_default(client, engine, setup_schema, monkeypatch):
    monkeypatch.delenv("NER_MIN_ENTITIES_PER_TYPE", raising=False)
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    await _seed_per_type_spans(engine, tid, schema, {"ONLY_TYPE": 3})
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_per_type_gate_rejects_short_type_and_names_it(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "200")
    tid, schema = setup_schema
    await _seed_per_type_spans(
        engine, tid, schema,
        {"PROGRAMMING_LANGUAGE": 400, "JOB_TITLE": 210, "CONTACT_DETAILS": 40},
    )
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "CONTACT_DETAILS" in detail and "40" in detail
    assert "PROGRAMMING_LANGUAGE" not in detail
    assert "JOB_TITLE" not in detail


@pytest.mark.asyncio
async def test_per_type_gate_rejects_type_with_zero_spans(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "200")
    tid, schema = setup_schema
    await _seed_per_type_spans(engine, tid, schema, {"SKILL": 200, "EDUCATION": 0})
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "EDUCATION" in detail and "(0)" in detail


@pytest.mark.asyncio
async def test_per_type_gate_accepts_when_all_types_meet_minimum(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "200")
    tid, schema = setup_schema
    await _seed_per_type_spans(engine, tid, schema, {"SKILL": 200, "EDUCATION": 250})
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_per_type_gate_ignores_inactive_types(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "200")
    tid, schema = setup_schema
    await _seed_per_type_spans(engine, tid, schema, {"SKILL": 200})
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.entity_definitions (id, tenant_id, name, is_active, version) "
                "VALUES (:id, :tid, 'LEGACY_FIELD', false, 1)"
            ),
            {"id": str(uuid.uuid4()), "tid": tid},
        )
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_both_gates_apply_independently(client, engine, setup_schema, monkeypatch):
    """900 total spans clears the total-count gate, but one starved type must
    still block submission."""
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "500")
    monkeypatch.setenv("NER_MIN_ENTITIES_PER_TYPE", "200")
    tid, schema = setup_schema
    await _seed_per_type_spans(engine, tid, schema, {"BULK_TYPE": 850, "STARVED": 50})
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(make_token(tid)))
    assert resp.status_code == 422
    assert "per type" in resp.json()["detail"]
    assert "STARVED" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_as_non_admin_403(client, engine, setup_schema):
    tid, schema = setup_schema
    token = make_token(tid, role="annotator")
    resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_submit_with_hyperparameters_is_ignored_or_rejected(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    resp = await client.post("/api/v1/training-jobs", json=VALID_HYPERPARAMS, headers=auth_header(token))
    # TrainingJobCreate forbids extra fields, so a body containing hyperparameters is rejected outright.
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_sequential_run_numbers_per_tenant(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    run_numbers = []
    for _ in range(3):
        resp = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
        assert resp.status_code == 201
        run_numbers.append(resp.json()["run_number"])
    assert run_numbers == [1, 2, 3]


@pytest.mark.asyncio
async def test_run_number_not_reused_after_cancel(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    first = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = first.json()["id"]
    cancel = await client.post(f"/api/v1/training-jobs/{job_id}/cancel", headers=auth_header(token))
    assert cancel.status_code == 200
    second = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    assert second.json()["run_number"] == 2


@pytest.mark.asyncio
async def test_get_status_queued_job(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
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
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
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
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
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
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", headers=auth_header(admin_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_system_admin_get_job_with_wrong_tenant_id_404(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    other_tid = str(uuid.uuid4())
    admin_token = make_token(tid, role="system_admin")
    resp = await client.get(f"/api/v1/training-jobs/{job_id}", params={"tenant_id": other_tid}, headers=auth_header(admin_token))
    assert resp.status_code == 404


# --- Approval (System Admin sets hyperparameters) ---


@pytest.mark.asyncio
async def test_approve_pending_job_with_valid_hyperparameters(client, engine, setup_schema, monkeypatch, fake_celery_send_task):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]
    assert created.json()["hyperparams"] is None

    admin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        json=VALID_HYPERPARAMS,
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "queued"
    assert data["hyperparams"] == VALID_HYPERPARAMS
    assert len(fake_celery_send_task) == 1
    assert fake_celery_send_task[0]["name"] == "fine_tune_model"
    assert fake_celery_send_task[0]["args"] == [tid, job_id, VALID_HYPERPARAMS]


@pytest.mark.asyncio
async def test_approve_without_hyperparameters_422(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_approve_with_invalid_hyperparameters_422(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    body = {**VALID_HYPERPARAMS, "num_epochs": -1}
    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        json=body,
        headers=auth_header(admin_token),
    )
    assert resp.status_code == 422

    # Job remains pending_approval with hyperparams unchanged.
    check = await client.get(f"/api/v1/training-jobs/{job_id}", params={"tenant_id": tid}, headers=auth_header(admin_token))
    assert check.json()["status"] == "pending_approval"
    assert check.json()["hyperparams"] is None


@pytest.mark.asyncio
async def test_approve_job_not_pending_approval_422(client, engine, setup_schema, monkeypatch, fake_celery_send_task):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    admin_token = make_token(tid, role="system_admin")
    first_approve = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        json=VALID_HYPERPARAMS,
        headers=auth_header(admin_token),
    )
    assert first_approve.status_code == 200

    second_approve = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        json=VALID_HYPERPARAMS,
        headers=auth_header(admin_token),
    )
    assert second_approve.status_code == 422


@pytest.mark.asyncio
async def test_approve_as_non_system_admin_403(client, engine, setup_schema, monkeypatch):
    monkeypatch.setenv("NER_MIN_TRAINING_ENTITIES", "0")
    tid, schema = setup_schema
    token = make_token(tid)
    created = await client.post("/api/v1/training-jobs", json={}, headers=auth_header(token))
    job_id = created.json()["id"]

    resp = await client.post(
        f"/api/v1/training-jobs/{job_id}/approve",
        params={"tenant_id": tid},
        json=VALID_HYPERPARAMS,
        headers=auth_header(token),
    )
    assert resp.status_code == 403
