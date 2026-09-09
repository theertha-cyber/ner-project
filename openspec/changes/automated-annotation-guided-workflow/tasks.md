## 1. Prerequisites

- [ ] 1.1 Confirm `seed-bootstrap` has landed (schema proposal, batch pre-labeling, sampled acceptance, readiness check are all present in `src/annotation_service`).
- [ ] 1.2 Confirm the Tenant Admin nav restructure Phases 2–3 have landed (commits `3747e25`, `f5febdf`): `/annotate/automated/{schema,prelabel,retrain}` routes, `public.notifications`, `src/annotation_service/services/notify.py`, and migration `041`'s `prelabel_batches.annotator_review_status` / `training_eligible_at` columns.
- [ ] 1.3 Confirm the PII / data-residency decision from `llm-assisted-prelabeling` — a `large` batch sends 50+ documents to an external LLM.
- [ ] 1.4 Decide the initial-batch size floor (1 vs 3) and record it. Assume 1 unless overridden.
- [ ] 1.5 Confirm the agreement threshold in force for `large` batches; it MUST NOT be lowered to admit a batch.

## 2. Database

- [ ] 2.1 Migration `042` (`apply_to_all_tenant_schemas`, additive): add `prelabel_batches.batch_kind VARCHAR(16) NOT NULL DEFAULT 'large'` and `prelabel_batches.state VARCHAR(24)` (nullable); create `{schema}.prelabel_batch_guidance (id, batch_id, document_id, corrected_spans JSONB, note TEXT, created_at)`; extend the `documents.purpose` allowed set to include `qa_pair`.
- [ ] 2.2 Update `scripts/setup_test_db.py` and the annotation test fixtures (`tests/test_annotation_workspace.py`, `tests/seed_bootstrap_support.py`) with the new columns/table and the `qa_pair` purpose.
- [ ] 2.3 Add `tests/test_migration_042_*.py` guard asserting the columns/table exist after upgrade and are absent after downgrade.

## 3. Q&A-Pair Proposal Input

- [ ] 3.1 Accept a `qa_pair` document upload on the schema-proposal request path (reuse the existing document upload + text-extraction pipeline; store as a `documents` row with `purpose = 'qa_pair'`). Reject unsupported file types with 422 naming PDF/DOC/DOCX/TXT. (Spec rows 1, 3)
- [ ] 3.2 Record the Q&A document id among the proposal's inputs and expose it on the proposal GET response. (Spec row 1)
- [ ] 3.3 In `src/annotation_service/services/schema_proposal.py`, append the Q&A document's extracted text to the proposal prompt alongside seed text and tenant QA pairs. (Spec row 2)
- [ ] 3.4 Confirm generating a proposal with a Q&A doc still creates zero entity types (existing invariant). (Spec row 4)
- [ ] 3.5 Add tests: `test_proposal_accepts_qa_pair_document`, `test_qa_pair_text_in_prompt`, `test_qa_pair_unsupported_type_422`, `test_qa_pair_creates_no_entity_types` in `tests/test_seed_bootstrap_proposal.py`. (Spec rows 1–4)

## 4. Batch Kind + Named State

- [ ] 4.1 Add `batch_kind` (`initial` | `large`) to the batch trigger request; default `large` if omitted; reject an `initial` batch of > 5 documents with 422. (Spec rows 5, 6)
- [ ] 4.2 Persist `batch_kind` on the batch row and include it in the batch status response. (Spec row 7)
- [ ] 4.3 Compute `state` from per-document outcome rows (`queued` / `processing` / `completed` / `partially_completed` / `failed`); cache the terminal value on `prelabel_batches.state` when the job finishes; reconcile on read if outcomes are complete but `state` is null. (Spec rows 8–11)
- [ ] 4.4 Include `state` and a progress count in the batch status response; the status endpoint MUST return promptly while `processing` (no blocking wait). (Spec row 11)
- [ ] 4.5 Add tests: `test_initial_batch_capped_at_five`, `test_large_batch_no_cap`, `test_batch_status_reports_kind`, `test_state_completed`, `test_state_partially_completed`, `test_state_failed_no_spans`, `test_state_processing_nonblocking` in `tests/test_seed_bootstrap_batch.py`. (Spec rows 5–11)

## 5. Initial-Batch Review Guidance

- [ ] 5.1 When a Tenant Admin reviews an `initial` batch, persist corrected spans and an optional per-document note to `{schema}.prelabel_batch_guidance`. (Spec row 12)
- [ ] 5.2 When a `large` batch is triggered, load the most recent reviewed `initial` batch's guidance and append it to the pre-labeling prompt as a "Reviewer guidance from validation" section (corrected spans as `"<quote>" → <type>` lines, notes verbatim). (Spec row 13)
- [ ] 5.3 A `large` batch with no prior reviewed `initial` batch runs on the QA-pairs-only prompt. (Spec row 14)
- [ ] 5.4 Add tests: `test_initial_guidance_persisted` (`tests/test_seed_bootstrap_acceptance.py`), `test_large_batch_prompt_includes_guidance`, `test_large_batch_without_guidance` (`tests/test_seed_bootstrap_batch.py`). (Spec rows 12–14)

## 6. Acceptance Gate — Role, Eligibility, Notification

- [ ] 6.1 Gate the acceptance-review and accept endpoints by `batch_kind`: `initial` → `require_roles(request, 'tenant_admin')`; `large` → `require_roles(request, 'annotator')`. Reuse `src/annotation_service/api/v1/_rbac.py`. (Spec rows 20, 22)
- [ ] 6.2 On accept of a `large` batch, in one transaction: promote spans (existing path) → conditional `UPDATE prelabel_batches SET training_eligible_at = NOW(), annotator_review_status = 'approved' WHERE id = :id AND training_eligible_at IS NULL` → if that UPDATE affected a row, call `notify(...)` with kind `automated_batch_approved`, `recipient_role = 'tenant_admin'`, `resource_type = 'prelabel_batch'`, `resource_id = batch_id`. (Spec rows 21, 23)
- [ ] 6.3 On accept of an `initial` batch: promote spans only — no eligibility stamp, no notification. (Spec row 22)
- [ ] 6.4 Ensure the whole accept transition is idempotent (re-accept is a no-op): guarded by the conditional UPDATE and by the existing "already promoted" check. (Spec row 23)
- [ ] 6.5 Add tests: `test_tenant_admin_cannot_accept_large_batch`, `test_annotator_accept_large_batch_eligible_and_notifies`, `test_initial_batch_accept_no_side_effects`, `test_large_batch_accept_is_idempotent` in `tests/test_seed_bootstrap_acceptance.py`. (Spec rows 20–23)
- [ ] 6.6 Re-run the carried-over acceptance tests (`test_sample_is_random_and_recorded`, `test_batch_above_threshold_bulk_accepts`, `test_batch_below_threshold_rejected`, `test_acceptance_requires_completed_sample_review`, `test_bulk_promoted_spans_record_route`) against the modified endpoint. (Spec rows 15–19)

## 7. `purpose = 'qa_pair'` filter audit

- [ ] 7.1 Grep every `purpose` filter in `src/annotation_service` and `src/training_service` (seed-document picker, `annotation-tasks` create, `annotation-export`, training dataset export). Confirm a `qa_pair` document appears in none of them. (Risk 6)

## 8. Portal

- [ ] 8.1 `/annotate/automated/schema` — add the Q&A-pair upload control to `SchemaProposalPage`; show the uploaded Q&A doc as a proposal input; keep the seed-document picker and candidate cards unchanged.
- [ ] 8.2 `/annotate/automated/prelabel` — add a `batch_kind` selector (Initial validation ≤5 / Large); render the named `state` (QUEUED/PROCESSING/COMPLETED/PARTIALLY_COMPLETED/FAILED) and progress; for an `initial` batch show the Tenant-Admin review with a per-document note field; for a `large` batch show a read-only "sent to Annotator Admin for review" state once submitted.
- [ ] 8.3 `/annotate/automated/retrain` — when a `large` batch is `annotator_review_status = 'approved'`, show "Training: Eligible" and a "Request training" action wired to `POST /api/v1/training-retrain-requests`. No "review annotations" action.
- [ ] 8.4 Annotator Admin: surface the `large`-batch acceptance queue from the annotator navigation (reuse `BatchAcceptancePage`); the annotator's accept is the final approval.
- [ ] 8.5 Update the automated stepper state derivation (`/annotate/automated/layout.tsx`) to use `batch_kind` + `state` + `annotator_review_status` instead of the current heuristic.
- [ ] 8.6 Portal tests: extend `src/portal/src/components/seed-bootstrap/*.test.tsx` for the Q&A upload, the batch-kind selector, and the state labels; add an annotator-view test for the large-batch queue.

## 9. Verification

- [ ] 9.1 Run `tests/test_seed_bootstrap_proposal.py`, `tests/test_seed_bootstrap_batch.py`, `tests/test_seed_bootstrap_acceptance.py` plus the portal `seed-bootstrap` suite; record output in verification.md §5 and §7.
- [ ] 9.2 Complete the Structural and Edge-Case evidence in verification.md §4.
- [ ] 9.3 Hand to a human reviewer for the §6 Audit Record sign-off.
