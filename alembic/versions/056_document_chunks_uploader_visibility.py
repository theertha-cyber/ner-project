"""add uploaded_by and ingested_by_kind to tenant document_chunks tables

The uploader-visibility rule decides what a chat answer may draw on, and every
retrieval channel evaluates it per chunk. Both facts are denormalized from
`documents` onto `document_chunks` for the same reason migration 054 denormalized
`conversation_id` and migration 022 denormalized `purpose`: joining `documents` in
the retriever would sit between the hnsw index scan and the vector ranking on the
hot path, and could not be expressed in the single-table inline-view rewrite the
generated-SQL path uses.

Unlike 054, this migration backfills. A NULL `conversation_id` meant "library
content, visible everywhere" — the correct answer for every pre-existing row. There
is no such benign default here: a NULL `ingested_by_kind` would either hide every
existing chunk from everyone or expose every chunk to everyone, depending on how the
predicate happened to treat NULL. So the values are copied from each chunk's own
document, and the migration asserts that none is left unset.

Two columns rather than one precomputed boolean: whether a document is visible
depends on *which* user is asking, which no row-level flag can express. A
source-system document is visible to all; a human-ingested one to exactly one user.

Both values are immutable after ingestion — a document is never reassigned to a
different uploader — so the denormalized copy cannot drift from its source.

Revision ID: 056
Revises: 055
Create Date: 2026-09-18
"""
import importlib

from alembic import op
from sqlalchemy import text

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None

# Leading-digit module name -- can't `from ... import` it by identifier, so
# import_module by string (same approach `revisions/__init__.py::_discover` uses).
_revision_006 = importlib.import_module(
    "src.shared.tenant_store.revisions.006_document_chunks_uploader_visibility"
)


def upgrade() -> None:
    # DDL and backfill both live in `_revision_006.statements()` -- the same function
    # `src/shared/tenant_store/migrate.py` calls for `tenant_owned` data planes -- so
    # platform and tenant-owned stores get identical statements from one authored
    # source (ADR-017 Design Decision 5).
    bind = op.get_bind()

    # `tenant_template` first, so new tenants inherit the columns via
    # `LIKE tenant_template.document_chunks INCLUDING ALL` in tenant_service.py. Then
    # every already-provisioned schema, which was copied from the template before these
    # columns existed -- same shape as migrations 022, 034, 040 and 054.
    provisioned = bind.execute(
        text(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template' "
            "ORDER BY nspname"
        )
    ).scalars().all()

    for schema_name in ["tenant_template", *provisioned]:
        # Both tables are checked, not just `document_chunks`: the backfill reads
        # `documents`, so a schema holding one without the other must be skipped rather
        # than half-migrated. The template is checked on the same terms as any other
        # schema -- it is not guaranteed to be complete in every environment.
        present = bind.execute(
            text("SELECT to_regclass(:chunks), to_regclass(:documents)"),
            {
                "chunks": f"{schema_name}.document_chunks",
                "documents": f"{schema_name}.documents",
            },
        ).fetchone()
        if present[0] is None or present[1] is None:
            continue
        for statement in _revision_006.statements(schema_name):
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
                        DROP COLUMN IF EXISTS uploaded_by,
                        DROP COLUMN IF EXISTS ingested_by_kind
                ', schema_name);
            END LOOP;
        END $$;
    """)
    op.execute("""
        ALTER TABLE tenant_template.document_chunks
            DROP COLUMN IF EXISTS uploaded_by,
            DROP COLUMN IF EXISTS ingested_by_kind
    """)
