"""add conversation_id to tenant document_chunks tables

ADR-014 / CAP-6: retrieval decides conversation visibility from the chunk row
itself, so ownership is denormalized from `documents.conversation_id` onto
`document_chunks` exactly as `purpose` already is (migration 022). The alternative
— joining `documents` in the retriever — would sit between the hnsw index scan and
the vector ranking on the hot path, and could not be expressed in the single-table
inline-view rewrite the generated-SQL path uses.

Nullable with no backfill: every chunk that exists before this migration belongs to
a tenant-library document, and NULL is precisely the value that keeps it visible
from every conversation.

No foreign key. `documents.conversation_id` already carries the FK to
`conversations`, and a second ON DELETE CASCADE path into `document_chunks` would
race the explicit chunk delete in `hard_delete_documents`.

Revision ID: 054
Revises: 053
Create Date: 2026-09-17
"""
from alembic import op

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Template schema first. New tenants inherit it via
    # `LIKE tenant_template.document_chunks INCLUDING ALL` in tenant_service.py.
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            ADD COLUMN IF NOT EXISTS conversation_id VARCHAR
    """)

    # Already-provisioned tenant schemas were copied from tenant_template before this
    # column existed, so they need it applied directly — same shape as migrations 022,
    # 034 and 040. The to_regclass guard keeps the migration from failing on a schema
    # missing the table.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        ALTER TABLE %I.document_chunks
                            ADD COLUMN IF NOT EXISTS conversation_id VARCHAR
                    ', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)

    # Retrieval filters on this column on every query, alongside `purpose`. Partial on
    # NOT NULL: conversation-owned chunks are the rare case, and library chunks are
    # already found by the existing predicates.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS idx_document_chunks_conversation_id
                            ON %I.document_chunks (conversation_id)
                            WHERE conversation_id IS NOT NULL
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
                    ALTER TABLE IF EXISTS %I.document_chunks
                        DROP COLUMN IF EXISTS conversation_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            DROP COLUMN IF EXISTS conversation_id
    """)
