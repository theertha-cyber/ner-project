"""Matches Alembic migration 054 (`alembic/versions/054_document_chunks_conversation_id.py`)
for `tenant_owned` data planes -- convention in `revisions/__init__.py`: every Alembic
migration that changes a tenant-scoped table ships a matching revision here in the
same PR. (054 itself predates this convention being enforced -- this revision closes
that gap; see openspec change `single-source-tenant-ddl`.)
"""

from __future__ import annotations

REVISION = 5

_COLUMN_ADDS: list[str] = [
    "ALTER TABLE {schema}.document_chunks ADD COLUMN IF NOT EXISTS conversation_id varchar",
]

# Partial index, `NOT NULL`-guarded: conversation-owned chunks are the rare case.
_INDEXES: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_document_chunks_conversation_id "
    "ON {schema}.document_chunks (conversation_id) WHERE conversation_id IS NOT NULL",
]


def statements(schema: str) -> list[str]:
    out = [statement.format(schema=schema) for statement in _COLUMN_ADDS]
    out.extend(statement.format(schema=schema) for statement in _INDEXES)
    return out
