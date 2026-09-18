"""`public.tenant_document_registry` — the content-free per-document projection
(ADR-017, Design D7, task group 12).

Two databases cannot share a transaction, so the tenant store (wherever its data
plane resolves) is authoritative for a document and this registry is a
*repairable projection* of it on the platform — written best-effort after the
tenant-store commit, and re-derivable by `reconcile_tenant_registry` if a write
is ever missed. It carries no filename, storage reference, error message, or any
other content-bearing field (`tests/test_tenant_document_registry.py` asserts the
column set directly) — quota checks, system-admin counts, and dashboard totals
read it precisely because it is safe to query without ever touching a tenant
store.
"""

from __future__ import annotations

import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_UPSERT_SQL = text(
    """
    INSERT INTO public.tenant_document_registry
        (document_id, tenant_id, source_type, status, file_size_bytes,
         checksum, retention_mode, created_at, updated_at)
    VALUES (:document_id, :tenant_id, :source_type, :status, :file_size_bytes,
            :checksum, :retention_mode, NOW(), NOW())
    ON CONFLICT (tenant_id, document_id) DO UPDATE SET
        status = EXCLUDED.status,
        file_size_bytes = EXCLUDED.file_size_bytes,
        checksum = EXCLUDED.checksum,
        retention_mode = EXCLUDED.retention_mode,
        updated_at = NOW()
    """
)

_DELETE_SQL = text(
    "DELETE FROM public.tenant_document_registry WHERE tenant_id = :tenant_id AND document_id = :document_id"
)

_UPDATE_STATUS_SQL = text(
    "UPDATE public.tenant_document_registry SET status = :status, updated_at = NOW() "
    "WHERE tenant_id = :tenant_id AND document_id = :document_id"
)


async def update_status(platform_session, *, tenant_id: str, document_id: str, status: str) -> None:
    """A status-only transition (OCR processed/failed, blob-sync replace/hide) on a
    row `record` already created at ingestion — an `UPDATE`, not an upsert, since
    this call site has no `source_type`/`retention_mode` to construct a correct
    row from if one were somehow missing (`reconcile_tenant_registry`, task 12.2,
    is what repairs that case). Same best-effort contract as `record`."""
    try:
        await platform_session.execute(
            _UPDATE_STATUS_SQL, {"tenant_id": tenant_id, "document_id": document_id, "status": status}
        )
        await platform_session.commit()
    except Exception:
        logger.warning(
            "tenant_document_registry_status_update_failed",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True,
        )


def update_status_sync(platform_conn, *, tenant_id: str, document_id: str, status: str) -> None:
    try:
        platform_conn.execute(
            _UPDATE_STATUS_SQL, {"tenant_id": tenant_id, "document_id": document_id, "status": status}
        )
        platform_conn.commit()
    except Exception:
        logger.warning(
            "tenant_document_registry_status_update_failed",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True,
        )


async def record(
    platform_session,
    *,
    tenant_id: str,
    document_id: str,
    source_type: str,
    status: str,
    retention_mode: str,
    file_size_bytes: int | None = None,
    checksum: str | None = None,
) -> None:
    """Upserts one document's registry row. Called after ingestion, an OCR status
    transition, and a blob-sync replace/hide — anywhere a document's row commits
    on the tenant store. `platform_session` is a session on the *platform*
    database (Design D10) — never the tenant-resolved one, since this table lives
    in `public`. Best-effort by design: a failure here is logged and swallowed
    rather than raised, so a registry write can never turn a successful
    tenant-store commit into a failed request — `reconcile_tenant_registry`
    (task 12.2) is what repairs a missed write."""
    try:
        await platform_session.execute(
            _UPSERT_SQL,
            {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "source_type": source_type,
                "status": status,
                "file_size_bytes": file_size_bytes,
                "checksum": checksum,
                "retention_mode": retention_mode,
            },
        )
        await platform_session.commit()
    except Exception:
        logger.warning(
            "tenant_document_registry_write_failed",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True,
        )


def record_sync(
    platform_conn,
    *,
    tenant_id: str,
    document_id: str,
    source_type: str,
    status: str,
    retention_mode: str,
    file_size_bytes: int | None = None,
    checksum: str | None = None,
) -> None:
    """`record` for a sync `Connection`/`Session` (Celery workers — OCR status
    transitions, blob-sync replace/hide)."""
    try:
        platform_conn.execute(
            _UPSERT_SQL,
            {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "source_type": source_type,
                "status": status,
                "file_size_bytes": file_size_bytes,
                "checksum": checksum,
                "retention_mode": retention_mode,
            },
        )
        platform_conn.commit()
    except Exception:
        logger.warning(
            "tenant_document_registry_write_failed",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True,
        )


def reconcile_schema_sync(platform_conn, tenant_conn, *, tenant_id: str, schema: str) -> int:
    """Re-derives every document row in `schema` into the registry (tenant-
    document-registry spec's "Drift is reconciled"). The same projection
    migration 043's backfill uses, but upserting (via `record_sync`) rather than
    `ON CONFLICT DO NOTHING`, so a status change that a missed live write
    (network blip, process restart between the tenant-store commit and the
    registry write) never made it to the registry is caught here instead.

    `tenant_conn` and `platform_conn` may be on two different databases for a
    `tenant_owned` tenant — this reads from one and writes to the other, one row
    at a time, never a single cross-database statement. The caller supplies
    `tenant_id` directly (from the same `tenant_data_planes`/`tenants` row it
    resolved `tenant_conn` from) rather than this function trying to derive it
    from `schema`, which is not reversible when a tenant id itself contains `_`.
    Returns the number of rows re-applied."""
    # `file_size_bytes` is the current-shape column name in every tenant store
    # (`baseline.py`) — unlike migration 043's platform-side backfill, which
    # additionally reads a legacy `file_size` some pre-migration platform schemas
    # still carried, a tenant store never has that legacy column to fall back to.
    rows = tenant_conn.execute(
        text(
            f"SELECT id, source_type, status, file_size_bytes, "
            f"checksum, retention_mode FROM {schema}.documents"
        )
    ).fetchall()
    for row in rows:
        record_sync(
            platform_conn,
            tenant_id=tenant_id,
            document_id=row.id,
            source_type=row.source_type,
            status=row.status,
            retention_mode=row.retention_mode,
            file_size_bytes=row.file_size_bytes,
            checksum=row.checksum,
        )
    return len(rows)


async def remove(platform_session, *, tenant_id: str, document_id: str) -> None:
    """Hard-removes one document's registry row. The tenant-content delete path
    itself soft-deletes (`documents.status = 'deleted'`), so that path calls
    `update_status(status="deleted")` instead — this is for a genuine hard delete
    (e.g. reconciliation dropping an orphaned row). Same best-effort contract as
    `record`."""
    try:
        await platform_session.execute(_DELETE_SQL, {"tenant_id": tenant_id, "document_id": document_id})
        await platform_session.commit()
    except Exception:
        logger.warning(
            "tenant_document_registry_delete_failed",
            extra={"tenant_id": tenant_id, "document_id": document_id},
            exc_info=True,
        )
