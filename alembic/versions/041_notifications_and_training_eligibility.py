"""notifications table + training-eligibility markers

Revision ID: 041
Revises: 040
Create Date: 2026-09-09

Adds:
  * public.notifications — persistent, per-tenant notifications addressed to a role
    (or a specific user). The Tenant Admin's "annotation task completed" / "batch
    approved" messages land here rather than in a transient toast.
  * tenant_*.annotation_tasks.training_eligible_at — stamped when an annotator marks
    a task completed (their approval is final). Read by the portal to show
    "Training: Eligible" and to enable "Request training".
  * tenant_*.prelabel_batches.training_eligible_at + annotator_review_status — the
    50+ automated batch becomes training-eligible only once an annotator approves it.
    annotator_review_status is NULL until the Tenant-Admin sample sign-off routes the
    batch to annotator review.
  * tenant_*.imported_annotations already carries `reviewed`; import files become
    training-eligible per-file, tracked on a new annotation_imports header table.
"""
from alembic import op
from tenant_schema_ddl import apply_to_all_tenant_schemas

revision = "041"
down_revision = "040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.notifications (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            recipient_role VARCHAR(50),
            recipient_user_id VARCHAR,
            kind VARCHAR(64) NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT,
            resource_type VARCHAR(64),
            resource_id VARCHAR,
            read_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_tenant_role_unread "
        "ON public.notifications (tenant_id, recipient_role, read_at)"
    )

    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.annotation_tasks "
        "ADD COLUMN IF NOT EXISTS training_eligible_at TIMESTAMPTZ",
    )

    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.prelabel_batches "
        "ADD COLUMN IF NOT EXISTS annotator_review_status VARCHAR(32), "
        "ADD COLUMN IF NOT EXISTS training_eligible_at TIMESTAMPTZ",
    )

    apply_to_all_tenant_schemas(
        op,
        "CREATE TABLE IF NOT EXISTS {schema}.annotation_imports ("
        "  source_file VARCHAR PRIMARY KEY,"
        "  row_count INTEGER NOT NULL DEFAULT 0,"
        "  type_map JSONB,"
        "  training_eligible_at TIMESTAMPTZ,"
        "  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        ")",
    )


def downgrade() -> None:
    apply_to_all_tenant_schemas(op, "DROP TABLE IF EXISTS {schema}.annotation_imports")
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.prelabel_batches "
        "DROP COLUMN IF EXISTS annotator_review_status, "
        "DROP COLUMN IF EXISTS training_eligible_at",
    )
    apply_to_all_tenant_schemas(
        op,
        "ALTER TABLE {schema}.annotation_tasks DROP COLUMN IF EXISTS training_eligible_at",
    )
    op.execute("DROP TABLE IF EXISTS public.notifications")
