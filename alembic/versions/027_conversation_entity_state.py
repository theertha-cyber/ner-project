"""per-conversation entity resolution state (pending clarification + resolved binding)

Revision ID: 027
Revises: 026
Create Date: 2026-07-31
"""
from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None

_CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS {schema}.conversation_entity_state (
        conversation_id VARCHAR PRIMARY KEY,
        pending_original_message TEXT,
        pending_mention TEXT,
        pending_candidates JSONB,
        pending_reask_count INTEGER NOT NULL DEFAULT 0,
        resolved_document_id VARCHAR,
        resolved_entity_value TEXT,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
"""


def upgrade() -> None:
    op.execute(_CREATE_TABLE.format(schema="tenant_template"))

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
                    CREATE TABLE IF NOT EXISTS %I.conversation_entity_state (
                        conversation_id VARCHAR PRIMARY KEY,
                        pending_original_message TEXT,
                        pending_mention TEXT,
                        pending_candidates JSONB,
                        pending_reask_count INTEGER NOT NULL DEFAULT 0,
                        resolved_document_id VARCHAR,
                        resolved_entity_value TEXT,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                    )
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
                EXECUTE format('DROP TABLE IF EXISTS %I.conversation_entity_state', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("DROP TABLE IF EXISTS tenant_template.conversation_entity_state")
