"""All four entity-definition write paths reconcile the tenant's generated schema, and none
of them drops anything.

`create`, `update`, `toggle`, and `soft_delete` each reconcile in that call's own transaction,
so a definition and the relation it describes cannot be committed apart. The never-drop rule is
what makes that safe: `entity_definitions` has no hard delete — `soft_delete_entity_type` only
sets `is_active = false` and `toggle_entity_type` flips the same flag back — so dropping a
relation on deactivation would turn an undo button into a data-loss event.

Covers verification.md rows 64, 65, 66, 67, 68, 114, 115, 116.
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.gateway.services.entity_service import EntityService

pytestmark = pytest.mark.asyncio

_TENANT_TABLES = """
    CREATE TABLE "{schema}".documents (
        id VARCHAR PRIMARY KEY, tenant_id VARCHAR NOT NULL, filename VARCHAR(255) NOT NULL
    );
    CREATE TABLE "{schema}".document_entities (
        id VARCHAR PRIMARY KEY, document_id VARCHAR NOT NULL, entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL
    );
"""


@pytest.fixture
async def tenant(engine, setup_database, db_session):
    tid = f"recon-{uuid.uuid4().hex[:8]}"
    schema = f"tenant_{tid.replace('-', '_')}"
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO public.tenants (id, name, slug, status, max_users, max_documents, "
                "max_storage_gb, max_model_versions) "
                "VALUES (:id, :id, :id, 'active', 10, 1000, 5, 10) ON CONFLICT (id) DO NOTHING"
            ),
            {"id": tid},
        )
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        for statement in _TENANT_TABLES.format(schema=schema).split(";"):
            if statement.strip():
                await conn.execute(text(statement))

    yield {"id": tid, "schema": schema, "service": EntityService(db_session)}

    async with engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM public.entity_definitions WHERE tenant_id = :id"), {"id": tid}
        )
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await conn.execute(text("DELETE FROM public.tenants WHERE id = :id"), {"id": tid})


async def _tables(engine, schema):
    async with engine.begin() as conn:
        rows = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = :s"), {"s": schema}
        )
    return {r[0] for r in rows.fetchall()}


async def _columns(engine, schema, table):
    async with engine.begin() as conn:
        rows = await conn.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t"
            ),
            {"s": schema, "t": table},
        )
    return {r[0] for r in rows.fetchall()}


async def _seed_child_row(engine, schema, table, doc_id="doc-1"):
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f'INSERT INTO "{schema}".{table} '
                "(document_id, value, normalized_value, confidence) "
                "VALUES (:doc, 'python', 'python', 0.9)"
            ),
            {"doc": doc_id},
        )


async def _row_count(engine, schema, table):
    async with engine.begin() as conn:
        result = await conn.execute(text(f'SELECT count(*) FROM "{schema}".{table}'))
    return result.scalar()


class TestCreateReconciles:
    """verification.md rows 64, 114"""

    async def test_creating_an_entity_type_creates_its_relation(self, engine, tenant):
        await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        assert {"e_skill", "subject"} <= await _tables(engine, tenant["schema"])

    async def test_creating_a_single_entity_type_adds_its_subject_column(self, engine, tenant):
        await tenant["service"].create_entity_type(
            tenant["id"],
            {"name": "Years Experience", "cardinality": "single", "value_kind": "number"},
        )
        assert "years_experience" in await _columns(engine, tenant["schema"], "subject")
        # A `single` definition's whole purpose is a typed column the LLM can compare and
        # order; landing in TEXT would make `WHERE years_experience > 5` impossible.
        async with engine.begin() as conn:
            data_type = (
                await conn.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_schema = :s AND table_name = 'subject' "
                        "AND column_name = 'years_experience'"
                    ),
                    {"s": tenant["schema"]},
                )
            ).scalar()
        assert data_type == "double precision"

    async def test_a_schema_without_document_entities_is_skipped_not_failed(
        self, engine, tenant
    ):
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP TABLE "{tenant["schema"]}".document_entities'))

        # A tenant provisioned from a template predating `document_entities` must not make
        # entity-type creation fail for everyone.
        created = await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        assert created["sql_identifier"] == "e_skill"
        assert "subject" not in await _tables(engine, tenant["schema"])


class TestUpdateReconciles:
    """verification.md row 115"""

    async def test_multi_to_single_adds_the_column_and_keeps_the_child_table(
        self, engine, tenant
    ):
        await tenant["service"].create_entity_type(tenant["id"], {"name": "Email"})
        await _seed_child_row(engine, tenant["schema"], "e_email")

        await tenant["service"].update_entity_type(
            tenant["id"], "Email", {"cardinality": "single"}
        )

        assert "email" in await _columns(engine, tenant["schema"], "subject")
        # Nothing is migrated between the two representations, and nothing is dropped: the old
        # relation keeps its rows and the new one stays empty until re-extraction.
        assert "e_email" in await _tables(engine, tenant["schema"])
        assert await _row_count(engine, tenant["schema"], "e_email") == 1

    async def test_single_to_multi_leaves_the_subject_column_in_place(self, engine, tenant):
        await tenant["service"].create_entity_type(
            tenant["id"], {"name": "Email", "cardinality": "single"}
        )
        assert "email" in await _columns(engine, tenant["schema"], "subject")

        await tenant["service"].update_entity_type(
            tenant["id"], "Email", {"cardinality": "multi"}
        )

        assert "e_email" in await _tables(engine, tenant["schema"])
        assert "email" in await _columns(engine, tenant["schema"], "subject")


class TestToggleAndDeleteNeverDrop:
    """verification.md rows 65, 67, 68, 116"""

    async def test_deactivation_keeps_the_table_and_its_rows(self, engine, tenant):
        await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        await _seed_child_row(engine, tenant["schema"], "e_skill")

        await tenant["service"].toggle_entity_type(tenant["id"], "Skill", False)

        assert "e_skill" in await _tables(engine, tenant["schema"])
        assert await _row_count(engine, tenant["schema"], "e_skill") == 1

    async def test_reactivation_finds_the_retained_rows(self, engine, tenant):
        await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        await _seed_child_row(engine, tenant["schema"], "e_skill")

        await tenant["service"].toggle_entity_type(tenant["id"], "Skill", False)
        await tenant["service"].toggle_entity_type(tenant["id"], "Skill", True)

        assert await _row_count(engine, tenant["schema"], "e_skill") == 1

    async def test_soft_delete_keeps_the_table_and_its_rows(self, engine, tenant):
        await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        await _seed_child_row(engine, tenant["schema"], "e_skill")

        await tenant["service"].soft_delete_entity_type(tenant["id"], "Skill")

        # There is no hard delete for an entity type, so this flag is reversible and the rows
        # must survive it.
        assert "e_skill" in await _tables(engine, tenant["schema"])
        assert await _row_count(engine, tenant["schema"], "e_skill") == 1

    async def test_deactivating_a_single_definition_keeps_its_subject_column(
        self, engine, tenant
    ):
        await tenant["service"].create_entity_type(
            tenant["id"], {"name": "Email", "cardinality": "single"}
        )
        await tenant["service"].toggle_entity_type(tenant["id"], "Email", False)
        assert "email" in await _columns(engine, tenant["schema"], "subject")

    async def test_no_write_path_emits_a_drop(self, engine, tenant, monkeypatch):
        import src.shared.entity_views as entity_views

        executed: list[str] = []
        real_build = entity_views.build_entity_table_statements

        def recording_build(schema, definitions):
            statements = real_build(schema, definitions)
            executed.extend(statements)
            return statements

        monkeypatch.setattr(entity_views, "build_entity_table_statements", recording_build)

        service = tenant["service"]
        await service.create_entity_type(tenant["id"], {"name": "Skill"})
        await service.update_entity_type(tenant["id"], "Skill", {"cardinality": "single"})
        await service.toggle_entity_type(tenant["id"], "Skill", False)
        await service.toggle_entity_type(tenant["id"], "Skill", True)
        await service.soft_delete_entity_type(tenant["id"], "Skill")

        assert executed
        for statement in executed:
            upper = statement.upper()
            for forbidden in ("DROP TABLE", "DROP VIEW", "DROP COLUMN", "DELETE", "TRUNCATE"):
                assert forbidden not in upper, statement


class TestQuerySurfaceFollowsTheFlag:
    """verification.md row 66"""

    async def test_a_deactivated_definition_leaves_the_generated_table_set(self, engine, tenant):
        from src.shared.entity_views import resolve_generated_tables

        await tenant["service"].create_entity_type(tenant["id"], {"name": "Skill"})
        service_db = tenant["service"].db
        surface = await resolve_generated_tables(service_db, [tenant["schema"]])
        assert "e_skill" in surface[tenant["schema"]]

        await tenant["service"].toggle_entity_type(tenant["id"], "Skill", False)
        surface = await resolve_generated_tables(service_db, [tenant["schema"]])
        # The table is retained but leaves the query surface — that exclusion is what
        # deactivation means for grants and for the whitelist.
        assert "e_skill" not in surface[tenant["schema"]]
        assert "e_skill" in await _tables(engine, tenant["schema"])

        await tenant["service"].toggle_entity_type(tenant["id"], "Skill", True)
        surface = await resolve_generated_tables(service_db, [tenant["schema"]])
        assert "e_skill" in surface[tenant["schema"]]


async def _column_type(engine, schema, table, column):
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema = :s AND table_name = :t AND column_name = :c"
            ),
            {"s": schema, "t": table, "c": column},
        )
    return result.scalar()


async def _persisted_value_kind(engine, tenant_id, name):
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT value_kind FROM public.entity_definitions "
                "WHERE tenant_id = :tid AND name = :name"
            ),
            {"tid": tenant_id, "name": name},
        )
    return result.scalar()


class TestValueKindChangeConvergesTheColumn:
    """verification.md rows 1, 2, 13.

    The catalog and the column have to move together or not at all. They already share a
    transaction — `update_entity_type` writes the row, reconciles, then commits — so what was
    missing was only the reconciler noticing that the column's type had gone stale.
    """

    async def test_changing_value_kind_retypes_the_column(self, engine, tenant):
        """Row 1, through the write path an admin actually uses."""
        await tenant["service"].create_entity_type(
            tenant["id"], {"name": "Phone Number", "cardinality": "single"}
        )
        assert await _column_type(engine, tenant["schema"], "subject", "phone_number") == "text"

        await tenant["service"].update_entity_type(
            tenant["id"], "Phone Number", {"value_kind": "number"}
        )

        assert (
            await _column_type(engine, tenant["schema"], "subject", "phone_number")
            == "double precision"
        )

    async def test_changing_it_back_retypes_the_column_back(self, engine, tenant):
        """Row 2 — the correction the observed `PHONE_NUMBER` misconfiguration needed."""
        await tenant["service"].create_entity_type(
            tenant["id"],
            {"name": "Phone Number", "cardinality": "single", "value_kind": "number"},
        )
        assert (
            await _column_type(engine, tenant["schema"], "subject", "phone_number")
            == "double precision"
        )

        await tenant["service"].update_entity_type(
            tenant["id"], "Phone Number", {"value_kind": "text"}
        )

        assert await _column_type(engine, tenant["schema"], "subject", "phone_number") == "text"

    async def test_the_catalog_and_the_column_agree_after_the_write(self, engine, tenant):
        """The invariant itself, stated over the pair rather than over either half."""
        await tenant["service"].create_entity_type(
            tenant["id"], {"name": "Start Date", "cardinality": "single"}
        )

        for kind, expected in (("date", "date"), ("number", "double precision"), ("text", "text")):
            await tenant["service"].update_entity_type(
                tenant["id"], "Start Date", {"value_kind": kind}
            )
            assert await _persisted_value_kind(engine, tenant["id"], "Start Date") == kind
            assert (
                await _column_type(engine, tenant["schema"], "subject", "start_date") == expected
            )

    async def test_a_failing_reconciliation_rolls_the_definition_back(self, engine, tenant):
        """Row 13 — the catalog must not commit over a schema that did not converge.

        Runs against its own engine rather than the shared `engine` fixture, which is created
        with `isolation_level="AUTOCOMMIT"` (tests/conftest.py) and therefore has no transaction
        to roll back. What is under test here *is* the transaction boundary, so the connection
        has to behave the way the gateway's does.

        The DDL is forced to fail rather than waited for: `USING NULL` cannot fail on data, so
        breaking the statement is the only way to reach this path. The statement is not what is
        being tested; the boundary around it is."""
        import src.shared.entity_views as entity_views
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        from src.shared.config import settings

        await tenant["service"].create_entity_type(
            tenant["id"], {"name": "Phone Number", "cardinality": "single"}
        )

        original = entity_views.build_subject_column_type_statements
        entity_views.build_subject_column_type_statements = lambda schema, definitions, actual: [
            f"ALTER TABLE {schema}.subject ALTER COLUMN phone_number TYPE nonesuch"
        ]
        transactional = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            session_factory = async_sessionmaker(transactional, expire_on_commit=False)
            async with session_factory() as session:
                with pytest.raises(Exception):
                    await EntityService(session).update_entity_type(
                        tenant["id"], "Phone Number", {"value_kind": "number"}
                    )
                await session.rollback()
        finally:
            entity_views.build_subject_column_type_statements = original
            await transactional.dispose()

        # Neither half moved: the definition still declares no kind, and the column is still text.
        assert await _persisted_value_kind(engine, tenant["id"], "Phone Number") is None
        assert await _column_type(engine, tenant["schema"], "subject", "phone_number") == "text"

    async def test_an_unrelated_update_does_not_retype_anything(self, engine, tenant):
        """Editing a description must not disturb the column — the reconcile runs on every
        write path, so "nothing diverged" has to mean "nothing happens"."""
        await tenant["service"].create_entity_type(
            tenant["id"],
            {"name": "Years Experience", "cardinality": "single", "value_kind": "duration"},
        )

        await tenant["service"].update_entity_type(
            tenant["id"], "Years Experience", {"description": "how long they have worked"}
        )

        assert (
            await _column_type(engine, tenant["schema"], "subject", "years_experience")
            == "double precision"
        )
