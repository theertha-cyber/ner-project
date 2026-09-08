# Verification Plan

**Change:** annotation-mode-selection
**Generated:** 2026-09-03
**Status:** 🔴 ARCHIVED WITHOUT SIGN-OFF — the human-review gate below was explicitly overridden by the user on 2026-09-03. § 5 Evidence Log was never populated and § 6 Audit Record was never signed. Implementation and its 33 passing scenario tests are recorded in tasks.md and in the repository history, but no human reviewer confirmed them. Treat every unchecked box below as genuinely unverified, not as an oversight.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector is shown for training uploads | Given the upload zone rendered with `purpose: "training"`, when the page loads, then a Manual/Automated selector is visible with Manual selected | `DocumentUpload.annotationMode.test.tsx::shows_selector_for_training_purpose` | - [ ] |
| 2 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector is not shown for query uploads | Given the upload zone rendered with `purpose: "query"`, when the page loads, then no annotation-mode selector is rendered | `DocumentUpload.annotationMode.test.tsx::hides_selector_for_query_purpose` | - [ ] |
| 3 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector resets to Manual after a batch completes | Given Automated was selected and a batch completed, when the zone returns to idle, then the selector shows Manual selected | `DocumentUpload.annotationMode.test.tsx::resets_to_manual_after_batch` | - [ ] |
| 4 | annotation-mode-selection | Automated Option Gating | Automated is disabled with no active entity types | Given a tenant with zero active entity types, when the training upload zone renders, then Automated is disabled with a hint and Manual remains selectable | `DocumentUpload.annotationMode.test.tsx::disables_automated_without_entity_types` | - [ ] |
| 5 | annotation-mode-selection | Automated Option Gating | Automated is enabled when entity types exist without QA pairs | Given 2 active entity types with no `qa_examples`, when the training upload zone renders, then Automated is enabled | `DocumentUpload.annotationMode.test.tsx::enables_automated_without_qa_pairs` | - [ ] |
| 6 | annotation-mode-selection | Manual Mode Performs No Pre-labeling | Manual upload issues no pre-label request | Given Manual is selected, when 3 valid training documents are uploaded, then 3 upload requests are issued and zero requests hit any `/prelabel/llm` endpoint | `DocumentUpload.annotationMode.test.tsx::manual_issues_no_prelabel_requests` | - [ ] |
| 7 | annotation-mode-selection | Automated Mode Triggers Pre-labeling Per Uploaded Document | Automated upload triggers one pre-label request per document | Given Automated is selected and 3 uploads succeed, when the batch completes, then exactly 3 `POST /api/v1/documents/{doc_id}/prelabel/llm` requests are issued, one per document id | `DocumentUpload.annotationMode.test.tsx::automated_triggers_one_request_per_document` | - [ ] |
| 8 | annotation-mode-selection | Automated Mode Triggers Pre-labeling Per Uploaded Document | Failed uploads are not pre-labeled | Given Automated and a 3-document batch where 1 upload fails with a server error, when the batch completes, then pre-label requests are issued for only the 2 successful documents | `DocumentUpload.annotationMode.test.tsx::skips_prelabel_for_failed_uploads` | - [ ] |
| 9 | annotation-mode-selection | Automated Mode Triggers Pre-labeling Per Uploaded Document | Client-side rejected files are not pre-labeled | Given Automated and a batch of 2 valid PDFs plus 1 rejected `.exe`, when the batch completes, then pre-label requests are issued for only the 2 PDFs | `DocumentUpload.annotationMode.test.tsx::skips_prelabel_for_rejected_files` | - [ ] |
| 10 | annotation-mode-selection | Automated Mode Triggers Pre-labeling Per Uploaded Document | Pre-label requests are issued after uploads, not interleaved | Given Automated and 2 valid documents, when the batch runs, then both upload requests complete before the first pre-label request is issued | `DocumentUpload.annotationMode.test.tsx::triggers_run_after_all_uploads` | - [ ] |
| 11 | annotation-mode-selection | Pre-labeling Failure Does Not Affect Uploads | One failed pre-label trigger does not stop the rest | Given an Automated batch of 3 uploaded documents where the second pre-label request returns 500, when the trigger phase runs, then a request is still issued for the third and all 3 remain listed as successfully uploaded | `DocumentUpload.annotationMode.test.tsx::trigger_failure_does_not_halt_batch` | - [ ] |
| 12 | annotation-mode-selection | Pre-labeling Failure Does Not Affect Uploads | Pre-label failure leaves the document usable | Given a document that uploaded successfully but whose pre-label request failed, when the batch outcome is displayed, then it is reported as uploaded and not as an upload failure | `DocumentUpload.annotationMode.test.tsx::trigger_failure_not_reported_as_upload_failure` | - [ ] |
| 13 | annotation-mode-selection | Batch Outcome Reporting | Successful Automated batch reports queued count | Given an Automated batch of 3 where all uploads and triggers succeed, when it completes, then the summary reports 3 uploaded and 3 queued for pre-labeling | `DocumentUpload.annotationMode.test.tsx::reports_queued_count_on_success` | - [ ] |
| 14 | annotation-mode-selection | Batch Outcome Reporting | Partial trigger failure is reported distinctly | Given an Automated batch of 3 uploaded documents where 1 trigger fails, when it completes, then the summary reports 3 uploaded, 2 queued, 1 failed to queue, naming the failed document | `DocumentUpload.annotationMode.test.tsx::reports_partial_trigger_failure` | - [ ] |
| 15 | annotation-mode-selection | Batch Outcome Reporting | Trigger phase shows progress | Given an Automated batch of 5 uploaded documents, when the trigger phase runs, then a progress indicator shows position within that phase, distinguishable from upload progress | `DocumentUpload.annotationMode.test.tsx::shows_trigger_phase_progress` | - [ ] |
| 16 | annotation-mode-selection | Batch Outcome Reporting | Manual batch reports no pre-labeling outcome | Given a Manual batch of 3 successful uploads, when it completes, then the summary reports 3 uploaded and does not mention pre-labeling | `DocumentUpload.annotationMode.test.tsx::manual_summary_omits_prelabeling` | - [ ] |
| 17 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in create mode from header button | Given the entity types page, when "+ Define entity type" is clicked, then the slide-over opens titled "Create entity type" with empty fields, an editable NAME field, and an empty EXAMPLE Q&A section | `DefineEntityTypeSlideOver.test.tsx` (existing create-mode test, extended for the Q&A section) | - [ ] |
| 18 | entity-types-screen | Define / Edit Entity Type Slide-Over | Slide-over opens in edit mode from card | Given entity type "vendor_name" exists, when "Edit" is clicked, then the slide-over opens titled "Edit entity type" with NAME disabled, DESCRIPTION pre-filled, ORG chip selected, Required toggle on | `DefineEntityTypeSlideOver.test.tsx` (existing edit-mode regression test) | - [ ] |
| 19 | entity-types-screen | Define / Edit Entity Type Slide-Over | Existing QA pairs are pre-filled in edit mode | Given "years_experience" with one `qa_examples` entry, when Edit is clicked, then exactly 1 Q&A row renders with the stored question and answer in their inputs | `DefineEntityTypeSlideOver.qaPairs.test.tsx::prefills_existing_qa_pairs` | - [ ] |
| 20 | entity-types-screen | Define / Edit Entity Type Slide-Over | Adding a QA pair row and saving submits qa_examples | Given edit mode with no Q&A rows, when a pair is added and saved, then the PUT body contains `qa_examples` with one object holding the entered question and answer | `DefineEntityTypeSlideOver.qaPairs.test.tsx::submits_added_qa_pair` | - [ ] |
| 21 | entity-types-screen | Define / Edit Entity Type Slide-Over | Removing a QA pair row | Given 2 Q&A rows, when the first is removed and saved, then the request body contains `qa_examples` with only the remaining pair | `DefineEntityTypeSlideOver.qaPairs.test.tsx::removes_qa_pair_row` | - [ ] |
| 22 | entity-types-screen | Define / Edit Entity Type Slide-Over | Partially filled QA pair row blocks submission | Given a Q&A row with a question but no answer, when save is clicked, then an inline validation message shows on that row, no API request is sent, and the slide-over stays open | `DefineEntityTypeSlideOver.qaPairs.test.tsx::blocks_partial_qa_row` | - [ ] |
| 23 | entity-types-screen | Define / Edit Entity Type Slide-Over | Saving with no QA pairs submits an empty array | Given create mode with name/description/examples filled and no Q&A rows, when "Create entity type" is clicked, then the POST body contains `qa_examples` as an empty array and the slide-over closes on 201 | `DefineEntityTypeSlideOver.qaPairs.test.tsx::submits_empty_qa_examples` | - [ ] |
| 24 | entity-types-screen | Define / Edit Entity Type Slide-Over | BASE MODEL LABEL chip selection is single-select | Given the slide-over is open, when "LOC" is clicked, then the LOC chip becomes active and any previously selected chip is unselected | `DefineEntityTypeSlideOver.test.tsx` (existing chip regression test) | - [ ] |
| 25 | entity-types-screen | Define / Edit Entity Type Slide-Over | Create submits POST and shows success toast | Given create mode with valid fields, when "Create entity type" is clicked, then a POST is sent, a success toast shows on 201, the slide-over closes, and the list refreshes | `DefineEntityTypeSlideOver.test.tsx` (existing create regression test) | - [ ] |
| 26 | entity-types-screen | Define / Edit Entity Type Slide-Over | Edit submits PUT and increments version | Given edit mode for "customer_name" at version 1, when the description is updated and saved, then a PUT is sent and on 200 the card shows `v2` with a success toast | `DefineEntityTypeSlideOver.test.tsx` (existing edit regression test) | - [ ] |
| 27 | entity-types-screen | Define / Edit Entity Type Slide-Over | Escape key closes the slide-over | Given the slide-over is open, when Escape is pressed, then it closes without saving | `DefineEntityTypeSlideOver.test.tsx` (existing escape regression test) | - [ ] |
| 28 | entity-types-screen | Define / Edit Entity Type Slide-Over | API error shows error toast | Given the API returns 422 or 500, when the form is submitted, then an error toast displays and the slide-over remains open | `DefineEntityTypeSlideOver.test.tsx` (existing error regression test) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Trigger phase placement (design.md Decision 4) | Implementer fires the pre-label request inside the existing upload loop, per file, rather than as a distinct phase after the batch — interleaving two progress streams and coupling the failure modes | Read the handler: the trigger loop must be a separate pass over the succeeded-upload list, entered only after the upload loop exits. Scenario 10 must fail if the calls are interleaved. |
| 2 | Concurrency model (design.md Decision 3) | Implementer uses `Promise.all` / `Promise.allSettled` over the document list instead of sequential awaits, firing N concurrent POSTs from the browser | Grep the trigger implementation for `Promise.all`/`allSettled`. Only sequential `await` in a loop is permitted, matching the existing upload loop at `DocumentUpload.tsx:87`. |
| 3 | Gating condition (design.md Decision 5) | Implementer disables Automated when no `qa_examples` exist anywhere, treating QA pairs as a precondition — which directly contradicts change 1's Extraction Scope requirement that types without QA pairs are still extracted | Read the gating predicate: it must test active entity type count only, never `qa_examples` presence. Scenario 5 must pass with zero QA pairs configured. |
| 4 | Failure coupling (design.md Decision 4) | Implementer marks the upload item's status as `failed` when its pre-label trigger errors, or aborts the trigger loop on first failure, making an LLM outage look like an ingestion outage | Confirm the upload item's status field is never written by the trigger loop, and that the loop has no early `break`/`return` on error. Scenarios 11 and 12 must both pass. |
| 5 | Manual-mode purity (design.md Decision 2) | Implementer refactors shared state or the submit path in a way that changes Manual behaviour, or leaves an unconditional trigger call that runs in both modes | Diff `DocumentUpload.tsx` and confirm every new call site is behind a mode check. Scenario 6 asserts zero `/prelabel/llm` requests in Manual and must be run against the real component, not a stub. |
| 6 | Purpose gating (design.md Decision 1) | Implementer renders the selector unconditionally, or gates it on a role check rather than the `purpose` prop, exposing a meaningless control on query uploads | Confirm the render condition reads the `purpose` prop, matching the existing branch at `DocumentUpload.tsx:173`. Scenario 2 must pass. |
| 7 | Auth/tenant context on the new call (ADR-001) | Implementer calls the pre-label endpoint with bare `fetch` instead of the project's authenticated fetch layer, dropping the tenant context header the gateway relies on | Confirm the trigger call goes through `src/portal/src/lib/auth-fetch.ts` like every other portal request; grep the new code for raw `fetch(` or `XMLHttpRequest` outside the existing upload hook. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas; the gateway validates the JWT `tenant_id` and injects `X-Tenant-ID` | This frontend change must issue its pre-label calls through the existing authenticated fetch layer so tenant context is attached identically to every other portal request, and must never carry a tenant identifier in UI state | Grep the new trigger code for raw `fetch(`; confirm it routes through `src/portal/src/lib/auth-fetch.ts`. Confirm no component prop or local state holds a tenant id. |

> ADR-002, ADR-003 and ADR-008 govern the tenant's own trained and served model; ADR-006, ADR-009 and ADR-010 govern training infrastructure, hyperparameters and dataset-readiness thresholds. None constrain a frontend-only change that neither trains nor serves a model. ADR-004 and ADR-005 are process ADRs, satisfied by producing this artifact set before writing code.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1 (Selector shown for training): Vitest output showing the selector renders with Manual preselected
- [ ] Scenario 2 (Selector hidden for query): Vitest output asserting no selector in the query-purpose render
- [ ] Scenario 3 (Resets to Manual): Vitest output asserting Manual is selected after batch completion
- [ ] Scenario 4 (Automated disabled, no entity types): Vitest output asserting the disabled state and the hint text
- [ ] Scenario 5 (Automated enabled without QA pairs): Vitest output asserting the enabled state with zero `qa_examples`
- [ ] Scenario 6 (Manual is a no-op): Vitest output plus request-mock assertion of zero `/prelabel/llm` calls
- [ ] Scenario 7 (One trigger per document): request-mock assertion of exactly 3 calls with the 3 distinct document ids
- [ ] Scenario 8 (Failed uploads skipped): request-mock assertion of 2 calls for the 2 succeeded documents
- [ ] Scenario 9 (Rejected files skipped): request-mock assertion of 2 calls, none for the rejected file
- [ ] Scenario 10 (Triggers after uploads): call-order assertion showing all uploads resolve before the first trigger
- [ ] Scenario 11 (Trigger failure does not halt batch): request-mock assertion showing the third call was still issued after the second returned 500
- [ ] Scenario 12 (Failure leaves document usable): rendered-output assertion showing the document listed as uploaded, not failed
- [ ] Scenario 13 (Queued count reported): rendered summary asserting "3 uploaded" and "3 queued"
- [ ] Scenario 14 (Partial failure reported): rendered summary asserting 3 uploaded / 2 queued / 1 failed with the failed filename shown
- [ ] Scenario 15 (Trigger progress shown): rendered-output assertion that a trigger-phase indicator is present and distinct from upload progress
- [ ] Scenario 16 (Manual summary omits pre-labeling): rendered summary assertion that no pre-labeling text appears
- [ ] Scenario 17 (Create mode opens with empty Q&A section): Vitest output from the extended create-mode test
- [ ] Scenario 18 (Edit mode pre-fill): existing regression test output, unchanged
- [ ] Scenario 19 (QA pairs pre-filled): Vitest output asserting one row with the stored question and answer values
- [ ] Scenario 20 (Added pair submitted): request-body assertion showing `qa_examples` with the entered pair
- [ ] Scenario 21 (Removed pair): request-body assertion showing `qa_examples` with only the remaining pair
- [ ] Scenario 22 (Partial row blocks save): Vitest output asserting the inline message and zero API calls
- [ ] Scenario 23 (Empty array submitted): request-body assertion showing `qa_examples: []`
- [ ] Scenario 24 (Chip single-select): existing regression test output, unchanged
- [ ] Scenario 25 (Create POST + toast): existing regression test output, unchanged
- [ ] Scenario 26 (Edit PUT + version): existing regression test output, unchanged
- [ ] Scenario 27 (Escape closes): existing regression test output, unchanged
- [ ] Scenario 28 (API error toast): existing regression test output, unchanged

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations) *(agent note: one addition not named in tasks.md — `useUpload` now resolves with the created document's `{ id }` instead of `void`, because the per-document trigger endpoint cannot be addressed without it. Existing callers ignore the value; no behaviour change. Human reviewer to confirm.)*
- [x] All ADR compliance steps in Section 3 confirmed ✓ — `use-prelabel-trigger.ts` calls only `authFetch`; grep for `fetch(`/`XMLHttpRequest` in the new code returns nothing, and no component prop or state holds a tenant id
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] No backend files modified — every code file added or changed by this change is under `src/portal/` (plus this change's own openspec artifacts)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — the trigger loop sits after the upload loop exits (`DocumentUpload.tsx`, after `setBatchIndex(null)`); `triggers_run_after_all_uploads` asserts the full call order
- [x] Risk 2 mitigation confirmed — grep for `Promise.all`/`allSettled` in `DocumentUpload.tsx` and `use-prelabel-trigger.ts` matches only a comment; the trigger path is a `for` loop of `await trigger(...)`
- [x] Risk 3 mitigation confirmed — `automatedDisabled = activeEntityTypeCount === 0`; `qa_examples` appears in `DocumentUpload.tsx` only in a comment, and `enables_automated_without_qa_pairs` passes with zero pairs
- [x] Risk 4 mitigation confirmed — the trigger loop contains no `setBatch` call and no `break`/`return`; failures accumulate in `triggerFailures`. `trigger_failure_does_not_halt_batch` and `trigger_failure_not_reported_as_upload_failure` pass
- [x] Risk 5 mitigation confirmed — the only `trigger(...)` call site is inside `if (modeForBatch === "automated" ...)`; `manual_issues_no_prelabel_requests` runs against the real `DocumentUpload` and observes zero trigger calls
- [x] Risk 6 mitigation confirmed — the selector renders under `{purpose === "training" && ...}`, the same branch as the existing explanatory copy; no role is read
- [x] Risk 7 mitigation confirmed — `use-prelabel-trigger.ts` imports and calls `authFetch` only; `auth-fetch.ts` already routes `/api/v1/documents/{id}/prelabel/...` to the annotation service

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** annotation-mode-selection
**Proposal:** `openspec/changes/annotation-mode-selection/proposal.md`
**Spec files reviewed:**

- specs/annotation-mode-selection/spec.md
- specs/entity-types-screen/spec.md

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

- This change consumes change 1 (`llm-assisted-prelabeling`) and cannot be implemented before it lands. Change 1's own gate — the unresolved PII / data-residency question in its task 1.1 — therefore also gates this change: do not build the Automated path until that policy is decided, since it determines whether consent copy must accompany the control.
- This change assumes `multi-document-upload` (38/44 tasks complete) has landed for its batch semantics. The selector and trigger logic degrade correctly to a single-document batch, so it is not hard-blocked, but the batch outcome summary scenarios (13-16) assume multi-file batches.
- The per-document trigger loop (design.md Decision 3) is a deliberate deferral of a batch-trigger endpoint. Change 4 anticipates 100-200 document batches and should revisit this rather than inherit it silently. Reviewer should confirm this trade-off is still acceptable at sign-off time.
