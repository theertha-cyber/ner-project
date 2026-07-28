import pytest
import httpx

from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.reranker import CrossEncoderReranker

pytestmark = [pytest.mark.asyncio]


def _make_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(document_id="doc-a", chunk_index=0, chunk_text="irrelevant chunk", similarity_score=0.9),
        RetrievalResult(document_id="doc-b", chunk_index=1, chunk_text="another irrelevant chunk", similarity_score=0.8),
        RetrievalResult(document_id="doc-c", chunk_index=2, chunk_text="the actually relevant chunk", similarity_score=0.5),
    ]


class TestCrossEncoderReordersResults:
    """Covers scenario 6: task 3.5."""

    async def test_rerank_reorders_and_preserves_fields(self, monkeypatch):
        results = _make_results()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": 2, "score": 0.95}, {"index": 0, "score": 0.3}, {"index": 1, "score": 0.1}]}

        class FakeAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, headers=None, json=None):
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        reranker = CrossEncoderReranker()
        reranked = await reranker.rerank("query", results, top_k=3)

        assert reranked is not None
        assert [r.chunk_index for r in reranked] == [2, 0, 1]
        assert reranked[0].document_id == "doc-c"
        assert reranked[0].chunk_text == "the actually relevant chunk"

    async def test_rerank_overwrites_similarity_score_with_reranker_score(self, monkeypatch):
        """similarity_score must reflect the cross-encoder's own score, not the
        pre-rerank retriever's score — otherwise the UI shows a stale/wrong number."""
        results = _make_results()

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"results": [{"index": 2, "score": 0.95}, {"index": 0, "score": 0.3}, {"index": 1, "score": 0.1}]}

        class FakeAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, headers=None, json=None):
                return FakeResponse()

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        reranker = CrossEncoderReranker()
        reranked = await reranker.rerank("query", results, top_k=3)

        assert [r.similarity_score for r in reranked] == [0.95, 0.3, 0.1]


class TestCrossEncoderReturnsNoneOnFailure:
    """Covers scenario 7, Hallucination Risk 2: task 3.6."""

    async def test_rerank_returns_none_on_unreachable_endpoint(self, monkeypatch):
        results = _make_results()

        class FakeAsyncClient:
            def __init__(self, *a, **kw):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, headers=None, json=None):
                raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

        reranker = CrossEncoderReranker()
        reranked = await reranker.rerank("query", results, top_k=3)

        assert reranked is None
