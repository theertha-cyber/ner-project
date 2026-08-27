"""Covers verification.md rows 90-92 for migration 036."""

import importlib.util
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_VERSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")

_EXTRACTION_RUNS_DDL = """
    CREATE TABLE IF NOT EXISTS {schema}.extraction_runs (
        id VARCHAR PRIMARY KEY,
        tenant_id VARCHAR NOT NULL,
        document_id VARCHAR,
        model_version VARCHAR,
        status VARCHAR(20) DEFAULT 'queued',
        started_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE,
        total_documents INTEGER NOT NULL DEFAULT 0,
        processed_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        failed_count INTEGER NOT NULL DEFAULT 0
    )
"""


_DROP_ADDED_COLUMNS = """
    ALTER TABLE {schema}.extraction_runs
        DROP COLUMN IF EXISTS processing_mode,
        DROP COLUMN IF EXISTS postprocess_model,
        DROP COLUMN IF EXISTS postprocess_prompt_version,
        DROP COLUMN IF EXISTS postprocess_degraded
"""


def _load_migration(filename: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_VERSIONS_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration_036 = _load_migration(
    "036_extraction_runs_processing_mode.py", "migration_036_extraction_runs_processing_mode"
)


def _run(sync_engine, module, direction: str):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = module.op
        module.op = op
        try:
            getattr(module, direction)()
        finally:
            module.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    """`tenant_template.extraction_runs` is created by the shared database setup and is
    referenced by a foreign key from `extracted_entities`, so it cannot be dropped and
    recreated per test. The migration only adds columns, so the template is left in
    place and the added columns are removed on teardown."""
    engine = create_engine(settings.database_url_sync)
    with engine.begin() as conn:
        conn.execute(text(_EXTRACTION_RUNS_DDL.format(schema="tenant_template")))
        conn.execute(text(_DROP_ADDED_COLUMNS.format(schema="tenant_template")))
    yield engine
    with engine.begin() as conn:
        conn.execute(text(_DROP_ADDED_COLUMNS.format(schema="tenant_template")))
    engine.dispose()


def _columns(conn, schema: str, table: str) -> set[str]:
    return {
        r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table})
    }


MODE_COLUMNS = {
    "processing_mode",
    "postprocess_model",
    "postprocess_prompt_version",
    "postprocess_degraded",
}


@pytest.mark.asyncio
class TestMigration036ExtractionRunsProcessingMode:
    """Covers verification.md rows 90-92."""

    async def _make_tenant_schema(self, engine, sync_engine, tid: str, with_table: bool = True):
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
        if with_table:
            with sync_engine.begin() as conn:
                conn.execute(text(_EXTRACTION_RUNS_DDL.format(schema=schema)))
        return schema

    async def _cleanup(self, engine, tid: str, schema: str):
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_template_and_two_tenant_schemas_receive_columns(self, engine, setup_database, sync_engine):
        """Row 90."""
        tid_a = f"mig036-a-{uuid.uuid4().hex[:6]}"
        tid_b = f"mig036-b-{uuid.uuid4().hex[:6]}"
        schema_a = await self._make_tenant_schema(engine, sync_engine, tid_a)
        schema_b = await self._make_tenant_schema(engine, sync_engine, tid_b)

        try:
            _run(sync_engine, migration_036, "upgrade")

            with sync_engine.begin() as conn:
                assert MODE_COLUMNS <= _columns(conn, "tenant_template", "extraction_runs")
                assert MODE_COLUMNS <= _columns(conn, schema_a, "extraction_runs")
                assert MODE_COLUMNS <= _columns(conn, schema_b, "extraction_runs")
        finally:
            await self._cleanup(engine, tid_a, schema_a)
            await self._cleanup(engine, tid_b, schema_b)

    async def test_existing_runs_are_labelled_bert_only(self, engine, setup_database, sync_engine):
        """Row 91 — every run that already happened really was BERT-only."""
        tid = f"mig036-rows-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, sync_engine, tid)

        try:
            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.extraction_runs
                        (id, tenant_id, status, total_documents, processed_count, skipped_count, failed_count)
                    VALUES ('run-legacy', :tid, 'completed', 3, 3, 0, 0)
                """), {"tid": tid})

            _run(sync_engine, migration_036, "upgrade")

            with sync_engine.begin() as conn:
                row = conn.execute(text(f"""
                    SELECT status, processed_count, processing_mode, postprocess_model,
                           postprocess_prompt_version, postprocess_degraded
                    FROM {schema}.extraction_runs WHERE id = 'run-legacy'
                """)).fetchone()

            assert row.processing_mode == "bert_only"
            assert row.postprocess_model is None
            assert row.postprocess_prompt_version is None
            assert row.postprocess_degraded is False
            assert row.status == "completed"
            assert row.processed_count == 3
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_tenant_schema_missing_table_is_skipped(self, engine, setup_database, sync_engine):
        tid_missing = f"mig036-missing-{uuid.uuid4().hex[:6]}"
        tid_present = f"mig036-present-{uuid.uuid4().hex[:6]}"
        schema_missing = await self._make_tenant_schema(engine, sync_engine, tid_missing, with_table=False)
        schema_present = await self._make_tenant_schema(engine, sync_engine, tid_present)

        try:
            _run(sync_engine, migration_036, "upgrade")

            with sync_engine.begin() as conn:
                assert conn.execute(text(f"SELECT to_regclass('{schema_missing}.extraction_runs')")).scalar() is None
                assert MODE_COLUMNS <= _columns(conn, schema_present, "extraction_runs")
        finally:
            await self._cleanup(engine, tid_missing, schema_missing)
            await self._cleanup(engine, tid_present, schema_present)

    async def test_newly_provisioned_tenant_inherits_columns(self, engine, setup_database, sync_engine):
        """Row 92 — provisioning clones the template, so the template must carry them."""
        _run(sync_engine, migration_036, "upgrade")

        tid = f"mig036-new-{uuid.uuid4().hex[:6]}"
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
            conn.execute(text(
                f"CREATE TABLE {schema}.extraction_runs (LIKE tenant_template.extraction_runs INCLUDING ALL)"
            ))

        try:
            with sync_engine.begin() as conn:
                assert MODE_COLUMNS <= _columns(conn, schema, "extraction_runs")
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_downgrade_removes_only_the_added_columns(self, engine, setup_database, sync_engine):
        tid = f"mig036-down-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, sync_engine, tid)

        try:
            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.extraction_runs
                        (id, tenant_id, status, total_documents, processed_count, skipped_count, failed_count)
                    VALUES ('run-down', :tid, 'completed', 1, 1, 0, 0)
                """), {"tid": tid})

            _run(sync_engine, migration_036, "upgrade")
            _run(sync_engine, migration_036, "downgrade")

            with sync_engine.begin() as conn:
                remaining = _columns(conn, schema, "extraction_runs")
                assert not (MODE_COLUMNS & remaining)
                assert {"id", "tenant_id", "status", "processed_count"} <= remaining
                row = conn.execute(text(
                    f"SELECT status, processed_count FROM {schema}.extraction_runs WHERE id = 'run-down'"
                )).fetchone()
                assert row.status == "completed"
                assert row.processed_count == 1
        finally:
            await self._cleanup(engine, tid, schema)
