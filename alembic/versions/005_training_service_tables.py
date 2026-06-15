"""add training service tables to tenant_template schema

Revision ID: 005
Revises: 004
Create Date: 2026-06-10
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.training_jobs (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'queued',
            hyperparams JSONB NOT NULL DEFAULT '{}',
            current_epoch INTEGER,
            current_loss FLOAT,
            metrics JSONB,
            error_message TEXT,
            model_version_id VARCHAR,
            celery_task_id VARCHAR,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_training_jobs_tenant_status
            ON tenant_template.training_jobs (tenant_id, status);
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.model_versions (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            version_number INTEGER NOT NULL,
            training_job_id VARCHAR,
            status VARCHAR(20) NOT NULL DEFAULT 'training',
            metrics JSONB,
            artifact_path TEXT,
            promoted_at TIMESTAMPTZ,
            archived_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_versions_tenant_status
            ON tenant_template.model_versions (tenant_id, status);
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_model_versions_tenant_promoted
            ON tenant_template.model_versions (tenant_id)
            WHERE status = 'promoted';
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_model_versions_tenant_promoted")
    op.execute("DROP INDEX IF EXISTS idx_model_versions_tenant_status")
    op.execute("DROP INDEX IF EXISTS idx_training_jobs_tenant_status")
    op.execute("DROP TABLE IF EXISTS tenant_template.model_versions")
    op.execute("DROP TABLE IF EXISTS tenant_template.training_jobs")
