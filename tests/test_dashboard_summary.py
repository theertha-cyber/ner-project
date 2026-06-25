import pytest
from httpx import AsyncClient, ASGITransport

from src.shared.auth import create_access_token
from src.gateway.main import app
from src.gateway.api.v1.dashboard import DashboardSummaryResponse, StatItem, ActivityRow, SideMetric, SideRow, DashboardData


def auth_header(tenant_id: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestDashboardSummaryEndpoint:
    async def _get(self, role: str, tenant_id: str = "test-tenant") -> tuple[int, dict]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary", headers=auth_header(tenant_id, role))
            return resp.status_code, resp.json() if resp.text else {}

    async def test_unauthenticated_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401

    async def test_system_admin_returns_correct_shape(self):
        status, body = await self._get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        assert "data" in body
        assert "sources" in body
        d = body["data"]
        assert d["kicker"] == "Platform control plane"
        assert isinstance(d["stats"], list) and len(d["stats"]) == 4
        assert d["pTitle"] == "Approval queue"
        assert isinstance(d["pRows"], list) and len(d["pRows"]) == 4
        assert d["sideTop"] == "Platform health"
        assert isinstance(d["sideMetrics"], list) and len(d["sideMetrics"]) == 3
        assert isinstance(d["sideRows"], list)

    async def test_tenant_admin_returns_correct_shape(self):
        status, body = await self._get("tenant_admin")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Good morning"
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Pipeline activity"
        assert d["sideTop"] == "Active model"

    async def test_annotator_returns_correct_shape(self):
        status, body = await self._get("annotator")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Your annotation queue"
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"

    async def test_business_user_returns_correct_shape(self):
        status, body = await self._get("business_user")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Extraction intelligence"
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Recent extractions"
        assert d["sideTop"] == "Active model"

    async def test_system_admin_tenant_count_is_wired(self):
        status, body = await self._get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        sources = body["sources"]
        assert "tenants" in sources
        assert sources["tenants"] is True

    async def test_response_model_validates_correctly(self):
        status, body = await self._get("tenant_admin")
        assert status == 200
        validated = DashboardSummaryResponse(**body)
        assert isinstance(validated.data, DashboardData)
        assert isinstance(validated.data.stats[0], StatItem)
        assert isinstance(validated.data.pRows[0], ActivityRow)
        assert isinstance(validated.data.sideMetrics[0], SideMetric)
