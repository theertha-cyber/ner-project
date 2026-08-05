"""Verifies migration 032 (chat_message_feedback + chat_messages.answer_kind/
model_version) was actually applied to the real dev database, not just the
ad-hoc tables the unit-test fixtures provision. Runs against NER_DATABASE_URL
directly (the dev DB, e.g. ner_dev on postgres-test), not the ner_test
database the rest of the suite uses via tests/conftest.py.
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


class TestMigration032AppliedToTenantTemplate:
    async def test_chat_message_feedback_table_exists_in_tenant_template(self, dev_engine):
        async with dev_engine.begin() as conn:
            columns = await _table_columns(conn, "tenant_template", "chat_message_feedback")
        assert set(columns) == {"id", "message_id", "tenant_id", "user_id", "rating", "created_at"}

    async def test_message_id_is_unique_in_tenant_template(self, dev_engine):
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT tc.constraint_type
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                WHERE tc.table_schema = 'tenant_template' AND tc.table_name = 'chat_message_feedback'
                    AND kcu.column_name = 'message_id'
            """))
            constraint_types = {row[0] for row in result.fetchall()}
        assert "UNIQUE" in constraint_types

    async def test_rating_check_constraint_restricts_to_up_down(self, dev_engine):
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT pg_get_constraintdef(oid) FROM pg_constraint
                WHERE conrelid = 'tenant_template.chat_message_feedback'::regclass AND contype = 'c'
            """))
            defs = [row[0] for row in result.fetchall()]
        assert any("rating" in d and "up" in d and "down" in d for d in defs)

    async def test_chat_messages_has_answer_kind_and_model_version(self, dev_engine):
        async with dev_engine.begin() as conn:
            columns = await _table_columns(conn, "tenant_template", "chat_messages")
        assert "answer_kind" in columns
        assert columns["answer_kind"] == "NO"  # NOT NULL, has a default
        assert "model_version" in columns
        assert columns["model_version"] == "YES"  # nullable


class TestMigration032BackfilledToLiveTenantSchemas:
    async def test_every_provisioned_tenant_schema_has_the_new_table_and_columns(self, dev_engine):
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
                if "answer_kind" not in columns or "model_version" not in columns:
                    missing.append((schema, "chat_messages", columns))
                fb_columns = await _table_columns(conn, schema, "chat_message_feedback")
                if not fb_columns:
                    missing.append((schema, "chat_message_feedback", fb_columns))

        assert not missing, f"tenant schemas missing migration 032 backfill: {missing}"

    async def test_default_pipeline_still_works_new_message_gets_answer_kind(self, dev_engine):
        """Sanity check: existing chat_messages rows (inserted before this
        migration) were backfilled to answer_kind='answer' by the column
        DEFAULT, not left NULL."""
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
                SELECT COUNT(*) FROM {schema}.chat_messages WHERE answer_kind IS NULL
            """))
            null_count = result.scalar()
        assert null_count == 0
