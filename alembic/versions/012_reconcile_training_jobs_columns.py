"""reconcile training_jobs and model_versions columns between 002 and 005

Revision ID: 012
Revises: 011
Create Date: 2026-06-29
"""
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None

TEMPLATE_ALTER_TRAINING_JOBS = """
    ALTER TABLE tenant_template.training_jobs
        ADD COLUMN IF NOT EXISTS metrics JSONB,
        ADD COLUMN IF NOT EXISTS hyperparams JSONB,
        ADD COLUMN IF NOT EXISTS current_epoch INTEGER,
        ADD COLUMN IF NOT EXISTS current_loss FLOAT,
        ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR,
        ADD COLUMN IF NOT EXISTS model_version_id VARCHAR
"""

TEMPLATE_ALTER_MODEL_VERSIONS = """
    ALTER TABLE tenant_template.model_versions
        ADD COLUMN IF NOT EXISTS metrics JSONB
"""


def upgrade() -> None:
    op.execute(TEMPLATE_ALTER_TRAINING_JOBS)
    op.execute(TEMPLATE_ALTER_MODEL_VERSIONS)
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('
                    ALTER TABLE %I.training_jobs
                        ADD COLUMN IF NOT EXISTS metrics JSONB,
                        ADD COLUMN IF NOT EXISTS hyperparams JSONB,
                        ADD COLUMN IF NOT EXISTS current_epoch INTEGER,
                        ADD COLUMN IF NOT EXISTS current_loss FLOAT,
                        ADD COLUMN IF NOT EXISTS celery_task_id VARCHAR,
                        ADD COLUMN IF NOT EXISTS model_version_id VARCHAR
                ', schema_name);

                EXECUTE format('
                    ALTER TABLE %I.model_versions
                        ADD COLUMN IF NOT EXISTS metrics JSONB
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%'
            LOOP
                EXECUTE format('
                    ALTER TABLE %I.training_jobs
                        DROP COLUMN IF EXISTS metrics,
                        DROP COLUMN IF EXISTS hyperparams,
                        DROP COLUMN IF EXISTS current_epoch,
                        DROP COLUMN IF EXISTS current_loss,
                        DROP COLUMN IF EXISTS celery_task_id,
                        DROP COLUMN IF EXISTS model_version_id
                ', schema_name);

                EXECUTE format('
                    ALTER TABLE %I.model_versions
                        DROP COLUMN IF EXISTS metrics
                ', schema_name);
            END LOOP;
        END $$;
    """)
