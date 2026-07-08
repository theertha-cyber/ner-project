"""backfill training_jobs.error_message that migration 005 intended to add

Revision ID: 016
Revises: 015
Create Date: 2026-07-08
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT",
    )


def downgrade() -> None:
    pass
