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

The backfill INSERT names `{schema}` twice, so the fan-out is a Python-side loop over every
tenant schema (as in migration 039) rather than `apply_to_all_tenant_schemas`.
"""
from alembic import op
from sqlalchemy import text

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None

_UPGRADE = [
    "ALTER TABLE {schema}.imported_annotations "
    "ADD COLUMN IF NOT EXISTS pending_mapping BOOLEAN NOT NULL DEFAULT FALSE",
    "INSERT INTO {schema}.annotation_imports (source_file, row_count, training_eligible_at) "
    "SELECT source_file, COUNT(*), NOW() FROM {schema}.imported_annotations "
    "GROUP BY source_file ON CONFLICT (source_file) DO NOTHING",
]

_DOWNGRADE = [
    "ALTER TABLE {schema}.imported_annotations DROP COLUMN IF EXISTS pending_mapping",
]


def _tenant_schemas() -> list[str]:
    rows = op.get_bind().execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname = 'tenant_template' OR nspname LIKE 'tenant\\_%' ORDER BY nspname"
        )
    ).fetchall()
    return [r[0] for r in rows]


def upgrade() -> None:
    for schema in _tenant_schemas():
        for statement in _UPGRADE:
            op.execute(statement.format(schema=f'"{schema}"'))


def downgrade() -> None:
    for schema in _tenant_schemas():
        for statement in _DOWNGRADE:
            op.execute(statement.format(schema=f'"{schema}"'))
