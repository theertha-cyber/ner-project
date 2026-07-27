# Verification Plan

**Change:** hybrid-retrieval-hnsw
**Generated:** 2026-07-24
**Status:** 🟡 Evidence Log populated by agent — Audit Record sign-off still required from a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | retrieval-core | Retriever interface | DenseRetriever uses the hnsw index | Given a tenant schema with chunks/embeddings and a fixed query, when `DenseRetriever.retrieve` is called, then the query executes against the `hnsw` index and results rank in descending similarity | migration check: task 1.5 | - [ ] |
| 2 | retrieval-core | Retriever interface | rag_orchestrator retrieves via the Retriever interface | Given the orchestrator needs document context, when `_vector_source` executes, then it calls a `Retriever.retrieve` implementation | code review: task 5.2 | - [ ] |
| 3 | retrieval-core | Retriever interface | SparseRetriever returns full-text matches | Given chunks whose `chunk_text` contains an exact term, when `SparseRetriever.retrieve` is called with that term, then the result includes the matching chunk, ranked by `ts_rank` descending | live pgvector test: task 2.2 | - [ ] |
| 4 | retrieval-core | Retriever interface | SparseRetriever returns no error on zero matches | Given chunks with no text overlap with the query, when `SparseRetriever.retrieve` is called, then the result is an empty list and no exception is raised | live pgvector test: task 2.3 | - [ ] |
| 5 | retrieval-core | Retriever interface | HybridRetriever fuses dense and sparse results via RRF | Given a chunk matching both semantically and lexically, when `HybridRetriever.retrieve` is called, then that chunk ranks at/near the top of the fused list, capped at `top_k` | live pgvector test: task 4.3 | - [ ] |
| 6 | retrieval-core | Retriever interface | HybridRetriever includes dense-only matches when sparse search returns nothing | Given a query with semantic-only overlap to a chunk (sparse returns zero, dense returns the chunk), when `HybridRetriever.retrieve` is called, then the fused list still includes that chunk | live pgvector test: task 4.4 | - [ ] |
| 7 | retrieval-core | Retriever interface | metadata_filter restricts results to one document | Given chunks from two documents both matching the query, when `retrieve` is called with `metadata_filter={"document_id": X}`, then every result has `document_id == X` | live pgvector test: task 3.5 | - [ ] |
| 8 | retrieval-core | Centralized retrieval configuration | Default configuration matches prior hardcoded behavior | Given no retrieval-specific env vars set, when configuration loads, then chunk size=512, overlap=128, top_k=5, embedding model=`text-embedding-3-small` | regression (retrieval-foundation): task 6.1 | - [ ] |
| 9 | retrieval-core | Centralized retrieval configuration | Configuration is overridable via environment variable | Given `NER_RETRIEVAL_TOP_K=8`, when configuration loads, then `DenseRetriever` defaults to `top_k=8` | regression (retrieval-foundation): task 6.1 | - [ ] |
| 10 | retrieval-core | Centralized retrieval configuration | HybridRetriever's per-source candidate count is bounded | Given `retrieval_top_k=20`, when `HybridRetriever.retrieve` queries both sources for fusion candidates, then the per-source candidate count does not exceed a fixed cap (e.g., 50) | unit test: task 4.5 | - [ ] |
| 11 | chat-api | pgvector semantic search | Semantic search returns relevant chunks | Given document chunks with embeddings for a tenant, when the RAG pipeline performs hybrid search, then the result contains the top-K fused-ranked chunks with `document_id`, `chunk_text`, `similarity_score` | regression: task 5.4 | - [ ] |
| 12 | chat-api | pgvector semantic search | Semantic search with empty corpus | Given a tenant with no document chunks, when hybrid search runs, then the pipeline skips the document-context source and the response has no document chunk sources | regression: task 5.4 | - [ ] |
| 13 | chat-api | pgvector semantic search | Citation includes page number when the chunk has one | Given a retrieved chunk with `page_number=3`, when `_enrich_citations` builds its citation, then `Citation.page_number == 3` | regression: task 5.4 | - [ ] |
| 14 | chat-api | pgvector semantic search | Citation page number is null for chunks without metadata | Given a retrieved chunk with no `page_number`, when `_enrich_citations` builds its citation, then `Citation.page_number` is `None` and no exception is raised | regression: task 5.4 | - [ ] |
| 15 | chat-api | pgvector semantic search | Chat retrieves relevant document context for a lexical (exact-term) query | Given a document chunk containing a specific identifier, when a user asks a question containing that exact term, then the response cites that chunk even with low semantic similarity | integration test: task 5.3 | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | HNSW index migration | AI may write the index-swap migration without `DROP INDEX IF EXISTS` for the old `ivfflat` index first, or get the `DO $$` loop pattern subtly wrong (missing `tenant_template`, wrong `LIKE` pattern), leaving some schemas on the old index or with duplicate indexes | Diff migration against migration 010's loop precedent line-by-line; query `pg_indexes` on a few tenant schemas post-migration to confirm only the `hnsw` index exists on `embedding` |
| 2 | RRF fusion implementation | AI may implement RRF incorrectly (e.g., sum raw scores instead of `1/(k+rank)`, or fuse using each source's raw ranking position from a differently-ordered list), producing a fused order that doesn't actually reflect combined relevance | Manually verify the RRF formula in the diff (`1 / (k + rank)`, summed per document across the two ranked lists) matches design.md's specification exactly |
| 3 | Generated tsvector column | AI may maintain `chunk_tsv` via application code (violating the design decision to use a Postgres generated column) or get the `GENERATED ALWAYS AS (...) STORED` syntax wrong, causing insert failures or a column that silently never updates | Confirm the migration uses `GENERATED ALWAYS AS (to_tsvector('english', chunk_text)) STORED`, not an application-side `_store_chunks` write to `chunk_tsv` |
| 4 | Metadata filter SQL injection | AI may interpolate `metadata_filter` values directly into SQL text instead of using bound parameters, since this is the first time a caller-supplied filter value flows into a WHERE clause in this codebase | Confirm `document_id` (and any future filter key) is passed as a bound parameter (`:document_id`), never string-interpolated into the SQL text |
| 5 | Per-source candidate cap | AI may forget to cap dense/sparse candidate counts before fusion, causing query cost to scale unboundedly with a large `top_k`, or may cap too aggressively and starve fusion of candidates | Test scenario 10 explicitly; confirm the cap constant and multiplier are visible and documented in the diff, not silently hardcoded to `top_k` itself |
| 6 | Existing DenseRetriever behavior regression | AI may inadvertently change `DenseRetriever`'s `WHERE`/`ORDER BY` clauses while updating it to accept `metadata_filter`, regressing `retrieval-foundation`'s already-verified parity behavior when no filter is passed | Test that calling `DenseRetriever.retrieve` with `metadata_filter=None` produces identical results to calling it with no `metadata_filter` argument at all |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG (SQL + document search + NER), citation-required, tenant-scoped, pgvector for document search (not a separate vector DB) | This change must keep document search on pgvector (no new vector store), keep the three-source shape, and not weaken citation enforcement | Confirm no new vector database dependency is introduced; confirm `RAGOrchestrator.execute`'s three-source `asyncio.gather` structure is unchanged; confirm `guardrails.enforce_sources` is unchanged |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (hnsw index used): query plan or index-name check confirming `hnsw` index used
- [x] Scenario 2 (orchestrator uses Retriever): code review confirming `_vector_source` calls `Retriever.retrieve`
- [x] Scenario 3 (sparse returns matches): live pgvector test with a seeded exact-term chunk
- [x] Scenario 4 (sparse zero matches, no error): live pgvector test with a non-overlapping query
- [x] Scenario 5 (RRF fuses dense+sparse): live pgvector test with a chunk matching both signals
- [x] Scenario 6 (dense-only survives fusion): live pgvector test with a semantic-only-match chunk
- [x] Scenario 7 (metadata_filter scopes to one document): live pgvector test with two documents
- [x] Scenario 8 (default config unchanged): unit test asserting defaults
- [x] Scenario 9 (config override): unit test asserting `NER_RETRIEVAL_TOP_K` override
- [x] Scenario 10 (candidate count bounded): test asserting per-source query cap
- [x] Scenario 11 (hybrid search returns relevant chunks): regression/integration test
- [x] Scenario 12 (empty corpus): regression test
- [x] Scenario 13 (citation page number populated): regression test (from chunk-metadata-ingest, re-run)
- [x] Scenario 14 (citation page number null-safe): regression test (from chunk-metadata-ingest, re-run)
- [x] Scenario 15 (lexical exact-term retrieval end-to-end): integration test simulating a chat query with an exact identifier

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] New alembic migration reviewed for idempotency and correctness against migration 010's precedent

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — migration diffed against 010's loop pattern; `pg_indexes` confirms only `hnsw` remains
- [x] Risk 2 mitigation confirmed — RRF formula manually verified against design.md
- [x] Risk 3 mitigation confirmed — `chunk_tsv` is a generated column, not application-maintained
- [x] Risk 4 mitigation confirmed — `metadata_filter` values are bound parameters, never string-interpolated
- [x] Risk 5 mitigation confirmed — candidate cap constant visible in diff, tested
- [x] Risk 6 mitigation confirmed — `DenseRetriever` with `metadata_filter=None` matches no-argument behavior exactly

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | migration run + `pg_indexes` query | Ran `alembic upgrade head` against live `pgvector/pgvector:pg16` test container (port 54320); `pg_indexes` on `tenant_template.document_chunks` showed only `document_chunks_pkey`, `idx_document_chunks_tsv`, `idx_document_chunks_embedding_hnsw` (no `ivfflat`); `information_schema.columns` confirmed `chunk_tsv` has `is_generated = ALWAYS` | 1 | agent (opsx:apply) | 2026-07-27 |
| 2 | migration downgrade/upgrade round-trip | Ran `alembic downgrade -1` then re-checked `pg_indexes`: only `idx_document_chunks_embedding` (ivfflat) remained; re-ran `alembic upgrade head` cleanly | 1 (rollback safety) | agent (opsx:apply) | 2026-07-27 |
| 3 | `pytest tests/test_hybrid_retrieval.py -v` | 9/9 passed: sparse exact-term match, sparse zero-match, metadata_filter document scoping, metadata_filter None==no-arg parity, bound-parameter check, hybrid dual-match ranking, hybrid dense-only survival, hybrid candidate-cap unit test, orchestrator low-similarity lexical retrieval | 3, 4, 5, 6, 7, 10, 15 | agent (opsx:apply) | 2026-07-27 |
| 4 | `pytest tests/test_retrieval_foundation.py tests/test_chat_api_rag.py -k "chat or rag or retriev or citation or chunk"` | 95 passed, 2 skipped, 1 pre-existing unrelated failure (`test_chat_response_sources`, a disclaimer-wording assertion in already-modified `schemas.py`, present before this change and untouched by it) | 2, 8, 9, 11, 12, 13, 14 | agent (opsx:apply) | 2026-07-27 |
| 5 | code review | `_vector_source` in `src/chat_api/services/rag_orchestrator.py` unchanged except which `Retriever` instance `self.retriever` holds (`HybridRetriever` instead of `DenseRetriever`); `RAGOrchestrator.execute`'s three-source `asyncio.gather` and `guardrails.enforce_sources` call sites unchanged | 2, ADR-007 | agent (opsx:apply) | 2026-07-27 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** hybrid-retrieval-hnsw
**Proposal:** `openspec/changes/hybrid-retrieval-hnsw/proposal.md`
**Spec files reviewed:**
  - specs/retrieval-core/spec.md
  - specs/chat-api/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
