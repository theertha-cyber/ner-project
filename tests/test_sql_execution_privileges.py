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

from src.chat_api.services.sql_execution_role import (
    SmokeCheckFailed,
    build_role_statements,
    provision_role,
    smoke_check_schema,
)
from src.chat_api.services.sql_generator import (
    WHITELISTED_TABLES,
    SQLGenerator,
    SQLValidationError,
)
from src.shared.config import settings
from src.shared.entity_views import EntityDefinitionSpec, build_query_surface

pytestmark = [pytest.mark.verification, pytest.mark.asyncio]

TEST_ROLE = "ner_chat_sql_test"


def _surface_of(*identifiers: str):
    """The query surface a tenant with these active `multi` definitions resolves to.

    Built through `build_query_surface` rather than by naming tables directly, so a test can
    never assert against a surface the resolver would not produce."""
    return build_query_surface([
        EntityDefinitionSpec(name=i.removeprefix("e_"), sql_identifier=i) for i in identifiers
    ])


class TestRoleStatements:
    """The grant list is derived from the whitelist, not restated beside it."""

    def test_every_whitelisted_table_is_granted(self):
        statements = "\n".join(build_role_statements(TEST_ROLE, ["tenant_x"]))
        for table in WHITELISTED_TABLES:
            assert f"GRANT SELECT ON tenant_x.{table} TO {TEST_ROLE}" in statements

    def test_tenant_grants_are_revoked_before_they_are_reapplied(self):
        statements = build_role_statements(TEST_ROLE, ["tenant_x"])
        revoke = f"REVOKE ALL ON ALL TABLES IN SCHEMA tenant_x FROM {TEST_ROLE}"
        assert revoke in statements

        # The order is the whole point. Grants are otherwise append-only, so a generated table
        # that leaves the surface — deactivated, or flipped to `single` — would keep the SELECT
        # it was granted while it was on it, and go on being readable by the execution role.
        first_grant = next(
            index
            for index, statement in enumerate(statements)
            if "GRANT SELECT ON tenant_x." in statement
        )
        assert statements.index(revoke) < first_grant

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


class TestGeneratedTableSurface:
    """The execution role's grants and `validate_sql`'s whitelist come from one resolver.

    A table granted but not whitelisted is a query the validator rejects for a table the role
    can read; whitelisted but not granted is a query the validator accepts and the database
    refuses. Neither is recoverable at run time and neither is visible in review, so the two
    are asserted equal here rather than kept in step by discipline.

    Covers verification.md rows 97, 98, 99, 100, 101.
    """

    async def _tenant(self, engine):
        tid = f"surface-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.tenants (id, name, slug, status, max_users, "
                    "max_documents, max_storage_gb, max_model_versions) "
                    "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) "
                    "ON CONFLICT (id) DO NOTHING"
                ),
                {"id": tid},
            )
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        return tid, schema

    async def _define(self, engine, tid, name, identifier, is_active=True, cardinality="multi"):
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO public.entity_definitions "
                    "(id, tenant_id, name, sql_identifier, cardinality, is_active, version) "
                    "VALUES (:id, :tid, :name, :identifier, :cardinality, :active, 1)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "tid": tid,
                    "name": name,
                    "identifier": identifier,
                    "cardinality": cardinality,
                    "active": is_active,
                },
            )

    async def _cleanup(self, engine, tid, schema):
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid}
            )
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
            await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})

    async def test_grants_and_whitelist_resolve_to_the_same_generated_set(
        self, engine, setup_database
    ):
        from src.shared.entity_views import resolve_generated_tables

        tid, schema = await self._tenant(engine)
        try:
            await self._define(engine, tid, "Skill", "e_skill")
            await self._define(engine, tid, "Email", "e_email", cardinality="single")

            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                surface = await resolve_generated_tables(session, [schema])

            granted = set()
            statements = build_role_statements(TEST_ROLE, [schema], surface)
            for table in surface[schema]:
                if f"GRANT SELECT ON {schema}.{table} TO {TEST_ROLE}" in "\n".join(statements):
                    granted.add(table)

            assert granted == surface[schema]
            # `e_email` is `single`: its values are `subject.email`, and it owns no relation.
            assert {"subject", "e_skill"} == surface[schema]

        finally:
            await self._cleanup(engine, tid, schema)

    async def test_an_inactive_definition_is_in_neither(self, engine, setup_database):
        from src.shared.entity_views import (
            resolve_generated_tables,
            resolve_query_surface,
        )

        tid, schema = await self._tenant(engine)
        try:
            await self._define(engine, tid, "Retired", "e_retired", is_active=False)

            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                surface = await resolve_generated_tables(session, [schema])
                resolved = await resolve_query_surface(session, [schema])

            assert "e_retired" not in surface[schema]
            statements = "\n".join(build_role_statements(TEST_ROLE, [schema], surface))
            assert f"GRANT SELECT ON {schema}.e_retired" not in statements

            generator = SQLGenerator.__new__(SQLGenerator)
            with pytest.raises(SQLValidationError):
                generator.validate_sql(
                    "SELECT * FROM e_retired LIMIT 10", resolved[schema]
                )
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_a_single_definition_is_in_neither(self, engine, setup_database):
        """A `single` definition's values are a `subject` column, so its identifier names no
        relation. A child table it retains from an earlier `multi` life must be granted to
        nobody and accepted by nothing: the projection stopped writing to it at the flip, so a
        query reaching it returns zero rows rather than an error."""
        from src.shared.entity_views import (
            resolve_generated_tables,
            resolve_query_surface,
        )

        tid, schema = await self._tenant(engine)
        try:
            await self._define(engine, tid, "Email", "e_email", cardinality="single")

            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                surface = await resolve_generated_tables(session, [schema])
                resolved = await resolve_query_surface(session, [schema])

            assert "e_email" not in surface[schema]
            statements = "\n".join(build_role_statements(TEST_ROLE, [schema], surface))
            assert f"GRANT SELECT ON {schema}.e_email" not in statements

            generator = SQLGenerator.__new__(SQLGenerator)
            with pytest.raises(SQLValidationError):
                generator.validate_sql("SELECT * FROM e_email LIMIT 10", resolved[schema])
            # The values stay reachable — as the `subject` column the flip moved them to.
            assert [c.name for c in resolved[schema].subject_columns] == ["email"]
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_reactivation_restores_both(self, engine, setup_database):
        from src.shared.entity_views import (
            resolve_generated_tables,
            resolve_query_surface,
        )

        tid, schema = await self._tenant(engine)
        try:
            await self._define(engine, tid, "Skill", "e_skill", is_active=False)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                assert "e_skill" not in (await resolve_generated_tables(session, [schema]))[schema]

                await session.execute(
                    text(
                        "UPDATE public.entity_definitions SET is_active = true "
                        "WHERE tenant_id = :tid"
                    ),
                    {"tid": tid},
                )
                await session.commit()
                surface = await resolve_generated_tables(session, [schema])

            assert "e_skill" in surface[schema]
            statements = "\n".join(build_role_statements(TEST_ROLE, [schema], surface))
            assert f"GRANT SELECT ON {schema}.e_skill TO {TEST_ROLE}" in statements
        finally:
            await self._cleanup(engine, tid, schema)

    async def test_a_query_naming_a_generated_table_validates(self, engine, setup_database):
        generator = SQLGenerator.__new__(SQLGenerator)
        validated = generator.validate_sql(
            "SELECT value FROM e_skill LIMIT 10", _surface_of("e_skill")
        )
        assert "e_skill" in validated

    async def test_a_generated_table_of_another_tenant_is_not_whitelisted(self):
        # The surface is per-tenant: one tenant having `e_skill` says nothing about another's.
        generator = SQLGenerator.__new__(SQLGenerator)
        with pytest.raises(SQLValidationError):
            generator.validate_sql("SELECT value FROM e_skill LIMIT 10", _surface_of())

    async def test_the_role_gets_select_only_on_generated_tables(self):
        statements = "\n".join(
            build_role_statements(TEST_ROLE, ["tenant_x"], {"tenant_x": {"subject", "e_skill"}})
        )
        assert f"GRANT SELECT ON tenant_x.e_skill TO {TEST_ROLE}" in statements
        assert f"GRANT SELECT ON tenant_x.subject TO {TEST_ROLE}" in statements
        for verb in ("INSERT", "UPDATE", "DELETE"):
            assert f"GRANT {verb} ON tenant_x" not in statements

    async def test_a_grant_for_a_table_that_does_not_exist_is_guarded(self):
        # `pg_tables` matches physical tables directly, so the existing IF EXISTS guard covers
        # a definition whose table the reconciler has not created yet.
        statements = build_role_statements(
            TEST_ROLE, ["tenant_x"], {"tenant_x": {"e_not_created_yet"}}
        )
        guarded = [s for s in statements if "e_not_created_yet" in s]
        assert guarded
        for statement in guarded:
            assert "SELECT 1 FROM pg_tables" in statement


class TestSmokeCheckCoversGeneratedRelations:
    """verification.md rows 72, 73 — provisioning is where a missing grant has to surface.

    The generator now names the tenant's generated relations, so a generated relation the role
    cannot read fails a user's question exactly as a static one does, and just as invisibly.
    """

    async def _schema_with_generated_table(self, engine) -> str:
        tid = f"smoke-{uuid.uuid4().hex[:8]}"
        schema = f"tenant_{tid.replace('-', '_')}"
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            for table in sorted(WHITELISTED_TABLES):
                await conn.execute(
                    text(f"CREATE TABLE {schema}.{table} (id VARCHAR PRIMARY KEY)")
                )
            await conn.execute(
                text(f"CREATE TABLE {schema}.subject (document_id VARCHAR PRIMARY KEY)")
            )
            await conn.execute(
                text(f"CREATE TABLE {schema}.e_skill (document_id VARCHAR, value TEXT)")
            )
            await provision_role(conn, TEST_ROLE, [schema])
            # Granted explicitly: the tenant has no catalog rows, so `provision_role`'s own
            # resolution covers `subject` alone. The check under test is what the smoke check
            # reads, not how the grant got there.
            await conn.execute(text(f"GRANT SELECT ON {schema}.e_skill TO {TEST_ROLE}"))
        return schema

    async def _drop(self, engine, schema: str) -> None:
        async with engine.begin() as conn:
            await conn.execute(
                text(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {TEST_ROLE}")
            )
            await conn.execute(text(f"REVOKE ALL ON SCHEMA {schema} FROM {TEST_ROLE}"))
            await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))

    async def test_generated_relations_are_read_by_the_smoke_check(self, engine, setup_database):
        """Row 72."""
        schema = await self._schema_with_generated_table(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                await smoke_check_schema(session, TEST_ROLE, schema, {"subject", "e_skill"})
        finally:
            await self._drop(engine, schema)

    async def test_a_missing_grant_on_a_generated_relation_is_named(self, engine, setup_database):
        """Row 73 — the operator has to know which grant to fix."""
        schema = await self._schema_with_generated_table(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"REVOKE SELECT ON {schema}.e_skill FROM {TEST_ROLE}"))

            async with session_factory() as session:
                with pytest.raises(SmokeCheckFailed) as exc:
                    await smoke_check_schema(session, TEST_ROLE, schema, {"subject", "e_skill"})

            assert "e_skill" in str(exc.value)
            assert "permission denied" in str(exc.value).lower()
        finally:
            await self._drop(engine, schema)

    async def test_static_tables_are_still_checked_without_a_surface(
        self, engine, setup_database
    ):
        """The static path is unchanged: omitting the surface checks the whitelist alone."""
        schema = await self._schema_with_generated_table(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"REVOKE SELECT ON {schema}.e_skill FROM {TEST_ROLE}"))

            async with session_factory() as session:
                await smoke_check_schema(session, TEST_ROLE, schema)
        finally:
            await self._drop(engine, schema)

    async def test_a_relation_the_reconciler_has_not_created_is_skipped(self, engine, setup_database):
        """A catalogued relation with no table is not a provisioning failure.

        The tenant's catalog can name a relation the reconciler has not created yet — a schema
        provisioned from an older template, or a definition added between runs. `pg_tables`
        guards each grant for exactly that reason, and the smoke check reads the same catalog:
        there is no grant to be missing, and failing here would report an absent table as a
        permission problem and hide any real one behind it.
        """
        schema = await self._schema_with_generated_table(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with session_factory() as session:
                await smoke_check_schema(
                    session, TEST_ROLE, schema, {"subject", "e_skill", "e_not_created_yet"}
                )
        finally:
            await self._drop(engine, schema)

    async def test_an_absent_relation_does_not_mask_a_real_missing_grant(
        self, engine, setup_database
    ):
        schema = await self._schema_with_generated_table(engine)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"REVOKE SELECT ON {schema}.e_skill FROM {TEST_ROLE}"))

            async with session_factory() as session:
                with pytest.raises(SmokeCheckFailed) as exc:
                    await smoke_check_schema(
                        session, TEST_ROLE, schema, {"subject", "e_skill", "e_not_created_yet"}
                    )

            assert "e_skill" in str(exc.value)
            assert "e_not_created_yet" not in str(exc.value)
        finally:
            await self._drop(engine, schema)
