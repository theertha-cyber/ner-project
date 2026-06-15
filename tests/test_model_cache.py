import time
import pytest
from src.model_serving.services.model_cache import ModelCache, CachedModel


@pytest.fixture
def cache():
    c = ModelCache()
    c._max_memory = 1024 * 1024 * 100
    c._ttl_seconds = 300
    return c


class TestLoadModelOnFirstRequest:
    def test_load_and_retrieve(self, cache):
        model_id = "tenant_a_v1"
        cache.put(model_id, {"dummy": "model"}, memory_bytes=100)
        entry = cache.get(model_id)
        assert entry is not None
        assert entry.model_id == model_id

    def test_returns_none_for_missing(self, cache):
        assert cache.get("nonexistent") is None

    def test_put_then_get_returns_same_model(self, cache):
        model_obj = {"layers": ["a", "b"]}
        cache.put("m1", model_obj, memory_bytes=200)
        entry = cache.get("m1")
        assert entry.model is model_obj


class TestCacheHitOnSubsequentRequest:
    def test_second_get_returns_cached(self, cache):
        cache.put("m1", {"data": 1}, memory_bytes=100)
        first = cache.get("m1")
        second = cache.get("m1")
        assert first is second
        assert first.model["data"] == 1

    def test_get_updates_last_access(self, cache):
        cache.put("m1", {"data": 1}, memory_bytes=100)
        e1 = cache.get("m1")
        old_access = e1.last_access
        time.sleep(0.01)
        e2 = cache.get("m1")
        assert e2.last_access > old_access


class TestLRUEvictionOnMemoryPressure:
    def test_evicts_lru_when_over_limit(self, cache):
        cache._max_memory = 150
        cache.put("m1", {"data": 1}, memory_bytes=100)
        cache.put("m2", {"data": 2}, memory_bytes=100)
        assert cache.get("m1") is None
        assert cache.get("m2") is not None

    def test_partial_eviction_frees_enough(self, cache):
        cache._max_memory = 200
        cache.put("m1", {"data": 1}, memory_bytes=80)
        cache.put("m2", {"data": 2}, memory_bytes=80)
        cache.put("m3", {"data": 3}, memory_bytes=100)
        assert cache.get("m1") is None
        assert cache.get("m3") is not None
        remaining = cache.memory_used_bytes
        assert remaining <= cache._max_memory

    def test_remove_frees_memory(self, cache):
        cache._max_memory = 200
        cache.put("m1", {"data": 1}, memory_bytes=100)
        cache.remove("m1")
        assert cache.memory_used_bytes == 0
        assert cache.get("m1") is None

    def test_clear_empties_cache(self, cache):
        cache._max_memory = 500
        cache.put("m1", {"data": 1}, memory_bytes=100)
        cache.put("m2", {"data": 2}, memory_bytes=200)
        cache.clear()
        assert cache.size == 0
        assert cache.memory_used_bytes == 0
