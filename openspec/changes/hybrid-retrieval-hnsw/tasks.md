## 1. Database Migration

- [x] 1.1 Create `alembic/versions/024_hybrid_retrieval_hnsw.py` (renumbered from 022 — 022/023 already taken by later migrations): add `chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED` to `tenant_template.document_chunks`, plus a GIN index on it
- [x] 1.2 In the same migration, drop the existing `ivfflat` index (`idx_document_chunks_embedding`) on `tenant_template.document_chunks` and create an `hnsw` index (`vector_cosine_ops`) in its place
- [x] 1.3 Loop the same four operations (add `chunk_tsv` + GIN index, drop `ivfflat`, create `hnsw`) over every existing `tenant_%` schema, following migration 010's `DO $$` pattern
- [x] 1.4 Write `downgrade()`: drop `chunk_tsv`/GIN index, drop `hnsw` index, recreate the original `ivfflat` index (`lists=100`) — for `tenant_template` and every `tenant_%` schema
- [x] 1.5 Run the migration against a live Postgres instance (confirmed pgvector 0.8.5 supports `hnsw`); verify via `pg_indexes` that only the `hnsw` index remains on `embedding` and confirm `chunk_tsv` is populated for existing rows (covers Hallucination Risk 1)

## 2. SparseRetriever

- [x] 2.1 Add `SparseRetriever` to `src/shared/retrieval/retriever.py`: `retrieve` queries `document_chunks` via `plainto_tsquery('english', query)` against `chunk_tsv`, ranked by `ts_rank` descending, respecting `top_k` and optional `metadata_filter`
- [x] 2.2 Live pgvector test: seed a chunk containing an exact term, query for that term, assert it's returned and ranked by `ts_rank` (covers scenario 3)
- [x] 2.3 Live pgvector test: query with no lexical overlap to any seeded chunk, assert empty list, no exception (covers scenario 4)

## 3. Retriever Interface Extension & metadata_filter

- [x] 3.1 Extend the `Retriever` protocol signature in `src/shared/retrieval/retriever.py` to `retrieve(query, session, schema, top_k, metadata_filter=None)`
- [x] 3.2 Update `DenseRetriever.retrieve` to accept and apply `metadata_filter` (currently only `document_id` key supported) as a bound-parameter `WHERE` clause addition; confirm no other query behavior changes when `metadata_filter=None`
- [x] 3.3 Update `SparseRetriever.retrieve` to accept and apply the same `metadata_filter`
- [x] 3.4 Test: `DenseRetriever.retrieve` called with `metadata_filter=None` vs. no argument at all — assert identical results and SQL (covers Hallucination Risk 6)
- [x] 3.5 Live pgvector test: seed chunks from two documents both matching a query, call `retrieve` with `metadata_filter={"document_id": doc_a}`, assert only `doc_a`'s chunks are returned (covers scenario 7)
- [x] 3.6 Confirm `metadata_filter` values are passed as bound parameters, never string-interpolated into SQL text (covers Hallucination Risk 4)

## 4. HybridRetriever & RRF Fusion

- [x] 4.1 Add `HybridRetriever` to `src/shared/retrieval/retriever.py`, composing a `DenseRetriever` and `SparseRetriever` instance
- [x] 4.2 Implement RRF fusion: run both retrievers sequentially (deviation from `asyncio.gather` plan — see design.md, both share one `AsyncSession` which can't run concurrent statements) with a bounded per-source candidate count (e.g., `min(top_k * 3, 50)`), compute `1 / (k + rank)` per source per document (`k=60`), sum across sources, sort descending, truncate to `top_k`
- [x] 4.3 Live pgvector test: seed a chunk matching both semantically and lexically, assert it ranks at/near the top of the fused result and the fused list has at most `top_k` entries (covers scenario 5)
- [x] 4.4 Live pgvector test: seed a chunk with semantic-only overlap (sparse returns zero matches, dense returns it), assert `HybridRetriever` still includes it (covers scenario 6)
- [x] 4.5 Test: assert the per-source candidate count requested by `HybridRetriever` does not exceed the fixed cap regardless of `top_k` (covers scenario 10)
- [x] 4.6 Manually verify the RRF formula in the diff matches `1 / (k + rank)` exactly, summed correctly across sources (covers Hallucination Risk 2)

## 5. Wire RAGOrchestrator

- [x] 5.1 Update `RAGOrchestrator.__init__` to construct `self.retriever` as a `HybridRetriever` (composed from `DenseRetriever(self.embedding_service)` and a new `SparseRetriever`) instead of `DenseRetriever` alone
- [x] 5.2 Confirm `_vector_source`'s code is unchanged beyond the retriever instance held (covers scenario 2)
- [x] 5.3 Live/integration test: simulate a chat query containing an exact identifier present in a seeded chunk with low semantic similarity, assert the response cites that chunk (covers scenario 15)
- [x] 5.4 Re-run existing hybrid-independent regression tests: `Semantic search returns relevant chunks`, `Semantic search with empty corpus`, citation page-number scenarios from `chunk-metadata-ingest` (covers scenarios 11, 12, 13, 14)

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 6.6 Run `openspec validate hybrid-retrieval-hnsw --type change --strict` and confirm it exits clean before archive.
