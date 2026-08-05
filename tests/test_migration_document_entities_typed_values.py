import importlib.util
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_VERSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")


def _load_migration(filename: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, os.path.join(_VERSIONS_DIR, filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


migration_026 = _load_migration("026_document_entities.py", "migration_026_document_entities")
migration_029 = _load_migration("029_document_entities_typed_values.py", "migration_029_document_entities_typed_values")


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


def _index_names(conn, schema: str, table: str) -> set[str]:
    return {
        r[0] for r in conn.execute(text(
            "SELECT indexname FROM pg_indexes WHERE schemaname = :schema AND tablename = :table"
        ), {"schema": schema, "table": table})
    }


_TYPED_COLUMNS = {"value_kind", "value_number", "value_number_high", "value_unit", "value_date", "value_date_high"}


@pytest.mark.asyncio
class TestMigration029DocumentEntitiesTypedValues:
    """Covers verification.md rows 38-42."""

    async def _make_tenant_schema(self, engine, tid: str):
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
        return schema

    async def _cleanup(self, engine, tid: str, schema: str):
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_template_and_two_tenant_schemas_receive_columns_and_indexes(self, engine, setup_database, sync_engine):
        tid_a = f"mig029-a-{uuid.uuid4().hex[:6]}"
        tid_b = f"mig029-b-{uuid.uuid4().hex[:6]}"
        schema_a = await self._make_tenant_schema(engine, tid_a)
        schema_b = await self._make_tenant_schema(engine, tid_b)

        try:
            _run(sync_engine, migration_026, "upgrade")
            _run(sync_engine, migration_029, "upgrade")

            with sync_engine.begin() as conn:
                assert _TYPED_COLUMNS <= _columns(conn, "tenant_template", "document_entities")
                assert _TYPED_COLUMNS <= _columns(conn, schema_a, "document_entities")
                assert _TYPED_COLUMNS <= _columns(conn, schema_b, "document_entities")

                for schema in (schema_a, schema_b):
                    idx_names = _index_names(conn, schema, "document_entities")
                    assert any("value_number" in n for n in idx_names)
                    assert any("value_date" in n for n in idx_names)
        finally:
            await self._cleanup(engine, tid_a, schema_a)
            await self._cleanup(engine, tid_b, schema_b)

    async def test_existing_rows_preserved_new_columns_null(self, engine, setup_database, sync_engine):
        tid = f"mig029-rows-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, tid)

        try:
            _run(sync_engine, migration_026, "upgrade")

            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.document_entities
                        (id, document_id, entity_type, entity_value, normalized_value, confidence)
                    VALUES ('de-1', 'doc-1', 'YEARS_OF_EXP', '5+ years', '5+ years', 0.9)
                """))

            _run(sync_engine, migration_029, "upgrade")

            with sync_engine.begin() as conn:
                row = conn.execute(text(f"""
                    SELECT entity_value, normalized_value, confidence, value_number, value_date
                    FROM {schema}.document_entities WHERE id = 'de-1'
                """)).fetchone()
                assert row.entity_value == "5+ years"
                assert row.normalized_value == "5+ years"
                assert row.confidence == 0.9
                assert row.value_number is None
                assert row.value_date is None
                count = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.document_entities")).scalar()
                assert count == 1
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_tenant_schema_missing_table_is_skipped(self, engine, setup_database, sync_engine):
        tid_missing = f"mig029-missing-{uuid.uuid4().hex[:6]}"
        tid_present = f"mig029-present-{uuid.uuid4().hex[:6]}"
        schema_missing = await self._make_tenant_schema(engine, tid_missing)
        schema_present = await self._make_tenant_schema(engine, tid_present)

        try:
            _run(sync_engine, migration_026, "upgrade")
            with sync_engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {schema_missing}.document_entities"))

            _run(sync_engine, migration_029, "upgrade")

            with sync_engine.begin() as conn:
                exists = conn.execute(text(f"SELECT to_regclass('{schema_missing}.document_entities')")).scalar()
                assert exists is None
                assert _TYPED_COLUMNS <= _columns(conn, schema_present, "document_entities")
        finally:
            await self._cleanup(engine, tid_missing, schema_missing)
            await self._cleanup(engine, tid_present, schema_present)

    async def test_rerun_is_noop(self, engine, setup_database, sync_engine):
        tid = f"mig029-rerun-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, tid)

        try:
            _run(sync_engine, migration_026, "upgrade")
            _run(sync_engine, migration_029, "upgrade")

            with sync_engine.begin() as conn:
                before = sorted(_columns(conn, schema, "document_entities"))

            _run(sync_engine, migration_029, "upgrade")

            with sync_engine.begin() as conn:
                after = sorted(_columns(conn, schema, "document_entities"))

            assert before == after
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_newly_provisioned_tenant_inherits_columns(self, engine, setup_database, sync_engine):
        # Simulates provisioning a new tenant by cloning tenant_template *after*
        # the migration has already been applied to the template.
        _run(sync_engine, migration_026, "upgrade")
        _run(sync_engine, migration_029, "upgrade")

        tid = f"mig029-new-{uuid.uuid4().hex[:6]}"
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
            template_ddl = conn.execute(text(
                "SELECT 'CREATE TABLE ' || :schema || '.document_entities (LIKE tenant_template.document_entities INCLUDING ALL)'"
            ), {"schema": schema}).scalar()
            conn.execute(text(template_ddl))

        try:
            with sync_engine.begin() as conn:
                assert _TYPED_COLUMNS <= _columns(conn, schema, "document_entities")
                idx_names = _index_names(conn, schema, "document_entities")
                assert any("value_number" in n for n in idx_names)
                assert any("value_date" in n for n in idx_names)
        finally:
            await self._cleanup(engine, tid, schema)
