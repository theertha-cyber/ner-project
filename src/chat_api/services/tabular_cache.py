"""Local Parquet cache for uploaded tabular files (design.md Decision 9).

Each chat worker keeps published `data.parquet` copies under
`NER_TABULAR_CACHE_DIR`, keyed `tenant/file/v{version}`, with an LRU byte
budget. Downloads stream from MinIO to a temporary file in the same directory
and are renamed into place, so a reader never sees a partial file. The version
is part of the key and the caller asks for the *served* version only, so a new
publish can never be answered from a stale copy; older versions of the same
file are dropped as soon as a newer one is fetched.
"""

from __future__ import annotations

import os
import tempfile
import threading

from src.shared.config import settings
from src.shared.tabular_files.storage import _check_ids


class ParquetCache:
    def __init__(self, root: str | None = None, max_bytes: int | None = None, object_store_factory=None):
        self.root = root or settings.tabular_cache_dir
        self.max_bytes = max_bytes if max_bytes is not None else settings.tabular_cache_max_bytes
        self._object_store_factory = object_store_factory
        self._object_store = None
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    def _store(self):
        if self._object_store is None:
            if self._object_store_factory is not None:
                self._object_store = self._object_store_factory()
            else:
                from src.shared.tabular_files.storage import TabularObjectStore

                self._object_store = TabularObjectStore()
        return self._object_store

    def _file_dir(self, tenant_id: str, file_id: str) -> str:
        _check_ids(tenant_id, file_id)
        return os.path.join(self.root, tenant_id, str(file_id))

    def path_for(self, tenant_id: str, file_id: str, version: int) -> str:
        _check_ids(tenant_id, file_id, version)
        return os.path.join(self._file_dir(tenant_id, file_id), f"v{version}.parquet")

    def _key_lock(self, path: str) -> threading.Lock:
        with self._lock:
            return self._key_locks.setdefault(path, threading.Lock())

    def get(self, tenant_id: str, file_id: str, version: int, object_key: str) -> str:
        """Local path of the served version's Parquet, downloading on a miss.
        Blocking; call from a worker thread."""
        path = self.path_for(tenant_id, file_id, version)
        with self._key_lock(path):
            if os.path.exists(path):
                os.utime(path)
                return path
            directory = os.path.dirname(path)
            os.makedirs(directory, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=directory, suffix=".part")
            os.close(fd)
            try:
                self._store().download_to(object_key, tmp)
                os.replace(tmp, path)
            finally:
                if os.path.exists(tmp):
                    os.remove(tmp)
            self._drop_other_versions(directory, os.path.basename(path))
        self._evict(keep=path)
        return path

    def _drop_other_versions(self, directory: str, keep_name: str) -> None:
        for name in os.listdir(directory):
            if name.endswith(".parquet") and name != keep_name:
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass

    def _entries(self) -> list[tuple[float, int, str]]:
        entries = []
        for base, _dirs, names in os.walk(self.root):
            for name in names:
                if name.endswith(".parquet"):
                    full = os.path.join(base, name)
                    try:
                        stat = os.stat(full)
                    except OSError:
                        continue
                    entries.append((stat.st_mtime, stat.st_size, full))
        return entries

    def _evict(self, keep: str) -> None:
        with self._lock:
            entries = sorted(self._entries())
            total = sum(size for _, size, _ in entries)
            for _mtime, size, full in entries:
                if total <= self.max_bytes:
                    break
                if full == keep:
                    continue
                try:
                    os.remove(full)
                    total -= size
                except OSError:
                    pass
