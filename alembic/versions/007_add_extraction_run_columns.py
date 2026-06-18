"""add status progress columns to extraction_runs

Revision ID: 007
Revises: 006
Create Date: 2026-06-17
"""
from alembic import op

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Update template schema for new tenants
    op.execute("""
        ALTER TABLE tenant_template.extraction_runs
        ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS total_documents INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS processed_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS skipped_count INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE tenant_template.extraction_runs
        ALTER COLUMN document_id DROP NOT NULL
    """)

    # Apply to existing tenant schemas
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
                    ALTER TABLE %I.extraction_runs
                    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ,
                    ADD COLUMN IF NOT EXISTS total_documents INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS processed_count INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS skipped_count INTEGER NOT NULL DEFAULT 0,
                    ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0
                ', schema_name);
                EXECUTE format('
                    ALTER TABLE %I.extraction_runs
                    ALTER COLUMN document_id DROP NOT NULL
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.extraction_runs
        DROP COLUMN IF EXISTS completed_at,
        DROP COLUMN IF EXISTS total_documents,
        DROP COLUMN IF EXISTS processed_count,
        DROP COLUMN IF EXISTS skipped_count,
        DROP COLUMN IF EXISTS failed_count
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
                    ALTER TABLE %I.extraction_runs
                    DROP COLUMN IF EXISTS completed_at,
                    DROP COLUMN IF EXISTS total_documents,
                    DROP COLUMN IF EXISTS processed_count,
                    DROP COLUMN IF EXISTS skipped_count,
                    DROP COLUMN IF EXISTS failed_count
                ', schema_name);
            END LOOP;
        END $$;
    """)
