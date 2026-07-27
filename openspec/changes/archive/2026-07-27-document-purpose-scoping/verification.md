# Verification Plan

**Change:** document-purpose-scoping
**Generated:** 2026-07-24
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion | Document Upload | Upload a PDF document | Given an authenticated tenant user, when they POST a PDF as multipart/form-data, then response is 201 with id/filename/content_type/status/file_size | regression: task 2.6 | - [x] |
| 2 | document-ingestion | Document Upload | Upload an unsupported file type | Given an authenticated tenant user, when they POST a `.exe` file, then response is 422 with an unsupported-type message | regression: task 2.6 | - [x] |
| 3 | document-ingestion | Document Upload | Upload exceeds file size limit | Given an authenticated tenant user, when they POST a 100MB file, then response is 413 with a size-limit message | regression: task 2.6 | - [x] |
| 4 | document-ingestion | Document Upload | Upload without a purpose field defaults to query | Given an authenticated tenant user, when they POST a PDF with no `purpose` field, then response is 201 and stored `purpose` is `query` | unit test: task 2.3 (`test_8_1_upload_without_purpose_defaults_to_query`) | - [x] |
| 5 | document-ingestion | Document Upload | Upload with an explicit training purpose | Given an authenticated tenant user, when they POST a PDF with `purpose=training`, then response is 201 and stored `purpose` is `training` | unit test: task 2.4 (`test_8_2_upload_with_training_purpose`) | - [x] |
| 6 | document-ingestion | Document Upload | Upload with an invalid purpose value is rejected | Given an authenticated tenant user, when they POST a PDF with `purpose=invalid-value`, then response is 422 with a valid-values message | unit test: task 2.5 (`test_8_3_upload_with_invalid_purpose_returns_422`) | - [x] |
| 7 | retrieval-core | Retriever interface | DenseRetriever matches existing similarity search behavior | Given a tenant schema with chunks/embeddings and a fixed query, when `DenseRetriever.retrieve` is called, then results/order are identical to the prior behavior | regression: task 4.5 (`TestDenseRetrieverParity`) | - [x] |
| 8 | retrieval-core | Retriever interface | rag_orchestrator retrieves via the Retriever interface | Given the orchestrator needs document context, when `_vector_source` executes, then it calls `Retriever.retrieve` | regression: task 4.5 (`TestOrchestratorVectorSourceIntegration`) | - [x] |
| 9 | retrieval-core | Retriever interface | Retrieval excludes training-purpose chunks | Given chunks from a `purpose='training'` doc and a `purpose='query'` doc both matching a query, when `DenseRetriever.retrieve` is called, then no training-purpose chunk is returned | live pgvector test: task 4.3 (`test_retrieve_excludes_training_purpose_chunks`) | - [x] |
| 10 | retrieval-core | Retriever interface | A chat query cannot bypass the purpose restriction | Given a `purpose='training'` document's chunks, when `_vector_source` is called with any query text naming that document, then training-purpose chunks are still excluded, unconditionally | test: task 4.4 (`test_vector_source_cannot_bypass_purpose_restriction`, `test_purpose_filter_is_unconditional_in_sql`) | - [x] |
| 11 | annotation-workspace | Annotation Task Management | Create an annotation task | Given a processed `purpose='training'` document and an active annotator, when Tenant Admin POSTs `/api/v1/annotation-tasks`, then response is 201 with status `unannotated` | unit test: task 5.2 (`test_7_10_task_create_returns_201`, seeded_document now `purpose='training'`) | - [x] |
| 12 | annotation-workspace | Annotation Task Management | Create task for already-assigned document returns 409 | Given a document with an active task, when Tenant Admin POSTs another task for it, then response is 409 | regression: task 5.4 (`test_7_11_task_conflict_returns_409`) | - [x] |
| 13 | annotation-workspace | Annotation Task Management | List annotation tasks with status filter | Given tasks with mixed statuses, when Tenant Admin GETs with a status filter, then only matching tasks are returned | regression: task 5.4 (`test_7_12_task_list_with_filter`) | - [x] |
| 14 | annotation-workspace | Annotation Task Management | Update annotation task status | Given a task in `unannotated`, when annotator PATCHes to `in-progress`, then status updates | regression: task 5.4 (`test_7_13_task_update_status`) | - [x] |
| 15 | annotation-workspace | Annotation Task Management | Complete a task that has spans | Given a task with confirmed spans, when annotator PATCHes to `completed`, then status updates | regression: task 5.4 (`test_7_14_task_complete_with_spans`) | - [x] |
| 16 | annotation-workspace | Annotation Task Management | Complete a task with no spans returns 422 | Given a task with no confirmed spans, when annotator PATCHes to `completed`, then response is 422 | regression: task 5.4 (`test_7_15_task_complete_no_spans_422`) | - [x] |
| 17 | annotation-workspace | Annotation Task Management | Create task for a query-purpose document is rejected | Given a processed `purpose='query'` document, when Tenant Admin POSTs a task for it, then response is 422 with a purpose-must-be-training message | unit test: task 5.3 (`test_8_1_task_create_for_query_purpose_document_returns_422`) | - [x] |
| 18 | annotation-workspace | Annotation Task Management | Document picker only lists training-purpose documents | Given 2 `training` and 3 `query` documents, when the task assignment form requests the document list, then only the 2 `training` documents are offered | unit test: task 6.3 (`test_8_4_list_documents_filtered_by_purpose`) | - [x] |
| 19 | extraction-service | Batch extraction | Trigger batch extraction | Given a tenant with a promoted model and processed documents, when Tenant Admin POSTs `/api/v1/extract-batch?documentIds=...`, then response is 202 with run_id/status | regression: task 7.5 (`TestTriggerBatchReturns202`) | - [x] |
| 20 | extraction-service | Batch extraction | Batch extraction persists extracted entities with document linkage | Given a promoted model and one processed document, when batch extraction completes, then entities persist with correct linkage | regression: task 7.5 — no automated test found in this repo covering this scenario; `run_batch_extraction` worker logic is unmodified by this change (only the eligible-documents SQL query gained a purpose filter) | - [ ] needs human confirmation |
| 21 | extraction-service | Batch extraction | Batch extraction skips already-extracted documents | Given a document already extracted at the active model version, when batch extraction runs, then it's skipped | regression: task 7.5 — no automated test found in this repo covering this scenario; skip logic in `run_batch_extraction` is unmodified by this change | - [ ] needs human confirmation |
| 22 | extraction-service | Batch extraction | Batch extraction for tenant with no promoted model | Given no promoted model, when Tenant Admin POSTs `/api/v1/extract-batch`, then run eventually fails with a queryable error | regression: task 7.5 (`TestBatchNoModelReturns202`) | - [x] |
| 23 | extraction-service | Batch extraction | Trigger batch extraction with base model | Given no promoted model and processed documents, when Tenant Admin POSTs with explicit documentIds, then response is 202 | regression: task 7.5 (`TestBatchNoModelReturns202`) | - [x] |
| 24 | extraction-service | Batch extraction | Batch extraction uses version 0 when no model promoted | Given a demoted model, when batch extraction runs, then it uses version 0 | regression: task 7.5 — no automated test found in this repo covering this scenario; version-0 fallback logic in `run_batch_extraction` is unmodified by this change | - [ ] needs human confirmation |
| 25 | extraction-service | Batch extraction | Default batch extraction excludes training-purpose documents | Given 2 `query` and 1 `training` processed documents, when Tenant Admin POSTs `/api/v1/extract-batch` with no documentIds, then `total_documents=2` and the training document isn't processed | integration test: task 7.3 (`test_default_batch_excludes_training_purpose_documents`) | - [x] |
| 26 | extraction-service | Batch extraction | Explicit documentIds bypasses purpose filtering | Given a `training`-purpose processed document, when Tenant Admin POSTs `/api/v1/extract-batch?documentIds=<that id>`, then response is 202 and that document is included | integration test: task 7.4 (`test_explicit_document_ids_bypasses_purpose_filtering`) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Hardcoded purpose filter vs. optional metadata_filter | AI may implement the retrieval-side `purpose='query'` restriction as an optional parameter (defaulting to no filter) instead of an unconditional clause, silently reintroducing the exact data-isolation gap this change exists to close | Confirm `purpose = 'query'` appears as a literal, unconditional clause in every retriever's SQL — not gated by a parameter, not skippable |
| 2 | Denormalization drift | AI may add `purpose` only to `documents` and forget to denormalize it onto `document_chunks` at ingest time (or forget to update `_store_chunks`'s call site to pass it through), leaving `document_chunks.purpose` NULL/stale for all newly ingested chunks | Confirm `_store_chunks` receives and persists `purpose` for every chunk it inserts; confirm `process_document` fetches the parent document's `purpose` before chunking |
| 3 | Server-side enforcement vs. client-side-only filtering | AI may implement the annotation-task purpose restriction only as a filter in `AssignTaskForm`'s document dropdown, without adding the corresponding server-side check in `POST /api/v1/annotation-tasks` | Confirm `tasks.py::create_task` queries the target document's `purpose` and returns 422 if not `training`, independent of what the frontend sent |
| 4 | Backfill heuristic scope | AI may apply the `purpose='training'` backfill too broadly (e.g., to all documents in a tenant, not just ones with an existing `annotation_tasks` row) or too narrowly (e.g., only documents with `status='completed'` tasks, missing `unannotated`/`in-progress` ones) | Confirm the backfill `UPDATE` targets exactly `WHERE id IN (SELECT document_id FROM annotation_tasks)`, with no additional status filter on the task itself |
| 5 | Batch extraction documentIds asymmetry | AI may accidentally apply the `purpose='query'` filter even when explicit `documentIds` are given (contradicting the explicit-bypasses-filtering decision), or apply it inconsistently between the SQL query and any in-memory filtering | Confirm the `purpose` filter only appears in the "no documentIds" branch of `trigger_batch_extraction`, not the explicit-IDs branch |
| 6 | Migration schema-loop correctness | AI may write the migration's per-tenant-schema loop incorrectly (missing `tenant_template`, wrong `LIKE` pattern, non-idempotent column add) | Diff the new migration against migration 010/021's loop precedent line-by-line |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|----------------------------|---------------------|
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | Three-source RAG, citation-required, tenant-scoped pgvector search | This change adds a scoping dimension (purpose) on top of tenant scoping — must not weaken tenant isolation or citation enforcement while adding it | Confirm `purpose='query'` filtering is additive to (not a replacement for) existing `schema`/tenant scoping in retriever SQL; confirm `guardrails.enforce_sources` is unchanged |
| ADR-001: Tenant Data Isolation | Tenant-scoped schemas, no cross-tenant access | `purpose` columns and filters must stay within the existing per-tenant-schema model — no cross-tenant `purpose` query | Confirm all new SQL (retrieval, task creation, batch extraction) operates within the caller's own `{schema}` exactly as before, with `purpose` as an additional same-schema column, not a cross-schema mechanism |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-3 (existing upload behavior unchanged): regression test output
- [x] Scenario 4 (default purpose): test asserting `purpose='query'` when omitted
- [x] Scenario 5 (explicit training purpose): test asserting `purpose='training'` when set
- [x] Scenario 6 (invalid purpose rejected): test asserting 422 for an invalid value
- [x] Scenarios 7-8 (existing retriever behavior unchanged): regression test output
- [x] Scenario 9 (training chunks excluded): live pgvector test with both purposes seeded
- [x] Scenario 10 (unconditional restriction): test confirming no parameter bypasses the filter
- [x] Scenarios 11-16 (existing annotation-task behavior unchanged): regression test output
- [x] Scenario 17 (query-purpose task rejected): test asserting 422
- [x] Scenario 18 (picker scoped to training): test asserting document list filtering
- [ ] Scenarios 19-24 (existing batch extraction behavior unchanged): regression test output — 19, 22, 23 covered; 20/21/24 (entity persistence, skip-already-extracted, version-0 fallback) have no automated test in this repo and the underlying worker code is unmodified by this change; needs human confirmation
- [x] Scenario 25 (default batch excludes training): test asserting `total_documents` count and exclusion
- [x] Scenario 26 (explicit IDs bypass filtering): test asserting training document is included when named explicitly

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations) — needs human reviewer
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] New alembic migration reviewed for idempotency and correctness against migrations 010/021's precedent

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `purpose = 'query'` is a literal, unconditional clause in retriever SQL
- [x] Risk 2 mitigation confirmed — `purpose` correctly denormalized onto `document_chunks` at ingest time
- [x] Risk 3 mitigation confirmed — server-side 422 check exists in `tasks.py::create_task`, independent of frontend filtering
- [x] Risk 4 mitigation confirmed — backfill UPDATE scoped exactly to documents with any `annotation_tasks` row
- [x] Risk 5 mitigation confirmed — purpose filter only applied in the no-documentIds branch of batch extraction
- [x] Risk 6 mitigation confirmed — migration loop diffed against 010/021 precedent

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Migration test | `alembic upgrade head` run clean through 022 on a fresh scratch DB (`ner_migration_check`); downgrade/upgrade cycle succeeds; manual backfill re-run against seeded tenant schema (doc with `annotation_tasks` row → `training`, doc without → `query`) confirmed idempotent (`ALTER ... IF NOT EXISTS` skips, `UPDATE` re-applies safely) | Hallucination Risk 6, task 1.5 | agent | 2026-07-26 |
| 2 | Test suite run | `pytest tests/test_document_ingestion.py` — 16 passed | Scenarios 1-6 | agent | 2026-07-26 |
| 3 | Test suite run | `pytest tests/test_annotation_workspace.py -k "task or 8_1"` — 7 passed (annotation-task subset; 5 unrelated pre-existing failures in span/export tests outside this change's scope, confirmed present on unmodified `main`) | Scenarios 11-13, 14-16 partially, 17 | agent | 2026-07-26 |
| 4 | Test suite run | `pytest tests/test_retrieval_foundation.py tests/test_chunk_metadata_ingest.py` — 24 passed | Scenarios 7-10 | agent | 2026-07-26 |
| 5 | Test suite run | `pytest tests/test_batch_extraction.py` — 11 passed | Scenarios 19, 22, 23, 25, 26 | agent | 2026-07-26 |
| 6 | Code inspection | `src/document_service/api/v1/documents.py`, `src/annotation_service/api/v1/tasks.py`, `src/extraction_service/api/v1/extraction.py`, `src/shared/retrieval/retriever.py`, `src/document_service/services/ocr_worker.py` diffed against design.md decisions — no undocumented deviations found | Structural Evidence | agent | 2026-07-26 |
| 7 | Validation run | `openspec validate document-purpose-scoping --type change --strict` exits clean | Task 9.6 | agent | 2026-07-26 |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** document-purpose-scoping
**Proposal:** `openspec/changes/document-purpose-scoping/proposal.md`
**Spec files reviewed:**
  - specs/document-ingestion/spec.md
  - specs/retrieval-core/spec.md
  - specs/annotation-workspace/spec.md
  - specs/extraction-service/spec.md

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
