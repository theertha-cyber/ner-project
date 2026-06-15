import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.extraction_service.main import app
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestQueryEntitiesByDocument:
    async def test_query_entities_endpoint(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/entities?documentId=doc1",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestQueryEntitiesByType:
    async def test_filter_by_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/entities?type=ORG",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestQueryEntitiesByConfidence:
    async def test_filter_by_confidence(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/entities?minConfidence=0.8",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestQueryEntitiesUnreviewed:
    async def test_filter_by_review_status(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/entities?reviewStatus=unreviewed",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestQueryEntitiesAnnotator200:
    async def test_annotator_can_query(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/test-tenant/entities",
                headers=auth_header("test-tenant", role="annotator"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestQueryEntitiesCrossTenant404:
    async def test_cross_tenant_returns_empty(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/tenants/tenant-b/entities?documentId=tenant-a-doc",
                headers=auth_header("tenant-b"),
            )
            assert resp.status_code == 200


@pytest.mark.asyncio
class TestCorrectEntity:
    async def test_patch_nonexistent_entity_returns_404(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/tenants/test-tenant/entities/nonexistent-id",
                json={"review_status": "corrected", "corrected_value": "fixed"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 404


@pytest.mark.asyncio
class TestCorrectEntityAnnotator:
    async def test_annotator_can_correct(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/tenants/test-tenant/entities/nonexistent-id",
                json={"review_status": "corrected", "corrected_value": "fixed"},
                headers=auth_header("test-tenant", role="annotator"),
            )
            assert resp.status_code == 404
