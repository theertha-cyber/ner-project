"""training_jobs.source_scope — which workflow a training job trains from

Revision ID: 046
Revises: 045
Create Date: 2026-09-12

Manual, Automated, and Import are independent annotation workflows (nav-config, the
Manual/Automated/Import landing pages). Training previously blended every confirmed span and
imported row together regardless of which workflow produced it. `source_scope` records which
single workflow a training job was submitted for — `manual`, `automated`, `import`, or NULL for
the pre-existing "everything" behaviour — so a tenant that chose one workflow trains only on
that workflow's data, not a mix (manual-training-data-source-scoping design.md Decision 1).
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "046"
down_revision = "045"
branch_labels = None
depends_on = None

_ALLOWED = "'manual', 'automated', 'import'"


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.training_jobs "
        "ADD COLUMN IF NOT EXISTS source_scope VARCHAR(16) "
        f"CHECK (source_scope IS NULL OR source_scope IN ({_ALLOWED}))",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.training_jobs DROP COLUMN IF EXISTS source_scope",
    )
