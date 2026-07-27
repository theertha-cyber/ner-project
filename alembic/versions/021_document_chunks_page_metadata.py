"""add page/location metadata columns to document_chunks

Revision ID: 021
Revises: 020
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            ADD COLUMN IF NOT EXISTS page_number INTEGER,
            ADD COLUMN IF NOT EXISTS char_start INTEGER,
            ADD COLUMN IF NOT EXISTS char_end INTEGER;
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
                    ALTER TABLE IF EXISTS %I.document_chunks
                        ADD COLUMN IF NOT EXISTS page_number INTEGER,
                        ADD COLUMN IF NOT EXISTS char_start INTEGER,
                        ADD COLUMN IF NOT EXISTS char_end INTEGER
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
                    ALTER TABLE IF EXISTS %I.document_chunks
                        DROP COLUMN IF EXISTS page_number,
                        DROP COLUMN IF EXISTS char_start,
                        DROP COLUMN IF EXISTS char_end
                ', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            DROP COLUMN IF EXISTS page_number,
            DROP COLUMN IF EXISTS char_start,
            DROP COLUMN IF EXISTS char_end;
    """)
