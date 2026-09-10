"""Tenant-schema sync state: runs, source ledger, leases, hidden documents (CAP-3).

All four tables live in the tenant schema beside the documents they describe,
so every query is tenant-scoped by construction (ADR-001). Rows carry opaque
source identity, version tokens, finite outcome classes, and document linkage —
never bytes, credentials, endpoints, or provider diagnostics.

`ensure_sync_tables` is idempotent DDL the alembic migration (041) applies to
`tenant_template` and every provisioned tenant schema; tests call it directly
against their own schema so no shared fixture needs to change.
"""

from datetime import datetime, timezone

from sqlalchemy import text

RUNS_TABLE = "azure_blob_sync_runs"
SOURCES_TABLE = "azure_blob_source_objects"
LEASES_TABLE = "azure_blob_sync_leases"
HIDDEN_TABLE = "azure_blob_hidden_documents"

SYNC_TABLES = (RUNS_TABLE, SOURCES_TABLE, LEASES_TABLE, HIDDEN_TABLE)

# A lease holder that stops reporting is presumed dead after this long; the next
# scheduled run may proceed, and the ledger makes re-execution idempotent.
LEASE_TTL_SECONDS = 15 * 60

RUNS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.azure_blob_sync_runs (
    id VARCHAR PRIMARY KEY,
    tenant_id VARCHAR(64) NOT NULL,
    connection_id VARCHAR NOT NULL,
    trigger VARCHAR(32) NOT NULL,
    outcome VARCHAR(32) NOT NULL DEFAULT 'started',
    reason VARCHAR(64) NOT NULL DEFAULT 'none',
    objects_seen INTEGER NOT NULL DEFAULT 0,
    objects_ingested INTEGER NOT NULL DEFAULT 0,
    objects_skipped INTEGER NOT NULL DEFAULT 0,
    objects_failed INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_blob_sync_runs_conn
    ON {schema}.azure_blob_sync_runs (connection_id, started_at DESC)
"""

SOURCES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.azure_blob_source_objects (
    connection_id VARCHAR NOT NULL,
    object_identity VARCHAR(1024) NOT NULL,
    source_version VARCHAR(256),
    document_id VARCHAR,
    missing_sightings INTEGER NOT NULL DEFAULT 0,
    confirmed_missing BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen_at TIMESTAMPTZ,
    PRIMARY KEY (connection_id, object_identity)
)
"""

LEASES_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.azure_blob_sync_leases (
    connection_id VARCHAR PRIMARY KEY,
    run_id VARCHAR NOT NULL,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
)
"""

HIDDEN_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {schema}.azure_blob_hidden_documents (
    document_id VARCHAR PRIMARY KEY,
    connection_id VARCHAR NOT NULL,
    cause VARCHAR(32) NOT NULL,
    hidden_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""

SYNC_TABLES_DDL = (
    RUNS_TABLE_DDL, SOURCES_TABLE_DDL, LEASES_TABLE_DDL, HIDDEN_TABLE_DDL,
)


async def ensure_sync_tables(session, schema: str) -> None:
    """Create the four sync tables if absent. Idempotent; safe to call per test."""
    for ddl in SYNC_TABLES_DDL:
        for statement in ddl.format(schema=schema).strip().split(";"):
            if statement.strip():
                await session.execute(text(statement))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Leases ----------------------------------------------------------------------------


async def acquire_lease(session, schema: str, connection_id: str, run_id: str) -> bool:
    """Atomically take the connection lease for `run_id`.

    Returns True when this run holds the lease. A stale lease (past expiry) is
    reaped by the acquirer; a live lease held by another run refuses.
    """
    now = _utcnow()
    row = (
        await session.execute(
            text(f"SELECT run_id, expires_at FROM {schema}.azure_blob_sync_leases "
                 "WHERE connection_id = :cid"),
            {"cid": connection_id},
        )
    ).fetchone()
    if row is not None:
        expires_at = row[1]
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if row[0] != run_id and expires_at is not None and expires_at > now:
            return False
    expires = _utcnow().timestamp() + LEASE_TTL_SECONDS
    await session.execute(
        text(
            f"INSERT INTO {schema}.azure_blob_sync_leases "
            "(connection_id, run_id, acquired_at, expires_at) "
            "VALUES (:cid, :rid, NOW(), to_timestamp(:exp)) "
            "ON CONFLICT (connection_id) DO UPDATE SET "
            "run_id = EXCLUDED.run_id, acquired_at = NOW(), "
            "expires_at = EXCLUDED.expires_at"
        ),
        {"cid": connection_id, "rid": run_id, "exp": expires},
    )
    # Re-read under the same transaction: a concurrent acquirer that committed
    # first wins, and this run must not mistake its own upsert for ownership.
    holder = (
        await session.execute(
            text(f"SELECT run_id FROM {schema}.azure_blob_sync_leases "
                 "WHERE connection_id = :cid"),
            {"cid": connection_id},
        )
    ).fetchone()
    return holder is not None and holder[0] == run_id


async def release_lease(session, schema: str, connection_id: str, run_id: str) -> None:
    """Release the lease only if this run still holds it. Never steals."""
    await session.execute(
        text(f"DELETE FROM {schema}.azure_blob_sync_leases "
             "WHERE connection_id = :cid AND run_id = :rid"),
        {"cid": connection_id, "rid": run_id},
    )


# --- Run records -----------------------------------------------------------------------


async def record_run_start(session, schema: str, *, run_id: str, tenant_id: str,
                           connection_id: str, trigger: str) -> None:
    await session.execute(
        text(
            f"INSERT INTO {schema}.azure_blob_sync_runs "
            "(id, tenant_id, connection_id, trigger, outcome, reason) "
            "VALUES (:id, :tid, :cid, :trigger, 'started', 'none')"
        ),
        {"id": run_id, "tid": tenant_id, "cid": connection_id, "trigger": trigger},
    )


async def record_run_finish(session, schema: str, *, run_id: str, outcome: str,
                            reason: str = "none", seen: int = 0,
                            ingested: int = 0, skipped: int = 0,
                            failed: int = 0) -> None:
    await session.execute(
        text(
            f"UPDATE {schema}.azure_blob_sync_runs SET outcome = :outcome, "
            "reason = :reason, objects_seen = :seen, "
            "objects_ingested = :ingested, objects_skipped = :skipped, "
            "objects_failed = :failed, "
            "completed_at = NOW() WHERE id = :id"
        ),
        {"id": run_id, "outcome": outcome, "reason": reason,
         "seen": seen, "ingested": ingested, "skipped": skipped,
         "failed": failed},
    )


async def last_successful_run_at(session, schema: str, connection_id: str):
    row = (
        await session.execute(
            text(
                f"SELECT completed_at FROM {schema}.azure_blob_sync_runs "
                "WHERE connection_id = :cid AND outcome = 'succeeded' "
                "ORDER BY completed_at DESC NULLS LAST LIMIT 1"
            ),
            {"cid": connection_id},
        )
    ).fetchone()
    return row[0] if row else None


# --- Source ledger ---------------------------------------------------------------------


async def get_source(session, schema: str, connection_id: str, identity: str):
    return (
        await session.execute(
            text(
                f"SELECT source_version, document_id, missing_sightings, "
                f"confirmed_missing FROM {schema}.azure_blob_source_objects "
                "WHERE connection_id = :cid AND object_identity = :oid"
            ),
            {"cid": connection_id, "oid": identity},
        )
    ).fetchone()


async def upsert_source_seen(session, schema: str, *, connection_id: str,
                             identity: str, version: str, document_id: str | None) -> None:
    """Record a sighted object: current version, linked document, absence cleared."""
    await session.execute(
        text(
            f"INSERT INTO {schema}.azure_blob_source_objects "
            "(connection_id, object_identity, source_version, document_id, "
            "missing_sightings, confirmed_missing, last_seen_at) "
            "VALUES (:cid, :oid, :ver, :doc, 0, FALSE, NOW()) "
            "ON CONFLICT (connection_id, object_identity) DO UPDATE SET "
            "source_version = EXCLUDED.source_version, "
            "document_id = EXCLUDED.document_id, missing_sightings = 0, "
            "confirmed_missing = FALSE, last_seen_at = NOW()"
        ),
        {"cid": connection_id, "oid": identity, "ver": version, "doc": document_id},
    )


async def record_absence(session, schema: str, connection_id: str, identity: str) -> int:
    """Count one absence for a known object. Returns the new sighting count."""
    await session.execute(
        text(
            f"UPDATE {schema}.azure_blob_source_objects "
            "SET missing_sightings = missing_sightings + 1 "
            "WHERE connection_id = :cid AND object_identity = :oid"
        ),
        {"cid": connection_id, "oid": identity},
    )
    row = (
        await session.execute(
            text(
                f"SELECT missing_sightings FROM {schema}.azure_blob_source_objects "
                "WHERE connection_id = :cid AND object_identity = :oid"
            ),
            {"cid": connection_id, "oid": identity},
        )
    ).fetchone()
    return row[0] if row else 0


async def confirm_missing(session, schema: str, connection_id: str, identity: str) -> None:
    await session.execute(
        text(
            f"UPDATE {schema}.azure_blob_source_objects SET confirmed_missing = TRUE "
            "WHERE connection_id = :cid AND object_identity = :oid"
        ),
        {"cid": connection_id, "oid": identity},
    )


async def ledger_identities(session, schema: str, connection_id: str) -> list[str]:
    rows = (
        await session.execute(
            text(
                f"SELECT object_identity FROM {schema}.azure_blob_source_objects "
                "WHERE connection_id = :cid"
            ),
            {"cid": connection_id},
        )
    ).fetchall()
    return [r[0] for r in rows]


# --- Hidden documents ------------------------------------------------------------------


async def hide_document(session, schema: str, *, document_id: str,
                        connection_id: str, cause: str) -> None:
    """Exclude a document's derived records from retrieval without deleting them."""
    await session.execute(
        text(
            f"INSERT INTO {schema}.azure_blob_hidden_documents "
            "(document_id, connection_id, cause) VALUES (:doc, :cid, :cause) "
            "ON CONFLICT (document_id) DO UPDATE SET cause = EXCLUDED.cause, "
            "connection_id = EXCLUDED.connection_id, hidden_at = NOW()"
        ),
        {"doc": document_id, "cid": connection_id, "cause": cause},
    )


async def hidden_document_ids(session, schema: str) -> list[str]:
    rows = (
        await session.execute(
            text(f"SELECT document_id FROM {schema}.azure_blob_hidden_documents")
        )
    ).fetchall()
    return [r[0] for r in rows]
