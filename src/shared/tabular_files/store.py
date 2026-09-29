"""Control-plane persistence for uploaded tabular files (ADR-019).

Every function takes a **platform** session (Design D10): these tables live in
`public`, and a `tenant_owned` tenant's resolved session has no `public.*`
tables at all. Every read and write is constrained by the caller's tenant id,
which comes from the authenticated context — never from a request field.

File status mirrors what chat and the portal need at a glance: `ready` once any
version is served, otherwise the latest version's status, `deleted` after delete.
Per-version detail (a pending v2 under review while v1 is served) is on the
version rows.
"""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

from sqlalchemy import text

FILES_TABLE = "public.tabular_files"
VERSIONS_TABLE = "public.tabular_file_versions"

STATUS_PROFILING = "profiling"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_PUBLISHING = "publishing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_SUPERSEDED = "superseded"
STATUS_DELETED = "deleted"

_VERSION_COLUMNS = (
    "file_id, version, tenant_id, status, failure_reason, source_kind, source_filename, "
    "sheet, original_key, parquet_key, profile, review, load_report, contract, "
    "created_at, updated_at, published_at"
)


def _json(value) -> str | None:
    return None if value is None else json.dumps(value, default=str)


_JSON_FIELDS = ("profile", "review", "load_report", "contract")


def _version(row):
    """A version row with its JSONB columns decoded (asyncpg hands `text()`
    JSONB back as a string)."""
    if row is None:
        return None
    values = dict(row._mapping)
    for name in _JSON_FIELDS:
        if isinstance(values.get(name), str):
            values[name] = json.loads(values[name])
    return SimpleNamespace(**values)


async def create_file(session, tenant_id: str, display_name: str) -> str:
    file_id = str(uuid.uuid4())
    await session.execute(
        text(f"INSERT INTO {FILES_TABLE} (id, tenant_id, display_name, status) "
             "VALUES (:id, :tid, :name, :status)"),
        {"id": file_id, "tid": tenant_id, "name": display_name, "status": STATUS_PROFILING},
    )
    return file_id


async def create_version(session, tenant_id: str, file_id: str, version: int, *,
                         source_kind: str, source_filename: str, original_key: str,
                         sheet: str | None = None) -> None:
    await session.execute(
        text(f"INSERT INTO {VERSIONS_TABLE} "
             "(file_id, version, tenant_id, status, source_kind, source_filename, sheet, original_key) "
             "VALUES (:fid, :v, :tid, :status, :kind, :fname, :sheet, :okey)"),
        {"fid": file_id, "v": version, "tid": tenant_id, "status": STATUS_PROFILING,
         "kind": source_kind, "fname": source_filename, "sheet": sheet, "okey": original_key},
    )
    await _refresh_file_status(session, tenant_id, file_id)


async def get_file(session, tenant_id: str, file_id: str, include_deleted: bool = False):
    try:
        uuid.UUID(str(file_id))
    except ValueError:
        return None
    deleted_clause = "" if include_deleted else " AND deleted_at IS NULL"
    result = await session.execute(
        text(f"SELECT id, tenant_id, display_name, served_version, status, created_at, "
             f"updated_at, deleted_at FROM {FILES_TABLE} WHERE id = :id AND tenant_id = :tid"
             f"{deleted_clause}"),
        {"id": str(file_id), "tid": tenant_id},
    )
    return result.fetchone()


async def get_version(session, tenant_id: str, file_id: str, version: int):
    try:
        uuid.UUID(str(file_id))
    except ValueError:
        return None
    result = await session.execute(
        text(f"SELECT {_VERSION_COLUMNS} FROM {VERSIONS_TABLE} "
             "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
        {"fid": str(file_id), "v": version, "tid": tenant_id},
    )
    return _version(result.fetchone())


async def get_version_unscoped(session, file_id: str, version: int):
    """For the ingest worker only: the task payload is identity (file, version),
    and the tenant it acts for is read from this row, never from the payload."""
    result = await session.execute(
        text(f"SELECT {_VERSION_COLUMNS} FROM {VERSIONS_TABLE} "
             "WHERE file_id = :fid AND version = :v"),
        {"fid": str(file_id), "v": version},
    )
    return _version(result.fetchone())


async def list_versions(session, tenant_id: str, file_id: str) -> list:
    result = await session.execute(
        text(f"SELECT {_VERSION_COLUMNS} FROM {VERSIONS_TABLE} "
             "WHERE file_id = :fid AND tenant_id = :tid ORDER BY version"),
        {"fid": str(file_id), "tid": tenant_id},
    )
    return [_version(row) for row in result.fetchall()]


async def list_files(session, tenant_id: str) -> list:
    result = await session.execute(
        text(f"SELECT id, tenant_id, display_name, served_version, status, created_at, "
             f"updated_at, deleted_at FROM {FILES_TABLE} "
             "WHERE tenant_id = :tid AND deleted_at IS NULL ORDER BY created_at"),
        {"tid": tenant_id},
    )
    return result.fetchall()


async def count_active_files(session, tenant_id: str) -> int:
    result = await session.execute(
        text(f"SELECT COUNT(*) FROM {FILES_TABLE} WHERE tenant_id = :tid AND deleted_at IS NULL"),
        {"tid": tenant_id},
    )
    return int(result.scalar() or 0)


async def next_version_number(session, file_id: str) -> int:
    result = await session.execute(
        text(f"SELECT COALESCE(MAX(version), 0) FROM {VERSIONS_TABLE} WHERE file_id = :fid"),
        {"fid": str(file_id)},
    )
    return int(result.scalar() or 0) + 1


async def set_version_status(session, tenant_id: str, file_id: str, version: int, status: str,
                             failure_reason: str | None = None) -> None:
    await session.execute(
        text(f"UPDATE {VERSIONS_TABLE} SET status = :status, failure_reason = :reason, "
             "updated_at = NOW() WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
        {"status": status, "reason": failure_reason, "fid": str(file_id), "v": version, "tid": tenant_id},
    )
    await _refresh_file_status(session, tenant_id, file_id)


async def save_profile(session, tenant_id: str, file_id: str, version: int, profile: dict,
                       review: dict, load_report: dict | None) -> None:
    """Persists the draft profile plus the initial review draft and moves the
    version to `needs_review`."""
    await session.execute(
        text(f"UPDATE {VERSIONS_TABLE} SET profile = CAST(:profile AS JSONB), "
             "review = CAST(:review AS JSONB), load_report = CAST(:report AS JSONB), "
             "status = :status, failure_reason = NULL, updated_at = NOW() "
             "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
        {"profile": _json(profile), "review": _json(review), "report": _json(load_report),
         "status": STATUS_NEEDS_REVIEW, "fid": str(file_id), "v": version, "tid": tenant_id},
    )
    await _refresh_file_status(session, tenant_id, file_id)


async def save_review(session, tenant_id: str, file_id: str, version: int, review: dict,
                      load_report: dict) -> None:
    await session.execute(
        text(f"UPDATE {VERSIONS_TABLE} SET review = CAST(:review AS JSONB), "
             "load_report = CAST(:report AS JSONB), updated_at = NOW() "
             "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
        {"review": _json(review), "report": _json(load_report), "fid": str(file_id),
         "v": version, "tid": tenant_id},
    )


async def switch_served_version(session, tenant_id: str, file_id: str, version: int, *,
                                parquet_key: str, contract: dict, load_report: dict) -> int | None:
    """Makes `version` the served one, in the caller's single transaction.

    The new version becomes `ready` with its contract; the previously served
    version becomes `superseded` and loses its contract; the file pointer moves.
    Returns the previously served version number (for object cleanup after
    commit), or None."""
    current = await session.execute(
        text(f"SELECT served_version FROM {FILES_TABLE} "
             "WHERE id = :fid AND tenant_id = :tid AND deleted_at IS NULL FOR UPDATE"),
        {"fid": str(file_id), "tid": tenant_id},
    )
    row = current.fetchone()
    if row is None:
        raise LookupError("file not found")
    previous = row.served_version
    await session.execute(
        text(f"UPDATE {VERSIONS_TABLE} SET status = :status, parquet_key = :pkey, "
             "contract = CAST(:contract AS JSONB), load_report = CAST(:report AS JSONB), "
             "failure_reason = NULL, published_at = NOW(), updated_at = NOW() "
             "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
        {"status": STATUS_READY, "pkey": parquet_key, "contract": _json(contract),
         "report": _json(load_report), "fid": str(file_id), "v": version, "tid": tenant_id},
    )
    if previous is not None and previous != version:
        await session.execute(
            text(f"UPDATE {VERSIONS_TABLE} SET status = :status, contract = NULL, "
                 "parquet_key = NULL, updated_at = NOW() "
                 "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
            {"status": STATUS_SUPERSEDED, "fid": str(file_id), "v": previous, "tid": tenant_id},
        )
    await session.execute(
        text(f"UPDATE {FILES_TABLE} SET served_version = :v, status = :status, updated_at = NOW() "
             "WHERE id = :fid AND tenant_id = :tid"),
        {"v": version, "status": STATUS_READY, "fid": str(file_id), "tid": tenant_id},
    )
    return previous if previous != version else None


async def mark_deleted(session, tenant_id: str, file_id: str) -> bool:
    """Marks the file deleted first, so chat stops offering it on the very next
    turn; object removal follows. Contracts are cleared in the same statement
    batch."""
    result = await session.execute(
        text(f"UPDATE {FILES_TABLE} SET status = :status, deleted_at = NOW(), "
             "served_version = NULL, updated_at = NOW() "
             "WHERE id = :fid AND tenant_id = :tid AND deleted_at IS NULL"),
        {"status": STATUS_DELETED, "fid": str(file_id), "tid": tenant_id},
    )
    if result.rowcount == 0:
        return False
    await session.execute(
        text(f"UPDATE {VERSIONS_TABLE} SET status = :status, contract = NULL, parquet_key = NULL, "
             "updated_at = NOW() WHERE file_id = :fid AND tenant_id = :tid"),
        {"status": STATUS_DELETED, "fid": str(file_id), "tid": tenant_id},
    )
    return True


async def ready_contracts(session, tenant_id: str) -> list[dict]:
    """Served contracts of this tenant's `ready`, non-deleted files — the only
    thing chat ever sees of an uploaded file."""
    result = await session.execute(
        text(f"SELECT f.id AS file_id, f.display_name, v.version, v.sheet, v.parquet_key, v.contract "
             f"FROM {FILES_TABLE} f JOIN {VERSIONS_TABLE} v "
             "ON v.file_id = f.id AND v.version = f.served_version "
             "WHERE f.tenant_id = :tid AND v.tenant_id = :tid AND f.deleted_at IS NULL "
             "AND f.status = :ready AND v.status = :ready AND v.contract IS NOT NULL "
             "ORDER BY f.created_at"),
        {"tid": tenant_id, "ready": STATUS_READY},
    )
    served = []
    for row in result.fetchall():
        contract = row.contract if isinstance(row.contract, dict) else json.loads(row.contract)
        served.append({
            "file_id": str(row.file_id), "display_name": row.display_name,
            "version": row.version, "sheet": row.sheet, "parquet_key": row.parquet_key,
            "contract": contract,
        })
    return served


async def relations_in_use(session, tenant_id: str, exclude_file_id: str) -> set[str]:
    """Relation names of the tenant's other non-deleted files, so a new file's
    relation is de-duplicated against them."""
    result = await session.execute(
        text(f"SELECT DISTINCT v.review -> 'table' ->> 'relation' AS relation "
             f"FROM {VERSIONS_TABLE} v JOIN {FILES_TABLE} f ON f.id = v.file_id "
             "WHERE f.tenant_id = :tid AND f.deleted_at IS NULL AND f.id <> :fid "
             "AND v.review IS NOT NULL"),
        {"tid": tenant_id, "fid": str(exclude_file_id)},
    )
    return {row.relation for row in result.fetchall() if row.relation}


async def _refresh_file_status(session, tenant_id: str, file_id: str) -> None:
    """File status = `ready` while a version is served, else the latest version's."""
    await session.execute(
        text(f"UPDATE {FILES_TABLE} f SET status = CASE "
             "WHEN f.served_version IS NOT NULL THEN 'ready' "
             f"ELSE COALESCE((SELECT v.status FROM {VERSIONS_TABLE} v WHERE v.file_id = f.id "
             "ORDER BY v.version DESC LIMIT 1), f.status) END, updated_at = NOW() "
             "WHERE f.id = :fid AND f.tenant_id = :tid AND f.deleted_at IS NULL"),
        {"fid": str(file_id), "tid": tenant_id},
    )
