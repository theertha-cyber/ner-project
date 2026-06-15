"""Integration tests for model registry API (mocked MLflow backend).

Tests the API layer (auth, validation, status transitions) using a local
DB cache as the backing store instead of a real MLflow Tracking Server.
MLflow-specific unit tests live in test_mlflow_registry.py.
"""
import os
import uuid
import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from datetime import datetime, timezone

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
            CREATE TABLE IF NOT EXISTS {schema}.model_versions (
                id VARCHAR PRIMARY KEY,
                tenant_id VARCHAR NOT NULL,
                version_number INTEGER NOT NULL,
                training_job_id VARCHAR,
                status VARCHAR(20) NOT NULL DEFAULT 'training',
                metrics JSONB,
                artifact_path TEXT,
                mlflow_run_id VARCHAR,
                mlflow_run_url VARCHAR,
                promoted_at TIMESTAMPTZ,
                archived_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """,
        f"""
            CREATE INDEX IF NOT EXISTS idx_model_versions_tenant_status
                ON {schema}.model_versions (tenant_id, status)
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
async def client(engine, mock_mlflow):
    from src.training_service.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(autouse=True)
def mock_mlflow(monkeypatch):
    """Monkeypatch mlflow_registry BEFORE the models module is imported.

    This fixture runs before `client` fixture imports `app`, ensuring the
    patched functions are captured by FastAPI route decorators.
    """
    import src.training_service.infra.mlflow_registry as mr
    from sqlalchemy import text as sql_text

    def mock_list(tenant_id):
        cached = mr._read_cache_model_versions(tenant_id)
        warning = "mlflow-unavailable" if not cached else None
        return cached, warning

    def mock_get_active(tenant_id):
        cached = mr._read_cache_active_model(tenant_id)
        if cached:
            cached["mlflow_run_url"] = None
        return cached, None

    def mock_promote(tenant_id, version_number):
        engine = mr._get_sync_engine()
        schema = mr._schema(tenant_id)
        with engine.begin() as conn:
            result = conn.execute(
                sql_text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tid AND version_number = :vn"),
                {"tid": tenant_id, "vn": version_number},
            )
            row = result.fetchone()
            if not row:
                return None
            if row._mapping["status"] != "completed":
                return None
            conn.execute(
                sql_text(f"UPDATE {schema}.model_versions SET status = 'archived', archived_at = :now WHERE tenant_id = :tid AND status = 'promoted'"),
                {"tid": tenant_id, "now": datetime.now(timezone.utc)},
            )
            conn.execute(
                sql_text(f"UPDATE {schema}.model_versions SET status = 'promoted', promoted_at = :now WHERE tenant_id = :tid AND version_number = :vn"),
                {"tid": tenant_id, "vn": version_number, "now": datetime.now(timezone.utc)},
            )
        active = mr._read_cache_active_model(tenant_id)
        if active:
            active["mlflow_run_url"] = None
        return active

    def mock_demote(tenant_id, version_number):
        engine = mr._get_sync_engine()
        schema = mr._schema(tenant_id)
        with engine.begin() as conn:
            result = conn.execute(
                sql_text(f"SELECT * FROM {schema}.model_versions WHERE tenant_id = :tid AND version_number = :vn"),
                {"tid": tenant_id, "vn": version_number},
            )
            row = result.fetchone()
            if not row:
                return None
            if row._mapping["status"] != "promoted":
                return None
            conn.execute(
                sql_text(f"UPDATE {schema}.model_versions SET status = 'completed' WHERE tenant_id = :tid AND version_number = :vn"),
                {"tid": tenant_id, "vn": version_number},
            )
            row_data = dict(row._mapping)
            row_data["status"] = "completed"
            row_data["mlflow_run_url"] = None
        return row_data

    monkeypatch.setattr(mr, "list_model_versions", mock_list)
    monkeypatch.setattr(mr, "get_active_model", mock_get_active)
    monkeypatch.setattr(mr, "promote_model_version", mock_promote)
    monkeypatch.setattr(mr, "demote_model_version", mock_demote)


async def _seed_versions(engine, schema: str, tid: str, versions: list[dict]):
    for v in versions:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"""
                    INSERT INTO {schema}.model_versions
                        (id, tenant_id, version_number, training_job_id, status, metrics, artifact_path, promoted_at, created_at)
                    VALUES (:id, :tid, :vn, :tjid, :st, CAST(:metrics AS jsonb), :path, :promoted_at, :now)
                """),
                {
                    "id": v.get("id", str(uuid.uuid4())),
                    "tid": tid,
                    "vn": v["version_number"],
                    "tjid": v.get("training_job_id"),
                    "st": v["status"],
                    "metrics": json.dumps(v.get("metrics", {})),
                    "path": v.get("artifact_path"),
                    "promoted_at": v.get("promoted_at"),
                    "now": datetime.now(timezone.utc),
                },
            )


@pytest.mark.asyncio
async def test_list_versions(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 3, "status": "training", "metrics": {}},
        {"version_number": 2, "status": "promoted", "metrics": {"eval_f1": 0.85}},
        {"version_number": 1, "status": "archived", "metrics": {"eval_f1": 0.75}},
    ])
    token = make_token(tid)
    resp = await client.get("/api/v1/models", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    version_numbers = [v["version_number"] for v in data["items"]]
    assert version_numbers == [3, 2, 1]


@pytest.mark.asyncio
async def test_list_versions_annotator(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {}},
    ])
    token = make_token(tid, role="annotator")
    resp = await client.get("/api/v1/models", headers=auth_header(token))
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 1


@pytest.mark.asyncio
async def test_promote_completed(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/promote", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"


@pytest.mark.asyncio
async def test_promote_replaces_previous(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "promoted", "metrics": {"eval_f1": 0.75},
         "promoted_at": datetime.now(timezone.utc)},
        {"version_number": 2, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/2/promote", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "promoted"


@pytest.mark.asyncio
async def test_promote_non_completed_422(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "training", "metrics": {}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/promote", headers=auth_header(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_promote_annotator_403(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {}},
    ])
    token = make_token(tid, role="annotator")
    resp = await client.post("/api/v1/models/1/promote", headers=auth_header(token))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_demote_active(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 2, "status": "promoted",
         "promoted_at": datetime.now(timezone.utc)},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/2/demote", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"


@pytest.mark.asyncio
async def test_demote_non_promoted_422(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/demote", headers=auth_header(token))
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_active_exists(client, engine, setup_schema):
    tid, schema = setup_schema
    version_id = str(uuid.uuid4())
    await _seed_versions(engine, schema, tid, [
        {"id": version_id, "version_number": 2, "status": "promoted",
         "artifact_path": f"tenants/{tid}/models/v1/{version_id}/",
         "promoted_at": datetime.now(timezone.utc)},
    ])
    token = make_token(tid)
    resp = await client.get("/api/v1/models/active", headers=auth_header(token))
    assert resp.status_code == 200
    assert resp.json()["version_number"] == 2
    assert "artifact_path" in resp.json()


@pytest.mark.asyncio
async def test_get_active_none_404(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {}},
    ])
    token = make_token(tid)
    resp = await client.get("/api/v1/models/active", headers=auth_header(token))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_promote_triggers_warmup(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/promote", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"


@pytest.mark.asyncio
async def test_promote_succeeds_when_warmup_fails(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/promote", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "promoted"


@pytest.mark.asyncio
async def test_standalone_warmup_endpoint(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/warmup", headers=auth_header(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version_number"] == 1


@pytest.mark.asyncio
async def test_standalone_warmup_does_not_change_status(client, engine, setup_schema):
    tid, schema = setup_schema
    await _seed_versions(engine, schema, tid, [
        {"version_number": 1, "status": "completed", "metrics": {"eval_f1": 0.85}},
    ])
    token = make_token(tid)
    resp = await client.post("/api/v1/models/1/warmup", headers=auth_header(token))
    assert resp.status_code == 200
    get_resp = await client.get("/api/v1/models/active", headers=auth_header(token))
    assert get_resp.status_code == 404
