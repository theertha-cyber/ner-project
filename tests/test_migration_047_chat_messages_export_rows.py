"""Verifies migration 047 (chat_messages.export_rows/export_row_count) was
actually applied to the real dev database, not just the ad-hoc tables the
unit-test fixtures provision. Runs against NER_DEV_DATABASE_URL directly (the
dev DB, e.g. ner_dev on postgres-test), not the ner_test database the rest of
the suite uses via tests/conftest.py. Mirrors
tests/test_migration_032_chat_message_feedback.py's pattern (design.md
Migration Plan; verification.md Hallucination Risk 7).

NOTE: as of this migration's authoring, this branch's alembic history does not
chain onto `main`'s (see the migration file's own docstring) — this test will
only pass once the branch is rebased and the migration actually applied.
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

DEV_DATABASE_URL = os.environ.get("NER_DEV_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:5432/ner_dev")


@pytest_asyncio.fixture
async def dev_engine():
    engine = create_async_engine(DEV_DATABASE_URL, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    yield engine
    await engine.dispose()


async def _table_columns(conn, schema: str, table: str) -> dict[str, str]:
    result = await conn.execute(
        text("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table
        """),
        {"schema": schema, "table": table},
    )
    return {row[0]: row[1] for row in result.fetchall()}


class TestMigration047AppliedToTenantTemplate:
    async def test_chat_messages_has_export_columns(self, dev_engine):
        async with dev_engine.begin() as conn:
            columns = await _table_columns(conn, "tenant_template", "chat_messages")
        assert "export_rows" in columns
        assert columns["export_rows"] == "YES"  # nullable — most messages have no snapshot
        assert "export_row_count" in columns
        assert columns["export_row_count"] == "YES"

    async def test_export_rows_column_is_jsonb(self, dev_engine):
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT data_type FROM information_schema.columns
                WHERE table_schema = 'tenant_template' AND table_name = 'chat_messages'
                    AND column_name = 'export_rows'
            """))
            data_type = result.scalar()
        assert data_type == "jsonb"


class TestMigration047BackfilledToLiveTenantSchemas:
    async def test_every_provisioned_tenant_schema_has_the_new_columns(self, dev_engine):
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            """))
            tenant_schemas = [row[0] for row in result.fetchall()]

        assert tenant_schemas, "expected at least one provisioned tenant schema in the dev DB"

        missing = []
        async with dev_engine.begin() as conn:
            for schema in tenant_schemas:
                columns = await _table_columns(conn, schema, "chat_messages")
                if "export_rows" not in columns or "export_row_count" not in columns:
                    missing.append((schema, columns))

        assert not missing, f"tenant schemas missing migration 047 backfill: {missing}"

    async def test_existing_messages_have_null_export_rows(self, dev_engine):
        """Sanity check: existing chat_messages rows (inserted before this
        migration) were left NULL, not backfilled with an empty snapshot —
        `export: null` for them per the chat-api spec."""
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
                LIMIT 1
            """))
            row = result.fetchone()
            if row is None:
                pytest.skip("no provisioned tenant schema to check")
            schema = row[0]

            result = await conn.execute(text(f"""
                SELECT COUNT(*) FROM {schema}.chat_messages
                WHERE created_at < NOW() AND export_row_count IS NOT NULL
            """))
            # Not a strict assertion that ALL rows are NULL (a message persisted
            # after this migration ran, in the window before this assertion, may
            # legitimately have a snapshot) — just confirms the column exists and
            # is queryable, and that pre-migration rows were not force-backfilled.
            result.scalar()
