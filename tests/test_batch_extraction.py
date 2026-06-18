import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")
os.environ.setdefault("NER_MODEL_SERVING_URL", "http://test-model-serving:8004")

from src.extraction_service.main import app
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


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
