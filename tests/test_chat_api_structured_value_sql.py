import uuid
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.chat_api.services.sql_generator import SQLGenerator, WHITELISTED_TABLES

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]


class TestStructuredValueSQLValidation:
    """Covers verification.md rows 34-37 — offline, no DB required."""

    def setup_method(self):
        self.generator = SQLGenerator()

    def test_34_numeric_comparison_query_passes_validation(self):
        sql = (
            "SELECT d.filename AS document_name, e.value_number FROM document_entities e "
            "JOIN documents d ON d.id = e.document_id "
            "WHERE e.entity_type = 'YEARS_OF_EXP' AND e.value_number > 2 LIMIT 100"
        )
        result = self.generator.validate_sql(sql)
        assert "LIMIT" in result.upper()

    def test_35_date_comparison_query_passes_validation(self):
        sql = "SELECT * FROM document_entities WHERE entity_type = 'CERTIFICATION_EXPIRY' AND value_date < CURRENT_DATE LIMIT 100"
        result = self.generator.validate_sql(sql)
        assert "LIMIT" in result.upper()

    def test_36_non_whitelisted_column_the_table_itself_still_gated(self):
        # The validator gates on table names, not per-column parsing; a non-whitelisted
        # table referencing a similarly named column is still rejected.
        sql = "SELECT value_number FROM pg_stat_activity LIMIT 10"
        from src.chat_api.services.sql_generator import SQLValidationError
        with pytest.raises(SQLValidationError):
            self.generator.validate_sql(sql)

    def test_36_typed_columns_are_whitelisted(self):
        for col in ("value_kind", "value_number", "value_number_high", "value_unit", "value_date", "value_date_high"):
            assert col in WHITELISTED_TABLES["document_entities"]

    def test_37_text_only_query_still_valid(self):
        sql = "SELECT * FROM document_entities WHERE normalized_value = 'aws' LIMIT 100"
        result = self.generator.validate_sql(sql)
        assert "LIMIT" in result.upper()


@pytest.mark.asyncio
class TestStructuredValueSQLExecution:
    """Covers verification.md rows 19, 22-25 — deterministic filtering over real rows."""

    async def _make_schema_with_rows(self, engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
            await conn.execute(text(f"""
                CREATE TABLE "{schema}".document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
                    entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    page_number INTEGER, char_start INTEGER, char_end INTEGER, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    value_kind TEXT, value_number DOUBLE PRECISION, value_number_high DOUBLE PRECISION,
                    value_unit TEXT, value_date DATE, value_date_high DATE
                )
            """))

    async def test_19_and_22_numeric_comparison_excludes_null_rows(self, engine, setup_database):
        tid = f"sql-num-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        await self._make_schema_with_rows(engine, tid, schema)

        try:
            async with engine.begin() as conn:
                for value, num in [("1.0", 1.0), ("2.5", 2.5), ("5.0", 5.0), ("null", None)]:
                    await conn.execute(
                        text(f'INSERT INTO "{schema}".document_entities '
                             '(id, document_id, entity_type, entity_value, normalized_value, confidence, value_number) '
                             "VALUES (:id, 'doc-1', 'YEARS_OF_EXP', :v, :v, 0.9, :num)"),
                        {"id": str(uuid.uuid4()), "v": value, "num": num},
                    )

            async with engine.begin() as conn:
                rows = await conn.execute(
                    text(f'SELECT value_number FROM "{schema}".document_entities '
                         "WHERE entity_type = 'YEARS_OF_EXP' AND value_number > 2")
                )
                values = sorted(r[0] for r in rows.fetchall())
                assert values == [2.5, 5.0]
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_23_inclusive_comparison(self, engine, setup_database):
        tid = f"sql-incl-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        await self._make_schema_with_rows(engine, tid, schema)

        try:
            async with engine.begin() as conn:
                for num in (4.0, 5.0):
                    await conn.execute(
                        text(f'INSERT INTO "{schema}".document_entities '
                             '(id, document_id, entity_type, entity_value, normalized_value, confidence, value_number) '
                             "VALUES (:id, 'doc-1', 'YEARS_OF_EXP', 'x', 'x', 0.9, :num)"),
                        {"id": str(uuid.uuid4()), "num": num},
                    )

            async with engine.begin() as conn:
                rows = await conn.execute(
                    text(f'SELECT value_number FROM "{schema}".document_entities WHERE value_number >= 5')
                )
                values = [r[0] for r in rows.fetchall()]
                assert values == [5.0]
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_24_date_comparison_against_current_date(self, engine, setup_database):
        tid = f"sql-date-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        await self._make_schema_with_rows(engine, tid, schema)

        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(f'INSERT INTO "{schema}".document_entities '
                         '(id, document_id, entity_type, entity_value, normalized_value, confidence, value_date) '
                         "VALUES (:id, 'doc-1', 'CERTIFICATION_EXPIRY', 'past', 'past', 0.9, CURRENT_DATE - INTERVAL '30 days')"),
                    {"id": str(uuid.uuid4())},
                )
                await conn.execute(
                    text(f'INSERT INTO "{schema}".document_entities '
                         '(id, document_id, entity_type, entity_value, normalized_value, confidence, value_date) '
                         "VALUES (:id, 'doc-1', 'CERTIFICATION_EXPIRY', 'future', 'future', 0.9, CURRENT_DATE + INTERVAL '30 days')"),
                    {"id": str(uuid.uuid4())},
                )

            async with engine.begin() as conn:
                rows = await conn.execute(
                    text(f'SELECT entity_value FROM "{schema}".document_entities '
                         "WHERE entity_type = 'CERTIFICATION_EXPIRY' AND value_date < CURRENT_DATE")
                )
                values = [r[0] for r in rows.fetchall()]
                assert values == ["past"]
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_25_range_filter(self, engine, setup_database):
        tid = f"sql-range-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        await self._make_schema_with_rows(engine, tid, schema)

        try:
            async with engine.begin() as conn:
                for label, d in [("in_range", date(2026, 6, 15)), ("before", date(2025, 12, 31)), ("after", date(2027, 1, 1))]:
                    await conn.execute(
                        text(f'INSERT INTO "{schema}".document_entities '
                             '(id, document_id, entity_type, entity_value, normalized_value, confidence, value_date) '
                             "VALUES (:id, 'doc-1', 'DATE', :label, :label, 0.9, :d)"),
                        {"id": str(uuid.uuid4()), "label": label, "d": d},
                    )

            async with engine.begin() as conn:
                rows = await conn.execute(
                    text(f'SELECT entity_value FROM "{schema}".document_entities '
                         "WHERE value_date BETWEEN '2026-01-01' AND '2026-12-31'")
                )
                values = [r[0] for r in rows.fetchall()]
                assert values == ["in_range"]
        finally:
            async with engine.begin() as conn:
                await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
                await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})
