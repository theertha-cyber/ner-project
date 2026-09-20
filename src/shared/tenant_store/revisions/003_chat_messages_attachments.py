"""Matches Alembic migration 055 (`alembic/versions/055_chat_messages_attachments.py`)
for `tenant_owned` data planes -- convention in `revisions/__init__.py`: every Alembic
migration that changes a tenant-scoped table ships a matching revision here in the
same PR.
"""

from __future__ import annotations

REVISION = 3

_COLUMN_ADDS: list[str] = [
    "ALTER TABLE {schema}.chat_messages ADD COLUMN IF NOT EXISTS attachments jsonb",
]


def statements(schema: str) -> list[str]:
    return [statement.format(schema=schema) for statement in _COLUMN_ADDS]
