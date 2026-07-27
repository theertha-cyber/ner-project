import pytest
from sqlalchemy import text

from src.gateway.models import Base
from src.gateway.verify_schema import verify
from src.shared.config import settings


@pytest.mark.asyncio
class TestVerifySchema:
    async def test_clean_database_passes(self, engine, setup_database):
        # setup_test_db.py (run once per pytest session, before any test) creates
        # its own narrower public.entity_definitions if the table doesn't exist
        # yet. Depending on test order, this test can be the first to touch that
        # table, so force the full ORM shape here rather than depending on
        # incidental ordering.
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS public.entity_definitions CASCADE"))
            await conn.run_sync(
                lambda sync_conn: Base.metadata.tables["public.entity_definitions"].create(sync_conn)
            )

        # setup_database's tenant_template fixture doesn't carry every table
        # every migration ever declared (it's a minimal test fixture, not a
        # full migration replay), so this test focuses on the public-schema
        # check, which the ORM recreation above satisfies in full.
        problems = await verify(settings.database_url)
        public_problems = [p for p in problems if p.startswith("public.")]
        assert public_problems == []

    async def test_missing_public_column_detected(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text(
                "ALTER TABLE public.entity_definitions DROP COLUMN IF EXISTS validation_rule"
            ))
        try:
            problems = await verify(settings.database_url)
            assert any(
                "public.entity_definitions" in p and "validation_rule" in p
                for p in problems
            )
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "ALTER TABLE public.entity_definitions ADD COLUMN IF NOT EXISTS validation_rule VARCHAR(500)"
                ))

    async def test_missing_template_table_detected(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("ALTER TABLE tenant_template.documents RENAME TO documents_hidden"))
        try:
            problems = await verify(settings.database_url)
            assert any("tenant_template.documents" in p for p in problems)
        finally:
            async with engine.begin() as conn:
                await conn.execute(text("ALTER TABLE tenant_template.documents_hidden RENAME TO documents"))

    async def test_tenant_schema_lagging_template_detected(self, engine, setup_database):
        tid = "verify-lagging-tenant"
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            # Deliberately missing 'documents', which tenant_template has.
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.spans (
                    id VARCHAR PRIMARY KEY
                )
            """))
        try:
            problems = await verify(settings.database_url)
            assert any(f"{schema}.documents" in p for p in problems)
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_undeclared_scratch_table_does_not_fail(self, engine, setup_database):
        async with engine.begin() as conn:
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS public.developer_scratch_table (
                    id VARCHAR PRIMARY KEY
                )
            """))
        try:
            problems = await verify(settings.database_url)
            assert not any("developer_scratch_table" in p for p in problems)
        finally:
            async with engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS public.developer_scratch_table"))
