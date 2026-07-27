import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from src.gateway.services.tenant_service import TenantService
from src.document_service.main import app as document_service_app
from src.shared.auth import create_access_token
from src.shared.config import settings


@pytest.mark.asyncio
class TestTenantProvisioningAtomicity:
    async def test_failed_table_clone_rolls_back_tenant(self, engine, setup_database, monkeypatch):
        # Force a deterministic tenant_id so the target schema/table name is
        # known ahead of time, then pre-create one of tenant_template's tables
        # inside that schema. The service's per-table CREATE TABLE has no IF NOT
        # EXISTS, so cloning that table fails partway through the loop.
        #
        # This must run on a session with real (non-autocommit) transaction
        # semantics — the `engine` fixture used elsewhere in this suite is
        # opened with isolation_level="AUTOCOMMIT" so every statement commits
        # immediately, which would make a rollback assertion meaningless. Build
        # a session the same way the production `get_db` dependency does.
        fixed_tenant_id = "11111111-2222-3333-4444-555555555555"
        schema_name = f"tenant_{fixed_tenant_id}".replace("-", "_")

        import src.gateway.services.tenant_service as tenant_service_module
        id_calls = iter([fixed_tenant_id, "admin-id-unused"])
        monkeypatch.setattr(tenant_service_module, "generate_uuid", lambda: next(id_calls))

        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
            await conn.execute(text(f"CREATE TABLE {schema_name}.documents (id VARCHAR PRIMARY KEY)"))

        transactional_engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            session_factory = async_sessionmaker(transactional_engine, expire_on_commit=False)
            async with session_factory() as session:
                service = TenantService(session)
                payload = {
                    "name": "Atomicity Test",
                    "slug": "atomicity-test",
                    "admin_email": "atomicity@example.com",
                    "admin_password": "Atomicity1234!",
                }
                with pytest.raises(Exception):
                    await service.create_tenant(payload, actor_email="tester", actor_role="system_admin")
        finally:
            await transactional_engine.dispose()

        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))

        async with engine.connect() as conn:
            tenant_row = await conn.execute(
                text("SELECT id FROM public.tenants WHERE slug = 'atomicity-test'")
            )
            assert tenant_row.fetchone() is None

            user_row = await conn.execute(
                text("SELECT id FROM public.tenant_users WHERE email = 'atomicity@example.com'")
            )
            assert user_row.fetchone() is None

            # The service's own CREATE SCHEMA call must not have left a schema
            # behind either — only the one this test pre-seeded (and already
            # dropped above) should ever have existed for this tenant id.
            schema_still_present = await conn.execute(
                text("SELECT nspname FROM pg_namespace WHERE nspname = :s"),
                {"s": schema_name},
            )
            assert schema_still_present.fetchone() is None

    async def test_provisioned_tenant_has_full_template_table_set(self, engine, db_session, setup_database):
        async with engine.begin() as conn:
            # Simulate a template that already carries migration 003's columns,
            # matching real deployments at head — the bare conftest fixture
            # predates 003 and lacks them.
            await conn.execute(text("""
                ALTER TABLE tenant_template.documents
                    ADD COLUMN IF NOT EXISTS content_type VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS file_size BIGINT,
                    ADD COLUMN IF NOT EXISTS blob_path VARCHAR(500),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
            """))

        service = TenantService(db_session)
        payload = {
            "name": "Full Table Set Test",
            "slug": "full-table-set-test",
            "admin_email": "fulltable@example.com",
            "admin_password": "FullTable1234!",
        }
        result = await service.create_tenant(payload, actor_email="tester", actor_role="system_admin")
        tenant_id = result["tenant"]["id"]
        schema_name = f"tenant_{tenant_id}".replace("-", "_")

        async with engine.connect() as conn:
            tmpl_tables = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'")
            )
            tmpl_names = {r[0] for r in tmpl_tables.fetchall()}

            tenant_tables = await conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = :s"),
                {"s": schema_name},
            )
            tenant_names = {r[0] for r in tenant_tables.fetchall()}

            assert tmpl_names == tenant_names

        token = create_access_token(tenant_id=tenant_id, user_id="fulltable-admin", role="tenant_admin")
        transport = ASGITransport(app=document_service_app)
        async with AsyncClient(transport=transport, base_url="http://test") as doc_client:
            resp = await doc_client.get(
                "/api/v1/documents",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        documents = body.get("documents", body if isinstance(body, list) else [])
        assert documents == []
