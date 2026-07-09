"""reconcile model_versions columns between 002 and 005/006

Revision ID: 018
Revises: 017
Create Date: 2026-07-09
"""
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.model_versions
            ADD COLUMN IF NOT EXISTS version_number INTEGER,
            ADD COLUMN IF NOT EXISTS artifact_path TEXT,
            ADD COLUMN IF NOT EXISTS mlflow_run_id VARCHAR
    """)

    op.execute("""
        UPDATE tenant_template.model_versions
        SET version_number = version
        WHERE version_number IS NULL AND version IS NOT NULL
    """)

    op.execute("""
        UPDATE tenant_template.model_versions
        SET artifact_path = artifact_uri
        WHERE artifact_path IS NULL AND artifact_uri IS NOT NULL
    """)

    op.execute("""
        ALTER TABLE tenant_template.model_versions
            ALTER COLUMN version DROP NOT NULL
    """)

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
                    ALTER TABLE %I.model_versions
                        ADD COLUMN IF NOT EXISTS version_number INTEGER,
                        ADD COLUMN IF NOT EXISTS artifact_path TEXT,
                        ADD COLUMN IF NOT EXISTS mlflow_run_id VARCHAR
                ', schema_name);

                EXECUTE format('
                    UPDATE %I.model_versions
                    SET version_number = version
                    WHERE version_number IS NULL AND version IS NOT NULL
                ', schema_name);

                EXECUTE format('
                    UPDATE %I.model_versions
                    SET artifact_path = artifact_uri
                    WHERE artifact_path IS NULL AND artifact_uri IS NOT NULL
                ', schema_name);

                EXECUTE format('
                    ALTER TABLE %I.model_versions
                        ALTER COLUMN version DROP NOT NULL
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.model_versions
            DROP COLUMN IF EXISTS version_number,
            DROP COLUMN IF EXISTS artifact_path,
            DROP COLUMN IF EXISTS mlflow_run_id
    """)

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
                    ALTER TABLE %I.model_versions
                        DROP COLUMN IF EXISTS version_number,
                        DROP COLUMN IF EXISTS artifact_path,
                        DROP COLUMN IF EXISTS mlflow_run_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
