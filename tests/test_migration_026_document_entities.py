import importlib.util
import os

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "026_document_entities.py"
)
_spec = importlib.util.spec_from_file_location("migration_026_document_entities", _MIGRATION_PATH)
migration_026 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_026)


def _run_upgrade_026(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_026.op
        migration_026.op = op
        try:
            migration_026.upgrade()
        finally:
            migration_026.op = original_op
        connection.commit()


def _run_downgrade_026(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_026.op
        migration_026.op = op
        try:
            migration_026.downgrade()
        finally:
            migration_026.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tenant_template.document_entities"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tenant_template.document_entities"))
    engine.dispose()


def _columns(conn, schema: str, table: str) -> set[str]:
    return {
        r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table})
    }


_EXPECTED_COLUMNS = {
    "id", "document_id", "entity_type", "entity_value", "normalized_value",
    "confidence", "page_number", "char_start", "char_end", "created_at",
}


@pytest.mark.asyncio
class TestMigration026DocumentEntities:
    async def test_template_and_tenant_schema_receive_table(self, engine, setup_database, sync_engine):
        tid = "mig026-basic-tenant"
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

        try:
            _run_upgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                assert _EXPECTED_COLUMNS <= _columns(conn, "tenant_template", "document_entities")
                assert _EXPECTED_COLUMNS <= _columns(conn, schema, "document_entities")

                idx_names = {
                    r[0] for r in conn.execute(text(
                        "SELECT indexname FROM pg_indexes WHERE schemaname = :schema AND tablename = 'document_entities'"
                    ), {"schema": schema})
                }
                assert len(idx_names) >= 3
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_inactive_tenant_schema_not_skipped(self, engine, setup_database, sync_engine):
        tid = "mig026-inactive-tenant"
        schema = f"tenant_{tid.replace('-', '_')}"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'inactive', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))

        try:
            _run_upgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                exists = conn.execute(text(f"SELECT to_regclass('{schema}.document_entities')")).scalar()
                assert exists is not None
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_extracted_entities_untouched(self, engine, setup_database, sync_engine):
        tid = "mig026-raw-untouched-tenant"
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

        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.extracted_entities (
                    id VARCHAR PRIMARY KEY,
                    run_id VARCHAR,
                    entity_id VARCHAR,
                    value VARCHAR,
                    confidence FLOAT,
                    document_id VARCHAR
                )
            """))
            conn.execute(text(f"""
                INSERT INTO {schema}.extracted_entities (id, run_id, entity_id, value, confidence, document_id)
                VALUES ('ee-1', 'run-1', 'B-PER', 'Arjun', 0.9, 'doc-1')
            """))
            before_cols = _columns(conn, schema, "extracted_entities")

        try:
            _run_upgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                after_cols = _columns(conn, schema, "extracted_entities")
                assert before_cols == after_cols
                row_count = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.extracted_entities")).scalar()
                assert row_count == 1
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {schema}.extracted_entities"))
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_rerun_is_noop(self, engine, setup_database, sync_engine):
        tid = "mig026-rerun-tenant"
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

        try:
            _run_upgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                before = sorted(_columns(conn, schema, "document_entities"))

            _run_upgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                after = sorted(_columns(conn, schema, "document_entities"))

            assert before == after
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_downgrade_drops_only_document_entities(self, engine, setup_database, sync_engine):
        tid = "mig026-downgrade-tenant"
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

        with sync_engine.begin() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema}.extracted_entities (
                    id VARCHAR PRIMARY KEY
                )
            """))

        try:
            _run_upgrade_026(sync_engine)
            _run_downgrade_026(sync_engine)

            with sync_engine.begin() as conn:
                template_exists = conn.execute(
                    text("SELECT to_regclass('tenant_template.document_entities')")
                ).scalar()
                tenant_exists = conn.execute(
                    text(f"SELECT to_regclass('{schema}.document_entities')")
                ).scalar()
                raw_exists = conn.execute(
                    text(f"SELECT to_regclass('{schema}.extracted_entities')")
                ).scalar()
                assert template_exists is None
                assert tenant_exists is None
                assert raw_exists is not None
        finally:
            with sync_engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {schema}.extracted_entities"))
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
