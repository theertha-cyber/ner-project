import importlib.util
import os

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "023_reconcile_tenant_schemas.py"
)
_spec = importlib.util.spec_from_file_location("migration_023_reconcile_tenant_schemas", _MIGRATION_PATH)
migration_023 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_023)


def _run_upgrade_023(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_023.op
        migration_023.op = op
        try:
            migration_023.upgrade()
        finally:
            migration_023.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


@pytest.mark.asyncio
class TestTenantSchemaReconciliation:
    async def test_pre_003_tenant_gains_document_columns(self, engine, setup_database, sync_engine):
        tid = "recon-pre003-tenant"
        schema = f"tenant_{tid.replace('-', '_')}"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )

        with sync_engine.begin() as conn:
            # Simulate the template already having migration 003's columns.
            conn.execute(text("""
                ALTER TABLE tenant_template.documents
                    ADD COLUMN IF NOT EXISTS content_type VARCHAR(255),
                    ADD COLUMN IF NOT EXISTS file_size BIGINT,
                    ADD COLUMN IF NOT EXISTS blob_path VARCHAR(500),
                    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW()
            """))
            # A pre-003 tenant schema: documents table without those columns.
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.execute(text(f"""
                CREATE TABLE {schema}.documents (
                    id VARCHAR PRIMARY KEY,
                    tenant_id VARCHAR NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    mime_type VARCHAR(100),
                    file_size_bytes BIGINT,
                    checksum VARCHAR(64),
                    storage_uri VARCHAR(500),
                    status VARCHAR(20) DEFAULT 'uploaded',
                    ocr_applied_flag BOOLEAN DEFAULT false,
                    error_message TEXT,
                    purpose VARCHAR(20) NOT NULL DEFAULT 'query',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))

        try:
            _run_upgrade_023(sync_engine)

            with sync_engine.begin() as conn:
                cols = {
                    r[0] for r in conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}' AND table_name = 'documents'"
                    ))
                }
                assert {"content_type", "file_size", "blob_path", "updated_at"} <= cols

                # A document upload's INSERT (the columns document_service writes) succeeds.
                conn.execute(text(f"""
                    INSERT INTO {schema}.documents
                        (id, tenant_id, filename, content_type, file_size, status, blob_path)
                    VALUES ('doc-upload-1', :tid, 'a.pdf', 'application/pdf', 1024, 'pending', 'blob/a.pdf')
                """), {"tid": tid})
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_missing_table_cloned_from_template(self, engine, setup_database, sync_engine):
        tid = "recon-missing-table-tenant"
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
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS tenant_template.recon_test_table (
                    id VARCHAR PRIMARY KEY,
                    label VARCHAR(50) NOT NULL DEFAULT 'x',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_recon_test_table_label
                ON tenant_template.recon_test_table (label)
            """))

        try:
            _run_upgrade_023(sync_engine)

            with sync_engine.begin() as conn:
                exists = conn.execute(
                    text(f"SELECT to_regclass('{schema}.recon_test_table')")
                ).scalar()
                assert exists is not None

                tmpl_cols = {
                    r[0] for r in conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = 'tenant_template' AND table_name = 'recon_test_table'"
                    ))
                }
                tenant_cols = {
                    r[0] for r in conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}' AND table_name = 'recon_test_table'"
                    ))
                }
                assert tmpl_cols == tenant_cols

                pk_exists = conn.execute(text(
                    "SELECT conname FROM pg_constraint "
                    f"WHERE conrelid = '{schema}.recon_test_table'::regclass AND contype = 'p'"
                )).scalar()
                assert pk_exists is not None

                idx_exists = conn.execute(text(
                    "SELECT indexname FROM pg_indexes "
                    f"WHERE schemaname = '{schema}' AND tablename = 'recon_test_table'"
                )).fetchall()
                assert len(idx_exists) >= 1
        finally:
            with sync_engine.begin() as conn:
                schemas = [
                    r[0] for r in conn.execute(text(
                        "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\\_%'"
                    ))
                ]
                for s in schemas:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{s}".recon_test_table CASCADE'))
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_tenant_only_column_preserved(self, engine, setup_database, sync_engine):
        tid = "recon-tenant-only-col"
        schema = f"tenant_{tid.replace('-', '_')}"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )

        with sync_engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            conn.execute(text(f"""
                CREATE TABLE {schema}.documents
                    (LIKE tenant_template.documents INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)
            """))
            conn.execute(text(f"""
                ALTER TABLE {schema}.documents ADD COLUMN legacy_note VARCHAR(255)
            """))
            conn.execute(text(f"""
                INSERT INTO {schema}.documents (id, tenant_id, filename, legacy_note)
                VALUES ('doc-legacy-1', :tid, 'legacy.pdf', 'keep-me')
            """), {"tid": tid})

        try:
            _run_upgrade_023(sync_engine)
            _run_upgrade_023(sync_engine)

            with sync_engine.begin() as conn:
                cols = {
                    r[0] for r in conn.execute(text(
                        "SELECT column_name FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}' AND table_name = 'documents'"
                    ))
                }
                assert "legacy_note" in cols
                value = conn.execute(text(
                    f"SELECT legacy_note FROM {schema}.documents WHERE id = 'doc-legacy-1'"
                )).scalar()
                assert value == "keep-me"
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_reconciliation_is_idempotent(self, engine, setup_database, sync_engine):
        tid = "recon-idempotent-tenant"
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
            _run_upgrade_023(sync_engine)

            with sync_engine.begin() as conn:
                before = sorted(
                    (r[0], r[1]) for r in conn.execute(text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}'"
                    ))
                )

            _run_upgrade_023(sync_engine)

            with sync_engine.begin() as conn:
                after = sorted(
                    (r[0], r[1]) for r in conn.execute(text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        f"WHERE table_schema = '{schema}'"
                    ))
                )

            assert before == after
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
