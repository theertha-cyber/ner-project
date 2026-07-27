"""add purpose column to documents and document_chunks

Revision ID: 022
Revises: 021
Create Date: 2026-07-26
"""
from alembic import op
import sqlalchemy as sa

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.documents
            ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) NOT NULL DEFAULT 'query';
    """)
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            ADD COLUMN IF NOT EXISTS purpose VARCHAR(20);
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
                        ADD COLUMN IF NOT EXISTS purpose VARCHAR(20) NOT NULL DEFAULT ''query''
                ', schema_name);
                EXECUTE format('
                    ALTER TABLE IF EXISTS %I.document_chunks
                        ADD COLUMN IF NOT EXISTS purpose VARCHAR(20)
                ', schema_name);
                IF to_regclass(format('%I.documents', schema_name)) IS NOT NULL
                   AND to_regclass(format('%I.annotation_tasks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        UPDATE %I.documents SET purpose = ''training''
                        WHERE id IN (SELECT document_id FROM %I.annotation_tasks)
                    ', schema_name, schema_name);
                END IF;
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
                        DROP COLUMN IF EXISTS purpose
                ', schema_name);
                EXECUTE format('
                    ALTER TABLE IF EXISTS %I.document_chunks
                        DROP COLUMN IF EXISTS purpose
                ', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("""
        ALTER TABLE tenant_template.documents
            DROP COLUMN IF EXISTS purpose;
    """)
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            DROP COLUMN IF EXISTS purpose;
    """)
