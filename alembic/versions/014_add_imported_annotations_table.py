"""add imported_annotations table for bulk annotation file uploads

Revision ID: 014
Revises: 013
Create Date: 2026-06-30
"""
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_template.imported_annotations (
            id VARCHAR PRIMARY KEY,
            tokens TEXT[] NOT NULL,
            tags TEXT[] NOT NULL,
            source_file VARCHAR NOT NULL,
            row_index INTEGER NOT NULL,
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
                    CREATE TABLE IF NOT EXISTS %I.imported_annotations (
                        id VARCHAR PRIMARY KEY,
                        tokens TEXT[] NOT NULL,
                        tags TEXT[] NOT NULL,
                        source_file VARCHAR NOT NULL,
                        row_index INTEGER NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                ', schema_name);
            END LOOP;
        END $$;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_template.imported_annotations")

    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\_%'
            LOOP
                EXECUTE format('DROP TABLE IF EXISTS %I.imported_annotations', schema_name);
            END LOOP;
        END $$;
    """)
