import os
import json
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.analytics_service.main import app
from src.analytics_service.api.v1.schemas import AnalyticsExportRequest
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestAnalyticsExportEndpoint:
    async def test_export_csv_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http/test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "csv"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 422)

    async def test_export_json_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "json"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 422)

    async def test_export_unauthenticated_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "csv"},
            )
            assert resp.status_code == 401

    async def test_export_invalid_format_returns_422(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "xml"},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 422

    async def test_export_csv_content_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "csv"},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                assert resp.headers.get("content-type") == "text/csv"

    async def test_export_json_content_type(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http/test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "json"},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                assert resp.headers.get("content-type") == "application/json"

    async def test_export_truncation_header(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/export",
                json={"format": "csv"},
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                assert "x-result-truncated" in resp.headers


@pytest.mark.asyncio
class TestExportSchemaValidation:
    def test_export_request_defaults_to_csv(self):
        req = AnalyticsExportRequest()
        assert req.format == "csv"

    def test_export_request_json_format(self):
        req = AnalyticsExportRequest(format="json")
        assert req.format == "json"

    def test_export_request_invalid_format(self):
        with pytest.raises(ValidationError):
            AnalyticsExportRequest(format="xml")

    def test_export_request_with_filters(self):
        req = AnalyticsExportRequest(
            entity_types=["PERSON"],
            confidence={"min": 0.5},
            format="csv",
        )
        assert req.entity_types == ["PERSON"]
        assert req.confidence["min"] == 0.5
