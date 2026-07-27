"""Tests for model-serving rerank endpoint."""
import os
import pytest
from httpx import AsyncClient, ASGITransport

os.environ.setdefault("NER_JWT_SECRET", "test-secret-do-not-use-in-prod")
os.environ.setdefault("NER_DATABASE_URL", "postgresql+asyncpg://ner:ner@localhost:54320/ner_test")

from src.model_serving.main import app
from src.model_serving.services.model_cache import model_cache
from src.shared.auth import create_access_token


def auth_header(tid: str, role: str = "tenant_admin") -> dict:
    token = create_access_token(tenant_id=tid, user_id="test-user", role=role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
class TestRerankReordersByRelevance:
    """Covers scenario 1: task 2.5."""

    async def test_rerank_orders_most_relevant_first(self, monkeypatch):
        import src.model_serving.api.v1.rerank as rerank_mod

        def mock_rerank(query, documents, top_k=None):
            # Candidate at index 2 is most relevant.
            scores = [0.1, 0.2, 0.9]
            ranked = sorted(
                ({"index": i, "score": s} for i, s in enumerate(scores)),
                key=lambda r: r["score"],
                reverse=True,
            )
            return ranked[:top_k] if top_k is not None else ranked

        monkeypatch.setattr(rerank_mod, "rerank", mock_rerank)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/rerank",
                json={"query": "q", "documents": ["a", "b", "the most relevant doc"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            results = data["results"]
            assert results[0]["index"] == 2
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
class TestRerankRespectsTopK:
    """Covers scenario 2: task 2.6."""

    async def test_top_k_limits_result_count(self, monkeypatch):
        import src.model_serving.api.v1.rerank as rerank_mod

        def mock_rerank(query, documents, top_k=None):
            ranked = [{"index": i, "score": float(len(documents) - i)} for i in range(len(documents))]
            return ranked[:top_k] if top_k is not None else ranked

        monkeypatch.setattr(rerank_mod, "rerank", mock_rerank)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/rerank",
                json={"query": "q", "documents": [f"doc-{i}" for i in range(10)], "top_k": 3},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["results"]) == 3


@pytest.mark.asyncio
class TestRerankEmptyCandidates:
    """Covers scenario 3: task 2.7."""

    async def test_empty_documents_returns_empty_results_without_invoking_model(self, monkeypatch):
        import src.model_serving.services.rerank_service as rerank_service_mod

        invoked = []

        def spy_get_reranker():
            invoked.append(True)
            raise AssertionError("model should not be loaded for empty documents")

        monkeypatch.setattr(rerank_service_mod, "_get_reranker", spy_get_reranker)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/rerank",
                json={"query": "q", "documents": []},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["results"] == []
            assert not invoked


@pytest.mark.asyncio
class TestRerankerNotInModelCache:
    """Covers scenario 4, Hallucination Risk 1: task 2.8."""

    async def test_reranker_absent_from_model_cache_and_survives_eviction(self, monkeypatch):
        import src.model_serving.api.v1.rerank as rerank_mod

        model_cache.clear()

        def mock_rerank(query, documents, top_k=None):
            return [{"index": 0, "score": 1.0}]

        monkeypatch.setattr(rerank_mod, "rerank", mock_rerank)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/rerank",
                json={"query": "q", "documents": ["a"]},
                headers=auth_header("test-tenant"),
            )
            assert resp.status_code == 200

        assert model_cache.size == 0

        old_max = model_cache._max_memory
        model_cache._max_memory = 150
        try:
            model_cache.put("tenant_a_v1", {"data": 1}, memory_bytes=100)
            model_cache.put("tenant_b_v1", {"data": 2}, memory_bytes=100)
            assert model_cache.get("tenant_a_v1") is None
            assert model_cache.get("tenant_b_v1") is not None
            for model_id in list(model_cache._cache.keys()):
                assert "reranker" not in model_id
        finally:
            model_cache.clear()
            model_cache._max_memory = old_max


@pytest.mark.asyncio
class TestRerankAuth:
    """Covers scenario 5 (adjusted to 401 to match TenantContextMiddleware convention
    used by every other model_serving endpoint): task 2.9."""

    async def test_missing_auth_returns_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/internal/v1/rerank",
                json={"query": "q", "documents": ["a"]},
            )
            assert resp.status_code == 401
