"""add conversation_id to tenant document_chunks tables

ADR-014 / CAP-6: retrieval decides conversation visibility from the chunk row
itself, so ownership is denormalized from `documents.conversation_id` onto
`document_chunks` exactly as `purpose` already is (migration 022). The alternative
— joining `documents` in the retriever — would sit between the hnsw index scan and
the vector ranking on the hot path, and could not be expressed in the single-table
inline-view rewrite the generated-SQL path uses.

Nullable with no backfill: every chunk that exists before this migration belongs to
a tenant-library document, and NULL is precisely the value that keeps it visible
from every conversation.

No foreign key. `documents.conversation_id` already carries the FK to
`conversations`, and a second ON DELETE CASCADE path into `document_chunks` would
race the explicit chunk delete in `hard_delete_documents`.

Revision ID: 054
Revises: 053
Create Date: 2026-09-17
"""
import importlib

from alembic import op
from sqlalchemy import text

revision = "054"
down_revision = "053"
branch_labels = None
depends_on = None

# Leading-digit module name -- can't `from ... import` it by identifier, so
# import_module by string (same approach `revisions/__init__.py::_discover` uses).
_revision_005 = importlib.import_module(
    "src.shared.tenant_store.revisions.005_document_chunks_conversation_id"
)


def upgrade() -> None:
    # DDL lives in `_revision_005.statements()` -- the same function
    # `src/shared/tenant_store/migrate.py` calls for `tenant_owned` Azure data
    # planes -- so platform and tenant-owned stores get identical DDL from one
    # authored source (ADR-017 Design Decision 5).
    bind = op.get_bind()
    for statement in _revision_005.statements("tenant_template"):
        op.execute(statement)

    # Already-provisioned tenant schemas were copied from tenant_template before this
    # column existed, so they need it applied directly — same shape as migrations 022,
    # 034 and 040. The to_regclass guard keeps the migration from failing on a schema
    # missing the table.
    schema_names = bind.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'"
        )
    ).scalars().all()

    for schema_name in schema_names:
        has_chunks = bind.execute(
            text("SELECT to_regclass(:table_name)"),
            {"table_name": f"{schema_name}.document_chunks"},
        ).scalar()
        if has_chunks is None:
            continue
        for statement in _revision_005.statements(schema_name):
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
                    ALTER TABLE IF EXISTS %I.document_chunks
                        DROP COLUMN IF EXISTS conversation_id
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            DROP COLUMN IF EXISTS conversation_id
    """)
