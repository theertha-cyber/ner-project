"""enable pgvector, create chatbot tables and index

Revision ID: 010
Revises: 009
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.document_chunks (
            id VARCHAR PRIMARY KEY,
            document_id VARCHAR NOT NULL REFERENCES tenant_template.documents(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding vector(1536),
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.conversations (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            user_id VARCHAR NOT NULL,
            title VARCHAR(255),
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.chat_messages (
            id VARCHAR PRIMARY KEY,
            conversation_id VARCHAR NOT NULL REFERENCES tenant_template.conversations(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            sources JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS public.widget_api_keys (
            id VARCHAR PRIMARY KEY,
            tenant_id VARCHAR NOT NULL,
            key_hash VARCHAR(64) NOT NULL,
            key_prefix VARCHAR(8) NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            last_used_at TIMESTAMPTZ,
            revoked_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
        ON tenant_template.document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
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
                    CREATE TABLE IF NOT EXISTS %I.document_chunks (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        chunk_text TEXT NOT NULL,
                        embedding vector(1536),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                ', schema_name);

                EXECUTE format('
                    CREATE TABLE IF NOT EXISTS %I.conversations (
                        id VARCHAR PRIMARY KEY,
                        tenant_id VARCHAR NOT NULL,
                        user_id VARCHAR NOT NULL,
                        title VARCHAR(255),
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    )
                ', schema_name);

                EXECUTE format('
                    CREATE TABLE IF NOT EXISTS %I.chat_messages (
                        id VARCHAR PRIMARY KEY,
                        conversation_id VARCHAR NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        sources JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                ', schema_name);

                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
                    ON %I.document_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
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
                EXECUTE format('DROP TABLE IF EXISTS %I.chat_messages CASCADE', schema_name);
                EXECUTE format('DROP TABLE IF EXISTS %I.conversations CASCADE', schema_name);
                EXECUTE format('DROP TABLE IF EXISTS %I.document_chunks CASCADE', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("DROP TABLE IF EXISTS tenant_template.chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_template.conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_template.document_chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS public.widget_api_keys CASCADE")
