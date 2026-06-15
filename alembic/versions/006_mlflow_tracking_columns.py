"""add mlflow tracking columns to training tables

Revision ID: 006
Revises: 005
Create Date: 2026-06-12
"""
from alembic import op

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.training_jobs
        ADD COLUMN IF NOT EXISTS mlflow_run_id VARCHAR,
        ADD COLUMN IF NOT EXISTS mlflow_run_url TEXT;
    """)

    op.execute("""
        ALTER TABLE tenant_template.model_versions
        ADD COLUMN IF NOT EXISTS mlflow_run_id VARCHAR;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE tenant_template.training_jobs DROP COLUMN IF EXISTS mlflow_run_id")
    op.execute("ALTER TABLE tenant_template.training_jobs DROP COLUMN IF EXISTS mlflow_run_url")
    op.execute("ALTER TABLE tenant_template.model_versions DROP COLUMN IF EXISTS mlflow_run_id")
