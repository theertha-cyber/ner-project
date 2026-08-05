import importlib.util
import os

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text

from src.shared.config import settings

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "027_conversation_entity_state.py"
)
_spec = importlib.util.spec_from_file_location("migration_027_conversation_entity_state", _MIGRATION_PATH)
migration_027 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_027)


def _run_upgrade_027(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_027.op
        migration_027.op = op
        try:
            migration_027.upgrade()
        finally:
            migration_027.op = original_op
        connection.commit()


def _run_downgrade_027(sync_engine):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_027.op
        migration_027.op = op
        try:
            migration_027.downgrade()
        finally:
            migration_027.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tenant_template.conversation_entity_state"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS tenant_template.conversation_entity_state"))
    engine.dispose()


def _columns(conn, schema: str, table: str) -> set[str]:
    return {
        r[0] for r in conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = :schema AND table_name = :table"
        ), {"schema": schema, "table": table})
    }


_EXPECTED_COLUMNS = {
    "conversation_id", "pending_original_message", "pending_mention", "pending_candidates",
    "pending_reask_count", "resolved_document_id", "resolved_entity_value", "updated_at",
}


@pytest.mark.asyncio
class TestMigration027ConversationEntityState:
    """Covers verification.md task 1.3: migration created and reversible."""

    async def test_template_and_tenant_schema_receive_table(self, engine, setup_database, sync_engine):
        tid = "mig027-basic-tenant"
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
            _run_upgrade_027(sync_engine)

            with sync_engine.begin() as conn:
                assert _EXPECTED_COLUMNS <= _columns(conn, "tenant_template", "conversation_entity_state")
                assert _EXPECTED_COLUMNS <= _columns(conn, schema, "conversation_entity_state")
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_rerun_is_noop(self, engine, setup_database, sync_engine):
        tid = "mig027-rerun-tenant"
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
            _run_upgrade_027(sync_engine)
            with sync_engine.begin() as conn:
                before = sorted(_columns(conn, schema, "conversation_entity_state"))
            _run_upgrade_027(sync_engine)
            with sync_engine.begin() as conn:
                after = sorted(_columns(conn, schema, "conversation_entity_state"))
            assert before == after
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_downgrade_drops_the_table(self, engine, setup_database, sync_engine):
        tid = "mig027-downgrade-tenant"
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
            _run_upgrade_027(sync_engine)
            _run_downgrade_027(sync_engine)

            with sync_engine.begin() as conn:
                template_exists = conn.execute(
                    text("SELECT to_regclass('tenant_template.conversation_entity_state')")
                ).scalar()
                tenant_exists = conn.execute(
                    text(f"SELECT to_regclass('{schema}.conversation_entity_state')")
                ).scalar()
                assert template_exists is None
                assert tenant_exists is None
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
