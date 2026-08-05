# Verification Plan

**Change:** batch-extraction-document-selection
**Generated:** 2026-07-31
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | List documents eligible for batch extraction | Eligible documents list marks already-extracted documents | Given a tenant with one document already extracted under the active model version and one not, when a Tenant Admin GETs `/api/v1/extract-batch/eligible-documents`, then the response is 200 and the already-extracted document has `already_extracted: true` while the other has `already_extracted: false` | tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsMarksAlreadyExtracted | - [x] |
| 2 | extraction-service | List documents eligible for batch extraction | Eligible documents list excludes non-processed documents | Given a tenant with one `processed` and one `pending` document, when a Tenant Admin GETs `/api/v1/extract-batch/eligible-documents`, then only the `processed` document appears in the response | tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsExcludesNonProcessed | - [x] |
| 3 | extraction-service | List documents eligible for batch extraction | Eligible documents list as non-admin | Given an authenticated `business_user`, when they GET `/api/v1/extract-batch/eligible-documents`, then the response is 200 | tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsNonAdmin | - [x] |
| 4 | extraction-service | List documents eligible for batch extraction | A document re-extracted under a new model version becomes eligible again | Given a document extracted only under a since-superseded model version, when a Tenant Admin GETs the eligible-documents endpoint after a new model is promoted, then that document has `already_extracted: false` | tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsReeligibleAfterPromotion | - [x] |
| 5 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Batch Runs tab lists existing runs | Given the user opens or reloads the Batch Runs tab, when it mounts, then `GET /api/v1/extract-batch` is called and each returned run appears as a card, with the most recent run selected by default | src/portal/src/components/extractions/BatchRunsTab.test.tsx (Test 7) | - [x] |
| 6 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Run history persists across page reload | Given a previously completed batch run, when the tab mounts after reload, then the run appears in the list and the empty state is not shown | src/portal/src/components/extractions/BatchRunsTab.test.tsx (Test 7) | - [x] |
| 7 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Selecting a batch run shows detail | Given multiple run cards are visible, when the user clicks one, then it gets a primary border and its stats appear in the right panel | src/portal/src/components/extractions/BatchRunsTab.test.tsx (Test 8) | - [x] |
| 8 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Clicking "New batch run" opens the document-selection modal | Given the Batch Runs tab is active, when the user clicks "New batch run", then the modal opens, `GET /api/v1/extract-batch/eligible-documents` is called, and no `POST /api/v1/extract-batch` is sent yet | src/portal/src/components/extractions/BatchDocumentSelectModal.test.tsx (fetches eligible documents when opened) | - [x] |
| 9 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Already-extracted documents are disabled in the modal | Given the modal is open with a document whose `already_extracted` is `true`, when that row renders, then its checkbox is disabled and a label indicates it was already processed | src/portal/src/components/extractions/BatchDocumentSelectModal.test.tsx (disables the checkbox for already-extracted documents and labels them) | - [x] |
| 10 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Confirm is disabled with no selection | Given the modal is open with no checkboxes checked, when the user views it, then "Run extraction" is disabled | src/portal/src/components/extractions/BatchDocumentSelectModal.test.tsx (disables confirm when nothing is selected) | - [x] |
| 11 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Triggering a new batch run with selected documents | Given the modal is open with two not-yet-extracted documents checked, when the user clicks "Run extraction", then `POST /api/v1/extract-batch?documentIds=<the two ids>` is sent, the modal closes, and the new run appears at the top of the list, selected | src/portal/src/components/extractions/BatchRunsTab.test.tsx (Test 9); BatchDocumentSelectModal.test.tsx (enables confirm and submits only checked, not-yet-extracted ids) | - [x] |
| 12 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Canceling the modal sends no request | Given the modal is open with some documents checked, when the user clicks cancel/close, then the modal closes and no `POST /api/v1/extract-batch` request is sent | src/portal/src/components/extractions/BatchDocumentSelectModal.test.tsx (cancel closes without calling onConfirm) | - [x] |
| 13 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | In-progress runs poll for status updates | Given one or more runs are "running" or "queued", when the tab is mounted, then it polls `GET /api/v1/extract-batch/{run_id}` every 3 seconds until each run reaches a terminal state | src/portal/src/hooks/use-batch-runs.ts polling logic (unchanged by this change) | - [x] |
| 14 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Status pills use correct visual styles | Given runs with various statuses, when the list renders, then completed/running-queued/failed use good/warn/bad color tokens respectively | src/portal/src/components/extractions/BatchRunsTab.test.tsx (Test 11) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Shared "already extracted" lookup (Decision 2) | AI may implement the new endpoint's already-extracted check with its own SQL instead of reusing/extracting the existing `_get_already_extracted` logic from `worker.py`, causing the modal and the actual worker skip behavior to silently diverge | Diff the new endpoint's query against `worker.py`'s idempotency query (or confirm both call one shared `entity_store.py` function) — confirm document_id + model_version matching logic is identical, not re-derived |
| 2 | Active model version resolution | AI may invent a different way of resolving "current active model version" for the new endpoint instead of reusing `_get_active_model_version` (worker.py:105), producing eligibility results inconsistent with what a batch run would actually skip | Confirm the new endpoint calls the same active-model-version resolution function used by the worker; test with a demoted/no-promoted-model tenant to confirm version "0" fallback matches |
| 3 | Enforcement boundary (Decision 3) | AI may add unneeded server-side 422 rejection of already-extracted `documentIds` in `trigger_batch_extraction`, unintentionally changing the documented "explicit documentIds bypasses purpose filtering" contract for non-UI callers | Confirm `POST /api/v1/extract-batch` behavior for explicit `documentIds` is unchanged from the existing extraction-service spec — no new validation/rejection added there |
| 4 | Modal disabled-checkbox implementation | AI may implement "disabled" as merely visually greyed-out (still checkable/submittable) rather than genuinely excluded from the selection and submission, letting a user submit an already-extracted document anyway | Manually attempt to check a disabled row in the browser and confirm no interaction is possible; confirm the submitted `documentIds` never include an `already_extracted: true` document even via devtools tampering |
| 5 | `triggerBatch` signature change | AI may leave a caller of the old no-arg `triggerBatch()` (e.g. `BaseModelConfirmDialog` confirm flow) uncalled or calling it with stale semantics, breaking the existing base-model confirmation flow | Trace every call site of `triggerBatch` after the change and confirm each supplies the selected `documentIds` from the modal, including the base-model-confirm path |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

No constraining ADRs.

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| N/A | design.md identifies no in-force ADR (001–008) as constraining this change | None | N/A |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: API test output showing `GET /api/v1/extract-batch/eligible-documents` returns correct `already_extracted` flags for a mixed already-extracted/not-extracted document set (`tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsMarksAlreadyExtracted`, passed)
- [x] Scenario 2: API test output showing non-`processed` documents excluded from the eligible list (`tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsExcludesNonProcessed`, passed)
- [x] Scenario 3: API test output showing 200 for a `business_user` role request (`tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsNonAdmin`, passed)
- [x] Scenario 4: API test output showing a document becomes eligible again after model version promotion (`tests/test_batch_extraction_eligibility.py::TestEligibleDocumentsReeligibleAfterPromotion`, passed)
- [x] Scenario 5: Component test showing the Batch Runs tab lists existing runs with the most recent selected (`BatchRunsTab.test.tsx`, Test 7, passed)
- [x] Scenario 6: Covered by the same run-list rendering path exercised in Test 7 — no reload-specific frontend behavior changed by this change
- [x] Scenario 7: Component test showing selecting a run card updates the detail panel (`BatchRunsTab.test.tsx`, Test 8, passed)
- [x] Scenario 8: Component test showing "New batch run" opens the modal and calls `useEligibleDocuments(true)` (`BatchDocumentSelectModal.test.tsx`, "fetches eligible documents when opened", passed)
- [x] Scenario 9: Component test showing already-extracted documents render disabled with a label (`BatchDocumentSelectModal.test.tsx`, "disables the checkbox for already-extracted documents and labels them", passed)
- [x] Scenario 10: Component test showing "Run extraction" is disabled with zero selections (`BatchDocumentSelectModal.test.tsx`, "disables confirm when nothing is selected", passed)
- [x] Scenario 11: Component test showing confirm calls `triggerBatch(["doc-1"])` with only the checked, not-yet-extracted ID and the new run is selected (`BatchRunsTab.test.tsx`, Test 9, passed; `BatchDocumentSelectModal.test.tsx`, "enables confirm and submits only checked, not-yet-extracted ids", passed)
- [x] Scenario 12: Component test showing cancel closes the modal with no `onConfirm`/POST call (`BatchDocumentSelectModal.test.tsx`, "cancel closes without calling onConfirm", passed)
- [x] Scenario 13: Polling logic lives entirely in `use-batch-runs.ts` and was not modified by this change; no regression risk
- [x] Scenario 14: Component test confirming status pill color tokens (`BatchRunsTab.test.tsx`, Test 11, passed)

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations), with one necessary correction: the endpoint path was changed from the proposal/design draft's `/api/v1/documents/eligible-for-extraction` to `/api/v1/extract-batch/eligible-documents` after discovering the portal's `authFetch` routes any `/api/v1/documents*` path directly to the document-service, bypassing the gateway/extraction-service entirely — all planning artifacts were updated to match
- [x] All ADR compliance steps in Section 3 confirmed ✓ (no constraining ADRs)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `get_already_extracted` now lives once in `src/extraction_service/services/entity_store.py`; `worker.py` and `extraction.py`'s new endpoint both import and call it, no duplicated SQL
- [x] Risk 2 mitigation confirmed — the new endpoint imports and calls `_get_active_model_version` from `worker.py` directly (same function, not re-derived); no-promoted-model fallback to `"0"` is unchanged
- [x] Risk 3 mitigation confirmed — `trigger_batch_extraction` in `extraction.py` was not modified by this change; existing `tests/test_batch_extraction.py` purpose-scoping/explicit-`documentIds` tests still pass unchanged
- [x] Risk 4 mitigation confirmed — `BatchDocumentSelectModal`'s `toggle()` early-returns on `alreadyExtracted`, and the `disabled` HTML attribute prevents the checkbox from receiving click events; test "cannot select an already-extracted document even by clicking it" confirms `fireEvent.click` on the disabled checkbox leaves it unchecked
- [x] Risk 5 mitigation confirmed — traced both call sites: the direct "New batch run" click and the `BaseModelConfirmDialog` confirm path both now route through `BatchDocumentSelectModal`'s `onConfirm`, which calls `triggerBatch(documentIds)`; no remaining no-arg `triggerBatch()` call sites in `BatchRunsTab.tsx`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_batch_extraction_eligibility.py tests/test_batch_extraction.py -q` → `15 passed in 7.54s` | 1, 2, 3, 4 | Claude (opsx:apply) | 2026-07-31 |
| 2 | Functional | `vitest run src/components/extractions/BatchDocumentSelectModal.test.tsx src/components/extractions/BatchRunsTab.test.tsx` → `2 passed (14 tests)` | 5, 6, 7, 8, 9, 10, 11, 12, 14 | Claude (opsx:apply) | 2026-07-31 |
| 3 | Edge Case | Full portal `vitest run` (85 files) → 7 failing files, all pre-existing and confined to `src/components/annotation/*.test.tsx` (jsdom `localStorage` env issue unrelated to this change); all extraction/batch-run files pass | 5–14 (regression check) | Claude (opsx:apply) | 2026-07-31 |
| 4 | Structural | Manual trace of `resolveUrl()` in `src/portal/src/lib/auth-fetch.ts` confirming `/api/v1/documents*` bypasses the gateway and hits `DOCUMENT_URL` directly — motivated the endpoint path correction to `/api/v1/extract-batch/eligible-documents` | 1–12 (routing correctness) | Claude (opsx:apply) | 2026-07-31 |
| 5 | Functional | Live smoke test after `docker compose up -d --build`: `GET http://localhost:8000/api/v1/extract-batch/eligible-documents` through the gateway with a real demo-tenant JWT → `HTTP 200` with seeded documents, all `already_extracted: false`; confirmed `/extract-batch` list (200) and `/extract-batch/{run_id}` (404 on bogus id) still resolve correctly, i.e. no FastAPI route-ordering collision with the new static path | 1, 8 (live routing + endpoint) | Claude (opsx:apply) | 2026-07-31 |
| 6 | Structural | Found and fixed a real deployment gap: `docker-compose.yml`'s `extraction_service` service had no `NER_DATABASE_URL_SYNC` env var (only `celery_worker_extraction` did), so the new endpoint's reused sync-engine lookup (`get_already_extracted`, `_get_active_model_version`) 500'd with `connection to server at "localhost" ... Connection refused` on first live test. Added `NER_DATABASE_URL_SYNC` to the `extraction_service` block in `docker-compose.yml`, rebuilt, retested → 200 | 1 (deployment correctness) | Claude (opsx:apply) | 2026-07-31 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** batch-extraction-document-selection
**Proposal:** `openspec/changes/batch-extraction-document-selection/proposal.md`
**Spec files reviewed:**
- specs/extraction-service/spec.md
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
