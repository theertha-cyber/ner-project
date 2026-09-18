## 1. Prerequisites

- [ ] 1.1 Confirm `seed-bootstrap` has landed (schema proposal, batch pre-labeling, sampled acceptance, readiness check are all present in `src/annotation_service`).
- [ ] 1.2 Confirm the Tenant Admin nav restructure Phases 2–3 have landed (commits `3747e25`, `f5febdf`): `/annotate/automated/{schema,prelabel,retrain}` routes, `public.notifications`, `src/annotation_service/services/notify.py`, and migration `041`'s `prelabel_batches.annotator_review_status` / `training_eligible_at` columns.
- [ ] 1.3 Confirm the PII / data-residency decision from `llm-assisted-prelabeling` — a `large` batch sends 50+ documents to an external LLM.
- [ ] 1.4 Decide the initial-batch size floor (1 vs 3) and record it. Assume 1 unless overridden.
- [ ] 1.5 Confirm the agreement threshold in force for `large` batches; it MUST NOT be lowered to admit a batch.

## 2. Database

- [x] 2.1 Migration `042` (per-tenant-schema loop — the guidance table names `{schema}` 3×, additive): add `prelabel_batches.batch_kind VARCHAR(16) NOT NULL DEFAULT 'large'` and `prelabel_batches.state VARCHAR(24)` (nullable); create `{schema}.prelabel_batch_guidance (id, batch_id FK, document_id FK, corrected_spans JSONB, note TEXT, created_at, UNIQUE(batch_id, document_id))`. `documents.purpose` has no CHECK constraint (migration 022) so `qa_pair` needs no DDL change.
- [x] 2.2 Update the annotation test fixtures — `tests/seed_bootstrap_support.py` gains `batch_kind` / `state` / `annotator_review_status` / `training_eligible_at` on `prelabel_batches`, the `prelabel_batch_guidance` table, and `public.notifications`. (setup_test_db.py holds only extraction tables — the seed-bootstrap tables live in the support module.)
- [x] 2.3 `tests/test_migration_042_045_guards.py::TestMigration042` + `TestMigration043` — run the real `upgrade()` / `downgrade()` for `tenant_template` and a tenant schema. The guard caught a real bug: `prelabel_batch_guidance` names `{schema}` 3 times (table + 2 FKs), which `apply_to_all_tenant_schemas`' single `format()` placeholder cannot express — migration 042 rewritten to a hand-rolled per-schema loop like migration 039.

## 3. Q&A-Pair Proposal Input

- [x] 3.1 The proposal request accepts an optional `qa_pair_document_id` referencing a document uploaded with `purpose='qa_pair'`; a non-qa_pair id or one with no extracted text is 422. (Q&A files are validated as PDF/DOC/DOCX/TXT at document upload.) Original: Accept a `qa_pair` document upload on the schema-proposal request path (reuse the existing document upload + text-extraction pipeline; store as a `documents` row with `purpose = 'qa_pair'`). Reject unsupported file types with 422 naming PDF/DOC/DOCX/TXT. (Spec rows 1, 3)
- [x] 3.2 Record the Q&A document id among the proposal's inputs and expose it on the proposal GET response. (Spec row 1)
- [x] 3.3 `schema_proposal.build_user_payload` gains `qa_pair_text`; the worker loads the Q&A doc text and passes it. Append the Q&A document's extracted text to the proposal prompt alongside seed text and tenant QA pairs. (Spec row 2)
- [x] 3.4 Confirm generating a proposal with a Q&A doc still creates zero entity types (existing invariant). (Spec row 4)
- [x] 3.5 Tests in `tests/test_automated_workflow_guided.py`: `test_proposal_accepts_qa_pair_document`, `test_qa_pair_text_in_prompt`, `test_qa_pair_unsupported_type_rejected`, `test_qa_pair_creates_no_entity_types`. Original:, `test_qa_pair_text_in_prompt`, `test_qa_pair_unsupported_type_422`, `test_qa_pair_creates_no_entity_types` in `tests/test_seed_bootstrap_proposal.py`. (Spec rows 1–4)

## 4. Batch Kind + Named State

- [x] 4.1 Add `batch_kind` (`initial` | `large`) to the batch trigger request; default `large` if omitted; reject an `initial` batch of > 5 documents with 422. (Spec rows 5, 6)
- [x] 4.2 Persist `batch_kind` on the batch row and include it in the batch status response. (Spec row 7)
- [x] 4.3 Compute `state` from per-document outcome rows via `_derive_batch_state`; the worker writes the terminal value on `prelabel_batches.state`; `get_prelabel_batch` reconciles on read if outcomes are complete but `state` is null. (Spec rows 8–11)
- [x] 4.4 Include `state` and a `progress` count in the batch status response; the status read is a single query, no blocking wait. (Spec row 11)
- [x] 4.5 Tests in `tests/test_automated_workflow_guided.py`: `test_initial_batch_capped_at_five`, `test_large_batch_no_cap_and_kind_recorded`, `test_batch_status_reports_kind`, `test_state_completed`, `test_state_failed_no_spans`, `test_state_queued_before_run`. (Spec rows 5–11) — 11/11 pass in the annotation_service container. `partially_completed` is covered by the worker classification + `_derive_batch_state`; add an explicit mixed-outcome test in 9.1.

## 5. Initial-Batch Review Guidance

- [x] 5.1 `POST /api/v1/prelabel-batches/{id}/guidance` (tenant_admin, initial batches only) persists corrected spans and an optional per-document note to `{schema}.prelabel_batch_guidance`. (Spec row 12)
- [x] 5.2 `create_prelabel_batch` for a `large` batch loads `_latest_initial_guidance`, renders it via `render_guidance_text`, and passes it to `run_prelabel_batch`; `build_user_payload` (llm_prelabel) threads it into the pre-label prompt. Original: load the most recent reviewed `initial` batch's guidance and append it to the pre-labeling prompt as a "Reviewer guidance from validation" section (corrected spans as `"<quote>" → <type>` lines, notes verbatim). (Spec row 13)
- [x] 5.3 A `large` batch with no prior reviewed `initial` batch runs on the QA-pairs-only prompt. (Spec row 14)
- [x] 5.4 Tests: `test_initial_guidance_persisted`, `test_large_batch_prompt_includes_guidance`, `test_large_batch_without_guidance_runs` in `tests/test_automated_workflow_guided.py`. Original: (`tests/test_seed_bootstrap_acceptance.py`), `test_large_batch_prompt_includes_guidance`, `test_large_batch_without_guidance` (`tests/test_seed_bootstrap_batch.py`). (Spec rows 12–14)

## 6. Acceptance Gate — Role, Eligibility, Notification

- [x] 6.1 `_gate_acceptance_reviewer(request, batch_kind)` gates start-review / get-review / submit-review / accept: `initial` → `tenant_admin`, `large` → `annotator`. `GET /prelabel-batches/{id}` and `GET /schema-proposals/{id}` also gained gates. (Spec rows 20, 22)
- [x] 6.2 On accept of a `large` batch, in one transaction: promote spans → conditional `UPDATE ... SET training_eligible_at = NOW(), annotator_review_status = 'approved' WHERE id = :id AND training_eligible_at IS NULL` → guarded `notify(kind="automated_batch_approved", recipient_role="tenant_admin", resource_type="prelabel_batch", resource_id=batch_id)`. Response gains `training_eligible`. (Spec rows 21, 23)
- [x] 6.3 On accept of an `initial` batch: promote spans only — no eligibility stamp, no notification. (Spec row 22)
- [x] 6.4 The accept transition is idempotent — the conditional UPDATE plus the existing `BATCH_ALREADY_DECIDED` guard mean a retried accept promotes nothing new and writes no second notification. (Spec row 23)
- [x] 6.5 Tests in `tests/test_automated_workflow_guided.py`: `test_tenant_admin_cannot_accept_large_batch`, `test_annotator_cannot_review_initial_batch`, `test_annotator_accept_large_batch_eligible_and_notifies`, `test_initial_batch_accept_no_side_effects`, `test_large_batch_accept_is_idempotent`. (Spec rows 20–23)
- [x] 6.6 Carried-over acceptance tests re-run green against the modified endpoint (helpers now review a `large` batch as `annotator`): `tests/test_seed_bootstrap_acceptance.py` 22/22 pass. (Spec rows 15–19)

## 7. `purpose = 'qa_pair'` filter audit

- [x] 7.1 Audited: `tasks.py` create-task requires `purpose='training'` (a qa_pair doc cannot be assigned); `export.py` has no purpose filter but a qa_pair doc has no spans so contributes nothing; `_documents_with_text` now excludes `purpose='qa_pair'` so the seed set and pre-label batches cannot include it. Original: Grep every `purpose` filter in `src/annotation_service` and `src/training_service` (seed-document picker, `annotation-tasks` create, `annotation-export`, training dataset export). Confirm a `qa_pair` document appears in none of them. (Risk 6)

## 8. Portal

- [x] 8.1 `SchemaProposalPage` — a Q&A-pair `<select>` populated from documents with `purpose === 'qa_pair'`; `useRequestSchemaProposal` now takes `{documentIds, qaPairDocumentId?}` and sends `qa_pair_document_id`. `DocumentPurpose` gains `'qa_pair'`. (Full drag-drop upload of the Q&A file is done via the existing document upload path — the selector picks an already-uploaded one.)
- [x] 8.2 `BatchAcceptancePage` — `batch_kind` radio selector (Initial ≤5 / Large) with a client-side 5-doc guard; renders `BATCH_STATE_LABEL[state]` + `progress` (`settled/total`) + the kind; for a `large` batch shows "now with an Annotator Admin for the final review"; for an `initial` batch keeps the Tenant-Admin acceptance review. `useCreatePrelabelBatch` takes `{documentIds, batchKind}`; `usePrelabelBatch` polls on `state`.
- [~] 8.3 `annotator_review_status === 'approved'` is surfaced on the batch status strip ("Approved — training eligible"). The full "Training: Eligible → Request training" retrain-step block is delivered by the `training-eligibility-overview` change, which owns that surface.
- [x] 8.4 New route `/annotate/review-batch/[id]` (annotator + tenant_admin) renders `BatchAcceptancePage` in `reviewOnly` mode opened on the batch; `NotificationBell` links an `automated_batch_approved` notification there for an annotator. (No list endpoint — the notification is the entry point.)
- [x] 8.5 New `GET /api/v1/prelabel-batches` (list, tenant_admin|annotator) + `usePrelabelBatches` hook. `annotate/automated/layout.tsx` now derives every step state from the batch list: step 2 done when a batch has finished (current while one runs), step 3 ready after a finished batch / done after an acceptance decision, step 4 ready when a `large` batch is `annotator_review_status='approved'` or accumulation > 0.
- [x] 8.6 `use-prelabel-batch.test.tsx` (batch_kind + guidance payload) and `use-schema-proposal.test.tsx` (qa_pair_document_id) added — 4 tests, green. `nav-config` + `app-shell` suites still green (23). Pre-existing unrelated portal failures unchanged.

## 9. Verification

- [ ] 9.1 Run `tests/test_seed_bootstrap_proposal.py`, `tests/test_seed_bootstrap_batch.py`, `tests/test_seed_bootstrap_acceptance.py` plus the portal `seed-bootstrap` suite; record output in verification.md §5 and §7.
- [ ] 9.2 Complete the Structural and Edge-Case evidence in verification.md §4.
- [ ] 9.3 Hand to a human reviewer for the §6 Audit Record sign-off.
