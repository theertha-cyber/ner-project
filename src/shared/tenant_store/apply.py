"""Apply the tenant-store baseline and pending revisions to one store (Design D5, D6).

Sync-only: the two callers — the provisioning Celery task and the `migrate` CLI — both
run outside any request's async context, matching `EngineResolver.resolve_sync`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.shared.tenant_store import baseline
from src.shared.tenant_store.revisions import all_revisions


def apply(conn: Connection, schema: str, tenant_id: str, store_id: str | None = None) -> tuple[str, int]:
    """Apply baseline + every tenant-store revision to `schema` on `conn`, then record
    the applied revision and store identity in `{schema}.platform_store_meta`.

    Idempotent: safe to call again on a schema already at the target revision, or
    partway through after a failed prior attempt — every statement in baseline and every
    revision is itself idempotent (`IF NOT EXISTS` or a `pg_constraint` guard).

    `store_id`, when given, is the identity a replacement connection must match
    (`tenant-residency-store-provisioning`'s "Replacement connections must point at the
    same store" requirement) — the caller reads it from the existing record and compares
    before calling; this function does not compare, only records.

    Returns `(store_id, schema_revision)`.
    """
    for statement in baseline.statements(schema):
        conn.execute(text(statement))

    revisions = all_revisions()
    target_revision = max((r.REVISION for r in revisions), default=baseline.BASELINE_REVISION)
    for revision in revisions:
        for statement in revision.statements(schema):
            conn.execute(text(statement))

    existing = conn.execute(
        text(f"SELECT store_id FROM {schema}.platform_store_meta LIMIT 1")
    ).fetchone()
    resolved_store_id = store_id or (str(existing.store_id) if existing else str(uuid.uuid4()))

    if existing:
        conn.execute(
            text(
                f"UPDATE {schema}.platform_store_meta "
                "SET schema_revision = :rev, tenant_id = :tid"
            ),
            {"rev": target_revision, "tid": tenant_id},
        )
    else:
        conn.execute(
            text(
                f"INSERT INTO {schema}.platform_store_meta "
                "(store_id, tenant_id, schema_revision) VALUES (:sid, :tid, :rev)"
            ),
            {"sid": resolved_store_id, "tid": tenant_id, "rev": target_revision},
        )
    return resolved_store_id, target_revision


def read_store_identity(conn: Connection, schema: str) -> tuple[str, int] | None:
    """The recorded `(store_id, schema_revision)` for `schema`, or `None` if the
    schema, its `platform_store_meta` table, or its row does not exist yet.

    A schema that exists but holds foreign tables and no `platform_store_meta` (the
    "non-empty foreign schema" case `schema_has_foreign_objects` calls this to
    detect) must return `None` here rather than raise — `SELECT ... FROM
    {schema}.platform_store_meta` on a schema that has every table *except* that one
    is `UndefinedTable`, not an empty result set, so the table's own existence is
    checked first."""
    exists = conn.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :s"),
        {"s": schema},
    ).fetchone()
    if not exists:
        return None
    has_meta = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :s AND table_name = 'platform_store_meta'"
        ),
        {"s": schema},
    ).fetchone()
    if not has_meta:
        return None
    row = conn.execute(
        text(f"SELECT store_id, schema_revision FROM {schema}.platform_store_meta LIMIT 1")
    ).fetchone()
    if row is None:
        return None
    return str(row.store_id), row.schema_revision


def schema_has_foreign_objects(conn: Connection, schema: str) -> bool:
    """True when `schema` exists, holds at least one table, and has no
    `platform_store_meta` row — the "non-empty foreign schema" case the provisioning
    spec requires provisioning to refuse rather than alter."""
    tables = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema = :s AND table_type = 'BASE TABLE'"
        ),
        {"s": schema},
    ).scalar_one()
    if tables == 0:
        return False
    return read_store_identity(conn, schema) is None
