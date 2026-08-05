import importlib.util
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "028_entity_definition_value_kind.py"
)
_spec = importlib.util.spec_from_file_location("migration_028_entity_definition_value_kind", _MIGRATION_PATH)
migration_028 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_028)


def _run(sync_engine, direction: str):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_028.op
        migration_028.op = op
        try:
            getattr(migration_028, direction)()
        finally:
            migration_028.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


def _columns(conn, schema: str, table: str) -> set[str]:
    return {
        r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table})
    }


@pytest.mark.asyncio
class TestMigration028EntityDefinitionValueKind:
    """Covers verification.md rows 43-44."""

    async def _seed_tenant_and_definition(self, engine, tid: str, ent_name: str):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions (id, tenant_id, name, description, version, required_flag, is_active) "
                    "VALUES (:id, :tid, :name, 'pre-existing', 1, false, true)"
                ),
                {"id": str(uuid.uuid4()), "tid": tid, "name": ent_name},
            )

    async def _cleanup(self, engine, tid: str):
        async with engine.begin() as conn:
            await conn.execute(text("DELETE FROM public.entity_definitions WHERE tenant_id = :tid"), {"tid": tid})
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_columns_added_existing_rows_null_and_untouched(self, engine, setup_database, sync_engine):
        tid = f"mig028-add-{uuid.uuid4().hex[:8]}"
        ent_name = "PRE_EXISTING_TYPE"
        await self._seed_tenant_and_definition(engine, tid, ent_name)

        with sync_engine.begin() as conn:
            before_cols = _columns(conn, "public", "entity_definitions")

        try:
            _run(sync_engine, "upgrade")

            with sync_engine.begin() as conn:
                after_cols = _columns(conn, "public", "entity_definitions")
                assert "value_kind" in after_cols
                assert "value_unit" in after_cols
                # No pre-existing column was removed or renamed.
                assert before_cols - {"value_kind", "value_unit"} <= after_cols

                row = conn.execute(
                    text("SELECT value_kind, value_unit, description, version FROM public.entity_definitions "
                         "WHERE tenant_id = :tid AND name = :name"),
                    {"tid": tid, "name": ent_name},
                ).fetchone()
                assert row.value_kind is None
                assert row.value_unit is None
                assert row.description == "pre-existing"
                assert row.version == 1
        finally:
            await self._cleanup(engine, tid)

    async def test_rerun_is_noop(self, engine, setup_database, sync_engine):
        _run(sync_engine, "upgrade")
        with sync_engine.begin() as conn:
            before = sorted(_columns(conn, "public", "entity_definitions"))
        _run(sync_engine, "upgrade")
        with sync_engine.begin() as conn:
            after = sorted(_columns(conn, "public", "entity_definitions"))
        assert before == after

    async def test_downgrade_removes_columns_and_preserves_rows(self, engine, setup_database, sync_engine):
        tid = f"mig028-down-{uuid.uuid4().hex[:8]}"
        ent_name = "DOWNGRADE_TYPE"
        _run(sync_engine, "upgrade")
        await self._seed_tenant_and_definition(engine, tid, ent_name)

        try:
            _run(sync_engine, "downgrade")

            with sync_engine.begin() as conn:
                cols = _columns(conn, "public", "entity_definitions")
                assert "value_kind" not in cols
                assert "value_unit" not in cols

                row = conn.execute(
                    text("SELECT name, description, version FROM public.entity_definitions "
                         "WHERE tenant_id = :tid AND name = :name"),
                    {"tid": tid, "name": ent_name},
                ).fetchone()
                assert row is not None
                assert row.description == "pre-existing"
                assert row.version == 1
        finally:
            # Leave the schema in the upgraded state for the rest of the suite.
            _run(sync_engine, "upgrade")
            await self._cleanup(engine, tid)
