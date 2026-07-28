import logging
from typing import Protocol
import httpx
from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult

logger = logging.getLogger(__name__)


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

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/internal/v1/rerank",
                    headers=headers,
                    json={"query": query, "documents": documents, "top_k": top_k},
                )
                response.raise_for_status()
                data = response.json()
                return [
                    results[r["index"]].model_copy(update={"similarity_score": r["score"]})
                    for r in data["results"]
                ]
            except (httpx.RequestError, httpx.HTTPStatusError) as e:
                logger.warning("Reranking request failed: %s", str(e))
                return None
