"""schema proposal Q&A-pair document reference

Revision ID: 043
Revises: 042
Create Date: 2026-09-09

A Tenant Admin may attach one question/answer document to a schema proposal. It is
uploaded through the ordinary document path as `purpose = 'qa_pair'` (a plain VARCHAR
with no CHECK, so no enum change is needed) and referenced here by id so the proposal's
inputs stay reproducible.
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.schema_proposals "
        "ADD COLUMN IF NOT EXISTS qa_pair_document_id VARCHAR",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.schema_proposals DROP COLUMN IF EXISTS qa_pair_document_id",
    )
