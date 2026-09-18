"""record each user message's attachments on the message row

A conversation already owns its attachments through `documents.conversation_id`,
which is what scopes retrieval (ADR-014). That answers "which documents does this
session have", but not "which turn did the user attach this on" — and the thread
needs the second question to show a file on the message that carried it, still
correctly after a reload or a conversation switch.

Stored on the message rather than as `documents.message_id` because the ingestion
happens before the turn's message rows exist: the attachment is ingested up front
so its content is indexed before retrieval runs, while the user row is written
once the reply is complete. A column on `documents` would need a second UPDATE
after the fact; a JSONB list on the message is written in the same statement that
creates it.

Metadata only — filename, media type, size and the document id. The content lives
in `documents`/`document_chunks`; this is for rendering a chip, and duplicating
more would create a second copy to keep correct.

Revision ID: 055
Revises: 054
Create Date: 2026-09-18
"""
from alembic import op

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
            ADD COLUMN IF NOT EXISTS attachments JSONB
    """)

    # Already-provisioned tenant schemas were cloned from the template before this
    # column existed — same loop-and-guard shape as migrations 022, 034, 040 and 054.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                IF to_regclass(format('%I.chat_messages', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        ALTER TABLE %I.chat_messages
                            ADD COLUMN IF NOT EXISTS attachments JSONB
                    ', schema_name);
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
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('
                    ALTER TABLE IF EXISTS %I.chat_messages
                        DROP COLUMN IF EXISTS attachments
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
            DROP COLUMN IF EXISTS attachments
    """)
