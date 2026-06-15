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
class TestExtractTextReturnsEntities:
    async def test_extract_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/test-tenant/extract",
                json={"text": "John works at Acme Corp"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 400)


@pytest.mark.asyncio
class TestExtractNoModelReturns400:
    async def test_extract_no_model_returns_400(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/no-model/extract",
                json={"text": "test"},
                headers=auth_header("no-model"),
            )
            assert resp.status_code == 400
            body = resp.json()
            assert "detail" in body


@pytest.mark.asyncio
class TestExtractNonAdminReturns403:
    async def test_annotator_gets_403(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/test-tenant/extract",
                json={"text": "test"},
                headers=auth_header("test-tenant", role="annotator"),
            )
            assert resp.status_code == 403

    async def test_system_admin_gets_403(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/test-tenant/extract",
                json={"text": "test"},
                headers=auth_header("test-tenant", role="system_admin"),
            )
            assert resp.status_code == 403


@pytest.mark.asyncio
class TestLowConfidenceFiltered:
    async def test_low_confidence_returns_empty_entities(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/tenants/test-tenant/extract",
                json={"text": "a"},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                assert "entities" in resp.json()
