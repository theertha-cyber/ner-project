# Verification Plan

**Change:** human-gated-retraining
**Generated:** 2026-09-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | human-gated-retraining | Training Runs Record Consumed Spans | A completed run records the spans it consumed | Given a run over a dataset built from 300 confirmed spans, when it completes producing version 4, then those 300 spans are recorded as consumed by version 4 | `tests/test_consumed_spans.py::test_completed_run_records_consumed_spans` | - [ ] |
| 2 | human-gated-retraining | Training Runs Record Consumed Spans | Accumulation resets after a completed run | Given accumulation of 134 against version 3, when a run consuming those spans completes and version 4 serves, then accumulation against version 4 is 0 | `tests/test_consumed_spans.py::test_accumulation_resets_after_run` | - [ ] |
| 3 | human-gated-retraining | Training Runs Record Consumed Spans | A rejected job records nothing | Given accumulation of 134 and a job in `pending_approval`, when a System Admin rejects it, then no spans are recorded consumed and accumulation stays 134 | `tests/test_consumed_spans.py::test_rejected_job_records_nothing` | - [ ] |
| 4 | human-gated-retraining | Training Runs Record Consumed Spans | A failed run records nothing | Given accumulation of 134 and an approved job, when the run fails, then no spans are recorded consumed and accumulation stays 134 | `tests/test_consumed_spans.py::test_failed_run_records_nothing` | - [ ] |
| 5 | human-gated-retraining | Training Runs Record Consumed Spans | Accumulation is unchanged while a run is in flight | Given accumulation of 134 and an approved job still running, when accumulation is requested, then it is still 134 | `tests/test_consumed_spans.py::test_accumulation_unchanged_during_run` | - [ ] |
| 6 | human-gated-retraining | Retraining Decision Surface | Decision surface shows accumulation against the serving version | Given 134 spans accumulated since version 3 was trained, when the surface is requested, then it reports 134 and identifies version 3 as serving | `tests/test_retraining_decision.py::test_surface_reports_accumulation_and_version` | - [ ] |
| 7 | human-gated-retraining | Retraining Decision Surface | Accumulation is broken down per entity type | Given 134 accumulated spans comprising 120 `organization` and 14 `person_name`, when the surface is requested, then it reports 120 and 14 respectively | `tests/test_retraining_decision.py::test_accumulation_broken_down_per_entity_type` | - [ ] |
| 8 | human-gated-retraining | Retraining Decision Surface | A tenant with no trained model is shown distinctly | Given a tenant served by the base model with no trained model, when the surface is requested, then it indicates no trained model exists and does not report zero against a version | `tests/test_retraining_decision.py::test_no_trained_model_shown_distinctly` | - [ ] |
| 9 | human-gated-retraining | Retraining Decision Surface | Accumulation is not presented as readiness | Given a surface reporting accumulation, when inspected, then it is labelled distinctly from readiness and is not compared to the per-type readiness threshold | `tests/test_retraining_decision.py::test_accumulation_not_presented_as_readiness` | - [ ] |
| 10 | human-gated-retraining | Manual Retrain Request | A retrain request creates a job pending approval | Given a tenant serving version 3 with accumulated spans, when a retrain is requested, then a job is created with status `pending_approval` and no Celery task is enqueued | `tests/test_retrain_request.py::test_request_creates_pending_approval_job` | - [ ] |
| 11 | human-gated-retraining | Manual Retrain Request | A requested retrain follows the existing approval flow | Given a retrain-requested job in `pending_approval`, when a System Admin approves it, then it transitions to `queued` and a Celery task is enqueued | `tests/test_retrain_request.py::test_requested_retrain_follows_approval_flow` | - [ ] |
| 12 | human-gated-retraining | Manual Retrain Request | A requested retrain can be rejected like any other job | Given a retrain-requested job in `pending_approval`, when a System Admin rejects it with a reason, then status is `rejected` and the reason is recorded | `tests/test_retrain_request.py::test_requested_retrain_can_be_rejected` | - [ ] |
| 13 | human-gated-retraining | Manual Retrain Request | A retrain request does not set hyperparameters | Given a retrain request from the decision surface, when the job is inspected before approval, then it carries no requester-supplied hyperparameters and they are set at approval | `tests/test_retrain_request.py::test_request_carries_no_hyperparameters` | - [ ] |
| 14 | human-gated-retraining | No Automatic Retraining Or Promotion | Accumulation reaching a large value creates no job | Given accumulation growing to 5000 spans, when the figure updates, then no training job is created, enqueued, or scheduled | `tests/test_no_auto_retraining.py::test_large_accumulation_creates_no_job` | - [ ] |
| 15 | human-gated-retraining | No Automatic Retraining Or Promotion | A completed run does not chain another run | Given a training run completing successfully, when completion is processed, then no further job is created, enqueued, or scheduled | `tests/test_no_auto_retraining.py::test_completion_does_not_chain_run` | - [ ] |
| 16 | human-gated-retraining | No Automatic Retraining Or Promotion | A completed run does not promote itself | Given a run completing and producing version 4, when completion is processed, then version 4 has status `completed`, is not promoted, and the previous version still serves | `tests/test_no_auto_retraining.py::test_completion_does_not_self_promote` | - [ ] |
| 17 | human-gated-retraining | No Automatic Retraining Or Promotion | Promotion still requires an explicit human action | Given a version with status `completed` and no user having promoted it, then it does not become serving and remains `completed` indefinitely | `tests/test_no_auto_retraining.py::test_promotion_requires_human_action` | - [ ] |
| 18 | human-gated-retraining | Promotion Decision Evidence | Candidate and current metrics are presented together | Given version 3 promoted and version 4 completed, when the promotion surface is requested for version 4, then both versions' metrics and their trained-on span counts are included | `tests/test_promotion_evidence.py::test_candidate_and_current_metrics_presented` | - [ ] |
| 19 | human-gated-retraining | Promotion Decision Evidence | Materially different dataset sizes are flagged | Given version 3 trained on 300 spans and version 4 on 1200, when the surface is requested for version 4, then it indicates the runs used materially different dataset sizes | `tests/test_promotion_evidence.py::test_different_dataset_sizes_flagged` | - [ ] |
| 20 | human-gated-retraining | Promotion Decision Evidence | No better-or-worse verdict is produced | Given version 4 with higher metrics than promoted version 3, when the surface is requested, then it does not state version 4 is better and does not recommend promotion | `tests/test_promotion_evidence.py::test_no_verdict_produced` | - [ ] |
| 21 | human-gated-retraining | Promotion Decision Evidence | No currently promoted version to compare against | Given version 1 completed with no previously promoted version, when the surface is requested for version 1, then version 1's metrics are included and the absence of a comparison target is indicated | `tests/test_promotion_evidence.py::test_no_promoted_version_to_compare` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
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

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-009-system-admin-sets-training-hyperparameters | A System Admin sets hyperparameters at approval time, not at submission | A retrain request must not carry or set hyperparameters | Inspect the retrain request schema and the created job before approval. Execute Scenario 13. |
| ADR-006-training-infrastructure | Async Celery GPU workers; jobs enqueued on approval | The retrain request must enter the existing queue-on-approval path, never enqueue directly or use a different queue | Confirm no Celery enqueue exists in the request path and that approval is what enqueues. Execute Scenarios 10 and 11. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | The consumed-span record and accumulation reset must be scoped to the tenant and to the version the run produced | Confirm the consumed-span record is keyed by tenant and produced model version. Execute Scenarios 1 and 2. |
| ADR-008-base-model-as-default | The base model serves as version 0 when a tenant has no active trained model | The retraining surface must present the no-trained-model state distinctly rather than as zero accumulation | Execute Scenario 8 against a tenant with no trained model. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | Accumulation is a different quantity from readiness and must be presented distinctly; any per-type breakdown must read the existing threshold rather than defining one | Confirm the surface labels accumulation distinctly and introduces no new threshold constant. Execute Scenario 9. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The consumed-span record and both surfaces resolve the tenant schema as existing endpoints do | Trace schema resolution for the new record and endpoints against the existing pattern. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1 (Consumed spans recorded): test output asserting the 300 spans recorded against version 4
- [ ] Scenario 2 (Accumulation resets): test output asserting 0 against version 4 after the run
- [ ] Scenario 3 (Rejected records nothing): test output asserting accumulation still 134 after rejection
- [ ] Scenario 4 (Failed records nothing): test output asserting accumulation still 134 after failure
- [ ] Scenario 5 (In-flight unchanged): test output asserting 134 while the run is still executing
- [ ] Scenario 6 (Surface reports figure and version): test output asserting 134 and version 3
- [ ] Scenario 7 (Per-type breakdown): test output asserting 120 `organization` and 14 `person_name`
- [ ] Scenario 8 (No trained model distinct): test output asserting the distinct state rather than a zero
- [ ] Scenario 9 (Not presented as readiness): test output asserting distinct labelling and no comparison to the readiness threshold
- [ ] Scenario 10 (Request creates pending job): test output asserting `pending_approval` and zero Celery enqueues at request time
- [ ] Scenario 11 (Approval enqueues): test output asserting transition to `queued` with a task enqueued
- [ ] Scenario 12 (Rejection works): test output asserting `rejected` status with the reason recorded
- [ ] Scenario 13 (No hyperparameters): test output asserting the pre-approval job carries none
- [ ] Scenario 14 (Large accumulation creates nothing): test output plus assertion of zero job creations as the figure grows to 5000
- [ ] Scenario 15 (No chained run): test output asserting no job created after a completion
- [ ] Scenario 16 (No self-promotion): test output asserting version 4 `completed`, unpromoted, previous version still serving
- [ ] Scenario 17 (Promotion needs a human): test output asserting a completed version never becomes serving on its own
- [ ] Scenario 18 (Both metrics presented): test output asserting both versions' metrics and span counts present
- [ ] Scenario 19 (Size difference flagged): test output asserting the materially-different indication for 300 versus 1200
- [ ] Scenario 20 (No verdict): test output asserting no comparative judgement or recommendation despite better candidate metrics
- [ ] Scenario 21 (No comparison target): test output asserting version 1's metrics plus the no-promoted-version indication

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] The full diff contains no scheduler registration, cron entry, or timer that could initiate a training job
- [ ] The full diff contains no comparison of an accumulation figure against a threshold constant
- [ ] `training-approval` and `model-registry` promote/demote code paths are unchanged in the diff

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — no job creation, enqueue, schedule, or threshold comparison reachable from the accumulation path
- [ ] Risk 2 mitigation confirmed — consumed spans recorded only in the run-completion path; rejected, failed and in-flight cases verified
- [ ] Risk 3 mitigation confirmed — no promote call reachable from run completion
- [ ] Risk 4 mitigation confirmed — request creates `pending_approval` and enqueues nothing; approval is what enqueues
- [ ] Risk 5 mitigation confirmed — retrain request schema carries no hyperparameters
- [ ] Risk 6 mitigation confirmed — no-trained-model returns a distinct state, not zero
- [ ] Risk 7 mitigation confirmed — promotion surface contains no verdict, ranking, or recommendation field

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
