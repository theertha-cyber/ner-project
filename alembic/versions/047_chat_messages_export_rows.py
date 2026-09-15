"""add export_rows/export_row_count to chat_messages

Revision ID: 047
Revises: 046
Create Date: 2026-09-14

NOTE (resolved 2026-09-15): this branch (`export-chat`) was originally cut
before nine migrations (038-046) landed on `main`, and `down_revision` here
briefly pointed at "037" (this branch's own stale head) rather than `main`'s
real tip. Two of those nine migrations were also duplicate revision IDs
("038" and "039", each independently created on separate branches) that
broke `alembic history`/`upgrade` outright — fixed separately by renumbering
them to "038b"/"039b" (see those files). With that fix landed on `main`, this
migration now correctly chains onto `046`, `main`'s real, verified-unambiguous
head (`alembic heads`/`upgrade head` both confirmed clean end-to-end before
this change).
"""
from alembic import op
import sqlalchemy as sa

revision = "047"
down_revision = "046"
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
