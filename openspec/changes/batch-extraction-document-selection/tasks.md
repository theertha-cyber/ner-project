## 1. Backend — shared eligibility lookup

- [x] 1.1 Move `_get_already_extracted(tenant_id, doc_ids, model_version)` from `src/extraction_service/worker.py` into `src/extraction_service/services/entity_store.py` as a shared function; update `worker.py` to import and call it.
- [x] 1.2 Add a helper to resolve currently-`processed` document IDs for a tenant (reuse existing query pattern from `trigger_batch_extraction` in `extraction.py`).

## 2. Backend — eligible-documents endpoint

- [x] 2.1 Add `GET /api/v1/extract-batch/eligible-documents` in `src/extraction_service/api/v1/extraction.py`, resolving tenant_id/role the same way as `trigger_batch_extraction` (tenant_admin/business_user allowed).
- [x] 2.2 In the endpoint, fetch `processed` documents, resolve the active model version (reuse `_get_active_model_version` from `worker.py`), and compute `already_extracted` via the shared lookup from 1.1.
- [x] 2.3 Add response schema (e.g. `EligibleDocument`, `EligibleDocumentListResponse`) in `src/extraction_service/api/v1/schemas.py` with `id`, `filename`/identifying fields, and `already_extracted: bool`.
- [x] 2.4 Verification: write API test(s) covering spec rows 1–4 (already-extracted flagging, non-processed exclusion, non-admin 200, re-eligibility after model promotion) — record file name in verification.md § Spec Alignment for rows 1–4.

## 3. Frontend — types and hook changes

- [x] 3.1 Add `already_extracted` field to the eligible-document type in `src/portal/src/types/extraction.ts` (or `documents.ts`), matching the new endpoint response.
- [x] 3.2 Add a hook/query (e.g. `useEligibleDocuments`) that calls `GET /api/v1/extract-batch/eligible-documents`, following the pattern in `src/portal/src/hooks/use-documents.ts`.
- [x] 3.3 Change `useBatchRuns().triggerBatch` in `src/portal/src/hooks/use-batch-runs.ts` to accept `documentIds: string[]` and POST `/api/v1/extract-batch?documentIds=<comma-separated>` instead of the no-arg call.

## 4. Frontend — document-selection modal

- [x] 4.1 Create a new modal component (e.g. `src/portal/src/components/extractions/BatchDocumentSelectModal.tsx`) that fetches eligible documents on open and lists them with checkboxes.
- [x] 4.2 Render `already_extracted: true` rows disabled/unselectable with a label indicating they were already processed; ensure their IDs can never enter the selected set (not just visually disabled).
- [x] 4.3 Disable the "Run extraction" confirm action when zero documents are checked.
- [x] 4.4 Wire confirm to call `triggerBatch(selectedIds)`, close the modal, and rely on existing `BatchRunsTab.tsx` logic to select the new run.
- [x] 4.5 Wire cancel/close to dismiss the modal without any network call.
- [x] 4.6 Verification: write component/E2E test(s) covering spec rows 8–12 (modal open on "New batch run" click, disabled already-extracted rows, confirm-disabled-when-empty, confirm submits selected IDs, cancel sends nothing) — record file names in verification.md for rows 8–12.

## 5. Frontend — wire modal into BatchRunsTab

- [x] 5.1 In `src/portal/src/components/extractions/BatchRunsTab.tsx`, replace the direct `handleNewBatchRun` trigger with opening `BatchDocumentSelectModal`.
- [x] 5.2 Preserve the existing base-model confirmation flow (`BaseModelConfirmDialog`) — confirm it still runs before/around the document-selection modal rather than being bypassed, and that it ultimately calls `triggerBatch(selectedIds)` with the ids chosen in the new modal.
- [x] 5.3 Verification: confirm existing scenarios (run list rendering, reload persistence, run selection, polling, status pill colors — spec rows 5–7, 13–14) still pass unchanged; record test file names in verification.md for rows 5–7, 13–14.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 6.6 Run `openspec validate batch-extraction-document-selection --type change --strict` and confirm it exits clean before archive.
