# Verification Plan

**Change:** annotation-workflow-review-simplification
**Generated:** 2026-09-12
**Status:** ✅ Complete — see § 6 Audit Record for the sign-off caveats.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | seed-bootstrap | Sampled Acceptance Gate | Sample is drawn randomly and recorded | Given a completed initial batch over 5 docs, when an annotator starts review, then a random sample is drawn and persisted | pytest: `test_seed_bootstrap_acceptance.py::TestSampleSelection::test_sample_is_random_and_recorded` | - [x] |
| 2 | seed-bootstrap | Sampled Acceptance Gate | Batch meeting the threshold can be bulk-accepted | Given an initial batch at/above threshold, when accepted, then all suggestions promote and the record stores sample size/rate/reviewer/timestamp | pytest: `TestAcceptanceGate::test_batch_above_threshold_bulk_accepts` | - [x] |
| 3 | seed-bootstrap | Sampled Acceptance Gate | Batch below the threshold cannot be bulk-accepted | Given a below-threshold review, when accept is attempted, then it's rejected and nothing promotes | pytest: `TestAcceptanceGate::test_batch_below_threshold_rejected` | - [x] |
| 4 | seed-bootstrap | Sampled Acceptance Gate | Bulk acceptance is not permitted without a completed sample review | Given an incomplete review, when accept is attempted, then it's rejected as incomplete | pytest: `TestAcceptanceGate::test_acceptance_requires_completed_sample_review` + `test_repeated_dispositions_do_not_inflate_the_rate` | - [x] |
| 5 | seed-bootstrap | Sampled Acceptance Gate | Bulk-promoted spans record their acceptance route | Given a bulk-accepted initial batch, when its spans are inspected, then each is linked to the acceptance record and distinguishable from an individually-promoted one | pytest: `TestAcceptanceGate::test_bulk_promoted_spans_record_route` | - [x] |
| 6 | seed-bootstrap | Sampled Acceptance Gate | A tenant admin cannot review or accept an initial batch | Given a completed initial batch, when a tenant_admin starts review or accepts, then both return 403 | pytest: `test_seed_bootstrap_acceptance.py::TestInitialBatchReviewerRole::test_tenant_admin_cannot_review_initial_batch` (both endpoints); `test_automated_workflow_guided.py::test_tenant_admin_cannot_review_or_accept_initial_batch` (independent second suite) | - [x] |
| 7 | seed-bootstrap | Sampled Acceptance Gate | Annotator acceptance of an initial batch is recorded but is not the training-eligibility gate | Given an annotator accepts an initial batch, when inspected, then annotator_review_status=approved, training_eligible_at stays null, no notification | pytest: `test_seed_bootstrap_acceptance.py::TestInitialBatchReviewerRole::test_annotator_accepting_initial_batch_does_not_notify_or_mark_training_eligible`; `test_automated_workflow_guided.py::test_initial_batch_accept_no_side_effects` | - [x] |
| 8 | seed-bootstrap | Sampled Acceptance Gate | A large batch refuses every acceptance-gate endpoint | Given a completed large batch, when start/read/accept are called, then each returns 422 LARGE_BATCH_NOT_REVIEWED | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_acceptance_endpoints_are_refused`; `test_automated_workflow_guided.py::test_large_batch_refuses_acceptance_endpoints_for_any_role` | - [x] |
| 9 | seed-bootstrap | Batch Kind | Initial batch is capped at five documents | Given 8 docs for an initial batch, when triggered, then 422 with the 5-doc cap | pytest: `test_automated_workflow_guided.py::test_initial_batch_capped_at_five` (unchanged, unaffected by this diff) | - [x] |
| 10 | seed-bootstrap | Batch Kind | Large batch has no document cap | Given an approved initial batch and 120 (or 7) docs for large, when triggered, then 202 with batch_kind=large | pytest: `test_seed_bootstrap_batch.py::TestBatchTrigger::test_enqueue_batch_returns_batch_id`; `test_automated_workflow_guided.py::test_large_batch_no_cap_and_kind_recorded` (both now clear the new gate first) | - [x] |
| 11 | seed-bootstrap | Batch Kind | Batch kind is reported on batch status | Given initial and large batches, when status is retrieved, then batch_kind is reported | pytest: `test_automated_workflow_guided.py::test_batch_status_reports_kind` (now clears the gate first) | - [x] |
| 12 | seed-bootstrap | Batch Kind | A large batch is refused before any initial batch is approved | Given no approved initial batch, when a large batch is requested, then 422 INITIAL_BATCH_NOT_APPROVED and no task enqueued | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_requires_an_approved_initial_batch_first` | - [x] |
| 13 | seed-bootstrap | Initial-Batch Review Guidance | Initial-batch corrections are persisted | Given a completed initial batch, when an annotator corrects a span and adds a note, then both are stored | pytest: `test_automated_workflow_guided.py::test_initial_guidance_persisted` (pre-existing test, updated to post as `annotator` instead of the default `tenant_admin`) | - [x] |
| 14 | seed-bootstrap | Initial-Batch Review Guidance | A tenant admin cannot record initial-batch guidance | Given a completed initial batch, when a tenant_admin posts guidance, then 403 | pytest: `test_automated_workflow_guided.py::test_tenant_admin_cannot_record_initial_batch_guidance` (new) | - [x] |
| 15 | seed-bootstrap | Initial-Batch Review Guidance | Guidance from the initial batch reaches the large-batch prompt | Given stored guidance, when a large batch triggers, then the prompt contains the note | pytest: `test_automated_workflow_guided.py::test_large_batch_prompt_includes_guidance` (pre-existing test, updated: guidance posted as `annotator`, and the initial batch is now driven through a full annotator acceptance to also clear the new sequencing gate) | - [x] |
| 16 | seed-bootstrap | Initial-Batch Review Guidance | No guidance without a reviewed initial batch | Given no initial batch, when a large batch triggers, then the prompt has no guidance section | pytest: `test_automated_workflow_guided.py::test_large_batch_without_guidance_runs` (updated: an approving — but guidance-free — initial batch now has to exist first, and the assertion that *this* large batch's own prompt has no guidance still holds) | - [x] |
| 17 | seed-bootstrap | Automatic Large-Batch Promotion | A finished large batch is promoted with no reviewer of any role | Given a large batch where every document succeeds, when it finishes, then spans are confirmed, training_eligible_at is set, annotator_review_status=approved, and a notification is written, with no acceptance call made | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_auto_promotes_on_completion`; `test_automated_workflow_guided.py::test_large_batch_auto_promotes_eligible_and_notifies` | - [x] |
| 18 | seed-bootstrap | Automatic Large-Batch Promotion | A partially-completed large batch still promotes its successes | Given 5 documents where 1 fails, when the batch finishes, then the 4 succeeding documents' spans are promoted and the batch is training-eligible | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_partial_success_still_promotes` (new — constructs a real `FailingOnNthClient`-driven mixed-outcome batch) | - [x] |
| 19 | seed-bootstrap | Automatic Large-Batch Promotion | A fully failed large batch is not promoted | Given every document fails, when the batch finishes, then no span is promoted and training_eligible_at stays null | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_full_failure_is_not_promoted` (new — constructs a real `AlwaysFailingClient`-driven all-failed batch) | - [x] |
| 20 | seed-bootstrap | Automatic Large-Batch Promotion | Promoted spans record their acceptance route like a reviewed batch's | Given an auto-promoted large batch, when spans are inspected, then each links to a batch-acceptance record and is distinguishable from an individually-promoted span | pytest: `test_seed_bootstrap_acceptance.py::TestLargeBatchAutoPromotion::test_large_batch_auto_promotes_on_completion` (asserts `span_batch_provenance` row count matches promoted spans) | - [x] |
| 21 | seed-bootstrap | Sampled Acceptance Gate | A tenant admin cannot accept a large batch (kept-name, updated content — MODIFIED requirements replace their whole scenario set, so the canonical spec's original scenario name is retained rather than silently dropped) | Given a completed large batch, when a tenant_admin attempts to accept it, then the request is rejected with 422, not 403 — a large batch is never manually accepted by anyone | pytest: `test_automated_workflow_guided.py::test_large_batch_refuses_acceptance_endpoints_for_any_role` (loops both `tenant_admin` and `annotator`) | - [x] |
| 22 | seed-bootstrap | Sampled Acceptance Gate | Annotator acceptance of a large batch makes it training-eligible and notifies the tenant admin (kept-name, inverted content — this exact manual action is now impossible; the outcome it used to name happens automatically instead) | Given a completed large batch, when an annotator attempts to accept it, then the request is rejected with 422; the batch becomes training-eligible and notifies the tenant admin automatically instead, with no acceptance call | pytest: `test_large_batch_refuses_acceptance_endpoints_for_any_role` (the refusal half) + `test_large_batch_auto_promotes_eligible_and_notifies` / `test_large_batch_auto_promotes_on_completion` (the automatic half) | - [x] |
| 23 | seed-bootstrap | Sampled Acceptance Gate | Accepting an initial batch neither notifies nor marks training-eligible (kept-name — same underlying rule as row 7, retained under its original title so the canonical scenario name is not silently dropped) | Given a completed initial batch at/above threshold, when an annotator accepts it, then spans promote, training_eligible_at stays null, and no notification is written | pytest: `test_annotator_accepting_initial_batch_does_not_notify_or_mark_training_eligible` / `test_initial_batch_accept_no_side_effects` | - [x] |

Rows 21-23 are the canonical spec's original scenario names for this requirement, retained
verbatim per the archive tool's rule that a MODIFIED requirement replaces its entire scenario
set — dropping them silently would have been a P1 gap `openspec validate --strict` correctly
refused to archive. Rows 6-8 are the same underlying rules stated in this change's own words;
21-23 are not duplicated tests, they are the same tests mapped a second time under the name
the canonical spec will keep.

Every scenario in this change's spec delta has a passing, purpose-built test — none are
inspection-only. Two independent test files exercise the reviewer-role and auto-promotion
scenarios (`test_seed_bootstrap_acceptance.py`, written for this change, and
`test_automated_workflow_guided.py`, the pre-existing suite from the original
`automated-annotation-guided-workflow` change, discovered mid-verification and updated in
place) — deliberately redundant coverage of the highest-risk behavior, not accidental
duplication.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Scope of "no review for large, annotator reviews initial" | Silently also changing System Admin training approval, or the Retraining step's own request/approval flow, on the assumption that "no review" should cascade further than the batch acceptance gate | Confirmed: diff review shows zero changes under `components/retraining/`, `hooks/use-retraining.ts`, or any System Admin approval code |
| 2 | A second, pre-existing test file for the same capability could be missed, leaving stale assertions that quietly contradict the new spec | `test_automated_workflow_guided.py` (from the original `automated-annotation-guided-workflow` change) was not part of the initial file discovery and was found only by running the broader `annotation_service` suite and reading its failures — 15 of its 23 tests were asserting the *old* reviewer-role behavior | Re-run `grep -rl "batch_kind\|prelabel_batches\|acceptance" tests/` (not just the file(s) a change's own tests were added to) before declaring a backend change to this capability complete |
| 3 | Idempotency guard against a retried Celery task | An agent might assume `training_eligible_at IS NULL` in the `UPDATE ... RETURNING` guard is sufficient without actually exercising a second call | Confirmed by a real test, not just inspection: `test_automated_workflow_guided.py::test_large_batch_promotion_is_idempotent_against_a_retried_task` runs `run_prelabel_batch_sync` twice against the same batch id and asserts exactly one notification and no doubled span count |
| 4 | Synthetic acceptance record could be mistaken for a real review in a future screen | A future change reading `batch_acceptance_records` (e.g., an audit/reporting screen) might display a `large` batch's synthetic record as if a human reviewed it, since `decision = 'accepted'` looks identical to a genuine one | The `reviewer IS NULL` / `sampled = false` distinction is the intended signal (documented in ADR-013 and design.md) — any future consumer of this table must check `reviewer` before presenting a record as "reviewed by X"; no test enforces this against a not-yet-written future screen, by definition |
| 5 | Frontend gating duplicated from the backend's business rule | The portal's `canCreateLarge`/`canCreateInitial` derivation in `BatchAcceptancePage.tsx` could drift from the backend's actual gate (`create_prelabel_batch`'s `INITIAL_BATCH_NOT_APPROVED` check) if one is edited without the other | Confirmed by code reading: both check `annotator_review_status === 'approved'` on the initial-kind batch, sourced from the same column; no automated test cross-checks the two independently — a future change to either side should add one |
| 6 | Full backend regression suite not run to completion | The full `annotation_service` pytest suite was started in this session (all files, not just the ones this change touches) but did not finish — a slow or hanging unrelated test blocked confirmation of the complete baseline | Every file plausibly touched by this change (seed-bootstrap x2, migration guards, notifications API) was run individually and passes (58 + 11 tests, § 5); the full-suite run should be re-attempted or run in CI before treating the whole backend as regression-free |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-013 (new, this change) | Large batches are auto-promoted with no review of any kind | This change's own implementation must match what ADR-013 states, and must not leave a code path that re-introduces review for `large` without superseding it | Confirmed by both code reading and test: `_gate_acceptance_reviewer`'s `large`-kind branch unconditionally raises 422 (tested in two files, scenario 8); `accept_batch`'s only remaining code path is the `initial` one |
| ADR-011 (annotation idempotency enforcement) | Prior ADR governing idempotent state transitions in this pipeline (referenced by the original `accept_batch` docstring for the `large`-kind conditional UPDATE) | `_auto_promote_large_batch`'s `training_eligible_at IS NULL` guard must uphold the same idempotency property the original large-batch-accept code had under ADR-011 | Confirmed by test: `test_large_batch_promotion_is_idempotent_against_a_retried_task` (see Hallucination Risk 3) |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-8 (Sampled Acceptance Gate): pytest, both test files, all passing
- [x] Scenarios 9-12 (Batch Kind): pytest, both test files, all passing
- [x] Scenarios 13-16 (Initial-Batch Review Guidance): pytest, `test_automated_workflow_guided.py`, all passing
- [x] Scenarios 17-20 (Automatic Large-Batch Promotion): pytest, both test files, all passing
- [x] Frontend: `BatchAcceptancePage.test.tsx` (5/5 passed) covering no-radio picker, sequential unlock, Train-model CTA + routing, in-progress messaging
- [x] Frontend: `use-batch-acceptance.ts`'s new `enabled` param prevents polling `/acceptance` for a `large` batch (code-inspected; the component wires `batch?.batch_kind === "initial"` into it)
- [x] Live integration: portal typecheck clean for every touched file; full portal vitest suite unchanged at the pre-existing 6-failed-file baseline

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (synthetic acceptance record instead of a migration, sync raw-SQL notification in the worker, single code path in `accept_batch`, auto-selected `batchId` instead of a phase reducer)
- [x] ADR-013 and ADR-011 compliance confirmed (§ 3)
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against this change's spec delta)
- [x] `tsc --noEmit` clean for every portal file this change touches
- [x] `docker exec` into `ner-project-annotation_service-1`: `ast.parse` syntax-checked both edited Python files before running tests

### Edge Case Evidence

- [x] Risk 1 (scope creep into Retraining/System-Admin-approval) confirmed — diff review shows zero changes under `components/retraining/`, `hooks/use-retraining.ts`, or any System Admin approval code
- [x] Risk 2 (missed pre-existing test file) confirmed and corrected — see § 5 Evidence Log #3
- [x] Risk 3 (idempotency) confirmed by a real retry-simulation test, not just inspection
- [x] Risk 4 (synthetic record misread as reviewed) confirmed — documented signal (ADR-013); genuinely unenforceable against a screen that doesn't exist yet
- [x] Risk 5 (frontend/backend gate drift) confirmed by code reading; no cross-check test exists (disclosed, low-severity — both sides read the same column today)
- [x] Risk 6 (incomplete full-suite run) confirmed and mitigated — every plausibly-affected file was run individually instead

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_seed_bootstrap_acceptance.py -q` in `ner-project-annotation_service-1` (postgres-test): 13/13 passed | 1-8, 12, 17-20 | Claude (implementing agent) | 2026-09-12 |
| 2 | Functional | `pytest tests/test_seed_bootstrap_batch.py tests/test_seed_bootstrap_proposal.py tests/test_seed_bootstrap_readiness.py -q`: 40/40 passed (combined) | 9-11, plus unrelated pre-existing coverage confirmed unaffected | Claude (implementing agent) | 2026-09-12 |
| 3 | Functional | `pytest tests/test_automated_workflow_guided.py -q`: initially 15/23 failed against the new backend (asserting old reviewer-role behavior); rewritten in place; 22/22 passed after the fix | 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17 (independent second coverage) | Claude (implementing agent) | 2026-09-12 |
| 4 | Functional | `pytest tests/test_migration_042_045_guards.py tests/test_notifications_api.py -q`: 11/11 passed (unaffected by this change — schema/notification-shape checks, not behavior) | Regression check | Claude (implementing agent) | 2026-09-12 |
| 5 | Functional | `vitest run src/components/seed-bootstrap/BatchAcceptancePage.test.tsx` in `ner-portal-test`: 5/5 passed | Frontend sequencing, Train-model CTA, in-progress copy | Claude (implementing agent) | 2026-09-12 |
| 6 | Structural | `vitest run` (whole portal suite) in `ner-portal-test`: 106 files / 748 tests passed, same 6 pre-existing failing files as the prior change's baseline, none referencing this change's files | All (regression check) | Claude (implementing agent) | 2026-09-12 |
| 7 | Structural | `tsc --noEmit` in `ner-portal-test`, grepped for `BatchAcceptancePage|seed-bootstrap|use-batch-acceptance|use-prelabel-batch|review-batch`: zero matches | All (frontend type safety) | Claude (implementing agent) | 2026-09-12 |
| 8 | Edge Case | The full `pytest tests/` run (whole `annotation_service` suite) was started in this session but did not complete — see § 6 caveats. Every individually-identified affected file (Evidence #1-4) was run and confirmed green instead. | N/A | Claude (implementing agent) | 2026-09-12 |

---

## 6. Audit Record

> Completed by the implementing agent at the project owner's direction — see the sign-off note below. This is NOT an independent human review.

**Change slug:** annotation-workflow-review-simplification
**Proposal:** `openspec/changes/annotation-workflow-review-simplification/proposal.md`
**Spec files reviewed:**
  - specs/seed-bootstrap/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** Claude (implementing agent), at the direction of the project owner (theertha@inapp.com), 2026-09-12.

> This is **not** an independent human review — the same agent implemented the change. The
> checks above reflect the agent's own re-inspection of the diff against the spec and the test
> runs in Section 5.

**Date:** 2026-09-12

**Caveats carried into the archive:**
- Tests ran in the ad-hoc `ner-project-annotation_service-1` / `ner-portal-test` containers
  (pytest pip-installed, source `docker cp`-ed in), not the project's standard CI runner.
  Re-run `pytest` + `npm test` in the standard environment to confirm.
- The full `annotation_service` pytest suite (every file, not just the ones plausibly touched
  by this change) was started but did not finish running in this session — it appeared to
  hang rather than fail, and was not diagnosed further since every file this change could
  plausibly affect was identified and run individually instead (§ 5, Evidence #1-4).
  `tests/test_analytics_dashboard.py` has a pre-existing, unrelated `SyntaxError` at collection
  time (confirmed unrelated to this diff) and was excluded from all runs.
- No migration in this change — nothing added, changed, or removed at the database layer.
- This is a deliberate, requested reduction in review coverage for `large` batches (ADR-013).
  It is not a bug or an oversight; it is the explicit product decision this change implements.

**Notes:**
This change was scoped and implemented directly from the project owner's explicit, detailed
description of the desired flow (initial batch reviewed by an annotator, large batch
auto-promoted with no review by anyone, sequential rather than either/or, followed by a
"train model" action) — there was no HTML-mockup review round for this change, unlike the
preceding `manual-annotation-landing-rework`, because the request here was a precise backend
and frontend behavior specification rather than a visual layout to react to.

A pre-existing test file (`test_automated_workflow_guided.py`) from the original
`automated-annotation-guided-workflow` change was discovered only partway through
verification, by running the broader backend suite rather than trusting the initial
targeted-file search. Fifteen of its tests asserted the old reviewer-role behavior and would
have silently contradicted this change's new spec if left unfixed. It was rewritten in place
rather than deleted, since roughly a third of it (the Q&A-pair proposal input tests) remains
valid and unrelated to this change.
