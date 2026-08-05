"""add chat_messages.response_time_ms

Revision ID: 033
Revises: 032
Create Date: 2026-08-05
"""
from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
        ADD COLUMN IF NOT EXISTS response_time_ms INTEGER NULL
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
                    ALTER TABLE %I.chat_messages
                    ADD COLUMN IF NOT EXISTS response_time_ms INTEGER NULL
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
                EXECUTE format('ALTER TABLE %I.chat_messages DROP COLUMN IF EXISTS response_time_ms', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("ALTER TABLE tenant_template.chat_messages DROP COLUMN IF EXISTS response_time_ms")
