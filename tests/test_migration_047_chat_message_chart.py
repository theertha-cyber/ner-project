"""Verifies migration 047 (chat_messages.chart) was actually applied to the real dev
database, not just the ad-hoc tables the unit-test fixtures provision. Runs against the
dev DB directly, following test_migration_032_chat_message_feedback.py.

Covers verification.md row 33.
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


async def _chart_column(conn, schema: str) -> tuple[str, str] | None:
    result = await conn.execute(
        text("""
            SELECT data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = 'chat_messages' AND column_name = 'chart'
        """),
        {"schema": schema},
    )
    row = result.fetchone()
    return (row[0], row[1]) if row else None


class TestMigration047AppliedToTenantTemplate:
    async def test_chart_column_exists_and_is_nullable_jsonb(self, dev_engine):
        async with dev_engine.begin() as conn:
            column = await _chart_column(conn, "tenant_template")

        assert column is not None, "tenant_template.chat_messages is missing the chart column"
        data_type, is_nullable = column
        assert data_type == "jsonb"
        # Nullable with no backfill: a turn that produced no chart, and every row
        # written before this migration, reads back as chart-less.
        assert is_nullable == "YES"


class TestMigration047BackfilledToLiveTenantSchemas:
    async def test_every_provisioned_tenant_schema_has_the_chart_column(self, dev_engine):
        """ADR-001: the column must reach every tenant schema, not only the template."""
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
                if await _chart_column(conn, schema) is None:
                    missing.append(schema)

        assert not missing, f"tenant schemas missing migration 047 backfill: {missing}"

    async def test_user_messages_never_carry_a_chart(self, dev_engine):
        """The migration backfills nothing, and a user's own message can never acquire a
        chart — only an assistant turn produces one. Asserting the invariant rather than
        "no charts exist anywhere", which stops being true the moment the feature is used."""
        async with dev_engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            """))
            schemas = [row[0] for row in result.fetchall()]

            offenders = []
            for schema in schemas:
                count = (await conn.execute(
                    text(f"SELECT COUNT(*) FROM {schema}.chat_messages "
                         "WHERE role = 'user' AND chart IS NOT NULL")
                )).scalar()
                if count:
                    offenders.append((schema, count))

        assert not offenders, f"user messages carrying a chart: {offenders}"
