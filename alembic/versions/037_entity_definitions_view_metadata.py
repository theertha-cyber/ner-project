"""view-layer metadata on entity_definitions

The read model for extracted entities is moving from raw EAV (`document_entities`, queried
directly by the Text-to-SQL generator) to a generated per-tenant view layer. Two facts about an
entity type decide how it renders, and neither is derivable from what the table already holds,
so both are recorded here.

`cardinality` decides whether an entity type becomes a pivoted column on the tenant's `subject`
view (`single`) or its own child view (`multi`). Every pre-existing row defaults to `multi`, and
that default is chosen rather than guessed: a genuinely single-valued entity rendered as a child
view is merely inconvenient — one extra join — whereas a genuinely multi-valued entity wrongly
marked `single` is collapsed by the pivot's `MAX()` aggregate and every value but one disappears
with no error. The safe backfill is the one whose failure mode is visible.

`sql_identifier` is the Postgres identifier for that entity type's view. It is assigned once and
never changed, so renaming an entity type's display name does not rename its view, break a saved
query, or orphan the old one. It is backfilled from `name` through the same
`to_sql_identifier` the view generator uses — imported, not reimplemented, because a second copy
of the slug rule would eventually drift and the migration would then record identifiers for
views the generator never creates.

Uniqueness is `(tenant_id, sql_identifier)`, not `sql_identifier` alone: views live in separate
tenant schemas (ADR-001), so two tenants sharing `e_skill` is correct rather than a collision.
The index is partial because `sql_identifier` stays NULL for rows created between this migration
and the entity-CRUD wiring that assigns it — NULL means "not yet rendered", and the generator
skips such rows rather than inventing a name at read time.

`public.entity_definitions` is a shared table, so this migration deliberately has no
`tenant_%` loop and creates no views. View DDL is the reconciler's job, and nothing calls the
reconciler yet.

Revision ID: 037
Revises: 036
Create Date: 2026-08-19
"""
from collections import defaultdict

from alembic import op
from sqlalchemy import text

from src.shared.entity_views import CARDINALITIES, CARDINALITY_MULTI, to_sql_identifier

revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None

_ADD_COLUMNS = f"""
    ALTER TABLE public.entity_definitions
        ADD COLUMN IF NOT EXISTS cardinality VARCHAR(16) NOT NULL DEFAULT '{CARDINALITY_MULTI}',
        ADD COLUMN IF NOT EXISTS sql_identifier VARCHAR(63)
"""

# VARCHAR + CHECK rather than an ENUM, matching `processing_mode` in `036`: adding a value to a
# Postgres ENUM is itself a migration, and the vocabulary here is expected to grow.
_ADD_CHECK = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_entity_definitions_cardinality'
              AND conrelid = 'public.entity_definitions'::regclass
        ) THEN
            ALTER TABLE public.entity_definitions
                ADD CONSTRAINT ck_entity_definitions_cardinality
                CHECK (cardinality IN (%s));
        END IF;
    END $$;
""" % ", ".join(f"'{value}'" for value in sorted(CARDINALITIES))

_ADD_INDEX = """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_definitions_tenant_sql_identifier
        ON public.entity_definitions (tenant_id, sql_identifier)
        WHERE sql_identifier IS NOT NULL
"""

_DROP_INDEX = "DROP INDEX IF EXISTS public.uq_entity_definitions_tenant_sql_identifier"

_DROP_CHECK = """
    ALTER TABLE public.entity_definitions
        DROP CONSTRAINT IF EXISTS ck_entity_definitions_cardinality
"""

_DROP_COLUMNS = """
    ALTER TABLE public.entity_definitions
        DROP COLUMN IF EXISTS cardinality,
        DROP COLUMN IF EXISTS sql_identifier
"""


def _backfill_sql_identifiers() -> None:
    """Assigns every existing row an identifier, resolving collisions within each tenant.

    Runs before the unique index is created, so a tenant that happens to hold two entity types
    whose names slug to the same base (`"Vendor Name"` and `"vendor-name"`) is resolved into
    `e_vendor_name` and `e_vendor_name_2` rather than failing the migration. Rows are ordered
    deterministically so a re-run on the same data assigns the same identifiers."""
    conn = op.get_bind()

    taken_by_tenant: dict[str, set[str]] = defaultdict(set)
    for tenant_id, identifier in conn.execute(
        text(
            "SELECT tenant_id, sql_identifier FROM public.entity_definitions "
            "WHERE sql_identifier IS NOT NULL"
        )
    ):
        taken_by_tenant[tenant_id].add(identifier)

    rows = conn.execute(
        text(
            "SELECT id, tenant_id, name FROM public.entity_definitions "
            "WHERE sql_identifier IS NULL "
            "ORDER BY tenant_id, created_at NULLS FIRST, id"
        )
    ).fetchall()

    for row in rows:
        identifier = to_sql_identifier(row.name, taken_by_tenant[row.tenant_id])
        taken_by_tenant[row.tenant_id].add(identifier)
        conn.execute(
            text(
                "UPDATE public.entity_definitions SET sql_identifier = :identifier "
                "WHERE id = :id"
            ),
            {"identifier": identifier, "id": row.id},
        )


def upgrade() -> None:
    op.execute(_ADD_COLUMNS)
    op.execute(_ADD_CHECK)
    _backfill_sql_identifiers()
    op.execute(_ADD_INDEX)


def downgrade() -> None:
    op.execute(_DROP_INDEX)
    op.execute(_DROP_CHECK)
    op.execute(_DROP_COLUMNS)
