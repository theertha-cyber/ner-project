import json
from pathlib import Path


class EmbeddingModelMismatchError(Exception):
    pass


class PrecomputedEmbeddingService:
    """Fixture embedding service used by the eval harness. Serves committed vectors
    from `embeddings.json` for known queries and corpus chunks — makes eval runs
    deterministic and offline by construction. Refuses to serve embeddings recorded
    under a different model name than the one configured for the run."""

    def __init__(self, embeddings_path: str | Path, expected_model: str):
        with open(embeddings_path, encoding="utf-8") as f:
            data = json.load(f)

        recorded_model = data.get("embedding_model")
        if recorded_model != expected_model:
            raise EmbeddingModelMismatchError(
                f"embeddings.json was recorded against model '{recorded_model}' but this run "
                f"is configured for model '{expected_model}' — regenerate embeddings.json before "
                "running against a different embedding model."
            )

        self._queries: dict[str, list[float]] = data["queries"]
        self._chunks: dict[str, list[float]] = data["chunks"]

    async def embed(self, query: str) -> list[float]:
        raise NotImplementedError("PrecomputedEmbeddingService serves by query_id, not raw text")

    def embed_query_by_id(self, query_id: str) -> list[float]:
        if query_id not in self._queries:
            raise KeyError(f"no precomputed embedding for query_id '{query_id}'")
        return self._queries[query_id]

    def chunk_embedding(self, document_id: str, chunk_index: int) -> list[float]:
        key = f"{document_id}::{chunk_index}"
        if key not in self._chunks:
            raise KeyError(f"no precomputed embedding for chunk '{key}'")
        return self._chunks[key]


class QueryIdEmbeddingService:
    """Adapts PrecomputedEmbeddingService to the `EmbeddingService.embed(query)`
    interface DenseRetriever expects, by resolving the current query text back to
    its golden-set query_id via a caller-supplied mapping."""

    def __init__(self, provider: PrecomputedEmbeddingService, query_text_to_id: dict[str, str]):
        self._provider = provider
        self._query_text_to_id = query_text_to_id

    async def embed(self, query: str) -> list[float]:
        query_id = self._query_text_to_id.get(query)
        if query_id is None:
            raise KeyError(f"no golden-set query_id mapped for query text: '{query}'")
        return self._provider.embed_query_by_id(query_id)
