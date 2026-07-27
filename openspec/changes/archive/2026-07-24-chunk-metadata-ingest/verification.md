# Verification Plan

**Change:** chunk-metadata-ingest
**Generated:** 2026-07-24
**Status:** 🟡 Functional evidence collected — Evidence Log/Audit Record still need human reviewer sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | retrieval-core | Typed retrieval domain model | Ingestion produces typed chunks | Given text extracted from a document, when the shared chunking function splits it, then each chunk is a `Chunk` model instance with `chunk_index` and `chunk_text`, never a raw dict | regression: task 5.1 | - [x] |
| 2 | retrieval-core | Typed retrieval domain model | Retrieval returns typed results | Given a similarity search for a query, when the retriever returns matches, then each result is a `RetrievalResult` with `document_id`, `chunk_index`, `chunk_text`, `similarity_score`, consumed directly by `rag_orchestrator` | regression: task 5.1 | - [x] |
| 3 | retrieval-core | Typed retrieval domain model | Chunk carries page metadata when produced from a span | Given a span with `page_number=2`, `char_start=100`, `char_end=400`, when chunked, then every resulting `Chunk` has `page_number=2` and `char_start`/`char_end` within `[100, 400]` | unit test: task 2.4 | - [x] |
| 4 | retrieval-core | Typed retrieval domain model | RetrievalResult exposes page metadata when present | Given a `document_chunks` row with `page_number=2`, `char_start=100`, `char_end=250`, when `DenseRetriever.retrieve` returns it, then `RetrievalResult` has matching `page_number`/`char_start`/`char_end` | live pgvector test: task 4.3 | - [x] |
| 5 | retrieval-core | Typed retrieval domain model | RetrievalResult metadata is None for chunks ingested before this change | Given a `document_chunks` row with `page_number`/`char_start`/`char_end` all `NULL`, when returned by `DenseRetriever.retrieve`, then `RetrievalResult` has all three as `None` and no exception is raised | live pgvector test: task 4.4 | - [x] |
| 6 | retrieval-core | Single chunking implementation | Ingestion and chat share one chunking function | Given the codebase after this change, when searching for chunking implementations, then exactly one exists in `src/shared/retrieval` and `ocr_worker.py` imports it | regression: task 5.1 | - [x] |
| 7 | retrieval-core | Single chunking implementation | A chunk never spans more than one page | Given a document with span A on page 0 and span B on page 1, when ingested and chunked, then no chunk contains text from both spans, and each chunk's `page_number` matches exactly one source span | integration test: task 3.3 | - [x] |
| 8 | retrieval-core | Single chunking implementation | Empty spans produce no chunks | Given a span whose text is empty or whitespace-only, when chunked, then no `Chunk` is produced for that span | unit test: task 2.5 | - [x] |
| 9 | chat-api | pgvector semantic search | Semantic search returns relevant chunks | Given document chunks with embeddings for a tenant, when the RAG pipeline performs semantic search, then the result contains the top-K most similar chunks with `document_id`, `chunk_text`, `similarity_score` | regression: task 5.2 | - [x] |
| 10 | chat-api | pgvector semantic search | Semantic search with empty corpus | Given a tenant with no document chunks, when semantic search runs, then the pipeline skips the pgvector source and the response has no document chunk sources | regression: task 5.2 | - [x] |
| 11 | chat-api | pgvector semantic search | Citation includes page number when the chunk has one | Given a retrieved chunk with `page_number=3`, when `_enrich_citations` builds its citation, then `Citation.page_number == 3` | unit test: task 4.6 | - [x] |
| 12 | chat-api | pgvector semantic search | Citation page number is null for chunks without metadata | Given a retrieved chunk with no `page_number` (pre-change), when `_enrich_citations` builds its citation, then `Citation.page_number` is `None` and no exception is raised | unit test: task 4.7 | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Per-span chunking rewrite of `process_document` | AI may accidentally revert to joining all spans into one `full_text` blob before chunking (the old behavior), silently losing per-page attribution while appearing to work (chunks still get created, just without correct page numbers) | Read the updated `ocr_worker.py` — confirm the chunker is called once per span's own text, not once on a joined multi-span string; confirm each stored chunk's `page_number` matches its originating span |
| 2 | Migration touching every tenant schema | AI may write the `DO $$ ... FOR schema_name IN ...` loop incorrectly (e.g., wrong `LIKE` pattern, missing `tenant_template` exclusion/inclusion, non-idempotent `ADD COLUMN` without `IF NOT EXISTS`) — could fail loudly on second run or silently skip schemas | Diff the new migration's loop against migration 010's proven loop structure line-by-line; run the migration twice locally (idempotency check) |
| 3 | Nullable metadata handling downstream | AI may forget that `page_number`/`char_start`/`char_end` can be `None` for pre-existing chunks and write code (e.g., in `_enrich_citations` or `DenseRetriever`) that assumes they're always present, raising on old data | Test scenario 5 and 12 explicitly exercise `NULL`/`None` metadata; confirm no `int(row.page_number)` or similar unguarded cast exists in the diff |
| 4 | Empty-span filtering scope creep | AI may change the empty-span filtering logic in a way that also changes which spans get stored in `document_text_spans` (not just which get chunked), altering existing ingestion behavior beyond this change's scope | Diff confirms `document_text_spans` insertion logic (which spans get stored) is unchanged; only the chunking step's per-span iteration gains an empty-check |
| 5 | Retriever SQL column addition | AI may change `DenseRetriever`'s `ORDER BY`, `WHERE`, or index usage while adding the three new `SELECT` columns, unintentionally altering retrieval-foundation's already-verified ranking behavior | Diff `DenseRetriever.retrieve`'s SQL against the `retrieval-foundation` version — only the `SELECT` column list should differ |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation-required responses, tenant-scoped | This change must not alter the three-source shape or weaken citation enforcement; it only enriches citations with page numbers | Confirm `guardrails.enforce_sources` is unchanged and `_enrich_citations` still returns a non-empty `Citation` list whenever sources exist, regardless of `page_number` presence |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (typed chunks): test output confirming `Chunk` instances, no raw dicts, at chunking boundary
- [x] Scenario 2 (typed results): test output confirming `RetrievalResult` consumed directly by `rag_orchestrator`
- [x] Scenario 3 (chunk carries page metadata): test chunking a span with known `page_number`/`char_start`/`char_end`, asserting propagation
- [x] Scenario 4 (RetrievalResult exposes metadata): live pgvector test — insert a chunk row with metadata, retrieve it, assert fields match
- [x] Scenario 5 (RetrievalResult metadata None-safe): live pgvector test — insert a chunk row with NULL metadata, retrieve it, assert `None` fields and no exception
- [x] Scenario 6 (single chunking impl): grep test confirming one implementation location
- [x] Scenario 7 (chunk never spans pages): test with a two-page document, asserting no chunk mixes page 0 and page 1 text
- [x] Scenario 8 (empty spans produce no chunks): test with a whitespace-only span, asserting zero chunks
- [x] Scenario 9 (semantic search returns relevant chunks): existing chat-api regression test still passes
- [x] Scenario 10 (empty corpus): existing chat-api regression test still passes
- [x] Scenario 11 (citation includes page number): test constructing a citation from a chunk with `page_number=3`, asserting `Citation.page_number == 3`
- [x] Scenario 12 (citation page number null-safe): test constructing a citation from a chunk with no page metadata, asserting `Citation.page_number is None` and no exception

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] New alembic migration reviewed for idempotency and correctness against migration 010's precedent

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `ocr_worker.py` chunks per-span, not per joined `full_text`
- [x] Risk 2 mitigation confirmed — migration loop diffed against migration 010, run twice locally without error
- [x] Risk 3 mitigation confirmed — no unguarded cast of nullable metadata fields found in diff
- [x] Risk 4 mitigation confirmed — `document_text_spans` insertion logic unchanged in diff
- [x] Risk 5 mitigation confirmed — `DenseRetriever` SQL diff shows only `SELECT` column list changed

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test run (live DB) | `docker exec ner-project-celery_worker-1 python -m pytest tests/test_chunk_metadata_ingest.py tests/test_retrieval_foundation.py -v` against `postgres-test` — 20/20 test assertions PASSED (5 teardown-only errors from a pre-existing unrelated "Acme Corp" tenant referenced by `audit_events`, not this change's data) | 1,2,3,4,5,6,7,8,9,10,11,12 | AI agent (opsx:apply) | 2026-07-24 |
| 2 | Migration run (live DB) | `alembic upgrade head` → `downgrade 020` → `upgrade head` in `ner-project-celery_worker-1` against `postgres-test`; raw upgrade SQL additionally re-executed twice directly via `psql` (bypassing alembic's revision-skip) — clean `NOTICE: already exists, skipping`, no errors both times | Hallucination Risk 2 | AI agent (opsx:apply) | 2026-07-24 |
| 3 | Code diff / grep | `git grep` confirms exactly one `chunk_text`/`_chunk_text` implementation (`src/shared/retrieval/chunking.py`); `document_text_spans` INSERT block byte-identical to prior committed revision; no `int(...)` unguarded cast of `page_number`/`char_start`/`char_end` found in `src/` | Hallucination Risks 1, 3, 4; Scenario 6 | AI agent (opsx:apply) | 2026-07-24 |

**Note on Risk 2 / Migration 021:** the first live run surfaced a real bug — the tenant-loop `ALTER TABLE` failed against an orphaned tenant schema (`tenant_test_tenant`, created by `tests/conftest.py`'s tenant fixture, which doesn't create the migration-010 `document_chunks` table). Fixed by changing `ALTER TABLE %I.document_chunks` to `ALTER TABLE IF EXISTS %I.document_chunks` in both the upgrade and downgrade loops of `021_document_chunks_page_metadata.py`.

**Note on `_store_chunks`:** the live test run also surfaced a pre-existing, unrelated bug: the embedding insert used `:embedding::vector`, which SQLAlchemy's `text()` never binds (its parser excludes `:name` immediately followed by `::`, to support Postgres's cast syntax) — sent to Postgres as literal `:embedding::vector` and would always fail on any real document ingestion. Fixed to `CAST(:embedding AS vector)` in `src/document_service/services/ocr_worker.py`.

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** chunk-metadata-ingest
**Proposal:** `openspec/changes/chunk-metadata-ingest/proposal.md`
**Spec files reviewed:**
  - specs/retrieval-core/spec.md
  - specs/chat-api/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** ____________Arjun_______________

**Date:** ____24-7-26_______

**Notes:**
