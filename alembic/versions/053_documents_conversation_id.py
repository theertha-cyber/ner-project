"""add conversation_id to tenant documents tables

ADR-011 / CAP-3: chat attachments are document rows owned by exactly one
conversation. The chat send path (`_persist_attachments` in chat.py) writes
`documents.conversation_id` on every attachment-bearing turn; until now the column
existed only in the test fixture (`tests/conftest.py`), so this migration makes it
part of the deployed tenant schema. Nullable on purpose: non-chat documents (the
tenant-wide Documents library) keep it NULL, which is exactly what keeps them out of
conversation-scoped retrieval and visible to the library (ADR-011, CAP-5).

Renumbered from 040 to 053 when `attachment-in-chat` merged main: main had
independently taken revision 040 (`040_confidence_routed_review`), and this column is
additive and independent of everything between, so it slots onto the end of main's
chain rather than forking it.

Revision ID: 053
Revises: 052
Create Date: 2026-09-14
"""
import importlib

from alembic import op
from sqlalchemy import text

revision = "053"
down_revision = "052"
branch_labels = None
depends_on = None

# Leading-digit module name -- can't `from ... import` it by identifier, so
# import_module by string (same approach `revisions/__init__.py::_discover` uses).
_revision_004 = importlib.import_module(
    "src.shared.tenant_store.revisions.004_documents_conversation_id"
)


def upgrade() -> None:
    # DDL lives in `_revision_004.statements()` -- the same function
    # `src/shared/tenant_store/migrate.py` calls for `tenant_owned` Azure data
    # planes -- so platform and tenant-owned stores get identical DDL from one
    # authored source (ADR-017 Design Decision 5).
    bind = op.get_bind()
    for statement in _revision_004.statements("tenant_template"):
        op.execute(statement)

    # Already-provisioned tenant schemas were copied from tenant_template before
    # this column existed, so they need it applied directly — same shape as
    # migrations 022 and 034. `conversations` exists in every tenant schema
    # created by migration 010 or cloned after it; the to_regclass guards keep
    # the migration from failing on a schema missing either table.
    schema_names = bind.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'"
        )
    ).scalars().all()

    for schema_name in schema_names:
        has_documents = bind.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"{schema_name}.documents"},
        ).scalar()
        has_conversations = bind.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"{schema_name}.conversations"},
        ).scalar()
        if has_documents is None or has_conversations is None:
            continue
        for statement in _revision_004.statements(schema_name):
            op.execute(statement)


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
                    ALTER TABLE %I.documents
                        DROP COLUMN IF EXISTS conversation_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.documents
            DROP COLUMN IF EXISTS conversation_id
    """)