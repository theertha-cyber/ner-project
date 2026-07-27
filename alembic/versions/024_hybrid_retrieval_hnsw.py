"""hybrid retrieval: chunk_tsv full-text column + hnsw vector index

Revision ID: 024
Revises: 023
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            ADD COLUMN IF NOT EXISTS chunk_tsv tsvector
            GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv
        ON tenant_template.document_chunks
        USING GIN (chunk_tsv);
    """)
    op.execute("DROP INDEX IF EXISTS tenant_template.idx_document_chunks_embedding;")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
        ON tenant_template.document_chunks
        USING hnsw (embedding vector_cosine_ops);
    """)

    op.execute(r"""
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
                        ADD COLUMN IF NOT EXISTS chunk_tsv tsvector
                        GENERATED ALWAYS AS (to_tsvector(''english'', chunk_text)) STORED
                ', schema_name);

                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv
                    ON %I.document_chunks
                    USING GIN (chunk_tsv)
                ', schema_name);

                EXECUTE format('DROP INDEX IF EXISTS %I.idx_document_chunks_embedding', schema_name);

                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw
                    ON %I.document_chunks
                    USING hnsw (embedding vector_cosine_ops)
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute(r"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%' AND nspname != 'tenant_template'
            LOOP
                EXECUTE format('DROP INDEX IF EXISTS %I.idx_document_chunks_tsv', schema_name);
                EXECUTE format('ALTER TABLE IF EXISTS %I.document_chunks DROP COLUMN IF EXISTS chunk_tsv', schema_name);
                EXECUTE format('DROP INDEX IF EXISTS %I.idx_document_chunks_embedding_hnsw', schema_name);
                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
                    ON %I.document_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                ', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("DROP INDEX IF EXISTS tenant_template.idx_document_chunks_tsv;")
    op.execute("ALTER TABLE tenant_template.document_chunks DROP COLUMN IF EXISTS chunk_tsv;")
    op.execute("DROP INDEX IF EXISTS tenant_template.idx_document_chunks_embedding_hnsw;")
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
        ON tenant_template.document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
