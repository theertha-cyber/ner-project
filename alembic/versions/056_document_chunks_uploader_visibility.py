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
from alembic import op

revision = "056"
down_revision = "055"
branch_labels = None
depends_on = None

# Matches `ActorKind.SOURCE_SYSTEM` in the ingestion contract and the default
# migration 038 applied to `documents.ingested_by_kind`.
_HUMAN = "human"

_COLUMNS = "ADD COLUMN IF NOT EXISTS uploaded_by VARCHAR, ADD COLUMN IF NOT EXISTS ingested_by_kind VARCHAR(32)"


def upgrade() -> None:
    # Template schema first. New tenants inherit it via
    # `LIKE tenant_template.document_chunks INCLUDING ALL` in tenant_service.py.
    op.execute(f"ALTER TABLE tenant_template.document_chunks {_COLUMNS}")

    # Already-provisioned schemas were copied from the template before these columns
    # existed — same shape as migrations 022, 034, 040 and 054. The to_regclass guard
    # keeps the migration from failing on a schema missing either table.
    op.execute(f"""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%' AND nspname != 'tenant_template'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('ALTER TABLE %I.document_chunks {_COLUMNS}', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)

    # Backfill from each chunk's own document. Batched by document rather than by row:
    # the join is on an indexed primary key and a tenant's chunk count is large while
    # its document count is not, so one correlated update per schema is cheaper than
    # paging chunks. `IS NOT DISTINCT FROM` is deliberate — re-running the migration
    # must not rewrite rows it already set, which is what makes it re-runnable.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL
                   AND to_regclass(format('%I.documents', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        UPDATE %I.document_chunks c
                        SET uploaded_by = d.uploaded_by,
                            ingested_by_kind = COALESCE(d.ingested_by_kind, %L)
                        FROM %I.documents d
                        WHERE d.id = c.document_id
                          AND (c.ingested_by_kind IS NULL OR c.uploaded_by IS DISTINCT FROM d.uploaded_by)
                    ', schema_name, 'human', schema_name);
                END IF;
            END LOOP;
        END $$;
    """)

    # A chunk whose document no longer exists cannot have its visibility derived, and
    # leaving it NULL would let the predicate decide by accident. There is no honest
    # uploader for it, so it is marked source-system — the same treatment a document
    # ingested by no human gets, and the same visibility the tenant already had for it
    # before this change.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        UPDATE %I.document_chunks
                        SET ingested_by_kind = %L
                        WHERE ingested_by_kind IS NULL
                    ', schema_name, 'source_system');
                END IF;
            END LOOP;
        END $$;
    """)

    # The backfill is the correctness-critical half of this migration, so it verifies
    # itself rather than trusting that the loop above reached every schema. A row with
    # no ingesting actor is a row whose visibility is undefined; failing here is far
    # better than shipping it.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
            unset_count BIGINT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format(
                        'SELECT COUNT(*) FROM %I.document_chunks WHERE ingested_by_kind IS NULL',
                        schema_name
                    ) INTO unset_count;
                    IF unset_count > 0 THEN
                        RAISE EXCEPTION
                            'migration 056: % chunks in schema % have no ingesting actor',
                            unset_count, schema_name;
                    END IF;
                END IF;
            END LOOP;
        END $$;
    """)

    # Every retrieval query filters on these two columns alongside `purpose` and
    # `conversation_id`. Composite because the predicate reads both together, and
    # partial on human ingestion because source-system chunks are the unrestricted case
    # that the existing predicates already find.
    # `%L` rather than an inlined literal: a quote inside the `format()` template would
    # terminate the template's own string, which is the kind of breakage that only shows
    # up when the statement actually runs.
    op.execute("""
        DO $$
        DECLARE
            schema_name TEXT;
        BEGIN
            FOR schema_name IN
                SELECT nspname FROM pg_namespace
                WHERE nspname LIKE 'tenant\\_%'
            LOOP
                IF to_regclass(format('%I.document_chunks', schema_name)) IS NOT NULL THEN
                    EXECUTE format('
                        CREATE INDEX IF NOT EXISTS idx_document_chunks_uploaded_by
                            ON %I.document_chunks (uploaded_by)
                            WHERE ingested_by_kind = %L
                    ', schema_name, 'human');
                END IF;
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
