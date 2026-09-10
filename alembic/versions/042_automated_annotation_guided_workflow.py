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

The statements name `{schema}` more than once (the guidance table and its foreign keys),
so they are fanned out with a Python-side loop over every tenant schema rather than through
`apply_to_all_tenant_schemas`, whose single `format()` placeholder cannot express that
(the same reason migration 039 uses a hand-rolled loop).

`documents.purpose` needs no constraint change — it is a plain VARCHAR with no CHECK
(migration 022) — so the new `qa_pair` value is already accepted.
"""
from alembic import op
from sqlalchemy import text

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None

_CREATE = [
    "ALTER TABLE {schema}.prelabel_batches "
    "ADD COLUMN IF NOT EXISTS batch_kind VARCHAR(16) NOT NULL DEFAULT 'large', "
    "ADD COLUMN IF NOT EXISTS state VARCHAR(24)",
    "CREATE TABLE IF NOT EXISTS {schema}.prelabel_batch_guidance ("
    "  id VARCHAR PRIMARY KEY,"
    "  batch_id VARCHAR NOT NULL REFERENCES {schema}.prelabel_batches(id) ON DELETE CASCADE,"
    "  document_id VARCHAR NOT NULL REFERENCES {schema}.documents(id) ON DELETE CASCADE,"
    "  corrected_spans JSONB,"
    "  note TEXT,"
    "  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),"
    "  UNIQUE (batch_id, document_id)"
    ")",
    "CREATE INDEX IF NOT EXISTS idx_prelabel_batch_guidance_batch "
    "ON {schema}.prelabel_batch_guidance (batch_id)",
]

_DROP = [
    "DROP TABLE IF EXISTS {schema}.prelabel_batch_guidance",
    "ALTER TABLE {schema}.prelabel_batches "
    "DROP COLUMN IF EXISTS batch_kind, DROP COLUMN IF EXISTS state",
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
        for statement in _CREATE:
            op.execute(statement.format(schema=f'"{schema}"'))


def downgrade() -> None:
    for schema in _tenant_schemas():
        for statement in _DROP:
            op.execute(statement.format(schema=f'"{schema}"'))
