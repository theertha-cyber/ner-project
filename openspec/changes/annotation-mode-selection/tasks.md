## 1. Prerequisites

- [ ] 1.1 Confirm change 1 (`llm-assisted-prelabeling`) has landed — specifically the `POST /api/v1/documents/{doc_id}/prelabel/llm` endpoint and the `qa_examples` field on entity type definitions. This change consumes both and cannot be built before them.
- [ ] 1.2 Confirm the data-residency decision from change 1 task 1.1 has been made, and determine whether consent or warning copy must accompany the Automated option (design.md Open Questions). Do not build the Automated path without this.
- [ ] 1.3 Confirm `multi-document-upload` has landed, or accept that batch outcome summary work (group 4) targets a single-document batch until it does.

## 2. Entity Type QA Pairs Editor

- [ ] 2.1 Add `qa_examples` to the entity type form model and API payload types in `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.tsx`, defaulting to an empty array.
- [ ] 2.2 Render the EXAMPLE Q&A section below the EXAMPLES field: zero or more question/answer row pairs, an "+ Add Q&A pair" control, and a per-row remove control.
- [ ] 2.3 Pre-fill rows from the entity type's existing `qa_examples` in edit mode.
- [ ] 2.4 Implement submit-time handling: discard fully empty rows, block submission with an inline message on any row where exactly one of question/answer is filled, and submit `qa_examples` as an empty array when no rows remain.
- [ ] 2.5 Extend `DefineEntityTypeSlideOver.test.tsx` so the existing create-mode test asserts the Q&A section renders empty, covering Spec Alignment row 17. Confirm rows 18 and 24-28 still pass unchanged.
- [ ] 2.6 Add `DefineEntityTypeSlideOver.qaPairs.test.tsx` with `prefills_existing_qa_pairs`, `submits_added_qa_pair`, `removes_qa_pair_row`, `blocks_partial_qa_row`, and `submits_empty_qa_examples`, covering Spec Alignment rows 19-23.

## 3. Annotation Mode Selector

- [ ] 3.1 Add a Manual/Automated selector to `src/portal/src/components/documents/DocumentUpload.tsx`, rendered only when `purpose === "training"`, reusing the existing branch condition at line 173. Default to Manual.
- [ ] 3.2 Reset the selector to Manual when the upload zone returns to its idle state after a batch.
- [ ] 3.3 Fetch the tenant's active entity types (reusing the existing entity types query hook) and disable the Automated option with an explanatory hint when the count is zero. The predicate MUST test active entity type count only — never `qa_examples` presence (design.md Decision 5).
- [ ] 3.4 Add `DocumentUpload.annotationMode.test.tsx` with `shows_selector_for_training_purpose`, `hides_selector_for_query_purpose`, `resets_to_manual_after_batch`, `disables_automated_without_entity_types`, and `enables_automated_without_qa_pairs`, covering Spec Alignment rows 1-5.

## 4. Pre-label Trigger Orchestration

- [ ] 4.1 Add a hook alongside `use-upload` that issues `POST /api/v1/documents/{doc_id}/prelabel/llm` for a single document id, routing through `src/portal/src/lib/auth-fetch.ts` so tenant context is attached (ADR-001). No raw `fetch` or `XMLHttpRequest`.
- [ ] 4.2 After the upload loop completes and only when Automated is selected, run a separate sequential trigger loop over the succeeded-upload list. It MUST NOT be interleaved into the upload loop (design.md Decision 4) and MUST NOT use `Promise.all`/`allSettled` (design.md Decision 3).
- [ ] 4.3 Exclude client-side-rejected files and failed uploads from the trigger list.
- [ ] 4.4 Record per-document trigger outcome without writing to the upload item's status field; do not break or return early from the loop on error.
- [ ] 4.5 Add trigger-phase progress state, distinguishable in the UI from upload progress.
- [ ] 4.6 Extend the batch summary to report queued and failed-to-queue counts for Automated batches, naming any document that failed to queue, and to omit pre-labeling entirely for Manual batches.
- [ ] 4.7 Extend `DocumentUpload.annotationMode.test.tsx` with `manual_issues_no_prelabel_requests`, `automated_triggers_one_request_per_document`, `skips_prelabel_for_failed_uploads`, `skips_prelabel_for_rejected_files`, `triggers_run_after_all_uploads`, `trigger_failure_does_not_halt_batch`, `trigger_failure_not_reported_as_upload_failure`, `reports_queued_count_on_success`, `reports_partial_trigger_failure`, `shows_trigger_phase_progress`, and `manual_summary_omits_prelabeling`, covering Spec Alignment rows 6-16.

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Confirm `git diff --stat` shows no changes outside `src/portal/` — this change is frontend-only.
- [ ] 5.6 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 5.7 Run `openspec validate annotation-mode-selection --type change --strict` and confirm it exits clean before archive.
