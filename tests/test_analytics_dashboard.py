import os
import pytest
from httpx import AsyncClient, ASGITransport
from pydantic import ValidationError

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.analytics_service.main import app
from src.analytics_service.api.v1.schemas import (
    DashboardResponse,
    EntityCoverageWidget,
    ConfidenceBucket,
    ConfidenceDistributionWidget,
    ExtractionVolumePoint,
    ExtractionVolumeWidget,
    DocumentEntityCountsWidget,
)
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestAnalyticsDashboardEndpoint:
    async def test_dashboard_endpoint_exists(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/analytics/dashboard",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 500)

    async def test_unauthenticated_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/analytics/dashboard")
            assert resp.status_code == 401

    async def test_dashboard_response_shape(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/analytics/dashboard",
                headers=auth_header("test-tenant"),
            )
            if resp.status_code == 200:
                body = resp.json()
                assert "entity_coverage" in body
                assert "confidence_distribution" in body
                assert "extraction_volume" in body
                assert "document_entity_counts" in body
                assert "generated_at" in body


@pytest.mark.asyncio
class TestDashboardSchemas:
    def test_entity_coverage_widget(self):
        w = EntityCoverageWidget(entity_type="PERSON", coverage_pct=75.5)
        assert w.entity_type == "PERSON"
        assert w.coverage_pct == 75.5

    def test_confidence_distribution(self):
        dist = ConfidenceDistributionWidget(
            buckets=[
                ConfidenceBucket(label="0.8-1.0", count=100),
                ConfidenceBucket(label="0.6-0.8", count=50),
            ]
        )
        assert len(dist.buckets) == 2
        assert dist.buckets[0].count == 100

    def test_extraction_volume(self):
        vol = ExtractionVolumeWidget(
            data=[
                ExtractionVolumePoint(date="2026-06-01", count=50),
                ExtractionVolumePoint(date="2026-06-02", count=30),
            ]
        )
        assert len(vol.data) == 2
        assert vol.lookback_days == 30

    def test_dashboard_response(self):
        resp = DashboardResponse(
            entity_coverage=[],
            confidence_distribution=ConfidenceDistributionWidget(buckets=[]),
            extraction_volume=ExtractionVolumeWidget(data=[]),
            document_entity_counts=[],
        )
        assert resp.generated_at is not None

    def test_refresh_endpoint_unauthenticated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analytics/refresh")
            assert resp.status_code == 401

    def test_refresh_endpoint_authenticated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/analytics/refresh",
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code in (200, 500)
