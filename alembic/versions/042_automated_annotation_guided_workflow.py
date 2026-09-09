"""automated annotation guided workflow: batch_kind, derived state, guidance

Revision ID: 042
Revises: 041
Create Date: 2026-09-09

Adds, per tenant schema (additive only):
  * prelabel_batches.batch_kind — 'initial' (<=5 docs, Tenant-Admin reviewed) or 'large'
    (the main batch, Annotator-Admin reviewed). Existing rows were all effectively large.
  * prelabel_batches.state — the named lifecycle the portal renders
    (queued/processing/completed/partially_completed/failed), derived from per-document
    outcomes and cached here once the job reaches a terminal state.
  * prelabel_batch_guidance — a Tenant Admin's corrections and notes from reviewing an
    `initial` batch, injected into the prompt for the subsequent `large` batch.

`documents.purpose` needs no constraint change — it is a plain VARCHAR with no CHECK
(migration 022) — so the new `qa_pair` value is already accepted.
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.prelabel_batches "
        "ADD COLUMN IF NOT EXISTS batch_kind VARCHAR(16) NOT NULL DEFAULT 'large', "
        "ADD COLUMN IF NOT EXISTS state VARCHAR(24)",
    )
    apply_to_all_tenant_schemas(
        op,
        "CREATE TABLE IF NOT EXISTS {schema}.prelabel_batch_guidance ("
        "  id VARCHAR PRIMARY KEY,"
        "  batch_id VARCHAR NOT NULL REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,"
        "  document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,"
        "  corrected_spans JSONB,"
        "  note TEXT,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
        "  UNIQUE (batch_id, document_id)"
        ")",
    )
    apply_to_all_tenant_schemas(
        op,
        "CREATE INDEX IF NOT EXISTS idx_prelabel_batch_guidance_batch "
        "ON {schema}.prelabel_batch_guidance (batch_id)",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(op, "DROP TABLE IF EXISTS {schema}.prelabel_batch_guidance")
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.prelabel_batches "
        "DROP COLUMN IF EXISTS batch_kind, "
        "DROP COLUMN IF EXISTS state",
    )
