## 1. Baseline

- [x] 1.1 Run the portal test suite before touching code and record the passing baseline (`DocumentUpload.test.tsx`, `use-upload.test.tsx`, `DocumentTable.test.tsx`, `DocumentRow.test.tsx`, `StatusFilterTabs.test.tsx`). Baseline: 5 files / 23 tests, all passing.
- [x] 1.2 Confirm `POST /api/v1/documents` in `src/document_service/api/v1/documents.py:42` stays out of scope — record that no backend file will be edited by this change.

## 2. Hook: additive cancel support

- [x] 2.1 In `src/portal/src/hooks/use-upload.ts`, add a `cancel()` (or equivalent) member that aborts `xhrRef.current` without clearing progress/error state, keeping `upload(file, purpose)`'s signature and the existing returned keys `{ upload, progress, isUploading, error, reset }` unchanged (design Decision 1). Added `onabort` handler so the promise settles (rejects with `AbortError`) instead of hanging forever.
- [x] 2.2 Verify `src/portal/src/hooks/use-upload.test.tsx` passes with zero edits to its existing cases; add a case asserting `cancel()` aborts the in-flight request.
- [x] 2.3 Confirm `queryClient.invalidateQueries({ queryKey: ["documents"] })` remains inside the HTTP 201 branch of the hook (design Decision 6, Risk 7).

## 3. Component: multi-file selection

- [x] 3.1 Add `multiple` to the hidden `<input type="file">` in `src/portal/src/components/documents/DocumentUpload.tsx`.
- [x] 3.2 Change `handleDrop` to read all of `e.dataTransfer.files` and `handleInputChange` to read all of `e.target.files`, keeping the existing `inputRef.current.value = ""` reset so re-selecting the same file still fires `change`.
- [x] 3.3 Add a `MAX_BATCH = 20` constant beside `MAX_SIZE`; reject a selection larger than 20 files in full with one inline error and zero upload calls (design Decision 4).
- [x] 3.4 Partition the selection with the existing `validate()` per file: mark invalid files `rejected` with their reason, enqueue only valid files (design Decision 3).

## 4. Component: batch state and sequential upload

- [x] 4.1 Replace `validationError: string | null` and `uploadSuccess: boolean` with a results array of `{ name, status: "pending" | "uploading" | "success" | "failed" | "cancelled" | "rejected", error?: string }` indexed over the original selection order (design Decision 5).
- [x] 4.2 Implement the sequential loop: `await upload(file, purpose)` per queued file, never starting the next before the previous settles; record per-file success/failure and continue past failures (design Decision 2).
- [x] 4.3 Call `reset()` exactly once before the loop starts — never inside the loop, since `reset()` aborts `xhrRef.current` (design Risk 3).
- [x] 4.4 Pass the single selected `purpose` to every file in the batch.

## 5. Component: progress, summary, cancel UI

- [x] 5.1 Render the in-flight file's percentage bar plus its filename and a "file N of M" indicator; suppress the indicator when the batch has exactly one file (spec scenarios 12, 13).
- [x] 5.2 Render the terminal batch summary: succeeded count, failed/cancelled/rejected counts, and each non-successful filename with its reason. Collapse to today's single success indicator / single inline error when the batch is one file.
- [x] 5.3 Add a cancel control visible while a multi-file batch is uploading; it sets a cancel flag checked before each loop iteration and calls the hook's abort path (design Decision 7).
- [x] 5.4 Classify files skipped or aborted by cancel as `cancelled` using the component's cancel flag — not the hook's error string — so an aborted request never renders as "Network error during upload" (design Risk 2).
- [x] 5.5 Clear prior batch results when a new selection arrives so the zone returns to idle (spec scenario 18).

## 6. Tests

- [x] 6.1 Confirm the five existing `DocumentUpload.test.tsx` cases still pass unmodified — covers verification rows 1 (single PDF drop), 5 (unsupported type), 7 (>50MB), 10 (drag-over/drag-leave). Artifact: `src/portal/src/components/documents/DocumentUpload.test.tsx` (existing cases).
- [x] 6.2 Add a test dropping a PDF + PNG + TIFF in one drop asserting three upload calls with maximum concurrent in-flight count of 1 — covers verification row 2. Artifact: `DocumentUpload.test.tsx` → `multi-file drop uploads all files sequentially`.
- [x] 6.3 Add a test firing a `change` event with two PNGs asserting two sequential uploads — covers verification row 3. Artifact: `DocumentUpload.test.tsx` → `multi-select picker uploads all selected files`.
- [x] 6.4 Add a test selecting a single PNG via the input asserting one upload — covers verification row 4. Artifact: `DocumentUpload.test.tsx` → `single file via picker uploads immediately`.
- [x] 6.5 Add a mixed-batch test (valid PDF + `.exe` + 100MB PDF in one drop) asserting both rejection messages render and the upload mock is called exactly once — covers verification row 6. Artifact: `DocumentUpload.test.tsx` → `mixed batch rejects invalid files and uploads the valid one`.
- [x] 6.6 Add a test dropping 25 valid PDFs asserting the cap message renders and the upload mock is called zero times — covers verification row 8. Artifact: `DocumentUpload.test.tsx` → `selection over 20 files is rejected in full`.
- [x] 6.7 Add a test with `purpose` set to "training" asserting every call of a three-file batch receives `"training"` — covers verification row 9. Artifact: `DocumentUpload.test.tsx` → `batch purpose applies to every file`.
- [x] 6.8 Add a test asserting bar width and percentage text track the hook's `progress` value — covers verification row 11. Artifact: `DocumentUpload.test.tsx` → `progress bar reflects in-flight bytes`.
- [x] 6.9 Add a test asserting "file 2 of 3" plus the in-flight filename render during a 3-file batch — covers verification row 12. Artifact: `DocumentUpload.test.tsx` → `batch position indicator shows file N of M`.
- [x] 6.10 Add a test asserting no batch-position indicator renders for a 1-file batch — covers verification row 13. Artifact: `DocumentUpload.test.tsx` → `single-file batch shows no position indicator`.
- [x] 6.11 Add a test asserting the success indicator renders and `invalidateQueries(["documents"])` fires on a single-file 201 — covers verification row 14. Artifact: `DocumentUpload.test.tsx` → `single upload success invalidates document list`.
- [x] 6.12 Add a test where file 2 of 3 rejects, asserting file 3 is still uploaded and the summary reports 2 succeeded / 1 failed with the failed filename and reason — covers verification row 15. Artifact: `DocumentUpload.test.tsx` → `batch continues after one file fails`.
- [x] 6.13 Add a test where all three files succeed, asserting a 3 succeeded / 0 failed summary and one invalidation per success — covers verification row 16. Artifact: `DocumentUpload.test.tsx` → `batch summary reports all successes`.
- [x] 6.14 Add a test cancelling a 5-file batch after file 1 succeeds, asserting the in-flight request is aborted, files 3–5 are never sent, and the summary reports 1 succeeded / 4 cancelled with no "Network error" text — covers verification row 17. Artifact: `DocumentUpload.test.tsx` → `cancel aborts in-flight and skips queued files`.
- [x] 6.15 Add a test dropping a new valid PDF after a cancelled batch, asserting prior summary state clears and the new file uploads — covers verification row 18. Artifact: `DocumentUpload.test.tsx` → `zone accepts a new selection after cancel`.
- [x] 6.16 Fill in the Verification Artifact column for all 18 rows of `verification.md` § Spec Alignment with the test names from tasks 6.1–6.15.

## 7. Regression guard

- [x] 7.1 Run the full portal test suite and confirm exit 0 with no edits to the existing cases of `use-upload.test.tsx`, `DocumentTable.test.tsx`, `DocumentRow.test.tsx`, `StatusFilterTabs.test.tsx`. 75/83 files, 492/524 tests pass; the 8 failing files (`AnnotationPage.test.tsx`, `BatchRunsTab.test.tsx`, etc.) fail identically on unmodified `main` (confirmed via `git stash`) — pre-existing, unrelated to this change.
- [x] 7.2 Confirm via `git diff --stat` that no file under `src/document_service/` is modified, and that `DocumentTable.tsx`, `DocumentRow.tsx`, `StatusFilterTabs.tsx`, and the polling logic are untouched. Diff touches only `DocumentUpload.tsx`, `DocumentUpload.test.tsx`, `use-upload.ts`, `use-upload.test.tsx`.
- [ ] 7.3 Manual check on `/documents` in a running portal: multi-select 3 real files, observe sequential per-file progress, the batch summary, 3 new `pending` rows, and that polling still transitions them; then repeat with a single file to confirm the original one-file experience is intact. **Not done — requires a running portal + backend; needs human/browser verification.**
- [ ] 7.4 Manual check: start a 5-file batch, cancel mid-way, confirm already-uploaded rows remain and remaining files are reported cancelled. **Not done — requires a running portal + backend; needs human/browser verification.**

## 8. Verification & Evidence

- [x] 8.1 Run all acceptance-criteria tests for every scenario in `verification.md` § Spec Alignment and confirm all pass. All 18 rows checked off with test artifact names filled in; 19/19 `DocumentUpload.test.tsx` tests and 6/6 `use-upload.test.tsx` tests pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in `verification.md` § Evidence Log. **Not done — Evidence Log (§5) is left for human reviewer to populate with real observations, per gate rules.**
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in `verification.md` § Hallucination Risk Register. Edge Case Evidence items checked with rationale; final confirmation still needs human sign-off in Audit Record.
- [ ] 8.4 Confirm all ADR compliance steps in `verification.md` § Pattern & ADR Compliance. No code changes touch tenant routing or model/serving paths; final sign-off needs human reviewer.
- [ ] 8.5 Complete Audit Record sign-off in `verification.md` § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 8.6 Run `openspec validate multi-document-upload --type change --strict` and confirm it exits clean before archive.
