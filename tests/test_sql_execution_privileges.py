"""Generated SQL executes under a role that holds SELECT on the whitelisted tables in
tenant schemas and nothing at all in `public`.

This is defence in depth behind `validate_sql`: `public` holds `tenants`,
`tenant_users`, `widget_api_keys`, `entity_definitions`, and `audit_events`, and a
future gap in table-reference resolution must degrade into a permission error rather
than a cross-tenant read.

Covers verification.md rows 1, 2, 3.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.chat_api.services.sql_execution_role import build_role_statements, provision_role
from src.chat_api.services.sql_generator import (
    WHITELISTED_TABLES,
    SQLGenerator,
    SQLValidationError,
)
from src.shared.config import settings

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

TEST_ROLE = "ner_chat_sql_test"


class TestRoleStatements:
    """The grant list is derived from the whitelist, not restated beside it."""

    def test_every_whitelisted_table_is_granted(self):
        statements = "\n".join(build_role_statements(TEST_ROLE, ["tenant_x"]))
        for table in WHITELISTED_TABLES:
            assert f"GRANT SELECT ON tenant_x.{table} TO {TEST_ROLE}" in statements

    def test_no_public_relation_is_granted(self):
        statements = "\n".join(build_role_statements(TEST_ROLE, ["tenant_x"]))
        assert "GRANT SELECT ON public." not in statements
        assert f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {TEST_ROLE}" in statements

    def test_role_is_created_without_login(self):
        statements = "\n".join(build_role_statements(TEST_ROLE, []))
        assert f"CREATE ROLE {TEST_ROLE} NOLOGIN" in statements

    def test_non_identifier_role_is_rejected(self):
        from src.chat_api.services.sql_execution_role import InvalidIdentifierError

        with pytest.raises(InvalidIdentifierError):
            build_role_statements("ner; DROP SCHEMA public", [])


class TestExecutionUnderRestrictedRole:
    async def _make_schema(self, engine) -> str:
        tid = f"role-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            await conn.execute(text(f"""
                CREATE TABLE {schema}.documents (
                    id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL,
                    filename VARCHAR(255) NOT NULL, mime_type VARCHAR(100),
                    file_size_bytes BIGINT, status VARCHAR(20),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            await conn.execute(text(f"""
                CREATE TABLE {schema}.document_entities (
                    id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL,
                    entity_type TEXT NOT NULL, entity_value TEXT NOT NULL,
                    normalized_value TEXT NOT NULL, confidence DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            await conn.execute(
                text(f"INSERT INTO {schema}.documents (id, tenant_id, filename) "
                     "VALUES ('doc-1', :tid, 'Resume 1.pdf')"),
                {"tid": tid},
            )
            await conn.execute(text(
                f"INSERT INTO {schema}.document_entities "
                "(id, document_id, entity_type, entity_value, normalized_value, confidence) "
                "VALUES ('ent-1', 'doc-1', 'SKILL', 'AWS', 'aws', 0.9)"
            ))
            await provision_role(conn, TEST_ROLE, [schema])
        return schema

    async def _drop_schema(self, engine, schema: str) -> None:
        async with engine.begin() as conn:
            await conn.execute(text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {TEST_ROLE}"))
            await conn.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM {TEST_ROLE}"))
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    @staticmethod
    def _generator(monkeypatch) -> SQLGenerator:
        monkeypatch.setattr(settings, "sql_execution_role_enabled", True, raising=False)
        monkeypatch.setattr(settings, "sql_execution_role_name", TEST_ROLE, raising=False)
        return SQLGenerator.__new__(SQLGenerator)

    async def test_cross_tenant_relation_denied_by_role(self, engine, setup_database, monkeypatch):
        """The statement below is exactly what a table-reference gap would let through.
        The role is what stops it reading a row."""
        schema = await self._make_schema(engine)
        generator = self._generator(monkeypatch)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                with pytest.raises(Exception) as exc:
                    await generator.execute_sql(
                        "SELECT id FROM public.tenants LIMIT 1", session, schema
                    )
                assert "permission denied" in str(exc.value).lower()
                await session.execute(text("ROLLBACK"))
        finally:
            await self._drop_schema(engine, schema)

    async def test_whitelisted_join_succeeds_under_restricted_role(
        self, engine, setup_database, monkeypatch
    ):
        schema = await self._make_schema(engine)
        sql = (
            "SELECT e.entity_value, d.filename AS document_name "
            "FROM document_entities e JOIN documents d ON d.id = e.document_id LIMIT 100"
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            unrestricted = SQLGenerator.__new__(SQLGenerator)
            monkeypatch.setattr(settings, "sql_execution_role_enabled", False, raising=False)
            async with session_factory() as session:
                baseline = await unrestricted.execute_sql(sql, session, schema)

            restricted = self._generator(monkeypatch)
            async with session_factory() as session:
                rows = await restricted.execute_sql(sql, session, schema)

            assert rows == baseline
            assert rows == [{"entity_value": "AWS", "document_name": "Resume 1.pdf"}]
        finally:
            await self._drop_schema(engine, schema)

    async def test_write_denied_by_role_and_by_read_only_tx(
        self, engine, setup_database, monkeypatch
    ):
        """Two independent controls. The read-only transaction is unchanged by this
        work; the role denies the write on its own, in a writable transaction."""
        schema = await self._make_schema(engine)
        update = f"UPDATE {schema}.document_entities SET entity_value = 'x'"
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                await session.execute(text("BEGIN"))
                await session.execute(text(f"SET LOCAL ROLE {TEST_ROLE}"))
                with pytest.raises(Exception) as role_exc:
                    await session.execute(text(update))
                assert "permission denied" in str(role_exc.value).lower()
                await session.execute(text("ROLLBACK"))

            async with session_factory() as session:
                await session.execute(text("BEGIN READ ONLY"))
                with pytest.raises(Exception) as tx_exc:
                    await session.execute(text(update))
                assert "read-only transaction" in str(tx_exc.value).lower()
                await session.execute(text("ROLLBACK"))
        finally:
            await self._drop_schema(engine, schema)

    async def test_misconfigured_role_name_is_refused_before_execution(self, monkeypatch):
        monkeypatch.setattr(settings, "sql_execution_role_enabled", True, raising=False)
        monkeypatch.setattr(settings, "sql_execution_role_name", "bad name; SET ROLE postgres", raising=False)
        with pytest.raises(SQLValidationError):
            SQLGenerator._execution_role()

    def test_toggle_off_keeps_the_connection_role(self, monkeypatch):
        monkeypatch.setattr(settings, "sql_execution_role_enabled", False, raising=False)
        assert SQLGenerator._execution_role() is None
