"""Migration 037: view-layer metadata on public.entity_definitions.

Follows the `importlib` + `MigrationContext`/`Operations` pattern used by
`test_tenant_schema_reconciliation.py`, so the migration's own `upgrade()` runs rather than a
paraphrase of it — the backfill is the part most likely to drift from the generator, and only
running the real function catches that.
"""

import importlib.util
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, ProgrammingError

from src.shared.config import settings
from src.shared.entity_views import GENERATED_IDENTIFIER_RE, to_sql_identifier

_MIGRATION_PATH = os.path.join(
    os.path.dirname(__file__), "..", "alembic", "versions", "037_entity_definitions_view_metadata.py"
)
_spec = importlib.util.spec_from_file_location("migration_037_entity_view_metadata", _MIGRATION_PATH)
migration_037 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration_037)


def _run(sync_engine, direction):
    with sync_engine.connect() as connection:
        ctx = MigrationContext.configure(connection)
        op = Operations(ctx)
        original_op = migration_037.op
        migration_037.op = op
        try:
            getattr(migration_037, direction)()
        finally:
            migration_037.op = original_op
        connection.commit()


@pytest.fixture
def sync_engine():
    engine = create_engine(settings.database_url_sync)
    yield engine
    engine.dispose()


@pytest.fixture
def migrated(sync_engine, setup_database):
    """`entity_definitions` at `036`, then upgraded to `037`.

    `setup_database` creates the table from the ORM models, which already declare the two new
    columns — so they are dropped first to reproduce the pre-`037` shape the migration actually
    encounters."""
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE public.entity_definitions "
                "DROP CONSTRAINT IF EXISTS ck_entity_definitions_cardinality"
            )
        )
        conn.execute(
            text("DROP INDEX IF EXISTS public.uq_entity_definitions_tenant_sql_identifier")
        )
        conn.execute(
            text(
                "ALTER TABLE public.entity_definitions "
                "DROP COLUMN IF EXISTS cardinality, DROP COLUMN IF EXISTS sql_identifier"
            )
        )
    yield sync_engine


def _insert_definition(conn, tenant_id, name, definition_id=None):
    definition_id = definition_id or str(uuid.uuid4())
    conn.execute(
        text(
            "INSERT INTO public.entity_definitions (id, tenant_id, name, version, is_active) "
            "VALUES (:id, :tenant_id, :name, 1, true)"
        ),
        {"id": definition_id, "tenant_id": tenant_id, "name": name},
    )
    return definition_id


def _columns(conn):
    rows = conn.execute(
        text(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns WHERE table_schema = 'public' "
            "AND table_name = 'entity_definitions'"
        )
    )
    return {r[0]: (r[1], r[2], r[3]) for r in rows.fetchall()}


class TestUpgrade:
    """verification.md row 34"""

    def test_preexisting_row_defaults_to_multi_with_identifier(self, migrated):
        with migrated.begin() as conn:
            definition_id = _insert_definition(conn, "test-tenant", "Skills & Tools")

        _run(migrated, "upgrade")

        with migrated.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT cardinality, sql_identifier FROM public.entity_definitions "
                    "WHERE id = :id"
                ),
                {"id": definition_id},
            ).fetchone()

        assert row.cardinality == "multi"
        assert row.sql_identifier == "e_skills_tools"
        assert GENERATED_IDENTIFIER_RE.fullmatch(row.sql_identifier)

    def test_columns_have_the_declared_shape(self, migrated):
        _run(migrated, "upgrade")
        with migrated.connect() as conn:
            columns = _columns(conn)

        assert columns["cardinality"][1] == "NO"  # NOT NULL
        assert "multi" in (columns["cardinality"][2] or "")
        assert columns["sql_identifier"][1] == "YES"  # nullable until entity CRUD assigns it

    def test_upgrade_is_rerunnable(self, migrated):
        with migrated.begin() as conn:
            _insert_definition(conn, "test-tenant", "Vendor Name")
        _run(migrated, "upgrade")
        with migrated.connect() as conn:
            first = conn.execute(
                text("SELECT sql_identifier FROM public.entity_definitions")
            ).scalar()

        _run(migrated, "upgrade")
        with migrated.connect() as conn:
            second = conn.execute(
                text("SELECT sql_identifier FROM public.entity_definitions")
            ).scalar()

        assert first == second == "e_vendor_name"


class TestConstraints:
    """verification.md rows 35-36"""

    def test_cardinality_check_constraint_rejects_unknown(self, migrated):
        _run(migrated, "upgrade")
        with pytest.raises((IntegrityError, ProgrammingError)):
            with migrated.begin() as conn:
                definition_id = _insert_definition(conn, "test-tenant", "Bad Cardinality")
                conn.execute(
                    text(
                        "UPDATE public.entity_definitions SET cardinality = 'many' WHERE id = :id"
                    ),
                    {"id": definition_id},
                )

    @pytest.mark.parametrize("cardinality", ["single", "multi"])
    def test_known_cardinalities_accepted(self, migrated, cardinality):
        _run(migrated, "upgrade")
        with migrated.begin() as conn:
            definition_id = _insert_definition(conn, "test-tenant", f"Ok {cardinality}")
            conn.execute(
                text("UPDATE public.entity_definitions SET cardinality = :c WHERE id = :id"),
                {"c": cardinality, "id": definition_id},
            )

    def test_sql_identifier_unique_per_tenant_not_globally(self, migrated):
        _run(migrated, "upgrade")

        # Two tenants may hold the same identifier — their views live in separate schemas.
        with migrated.begin() as conn:
            a = _insert_definition(conn, "test-tenant", "Skill")
            b = _insert_definition(conn, "tenant-b", "Skill")
            conn.execute(
                text("UPDATE public.entity_definitions SET sql_identifier = 'e_skill' WHERE id IN (:a, :b)"),
                {"a": a, "b": b},
            )

        # A second row for the same tenant may not.
        with pytest.raises(IntegrityError):
            with migrated.begin() as conn:
                duplicate = _insert_definition(conn, "test-tenant", "Skill Again")
                conn.execute(
                    text(
                        "UPDATE public.entity_definitions SET sql_identifier = 'e_skill' "
                        "WHERE id = :id"
                    ),
                    {"id": duplicate},
                )

    def test_null_sql_identifier_is_not_constrained(self, migrated):
        # The index is partial: rows created before entity CRUD assigns an identifier are
        # legitimately NULL, and several NULLs per tenant must be allowed.
        _run(migrated, "upgrade")
        with migrated.begin() as conn:
            _insert_definition(conn, "test-tenant", "One")
            _insert_definition(conn, "test-tenant", "Two")
            conn.execute(text("UPDATE public.entity_definitions SET sql_identifier = NULL"))


class TestBackfillMatchesGenerator:
    """The anti-drift guard: a second slug implementation would orphan views silently."""

    def test_backfill_equals_to_sql_identifier(self, migrated):
        names = ["Skills & Tools", "skills-tools", "2024 Revenue", "select", "", "Café Región"]
        ids = []
        with migrated.begin() as conn:
            for index, name in enumerate(names):
                # Ids are ordered so `created_at` ties break the same way the migration orders.
                ids.append(_insert_definition(conn, "test-tenant", name, f"def-{index:02d}"))

        _run(migrated, "upgrade")

        with migrated.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, name, sql_identifier FROM public.entity_definitions "
                    "WHERE tenant_id = 'test-tenant' ORDER BY created_at NULLS FIRST, id"
                )
            ).fetchall()

        taken: set[str] = set()
        for row in rows:
            expected = to_sql_identifier(row.name, taken)
            taken.add(expected)
            assert row.sql_identifier == expected, row.name

    def test_colliding_names_within_a_tenant_are_resolved(self, migrated):
        with migrated.begin() as conn:
            _insert_definition(conn, "test-tenant", "Vendor Name", "def-00")
            _insert_definition(conn, "test-tenant", "vendor-name", "def-01")

        _run(migrated, "upgrade")

        with migrated.connect() as conn:
            identifiers = [
                r[0]
                for r in conn.execute(
                    text(
                        "SELECT sql_identifier FROM public.entity_definitions "
                        "WHERE tenant_id = 'test-tenant' ORDER BY id"
                    )
                ).fetchall()
            ]

        assert identifiers == ["e_vendor_name", "e_vendor_name_2"]


class TestDowngrade:
    def test_downgrade_removes_columns_index_and_constraint(self, migrated):
        _run(migrated, "upgrade")
        _run(migrated, "downgrade")

        with migrated.connect() as conn:
            columns = _columns(conn)
            index = conn.execute(
                text(
                    "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' "
                    "AND indexname = 'uq_entity_definitions_tenant_sql_identifier'"
                )
            ).fetchone()
            constraint = conn.execute(
                text(
                    "SELECT 1 FROM pg_constraint "
                    "WHERE conname = 'ck_entity_definitions_cardinality'"
                )
            ).fetchone()

        assert "cardinality" not in columns
        assert "sql_identifier" not in columns
        assert index is None
        assert constraint is None

    def test_upgrade_after_downgrade_restores_state(self, migrated):
        with migrated.begin() as conn:
            _insert_definition(conn, "test-tenant", "Skill")
        _run(migrated, "upgrade")
        _run(migrated, "downgrade")
        _run(migrated, "upgrade")

        with migrated.connect() as conn:
            row = conn.execute(
                text("SELECT cardinality, sql_identifier FROM public.entity_definitions")
            ).fetchone()

        assert row.cardinality == "multi"
        assert row.sql_identifier == "e_skill"
