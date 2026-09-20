"""Matches Alembic migration 056 (`alembic/versions/056_document_chunks_uploader_visibility.py`)
for `tenant_owned` data planes -- convention in `revisions/__init__.py`: every Alembic
migration that changes a tenant-scoped table ships a matching revision here in the
same PR.

Unlike revisions 003-005, this one carries data statements as well as DDL. The
uploader-visibility predicate reads `ingested_by_kind` on every retrieval, and a NULL
there has no safe reading: depending on how the predicate treats it, an unbackfilled
chunk is either invisible to its own uploader or visible to everyone. A tenant-owned
store that received only the columns would be in exactly that undefined state, so the
backfill and its self-check travel with them rather than being left to the platform
migration.

Every statement is idempotent and re-runnable -- `apply()` replays baseline and every
revision on each run, including against a store already at this revision.
"""

from __future__ import annotations

REVISION = 6

# Matches `ActorKind.SOURCE_SYSTEM` in the ingestion contract and the default
# migration 038 applied to `documents.ingested_by_kind`.
_HUMAN = "human"
_SOURCE_SYSTEM = "source_system"

_COLUMN_ADDS: list[str] = [
    "ALTER TABLE {schema}.document_chunks "
    "ADD COLUMN IF NOT EXISTS uploaded_by varchar, "
    "ADD COLUMN IF NOT EXISTS ingested_by_kind varchar(32)",
]

# Copied from each chunk's own document. The join is on an indexed primary key, and a
# tenant's chunk count is large while its document count is not, so one correlated
# update is cheaper than paging chunks. The WHERE clause is what makes a re-run free:
# a row already carrying its document's values is not rewritten.
_BACKFILL: list[str] = [
    "UPDATE {schema}.document_chunks c "
    "SET uploaded_by = d.uploaded_by, "
    f"    ingested_by_kind = COALESCE(d.ingested_by_kind, '{_HUMAN}') "
    "FROM {schema}.documents d "
    "WHERE d.id = c.document_id "
    "  AND (c.ingested_by_kind IS NULL "
    "       OR c.uploaded_by IS DISTINCT FROM d.uploaded_by)",
    # A chunk whose document no longer exists cannot have its visibility derived, and
    # leaving it NULL would let the predicate decide by accident. There is no honest
    # uploader for it, so it is marked source-system -- the same visibility the tenant
    # already had for it before this revision.
    "UPDATE {schema}.document_chunks "
    f"SET ingested_by_kind = '{_SOURCE_SYSTEM}' "
    "WHERE ingested_by_kind IS NULL",
]

# The backfill is the correctness-critical half of this revision, so it verifies itself
# rather than trusting the statements above reached every row. A chunk with no ingesting
# actor is a chunk whose visibility is undefined; failing the migration is far better
# than leaving the store serving it.
_VERIFY: list[str] = [
    """
    DO $$
    DECLARE
        unset_count BIGINT;
    BEGIN
        SELECT COUNT(*) INTO unset_count
        FROM {schema}.document_chunks
        WHERE ingested_by_kind IS NULL;
        IF unset_count > 0 THEN
            RAISE EXCEPTION
                'tenant-store revision 6: % chunks have no ingesting actor', unset_count;
        END IF;
    END $$;
    """,
]

# Composite intent, partial on human ingestion: source-system chunks are the
# unrestricted case the existing predicates already find, so only human-ingested rows
# need an index to narrow by uploader.
_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_uploaded_by "
    "ON {schema}.document_chunks (uploaded_by) "
    f"WHERE ingested_by_kind = '{_HUMAN}'",
]


def statements(schema: str) -> list[str]:
    out: list[str] = []
    for group in (_COLUMN_ADDS, _BACKFILL, _VERIFY, _INDEXES):
        out.extend(statement.format(schema=schema) for statement in group)
    return out
