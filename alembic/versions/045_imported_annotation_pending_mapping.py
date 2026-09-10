"""imported annotations: hold unmapped-type rows instead of dropping them

Revision ID: 045
Revises: 044
Create Date: 2026-09-10

`pending_mapping` marks an imported row whose tags reference an entity type not yet
defined for the tenant. Such rows used to be dropped at import; they are now stored and
flagged, resolved by the type-map endpoint. A file is training-eligible
(`annotation_imports.training_eligible_at`) once none of its rows are pending.

The `annotation_imports` header table already exists (migration 041). This migration
backfills one header row per distinct existing `source_file` — those rows only ever
contained known types, so they are `pending_mapping = false` and immediately eligible.
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.imported_annotations "
        "ADD COLUMN IF NOT EXISTS pending_mapping BOOLEAN NOT NULL DEFAULT FALSE",
    )
    apply_to_all_tenant_schemas(
        op,
        "INSERT INTO {schema}.annotation_imports (source_file, row_count, training_eligible_at) "
        "SELECT source_file, COUNT(*), NOW() "
        "FROM {schema}.imported_annotations GROUP BY source_file "
        "ON CONFLICT (source_file) DO NOTHING",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.imported_annotations DROP COLUMN IF EXISTS pending_mapping",
    )
