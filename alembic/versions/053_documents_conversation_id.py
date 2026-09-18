"""add conversation_id to tenant documents tables

ADR-011 / CAP-3: chat attachments are document rows owned by exactly one
conversation. The chat send path (`_persist_attachments` in chat.py) writes
`documents.conversation_id` on every attachment-bearing turn; until now the column
existed only in the test fixture (`tests/conftest.py`), so this migration makes it
part of the deployed tenant schema. Nullable on purpose: non-chat documents (the
tenant-wide Documents library) keep it NULL, which is exactly what keeps them out of
conversation-scoped retrieval and visible to the library (ADR-011, CAP-5).

Renumbered from 040 to 053 when `attachment-in-chat` merged main: main had
independently taken revision 040 (`040_confidence_routed_review`), and this column is
additive and independent of everything between, so it slots onto the end of main's
chain rather than forking it.

Revision ID: 053
Revises: 052
Create Date: 2026-09-14
"""
from alembic import op

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Template schema first. New tenants inherit it via
    # `LIKE tenant_template.documents INCLUDING ALL` in tenant_service.py.
    op.execute("""
        ALTER TABLE tenant_template.documents
            ADD COLUMN IF NOT EXISTS conversation_id VARCHAR
            REFERENCES tenant_template.conversations(id) ON DELETE CASCADE
    """)

    # Already-provisioned tenant schemas were copied from tenant_template before
    # this column existed, so they need it applied directly — same shape as
    # migrations 022 and 034. `conversations` exists in every tenant schema
    # created by migration 010 or cloned after it; the to_regclass guards keep
    # the migration from failing on a schema missing either table.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                IF to_regclass(format('%I.documents', schema_name)) IS NOT NULL
                   AND to_regclass(format('%I.conversations', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        ALTER TABLE %I.documents
                            ADD COLUMN IF NOT EXISTS conversation_id VARCHAR
                            REFERENCES %I.conversations(id) ON DELETE CASCADE
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
                    ALTER TABLE %I.documents
                        DROP COLUMN IF EXISTS conversation_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.documents
            DROP COLUMN IF EXISTS conversation_id
    """)