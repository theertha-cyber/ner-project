## Why

Retrieval today is dense-vector-only: `DenseRetriever` does pgvector cosine search over an `ivfflat` index and nothing else. Two known gaps from the original RAG architecture review: (1) `ivfflat` requires tuning `lists` and trades recall for build speed — `HNSW` gives better recall at query time with no training step, and is the modern pgvector default recommendation; (2) purely semantic search misses exact-term matches (IDs, codes, precise names) that keyword/full-text search catches, which is why the roadmap called for combining dense vectors with PostgreSQL full-text search (BM25-style) rather than relying on embeddings alone. Both are foundational retrieval-quality improvements that should land before reranking or agentic retrieval, per the sequencing agreed in the RAG architecture exploration.

## What Changes

- Swap the `document_chunks.embedding` index from `ivfflat` to `hnsw` (`vector_cosine_ops`) in every tenant schema, via alembic migration following the established per-schema `DO $$` loop pattern.
- Add a `chunk_tsv tsvector` generated column (or trigger-maintained column) to `document_chunks` with a GIN index, populated from `chunk_text`, for PostgreSQL full-text search.
- Add a `SparseRetriever` implementing the `Retriever` protocol, performing `ts_rank`-scored full-text search (`plainto_tsquery`) over `chunk_tsv`.
- Add a `HybridRetriever` implementing the `Retriever` protocol, running `DenseRetriever` and `SparseRetriever` concurrently and fusing their ranked result lists via Reciprocal Rank Fusion (RRF).
- Extend the `Retriever` protocol's `retrieve` signature with an optional `metadata_filter` parameter (e.g., `document_id`, `page_number`) applied as a `WHERE` clause before ranking, so filtering happens at the database level, not after retrieval.
- Wire `RAGOrchestrator._vector_source` to use `HybridRetriever` (composing the existing `DenseRetriever` and the new `SparseRetriever`) instead of `DenseRetriever` alone.
- **BREAKING (internal only)**: `Retriever.retrieve`'s signature gains a new optional parameter; existing callers (`DenseRetriever` used directly, if any remain) are unaffected since the parameter is optional and defaults to no filter.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `retrieval-core`: "Retriever interface" requirement gains `SparseRetriever`, `HybridRetriever`, RRF fusion behavior, and optional metadata filtering; the underlying pgvector index changes from `ivfflat` to `hnsw`.
- `chat-api`: "pgvector semantic search" requirement becomes hybrid (dense + full-text) search — result composition and ranking behavior change, though the response shape (`document_id`, `chunk_text`, `similarity_score`) stays the same.

## Impact

- `src/shared/retrieval/retriever.py` — new `SparseRetriever`, `HybridRetriever`, `Retriever` protocol signature change
- `src/chat_api/services/rag_orchestrator.py` — `_vector_source` uses `HybridRetriever`
- New alembic migration `022_hybrid_retrieval_hnsw.py` — add `chunk_tsv tsvector` + GIN index, drop `ivfflat` index and create `hnsw` index, across `tenant_template` and every existing `tenant_%` schema
- No change to `document_chunks`' existing columns (`page_number`, `char_start`, `char_end` from `chunk-metadata-ingest` are untouched)
- No change to `/api/v1/chat` request/response contract

## Open Questions

- Confirm the running `pgvector/pgvector:pg16` image's pgvector extension version supports `hnsw` index type (added in pgvector 0.5.0) — check `SELECT extversion FROM pg_extension WHERE extname='vector'` before writing the migration; if the version predates 0.5.0, the migration must also bump the extension version.
- RRF fusion constant `k` (typically 60 in the literature) — confirm whether to make this configurable via `Settings` now or hardcode with a documented rationale, deferring configurability to a later change if no concrete need arises.
- Should `chunk_tsv` be a Postgres `GENERATED ALWAYS AS` computed column (simplest, always in sync, but requires Postgres 12+ which is satisfied by pg16) or a plain column maintained by application code at insert time (more control, more places that can drift out of sync)? Leaning generated column — confirm in design.
