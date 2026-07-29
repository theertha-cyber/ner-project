"""add run_number to training_jobs and model_versions

Revision ID: 025
Revises: 024
Create Date: 2026-07-29
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS run_number INTEGER",
    )
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.model_versions ADD COLUMN IF NOT EXISTS run_number INTEGER",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.training_jobs DROP COLUMN IF EXISTS run_number",
    )
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.model_versions DROP COLUMN IF EXISTS run_number",
    )
