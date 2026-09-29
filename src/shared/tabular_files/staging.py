"""Process-local staging DuckDB files for uploaded tabular versions.

Profiling (worker), the review load report (gateway) and publishing (worker)
all read the same all-text staging table. Each process keeps its own copy under
`NER_TABULAR_STAGING_DIR`, rebuilt from the original object on a miss, so no
staging artifact is ever shared or stored outside the two keys ADR-019 names.
Paths are built from server identifiers only.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
import threading

from src.shared.config import settings
from src.shared.tabular_files import ingest
from src.shared.tabular_files.storage import _check_ids

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def staging_root() -> str:
    return settings.tabular_staging_dir or os.path.join(tempfile.gettempdir(), "ner-tabular-staging")


def version_dir(tenant_id: str, file_id: str, version: int) -> str:
    _check_ids(tenant_id, file_id, version)
    return os.path.join(staging_root(), tenant_id, str(file_id), f"v{version}")


def _lock_for(path: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(path, threading.Lock())


def ensure_staged(object_store, version_row, max_rows: int | None = None) -> tuple[str, list[str], str | None]:
    """Returns `(staging_path, labels, sheet)` for one version, staging it from
    the original object when this process has no copy yet."""
    directory = version_dir(version_row.tenant_id, str(version_row.file_id), version_row.version)
    staging_path = os.path.join(directory, "staging.duckdb")
    with _lock_for(staging_path):
        if os.path.exists(staging_path):
            con = ingest.open_staging(staging_path)
            try:
                labels = ingest.staged_labels(con)
            finally:
                con.close()
            return staging_path, labels, version_row.sheet
        os.makedirs(directory, exist_ok=True)
        original = os.path.join(directory, f"original.{version_row.source_kind}")
        try:
            object_store.download_to(version_row.original_key, original)
            labels, sheet = ingest.stage_original(
                original, version_row.source_kind, version_row.sheet, staging_path,
                max_rows or settings.tabular_max_rows, directory,
            )
        finally:
            if os.path.exists(original):
                os.remove(original)
        return staging_path, labels, sheet


@contextlib.contextmanager
def staged_connection(object_store, version_row):
    staging_path, labels, sheet = ensure_staged(object_store, version_row)
    con = ingest.open_staging(staging_path)
    try:
        yield con, labels, sheet
    finally:
        con.close()


def discard(tenant_id: str, file_id: str, version: int | None = None) -> None:
    """Drops this process's staging copies for one version or a whole file."""
    if version is None:
        _check_ids(tenant_id, file_id)
        path = os.path.join(staging_root(), tenant_id, str(file_id))
    else:
        path = version_dir(tenant_id, file_id, version)
    shutil.rmtree(path, ignore_errors=True)
