"""add missing created_at/failed_at columns to training_jobs and model_versions

Revision ID: 013
Revises: 012
Create Date: 2026-06-29
"""
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.training_jobs
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
            ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ
    """)

    op.execute("""
        ALTER TABLE tenant_template.model_versions
            ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()
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
                    ALTER TABLE %I.training_jobs
                        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
                        ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ
                ', schema_name);

                EXECUTE format('
                    ALTER TABLE %I.model_versions
                        ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW()
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
                EXECUTE format('ALTER TABLE %I.training_jobs DROP COLUMN IF EXISTS created_at', schema_name);
                EXECUTE format('ALTER TABLE %I.training_jobs DROP COLUMN IF EXISTS failed_at', schema_name);
                EXECUTE format('ALTER TABLE %I.model_versions DROP COLUMN IF EXISTS created_at', schema_name);
            END LOOP;
        END $$;
    """)
