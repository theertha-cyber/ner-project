# Verification Plan

**Change:** multi-document-upload
**Generated:** 2026-07-28
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-documents | Document Upload Zone (MODIFIED) | Drag a single valid PDF onto the zone | Given `/documents` is open, when one PDF is dropped, then exactly one `POST /api/v1/documents` multipart request is sent and one row appears with `status: "pending"` | `DocumentUpload.test.tsx` → `shows inline error for unsupported file type on drop` sibling case (single-drop path, pre-existing) | - [x] |
| 2 | portal-documents | Document Upload Zone (MODIFIED) | Drag three valid files onto the zone | Given `/documents` is open, when a PDF + PNG + TIFF are dropped in one drop, then three `POST /api/v1/documents` requests are sent with never more than one in flight, and three `pending` rows appear | `DocumentUpload.test.tsx` → `multi-file drop uploads all files sequentially` | - [x] |
| 3 | portal-documents | Document Upload Zone (MODIFIED) | Click to browse and multi-select files | Given the picker is open, when two PNGs are selected, then both upload sequentially and two `pending` rows appear | `DocumentUpload.test.tsx` → `multi-select picker uploads all selected files` | - [x] |
| 4 | portal-documents | Document Upload Zone (MODIFIED) | Click to browse and select a single valid PNG | Given the picker is open, when one PNG is selected, then it uploads immediately and one `pending` row appears | `DocumentUpload.test.tsx` → `single file via picker uploads immediately` | - [x] |
| 5 | portal-documents | Document Upload Zone (MODIFIED) | Drop an unsupported file type | Given `/documents` is open, when a `.exe` is dropped, then an inline error naming the unsupported type is shown and zero API calls are made | `DocumentUpload.test.tsx` → `shows inline error for unsupported file type on drop` (pre-existing) | - [x] |
| 6 | portal-documents | Document Upload Zone (MODIFIED) | Drop a mixed batch of valid and invalid files | Given `/documents` is open, when one valid PDF + one `.exe` + one 100MB PDF are dropped together, then the `.exe` shows "not supported", the 100MB file shows "exceeds the 50MB limit", the valid PDF still uploads, and exactly one API call is made | `DocumentUpload.test.tsx` → `mixed batch rejects invalid files and uploads the valid one` | - [x] |
| 7 | portal-documents | Document Upload Zone (MODIFIED) | Drop a file exceeding 50MB | Given `/documents` is open, when a 100MB file is dropped, then an inline "exceeds the 50MB limit" error is shown and zero API calls are made | `DocumentUpload.test.tsx` → `shows inline error for oversized file on drop` (pre-existing) | - [x] |
| 8 | portal-documents | Document Upload Zone (MODIFIED) | Selection exceeds the 20-file cap | Given `/documents` is open, when 25 valid PDFs are dropped in one drop, then an inline error stating the 20-file maximum is shown and zero API calls are made for any file in the selection | `DocumentUpload.test.tsx` → `selection over 20 files is rejected in full` | - [x] |
| 9 | portal-documents | Document Upload Zone (MODIFIED) | Purpose applies to every file in the batch | Given `purpose` is set to "training", when three valid files are dropped, then every request's form data carries `purpose: "training"` | `DocumentUpload.test.tsx` → `batch purpose applies to every file` | - [x] |
| 10 | portal-documents | Document Upload Zone (MODIFIED) | Drag-over visual state change | Given the zone is idle, when a file is dragged over it, then the highlighted border state is applied, and it returns to idle on drag-leave or drop | `DocumentUpload.test.tsx` → `shows highlighted state on drag over` / `resets visual state on drag leave` (pre-existing) | - [x] |
| 11 | portal-documents | Upload Progress Bar (MODIFIED) | Upload progress updates in real time | Given a file is uploading, when `upload.onprogress` fires, then the bar width and percentage text reflect `(loaded / total) * 100` | `DocumentUpload.test.tsx` → `progress bar reflects in-flight bytes`; `use-upload.test.tsx` → `sets progress via onprogress event` (pre-existing) | - [x] |
| 12 | portal-documents | Upload Progress Bar (MODIFIED) | Batch position is shown during a multi-file upload | Given a 3-file batch with file 2 in flight, when the progress area renders, then the in-flight filename and a "file 2 of 3" indicator are shown and the bar reflects only file 2's bytes | `DocumentUpload.test.tsx` → `batch position indicator shows file N of M` | - [x] |
| 13 | portal-documents | Upload Progress Bar (MODIFIED) | Single-file upload shows no batch position | Given a 1-file batch is uploading, when the progress area renders, then bar and percentage are shown and no "file N of M" indicator is present | `DocumentUpload.test.tsx` → `single-file batch shows no position indicator` | - [x] |
| 14 | portal-documents | Upload Progress Bar (MODIFIED) | Upload completes | Given a single-file upload reaches 100%, when the server responds HTTP 201, then the bar is replaced by a success indicator and the `["documents"]` query is invalidated | `DocumentUpload.test.tsx` → `single upload success invalidates document list` | - [x] |
| 15 | portal-documents | Upload Progress Bar (MODIFIED) | One file fails mid-batch | Given a 3-file batch, when file 2 returns HTTP 500, then file 3 is still uploaded and the summary reports 2 succeeded / 1 failed with file 2's name and the server's reason | `DocumentUpload.test.tsx` → `batch continues after one file fails` | - [x] |
| 16 | portal-documents | Upload Progress Bar (MODIFIED) | Batch summary after all files succeed | Given a 3-file batch, when all three return HTTP 201, then the summary reports 3 succeeded / 0 failed and the `["documents"]` query was invalidated once per success | `DocumentUpload.test.tsx` → `batch summary reports all successes` | - [x] |
| 17 | portal-documents | Cancel an In-Progress Batch (ADDED) | Cancel a batch after the first file succeeds | Given a 5-file batch where file 1 succeeded and file 2 is in flight, when cancel is activated, then file 2's request is aborted, files 3–5 are never sent, the summary reports 1 succeeded / 4 cancelled, and file 1's row remains in the table | `DocumentUpload.test.tsx` → `cancel aborts in-flight and skips queued files`; `use-upload.test.tsx` → `cancel aborts the in-flight request` | - [x] |
| 18 | portal-documents | Cancel an In-Progress Batch (ADDED) | Zone accepts a new selection after cancel | Given a batch was cancelled mid-upload, when a new valid PDF is dropped, then the prior batch's progress and summary state is cleared and the new file uploads normally | `DocumentUpload.test.tsx` → `zone accepts a new selection after cancel` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `useUpload` contract stability (design Decision 1) | Agent rewrites `useUpload` into a batch hook, changing the `upload(file, purpose)` signature or the meaning of `progress`/`isUploading`/`error`, silently breaking `src/portal/src/hooks/use-upload.test.tsx` or other callers | Diff `src/portal/src/hooks/use-upload.ts` — the exported `upload` signature and the returned keys `{ upload, progress, isUploading, error, reset }` must be unchanged; only additive members are allowed. Confirm `use-upload.test.tsx` passes with **zero edits to its existing cases** |
| 2 | Concurrency (design Decision 2) | Agent implements `Promise.all` / `map(upload)` over the queue instead of an `await`-per-file loop, producing parallel uploads that break progress attribution and the "no two requests in flight" assertion in Scenario 2 | Read the batch loop: it must `await` each `upload()` before starting the next. Confirm the multi-file test asserts request serialization (e.g. mock records overlapping in-flight count max = 1), not just the total call count |
| 3 | Partial-failure and partial-rejection paths (design Decision 3, Risk register) | Agent implements only the happy path — rejecting the whole selection when one file is invalid, or aborting the batch on the first HTTP failure — silently dropping the THEN clauses of Scenarios 6 and 15 | Verify Scenario 6 (mixed batch: valid file still uploads, exactly one API call) and Scenario 15 (file 3 uploads after file 2's 500) each have a dedicated failing-then-passing test, not merely an assertion on the error message |
| 4 | Cancel vs. network-error classification (design Risk 2) | `xhr.abort()` triggers the hook's `onerror` handler, so the agent labels a user cancel as "Network error during upload" and reports cancelled files as `failed` in the summary | Trigger a mid-batch cancel and read the summary: remaining files must be reported as **cancelled**, not failed, and no "Network error" text may appear. Confirm the component's cancel flag — not the hook's error string — drives the classification |
| 5 | `reset()` aborting the wrong request (design Risk 3) | Agent calls `reset()` inside the per-file loop; because `reset()` already calls `xhrRef.current?.abort()`, this aborts the request just started, producing intermittent failures that look like flakiness | Grep the batch loop for `reset(` — it must be called once before the loop begins, never per iteration. Confirm a 3-file batch test passes repeatedly (not just once) with all three succeeding |
| 6 | 20-file cap semantics (design Decision 4) | Agent silently truncates the selection to the first 20 files (or uploads 20 and warns) instead of rejecting the whole selection with zero API calls | Run the 25-file drop test and assert the mock upload function was called **zero** times. A non-zero call count means truncation was implemented instead of all-or-nothing rejection |
| 7 | Per-file query invalidation (design Decision 6) | Agent moves `queryClient.invalidateQueries({ queryKey: ["documents"] })` out of the hook to end-of-batch, changing hook behaviour (forbidden by Decision 1) and freezing the table during long batches | Confirm the invalidation call still lives in `use-upload.ts` inside the HTTP 201 branch, and that Scenario 16's test asserts one invalidation per successful file |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data isolated via separate database schemas | Every file's upload must traverse the normal authenticated request path so tenant schema routing is unchanged; batching must not introduce a bypass or a shared/cached request context | Confirm each queued file is sent as its own `XMLHttpRequest` to `POST /api/v1/documents` with an `Authorization: Bearer` header obtained from `getAccessToken()` at request time. Grep the diff for any new direct document-service call path or hardcoded tenant identifier — there must be none |
| ADR-004-openspec-governance | OpenSpec spec-driven development; specs are the source of truth | Implementation must satisfy the delta spec at `specs/portal-documents/spec.md` and introduce no upload behaviour absent from it | Walk all 18 rows of Section 1 against the implementation; confirm no additional user-visible upload behaviour (retry buttons, per-file purpose, folder recursion, chunked upload) was added beyond the delta spec |

> ADR-002, ADR-003, ADR-006, ADR-007, and ADR-008 concern model strategy, serving topology, training infrastructure, and chatbot/RAG architecture. No model, inference, or retrieval surface is touched by this change, so they impose no constraint. ADR-008 partially supersedes ADR-002; neither is in scope here.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (single valid PDF drop): test output showing the single-file drop case passing, with the upload mock called exactly once
- [x] Scenario 2 (three valid files dropped): test output showing three sequential upload calls with maximum concurrent in-flight count of 1
- [x] Scenario 3 (multi-select via picker): test output showing a two-file `change` event producing two sequential uploads
- [x] Scenario 4 (single PNG via picker): existing single-file picker test passing unmodified
- [x] Scenario 5 (unsupported type): test output asserting the inline "not supported" alert text and zero upload calls
- [x] Scenario 6 (mixed valid/invalid batch): test output asserting both rejection messages are rendered AND the upload mock was called exactly once
- [x] Scenario 7 (>50MB file): existing oversized-file test passing, asserting "exceeds" text and zero upload calls
- [x] Scenario 8 (25-file selection): test output asserting the 20-file cap message is rendered and the upload mock was called zero times
- [x] Scenario 9 (purpose applies to batch): test output (or captured request form data) showing `purpose: "training"` on every request of a three-file batch
- [x] Scenario 10 (drag-over visual state): existing drag-over and drag-leave class-assertion tests passing unmodified
- [x] Scenario 11 (progress updates): test or screenshot showing bar width and percentage text tracking `loaded/total`
- [x] Scenario 12 (batch position): test output or screenshot showing "file 2 of 3" plus the in-flight filename during a 3-file batch
- [x] Scenario 13 (no batch position for single file): test output asserting no "of" / "file N of M" indicator is rendered for a 1-file batch
- [x] Scenario 14 (single upload completes): test output showing the success indicator rendered and `invalidateQueries` called with `["documents"]`
- [x] Scenario 15 (one file fails mid-batch): test output showing the third upload still invoked after the second rejects, and a summary of 2 succeeded / 1 failed listing the failed filename and reason
- [x] Scenario 16 (all succeed): test output showing summary of 3 succeeded / 0 failed and one `invalidateQueries` call per success
- [x] Scenario 17 (cancel mid-batch): test output or screen recording showing abort of the in-flight request, zero requests for files 3–5, a 1 succeeded / 4 cancelled summary, and file 1's row still present
- [x] Scenario 18 (new selection after cancel): test output showing prior batch state cleared and a subsequent single-file drop uploading normally
- [x] Full portal test suite run (`DocumentUpload.test.tsx`, `use-upload.test.tsx`, `DocumentTable.test.tsx`, `DocumentRow.test.tsx`, `StatusFilterTabs.test.tsx`) passing with exit 0
- [ ] Manual browser check on `/documents`: multi-select 3 real files, observe sequential progress, batch summary, and 3 new table rows

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] `src/document_service/api/v1/documents.py` is unchanged in the diff (backend contract untouched) — confirmed via `git diff --stat`: only `DocumentUpload.tsx`, `DocumentUpload.test.tsx`, `use-upload.ts`, `use-upload.test.tsx` touched
- [x] `DocumentTable.tsx`, `DocumentRow.tsx`, `StatusFilterTabs.tsx`, and polling logic are unchanged in the diff — confirmed via same `git diff --stat`

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `useUpload`'s `upload(file, purpose)` signature and returned keys verified unchanged; `use-upload.test.tsx` existing cases pass without edits
- [x] Risk 2 mitigation confirmed — batch loop verified to `await` each upload; serialization asserted by test (`maxInFlight === 1`), not inferred
- [x] Risk 3 mitigation confirmed — mixed-batch and mid-batch-failure paths each have a dedicated test (`mixed batch rejects...`, `batch continues after one file fails`)
- [x] Risk 4 mitigation confirmed — `cancel aborts in-flight and skips queued files` test asserts summary shows "cancelled" and asserts no "Network error" text is present
- [x] Risk 5 mitigation confirmed — `reset()` called once per batch in `handleFiles`, not per loop iteration; multi-file batch tests pass reliably
- [x] Risk 6 mitigation confirmed — `selection over 20 files is rejected in full` asserts upload mock called zero times
- [x] Risk 7 mitigation confirmed — `invalidateQueries` still in `use-upload.ts` HTTP 201 branch (unchanged); `batch summary reports all successes` / `single upload success invalidates document list` tests pass

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** multi-document-upload
**Proposal:** `openspec/changes/multi-document-upload/proposal.md`
**Spec files reviewed:**
  - `specs/portal-documents/spec.md`

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
