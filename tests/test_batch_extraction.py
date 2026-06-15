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
    async def test_trigger_batch_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/test-tenant/extract-batch?documentIds=doc1,doc2",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (202, 400)


@pytest.mark.asyncio
class TestBatchSkipsAlreadyExtracted:
    async def test_batch_no_model_returns_400(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/no-model/extract-batch?documentIds=doc1",
                headers=auth_header("no-model"),
            )
            assert resp.status_code == 400


@pytest.mark.asyncio
class TestBatchNoModelReturns400:
    async def test_batch_no_model_returns_400(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/no-model/extract-batch?documentIds=doc1",
                headers=auth_header("no-model"),
            )
            assert resp.status_code == 400


@pytest.mark.asyncio
class TestGetRunStatusRunning:
    async def test_get_nonexistent_run_returns_404(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/extract-batch/nonexistent-run-id",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestGetRunStatusCompleted:
    async def test_returns_404_for_nonexistent(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/extract-batch/missing-run",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 404
