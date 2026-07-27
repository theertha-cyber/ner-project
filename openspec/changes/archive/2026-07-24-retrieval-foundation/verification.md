# Verification Plan

**Change:** retrieval-foundation
**Generated:** 2026-07-24
**Status:** 🟡 Evidence collected, all scenarios pass — Audit Record still requires human sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | retrieval-core | Typed retrieval domain model | Ingestion produces typed chunks | Given text extracted from a document, when the shared chunking function splits it, then each chunk is a `Chunk` model instance (not a dict) with `chunk_index` and `chunk_text` | `tests/test_retrieval_foundation.py::TestSharedChunking` + `TestOrchestratorVectorSourceIntegration` (task 4.4) | - [x] |
| 2 | retrieval-core | Typed retrieval domain model | Retrieval returns typed results | Given a similarity search for a query, when the retriever returns matches, then each result is a `RetrievalResult` model instance with `document_id`, `chunk_index`, `chunk_text`, `similarity_score`, and `rag_orchestrator` consumes these objects directly | `tests/test_retrieval_foundation.py::TestOrchestratorVectorSourceIntegration` (task 4.4) | - [x] |
| 3 | retrieval-core | Retriever interface | DenseRetriever matches existing similarity search behavior | Given a tenant schema with chunks/embeddings and a fixed query, when `DenseRetriever.retrieve` is called with `top_k=5`, then results (document_id, chunk_index, chunk_text, similarity_score, ordering) are identical to the prior `EmbeddingService.similarity_search` output | `tests/test_retrieval_foundation.py::TestDenseRetrieverParity` (tasks 3.3-3.4) | - [x] |
| 4 | retrieval-core | Retriever interface | rag_orchestrator retrieves via the Retriever interface | Given the orchestrator needs document context, when `_vector_source` executes, then it calls a `Retriever.retrieve` implementation rather than `EmbeddingService.similarity_search` directly | `tests/test_retrieval_foundation.py::TestOrchestratorVectorSourceIntegration` (task 4.4) | - [x] |
| 5 | retrieval-core | Single chunking implementation | Ingestion and chat share one chunking function | Given the codebase after this change, when searching for fixed-size token chunking implementations, then exactly one exists in `src/shared/retrieval` and `ocr_worker.py` imports it | `tests/test_retrieval_foundation.py::TestSharedChunking::test_single_chunking_implementation_in_codebase` (task 2.6) | - [x] |
| 6 | retrieval-core | Single chunking implementation | Chunking output is unchanged for existing documents | Given a document's text that produced N chunks under the old `_chunk_text` (512/128), when chunked by the shared implementation with equivalent defaults, then chunk boundaries and count are identical | `tests/test_retrieval_foundation.py::TestSharedChunking::test_chunking_preserves_512_128_boundaries_and_overlap` (task 2.2) | - [x] |
| 7 | retrieval-core | Citation enrichment executes without error | Document name resolution succeeds for a chat response with document sources | Given a chat response with at least one `Source` having a `document_id`, when `_enrich_citations` runs, then the filename lookup executes without `NameError` and `Citation.document_name` is populated when the document exists | `tests/test_retrieval_foundation.py::TestCitationEnrichmentBugFix` (task 5.3) | - [x] |
| 8 | retrieval-core | Centralized retrieval configuration | Default configuration matches prior hardcoded behavior | Given no retrieval-specific env vars are set, when configuration loads, then chunk size=512, overlap=128, top_k=5, embedding model=`text-embedding-3-small` | `tests/test_retrieval_foundation.py::TestRetrievalConfigDefaults::test_defaults_match_prior_hardcoded_values` (task 1.3) | - [x] |
| 9 | retrieval-core | Centralized retrieval configuration | Configuration is overridable via environment variable | Given `NER_RETRIEVAL_TOP_K=8`, when configuration loads, then `DenseRetriever` defaults to `top_k=8` when no explicit argument is passed | `tests/test_retrieval_foundation.py::TestRetrievalConfigDefaults::test_top_k_overridable_via_env` + `TestDenseRetrieverConfig` (task 3.5) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | "Behavior-identical" `DenseRetriever` refactor | AI may subtly change the SQL (e.g., different `ORDER BY`, different `<=>` vs `<->` operator, off-by-one on `LIMIT`) while believing it preserved behavior, silently changing which chunks get cited | Run the before/after fixture diff from design.md's first risk mitigation — compare raw SQL text and query output row-for-row against the pre-refactor `similarity_search` on the same seeded data |
| 2 | Chunking consolidation deleting `chunking_service.chunk_and_embed_document` | AI may delete this function assuming it's dead code without confirming no caller exists (e.g., a Celery task, script, or test references it) | grep the full repo (including `tests/`, `scripts/`, alembic data-migration scripts) for `chunk_and_embed_document` before removing it |
| 3 | Citation bug fix scope creep | AI may "improve" `_enrich_citations` beyond the missing import fix (e.g., changing the SQL, changing which fields populate `Citation`), conflating a bug fix with a behavior change not covered by any scenario | Diff the fix against the original function — only the missing `from sqlalchemy import text` import (and strictly necessary adjacent syntax) should change; any other diff line needs justification against a spec scenario |
| 4 | `RetrievalConfig` defaults drifting from current literals | AI may introduce new default values (e.g., "improving" top_k to 10) instead of preserving the exact current constants (512, 128, 5, text-embedding-3-small) | Unit test asserting `Settings()` defaults equal the four literals verbatim, run with no `NER_*` retrieval env vars set |
| 5 | Domain model field naming not matching spec | AI may name `RetrievalResult` fields differently than the spec's `document_id`/`chunk_index`/`chunk_text`/`similarity_score` (e.g., `score` instead of `similarity_score`), breaking `rag_orchestrator`'s existing `Source` construction silently via attribute access | Compare `RetrievalResult` field names directly against spec §Requirement "Typed retrieval domain model" and against every attribute access in the updated `rag_orchestrator.py` |
| 6 | Shared module scope creep | AI may move service-specific logic (guardrails, SQL generation, NER client) into `src/shared/retrieval/` beyond models/protocol/chunking/config, widening blast radius against design.md's explicit non-goal | Review the diff of `src/shared/retrieval/` — only `Chunk`, `RetrievalResult`, `Retriever` protocol, `DenseRetriever`, chunking function, and config fields should appear |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG (SQL + pgvector semantic search + NER), citation-required responses, tenant-scoped, complexity limits | This change must not alter the three-source shape, must not remove or weaken citation enforcement, must keep responses tenant-scoped, and must not touch the complexity-limit guardrail | Confirm `RAGOrchestrator.execute` still calls `_sql_source`, `_vector_source`, and NER inference; confirm `guardrails.enforce_sources` and `check_blocked_question_type` are unchanged; confirm no cross-tenant schema parameter is introduced |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 & 2 (typed models): `TestOrchestratorVectorSourceIntegration` shows `_vector_source` returns `RetrievalResult` instances end-to-end against a live seeded schema; `_store_chunks`/ingestion path constructs `Chunk` instances (task 4.3, code review)
- [x] Scenario 3 (DenseRetriever parity): `TestDenseRetrieverParity` — live pgvector fixture diff, identical document_id/chunk_index/chunk_text/similarity_score/ordering for all 3 seeded chunks
- [x] Scenario 4 (orchestrator uses Retriever): `TestOrchestratorVectorSourceIntegration` confirms `_vector_source` returns via `Retriever.retrieve`, and `EmbeddingService.similarity_search` no longer exists (`hasattr` check)
- [x] Scenario 5 (single chunking impl): `test_single_chunking_implementation_in_codebase` — `git grep --untracked` returns exactly `src/shared/retrieval/chunking.py`
- [x] Scenario 6 (chunking output unchanged): `test_chunking_preserves_512_128_boundaries_and_overlap` — 512-token chunks, exact 128-token overlap verified via tokenizer round-trip
- [x] Scenario 7 (citation bug fixed): `TestCitationEnrichmentBugFix` — `_enrich_citations` executes without `NameError`, `Citation.document_name` populated
- [x] Scenario 8 (default config matches prior literals): `test_defaults_match_prior_hardcoded_values` passes
- [x] Scenario 9 (config override works): `test_top_k_overridable_via_env` + `TestDenseRetrieverConfig` pass

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `TestDenseRetrieverParity` diffs `DenseRetriever` output against the verbatim-ported pre-refactor SQL (`_old_similarity_search`) on live seeded data — identical
- [x] Risk 2 mitigation confirmed — repo-wide grep for `chunk_and_embed_document` performed before deletion (task 2.4), zero callers found
- [x] Risk 3 mitigation confirmed — citation bug fix diff contains only the added `from sqlalchemy import text` import; function body byte-identical (task 5.2)
- [x] Risk 4 mitigation confirmed — `test_defaults_match_prior_hardcoded_values` passes with no env overrides
- [x] Risk 5 mitigation confirmed — `RetrievalResult` field names (`document_id`, `chunk_index`, `chunk_text`, `similarity_score`) match spec and all `rag_orchestrator.py` attribute accesses
- [x] Risk 6 mitigation confirmed — `src/shared/retrieval/` contains only `models.py`, `chunking.py`, `retriever.py`, `__init__.py` — no service-specific logic

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | Standalone script execution (`py -c` against project venv): `Settings()` defaults verified equal to 512/128/5/`text-embedding-3-small`; `NER_RETRIEVAL_TOP_K=8` override verified changing `retrieval_top_k` | 8, 9 | agent | 2026-07-24 |
| 2 | Functional | Standalone script execution: `chunk_text` on a 2000-token sample produced 13 chunks, each interior chunk exactly 512 tokens, consecutive chunks overlapping by exactly 128 tokens (`prev_tokens[-128:] == next_tokens[:128]`) | 6 | agent | 2026-07-24 |
| 3 | Functional | Standalone script execution: `DenseRetriever.retrieve` called with a fake embedding service + fake session; captured SQL bind param confirmed `top_k=5` default from `settings.retrieval_top_k` (unpatched) | 9 (default path) | agent | 2026-07-24 |
| 4 | Functional | Standalone script execution: `RAGOrchestrator._enrich_citations` invoked with a `Source(document_id="doc-1", ...)` against a fake session — executed without `NameError`, `Citation.document_name == "report.pdf"` | 7 | agent | 2026-07-24 |
| 5 | Structural | `git grep --untracked -l 'def chunk_text\|def _chunk_text' -- src` returned exactly `src/shared/retrieval/chunking.py`; confirmed `src/chat_api/services/chunking_service.py` no longer exists on disk | 5 | agent | 2026-07-24 |
| 6 | Structural | `grep -rn similarity_search` across `src/**/*.py` returned zero matches after removal from `embedding_service.py`, confirming no other caller existed | 4 (partial — structural only) | agent | 2026-07-24 |
| 7 | Structural | `python -m py_compile` run against all 9 touched files (`src/shared/retrieval/*.py`, `src/shared/config.py`, `src/document_service/services/ocr_worker.py`, `src/chat_api/services/embedding_service.py`, `src/chat_api/services/rag_orchestrator.py`, `tests/test_retrieval_foundation.py`) — all compiled cleanly | 1, 2, 3, 4, 5, 6, 7, 8, 9 (syntax-level only) | agent | 2026-07-24 |
| 8 | Functional | Live pgvector run (docker `postgres-test` container, isolated `ner_test` DB created for this run; `tests/conftest.py`'s pre-existing schema-qualified-constraint bug in the `tenant_schema` fixture fixed to unblock — `ALTER TABLE ... DROP CONSTRAINT` doesn't accept a schema-qualified constraint name): `pytest tests/test_retrieval_foundation.py -v` → 10 passed, 0 failed, 0 skipped. Includes `TestDenseRetrieverParity` (scenario 3) and `TestOrchestratorVectorSourceIntegration` (scenarios 1, 2, 4), previously blocked | 1, 2, 3, 4, 5, 6, 7, 8, 9 | agent | 2026-07-24 |
| 9 | Functional | Pre-existing regression suite run against the same live DB: `tests/test_document_ingestion.py` → 12 passed; `tests/test_chat_api_rag.py` → 18 passed, 2 skipped (OpenAI-key-gated, pre-existing skip markers), 1 failed (`test_chat_response_sources` — disclaimer text assertion, unrelated to this change) | (regression — no new scenarios) | agent | 2026-07-24 |
| 10 | Structural | Confirmed via `git stash` that `test_chat_response_sources` fails identically on unmodified `main` (disclaimer text says "generated by AI", test asserts "AI-generated") — pre-existing failure, not introduced by this change; `src/chat_api/api/v1/schemas.py` was never touched | (regression — confirms no new failure) | agent | 2026-07-24 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** retrieval-foundation
**Proposal:** `openspec/changes/retrieval-foundation/proposal.md`
**Spec files reviewed:**
  - specs/retrieval-core/spec.md

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

**Archive approved by:** _____Arjun______________________

**Date:** _____24 July 2026______

**Notes:**
All 9 scenarios verified with real evidence: 8 initially via standalone execution, then all 9 (including the previously-blocked live-DB scenarios 1, 2, 3, 4) via `pytest` against a live pgvector instance once Docker containers became available. Two incidental fixes were needed to get there, both out of this change's spec scope but necessary and minimal: (1) `tests/conftest.py`'s `tenant_schema` fixture had a pre-existing SQL syntax bug (`DROP CONSTRAINT` with a schema-qualified name) unrelated to this change, fixed to unblock test execution; (2) tests were pointed at a fresh isolated `ner_test` database created on the running Postgres container rather than the real `ner_dev` dev database, after the first attempt against `ner_dev` hit foreign-key errors from real seeded data during fixture teardown.

One pre-existing, unrelated test failure remains: `tests/test_chat_api_rag.py::TestGuardrailEnforcement::test_chat_response_sources` (disclaimer text mismatch in `src/chat_api/api/v1/schemas.py`, a file this change never touches) — confirmed present on unmodified `main` via `git stash`. Not in scope for this change; flagging for a separate fix.

Remaining before archive: human reviewer sign-off below (Reviewer Sign-Off, AI Output Review, Archive approved by).
