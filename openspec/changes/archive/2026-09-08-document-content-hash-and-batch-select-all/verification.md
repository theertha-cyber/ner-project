# Verification Plan

**Change:** document-content-hash-and-batch-select-all
**Generated:** 2026-08-10
**Status:** 🔴 Incomplete — Audit Record must be signed by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion | Document Content Hashing and Duplicate Identification | Upload persists a SHA-256 content hash | Given an authenticated tenant user, when they POST a PDF to `/api/v1/documents`, then the 201 response carries a `checksum` equal to the SHA-256 hex digest of the bytes and the same value is stored in the `checksum` column | tests/test_document_content_hash.py::TestUploadPersistsChecksum::test_upload_returns_and_stores_the_checksum | - [x] |
| 2 | document-ingestion | Document Content Hashing and Duplicate Identification | Identical content produces the same deterministic hash | Given the same file bytes hashed twice, when the content hash is computed, then both hashes are identical and the digest is a 64-character lowercase hex string | tests/test_document_content_hash.py::TestContentHashDeterminism (4 tests) | - [x] |
| 3 | document-ingestion | Document Content Hashing and Duplicate Identification | Different filenames with identical content are recognised as identical content | Given a file already uploaded as `original.pdf`, when the same bytes are uploaded as `renamed-copy.pdf`, then the response is 201 with a new distinct id, both stored checksums are equal, and `duplicate_of` is the first document's id | tests/test_document_content_hash.py::TestDuplicateIdentification::test_identical_content_under_a_different_filename_is_linked; ::test_a_third_copy_points_at_the_original | - [x] |
| 4 | document-ingestion | Document Content Hashing and Duplicate Identification | Different content is not reported as a duplicate | Given a prior upload, when a file with different bytes is uploaded, then the checksums differ and `duplicate_of` is `null` | tests/test_document_content_hash.py::TestDuplicateIdentification::test_different_content_is_not_a_duplicate | - [x] |
| 5 | document-ingestion | Document Content Hashing and Duplicate Identification | Duplicate upload does not modify the original document | Given a prior upload now in `processed` status, when the same bytes are uploaded again, then the original retains its id, filename, `uploaded_by`, and status, and the new document has its own id and `status: "pending"` | tests/test_document_content_hash.py::TestDuplicateIdentification::test_duplicate_upload_does_not_modify_the_original | - [x] |
| 6 | document-ingestion | Document Content Hashing and Duplicate Identification | Duplicate detection does not cross tenant boundaries | Given tenant A uploaded a file, when a tenant B user uploads the same bytes, then tenant B's `duplicate_of` is `null` | tests/test_document_content_hash.py::TestDuplicateIdentification::test_duplicate_detection_does_not_cross_tenants | - [x] |
| 7 | document-ingestion | Document Content Hashing and Duplicate Identification | A soft-deleted document is not reported as a duplicate | Given a prior upload left in `deleted` status, when the same bytes are uploaded again, then `duplicate_of` is `null` | tests/test_document_content_hash.py::TestDuplicateIdentification::test_soft_deleted_document_is_not_reported_as_a_duplicate | - [x] |
| 8 | document-ingestion | Document Content Hashing and Duplicate Identification | Document metadata exposes the stored checksum | Given a document uploaded after hashing was introduced, when a tenant user GETs `/api/v1/documents/{doc_id}`, then the `document` object includes the stored `checksum` | tests/test_document_content_hash.py::TestUploadPersistsChecksum::test_document_metadata_exposes_the_checksum | - [x] |
| 9 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Unextracted documents are selectable | Given a document with `already_extracted: false`, when the user clicks its checkbox, then it becomes checked and the count line reports one selected document | BatchDocumentSelectModal.test.tsx ("makes not-yet-extracted documents selectable and counts them") | - [x] |
| 10 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Select all selects every eligible document and excludes already-extracted ones | Given three selectable and two already-extracted documents, when "Select all" is checked, then all three selectable are checked, both already-extracted remain unchecked and disabled, and the count reports three | BatchDocumentSelectModal.test.tsx ("select all selects every eligible document and excludes already-extracted ones"); ("keeps already-extracted documents visible but disabled") | - [x] |
| 11 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Clearing Select all deselects eligible documents without affecting disabled ones | Given "Select all" checked, when it is unchecked, then every selectable checkbox clears, disabled ones stay unchecked and disabled, and "Run extraction" is disabled | BatchDocumentSelectModal.test.tsx ("clearing select all deselects eligible documents without affecting disabled ones") | - [x] |
| 12 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Select all reflects the current selection state | Given every selectable document individually checked, when the modal renders, then "Select all" is checked; unchecking any single document makes it unchecked | BatchDocumentSelectModal.test.tsx ("reflects the current selection state in the select-all checkbox") | - [x] |
| 13 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Select all is disabled when there are no eligible documents | Given every listed document has `already_extracted: true`, when the modal renders, then "Select all" is disabled and "Run extraction" is disabled | BatchDocumentSelectModal.test.tsx ("disables select all when there are no eligible documents") | - [x] |
| 14 | portal-extraction-page | Batch Document-Selection Modal — Bulk Selection | Run extraction submits only eligible selected documents | Given a mix of selectable and already-extracted documents with "Select all" checked, when the user clicks "Run extraction", then the confirmed id list is exactly the selectable ids | BatchDocumentSelectModal.test.tsx ("run extraction submits only eligible selected documents") | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Column choice (Decision 4) | AI may add a new `content_hash` column instead of populating the `checksum VARCHAR(64)` column that `tenant_template.documents` has declared since migration `002`, leaving a permanently-NULL duplicate column and contradicting `docs/requirements.md` | Confirm no new column is added by any migration in this change; confirm the INSERT writes `checksum` and that migration `034` only creates an index |
| 2 | Duplicate policy (Decision 2) | AI may reject duplicate uploads (409), auto-merge them, or add a unique constraint on `(tenant_id, checksum)` — any of which would break the independent-ownership case and destroy extraction/annotation history | Confirm a duplicate upload returns 201 with its own new id and blob; confirm no `UNIQUE` index exists on `checksum`; confirm no `UPDATE`/`DELETE` targets a pre-existing document row |
| 3 | Tenant isolation (ADR-001) | AI may write the duplicate lookup without the tenant-schema qualifier or without the `tenant_id` predicate, letting one tenant's upload be reported as a duplicate of another tenant's document | Read the duplicate-lookup SQL and confirm it is schema-qualified with `_schema(tenant_id)` *and* filters `tenant_id = :tid`; confirm the cross-tenant test asserts `duplicate_of is None` |
| 4 | Select-all selection state (Decision 5) | AI may store a separate `allSelected` boolean alongside the selection `Set`, letting the header checkbox and row checkboxes drift out of sync, or may iterate all `documents` rather than only selectable ones, admitting a disabled id into the submitted list | Confirm the modal holds exactly one selection state (`Set<string>`) and derives all-selected from it; confirm every mutation path iterates `documents.filter(d => !d.already_extracted)` |
| 5 | Scope creep into the extraction API (Decision 6) | AI may add server-side rejection of already-extracted `documentIds` at `POST /api/v1/extract-batch`, duplicating the worker's idempotency skip and changing the explicit-`documentIds` contract for non-UI callers | Confirm `src/extraction_service/api/v1/extraction.py` and `src/extraction_service/worker.py` are untouched by this change's diff, and that `tests/test_batch_extraction.py` passes unmodified |
| 6 | Modal visual regression (spec constraint) | AI may restyle the modal — new widths, new spacing scale, hard-coded colors instead of theme tokens — while adding the two new controls | Diff the modal component and confirm the dialog wrapper, `max-w-md`, `max-h-[80vh]`, `overflow-y-auto` list, per-row checkbox markup, button classes, and all `text-*`/`bg-*`/`border-*` theme tokens are unchanged |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation | Tenant data is isolated per-schema; queries must never span tenant boundaries | The duplicate-checksum lookup must stay inside the caller's tenant schema and additionally filter on `tenant_id`; no cross-tenant or cross-schema checksum query is permitted | Read the lookup SQL in `upload_document`; run `tests/test_document_content_hash.py::TestDuplicateIdentification::test_duplicate_detection_does_not_cross_tenants` |
| ADR-002 – ADR-010 | Base-model strategy, model-serving topology, OpenSpec governance, agent boundaries, training infra, chatbot architecture, base-model-as-default, sysadmin hyperparameters, per-entity-type dataset threshold | None constrain document hashing or a portal selection control | N/A |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: `TestUploadPersistsChecksum::test_upload_returns_and_stores_the_checksum` passed — response `checksum` and stored column both equal `hashlib.sha256(bytes).hexdigest()`
- [x] Scenario 2: `TestContentHashDeterminism` (4 tests) passed — same bytes → same digest, 64-char lowercase hex matching `hashlib.sha256`, different bytes → different digest, no filename input path
- [x] Scenario 3: `test_identical_content_under_a_different_filename_is_linked` and `test_a_third_copy_points_at_the_original` passed — `original.pdf` / `renamed-copy.pdf` share a checksum, second reports `duplicate_of` = first id, third also points at the original (not the second)
- [x] Scenario 4: `test_different_content_is_not_a_duplicate` passed
- [x] Scenario 5: `test_duplicate_upload_does_not_modify_the_original` passed — original stays `processed` with its own filename; new document is a distinct `pending` record
- [x] Scenario 6: `test_duplicate_detection_does_not_cross_tenants` passed — two separately provisioned tenant schemas, identical bytes, `duplicate_of is None`
- [x] Scenario 7: `test_soft_deleted_document_is_not_reported_as_a_duplicate` passed
- [x] Scenario 8: `test_document_metadata_exposes_the_checksum` passed
- [x] Scenarios 9–14: `BatchDocumentSelectModal.test.tsx` — 13 tests passed (6 pre-existing + 7 new bulk-selection tests)

### Structural Evidence

- [x] Code review completed — implementation matches design.md; the only deviation from the original plan is documented below under Notes (pre-existing test-fixture drift repaired)
- [x] ADR-001 compliance confirmed (Section 3) — lookup is schema-qualified and `tenant_id`-filtered
- [x] No undocumented architectural patterns introduced — migration `034` reuses the `DO $$` tenant-schema loop pattern established by migration `023`
- [x] No AI-invented fields, endpoints, or behaviours — `checksum` is the pre-existing column; `duplicate_of` is the only new response field and is specified

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — migration `034` contains only `CREATE INDEX` / `DROP INDEX`; no `ADD COLUMN` anywhere in this change's diff
- [x] Risk 2 mitigation confirmed — index is non-unique; `upload_document` issues one `SELECT` and one `INSERT` and no `UPDATE`/`DELETE` against `documents`; `test_duplicate_upload_does_not_modify_the_original` asserts the original is untouched
- [x] Risk 3 mitigation confirmed — lookup is `SELECT id FROM {_schema(tenant_id)}.documents WHERE tenant_id = :tid AND checksum = :checksum AND status != 'deleted'`
- [x] Risk 4 mitigation confirmed — the modal's only selection state is `useState<Set<string>>`; `allSelected` is derived per render; both `toggle()` (early-returns on `already_extracted`) and `toggleAll()` (iterates `selectable`) exclude disabled ids; `handleConfirm` submits `selectedIds`, itself derived from `selectable`
- [x] Risk 5 mitigation confirmed — `extraction.py` and `worker.py` are not in this change's diff; `tests/test_batch_extraction.py` + `tests/test_batch_extraction_eligibility.py` → 15 passed
- [x] Risk 6 mitigation confirmed — dialog wrapper, `max-w-md`, `max-h-[80vh]`, `overflow-y-auto` list, per-row `<label>`/`<input type="checkbox">` markup, and both button class strings are byte-identical to the previous version; the two new controls reuse the same row classes and theme tokens; the footer gained only `items-center justify-between` to seat the count line beside the existing button group

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_document_content_hash.py -q` → `12 passed in 3.64s` | 1–8 | Claude | 2026-08-10 |
| 2 | Functional | `pytest tests/test_document_ingestion.py tests/test_document_content_hash.py -q` → `29 passed in 8.92s` | 1–8 + ingestion regression | Claude | 2026-08-10 |
| 3 | Functional | `vitest run src/components/extractions/BatchDocumentSelectModal.test.tsx src/components/extractions/BatchRunsTab.test.tsx` → `2 passed (21 tests)` | 9–14 + modal/tab regression | Claude | 2026-08-10 |
| 4 | Edge Case | `pytest tests/test_batch_extraction.py tests/test_batch_extraction_eligibility.py -q` → `15 passed in 3.58s`, with neither `extraction.py` nor `worker.py` modified | Risk 5 | Claude | 2026-08-10 |
| 5 | Structural | Migration `034`'s exact SQL executed against `ner_test` (`CREATE INDEX` on `tenant_template.documents` plus the `DO $$` tenant-schema loop) → both statements succeeded, `pg_indexes` confirmed `tenant_template / ix_documents_checksum`; the throwaway verification schema was dropped afterwards | Risk 1, migration correctness | Claude | 2026-08-10 |
| 6 | Structural | Pre-existing test-fixture drift found and repaired in `tests/test_document_ingestion.py`: the fixture `documents` DDL was missing `uploaded_by` (added to the live schema by migration `030`), so 9 tests failed with `column "uploaded_by" of relation "documents" does not exist` before this change was made; three direct-INSERT statements also predated the `uploaded_by` ownership filter in `list_documents` and returned 0 rows for a `business_user`. Added the column to the fixture DDL and `uploaded_by = 'test-user'` to those inserts | Ingestion regression baseline | Claude | 2026-08-10 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** document-content-hash-and-batch-select-all
**Proposal:** `openspec/changes/document-content-hash-and-batch-select-all/proposal.md`
**Spec files reviewed:**
- specs/document-ingestion/spec.md
- specs/portal-extraction-page/spec.md

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

- Migration `034` has not yet been applied to the live `ner_dev` database — its SQL was verified against `ner_test` only. Run `alembic upgrade head` before the duplicate lookup is exercised at any meaningful volume; without the index the lookup still returns correct results, just via a sequential scan.
- Documents uploaded before this change have `checksum IS NULL` and will never be reported as duplicates. A backfill is deliberately out of scope (see proposal § Open Questions).
