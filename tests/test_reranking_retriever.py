import pytest
from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.retriever import RerankingRetriever, Retriever

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
    def __init__(self, reordered: list[RetrievalResult] | None):
        self.reordered = reordered
        self.calls: list[dict] = []

    async def rerank(self, query, results, top_k=None, jwt_token=None):
        self.calls.append({"query": query, "results": results, "top_k": top_k})
        if self.reordered is None:
            return None
        return self.reordered


class TestOverfetchThenTruncate:
    """Covers scenario 8, Hallucination Risk 4: task 4.6."""

    async def test_requests_candidate_count_and_truncates_to_top_k(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 20)

        candidates = _make_results(20)
        wrapped = SpyRetriever(candidates)
        reranker = SpyReranker(reordered=candidates)

        retriever = RerankingRetriever(wrapped, reranker)
        results = await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=5)

        assert wrapped.calls[0]["top_k"] == 20
        assert len(reranker.calls[0]["results"]) == 20
        assert len(results) <= 5


class TestFallbackOnRerankFailure:
    """Covers scenario 9: task 4.7."""

    async def test_falls_back_to_wrapped_order_when_reranker_returns_none(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 20)

        candidates = _make_results(20)
        wrapped = SpyRetriever(candidates)
        reranker = SpyReranker(reordered=None)

        retriever = RerankingRetriever(wrapped, reranker)
        results = await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=5)

        assert results == candidates[:5]


class TestBypassWhenDisabled:
    """Covers scenario 10, Hallucination Risk 5: task 4.8."""

    async def test_disabled_flag_requests_top_k_and_never_calls_reranker(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", False)
        monkeypatch.setattr(settings, "rerank_candidate_count", 20)

        candidates = _make_results(5)
        wrapped = SpyRetriever(candidates)
        reranker = SpyReranker(reordered=candidates)

        retriever = RerankingRetriever(wrapped, reranker)
        results = await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=5)

        assert wrapped.calls[0]["top_k"] == 5
        assert reranker.calls == []
        assert results == candidates[:5]


class TestProtocolConformance:
    """Covers scenario 11: task 4.9."""

    async def test_reranking_retriever_satisfies_retriever_protocol(self, monkeypatch):
        monkeypatch.setattr(settings, "reranker_enabled", True)
        monkeypatch.setattr(settings, "rerank_candidate_count", 5)

        candidates = _make_results(5)
        wrapped = SpyRetriever(candidates)
        reranker = SpyReranker(reordered=candidates)
        retriever: Retriever = RerankingRetriever(wrapped, reranker)

        results = await retriever.retrieve("q", session=object(), schema="tenant_x", top_k=3)

        assert isinstance(results, list)
        assert all(isinstance(r, RetrievalResult) for r in results)
