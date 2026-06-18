"""add document_id to extracted_entities

Revision ID: 008
Revises: 007
Create Date: 2026-06-17
"""
from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.extracted_entities
        ADD COLUMN IF NOT EXISTS document_id VARCHAR
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
                    ALTER TABLE %I.extracted_entities
                    ADD COLUMN IF NOT EXISTS document_id VARCHAR
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.extracted_entities
        DROP COLUMN IF EXISTS document_id
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
                    ALTER TABLE %I.extracted_entities
                    DROP COLUMN IF EXISTS document_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
