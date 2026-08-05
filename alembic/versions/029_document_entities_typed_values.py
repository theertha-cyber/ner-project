"""semantic (typed) value columns on document_entities

Revision ID: 029
Revises: 028
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None

_ADD_COLUMNS = """
    ALTER TABLE {schema}.document_entities
        ADD COLUMN IF NOT EXISTS value_kind TEXT,
        ADD COLUMN IF NOT EXISTS value_number DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS value_number_high DOUBLE PRECISION,
        ADD COLUMN IF NOT EXISTS value_unit TEXT,
        ADD COLUMN IF NOT EXISTS value_date DATE,
        ADD COLUMN IF NOT EXISTS value_date_high DATE
"""
_ADD_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_value_number ON {schema}.document_entities (entity_type, value_number) WHERE value_number IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_{suffix}_value_date ON {schema}.document_entities (entity_type, value_date) WHERE value_date IS NOT NULL",
]
_DROP_COLUMNS = """
    ALTER TABLE {schema}.document_entities
        DROP COLUMN IF EXISTS value_kind,
        DROP COLUMN IF EXISTS value_number,
        DROP COLUMN IF EXISTS value_number_high,
        DROP COLUMN IF EXISTS value_unit,
        DROP COLUMN IF EXISTS value_date,
        DROP COLUMN IF EXISTS value_date_high
"""


def upgrade() -> None:
    op.execute(_ADD_COLUMNS.format(schema="tenant_template"))
    for stmt in _ADD_INDEXES:
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
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = schema_name AND table_name = 'document_entities'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.document_entities
                            ADD COLUMN IF NOT EXISTS value_kind TEXT,
                            ADD COLUMN IF NOT EXISTS value_number DOUBLE PRECISION,
                            ADD COLUMN IF NOT EXISTS value_number_high DOUBLE PRECISION,
                            ADD COLUMN IF NOT EXISTS value_unit TEXT,
                            ADD COLUMN IF NOT EXISTS value_date DATE,
                            ADD COLUMN IF NOT EXISTS value_date_high DATE
                    ', schema_name);
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS idx_%s_value_number ON %I.document_entities (entity_type, value_number) WHERE value_number IS NOT NULL
                    ', schema_name, schema_name);
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS idx_%s_value_date ON %I.document_entities (entity_type, value_date) WHERE value_date IS NOT NULL
                    ', schema_name, schema_name);
                END IF;
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
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = schema_name AND table_name = 'document_entities'
                ) THEN
                    EXECUTE format('
                        ALTER TABLE %I.document_entities
                            DROP COLUMN IF EXISTS value_kind,
                            DROP COLUMN IF EXISTS value_number,
                            DROP COLUMN IF EXISTS value_number_high,
                            DROP COLUMN IF EXISTS value_unit,
                            DROP COLUMN IF EXISTS value_date,
                            DROP COLUMN IF EXISTS value_date_high
                    ', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)
    op.execute(_DROP_COLUMNS.format(schema="tenant_template"))
