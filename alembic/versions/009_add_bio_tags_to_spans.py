"""add bio_tags to spans

Revision ID: 009
Revises: 008
Create Date: 2026-06-22
"""
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.spans
        ADD COLUMN IF NOT EXISTS bio_tags TEXT[]
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
                    ALTER TABLE %I.spans
                    ADD COLUMN IF NOT EXISTS bio_tags TEXT[]
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.spans
        DROP COLUMN IF EXISTS bio_tags
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
                    ALTER TABLE %I.spans
                    DROP COLUMN IF EXISTS bio_tags
                ', schema_name);
            END LOOP;
        END $$;
    """)
