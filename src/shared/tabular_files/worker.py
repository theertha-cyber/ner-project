"""Profile and publish runs for one tabular file version (ADR-018 Decision 6).

Called by the Celery tasks in `tasks.py` with identity only (file id, version).
The tenant each run acts for is read from the version row, never from the task
payload. Every failure lands the version in `failed` with a finite reason class;
no parser diagnostic, cell value or stack trace is persisted.
"""

from __future__ import annotations

import asyncio
import logging
import os

from src.shared.tabular_files import ingest, staging, store
from src.shared.tabular_files.storage import parquet_key as build_parquet_key
from src.shared.tabular_files.storage import version_prefix

logger = logging.getLogger(__name__)

INTERNAL_ERROR = "INTERNAL_ERROR"
NOT_PUBLISHABLE = "NOT_PUBLISHABLE"


async def _fail(session_factory, row, reason: str) -> None:
    async with session_factory() as session:
        await store.set_version_status(session, row.tenant_id, str(row.file_id), row.version,
                                       store.STATUS_FAILED, reason)
        await session.commit()


async def run_profile(session_factory, object_store, file_id: str, version: int) -> dict:
    """Stages the original, infers types over every row, and stores the draft
    profile and review with the version in `needs_review`."""
    async with session_factory() as session:
        row = await store.get_version_unscoped(session, file_id, version)
        if row is None or row.status != store.STATUS_PROFILING:
            return {"outcome": "skipped"}
        file_row = await store.get_file(session, row.tenant_id, str(row.file_id))
        if file_row is None:
            return {"outcome": "skipped"}
        taken = await store.relations_in_use(session, row.tenant_id, str(row.file_id))

    try:
        staging.discard(row.tenant_id, str(row.file_id), row.version)
        profile, review, report = await asyncio.to_thread(
            _profile_sync, object_store, row, file_row.display_name, taken,
        )
    except ingest.TabularIngestError as exc:
        staging.discard(row.tenant_id, str(row.file_id), row.version)
        logger.info("tabular_profile_failed", extra={"reason": exc.code})
        await _fail(session_factory, row, exc.code)
        return {"outcome": "failed", "reason": exc.code}
    except Exception as exc:
        staging.discard(row.tenant_id, str(row.file_id), row.version)
        logger.warning("tabular_profile_failed", extra={"reason": INTERNAL_ERROR,
                                                        "error_class": type(exc).__name__})
        await _fail(session_factory, row, INTERNAL_ERROR)
        return {"outcome": "failed", "reason": INTERNAL_ERROR}

    async with session_factory() as session:
        await store.save_profile(session, row.tenant_id, str(row.file_id), row.version,
                                 profile, review, report)
        if profile.get("sheet") and profile["sheet"] != row.sheet:
            from sqlalchemy import text
            await session.execute(
                text(f"UPDATE {store.VERSIONS_TABLE} SET sheet = :sheet "
                     "WHERE file_id = :fid AND version = :v AND tenant_id = :tid"),
                {"sheet": profile["sheet"], "fid": str(row.file_id), "v": row.version, "tid": row.tenant_id},
            )
        await session.commit()
    return {"outcome": "needs_review"}


def _profile_sync(object_store, row, display_name: str, taken: set[str]):
    with staging.staged_connection(object_store, row) as (con, labels, sheet):
        relation = ingest.relation_for(display_name, sheet, taken)
        profile = ingest.build_profile(con, labels, relation)
        profile["sheet"] = sheet
        review = ingest.draft_review(profile)
        report = ingest.compute_load_report(con, review)
    return profile, review, report


async def run_publish(session_factory, object_store, file_id: str, version: int) -> dict:
    """Writes `data.parquet` with the approved casts, uploads it, stores the
    canonical contract and switches the served version in one transaction. The
    previous version's objects are removed only after that commit."""
    async with session_factory() as session:
        row = await store.get_version_unscoped(session, file_id, version)
        if row is None or row.status != store.STATUS_PUBLISHING:
            return {"outcome": "skipped"}
        file_row = await store.get_file(session, row.tenant_id, str(row.file_id))
        if file_row is None:
            return {"outcome": "skipped"}

    review = row.review
    if ingest.publish_blockers(review):
        await _fail(session_factory, row, NOT_PUBLISHABLE)
        return {"outcome": "failed", "reason": NOT_PUBLISHABLE}

    key = build_parquet_key(row.tenant_id, str(row.file_id), row.version)
    try:
        report = await asyncio.to_thread(_publish_sync, object_store, row, key)
    except ingest.TabularIngestError as exc:
        await _fail(session_factory, row, exc.code)
        return {"outcome": "failed", "reason": exc.code}
    except Exception as exc:
        logger.warning("tabular_publish_failed", extra={"reason": INTERNAL_ERROR,
                                                        "error_class": type(exc).__name__})
        await _fail(session_factory, row, INTERNAL_ERROR)
        return {"outcome": "failed", "reason": INTERNAL_ERROR}

    contract = ingest.build_contract(review, display_name=file_row.display_name,
                                     sheet=row.sheet, version=row.version)
    async with session_factory() as session:
        try:
            previous = await store.switch_served_version(
                session, row.tenant_id, str(row.file_id), row.version,
                parquet_key=key, contract=contract, load_report=report,
            )
            await session.commit()
        except LookupError:
            # Deleted while publishing: nothing to serve, drop what was written.
            await session.rollback()
            object_store.delete_prefix(version_prefix(row.tenant_id, str(row.file_id), row.version))
            return {"outcome": "skipped"}

    if previous is not None:
        object_store.delete_prefix(version_prefix(row.tenant_id, str(row.file_id), previous))
        staging.discard(row.tenant_id, str(row.file_id), previous)
    return {"outcome": "ready", "previous_version": previous}


def _publish_sync(object_store, row, key: str) -> dict:
    with staging.staged_connection(object_store, row) as (con, _labels, _sheet):
        report = ingest.compute_load_report(con, row.review)
        out = os.path.join(staging.version_dir(row.tenant_id, str(row.file_id), row.version), "data.parquet")
        try:
            ingest.write_parquet(con, row.review, out)
            object_store.put_file(key, out)
        finally:
            if os.path.exists(out):
                os.remove(out)
    return report
