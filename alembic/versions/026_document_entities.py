"""normalized document_entities table for structured retrieval

Revision ID: 026
Revises: 025
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS {schema}.document_entities (
        id VARCHAR PRIMARY KEY,
        document_id VARCHAR NOT NULL,
        entity_type TEXT NOT NULL,
        entity_value TEXT NOT NULL,
        normalized_value TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        page_number INTEGER,
        char_start INTEGER,
        char_end INTEGER,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""
_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_document_id ON {schema}.document_entities (document_id)",
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_entity_type ON {schema}.document_entities (entity_type)",
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_normalized_value ON {schema}.document_entities (normalized_value)",
]


def upgrade() -> None:
    op.execute(_CREATE_TABLE.format(schema="tenant_template"))
    for stmt in _CREATE_INDEXES:
        op.execute(stmt.format(schema="tenant_template", suffix="document_entities_template"))

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
                    CREATE TABLE IF NOT EXISTS %I.document_entities (
                        id VARCHAR PRIMARY KEY,
                        document_id VARCHAR NOT NULL,
                        entity_type TEXT NOT NULL,
                        entity_value TEXT NOT NULL,
                        normalized_value TEXT NOT NULL,
                        confidence DOUBLE PRECISION NOT NULL,
                        page_number INTEGER,
                        char_start INTEGER,
                        char_end INTEGER,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
                ', schema_name);
                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_%s_document_id ON %I.document_entities (document_id)
                ', schema_name, schema_name);
                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_%s_entity_type ON %I.document_entities (entity_type)
                ', schema_name, schema_name);
                EXECUTE format('
                    CREATE INDEX IF NOT EXISTS idx_%s_normalized_value ON %I.document_entities (normalized_value)
                ', schema_name, schema_name);
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
                EXECUTE format('DROP TABLE IF EXISTS %I.document_entities', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("DROP TABLE IF EXISTS tenant_template.document_entities")
