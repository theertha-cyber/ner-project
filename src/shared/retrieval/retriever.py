from typing import Protocol
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.shared.retrieval.models import RetrievalResult


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[RetrievalResult]: ...


def _metadata_filter_clause(metadata_filter: dict | None) -> tuple[str, dict]:
    """Only `document_id` is a supported filter key today. Returns a bound-parameter
    SQL fragment (or empty string) and its params — never string-interpolates the value."""
    if metadata_filter and "document_id" in metadata_filter:
        return " AND document_id = :mf_document_id", {"mf_document_id": metadata_filter["document_id"]}
    return "", {}


class DenseRetriever:
    def __init__(self, embedding_service=None):
        if embedding_service is None:
            from src.chat_api.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
        self.embedding_service = embedding_service

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[RetrievalResult]:
        top_k = top_k if top_k is not None else settings.retrieval_top_k
        filter_clause, filter_params = _metadata_filter_clause(metadata_filter)

        query_embedding = await self.embedding_service.embed(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await session.execute(
            text(f"""
                SELECT id, document_id, chunk_index, chunk_text, page_number, char_start, char_end,
                       1 - (embedding <=> :query_emb) AS similarity_score
                FROM {schema}.document_chunks
                WHERE embedding IS NOT NULL AND purpose = 'query'{filter_clause}
                ORDER BY embedding <=> :query_emb
                LIMIT :top_k
            """),
            {"query_emb": embedding_str, "top_k": top_k, **filter_params},
        )
        rows = result.fetchall()
        return [
            RetrievalResult(
                document_id=r.document_id,
                chunk_index=r.chunk_index,
                chunk_text=r.chunk_text,
                similarity_score=float(r.similarity_score),
                page_number=r.page_number,
                char_start=r.char_start,
                char_end=r.char_end,
            )
            for r in rows
        ]


class SparseRetriever:
    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[RetrievalResult]:
        top_k = top_k if top_k is not None else settings.retrieval_top_k
        filter_clause, filter_params = _metadata_filter_clause(metadata_filter)

        result = await session.execute(
            text(f"""
                SELECT id, document_id, chunk_index, chunk_text, page_number, char_start, char_end,
                       ts_rank(chunk_tsv, plainto_tsquery('english', :query)) AS rank_score
                FROM {schema}.document_chunks
                WHERE chunk_tsv @@ plainto_tsquery('english', :query) AND purpose = 'query'{filter_clause}
                ORDER BY rank_score DESC
                LIMIT :top_k
            """),
            {"query": query, "top_k": top_k, **filter_params},
        )
        rows = result.fetchall()
        return [
            RetrievalResult(
                document_id=r.document_id,
                chunk_index=r.chunk_index,
                chunk_text=r.chunk_text,
                similarity_score=float(r.rank_score),
                page_number=r.page_number,
                char_start=r.char_start,
                char_end=r.char_end,
            )
            for r in rows
        ]


class HybridRetriever:
    """Fuses DenseRetriever and SparseRetriever rankings via Reciprocal Rank Fusion."""

    RRF_K = 60
    CANDIDATE_MULTIPLIER = 3
    CANDIDATE_CAP = 50

    def __init__(self, dense_retriever: DenseRetriever | None = None, sparse_retriever: SparseRetriever | None = None):
        self.dense = dense_retriever if dense_retriever is not None else DenseRetriever()
        self.sparse = sparse_retriever if sparse_retriever is not None else SparseRetriever()

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
    ) -> list[RetrievalResult]:
        top_k = top_k if top_k is not None else settings.retrieval_top_k
        candidate_k = min(top_k * self.CANDIDATE_MULTIPLIER, self.CANDIDATE_CAP)

        # Sequential, not asyncio.gather: both retrievers share the same AsyncSession,
        # and SQLAlchemy's AsyncSession cannot run two statements concurrently on one
        # connection (IllegalStateChangeError) — gather here would be a correctness bug.
        dense_results = await self.dense.retrieve(query, session, schema, top_k=candidate_k, metadata_filter=metadata_filter)
        sparse_results = await self.sparse.retrieve(query, session, schema, top_k=candidate_k, metadata_filter=metadata_filter)

        rrf_scores: dict[tuple[str, int], float] = {}
        chunks_by_key: dict[tuple[str, int], RetrievalResult] = {}
        for ranked_list in (dense_results, sparse_results):
            for rank, r in enumerate(ranked_list, start=1):
                key = (r.document_id, r.chunk_index)
                rrf_scores[key] = rrf_scores.get(key, 0.0) + 1.0 / (self.RRF_K + rank)
                chunks_by_key.setdefault(key, r)

        ranked_keys = sorted(rrf_scores, key=lambda k: rrf_scores[k], reverse=True)[:top_k]
        return [
            chunks_by_key[key].model_copy(update={"similarity_score": rrf_scores[key]})
            for key in ranked_keys
        ]
