import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app


def auth_header(tenant_id: str, role: str = "tenant_admin", user_id: str = "test-user") -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _get(role: str, tenant_id: str = "test-tenant", user_id: str = "test-user") -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/dashboard/summary", headers=auth_header(tenant_id, role, user_id))
        return resp.status_code, resp.json() if resp.text else {}


@pytest.mark.asyncio
class TestDashboardSummaryRoles:
    async def test_system_admin_summary_returns_role_specific_data(self, engine, setup_database):
        status, body = await _get("system_admin", "00000000-0000-0000-0000-000000000000")
        assert status == 200
        d = body["data"]
        assert d["kicker"] == "Platform control plane"
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Approval queue"
        assert len(d["pRows"]) == 4
        assert d["sideTop"] == "Platform health"

    async def test_tenant_admin_summary_returns_pipeline_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Pipeline activity"
        assert len(d["pRows"]) == 4
        assert d["sideTop"] == "Active model"

    async def test_annotator_summary_returns_task_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("annotator", tid)
        assert status == 200
        d = body["data"]
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "My tasks"
        assert d["sideTop"] == "Dataset readiness"

    async def test_business_user_summary_returns_extraction_data(self, engine, tenant_schema):
        tid, _schema = tenant_schema
        status, body = await _get("business_user", tid)
        assert status == 200
        d = body["data"]
        assert len(d["stats"]) == 4
        assert d["pTitle"] == "Recent extractions"
        assert d["sideTop"] == "Active model"

    async def test_unavailable_training_service_returns_null_values(self, engine, tenant_schema):
        tid, schema = tenant_schema
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP TABLE IF EXISTS {schema}.training_jobs CASCADE"))

        status, body = await _get("tenant_admin", tid)
        assert status == 200
        d = body["data"]
        training_stat = d["stats"][3]
        assert training_stat["value"] is None
        assert body["sources"]["training"] is False

    async def test_unauthenticated_request_rejected(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/dashboard/summary")
        assert resp.status_code == 401
