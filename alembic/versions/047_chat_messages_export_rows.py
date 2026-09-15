"""add export_rows/export_row_count to chat_messages

Revision ID: 047
Revises: 037
Create Date: 2026-09-14

NOTE (found during implementation of export-chat-results, 2026-09-14): this
branch (`export-chat`) was cut before nine migrations (038-046) landed on
`main` — including two files both numbered `038`
(`038_document_provenance_and_retention.py`,
`038_llm_prelabeling_columns.py`), so `main`'s own chain already has a branch
point this file knows nothing about. `down_revision` below is still "037",
this branch's own local head — it does NOT chain onto `main`'s actual tip
(046, or wherever the two 038s converge). Renumbered from 038 to 047 (the
next free number after main's highest, 046) purely to avoid an obvious
filename/revision-id collision; `down_revision` MUST be corrected to the
real chain tip as part of rebasing this branch onto `main` before this
migration is merged or run anywhere `main`'s migrations have been applied
(e.g. the shared `ner_dev` database, observed at revision 046 during this
session). Do not run `alembic upgrade head` on a shared database from this
branch as-is.
"""
from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
        ADD COLUMN IF NOT EXISTS export_rows JSONB,
        ADD COLUMN IF NOT EXISTS export_row_count INTEGER
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
                    ADD COLUMN IF NOT EXISTS export_rows JSONB,
                    ADD COLUMN IF NOT EXISTS export_row_count INTEGER
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
                EXECUTE format('
                    ALTER TABLE %I.chat_messages
                    DROP COLUMN IF EXISTS export_rows,
                    DROP COLUMN IF EXISTS export_row_count
                ', schema_name);
            END LOOP;
        END $$;
    """)

    op.execute("""
        ALTER TABLE tenant_template.chat_messages
        DROP COLUMN IF EXISTS export_rows,
        DROP COLUMN IF EXISTS export_row_count
    """)
