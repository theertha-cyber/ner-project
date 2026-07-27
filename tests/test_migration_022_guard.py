import importlib.util
import os

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "022_document_purpose_scoping.py"
)
_spec = importlib.util.spec_from_file_location("migration_022_document_purpose_scoping", _MIGRATION_PATH)
migration_022 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_022)


def _run_upgrade_022(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_022.op
        migration_022.op = op
        try:
            migration_022.upgrade()
        finally:
            migration_022.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_template.document_chunks (
                id VARCHAR PRIMARY KEY,
                document_id VARCHAR,
                chunk_index INTEGER,
                chunk_text TEXT
            )
        """))
    yield engine
    engine.dispose()


def _create_bare_documents(conn, schema: str):
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {schema}.documents (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            filename VARCHAR(255) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))


def _create_annotation_tasks(conn, schema: str):
    conn.execute(text(f"""
        CREATE TABLE IF NOT EXISTS {schema}.annotation_tasks (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,
            status VARCHAR(20) DEFAULT 'open'
        )
    """))


@pytest.mark.asyncio
class TestMigration022Guard:
    async def test_missing_annotation_tasks_does_not_abort(self, engine, setup_database, sync_engine):
        complete_id = "mig022-complete-tenant"
        complete_schema = f"tenant_{complete_id.replace('-', '_')}"
        incomplete_id = "mig022-incomplete-tenant"
        incomplete_schema = f"tenant_{incomplete_id.replace('-', '_')}"

        async with engine.begin() as conn:
            for tid in (complete_id, incomplete_id):
                await conn.execute(
                    text(
                        "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                        "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                    ),
                    {"id": tid},
                )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {complete_schema}"))
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {incomplete_schema}"))

        with sync_engine.begin() as conn:
            _create_bare_documents(conn, complete_schema)
            _create_annotation_tasks(conn, complete_schema)
            conn.execute(
                text(f"INSERT INTO {complete_schema}.documents (id, tenant_id, filename) VALUES ('doc-1', :tid, 'a.pdf')"),
                {"tid": complete_id},
            )
            conn.execute(
                text(f"INSERT INTO {complete_schema}.annotation_tasks (id, document_id) VALUES ('at-1', 'doc-1')"),
            )

            _create_bare_documents(conn, incomplete_schema)
            conn.execute(
                text(f"INSERT INTO {incomplete_schema}.documents (id, tenant_id, filename) VALUES ('doc-2', :tid, 'b.pdf')"),
                {"tid": incomplete_id},
            )

        try:
            _run_upgrade_022(sync_engine)

            with sync_engine.begin() as conn:
                complete_purpose = conn.execute(
                    text(f"SELECT purpose FROM {complete_schema}.documents WHERE id = 'doc-1'")
                ).scalar()
                incomplete_purpose = conn.execute(
                    text(f"SELECT purpose FROM {incomplete_schema}.documents WHERE id = 'doc-2'")
                ).scalar()
                assert complete_purpose == "training"
                assert incomplete_purpose == "query"
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {complete_schema} CASCADE"))
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {incomplete_schema} CASCADE"))
                await conn.execute(
                    text("DELETE FROM public.tenants WHERE id IN (:a, :b)"),
                    {"a": complete_id, "b": incomplete_id},
                )

    async def test_schema_missing_all_target_tables_is_skipped(self, engine, setup_database, sync_engine):
        empty_id = "mig022-empty-tenant"
        empty_schema = f"tenant_{empty_id.replace('-', '_')}"

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": empty_id},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {empty_schema}"))

        try:
            _run_upgrade_022(sync_engine)
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {empty_schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": empty_id})

    async def test_guarded_loop_rerun_is_noop(self, engine, setup_database, sync_engine):
        tid = "mig022-rerun-tenant"
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
            _create_bare_documents(conn, schema)
            _create_annotation_tasks(conn, schema)
            conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename) VALUES ('doc-1', :tid, 'a.pdf')"),
                {"tid": tid},
            )
            conn.execute(text(f"INSERT INTO {schema}.annotation_tasks (id, document_id) VALUES ('at-1', 'doc-1')"))

        try:
            _run_upgrade_022(sync_engine)
            _run_upgrade_022(sync_engine)

            with sync_engine.begin() as conn:
                purpose = conn.execute(
                    text(f"SELECT purpose FROM {schema}.documents WHERE id = 'doc-1'")
                ).scalar()
                assert purpose == "training"
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
