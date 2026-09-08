# Verification Plan

**Change:** seed-bootstrap
**Generated:** 2026-09-03
**Status:** 🔴 ARCHIVED WITHOUT VERIFICATION SIGN-OFF — see § 8.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | seed-bootstrap | Entity Schema Proposal | Generate a schema proposal from a seed set | Given a tenant with 5 processed seed documents, when a schema proposal is requested, then status is 202 and the body contains a `proposal_id` | `tests/test_seed_bootstrap_proposal.py::test_request_proposal_returns_202` | - [x] |
| 2 | seed-bootstrap | Entity Schema Proposal | Proposal candidates carry verbatim examples | Given a completed proposal from a seed set, when it is retrieved, then each candidate has a name, description and ≥1 example, and every example appears verbatim in a seed document | `tests/test_seed_bootstrap_proposal.py::test_candidate_examples_are_verbatim` | - [x] |
| 3 | seed-bootstrap | Entity Schema Proposal | Generating a proposal creates no entity types | Given a tenant with exactly 2 active entity types, when a proposal completes returning 4 candidates, then the tenant still has exactly 2 and no version was incremented | `tests/test_seed_bootstrap_proposal.py::test_proposal_creates_no_entity_types` | - [x] |
| 4 | seed-bootstrap | Entity Schema Proposal | Proposal on a seed set with no processed documents | Given a seed set where no document has extracted text, when a proposal is requested, then status is 422 with an error indicating no processed documents | `tests/test_seed_bootstrap_proposal.py::test_proposal_422_no_processed_documents` | - [x] |
| 5 | seed-bootstrap | Schema Proposal Approval | Approving a candidate creates an entity type | Given a proposal with candidate `institute`, when it is approved, then an entity type `institute` exists at version 1 and the candidate is recorded approved | `tests/test_seed_bootstrap_proposal.py::test_approve_candidate_creates_entity_type` | - [x] |
| 6 | seed-bootstrap | Schema Proposal Approval | Rejecting a candidate creates nothing | Given a proposal with candidate `job_title`, when it is rejected, then no such entity type exists and the candidate is recorded rejected | `tests/test_seed_bootstrap_proposal.py::test_reject_candidate_creates_nothing` | - [x] |
| 7 | seed-bootstrap | Schema Proposal Approval | Editing a candidate before approval | Given candidate `institute` with description "A school", when it is edited to "A degree-granting institution" and approved, then the created type carries the edited description | `tests/test_seed_bootstrap_proposal.py::test_edit_candidate_before_approval` | - [x] |
| 8 | seed-bootstrap | Schema Proposal Approval | Approving a candidate whose name already exists | Given an existing active entity type `institute` and a candidate of the same name, when it is approved, then status is 422 and no duplicate is created | `tests/test_seed_bootstrap_proposal.py::test_approve_duplicate_name_422` | - [x] |
| 9 | seed-bootstrap | Batch Pre-labeling | Enqueue a batch pre-labeling job | Given 120 processed documents and ≥1 active entity type, when they are submitted for batch pre-labeling, then status is 202 and the body contains a single `batch_id` | `tests/test_seed_bootstrap_batch.py::test_enqueue_batch_returns_batch_id` | - [x] |
| 10 | seed-bootstrap | Batch Pre-labeling | One document failing does not abort the batch | Given a 10-document batch where the third document's LLM call fails, when the batch completes, then status reports 9 succeeded / 1 failed and spans exist for the 9 | `tests/test_seed_bootstrap_batch.py::test_single_document_failure_does_not_abort_batch` | - [x] |
| 11 | seed-bootstrap | Batch Pre-labeling | Batch pre-labeling honours the entity type constraint | Given a tenant whose only active types are `institute` and `person_name`, when a batch completes, then every suggested span carries one of those types and no new type was created | `tests/test_seed_bootstrap_batch.py::test_batch_honours_entity_type_constraint` | - [x] |
| 12 | seed-bootstrap | Batch Pre-labeling | Batch pre-labeling grounds quotes the same way as single-document pre-labeling | Given a batch document where the LLM returns an ungrounded quote, when the batch completes, then no span is stored for it and it is counted in that document's ungrounded count | `tests/test_seed_bootstrap_batch.py::test_batch_grounding_matches_single_document` | - [x] |
| 13 | seed-bootstrap | Sampled Acceptance Gate | Sample is drawn randomly and recorded | Given a completed 100-document batch, when acceptance review starts, then a randomly drawn sample is presented and the sampled document identities are stored with the acceptance record | `tests/test_seed_bootstrap_acceptance.py::test_sample_is_random_and_recorded` | - [x] |
| 14 | seed-bootstrap | Sampled Acceptance Gate | Batch meeting the threshold can be bulk-accepted | Given a sampled agreement rate at or above threshold, when the reviewer accepts, then all the batch's suggested spans become confirmed spans and the record stores sample size, rate, reviewer and timestamp | `tests/test_seed_bootstrap_acceptance.py::test_batch_above_threshold_bulk_accepts` | - [x] |
| 15 | seed-bootstrap | Sampled Acceptance Gate | Batch below the threshold cannot be bulk-accepted | Given a sampled agreement rate below threshold, when acceptance is attempted, then it is rejected, no span is promoted, and the measured rate is recorded | `tests/test_seed_bootstrap_acceptance.py::test_batch_below_threshold_rejected` | - [x] |
| 16 | seed-bootstrap | Sampled Acceptance Gate | Bulk acceptance is not permitted without a completed sample review | Given a completed batch whose sample review is incomplete, when bulk acceptance is attempted, then it is rejected with an error indicating the sample review is incomplete | `tests/test_seed_bootstrap_acceptance.py::test_acceptance_requires_completed_sample_review` | - [x] |
| 17 | seed-bootstrap | Sampled Acceptance Gate | Bulk-promoted spans record their acceptance route | Given a bulk-accepted batch, when the resulting confirmed spans are inspected, then each records batch-acceptance provenance and is distinguishable from an individually promoted span | `tests/test_seed_bootstrap_acceptance.py::test_bulk_promoted_spans_record_route` | - [x] |
| 18 | seed-bootstrap | Pre-Submission Readiness Check | Readiness check names shortfalling entity types | Given `institute` at 250 and `person_name` at 40 against a 200 per-type threshold, when the check runs, then `institute` is reported as meeting it and `person_name` as short with its count of 40 | `tests/test_seed_bootstrap_readiness.py::test_readiness_names_shortfalling_types` | - [x] |
| 19 | seed-bootstrap | Pre-Submission Readiness Check | Configured but unannotated entity types are visible | Given an active entity type `skill` with zero confirmed spans, when the check runs, then `skill` appears with a count of 0 | `tests/test_seed_bootstrap_readiness.py::test_unannotated_types_are_visible` | - [x] |
| 20 | seed-bootstrap | Pre-Submission Readiness Check | Readiness check does not block submission | Given a readiness report with two types below threshold, when a training job is submitted, then the submission is accepted and the job enters pending approval | `tests/test_seed_bootstrap_readiness.py::test_readiness_does_not_block_submission` | - [x] |
| 21 | seed-bootstrap | Pre-Submission Readiness Check | Readiness check does not use a tenant-wide total | Given 1000 `institute` entities and 5 `person_name`, when the check runs, then `person_name` is reported short and readiness is not asserted from the combined total | `tests/test_seed_bootstrap_readiness.py::test_readiness_is_per_type_not_total` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Schema proposal write path (design.md Decision 1) | Implementer has the proposal job insert into `entity_definitions` directly "to save a round trip", bypassing the entity-config API's validation, versioning and tenant scoping — and contradicting change 1's constraint that the LLM never creates entity types | Trace the approval path: it must call the existing entity type creation API, not write the table. Grep the proposal job for any INSERT against `entity_definitions`. Scenario 3 must show zero entity types created by proposal generation alone. |
| 2 | Grounding reuse in batch mode (design.md Decision 2) | Implementer writes a second, simplified extraction/grounding path for the batch job rather than reusing change 1's, so the extractive-only and exact-match guarantees silently differ between single and batch paths | Confirm the batch task calls the same grounding function change 1 introduced; there must not be two implementations. Scenarios 11 and 12 exist to catch divergence and must exercise the real batch path, not a stub. |
| 3 | Sample selection (design.md Decision 4) | Implementer takes the first N documents of the batch, or lets the reviewer choose which to review, producing an agreement rate that does not generalise — the first N uploads are frequently the most similar to each other | Read the sampling code: it must draw randomly across the whole batch. Confirm the drawn identities are persisted, not recomputed at read time. Scenario 13 must assert both randomness and persistence. |
| 4 | Partial acceptance (design.md Decision 3) | Implementer allows a sub-threshold batch to be "partially accepted" for the documents that happened to be reviewed, producing a dataset that silently mixes verified and unverified labels with no way to separate them later | Confirm the rejection path promotes zero spans. Scenario 15 must assert no span from a failing batch is promoted, not merely that the request errored. |
| 5 | Readiness threshold duplication (design.md Decision 5, ADR-010) | Implementer defines a new threshold constant in the readiness check rather than reading the existing `DATASET_READINESS_ENTITIES_PER_TYPE`, recreating the duplicate-threshold conflict ADR-010 was written to resolve | Grep the diff for any new per-type or total entity count constant. The check must import or query the existing single source of truth. Scenario 21 asserts per-type evaluation, not a tenant-wide total. |
| 6 | Readiness check becoming a gate (design.md Decision 5, ADR-009) | Implementer makes the check block training submission below threshold, duplicating `NER_MIN_ENTITIES_PER_TYPE` and taking a decision away from the System Admin approval step | Confirm the check has no rejection path into submission. Scenario 20 must show a submission succeeding while the report shows shortfalls. |
| 7 | Batch job queue selection (ADR-006) | Implementer routes the batch pre-labeling job onto the GPU `training.jobs` queue because it is "the batch queue", coupling I/O-bound LLM work to the GPU node pool and queueing it behind training runs | Grep the batch task registration for the queue name; it must be change 1's non-GPU queue. Confirm no GPU node-pool selector or resource request is attached, and that `training_service` queue config is unchanged in the diff. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type; the evaluated set is the union of active definitions and spanned types; per-type progress capped before aggregation | The readiness check must read the existing threshold constant, evaluate that same union, and never gate on a tenant-wide total | Grep the diff for new entity-count constants — there must be none. Confirm the readiness query enumerates active definitions unioned with distinct spanned types. Execute Scenarios 19 and 21. |
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets hyperparameters at approval time | The readiness check is advisory and must not block submission, set hyperparameters, or pre-empt approval | Confirm no code path returns a rejection from the readiness check into training submission. Execute Scenario 20. |
| ADR-006-training-infrastructure | Async Celery + RabbitMQ; GPU workers for training specifically | Batch pre-labeling is I/O-bound and must run on the non-GPU queue established by change 1 | Confirm the batch task's queue name matches change 1's queue and carries no GPU selector. Confirm `git diff` shows no `training_service` queue changes. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The batch job, proposal records, and acceptance records live in the tenant schema and resolve it as existing endpoints do; no LLM call may span tenants even in batch mode | Trace schema resolution in the batch task and the new tables against the existing `_schema(tenant_id)` pattern. Confirm the batch task receives a single tenant id and never iterates tenants. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1 (Proposal request): test output showing 202 with a `proposal_id`
- [ ] Scenario 2 (Verbatim examples): test output asserting every example is a substring of a seed document
- [ ] Scenario 3 (Proposal creates nothing): test output asserting entity type count and versions unchanged
- [ ] Scenario 4 (No processed documents): test output showing 422 with the expected error
- [ ] Scenario 5 (Approve creates type): test output asserting the entity type exists at version 1
- [ ] Scenario 6 (Reject creates nothing): test output asserting no entity type was created
- [ ] Scenario 7 (Edit before approval): test output asserting the edited description on the created type
- [ ] Scenario 8 (Duplicate name): test output showing 422 and no duplicate
- [ ] Scenario 9 (Batch enqueue): test output showing 202 with a single `batch_id` for 120 documents
- [ ] Scenario 10 (Failure isolation): test output asserting 9 succeeded / 1 failed with spans for the 9
- [ ] Scenario 11 (Entity type constraint in batch): test output asserting every span's type is configured and no type was created
- [ ] Scenario 12 (Batch grounding parity): test output asserting the ungrounded quote was dropped and counted
- [ ] Scenario 13 (Random recorded sample): test output asserting the sample is not the first N and that drawn ids were persisted
- [ ] Scenario 14 (Bulk accept above threshold): test output asserting all spans promoted plus the stored sample size, rate, reviewer and timestamp
- [ ] Scenario 15 (Reject below threshold): test output asserting zero spans promoted and the rate recorded
- [ ] Scenario 16 (Review required first): test output showing rejection with the incomplete-review error
- [ ] Scenario 17 (Provenance recorded): test output asserting bulk-accepted spans are distinguishable from individually promoted ones
- [ ] Scenario 18 (Shortfalls named): test output asserting `institute` ready and `person_name` short at 40
- [ ] Scenario 19 (Unannotated types visible): test output asserting `skill` present with count 0
- [ ] Scenario 20 (Advisory only): test output asserting submission accepted and job in pending approval despite shortfalls
- [ ] Scenario 21 (Per-type not total): test output asserting `person_name` reported short despite a large combined total

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Change 1's grounding and extraction code is reused by the batch path, not reimplemented — confirmed by reading the call graph
- [x] Only additive schema changes were introduced (new tables); no existing table was altered destructively

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — approval routes through the entity type creation API; no direct `entity_definitions` INSERT in the proposal path
- [x] Risk 2 mitigation confirmed — one grounding implementation shared by single and batch paths
- [x] Risk 3 mitigation confirmed — sample drawn randomly across the batch and drawn ids persisted
- [x] Risk 4 mitigation confirmed — a sub-threshold batch promotes zero spans; no partial acceptance path exists
- [x] Risk 5 mitigation confirmed — no new entity-count constant; the existing threshold is read
- [x] Risk 6 mitigation confirmed — readiness check has no path that rejects a training submission
- [x] Risk 7 mitigation confirmed — batch task on the non-GPU queue; no GPU selector; `training_service` queue config untouched

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

**Change slug:** seed-bootstrap
**Proposal:** `openspec/changes/seed-bootstrap/proposal.md`
**Spec files reviewed:**

- specs/seed-bootstrap/spec.md

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

- **Hard dependencies**: change 1 (`llm-assisted-prelabeling`) and change 3 (`training-data-integrity`) must both land first. Without change 3, a model trained from this flow would still learn from misaligned and truncated data no matter how good the annotations are — the quality gate would pass and the model would still be wrong.
- **The PII / data-residency question from change 1 task 1.1 gates this change with more force than it gates changes 1 and 2**, because this sends 100-200 documents to an external LLM rather than one. Do not implement before it is answered.
- **Four measurement questions are deliberately unresolved and must be answered with real data, not chosen at implementation time**: the agreement threshold, the sample size, what counts as agreement (exact span match versus overlap — a one-token boundary correction is a different signal from deleting a hallucinated entity), and the practical seed set size. Until these have evidence, the threshold should be configured conservatively or full review required. Reviewer should confirm the values used were measured.
- **Unresolved before implementation**: whether a rejected batch's suggestions are discarded or left for individual review. Leaving them preserves the option but lets a reviewer quietly accept what the gate rejected; discarding them prevents that but wastes the LLM spend.
- Sampling cannot eliminate the risk that the unsampled remainder contains systematic errors the sample missed — only bound it. The recorded sample and rate exist so a later quality problem is traceable to the batch and rate that admitted it.

---

## 7. Agent Verification Record

> Written by the implementing agent, not by a human reviewer. It records what was executed and
> what was inspected, so the reviewer signing Section 6 is checking claims rather than
> reconstructing them. **It is not a substitute for Section 5 or Section 6**, both of which
> remain unfilled and unsigned.

### Test execution (task 7.1)

All 21 acceptance-criteria tests — one per Spec Alignment row — executed against a real
PostgreSQL database with the LLM provider stubbed (`StubLLMClient`; no network call is made by
any test in this change).

```
tests/test_seed_bootstrap_proposal.py    8 passed   (rows 1-8)
tests/test_seed_bootstrap_batch.py       4 passed   (rows 9-12)
tests/test_seed_bootstrap_acceptance.py  5 passed   (rows 13-17)
tests/test_seed_bootstrap_readiness.py   4 passed   (rows 18-21)
=================== 21 passed, 3 warnings in 69.19s ====================
```

Change 1's own suite was re-run after `worker.py` was refactored to share its per-document
pipeline with the batch: `tests/test_llm_prelabel_api.py`,
`tests/test_llm_prelabel_cache.py`, `tests/test_llm_prelabel_extraction_scope.py` — 26 passed;
`tests/test_llm_prelabel_grounding.py` — 34 passed.

Frontend: `submit-job-slideover.test.tsx` (7) and the new
`submit-job-slideover.readiness.test.tsx` (4) pass; `auth-fetch.test.ts` (18, including two new
routing cases), `use-upload.test.tsx` and `DocumentUpload.annotationMode.test.tsx` (40 combined)
pass unchanged — the change 1/2 Suggest flow (task 6.4).

`docker compose build portal` succeeds. `next build` typechecks and fails the build on any type
error, so the new components compile clean; both new routes are present in the built image
(`.next/server/app/(auth)/schema-proposals`, `.../prelabel-batches`). With the rebuilt image
running, `GET /schema-proposals` and `GET /prelabel-batches` return 200 and redirect an
unauthenticated visitor to the login screen, as the existing authenticated routes do.

**The authenticated views were not rendered.** Doing so requires signing in, plus seeded
documents and a live LLM provider key for the screens to show more than an empty state. That
walkthrough belongs to task 7.6 and should be done there. What the reviewer should look at when
they run it: that the proposal screen shows each candidate's quoted examples beside its name
(they are the reviewer's only evidence the candidate is real), and that the acceptance screen's
"Confirm whole batch" control is disabled until the recorded rate clears the threshold — the
server refuses a sub-threshold batch regardless, so a discrepancy between the two would be a UI
defect, not a hole in the gate.

### Hallucination Risk Register (task 7.3)

| # | How it was checked | Result |
|---|-------------------|--------|
| 1 | `grep -rn "INSERT INTO public.entity_definitions" src/` | One hit, in `EntityService.create_entity_type`. The proposal task writes only `schema_proposal_candidates`; the approve endpoint's sole `entity_definitions` statement is a read (the duplicate-name check) before it calls `EntityService`. Scenario 3 asserts a completed 4-candidate proposal leaves the entity type count and every version unchanged. |
| 2 | `grep -rn "def ground_entities\|ground_entities(" src/` | One definition, one call site — `worker.extract_and_ground_document`, which has exactly two callers: `run_llm_prelabel_sync` (change 1's single-document path) and `run_prelabel_batch_sync` (the batch). There is no second implementation to drift. Scenarios 11 and 12 drive the real batch task. |
| 3 | Read `services/batch_acceptance.draw_sample` and the acceptance endpoint | Uniform `random.SystemRandom().sample` across the whole batch; drawn ids written to `batch_acceptance_records.sampled_document_ids` at selection time and read back unchanged. Scenario 13 asserts the draw differs from the first N, that the persisted ids match, and that a second read returns the same draw. |
| 4 | Read the accept endpoint | One threshold comparison; the sub-threshold branch records the rejection and raises before any promotion loop is reached. No branch promotes a subset. Scenario 15 asserts zero rows in `spans` after the refusal, and that the batch cannot be re-sampled afterwards. |
| 5 | `grep -rn "= 200\|ENTITIES_PER_TYPE" src/gateway/api/v1/training_readiness.py` | No new constant. `DATASET_READINESS_ENTITIES_PER_TYPE` is imported from `dashboard.py`, still its only definition in the tree. The readiness tests build their fixtures from the imported constant rather than the literal 200. |
| 6 | Read `training_readiness.py`; ran Scenario 20 | The module has no write path and no caller in `training_service`. Scenario 20 drives two apps: the report names two shortfalling types and the training submission returns 201 `pending_approval`. The frontend test asserts the submit button stays enabled while shortfalls are displayed. |
| 7 | `grep -rn "queue=" src/annotation_service/api/v1/seed_bootstrap.py` | Both enqueues use `settings.annotation_llm_celery_queue`. No occurrence of `training.jobs`, `nodeSelector`, or any GPU selector in the change's files. `git diff src/training_service/worker.py \| grep -c queue` returns 0 — no `training_service` queue configuration was touched. |

### Pattern & ADR Compliance (task 7.4)

| ADR | Verification step | Result |
|-----|------------------|--------|
| ADR-010 | Grep for new entity-count constants; confirm the union query | None found. The readiness endpoint reuses `dashboard._annotator_type_counts`, whose SQL unions active `entity_definitions` with the distinct types present in `spans` — the same query the annotator dashboard reads, not a second one. Scenarios 19 and 21 executed and pass. |
| ADR-009 | Confirm no rejection path from the check into submission | Confirmed by inspection and by Scenario 20. The check sets no hyperparameters — the response contains no hyperparameter field — and the job still enters `pending_approval` for a System Admin. |
| ADR-006 | Confirm queue name and absence of GPU selectors; confirm `training_service` untouched | Confirmed (Risk 7 row above). Both new tasks are registered on `annotation_service`'s Celery app, whose default queue is change 1's `annotation.llm_jobs`. |
| ADR-001 | Trace schema resolution and confirm no tenant iteration | Both task bodies take a single `tenant_id` argument and derive `_schema(tenant_id)` from it, the same derivation every `annotation_service` endpoint uses. No new code reads `public.tenants` or enumerates schemas. All six new tables live in the tenant schema; every statement against them is schema-qualified. |

### Call graph (task 7.5)

```
services/llm_prelabel.ground_entities        <- the only grounding implementation
  ^
  |  called by
worker.extract_and_ground_document           <- the only per-document pipeline
  ^                       ^
  |                       |
run_llm_prelabel_sync     run_prelabel_batch_sync
(change 1, one document)  (this change, N documents)
```

`services/schema_proposal.validate_candidate_examples` reaches the same module's `ground_quote`
for its verbatim check, so "appears in the document" means one thing across pre-labeling and
schema proposal alike.

### Schema additivity

Migration `039` creates six tenant-schema tables and alters no existing table in either
direction. `downgrade()` drops exactly what `upgrade()` creates. Bulk promotion writes ordinary
rows into the existing `spans` table through the same column list `promote_suggested_span` uses;
provenance lives in the new `span_batch_provenance` table rather than as a column on `spans`, so
no pre-existing row or column is touched.

### Not done by the agent — outstanding for the human reviewer

- **Task 7.2 / Section 5 Evidence Log** — deliberately left empty. Entries must describe
  observations the reviewer made.
- **Task 7.6** — the real end-to-end bootstrap on a live tenant. Not run: it sends real tenant
  documents to the external LLM provider, and the resulting per-type counts and agreement rate
  must be recorded from a real run, not a stubbed one.
- **Task 7.7 / Section 6 Audit Record** — unsigned, and cannot be signed by an agent.
- **The threshold and sample size remain placeholders.** `seed_bootstrap_agreement_threshold`
  defaults to `1.0` and sampling ships disabled, so bulk acceptance currently requires a full
  review at perfect agreement. These are conservative defaults standing in for a measurement,
  not measurements. The reviewer should confirm this is understood before the change is archived
  and before any deployment lowers the threshold.

---

## 8. Archive Waiver

**Archived:** 2026-09-07, on the explicit instruction of the change owner, with the verification
gate in § 6 unsatisfied.

§ 6 of this document states that an unsigned or incomplete Audit Record is a hard block on
archive. That block was waived. This section records what was and was not true at the moment of
archiving, so nobody later reads the archived state as evidence of a verification that did not
happen.

### Not satisfied at archive time

| Item | State |
|------|-------|
| Task 7.2 — Evidence Log | **Not done.** § 5 is empty. No human recorded an observation. |
| Task 7.6 — real end-to-end bootstrap on a tenant | **Not run.** No schema proposal, batch pre-label, sampled acceptance, or training submission has been executed against a live tenant with a real LLM provider. No per-type counts or agreement rate from a real run exist. |
| Task 7.7 — Audit Record sign-off | **Unsigned.** Every checkbox in § 6 is unticked and "Archive approved by" is blank. |

### What *is* verified

The 21 acceptance-criteria tests in § 1 all pass against a real PostgreSQL database with the LLM
provider stubbed, and the seven Hallucination Risk mitigations and four ADR compliance steps were
confirmed by inspection. § 7 records how each was checked. That is machine-verifiable
correctness against the spec — it is not the same thing as a human having watched the feature
work.

### The consequence a future reader most needs

**The agreement threshold has never been measured.** `seed_bootstrap_agreement_threshold`
defaults to `1.0` and `seed_bootstrap_sampling_enabled` defaults to `false`, so as shipped, bulk
acceptance requires reviewing every document in a batch and agreeing with every single
suggestion. That is deliberately too strict to be practical; it is a placeholder chosen because
it cannot be too permissive, standing in for a number that task 7.6 was supposed to produce.

Anyone lowering that threshold is setting the point at which unverified machine annotations enter
a training set. Doing so on the basis of this archived change would be relying on a measurement
that was never taken. Take it first.
