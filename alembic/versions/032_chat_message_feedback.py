"""add chat_message_feedback table and chat_messages.answer_kind/model_version

Revision ID: 032
Revises: 031
Create Date: 2026-08-05
"""
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
        ADD COLUMN IF NOT EXISTS answer_kind TEXT NOT NULL DEFAULT 'answer'
    """)
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
        ADD COLUMN IF NOT EXISTS model_version TEXT NULL
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.chat_message_feedback (
            id VARCHAR PRIMARY KEY,
            message_id VARCHAR NOT NULL UNIQUE REFERENCES tenant_template.chat_messages(id) ON DELETE CASCADE,
            tenant_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            rating TEXT NOT NULL CHECK (rating IN ('up', 'down')),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
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
                    ADD COLUMN IF NOT EXISTS answer_kind TEXT NOT NULL DEFAULT ''answer''
                ', schema_name);

                EXECUTE format('
                    ALTER TABLE %I.chat_messages
                    ADD COLUMN IF NOT EXISTS model_version TEXT NULL
                ', schema_name);

                EXECUTE format('
                    CREATE TABLE IF NOT EXISTS %I.chat_message_feedback (
                        id VARCHAR PRIMARY KEY,
                        message_id VARCHAR NOT NULL UNIQUE REFERENCES %I.chat_messages(id) ON DELETE CASCADE,
                        tenant_id VARCHAR NOT NULL,
                        user_id VARCHAR NOT NULL,
                        rating TEXT NOT NULL CHECK (rating IN (''up'', ''down'')),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                ', schema_name, schema_name);
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
                EXECUTE format('DROP TABLE IF EXISTS %I.chat_message_feedback CASCADE', schema_name);
                EXECUTE format('ALTER TABLE %I.chat_messages DROP COLUMN IF EXISTS answer_kind', schema_name);
                EXECUTE format('ALTER TABLE %I.chat_messages DROP COLUMN IF EXISTS model_version', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("DROP TABLE IF EXISTS tenant_template.chat_message_feedback CASCADE")
    op.execute("ALTER TABLE tenant_template.chat_messages DROP COLUMN IF EXISTS answer_kind")
    op.execute("ALTER TABLE tenant_template.chat_messages DROP COLUMN IF EXISTS model_version")
