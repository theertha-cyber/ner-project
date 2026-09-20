import logging
from typing import Protocol
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.config import settings
from src.shared.document_visibility import (
    RequestingUser,
    visibility_clause,
)
from src.shared.retrieval.config import (
    RetrievalConfig,
    resolve_rerank_candidate_count,
    resolve_reranker_enabled,
    resolve_top_k,
)
from src.shared.retrieval.models import RetrievalResult
from src.shared.retrieval.reranker import Reranker

logger = logging.getLogger(__name__)


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
        conversation_id: str | None = None,
        requesting_user: RequestingUser | None = None,
    ) -> list[RetrievalResult]: ...


def _conversation_clause(conversation_id: str | None) -> tuple[str, dict]:
    """The conversation-visibility guardrail (ADR-014).

    A chunk is admitted when it belongs to no conversation — tenant-library content,
    visible from everywhere, which is also what every row predating migration 054 is —
    or when it belongs to the conversation this retrieval is being performed for.

    Deliberately not part of `_metadata_filter_clause`: `metadata_filter` is derived
    from the `scope` argument the model chooses, and a boundary the model can omit is
    not a boundary. This clause is built unconditionally from the caller's
    authenticated request context and can only narrow, never widen, exactly like the
    `purpose = 'query'` restriction it sits beside.
    """
    if conversation_id is None:
        return " AND conversation_id IS NULL", {}
    return (
        " AND (conversation_id IS NULL OR conversation_id = :conversation_id)",
        {"conversation_id": conversation_id},
    )


# The uploader-visibility guardrail sits beside the conversation one and is built the
# same way: `visibility_clause` in `src/shared/document_visibility.py`, from the
# caller's authenticated request context, never from `metadata_filter`. It is imported
# rather than written here because document listing applies the identical rule, and the
# defect this change fixes was two implementations of one rule drifting apart.
#
# It reads the chunk row's own denormalized `ingested_by_kind` / `uploaded_by` (migration
# 056), for the reason ADR-014 gives for `conversation_id`: a join to `documents` would
# sit between the hnsw index scan and the vector ranking.


def _metadata_filter_clause(metadata_filter: dict | None) -> tuple[str, dict]:
    """Supports `document_id` (single id, kept for backward compatibility) and
    `document_ids` (a list, used by the `document` retrieval scope). Returns a
    bound-parameter SQL fragment (or empty string) and its params — never
    string-interpolates the value(s)."""
    if not metadata_filter:
        return "", {}
    if "document_ids" in metadata_filter:
        return " AND document_id = ANY(:mf_document_ids)", {"mf_document_ids": list(metadata_filter["document_ids"])}
    if "document_id" in metadata_filter:
        return " AND document_id = :mf_document_id", {"mf_document_id": metadata_filter["document_id"]}
    return "", {}


def _hidden_documents_clause(schema: str) -> str:
    """Exclude chunks of superseded or confirmed-missing sync source documents.

    The predicate is unconditional and caller-invisible, like the purpose
    restriction. It plans against the CAP-3 hidden table, which migration 041
    creates in every tenant schema: a schema without it is a broken deploy,
    and the query fails closed rather than serving hidden content. The schema
    name is server-derived tenant context, same as the table reference it
    guards — never caller input.
    """
    return (
        f" AND NOT EXISTS (SELECT 1 FROM {schema}.azure_blob_hidden_documents h"
        f" WHERE h.document_id = document_chunks.document_id)"
    )


class DenseRetriever:
    def __init__(self, embedding_service=None, config: RetrievalConfig | None = None):
        if embedding_service is None:
            from src.chat_api.services.embedding_service import EmbeddingService
            embedding_service = EmbeddingService()
        self.embedding_service = embedding_service
        self.config = config

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
        conversation_id: str | None = None,
        requesting_user: RequestingUser | None = None,
    ) -> list[RetrievalResult]:
        top_k = resolve_top_k(top_k, self.config, settings)
        filter_clause, filter_params = _metadata_filter_clause(metadata_filter)
        hidden_clause = _hidden_documents_clause(schema)
        conv_clause, conv_params = _conversation_clause(conversation_id)
        vis_clause, vis_params = visibility_clause(requesting_user)

        query_embedding = await self.embedding_service.embed(query)
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        result = await session.execute(
            text(f"""
                SELECT id, document_id, chunk_index, chunk_text, page_number, char_start, char_end,
                        1 - (embedding <=> :query_emb) AS similarity_score
                FROM {schema}.document_chunks
                WHERE embedding IS NOT NULL AND purpose = 'query'{conv_clause}{vis_clause}{filter_clause}{hidden_clause}
                ORDER BY embedding <=> :query_emb
                LIMIT :top_k
            """),
            {
                "query_emb": embedding_str, "top_k": top_k,
                **conv_params, **vis_params, **filter_params,
            },
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
    def __init__(self, config: RetrievalConfig | None = None):
        self.config = config

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
        conversation_id: str | None = None,
        requesting_user: RequestingUser | None = None,
    ) -> list[RetrievalResult]:
        top_k = resolve_top_k(top_k, self.config, settings)
        filter_clause, filter_params = _metadata_filter_clause(metadata_filter)
        hidden_clause = _hidden_documents_clause(schema)
        conv_clause, conv_params = _conversation_clause(conversation_id)
        vis_clause, vis_params = visibility_clause(requesting_user)

        result = await session.execute(
            text(f"""
                SELECT id, document_id, chunk_index, chunk_text, page_number, char_start, char_end,
                        ts_rank(chunk_tsv, plainto_tsquery('english', :query)) AS rank_score
                FROM {schema}.document_chunks
                WHERE chunk_tsv @@ plainto_tsquery('english', :query) AND purpose = 'query'{conv_clause}{vis_clause}{filter_clause}{hidden_clause}
                ORDER BY rank_score DESC
                LIMIT :top_k
            """),
            {
                "query": query, "top_k": top_k,
                **conv_params, **vis_params, **filter_params,
            },
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

    def __init__(
        self,
        dense_retriever: DenseRetriever | None = None,
        sparse_retriever: SparseRetriever | None = None,
        config: RetrievalConfig | None = None,
    ):
        self.dense = dense_retriever if dense_retriever is not None else DenseRetriever()
        self.sparse = sparse_retriever if sparse_retriever is not None else SparseRetriever()
        self.config = config

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
        conversation_id: str | None = None,
        requesting_user: RequestingUser | None = None,
    ) -> list[RetrievalResult]:
        top_k = resolve_top_k(top_k, self.config, settings)
        candidate_k = min(top_k * self.CANDIDATE_MULTIPLIER, self.CANDIDATE_CAP)

        # Sequential, not asyncio.gather: both retrievers share the same AsyncSession,
        # and SQLAlchemy's AsyncSession cannot run two statements concurrently on one
        # connection (IllegalStateChangeError) — gather here would be a correctness bug.
        dense_results = await self.dense.retrieve(
            query, session, schema, top_k=candidate_k,
            metadata_filter=metadata_filter, conversation_id=conversation_id,
            requesting_user=requesting_user,
        )
        sparse_results = await self.sparse.retrieve(
            query, session, schema, top_k=candidate_k,
            metadata_filter=metadata_filter, conversation_id=conversation_id,
            requesting_user=requesting_user,
        )

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


class RerankingRetriever:
    """Wraps a Retriever with a Reranker (decorator pattern). Implements the Retriever
    protocol itself so callers need no change beyond which instance they hold."""

    def __init__(self, retriever: "Retriever", reranker: Reranker, config: RetrievalConfig | None = None):
        self.retriever = retriever
        self.reranker = reranker
        self.config = config

    async def retrieve(
        self,
        query: str,
        session: AsyncSession,
        schema: str,
        top_k: int | None = None,
        metadata_filter: dict | None = None,
        conversation_id: str | None = None,
        requesting_user: RequestingUser | None = None,
        jwt_token: str | None = None,
        degraded_sink: list | None = None,
    ) -> list[RetrievalResult]:
        """`degraded_sink`, when provided, receives `True` appended to it if the
        reranker was attempted but failed and the call fell back to unreranked
        candidates. Callers that don't need to observe degradation (e.g. the chat
        graph today) pass nothing and behaviour is unchanged."""
        top_k = resolve_top_k(top_k, self.config, settings)

        if not resolve_reranker_enabled(self.config, settings):
            return await self.retriever.retrieve(
                query, session, schema, top_k=top_k,
                metadata_filter=metadata_filter, conversation_id=conversation_id,
            requesting_user=requesting_user,
            )

        candidate_count = resolve_rerank_candidate_count(self.config, settings)
        candidates = await self.retriever.retrieve(
            query, session, schema, top_k=candidate_count,
            metadata_filter=metadata_filter, conversation_id=conversation_id,
            requesting_user=requesting_user,
        )
        reranked = await self.reranker.rerank(query, candidates, top_k=top_k, jwt_token=jwt_token)
        if reranked is None:
            logger.warning(
                "Reranker fallback: reranking failed or unavailable, returning unranked candidates truncated to top_k=%d",
                top_k,
            )
            if degraded_sink is not None:
                degraded_sink.append(True)
            return candidates[:top_k]
        return reranked[:top_k]
