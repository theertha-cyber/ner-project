"""relax training_jobs.hyperparams to nullable

Revision ID: 031
Revises: 030
Create Date: 2026-08-05
"""
from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.training_jobs
            ALTER COLUMN hyperparams DROP NOT NULL,
            ALTER COLUMN hyperparams DROP DEFAULT;
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
                    ALTER TABLE IF EXISTS %I.training_jobs
                        ALTER COLUMN hyperparams DROP NOT NULL,
                        ALTER COLUMN hyperparams DROP DEFAULT
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE tenant_template.training_jobs SET hyperparams = '{}'::jsonb WHERE hyperparams IS NULL;
        ALTER TABLE tenant_template.training_jobs
            ALTER COLUMN hyperparams SET DEFAULT '{}'::jsonb,
            ALTER COLUMN hyperparams SET NOT NULL;
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
                    UPDATE %I.training_jobs SET hyperparams = ''{}''::jsonb WHERE hyperparams IS NULL;
                    ALTER TABLE IF EXISTS %I.training_jobs
                        ALTER COLUMN hyperparams SET DEFAULT ''{}''::jsonb,
                        ALTER COLUMN hyperparams SET NOT NULL
                ', schema_name, schema_name);
            END LOOP;
        END $$;
    """)
