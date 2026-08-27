"""Covers verification.md rows 86-89 for migration 035.

The provenance columns must reach every tenant schema and the template, must leave
existing rows byte-identical (their `confidence` values are uncalibrated logits that
cannot be converted after the fact), must tolerate a tenant schema with no
`document_entities` table, and must downgrade without touching pre-existing data."""

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


migration_026 = _load_migration("026_document_entities.py", "migration_026_document_entities_prov")
migration_035 = _load_migration("035_document_entities_provenance.py", "migration_035_document_entities_provenance")


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


PROVENANCE_COLUMNS = {
    "source_entity_value",
    "source_entity_type",
    "postprocess_status",
    "postprocess_model",
    "postprocess_prompt_version",
    "postprocess_at",
    "extraction_schema_version",
    "occurrence_count",
}

_PRE_EXISTING_COLUMNS = {
    "id", "document_id", "entity_type", "entity_value", "normalized_value",
    "confidence", "page_number", "char_start", "char_end", "created_at",
}


@pytest.mark.asyncio
class TestMigration035DocumentEntitiesProvenance:
    """Covers verification.md rows 86-89."""

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

    async def test_template_and_two_tenant_schemas_receive_columns(self, engine, setup_database, sync_engine):
        """Row 86."""
        tid_a = f"mig035-a-{uuid.uuid4().hex[:6]}"
        tid_b = f"mig035-b-{uuid.uuid4().hex[:6]}"
        schema_a = await self._make_tenant_schema(engine, tid_a)
        schema_b = await self._make_tenant_schema(engine, tid_b)

        try:
            _run(sync_engine, migration_026, "upgrade")
            _run(sync_engine, migration_035, "upgrade")

            with sync_engine.begin() as conn:
                assert PROVENANCE_COLUMNS <= _columns(conn, "tenant_template", "document_entities")
                assert PROVENANCE_COLUMNS <= _columns(conn, schema_a, "document_entities")
                assert PROVENANCE_COLUMNS <= _columns(conn, schema_b, "document_entities")
        finally:
            await self._cleanup(engine, tid_a, schema_a)
            await self._cleanup(engine, tid_b, schema_b)

    async def test_existing_rows_are_not_rewritten(self, engine, setup_database, sync_engine):
        """Row 87. The stored 5.63 is an uncalibrated logit — the migration must leave it
        exactly as it is rather than pretending it is a probability."""
        tid = f"mig035-rows-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, tid)

        try:
            _run(sync_engine, migration_026, "upgrade")

            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.document_entities
                        (id, document_id, entity_type, entity_value, normalized_value, confidence)
                    VALUES ('de-legacy', 'doc-1', 'JOB_TITLE', 'Software Engineer', 'software engineer', 5.6263)
                """))

            _run(sync_engine, migration_035, "upgrade")

            with sync_engine.begin() as conn:
                row = conn.execute(text(f"""
                    SELECT entity_value, entity_type, normalized_value, confidence,
                           source_entity_value, source_entity_type, postprocess_status,
                           postprocess_model, postprocess_prompt_version, postprocess_at,
                           extraction_schema_version, occurrence_count
                    FROM {schema}.document_entities WHERE id = 'de-legacy'
                """)).fetchone()

                assert row.entity_value == "Software Engineer"
                assert row.entity_type == "JOB_TITLE"
                assert row.normalized_value == "software engineer"
                assert row.confidence == 5.6263

                assert row.source_entity_value is None
                assert row.source_entity_type is None
                assert row.postprocess_model is None
                assert row.postprocess_prompt_version is None
                assert row.postprocess_at is None
                assert row.postprocess_status == "not_applied"
                assert row.extraction_schema_version == migration_035.LEGACY_SCHEMA_VERSION
                assert row.occurrence_count == 1

                assert conn.execute(text(f"SELECT COUNT(*) FROM {schema}.document_entities")).scalar() == 1
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_tenant_schema_missing_table_is_skipped(self, engine, setup_database, sync_engine):
        """Row 88."""
        tid_missing = f"mig035-missing-{uuid.uuid4().hex[:6]}"
        tid_present = f"mig035-present-{uuid.uuid4().hex[:6]}"
        schema_missing = await self._make_tenant_schema(engine, tid_missing)
        schema_present = await self._make_tenant_schema(engine, tid_present)

        try:
            _run(sync_engine, migration_026, "upgrade")
            with sync_engine.begin() as conn:
                conn.execute(text(f"DROP TABLE IF EXISTS {schema_missing}.document_entities"))

            _run(sync_engine, migration_035, "upgrade")

            with sync_engine.begin() as conn:
                assert conn.execute(text(f"SELECT to_regclass('{schema_missing}.document_entities')")).scalar() is None
                assert PROVENANCE_COLUMNS <= _columns(conn, schema_present, "document_entities")
        finally:
            await self._cleanup(engine, tid_missing, schema_missing)
            await self._cleanup(engine, tid_present, schema_present)

    async def test_downgrade_removes_only_the_added_columns(self, engine, setup_database, sync_engine):
        """Row 89."""
        tid = f"mig035-down-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, tid)

        try:
            _run(sync_engine, migration_026, "upgrade")
            with sync_engine.begin() as conn:
                conn.execute(text(f"""
                    INSERT INTO {schema}.document_entities
                        (id, document_id, entity_type, entity_value, normalized_value, confidence)
                    VALUES ('de-down', 'doc-1', 'COMPANY', 'Centizen Inc.', 'centizen inc', 4.98)
                """))

            _run(sync_engine, migration_035, "upgrade")
            _run(sync_engine, migration_035, "downgrade")

            with sync_engine.begin() as conn:
                remaining = _columns(conn, schema, "document_entities")
                assert not (PROVENANCE_COLUMNS & remaining)
                assert _PRE_EXISTING_COLUMNS <= remaining

                row = conn.execute(text(
                    f"SELECT entity_value, normalized_value, confidence FROM {schema}.document_entities WHERE id = 'de-down'"
                )).fetchone()
                assert row.entity_value == "Centizen Inc."
                assert row.normalized_value == "centizen inc"
                assert row.confidence == 4.98
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_rerun_is_noop(self, engine, setup_database, sync_engine):
        tid = f"mig035-rerun-{uuid.uuid4().hex[:6]}"
        schema = await self._make_tenant_schema(engine, tid)

        try:
            _run(sync_engine, migration_026, "upgrade")
            _run(sync_engine, migration_035, "upgrade")
            with sync_engine.begin() as conn:
                before = sorted(_columns(conn, schema, "document_entities"))

            _run(sync_engine, migration_035, "upgrade")
            with sync_engine.begin() as conn:
                after = sorted(_columns(conn, schema, "document_entities"))

            assert before == after
        finally:
            await self._cleanup(engine, tid, schema)
