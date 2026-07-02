import os
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
async def isolated_tenant_schemas():
    """Provisions fresh tenant_<id>.extraction_runs tables for arbitrary tenant ids
    not part of the fixed baseline set created by scripts/setup_test_db.py."""
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
                    failed_count INTEGER NOT NULL DEFAULT 0
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


@pytest.mark.asyncio
class TestTriggerBatchReturns202:
    async def test_trigger_batch_endpoint_returns_202(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1,doc2",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 202
            body = resp.json()
            assert "run_id" in body
            assert body["status"] == "queued"


@pytest.mark.asyncio
class TestBatchQueuedRunIsQueryable:
    async def test_get_run_returns_queued_after_post(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            post_resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1",
                headers=auth_header("test-tenant"),
            )
            assert post_resp.status_code == 202
            run_id = post_resp.json()["run_id"]

            get_resp = await client.get(
                f"/api/v1/extract-batch/{run_id}",
                headers=auth_header("test-tenant"),
            )
            assert get_resp.status_code == 200
            body = get_resp.json()
            assert body["status"] == "queued"
            assert body["total_documents"] == 1
            assert body["processed_count"] == 0
            assert body["skipped_count"] == 0
            assert body["failed_count"] == 0


@pytest.mark.asyncio
class TestBatchNoModelReturns202:
    async def test_batch_no_model_still_returns_202(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/extract-batch?documentIds=doc1",
                headers=auth_header("no-model"),
            )
            assert resp.status_code == 202
            body = resp.json()
            assert body["status"] == "queued"


@pytest.mark.asyncio
class TestGetRunStatusNotFound:
    async def test_get_nonexistent_run_returns_404(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/extract-batch/nonexistent-run-id",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestListBatchRuns:
    async def test_list_batch_runs_returns_all_fields(self, isolated_tenant_schemas):
        tid = "list-fields-tenant"
        await isolated_tenant_schemas(tid)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = auth_header(tid)
            run_ids = set()
            for _ in range(3):
                post_resp = await client.post(
                    "/api/v1/extract-batch?documentIds=doc1",
                    headers=headers,
                )
                assert post_resp.status_code == 202
                run_ids.add(post_resp.json()["run_id"])

            list_resp = await client.get("/api/v1/extract-batch", headers=headers)
            assert list_resp.status_code == 200
            body = list_resp.json()
            assert "runs" in body
            listed_ids = {r["run_id"] for r in body["runs"]}
            assert run_ids.issubset(listed_ids)
            for run in body["runs"]:
                for field in (
                    "run_id",
                    "status",
                    "total_documents",
                    "processed_count",
                    "skipped_count",
                    "failed_count",
                    "started_at",
                    "completed_at",
                    "model_version",
                ):
                    assert field in run

    async def test_list_batch_runs_ordered_desc(self, isolated_tenant_schemas):
        tid = "list-order-tenant"
        await isolated_tenant_schemas(tid)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            headers = auth_header(tid)
            run_ids = []
            for _ in range(3):
                post_resp = await client.post(
                    "/api/v1/extract-batch?documentIds=doc1",
                    headers=headers,
                )
                run_ids.append(post_resp.json()["run_id"])

            list_resp = await client.get("/api/v1/extract-batch", headers=headers)
            assert list_resp.status_code == 200
            started_ats = [r["started_at"] for r in list_resp.json()["runs"]]
            assert started_ats == sorted(started_ats, reverse=True)

    async def test_list_batch_runs_tenant_isolated(self, isolated_tenant_schemas):
        tenant_a = "isolation-tenant-a"
        tenant_b = "isolation-tenant-b"
        await isolated_tenant_schemas(tenant_a)
        await isolated_tenant_schemas(tenant_b)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/extract-batch?documentIds=doc1",
                headers=auth_header(tenant_a),
            )

            list_resp = await client.get(
                "/api/v1/extract-batch", headers=auth_header(tenant_b)
            )
            assert list_resp.status_code == 200
            assert list_resp.json()["runs"] == []

    async def test_list_batch_runs_empty_for_new_tenant(self, isolated_tenant_schemas):
        tid = "fresh-tenant"
        await isolated_tenant_schemas(tid)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get(
                "/api/v1/extract-batch", headers=auth_header(tid)
            )
            assert list_resp.status_code == 200
            assert list_resp.json()["runs"] == []

    async def test_list_batch_runs_business_user_allowed(self, isolated_tenant_schemas):
        tid = "business-user-tenant"
        await isolated_tenant_schemas(tid)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            list_resp = await client.get(
                "/api/v1/extract-batch",
                headers=auth_header(tid, role="business_user"),
            )
            assert list_resp.status_code == 200
