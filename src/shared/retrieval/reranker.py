import logging
from typing import Protocol
import time

import httpx
from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


def _metrics():
    """The domain-metric recorders, resolved on first use rather than imported at the top.

    `domain_metrics` imports the chat service modules' own constants so a rename there is
    an ImportError rather than a stale label (design Decision 2). `src/shared/retrieval/`
    must not pull `src.chat_api` into its import graph — `test_retrieval_tools.py` asserts
    that in a subprocess, because the retrieval tools are shared by services that do not
    ship chat_api at all. A function-local import keeps the recorders reachable without
    putting chat_api on this module's import path; `sys.modules` makes every call after
    the first a dict lookup.
    """
    from src.shared.observability import domain_metrics

    return domain_metrics


class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int | None = None,
        jwt_token: str | None = None,
    ) -> list[RetrievalResult] | None: ...


class CrossEncoderReranker:
    def __init__(self):
        self.base_url = settings.model_serving_url.rstrip("/")

    async def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int | None = None,
        jwt_token: str | None = None,
    ) -> list[RetrievalResult] | None:
        if not results:
            return []

        headers = {}
        if jwt_token:
            headers["Authorization"] = f"Bearer {jwt_token}"

        documents = [r.chunk_text for r in results]
        started = time.perf_counter()

        async with httpx.AsyncClient(timeout=settings.rerank_timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/internal/v1/rerank",
                    headers=headers,
                    json={"query": query, "documents": documents, "top_k": top_k},
                )
                response.raise_for_status()
                data = response.json()
                # Measured around the provider call only. The reranker is a network hop
                # to model_serving, so its latency is a different fact from the retrieval
                # that produced the candidates, and folding them together is what makes a
                # slow answer undiagnosable today.
                _metrics().record_rerank_duration(time.perf_counter() - started)
                return [
                    results[r["index"]].model_copy(update={"similarity_score": r["score"]})
                    for r in data["results"]
                ]
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                # The exception type carries the diagnosis when the message does not:
                # httpx timeouts stringify to "", which made every cold-start fallback
                # log as a bare "Reranking request failed: " with nothing to act on.
                logger.warning(
                    "Reranking request failed (%s after %.1fs timeout budget): %s",
                    type(e).__name__, settings.rerank_timeout_seconds, str(e) or "<no detail>",
                )
                return None
