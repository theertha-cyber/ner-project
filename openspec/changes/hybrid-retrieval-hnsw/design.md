## Context

`document_chunks` currently has one index: `idx_document_chunks_embedding` (`ivfflat`, `vector_cosine_ops`, `lists=100`), created per-schema by migration 010. `DenseRetriever.retrieve` (in `src/shared/retrieval/retriever.py`) runs a single cosine-distance query and returns `RetrievalResult` objects; `RAGOrchestrator._vector_source` calls it directly. There is no full-text search capability anywhere in `document_chunks`. The running Postgres instance uses `pgvector/pgvector:pg16` with extension version `0.8.5` (confirmed live via `SELECT extversion FROM pg_extension WHERE extname='vector'`), which supports `hnsw` indexes (added in pgvector 0.5.0) — the proposal's open question about version support is resolved, no extension upgrade needed.

`retrieval-foundation` (archived) established `Retriever` as a `typing.Protocol` specifically so additional implementations (`SparseRetriever`, `HybridRetriever`) could be added without touching `RAGOrchestrator`'s call sites beyond swapping which retriever instance it holds. `chunk-metadata-ingest` (archived) added `page_number`/`char_start`/`char_end` to `document_chunks` and `RetrievalResult` — this change adds `chunk_tsv` alongside those, untouched.

## Goals / Non-Goals

**Goals:**

- Replace the `ivfflat` index with `hnsw` for better recall with no `lists`-tuning step.
- Add PostgreSQL full-text search (BM25-style ranking via `ts_rank`) over `chunk_text`.
- Fuse dense and sparse rankings via Reciprocal Rank Fusion (RRF) into one ranked result list.
- Support optional metadata filtering (e.g., restrict to one `document_id`) applied as a `WHERE` clause before ranking, at the database level.
- `RAGOrchestrator` uses the fused hybrid retriever by default, with no change to its own code beyond which `Retriever` it holds.

**Non-Goals:**

- No cross-encoder reranking (a later change, `cross-encoder-rerank`).
- No context-assembly changes (a later change, `context-assembly-pipeline`).
- No query rewriting or multi-query retrieval.
- No change to `chunk-metadata-ingest`'s page/location columns — this change only adds `chunk_tsv` and swaps the vector index.
- No configurable RRF constant in this change (see Decisions) — hardcoded with documented rationale; configurability is trivial to add later if a concrete need arises, and inventing a config surface with no current consumer is premature.

## Decisions

**Index swap: `ivfflat` → `hnsw`, same `vector_cosine_ops`, no other retrieval-behavior change.**
`hnsw` requires no `lists` parameter and no pre-population training step (unlike `ivfflat`, which degrades on empty/small tables until enough vectors exist to compute good centroids) — better fit for a per-tenant schema where some tenants may have very few chunks. Migration drops the existing `ivfflat` index and creates `hnsw` in place, per schema, following migration 010's `DO $$ ... FOR schema_name IN ...` loop precedent.
Alternative considered: keep `ivfflat` and just tune `lists` per tenant size — rejected, adds operational complexity (per-tenant tuning) for a problem `hnsw` solves structurally.

**`chunk_tsv` as a Postgres `GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED` column, not application-maintained.**
Resolves the proposal's open question. A generated column is always in sync with `chunk_text` by construction — there is no code path that can insert a chunk with a stale or missing `chunk_tsv`, which an application-maintained column would risk (e.g., a future direct SQL `UPDATE chunk_text` that forgets to also update `chunk_tsv`). Postgres 12+ supports generated columns; the running pg16 satisfies this.
Alternative considered: maintain `chunk_tsv` in application code (`_store_chunks`) — rejected, adds a synchronization responsibility to every future ingestion code path for no benefit over a generated column.

**`SparseRetriever` uses `plainto_tsquery('english', query)` against `chunk_tsv`, ranked by `ts_rank`.**
`plainto_tsquery` (not `websearch_to_tsquery` or `to_tsquery`) is chosen for simplicity and safety with arbitrary user input — it doesn't support operators a user could misuse, and doesn't require query-syntax validation the way `to_tsquery` would. `websearch_to_tsquery` (which supports quoted phrases and `-exclusion`) is a reasonable future upgrade if users want that, but isn't needed for this change's scope.

**`HybridRetriever` runs `DenseRetriever` and `SparseRetriever` sequentially (not `asyncio.gather`) and fuses with Reciprocal Rank Fusion.**
Deviation from the original plan: both retrievers are called with the same `AsyncSession` argument, and a single `AsyncSession` cannot run two statements concurrently (SQLAlchemy raises `IllegalStateChangeError` — confirmed via a failing live test during implementation). `RAGOrchestrator.execute`'s existing `asyncio.gather(sql_task, vector_task)` has the same latent issue but is out of scope here. Sequential awaits are used instead; each query is fast (single indexed lookup), so the latency cost is small and correctness takes priority.
RRF score for a result at rank `r` in a ranked list: `1 / (k + r)`, summed across the lists it appears in (`k=60`, the standard literature default — hardcoded with this comment, not configurable in this change per Non-Goals). RRF is chosen over score-normalization-based fusion (e.g., min-max normalizing cosine similarity and `ts_rank` then averaging) because the two scores are on incomparable scales (`ts_rank` is unbounded and corpus-dependent, cosine similarity is bounded but not calibrated to the same meaning) — RRF only needs rank order from each source, sidestepping the scale-mismatch problem entirely. This is the standard, well-established approach for combining dense and sparse retrieval (used by Elasticsearch, Azure AI Search, and most published hybrid-RAG references).
Each retriever is queried independently with a wider `top_k` (e.g., `top_k * 3`, capped) than the final fused result count, so RRF has enough candidates from each source to fuse meaningfully before truncating to the requested `top_k`.

**`Retriever.retrieve` signature gains `metadata_filter: dict | None = None`.**
Only `document_id` is supported as a filter key in this change (the only metadata column with an obvious, unambiguous filtering use case today); the parameter is a dict (not a single `document_id: str | None` kwarg) so later changes (e.g., filtering by `page_number` range) can extend it without another signature change. `DenseRetriever` and `SparseRetriever` both translate `metadata_filter` into an additional `WHERE` clause; `HybridRetriever` passes it through unchanged to both.

**`RAGOrchestrator` holds a `HybridRetriever` instead of a `DenseRetriever`; `HybridRetriever` is constructed from a `DenseRetriever` instance (reusing the existing `embedding_service`) plus a new `SparseRetriever` instance.**
No change to `_vector_source`'s code beyond which retriever instance `self.retriever` is — the `Retriever` protocol interface is unchanged in shape (`retrieve(query, session, schema, top_k)`), only its default implementation is now the fused one, and `metadata_filter` is added as an optional keyword nobody is required to pass yet.

## Risks / Trade-offs

- **[Risk] `HNSW` index build/query behavior differs from `ivfflat` in ways not caught by existing tests (e.g., different default `ef_search`, different recall/latency trade-off)** → Mitigation: reuse `retrieval-foundation`'s parity-test pattern — seed known chunks, compare top-K result sets before/after the index swap on the same data, confirm the same (or a superset with correct ranking) top matches are returned.
- **[Risk] RRF fusion combining two independently-ranked lists could regress relevance for queries that were previously well-served by dense-only search (e.g., a paraphrased question with no exact keyword overlap)** → Mitigation: test with a query that has strong semantic-but-not-lexical overlap with a seeded chunk, confirm it's still retrieved as a top result after fusion (dense contributes its RRF share even with zero sparse matches).
- **[Risk] `plainto_tsquery` against a query with no recognized English stop-words/stems could return zero sparse matches for some queries (e.g., queries in another language, or pure numeric/ID lookups)** → Mitigation: `HybridRetriever` must not fail or return empty when one side returns zero results — dense-only results still flow through RRF; explicit test for a query yielding zero sparse matches.
- **[Risk] Generated column migration (`GENERATED ALWAYS AS ... STORED`) requires a full table rewrite on existing tenant schemas with data — could be slow/locking on large tenants** → Mitigation: acceptable for this system's current scale (documented assumption); if any tenant's `document_chunks` grows large enough for this to matter, that's a future migration-strategy change, not blocking this one.
- **[Risk] Wider per-source `top_k` (e.g., `top_k * 3`) for fusion candidates increases per-query cost on both dense and sparse sides** → Mitigation: cap the multiplier and the absolute candidate count (e.g., `min(top_k * 3, 50)`) so cost doesn't scale unboundedly with `top_k`.

## Migration Plan

1. New alembic migration `022_hybrid_retrieval_hnsw.py`:
   - `ALTER TABLE tenant_template.document_chunks ADD COLUMN IF NOT EXISTS chunk_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED;`
   - `CREATE INDEX IF NOT EXISTS idx_document_chunks_tsv ON tenant_template.document_chunks USING GIN (chunk_tsv);`
   - `DROP INDEX IF EXISTS tenant_template.idx_document_chunks_embedding;`
   - `CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw ON tenant_template.document_chunks USING hnsw (embedding vector_cosine_ops);`
   - Loop the same four statements over every existing `tenant_%` schema (migration 010's `DO $$` pattern).
2. Code changes (`SparseRetriever`, `HybridRetriever`, `Retriever` signature, `RAGOrchestrator` wiring) ship in the same change — both are needed together for the feature to do anything.
3. Rollback: downgrade drops `chunk_tsv`/GIN index, drops the `hnsw` index, recreates the `ivfflat` index (matching migration 010's index definition exactly) — full round-trip back to the pre-change state.
4. No backfill needed beyond the generated column itself, which Postgres populates automatically for existing rows as part of `ADD COLUMN ... GENERATED ALWAYS AS ... STORED`.

## Open Questions

- None of the in-force ADRs need revisiting — ADR-007 specifies pgvector for document search and doesn't prescribe `ivfflat` vs `hnsw` or dense-only vs hybrid; this change is consistent with it.
- Confirmed: pgvector 0.8.5 (live check) supports `hnsw` — no extension upgrade needed.
- Confirmed: RRF `k=60` hardcoded per Non-Goals, not made configurable in this change.
