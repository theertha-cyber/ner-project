"""Matches Alembic migration 053 (`alembic/versions/053_documents_conversation_id.py`)
for `tenant_owned` data planes -- convention in `revisions/__init__.py`: every Alembic
migration that changes a tenant-scoped table ships a matching revision here in the
same PR. (053 itself predates this convention being enforced -- this revision closes
that gap; see openspec change `single-source-tenant-ddl`.)
"""

from __future__ import annotations

REVISION = 4

_COLUMN_ADDS: list[str] = [
    "ALTER TABLE {schema}.documents ADD COLUMN IF NOT EXISTS conversation_id varchar",
]

# `ALTER TABLE ... ADD CONSTRAINT` has no `IF NOT EXISTS` in PostgreSQL; guard with a
# `pg_constraint` existence check, same as `baseline.py`'s `_guarded_add_constraint`.
_FOREIGN_KEYS: list[tuple[str, str, str]] = [
    ("documents", "documents_conversation_id_fkey",
     "FOREIGN KEY (conversation_id) REFERENCES {schema}.conversations(id) ON DELETE CASCADE"),
]


def _guarded_add_constraint(schema: str, table: str, name: str, ddl: str) -> str:
    return f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{name}'
                  AND connamespace = '{schema}'::regnamespace
            ) THEN
                ALTER TABLE {schema}.{table} ADD CONSTRAINT {name} {ddl.format(schema=schema)};
            END IF;
        END $$;
    """


def statements(schema: str) -> list[str]:
    out = [statement.format(schema=schema) for statement in _COLUMN_ADDS]
    for table, name, ddl in _FOREIGN_KEYS:
        out.append(_guarded_add_constraint(schema, table, name, ddl))
    return out
