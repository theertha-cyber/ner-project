"""record each user message's attachments on the message row

A conversation already owns its attachments through `documents.conversation_id`,
which is what scopes retrieval (ADR-014). That answers "which documents does this
session have", but not "which turn did the user attach this on" — and the thread
needs the second question to show a file on the message that carried it, still
correctly after a reload or a conversation switch.

Stored on the message rather than as `documents.message_id` because the ingestion
happens before the turn's message rows exist: the attachment is ingested up front
so its content is indexed before retrieval runs, while the user row is written
once the reply is complete. A column on `documents` would need a second UPDATE
after the fact; a JSONB list on the message is written in the same statement that
creates it.

Metadata only — filename, media type, size and the document id. The content lives
in `documents`/`document_chunks`; this is for rendering a chip, and duplicating
more would create a second copy to keep correct.

Revision ID: 055
Revises: 054
Create Date: 2026-09-18
"""
import importlib

from alembic import op
from sqlalchemy import text

revision = "055"
down_revision = "054"
branch_labels = None
depends_on = None

# Leading-digit module name -- can't `from ... import` it by identifier, so
# import_module by string (same approach `revisions/__init__.py::_discover` uses).
_revision_003 = importlib.import_module(
    "src.shared.tenant_store.revisions.003_chat_messages_attachments"
)


def upgrade() -> None:
    # DDL lives in `_revision_003.statements()` -- the same function
    # `src/shared/tenant_store/migrate.py` calls for `tenant_owned` Azure data
    # planes -- so platform and tenant-owned stores get identical DDL from one
    # authored source (ADR-017 Design Decision 5).
    bind = op.get_bind()
    for statement in _revision_003.statements("tenant_template"):
        op.execute(statement)

    # Already-provisioned tenant schemas were cloned from the template before this
    # column existed — same loop-and-guard shape as migrations 022, 034, 040 and 054.
    schema_names = bind.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'"
        )
    ).scalars().all()

    for schema_name in schema_names:
        table_exists = bind.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"{schema_name}.chat_messages"},
        ).scalar()
        if table_exists is None:
            continue
        for statement in _revision_003.statements(schema_name):
            op.execute(statement)


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
                    ALTER TABLE IF EXISTS %I.chat_messages
                        DROP COLUMN IF EXISTS attachments
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.chat_messages
            DROP COLUMN IF EXISTS attachments
    """)
