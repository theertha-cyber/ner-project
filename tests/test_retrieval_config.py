import pytest

from src.shared.config import settings
from src.shared.retrieval.config import RetrievalConfig
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever

pytestmark = [pytest.mark.asyncio]


def _make_results(n: int) -> list[RetrievalResult]:
    return [
        RetrievalResult(document_id=f"doc-{i}", chunk_index=i, chunk_text=f"chunk {i}", similarity_score=1.0 - i * 0.01)
        for i in range(n)
    ]


class SpyRetriever:
    def __init__(self, results: list[RetrievalResult]):
        self.results = results
        self.calls: list[dict] = []

    async def retrieve(self, query, session, schema, top_k=None, metadata_filter=None):
        self.calls.append({"top_k": top_k, "metadata_filter": metadata_filter})
        return self.results[:top_k] if top_k is not None else self.results


class SpyReranker:
    def __init__(self):
        self.calls: list[dict] = []

    async def rerank(self, query, results, top_k=None, jwt_token=None):
        self.calls.append({"query": query, "top_k": top_k})
        return results


class TestPerInstanceOverride:
    """Covers verification.md row 50."""

    async def test_instance_override_wins_over_global_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)

        wrapped = SpyRetriever(_make_results(5))
        reranker = SpyReranker()
        config = RetrievalConfig(reranker_enabled=False)
        retriever = RerankingRetriever(wrapped, reranker, config=config)

        results = await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=5)

        assert reranker.calls == []
        assert results == wrapped.results


class TestAbsentOverrideFallsBack:
    """Covers verification.md row 51."""

    async def test_absent_override_uses_global_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "retrieval_top_k", 7)
        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 12)

        wrapped = SpyRetriever(_make_results(12))
        reranker = SpyReranker()
        retriever = RerankingRetriever(wrapped, reranker)

        results = await retriever.retrieve("q", session=object(), schema="tenant_x")

        assert wrapped.calls[0]["top_k"] == 12
        assert reranker.calls[0]["top_k"] == 7
        assert len(results) == 7


class TestOverridesDoNotLeak:
    """Covers verification.md row 52."""

    async def test_overrides_do_not_mutate_global_settings(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "retrieval_top_k", 5)
        before_enabled = settings.reranker_enabled
        before_top_k = settings.retrieval_top_k

        retriever_off = RerankingRetriever(
            SpyRetriever(_make_results(5)), SpyReranker(), config=RetrievalConfig(reranker_enabled=False, top_k=3)
        )
        retriever_on = RerankingRetriever(
            SpyRetriever(_make_results(5)), SpyReranker(), config=RetrievalConfig(reranker_enabled=True, top_k=5)
        )

        await retriever_off.retrieve("q", session=object(), schema="tenant_x")
        await retriever_on.retrieve("q", session=object(), schema="tenant_x")

        assert settings.reranker_enabled == before_enabled
        assert settings.retrieval_top_k == before_top_k
        assert retriever_on.reranker.calls != []
        assert retriever_off.reranker.calls == []
