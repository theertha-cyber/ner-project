"""add uploaded_by column to documents

Revision ID: 030
Revises: 029
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.documents
            ADD COLUMN IF NOT EXISTS uploaded_by VARCHAR(64);
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
                    ALTER TABLE IF EXISTS %I.documents
                        ADD COLUMN IF NOT EXISTS uploaded_by VARCHAR(64)
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
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('
                    ALTER TABLE IF EXISTS %I.documents
                        DROP COLUMN IF EXISTS uploaded_by
                ', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("""
        ALTER TABLE tenant_template.documents
            DROP COLUMN IF EXISTS uploaded_by;
    """)
