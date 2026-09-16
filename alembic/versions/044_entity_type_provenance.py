"""entity type provenance

Revision ID: 044
Revises: 043
Create Date: 2026-09-10

`provenance` records how an entity type came to exist: `manual` (created by hand — the
default and the backfill value for every existing row), `suggested` (created by approving
an LLM schema-proposal candidate), or `imported` (created while mapping an unknown type
during annotation import). Assigned at creation, never changed by an update.
`provenance_ref` optionally names the schema version or source file.

`server_default` — following `cardinality` (migration 037) — because
`entity_service.create_entity_type` inserts through an explicit column list; a Python-side
default would not fire and the NOT NULL insert would fail. `public`, not a tenant schema:
`entity_definitions` is a shared table scoped by `tenant_id`.
"""
from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.entity_definitions "
        "ADD COLUMN IF NOT EXISTS provenance VARCHAR(16) NOT NULL DEFAULT 'manual', "
        "ADD COLUMN IF NOT EXISTS provenance_ref VARCHAR(255)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.entity_definitions "
        "DROP COLUMN IF EXISTS provenance, "
        "DROP COLUMN IF EXISTS provenance_ref"
    )
