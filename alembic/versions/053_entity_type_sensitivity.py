"""entity type sensitivity classification

`sensitivity` classifies whether an entity type's real values may reach an external LLM
provider during pre-labeling: `open` (may be sent externally — the default, and the backfill
value for every existing row, since that is the unrestricted treatment every entity type has
always had), `pattern` (a fixed, regex-matchable shape such as an SSN or phone number — detected
locally via the type's own `validation_rule`), or `local_only` (free text with no fixed shape,
such as a person's name — detected locally via the tenant's own hosted extraction model, never
sent externally).

This migration is additive and inert on its own: nothing reads `sensitivity` yet (see the
`automated-annotation-pii-masking` change). `open` is chosen as both the default and the backfill
value because it is the value that accurately describes today's actual, unchanged behavior — not
a judgment call about which existing tenants should be protected once masking ships.

VARCHAR + CHECK rather than an ENUM, matching `cardinality` (migration `037`) and `processing_mode`
(migration `036`): the vocabulary here may grow, and adding a value to a Postgres ENUM is itself a
migration. `public`, not a tenant schema: `entity_definitions` is a shared table scoped by
`tenant_id`, same as `cardinality` and `provenance`.

Revision ID: 053
Revises: 052
Create Date: 2026-09-17

NOTE (renumbered 2026-09-18): originally revision "049" (down_revision "048"), renumbered ahead
of the main merge to resolve a collision with 049_tenant_data_source_connections.py.
"""
from alembic import op

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

SENSITIVITY_VALUES = ("open", "pattern", "local_only")
DEFAULT_SENSITIVITY = "open"

_ADD_COLUMN = (
    "ALTER TABLE public.entity_definitions "
    f"ADD COLUMN IF NOT EXISTS sensitivity VARCHAR(16) NOT NULL DEFAULT '{DEFAULT_SENSITIVITY}'"
)

_ADD_CHECK = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_entity_definitions_sensitivity'
              AND conrelid = 'public.entity_definitions'::regclass
        ) THEN
            ALTER TABLE public.entity_definitions
                ADD CONSTRAINT ck_entity_definitions_sensitivity
                CHECK (sensitivity IN (%s));
        END IF;
    END $$;
""" % ", ".join(f"'{value}'" for value in SENSITIVITY_VALUES)

_DROP_CHECK = (
    "ALTER TABLE public.entity_definitions "
    "DROP CONSTRAINT IF EXISTS ck_entity_definitions_sensitivity"
)

_DROP_COLUMN = "ALTER TABLE public.entity_definitions DROP COLUMN IF EXISTS sensitivity"


def upgrade() -> None:
    op.execute(_ADD_COLUMN)
    op.execute(_ADD_CHECK)


def downgrade() -> None:
    op.execute(_DROP_CHECK)
    op.execute(_DROP_COLUMN)
