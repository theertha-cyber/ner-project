import time
import threading
from collections import OrderedDict
from src.shared.config import settings


class CachedModel:
    def __init__(self, model_id: str, model, memory_bytes: int):
        self.model_id = model_id
        self.model = model
        self.memory_bytes = memory_bytes
        self.last_access = time.monotonic()
        self.loaded_at = time.monotonic()

    def touch(self):
        self.last_access = time.monotonic()


class ModelCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, CachedModel] = OrderedDict()
        self._current_memory = 0
        self._max_memory = settings.model_cache_memory_limit_gb * 1024 * 1024 * 1024
        self._ttl_seconds = settings.model_cache_ttl_minutes * 60

    def get(self, model_id: str) -> CachedModel | None:
        with self._lock:
            entry = self._cache.get(model_id)
            if entry is None:
                return None
            if time.monotonic() - entry.last_access > self._ttl_seconds:
                self._evict(model_id)
                return None
            entry.touch()
            self._cache.move_to_end(model_id)
            return entry

    def put(self, model_id: str, model, memory_bytes: int) -> CachedModel:
        with self._lock:
            while self._current_memory + memory_bytes > self._max_memory:
                if not self._cache:
                    break
                lru_id = next(iter(self._cache))
                self._evict(lru_id)

            entry = CachedModel(model_id, model, memory_bytes)
            self._cache[model_id] = entry
            self._current_memory += memory_bytes
            return entry

    def remove(self, model_id: str):
        with self._lock:
            self._evict(model_id)

    def _evict(self, model_id: str):
        entry = self._cache.pop(model_id, None)
        if entry:
            self._current_memory -= entry.memory_bytes

    @property
    def memory_used_bytes(self) -> int:
        with self._lock:
            return self._current_memory

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._cache)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._current_memory = 0


model_cache = ModelCache()
