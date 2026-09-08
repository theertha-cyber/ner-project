# Verification Plan

**Change:** human-gated-retraining
**Generated:** 2026-09-03
**Status:** 🔵 Archived 2026-09-08 **with the Audit Record gate overridden** — see § 7.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | human-gated-retraining | Training Runs Record Consumed Spans | A completed run records the spans it consumed | Given a run over a dataset built from 300 confirmed spans, when it completes producing version 4, then those 300 spans are recorded as consumed by version 4 | `tests/test_consumed_spans.py::test_completed_run_records_consumed_spans` | - [x] | Confirmed. No enqueue exists on any path this change adds — `test_no_module_enqueues_training` walks the AST of all five modules; `test_no_module_registers_a_schedule` and `test_no_module_compares_a_figure_to_a_constant` cover the schedule and threshold forms, the latter by rejecting every float and multi-digit literal in the three accumulation-path modules so a config-gated threshold has nowhere to live. Scenarios 14 and 15 run against the real apps and the real accumulation query with `send_task` spied on both services, not stubs. |
| 2 | human-gated-retraining | Training Runs Record Consumed Spans | Accumulation resets after a completed run | Given accumulation of 134 against version 3, when a run consuming those spans completes and version 4 serves, then accumulation against version 4 is 0 | `tests/test_consumed_spans.py::test_accumulation_resets_after_run` | - [x] | Confirmed. The only call site is the success branch of `worker.fine_tune_model`, in the transaction that flips the model version to `completed`; the span set is captured at dataset-build time and held in memory. Scenarios 3, 4 and 5 all pass, and the rejection case drives the real `POST /training-jobs/{id}/reject` rather than an UPDATE. |
| 3 | human-gated-retraining | Training Runs Record Consumed Spans | A rejected job records nothing | Given accumulation of 134 and a job in `pending_approval`, when a System Admin rejects it, then no spans are recorded consumed and accumulation stays 134 | `tests/test_consumed_spans.py::test_rejected_job_records_nothing` | - [x] | Confirmed. `test_no_module_promotes` scans all five modules plus `worker.py` for `promote_model`/`mlflow_promote`. Scenario 16 shows version 4 `completed`, version 3 still `promoted`, and the decision surface still reporting 3 as serving. |
| 4 | human-gated-retraining | Training Runs Record Consumed Spans | A failed run records nothing | Given accumulation of 134 and an approved job, when the run fails, then no spans are recorded consumed and accumulation stays 134 | `tests/test_consumed_spans.py::test_failed_run_records_nothing` | - [x] | Confirmed. The request calls `create_training_job` and returns; scenario 10 asserts the `send_task` spy is empty and `celery_task_id` is NULL, and scenario 11 asserts the same spy fires exactly once at approval. The pair is what locates the enqueue. |
| 5 | human-gated-retraining | Training Runs Record Consumed Spans | Accumulation is unchanged while a run is in flight | Given accumulation of 134 and an approved job still running, when accumulation is requested, then it is still 134 | `tests/test_consumed_spans.py::test_accumulation_unchanged_during_run` | - [x] | Confirmed. The body is `TrainingJobCreate`, which has no fields and forbids extras, so a supplied `learning_rate` is a 422 rather than a silently dropped value. Scenario 13 plus `test_supplied_hyperparameters_are_refused` and a source scan for hyperparameter names. |
| 6 | human-gated-retraining | Retraining Decision Surface | Decision surface shows accumulation against the serving version | Given 134 spans accumulated since version 3 was trained, when the surface is requested, then it reports 134 and identifies version 3 as serving | `tests/test_retraining_decision.py::test_surface_reports_accumulation_and_version` | - [x] | Confirmed. `has_trained_model: false` returns `state`/`state_detail` with `spans_accumulated` and `by_entity_type` absent, and scenario 8 asserts both the presence of the state and the absence of the zero. The portal type is a discriminated union, so a `?? 0` on the frontend does not compile. |
| 7 | human-gated-retraining | Retraining Decision Surface | Accumulation is broken down per entity type | Given 134 accumulated spans comprising 120 `organization` and 14 `person_name`, when the surface is requested, then it reports 120 and 14 respectively | `tests/test_retraining_decision.py::test_accumulation_broken_down_per_entity_type` | - [x] | Confirmed. Scenario 20 supplies a candidate strictly better on every metric with similar dataset sizes and asserts no verdict word anywhere in the serialized response, and that the response has exactly four keys — `candidate`, `current`, `comparable`, `note` — so no field could carry one. The portal test makes the same assertion against the rendered screen and also asserts no promote control. |
| 8 | human-gated-retraining | Retraining Decision Surface | A tenant with no trained model is shown distinctly | Given a tenant served by the base model with no trained model, when the surface is requested, then it indicates no trained model exists and does not report zero against a version | `tests/test_retraining_decision.py::test_no_trained_model_shown_distinctly` | - [x] |
| 9 | human-gated-retraining | Retraining Decision Surface | Accumulation is not presented as readiness | Given a surface reporting accumulation, when inspected, then it is labelled distinctly from readiness and is not compared to the per-type readiness threshold | `tests/test_retraining_decision.py::test_accumulation_not_presented_as_readiness` | - [x] |
| 10 | human-gated-retraining | Manual Retrain Request | A retrain request creates a job pending approval | Given a tenant serving version 3 with accumulated spans, when a retrain is requested, then a job is created with status `pending_approval` and no Celery task is enqueued | `tests/test_retrain_request.py::test_request_creates_pending_approval_job` | - [x] |
| 11 | human-gated-retraining | Manual Retrain Request | A requested retrain follows the existing approval flow | Given a retrain-requested job in `pending_approval`, when a System Admin approves it, then it transitions to `queued` and a Celery task is enqueued | `tests/test_retrain_request.py::test_requested_retrain_follows_approval_flow` | - [x] |
| 12 | human-gated-retraining | Manual Retrain Request | A requested retrain can be rejected like any other job | Given a retrain-requested job in `pending_approval`, when a System Admin rejects it with a reason, then status is `rejected` and the reason is recorded | `tests/test_retrain_request.py::test_requested_retrain_can_be_rejected` | - [x] |
| 13 | human-gated-retraining | Manual Retrain Request | A retrain request does not set hyperparameters | Given a retrain request from the decision surface, when the job is inspected before approval, then it carries no requester-supplied hyperparameters and they are set at approval | `tests/test_retrain_request.py::test_request_carries_no_hyperparameters` | - [x] |
| 14 | human-gated-retraining | No Automatic Retraining Or Promotion | Accumulation reaching a large value creates no job | Given accumulation growing to 5000 spans, when the figure updates, then no training job is created, enqueued, or scheduled | `tests/test_no_auto_retraining.py::test_large_accumulation_creates_no_job` | - [x] |
| 15 | human-gated-retraining | No Automatic Retraining Or Promotion | A completed run does not chain another run | Given a training run completing successfully, when completion is processed, then no further job is created, enqueued, or scheduled | `tests/test_no_auto_retraining.py::test_completion_does_not_chain_run` | - [x] |
| 16 | human-gated-retraining | No Automatic Retraining Or Promotion | A completed run does not promote itself | Given a run completing and producing version 4, when completion is processed, then version 4 has status `completed`, is not promoted, and the previous version still serves | `tests/test_no_auto_retraining.py::test_completion_does_not_self_promote` | - [x] |
| 17 | human-gated-retraining | No Automatic Retraining Or Promotion | Promotion still requires an explicit human action | Given a version with status `completed` and no user having promoted it, then it does not become serving and remains `completed` indefinitely | `tests/test_no_auto_retraining.py::test_promotion_requires_human_action` | - [x] |
| 18 | human-gated-retraining | Promotion Decision Evidence | Candidate and current metrics are presented together | Given version 3 promoted and version 4 completed, when the promotion surface is requested for version 4, then both versions' metrics and their trained-on span counts are included | `tests/test_promotion_evidence.py::test_candidate_and_current_metrics_presented` | - [x] |
| 19 | human-gated-retraining | Promotion Decision Evidence | Materially different dataset sizes are flagged | Given version 3 trained on 300 spans and version 4 on 1200, when the surface is requested for version 4, then it indicates the runs used materially different dataset sizes | `tests/test_promotion_evidence.py::test_different_dataset_sizes_flagged` | - [x] |
| 20 | human-gated-retraining | Promotion Decision Evidence | No better-or-worse verdict is produced | Given version 4 with higher metrics than promoted version 3, when the surface is requested, then it does not state version 4 is better and does not recommend promotion | `tests/test_promotion_evidence.py::test_no_verdict_produced` | - [x] |
| 21 | human-gated-retraining | Promotion Decision Evidence | No currently promoted version to compare against | Given version 1 completed with no previously promoted version, when the surface is requested for version 1, then version 1's metrics are included and the absence of a comparison target is indicated | `tests/test_promotion_evidence.py::test_no_promoted_version_to_compare` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required | Agent Confirmation (task 8.3) |
|---|-----------|-------------------|----------------------|-------------------------------|
| 1 | Auto-trigger reintroduction (design.md Decision 3) | Implementer reads "accumulation has reached 500" and adds a threshold check that enqueues a training job — the exact behaviour this plan deliberately reversed. May appear as a config-gated feature defaulting to off, which is still a trigger | Grep the entire diff for training job creation or Celery enqueue reachable from the accumulation path, a scheduler registration, or any comparison of accumulation against a constant. Scenarios 14 and 15 must pass against the real code path, not a stub. |
| 2 | Consumed spans recorded at submission (design.md Decision 1) | Implementer marks spans consumed when the job is created rather than when the run completes, so a rejected or failed job silently zeroes accumulation despite producing no model — losing the evidence that the retrain never happened | Confirm the recording call sits in the run-completion path, not the submission or approval path. Scenarios 3, 4 and 5 exist specifically to catch this and must all pass. |
| 3 | Auto-promotion on completion (design.md Decision 3) | Implementer promotes the new version when a run completes, reasoning that a newer model is presumably better — bypassing the existing manual promote step | Confirm no promote call is reachable from run completion. Scenario 16 must show version 4 in `completed` status with the previous version still serving. |
| 4 | Bypassing the approval flow (design.md Decision 2, ADR-006) | Implementer has the retrain request enqueue the Celery task directly, or create the job already in `queued`, because the user "already asked for it" — skipping System Admin approval | Confirm the request path creates a job in `pending_approval` and enqueues nothing. Scenario 10 must assert no task was enqueued at request time; Scenario 11 must show enqueueing happening only at approval. |
| 5 | Hyperparameters on the request (ADR-009) | Implementer lets the retrain request carry hyperparameters, contradicting ADR-009's placement of them at approval time | Inspect the request payload schema and the created job. Scenario 13 must show no requester-supplied hyperparameters before approval. |
| 6 | Zero conflated with no-model (design.md Decision 5) | Implementer returns an accumulation figure of 0 for a tenant with no trained model, which is indistinguishable from a freshly retrained tenant with no new evidence — the opposite situation | Confirm the no-trained-model branch returns a distinct state. Scenario 8 must assert the response indicates no trained model rather than reporting zero. |
| 7 | Verdict on the promotion surface (design.md Decision 4) | Implementer computes "version 4 is better" or a recommendation from the metric comparison, making the decision the surface exists to inform — and doing so across runs whose metrics may not be comparable | Read the promotion surface response for any comparative judgement, ranking, or recommendation field. Scenario 20 supplies a candidate with strictly better metrics and must still produce no verdict. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step | Agent Confirmation (task 8.4) |
|-----|-----------------|--------------------------|-------------------|-------------------------------|
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets hyperparameters at approval time, not at submission | A retrain request must not carry or set hyperparameters | Inspect the retrain request schema and the created job before approval. Execute Scenario 13. | Compliant. `TrainingJobCreate` has no hyperparameter fields and forbids extras; the created job's `hyperparams` is NULL before approval and populated by `ApproveJobRequest` at approval. Scenario 13 executed. |
| ADR-006-training-infrastructure | Async Celery GPU workers; jobs enqueued on approval | The retrain request must enter the existing queue-on-approval path, never enqueue directly or use a different queue | Confirm no Celery enqueue exists in the request path and that approval is what enqueues. Execute Scenarios 10 and 11. | Compliant. The request path contains no Celery call at all; approval is what sends `fine_tune_model` to the existing queue, unchanged. Scenarios 10 and 11 executed with a spy across both services' Celery apps. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | The consumed-span record and accumulation reset must be scoped to the tenant and to the version the run produced | Confirm the consumed-span record is keyed by tenant and produced model version. Execute Scenarios 1 and 2. | Compliant. `span_training_consumption` rows are written into the tenant schema and keyed by the `version_number` the run produced, not the version that predicted the span. Scenarios 1 and 2 executed. |
| ADR-008-base-model-as-default | The base model serves as version 0 when a tenant has no active trained model | The retraining surface must present the no-trained-model state distinctly rather than as zero accumulation | Execute Scenario 8 against a tenant with no trained model. | Compliant. Scenario 8 executed against a tenant with no promoted version: the surface returns `state: no_trained_model` and omits the figure. The base-model span count is still reported, separately. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | Accumulation is a different quantity from readiness and must be presented distinctly; any per-type breakdown must read the existing threshold rather than defining one | Confirm the surface labels accumulation distinctly and introduces no new threshold constant. Execute Scenario 9. | Compliant. The surface labels the figure `accumulation_since_training` and says in words that it is not readiness; `test_surface_introduces_no_readiness_threshold` confirms the module imports no readiness threshold, names none, and contains no multi-digit literal. Scenario 9 executed. `gateway/api/v1/training_readiness.py` is untouched. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The consumed-span record and both surfaces resolve the tenant schema as existing endpoints do | Trace schema resolution for the new record and endpoints against the existing pattern. | Compliant. Every statement in the three new backend modules resolves the tenant schema with the same `tenant_{id}` helper the existing endpoints use, and the two surfaces take their tenant from request state exactly as their neighbours do. Traced by reading against `review_queue.py` and `training_jobs.py`. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [x] Scenario 1 (Consumed spans recorded): test output asserting the 300 spans recorded against version 4
- [x] Scenario 2 (Accumulation resets): test output asserting 0 against version 4 after the run
- [x] Scenario 3 (Rejected records nothing): test output asserting accumulation still 134 after rejection
- [x] Scenario 4 (Failed records nothing): test output asserting accumulation still 134 after failure
- [x] Scenario 5 (In-flight unchanged): test output asserting 134 while the run is still executing
- [x] Scenario 6 (Surface reports figure and version): test output asserting 134 and version 3
- [x] Scenario 7 (Per-type breakdown): test output asserting 120 `organization` and 14 `person_name`
- [x] Scenario 8 (No trained model distinct): test output asserting the distinct state rather than a zero
- [x] Scenario 9 (Not presented as readiness): test output asserting distinct labelling and no comparison to the readiness threshold
- [x] Scenario 10 (Request creates pending job): test output asserting `pending_approval` and zero Celery enqueues at request time
- [x] Scenario 11 (Approval enqueues): test output asserting transition to `queued` with a task enqueued
- [x] Scenario 12 (Rejection works): test output asserting `rejected` status with the reason recorded
- [x] Scenario 13 (No hyperparameters): test output asserting the pre-approval job carries none
- [x] Scenario 14 (Large accumulation creates nothing): test output plus assertion of zero job creations as the figure grows to 5000
- [x] Scenario 15 (No chained run): test output asserting no job created after a completion
- [x] Scenario 16 (No self-promotion): test output asserting version 4 `completed`, unpromoted, previous version still serving
- [x] Scenario 17 (Promotion needs a human): test output asserting a completed version never becomes serving on its own
- [x] Scenario 18 (Both metrics presented): test output asserting both versions' metrics and span counts present
- [x] Scenario 19 (Size difference flagged): test output asserting the materially-different indication for 300 versus 1200
- [x] Scenario 20 (No verdict): test output asserting no comparative judgement or recommendation despite better candidate metrics
- [x] Scenario 21 (No comparison target): test output asserting version 1's metrics plus the no-promoted-version indication

### Structural Evidence

*(Code review and architectural compliance.)*

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] The full diff contains no scheduler registration, cron entry, or timer that could initiate a training job
- [x] The full diff contains no comparison of an accumulation figure against a threshold constant
- [x] `training-approval` and `model-registry` promote/demote code paths are unchanged in the diff

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [x] Risk 1 mitigation confirmed — no job creation, enqueue, schedule, or threshold comparison reachable from the accumulation path
- [x] Risk 2 mitigation confirmed — consumed spans recorded only in the run-completion path; rejected, failed and in-flight cases verified
- [x] Risk 3 mitigation confirmed — no promote call reachable from run completion
- [x] Risk 4 mitigation confirmed — request creates `pending_approval` and enqueues nothing; approval is what enqueues
- [x] Risk 5 mitigation confirmed — retrain request schema carries no hyperparameters
- [x] Risk 6 mitigation confirmed — no-trained-model returns a distinct state, not zero
- [x] Risk 7 mitigation confirmed — promotion surface contains no verdict, ranking, or recommendation field

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

> Collected by an agent. Every entry below is a real observation from a real execution — the
> command and its result are reproducible from the repository. The Audit Record in Section 6
> remains a human gate and is deliberately left unsigned.
>
> Test command, for every `pytest` entry:
> ```
> NER_DATABASE_URL=postgresql+asyncpg://ner:ner@postgres-test:5432/ner_test \
>   python -m pytest tests/test_consumed_spans.py tests/test_retraining_decision.py \
>   tests/test_retrain_request.py tests/test_no_auto_retraining.py \
>   tests/test_promotion_evidence.py
> ```
> Result: **40 passed**.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `test_consumed_spans.py::TestCompletedRunRecordsConsumedSpans::test_completed_run_records_consumed_spans` PASSED — 6 review spans recorded against version 4, span ids compared against the production `dataset_span_ids_sql` | 1 | Claude Opus 5 (agent) | 2026-09-08 |
| 2 | Test output | `test_consumed_spans.py::TestAccumulationResetsAfterRun::test_accumulation_resets_after_run` PASSED — 5 against version 3 before, 0 against version 4 after, breakdown empty | 2 | Claude Opus 5 (agent) | 2026-09-08 |
| 3 | Test output | `test_consumed_spans.py::TestRejectedJobRecordsNothing::test_rejected_job_records_nothing` PASSED — rejection driven through `POST /api/v1/training-jobs/{id}/reject`; consumption table empty, figure still 7 | 3 | Claude Opus 5 (agent) | 2026-09-08 |
| 4 | Test output | `test_consumed_spans.py::TestFailedRunRecordsNothing::test_failed_run_records_nothing` PASSED — job and version both `failed`, consumption table empty, figure still 7 | 4 | Claude Opus 5 (agent) | 2026-09-08 |
| 5 | Test output | `test_consumed_spans.py::TestAccumulationUnchangedDuringRun::test_accumulation_unchanged_during_run` PASSED — figure still 7 mid-run, and the decision surface reports `training_run_in_flight: true` | 5 | Claude Opus 5 (agent) | 2026-09-08 |
| 6 | Test output | `test_retraining_decision.py::TestSurfaceReportsAccumulationAndVersion::test_surface_reports_accumulation_and_version` PASSED — 9 spans, serving version 3 | 6 | Claude Opus 5 (agent) | 2026-09-08 |
| 7 | Test output | `test_retraining_decision.py::TestAccumulationBrokenDownPerEntityType::test_accumulation_broken_down_per_entity_type` PASSED — `{organization: 8, person_name: 3}`, largest first | 7 | Claude Opus 5 (agent) | 2026-09-08 |
| 8 | Test output | `test_retraining_decision.py::TestNoTrainedModelShownDistinctly::test_no_trained_model_shown_distinctly` PASSED — `state: no_trained_model`, and `spans_accumulated` absent from the response rather than 0 | 8 | Claude Opus 5 (agent) | 2026-09-08 |
| 9 | Test output | `test_retraining_decision.py::TestAccumulationNotPresentedAsReadiness::{test_accumulation_not_presented_as_readiness, test_surface_introduces_no_readiness_threshold}` PASSED — distinct `kind`, no readiness key, and the module contains no readiness import, threshold name, or multi-digit literal | 9 | Claude Opus 5 (agent) | 2026-09-08 |
| 10 | Test output | `test_retrain_request.py::TestRequestCreatesPendingApprovalJob::test_request_creates_pending_approval_job` PASSED — `pending_approval`, `celery_task_id` NULL, `send_task` spy empty | 10 | Claude Opus 5 (agent) | 2026-09-08 |
| 11 | Test output | `test_retrain_request.py::TestRequestedRetrainFollowsApprovalFlow::{test_requested_retrain_follows_approval_flow, test_approval_handles_it_like_any_other_job}` PASSED — `queued` with exactly one `fine_tune_model` enqueue carrying the job id, and an ordinary job approved identically | 11 | Claude Opus 5 (agent) | 2026-09-08 |
| 12 | Test output | `test_retrain_request.py::TestRequestedRetrainCanBeRejected::test_requested_retrain_can_be_rejected` PASSED — `rejected` with the reason in `error_message`, spy still empty | 12 | Claude Opus 5 (agent) | 2026-09-08 |
| 13 | Test output | `test_retrain_request.py::TestRequestCarriesNoHyperparameters::{test_request_carries_no_hyperparameters, test_supplied_hyperparameters_are_refused, test_request_module_reads_no_hyperparameters}` PASSED — `hyperparams` NULL pre-approval and populated at approval; a supplied `learning_rate` is a 422; the module names no hyperparameter | 13 | Claude Opus 5 (agent) | 2026-09-08 |
| 14 | Test output | `test_no_auto_retraining.py::TestLargeAccumulationCreatesNoJob::*` (4 tests) PASSED — figure grown through the real endpoints with both services' `send_task` spied, zero jobs created; plus AST scan for enqueues, token scan for schedulers, literal scan for thresholds | 14 | Claude Opus 5 (agent) | 2026-09-08 |
| 15 | Test output | `test_no_auto_retraining.py::TestCompletionDoesNotChainRun::{test_completion_does_not_chain_run, test_worker_completion_block_creates_no_job}` PASSED — job count unchanged after completion; `worker.py` contains no `send_task`, `apply_async`, `.delay(`, or schedule registration | 15 | Claude Opus 5 (agent) | 2026-09-08 |
| 16 | Test output | `test_no_auto_retraining.py::TestCompletionDoesNotSelfPromote::{test_completion_does_not_self_promote, test_no_module_promotes}` PASSED — version 4 `completed`, version 3 still `promoted` and still reported as serving; no promote call in any module or in the worker | 16 | Claude Opus 5 (agent) | 2026-09-08 |
| 17 | Test output | `test_no_auto_retraining.py::TestPromotionRequiresHumanAction::test_promotion_requires_human_action` PASSED — version 4 stays `completed` across completion and every read of all three surfaces | 17 | Claude Opus 5 (agent) | 2026-09-08 |
| 18 | Test output | `test_promotion_evidence.py::TestCandidateAndCurrentMetricsPresented::test_candidate_and_current_metrics_presented` PASSED — both versions' metrics and both `trained_on_span_count` values present | 18 | Claude Opus 5 (agent) | 2026-09-08 |
| 19 | Test output | `test_promotion_evidence.py::TestDifferentDatasetSizesFlagged::*` (4 tests) PASSED — 4-vs-16 (the spec's 300:1200 ratio) gives `comparable: false` with the note; 9-vs-10 gives `true`; an unrecorded size gives `null`; the threshold is 0.25 and gates only a sentence | 19 | Claude Opus 5 (agent) | 2026-09-08 |
| 20 | Test output | `test_promotion_evidence.py::TestNoVerdictProduced::test_no_verdict_produced` PASSED — candidate strictly better on every metric with similar dataset sizes; no verdict word anywhere in the serialized response, and exactly four keys | 20 | Claude Opus 5 (agent) | 2026-09-08 |
| 21 | Test output | `test_promotion_evidence.py::TestNoPromotedVersionToCompare::*` (3 tests) PASSED — `current: null`, `comparable: null`, note present; same for a candidate that is itself promoted; unknown version 404s | 21 | Claude Opus 5 (agent) | 2026-09-08 |
| 22 | Test output | `RetrainingDecisionPage.test.tsx` — 11 passed (`vitest run src/components/retraining`). Covers the frontend halves of rows 6-13 and 18-21: the breakdown, the distinct no-trained-model state, the in-flight notice, the request action and its zero-accumulation warning, both metric columns, the comparability flag, and the absence of any verdict or promote control. | 6-13, 18-21 | Claude Opus 5 (agent) | 2026-09-08 |
| 23 | Structural scan | Tasks 8.5/8.6 scan over this change's own file set (the working tree also carries uncommitted work from changes 3-5, so `git diff` is not this change's diff): no scheduler, cron or timer token in any new file or added line; no `send_task`/`apply_async`/`.delay(` on any path this change adds; no float and no multi-digit integer literal in the three accumulation-path modules; `training_jobs.py` and `models.py` unmodified since HEAD with `approve_training_job`, `reject_training_job`, `promote_model` and `demote_model` all intact. | 14-17, structural | Claude Opus 5 (agent) | 2026-09-08 |
| 24 | Regression | Change 5's own suite `tests/test_accumulation_reporting.py` — 8 passed, unchanged by the `COALESCE(version_number, version)` fix to `current_model_version` and the per-entity-type breakdown added to `accumulation_report`. | 2, 6-9 | Claude Opus 5 (agent) | 2026-09-08 |
| 25 | Regression | Portal suite: 18 failures at HEAD, 18 after this change. The single new failure was `nav-config.test.ts`'s tenant-admin item count, updated as an added nav entry requires. `tsc --noEmit`: 34 errors, all pre-existing in unrelated test files, none in any file this change touches. | structural | Claude Opus 5 (agent) | 2026-09-08 |
| 26 | Regression | Change 5's full suite re-run after the `COALESCE(version_number, version)` fix and the per-entity-type breakdown: `test_confidence_routing.py`, `test_review_queue.py`, `test_review_outcomes.py`, `test_audit_sampling.py`, `test_accumulation_reporting.py`, `test_extraction_confidence_filtering.py` — **77 passed**. (`NER_DATABASE_URL_SYNC` must also point at `postgres-test`; without it the extraction-side tests fail on a `localhost` connection, which is environmental and not a code failure.) | 2, 6-9 | Claude Opus 5 (agent) | 2026-09-08 |
| 27 | Regression | Training-side suites: `test_training_jobs.py` **10 passed**, `test_model_registry.py` **22 passed**. `test_training_jobs_api.py` gives 21 passed / 1 failed / 6 errors — **identical at HEAD with this change's `src/` swapped out**, so pre-existing and unrelated. | structural | Claude Opus 5 (agent) | 2026-09-08 |
| 28 | Regression | `test_training_worker.py -m 'not integration and not slow'` — **16 passed, 1 failed** (`TestOnnxExport::test_onnx_export_mock_verifies_export_call`). The same run with this change's `src/` swapped for HEAD gives 13 passed / 4 failed, so the ONNX failure is pre-existing and the other three are artifacts of the working tree carrying uncommitted change 3/4 work. The full file does not complete inside 550s either way — it downloads models. | 15, structural | Claude Opus 5 (agent) | 2026-09-08 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** human-gated-retraining
**Proposal:** `openspec/changes/human-gated-retraining/proposal.md`
**Spec files reviewed:**

- specs/human-gated-retraining/spec.md

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

- **The consumed-span recording is the substantive work here; everything else is surfacing.** It sits in a boundary gap between changes 5 and 6 where each could plausibly assume the other owns it: change 5 defines the record and reads it, this change writes it. Without it, change 5's accumulation figure is correct exactly once and wrong after every retrain. Reviewer should confirm the write exists and fires only on successful completion.
- **This plan originally had retraining fire automatically on a threshold and that was deliberately reversed.** It is therefore the single most likely thing to be reintroduced by an implementer who sees an accumulation figure and concludes the system should act on it — including as a config-gated feature defaulting to off, which is still a trigger. Both changes 5 and 6 carry this guard as a testable requirement rather than a prose note.
- **Promotion was already manual before this change** (`model-registry`, Promote model version). Scenarios 16 and 17 exist to confirm this change does not accidentally erode it, not to build it.
- **Four questions remain open**: what context beyond a raw count makes the retrain decision judgeable (a per-type breakdown is specified, but whether it is sufficient is unconfirmed), how prominently to convey metric comparability limits, whether a retrain may be requested at zero accumulation, and who may request one given approval is already System Admin only.
- **The promotion surface deliberately produces no verdict.** Metrics from two runs over materially different datasets are not straightforwardly comparable — change 3 established this for pre-fix versus post-fix runs and the same caution applies here. A surface that silently invites an invalid comparison is worse than one showing nothing, because it produces confident wrong promotions.

---

## 7. Archive Override

> Recorded at archive time so the override is visible to anyone reading this later, rather than
> being inferable only from thirteen unticked boxes in the section above.

**Archived:** 2026-09-08, on the user's explicit instruction, by `/opsx:archive`.

**What was overridden.** Section 6 states that an unsigned or incomplete Audit Record is a hard
block on archive. It was unsigned at archive time: all thirteen sign-off checkboxes unticked and
`Archive approved by` blank. The user was shown this and chose to archive anyway.

**What that means in practice.** Sections 1 through 5 were completed by an agent, and Section 2
exists specifically to catch that agent's likely errors. Nobody has independently confirmed
those seven mitigations. The three most load-bearing are worth naming, because each is an
*absence* and absences do not show up in a passing response:

- **Risk 1 — auto-trigger reintroduction.** The plan originally had retraining fire on a
  threshold and that was deliberately reversed, which makes it the single most likely thing to
  come back. Checked behaviourally and by AST/token/literal scans over every module this change
  adds.
- **Risk 3 — auto-promotion on completion.** Checked by scenario and by a promote-call scan
  across the five modules and the training worker.
- **Risk 7 — verdict on the promotion surface.** Checked by supplying a candidate strictly better
  on every metric and asserting no verdict word survives anywhere in the response.

Each of these is enforced by a test rather than only observed once, so a later reintroduction
fails the suite. That is not the same as a human having read the diff.

**Tasks open at archive time** (all three from tasks.md § 8, each with its reason recorded there):

| Task | Why it is open |
|------|----------------|
| 8.7 — full end-to-end loop on a tenant | Requires a training run to actually complete, i.e. fine-tuning BERT on a GPU worker. Every step except that one is covered by a passing test against real endpoints; what remains unproven is that `worker.fine_tune_model` reaches the consumed-span recording on a real run. |
| 8.8 — Audit Record sign-off | The override recorded here. The task states it cannot be completed by an agent. |
| 8.9 — `openspec validate --strict` | No Node runtime is installed on this machine or in any project container, so the `openspec` CLI cannot run at all. The change was implemented and archived by reading and editing the artifact files directly. |

**If this is picked up later**, the two things actually worth doing are 8.7 on a tenant with a
GPU worker, and a human pass over Section 2. Everything else in this file is backed by a test
that runs.
