"""add reviewed/reviewed_at/reviewed_by columns to imported_annotations

Revision ID: 017
Revises: 016
Create Date: 2026-07-08
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.imported_annotations "
        "ADD COLUMN IF NOT EXISTS reviewed BOOLEAN NOT NULL DEFAULT FALSE, "
        "ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ, "
        "ADD COLUMN IF NOT EXISTS reviewed_by VARCHAR",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.imported_annotations "
        "DROP COLUMN IF EXISTS reviewed, "
        "DROP COLUMN IF EXISTS reviewed_at, "
        "DROP COLUMN IF EXISTS reviewed_by",
    )
