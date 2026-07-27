import logging

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from src.shared.auth import create_access_token
from src.gateway.main import app

SYSTEM_ADMIN_USER = "00000000-0000-0000-0000-000000000000"


def auth_header(tenant_id: str, role: str = "system_admin", user_id: str = SYSTEM_ADMIN_USER) -> dict:
    token = create_access_token(tenant_id=tenant_id, user_id=user_id, role=role)
    return {"Authorization": f"Bearer {token}"}


async def _get_system_admin() -> tuple[int, dict]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/dashboard/summary",
            headers=auth_header(SYSTEM_ADMIN_USER, "system_admin", SYSTEM_ADMIN_USER),
        )
        return resp.status_code, resp.json() if resp.text else {}


async def _insert_tenant(engine, tenant_id: str, name: str | None = None):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                "VALUES (:id, :name, :slug, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tenant_id, "name": name or tenant_id, "slug": tenant_id},
        )


async def _delete_tenant(engine, tenant_id: str):
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tenant_id})


@pytest.mark.asyncio
class TestDashboardTenantEnumeration:
    async def test_system_tenant_excluded_from_iteration(self, engine, setup_database, caplog):
        await _insert_tenant(engine, "system", "System")
        try:
            with caplog.at_level(logging.ERROR):
                status, body = await _get_system_admin()
            assert status == 200
            assert "tenant_system" not in caplog.text
        finally:
            await _delete_tenant(engine, "system")

    async def test_schemaless_tenants_excluded_from_aggregates(self, engine, setup_database, caplog):
        ghost_id = "ghost-tenant-no-schema"
        await _insert_tenant(engine, ghost_id, "Ghost Tenant")
        try:
            with caplog.at_level(logging.ERROR):
                status, body = await _get_system_admin()
            assert status == 200
            assert f"tenant_{ghost_id.replace('-', '_')}" not in caplog.text
        finally:
            await _delete_tenant(engine, ghost_id)

    async def test_partial_aggregate_marks_source_false(self, engine, setup_database):
        empty_id = "empty-schema-tenant"
        empty_schema = f"tenant_{empty_id.replace('-', '_')}"
        await _insert_tenant(engine, empty_id, "Empty Schema Tenant")
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {empty_schema}"))
        try:
            status, body = await _get_system_admin()
            assert status == 200
            assert body["sources"]["documents"] is False
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {empty_schema} CASCADE"))
            await _delete_tenant(engine, empty_id)

    async def test_one_schema_failure_preserves_other_tenants(self, engine, setup_database):
        bad_id = "bad-schema-tenant"
        bad_schema = f"tenant_{bad_id.replace('-', '_')}"
        healthy_id = "healthy-schema-tenant-2"
        healthy_schema = f"tenant_{healthy_id.replace('-', '_')}"

        await _insert_tenant(engine, bad_id, "Bad Schema Tenant")
        await _insert_tenant(engine, healthy_id, "Healthy Schema Tenant 2")

        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {bad_schema}"))

            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {healthy_schema}"))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {healthy_schema}.training_jobs (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'queued',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {healthy_schema}.model_versions (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    version INTEGER NOT NULL,
                    metrics JSONB,
                    status VARCHAR(20) DEFAULT 'candidate',
                    promoted_at TIMESTAMPTZ
                )
            """))
            await conn.execute(
                text(f"""
                    INSERT INTO {healthy_schema}.training_jobs (id, tenant_id, status, created_at)
                    VALUES ('tj-enum-1', :tid, 'pending_approval', NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"tid": healthy_id},
            )
            await conn.execute(
                text(f"""
                    INSERT INTO {healthy_schema}.model_versions (id, tenant_id, version, metrics, status, promoted_at)
                    VALUES ('mv-enum-1', :tid, 1, :met, 'promoted', NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                {"tid": healthy_id, "met": '{"f1": 0.75}'},
            )

        try:
            status, body = await _get_system_admin()
            assert status == 200
            s = body["data"]["stats"]
            assert s[2]["value"] == "1"
            assert s[3]["value"] == "75.0"
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {bad_schema} CASCADE"))
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {healthy_schema} CASCADE"))
            await _delete_tenant(engine, bad_id)
            await _delete_tenant(engine, healthy_id)
