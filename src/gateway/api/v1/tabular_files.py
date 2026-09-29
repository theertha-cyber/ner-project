"""Tenant-admin uploaded tabular files API (ADR-018, ADR-019).

`/api/v1/data-sources/files`: upload, list, profile, review, publish, new
version and delete. Every route requires a valid JWT, `require_tenant_admin`
and `resolve_tenant_from_jwt`; the tenant id is taken only from the
authenticated context — no path, query or body field names a tenant. Object
keys are built server-side from that tenant id, a server-generated file id and
an integer version (`src/shared/tabular_files/storage.py`).

Errors use the data-sources shape
`{"error": {"code": <FINITE_CODE>, "message": <safe text>, "request_id": ...}}`
and never quote cell values, parser diagnostics or raw exceptions.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import logging
import os
import re
import shutil
import tempfile
import unicodedata

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from python_multipart import MultipartParser
from python_multipart.multipart import parse_options_header
from sqlalchemy.ext.asyncio import AsyncSession

from src.gateway.dependencies import get_db, require_tenant_admin, resolve_tenant_from_jwt
from src.shared.config import settings
from src.shared.data_sources.service import check_replay, store_replay
from src.shared.tabular_files import ingest, staging, store
from src.shared.tabular_files.storage import (
    TabularObjectStore,
    file_prefix,
    original_key,
    version_prefix,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/data-sources/files", tags=["tenant-tabular-files"])

ALLOWED_EXTENSIONS = {".csv": "csv", ".xlsx": "xlsx"}
_IDEMPOTENCY_KEY_RE = re.compile(r"^[\x20-\x7E]{1,128}$")
# Multipart framing around the file part; a request larger than the file cap
# plus this is refused from its Content-Length before any byte is read.
_MULTIPART_OVERHEAD = 64 * 1024
_MAX_FIELD_BYTES = 1024

_CODE_STATUS = {
    "UNSUPPORTED_FILE_TYPE": 415,
    "FILE_TOO_LARGE": 413,
    "FILE_LIMIT_REACHED": 409,
    "FILE_NOT_FOUND": 404,
    "VERSION_NOT_FOUND": 404,
    "INVALID_REQUEST": 422,
    "INVALID_STATE": 409,
    "IDEMPOTENCY_KEY_REQUIRED": 400,
    "IDEMPOTENCY_KEY_REUSED": 409,
    ingest.DATE_FORMAT_REQUIRED: 409,
    ingest.DESCRIPTION_REQUIRED: 409,
    ingest.DUPLICATE_IDENTIFIER: 409,
    ingest.NO_INCLUDED_COLUMNS: 409,
    "TABULAR_FILES_DISABLED": 503,
    "INGEST_QUEUE_UNAVAILABLE": 503,
    "STAGING_UNAVAILABLE": 503,
    "INTERNAL_ERROR": 500,
}

_CODE_HINTS = {
    "UNSUPPORTED_FILE_TYPE": "Only .csv and .xlsx files can be uploaded.",
    "FILE_TOO_LARGE": f"Files are limited to {settings.tabular_max_file_bytes // (1024 * 1024)} MB.",
    "FILE_LIMIT_REACHED": f"Your tenant already has {settings.tabular_max_files_per_tenant} files; delete one first.",
    "FILE_NOT_FOUND": "No file with that identifier exists for your tenant.",
    "VERSION_NOT_FOUND": "No version with that number exists for this file.",
    "INVALID_STATE": "This version is not in a state that allows that action.",
    "IDEMPOTENCY_KEY_REQUIRED": "Send a unique Idempotency-Key header (1-128 printable ASCII).",
    "IDEMPOTENCY_KEY_REUSED": "That Idempotency-Key was already used with a different request body.",
    ingest.DESCRIPTION_REQUIRED: "Add a table description before publishing.",
    ingest.NO_INCLUDED_COLUMNS: "Include at least one column before publishing.",
    "TABULAR_FILES_DISABLED": "Uploaded files are turned off for this deployment.",
    "INGEST_QUEUE_UNAVAILABLE": "The processing queue is temporarily unavailable; try again shortly.",
    "STAGING_UNAVAILABLE": "The file could not be prepared for review; try again shortly.",
}


class UploadRejected(Exception):
    def __init__(self, code: str, message: str | None = None):
        super().__init__(code)
        self.code = code
        self.message = message


# ------------------------------------------------------------ seams (tests)

@functools.lru_cache(maxsize=1)
def _default_object_store() -> TabularObjectStore:
    return TabularObjectStore()


def get_object_store() -> TabularObjectStore:
    return _default_object_store()


def _enqueue_profile(file_id: str, version: int) -> None:
    from src.shared.tabular_files.tasks import enqueue_profile

    enqueue_profile(file_id, version)


def _enqueue_publish(file_id: str, version: int) -> None:
    from src.shared.tabular_files.tasks import enqueue_publish

    enqueue_publish(file_id, version)


# ------------------------------------------------------------------ helpers

def _error(request: Request, code: str, message: str | None = None, extra: dict | None = None):
    body = {"code": code, "message": message or _CODE_HINTS.get(code, "Request failed."),
            "request_id": getattr(request.state, "request_id", "") or ""}
    if extra:
        body.update(extra)
    return JSONResponse(status_code=_CODE_STATUS.get(code, 500), content={"error": body})


def _iso(value):
    return value.isoformat() if hasattr(value, "isoformat") else value


def _display_name(filename: str) -> str:
    name = os.path.basename(filename.replace("\\", "/")).strip()
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C")
    return name[:255]


def _extension(filename: str) -> str | None:
    return ALLOWED_EXTENSIONS.get(os.path.splitext(filename.lower())[1])


async def _receive_upload(request: Request, directory: str) -> tuple[str, str, str | None]:
    """Streams a `multipart/form-data` body with a `file` part (and an optional
    `sheet` text part) to disk. The extension is checked from the part headers
    before any file byte is written, and the size cap is enforced chunk by
    chunk — an oversized upload is refused once the cap is crossed, never
    buffered whole. Returns `(temp_path, filename, sheet)`."""
    max_bytes = settings.tabular_max_file_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes + _MULTIPART_OVERHEAD:
        raise UploadRejected("FILE_TOO_LARGE")
    content_type, options = parse_options_header(request.headers.get("content-type", ""))
    boundary = options.get(b"boundary")
    if content_type != b"multipart/form-data" or not boundary:
        raise UploadRejected("INVALID_REQUEST", "Send the file as multipart/form-data in a 'file' field.")

    state = {"headers": {}, "field": b"", "value": b"", "part": None, "fh": None,
             "size": 0, "filename": None, "sheet": None, "path": None}

    def on_part_begin():
        state["headers"], state["part"] = {}, None

    def on_header_field(data, start, end):
        state["field"] += data[start:end]

    def on_header_value(data, start, end):
        state["value"] += data[start:end]

    def on_header_end():
        state["headers"][state["field"].decode("latin-1").lower()] = state["value"]
        state["field"], state["value"] = b"", b""

    def on_headers_finished():
        _, params = parse_options_header(state["headers"].get("content-disposition", b""))
        name = params.get(b"name", b"").decode("utf-8", "replace")
        if name == "file":
            if state["filename"] is not None:
                raise UploadRejected("INVALID_REQUEST", "Send exactly one file.")
            filename = params.get(b"filename", b"").decode("utf-8", "replace")
            if not filename or _extension(filename) is None:
                raise UploadRejected("UNSUPPORTED_FILE_TYPE")
            state["filename"] = filename
            state["path"] = os.path.join(directory, "upload" + os.path.splitext(filename.lower())[1])
            state["fh"] = open(state["path"], "wb")
            state["part"] = "file"
        elif name == "sheet":
            state["part"], state["sheet"] = "sheet", b""
        else:
            state["part"] = "ignored"

    def on_part_data(data, start, end):
        chunk = data[start:end]
        if state["part"] == "file":
            state["size"] += len(chunk)
            if state["size"] > max_bytes:
                raise UploadRejected("FILE_TOO_LARGE")
            state["fh"].write(chunk)
        elif state["part"] == "sheet":
            state["sheet"] += chunk
            if len(state["sheet"]) > _MAX_FIELD_BYTES:
                raise UploadRejected("INVALID_REQUEST", "'sheet' is too long.")

    def on_part_end():
        if state["part"] == "file" and state["fh"] is not None:
            state["fh"].close()
            state["fh"] = None

    parser = MultipartParser(boundary, {
        "on_part_begin": on_part_begin, "on_header_field": on_header_field,
        "on_header_value": on_header_value, "on_header_end": on_header_end,
        "on_headers_finished": on_headers_finished, "on_part_data": on_part_data,
        "on_part_end": on_part_end,
    })
    try:
        async for chunk in request.stream():
            parser.write(chunk)
        parser.finalize()
    finally:
        if state["fh"] is not None:
            state["fh"].close()
    if state["filename"] is None:
        raise UploadRejected("INVALID_REQUEST", "Send the file in a 'file' field.")
    if state["size"] == 0:
        raise UploadRejected("INVALID_REQUEST", "The uploaded file is empty.")
    sheet = state["sheet"].decode("utf-8", "replace").strip() if state["sheet"] else None
    return state["path"], state["filename"], sheet or None


def _pending(file_row, versions: list):
    latest = versions[-1] if versions else None
    if latest is None or latest.version == file_row.served_version:
        return None
    if latest.status in (store.STATUS_SUPERSEDED, store.STATUS_DELETED):
        return None
    return latest


def _file_body(file_row, versions: list) -> dict:
    by_number = {v.version: v for v in versions}
    served = by_number.get(file_row.served_version) if file_row.served_version else None
    pending = _pending(file_row, versions)
    row_count = None
    if served is not None and served.load_report:
        row_count = served.load_report.get("rows_to_load")
    elif pending is not None and pending.profile:
        row_count = pending.profile.get("row_count")
    return {
        "id": str(file_row.id),
        "display_name": file_row.display_name,
        "status": file_row.status,
        "served_version": file_row.served_version,
        "served": None if served is None else {
            "version": served.version, "status": served.status, "sheet": served.sheet,
            "published_at": _iso(served.published_at),
        },
        "pending": None if pending is None else {
            "version": pending.version, "status": pending.status,
            "failure_reason": pending.failure_reason, "sheet": pending.sheet,
        },
        "row_count": row_count,
        "updated_at": _iso(file_row.updated_at),
    }


async def _render_file(db, tenant_id: str, file_row) -> dict:
    versions = await store.list_versions(db, tenant_id, str(file_row.id))
    return _file_body(file_row, versions)


def _served_contract(versions: list, served_version: int | None) -> dict | None:
    for v in versions:
        if v.version == served_version and v.status == store.STATUS_READY:
            return v.contract
    return None


async def _review_body(db, tenant_id: str, file_row, version_row) -> dict:
    versions = await store.list_versions(db, tenant_id, str(file_row.id))
    review = version_row.review
    diff = None
    if review and file_row.served_version and file_row.served_version != version_row.version:
        diff = ingest.schema_diff(_served_contract(versions, file_row.served_version), review)
    return {
        "file": _file_body(file_row, versions),
        "version": version_row.version,
        "status": version_row.status,
        "failure_reason": version_row.failure_reason,
        "source_filename": version_row.source_filename,
        "sheet": version_row.sheet,
        "profile": version_row.profile,
        "review": review,
        "load_report": version_row.load_report,
        "blockers": ingest.publish_blockers(review) if review else [],
        "schema_diff": diff,
    }


def _disabled(request: Request):
    if not settings.tabular_files_enabled:
        return _error(request, "TABULAR_FILES_DISABLED")
    return None


async def _store_original(tenant_id: str, file_id: str, version: int, kind: str, path: str) -> str:
    key = original_key(tenant_id, file_id, version, kind)
    await asyncio.to_thread(get_object_store().put_file, key, path)
    return key


async def _enqueue_or_fail(db, tenant_id: str, file_id: str, version: int, enqueue) -> bool:
    try:
        enqueue(file_id, version)
        return True
    except Exception as exc:
        logger.warning("tabular_enqueue_failed", extra={"error_class": type(exc).__name__})
        await store.set_version_status(db, tenant_id, file_id, version, store.STATUS_FAILED,
                                       "INGEST_QUEUE_UNAVAILABLE")
        await db.commit()
        return False


# ------------------------------------------------------------------- routes

@router.post("", status_code=201)
async def upload_file(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    if (refused := _disabled(request)) is not None:
        return refused
    if await store.count_active_files(db, tenant_id) >= settings.tabular_max_files_per_tenant:
        return _error(request, "FILE_LIMIT_REACHED")
    directory = tempfile.mkdtemp(prefix="tabular-upload-")
    file_id = None
    try:
        try:
            path, filename, sheet = await _receive_upload(request, directory)
        except UploadRejected as exc:
            return _error(request, exc.code, exc.message)
        kind = _extension(filename)
        display_name = _display_name(filename)
        file_id = await store.create_file(db, tenant_id, display_name)
        key = await _store_original(tenant_id, file_id, 1, kind, path)
        await store.create_version(db, tenant_id, file_id, 1, source_kind=kind,
                                   source_filename=display_name, original_key=key, sheet=sheet)
        await db.commit()
    except Exception as exc:
        # Class only, like the other handlers here: a driver traceback carries the
        # platform SQL and its bound values (ADR-013/015 telemetry redaction).
        logger.warning("tabular_upload_failed", extra={"error_class": type(exc).__name__})
        await db.rollback()
        if file_id is not None:
            try:
                await asyncio.to_thread(get_object_store().delete_prefix, file_prefix(tenant_id, file_id))
            except Exception:
                pass
        return _error(request, "INTERNAL_ERROR")
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    if not await _enqueue_or_fail(db, tenant_id, file_id, 1, _enqueue_profile):
        return _error(request, "INGEST_QUEUE_UNAVAILABLE")
    file_row = await store.get_file(db, tenant_id, file_id)
    return JSONResponse(status_code=201, content=await _render_file(db, tenant_id, file_row))


@router.get("")
async def list_files(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    limits = {"max_file_bytes": settings.tabular_max_file_bytes, "max_rows": settings.tabular_max_rows,
              "max_files": settings.tabular_max_files_per_tenant, "extensions": sorted(ALLOWED_EXTENSIONS)}
    if not settings.tabular_files_enabled:
        return {"enabled": False, "files": [], "limits": limits}
    files = [await _render_file(db, tenant_id, row) for row in await store.list_files(db, tenant_id)]
    return {"enabled": True, "files": files, "limits": limits}


async def _load(request: Request, db, tenant_id: str, file_id: str, version: int | None = None):
    file_row = await store.get_file(db, tenant_id, file_id)
    if file_row is None:
        return None, None, _error(request, "FILE_NOT_FOUND")
    if version is None:
        return file_row, None, None
    version_row = await store.get_version(db, tenant_id, file_id, version)
    if version_row is None or version_row.status == store.STATUS_DELETED:
        return file_row, None, _error(request, "VERSION_NOT_FOUND")
    return file_row, version_row, None


@router.get("/{file_id}/versions/{version}/profile")
async def get_profile(
    file_id: str,
    version: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    file_row, version_row, failed = await _load(request, db, tenant_id, file_id, version)
    if failed is not None:
        return failed
    return await _review_body(db, tenant_id, file_row, version_row)


@router.put("/{file_id}/versions/{version}/review")
async def put_review(
    file_id: str,
    version: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    if (refused := _disabled(request)) is not None:
        return refused
    file_row, version_row, failed = await _load(request, db, tenant_id, file_id, version)
    if failed is not None:
        return failed
    if version_row.status != store.STATUS_NEEDS_REVIEW or not version_row.review:
        return _error(request, "INVALID_STATE")
    try:
        edit = await request.json()
    except Exception:
        return _error(request, "INVALID_REQUEST", "Request body must be valid JSON.")
    try:
        review = ingest.validate_review(edit, version_row.profile, version_row.review)
    except ingest.ReviewInvalid as exc:
        return _error(request, "INVALID_REQUEST", exc.message, {"field": exc.field})

    def _recompute():
        with staging.staged_connection(get_object_store(), version_row) as (con, _labels, _sheet):
            return ingest.compute_load_report(con, review)

    try:
        report = await asyncio.to_thread(_recompute)
    except Exception as exc:
        logger.warning("tabular_review_staging_failed", extra={"error_class": type(exc).__name__})
        return _error(request, "STAGING_UNAVAILABLE")
    await store.save_review(db, tenant_id, file_id, version, review, report)
    await db.commit()
    version_row = await store.get_version(db, tenant_id, file_id, version)
    return await _review_body(db, tenant_id, file_row, version_row)


@router.post("/{file_id}/versions/{version}/publish", status_code=202)
async def publish_version(
    file_id: str,
    version: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    if (refused := _disabled(request)) is not None:
        return refused
    key = request.headers.get("Idempotency-Key")
    if key is None or not _IDEMPOTENCY_KEY_RE.match(key):
        return _error(request, "IDEMPOTENCY_KEY_REQUIRED")
    raw = await request.body()
    digest = hashlib.sha256(raw).hexdigest()
    path = request.url.path
    seen = await check_replay(db, tenant_id, request.method, path, key, digest)
    if seen is not None:
        kind, status_code, stored = seen
        if kind == "reused":
            return _error(request, "IDEMPOTENCY_KEY_REUSED")
        return JSONResponse(status_code=status_code, content=stored, headers={"Idempotent-Replay": "true"})

    file_row, version_row, failed = await _load(request, db, tenant_id, file_id, version)
    if failed is not None:
        return failed
    if version_row.status != store.STATUS_NEEDS_REVIEW or not version_row.review:
        return _error(request, "INVALID_STATE")
    blockers = ingest.publish_blockers(version_row.review)
    if blockers:
        first = blockers[0]
        message = _CODE_HINTS.get(first["code"])
        if first.get("column"):
            message = {
                ingest.DATE_FORMAT_REQUIRED: f"Choose a date format for column '{first['column']}'.",
                ingest.DUPLICATE_IDENTIFIER: f"Two included columns are named '{first['column']}'.",
            }[first["code"]]
        return _error(request, first["code"], message, {"blockers": blockers})

    await store.set_version_status(db, tenant_id, file_id, version, store.STATUS_PUBLISHING)
    await db.commit()
    if not await _enqueue_or_fail(db, tenant_id, file_id, version, _enqueue_publish):
        return _error(request, "INGEST_QUEUE_UNAVAILABLE")
    file_row = await store.get_file(db, tenant_id, file_id)
    body = {"file": await _render_file(db, tenant_id, file_row), "version": version, "status": store.STATUS_PUBLISHING}
    await store_replay(db, tenant_id, request.method, path, key, digest, 202, body)
    await db.commit()
    return JSONResponse(status_code=202, content=body)


@router.post("/{file_id}/versions", status_code=201)
async def upload_new_version(
    file_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    if (refused := _disabled(request)) is not None:
        return refused
    file_row, _v, failed = await _load(request, db, tenant_id, file_id)
    if failed is not None:
        return failed
    directory = tempfile.mkdtemp(prefix="tabular-upload-")
    superseded: list[int] = []
    try:
        try:
            path, filename, sheet = await _receive_upload(request, directory)
        except UploadRejected as exc:
            return _error(request, exc.code, exc.message)
        kind = _extension(filename)
        version = await store.next_version_number(db, file_id)
        # A newer upload replaces any version still waiting for review; the
        # served version is untouched until the new one is published.
        for existing in await store.list_versions(db, tenant_id, file_id):
            if existing.version != file_row.served_version and existing.status in (
                    store.STATUS_PROFILING, store.STATUS_NEEDS_REVIEW, store.STATUS_FAILED):
                await store.set_version_status(db, tenant_id, file_id, existing.version, store.STATUS_SUPERSEDED)
                superseded.append(existing.version)
        key = await _store_original(tenant_id, file_id, version, kind, path)
        await store.create_version(db, tenant_id, file_id, version, source_kind=kind,
                                   source_filename=_display_name(filename), original_key=key, sheet=sheet)
        await db.commit()
    except Exception as exc:
        # Class only, like the other handlers here: a driver traceback carries the
        # platform SQL and its bound values (ADR-013/015 telemetry redaction).
        logger.warning("tabular_version_upload_failed", extra={"error_class": type(exc).__name__})
        await db.rollback()
        return _error(request, "INTERNAL_ERROR")
    finally:
        shutil.rmtree(directory, ignore_errors=True)
    for old in superseded:
        await asyncio.to_thread(get_object_store().delete_prefix, version_prefix(tenant_id, file_id, old))
        staging.discard(tenant_id, file_id, old)
    if not await _enqueue_or_fail(db, tenant_id, file_id, version, _enqueue_profile):
        return _error(request, "INGEST_QUEUE_UNAVAILABLE")
    file_row = await store.get_file(db, tenant_id, file_id)
    return JSONResponse(status_code=201, content=await _render_file(db, tenant_id, file_row))


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(require_tenant_admin),
    tenant_id: str = Depends(resolve_tenant_from_jwt),
):
    """Marks the file deleted first — chat stops offering it on the next turn —
    then removes every version's objects and this process's staging copies."""
    file_row, _v, failed = await _load(request, db, tenant_id, file_id)
    if failed is not None:
        return failed
    await store.mark_deleted(db, tenant_id, file_id)
    await db.commit()
    try:
        await asyncio.to_thread(get_object_store().delete_prefix, file_prefix(tenant_id, file_id))
    except Exception as exc:
        logger.warning("tabular_delete_objects_failed", extra={"error_class": type(exc).__name__})
    staging.discard(tenant_id, file_id)
    return {"id": file_id, "status": store.STATUS_DELETED}
