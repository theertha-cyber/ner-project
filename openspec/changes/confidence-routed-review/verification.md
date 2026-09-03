# Verification Plan

**Change:** confidence-routed-review
**Generated:** 2026-09-03
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | Post-processing confidence filtering | Low-confidence entities are filtered out | Given a threshold of 0.50, when extraction runs on text producing an entity at confidence 0.30, then that entity does not appear in the results | `tests/test_extraction_confidence_filtering.py` (existing regression test) | - [ ] |
| 2 | extraction-service | Post-processing confidence filtering | Low-confidence entities are retained for routing | Given a threshold of 0.50 and a prediction at 0.30, when extraction runs, then the prediction is retained with type, value, confidence, offsets and model version, and is available to routing | `tests/test_extraction_confidence_filtering.py::test_below_threshold_predictions_retained` | - [ ] |
| 3 | extraction-service | Post-processing confidence filtering | Retained low-confidence predictions are not visible to business consumers | Given a run with 3 above-threshold and 2 below-threshold entities, when a business consumer queries entities, then exactly 3 are returned and neither retained prediction appears | `tests/test_extraction_confidence_filtering.py::test_retained_predictions_hidden_from_consumers` | - [ ] |
| 4 | confidence-routed-review | Confidence-Based Routing | High-confidence prediction is auto-accepted | Given a review threshold of 0.90 and a prediction at 0.95, when routing runs, then it is recorded auto-accepted and does not appear in the review queue | `tests/test_confidence_routing.py::test_high_confidence_auto_accepted` | - [ ] |
| 5 | confidence-routed-review | Confidence-Based Routing | Low-confidence prediction enters the review queue | Given a review threshold of 0.90 and a prediction at 0.62, when routing runs, then it appears in the review queue with recorded confidence 0.62 | `tests/test_confidence_routing.py::test_low_confidence_enters_queue` | - [ ] |
| 6 | confidence-routed-review | Confidence-Based Routing | Review threshold is independent of the extraction threshold | Given extraction threshold 0.50 and review threshold 0.90, when the review threshold changes to 0.80, then the extraction threshold stays 0.50 and business-facing results are unchanged | `tests/test_confidence_routing.py::test_review_threshold_independent` | - [ ] |
| 7 | confidence-routed-review | Confidence-Based Routing | Routed predictions record the serving model version | Given an extraction run served by tenant model version 3, when routing runs, then every routed prediction records model version 3 | `tests/test_confidence_routing.py::test_routed_predictions_record_model_version` | - [ ] |
| 8 | confidence-routed-review | Review Queue Resolution | Human reviewer confirms a queued prediction | Given a queued prediction of type `organization` at 45-53, when a human confirms it as-is, then the outcome is recorded confirmed with the human route | `tests/test_review_queue.py::test_human_confirms_prediction` | - [ ] |
| 9 | confidence-routed-review | Review Queue Resolution | Human reviewer corrects the offsets of a queued prediction | Given a queued prediction at 45-53, when a human corrects it to 45-58, then the outcome is recorded corrected with offsets 45-58 | `tests/test_review_queue.py::test_human_corrects_offsets` | - [ ] |
| 10 | confidence-routed-review | Review Queue Resolution | Reviewer rejects a queued prediction | Given a queued prediction judged not an entity, when the reviewer rejects it, then the outcome is recorded rejected and no confirmed span is created | `tests/test_review_queue.py::test_reviewer_rejects_prediction` | - [ ] |
| 11 | confidence-routed-review | Review Queue Resolution | LLM review produces the same outcome structure | Given a tenant policy routing to the LLM, when the LLM review job resolves a prediction, then the outcome is confirmed, corrected or rejected and records the LLM route | `tests/test_review_queue.py::test_llm_review_outcome_structure` | - [ ] |
| 12 | confidence-routed-review | Review Queue Resolution | LLM review does not bypass the outcome path | Given a tenant policy routing to the LLM, when the job completes, then every resulting span was created from a recorded review outcome and none was written directly by the job | `tests/test_review_queue.py::test_llm_review_does_not_bypass_outcome_path` | - [ ] |
| 13 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A confirmed outcome creates a span at the predicted offsets | Given an outcome confirming an `organization` prediction at 45-53, when processed, then a confirmed span exists with that type and those offsets | `tests/test_review_outcomes.py::test_confirmed_outcome_creates_span` | - [ ] |
| 14 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A corrected outcome creates a span at the corrected offsets | Given an outcome correcting to 45-58, when processed, then a span exists at 45-58 and none at the original 45-53 | `tests/test_review_outcomes.py::test_corrected_outcome_uses_corrected_offsets` | - [ ] |
| 15 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A rejected outcome creates no span | Given an outcome rejecting a prediction, when processed, then no confirmed span is created for it | `tests/test_review_outcomes.py::test_rejected_outcome_creates_no_span` | - [ ] |
| 16 | confidence-routed-review | Review Outcomes Become Confirmed Spans | A value correction does not produce a span | Given an extracted entity whose `corrected_value` differs from the document text at its offsets, when outcomes are processed, then no span is created from that value | `tests/test_review_outcomes.py::test_value_correction_does_not_create_span` | - [ ] |
| 17 | confidence-routed-review | Review Outcomes Become Confirmed Spans | Spans from production review are distinguishable by origin | Given spans from manual annotation, batch acceptance and production review, when inspected, then each records its origin and production-review spans are distinguishable | `tests/test_review_outcomes.py::test_span_origin_is_recorded` | - [ ] |
| 18 | confidence-routed-review | Accumulation Reporting | Accumulation is reported against the current model version | Given a tenant on model version 3 with 40 production-review spans since it was trained, when accumulation is requested, then 40 is reported against version 3 | `tests/test_accumulation_reporting.py::test_accumulation_against_current_version` | - [ ] |
| 19 | confidence-routed-review | Accumulation Reporting | Base-model predictions do not count toward accumulation | Given a tenant with no trained model and 25 production-review spans from base-model predictions, when accumulation is requested, then those 25 are not counted and are recorded distinctly | `tests/test_accumulation_reporting.py::test_base_model_spans_excluded` | - [ ] |
| 20 | confidence-routed-review | Accumulation Reporting | Accumulation growth triggers nothing | Given accumulation growing from 40 to 500, when the figure updates, then no training job is created, queued or submitted and no notification initiates a run | `tests/test_accumulation_reporting.py::test_accumulation_triggers_no_training` | - [ ] |
| 21 | confidence-routed-review | Auto-Accept Audit Sampling | Audit sample is drawn randomly and recorded | Given 500 auto-accepted predictions, when an audit sample is drawn, then it is selected randomly from that population and the sampled identities are recorded | `tests/test_audit_sampling.py::test_audit_sample_random_and_recorded` | - [ ] |
| 22 | confidence-routed-review | Auto-Accept Audit Sampling | Audit agreement rate is recorded | Given a fully reviewed audit sample, when the audit completes, then the agreement rate is recorded with the sample size and the audited model version | `tests/test_audit_sampling.py::test_audit_agreement_rate_recorded` | - [ ] |
| 23 | confidence-routed-review | Auto-Accept Audit Sampling | Audit sampling does not alter unsampled predictions | Given 500 auto-accepted predictions and a sample of 20, when the audit finds some sampled ones incorrect, then the 480 unsampled retain accepted status | `tests/test_audit_sampling.py::test_audit_does_not_alter_unsampled` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Threshold conflation (design.md Decision 1) | Implementer reuses `settings.confidence_threshold` for routing, or lowers it so low-confidence predictions survive — coupling review volume to what analytics, chat and the entity projection see | Confirm two distinct configuration values exist and that routing reads the new one. Scenario 6 must show the extraction threshold unchanged when the review threshold moves, and Scenario 3 must show business consumers unaffected. |
| 2 | Second inference pass (design.md Decision 2) | Implementer adds a dedicated annotation-inference call over the document rather than routing the predictions extraction already produced, creating two paths that can disagree about what the model said | Trace the routing input: it must consume the existing extraction run's output. Grep for any new model-serving call in the routing path. |
| 3 | Span derived from `corrected_value` (design.md Decision 3) | Implementer treats the existing value-correction flow as the source of training spans, or searches the document for the corrected value to find offsets — which fails whenever the correction normalises rather than re-quotes, reintroducing the "answer not in the text" problem from change 1 | Confirm span creation reads only character offsets from the review outcome. Grep the span-creation path for any read of `corrected_value`. Scenario 16 supplies a corrected value that does not match the text and must produce no span. |
| 4 | LLM route bypassing review outcomes (design.md Decision 4) | Implementer has the LLM review job write confirmed spans directly "since it already decided", giving the LLM a privileged unaudited path into training data | Confirm the LLM job writes review outcomes and that span creation is driven only from outcomes. Scenario 12 must assert no span was written directly by the job. |
| 5 | Auto-trigger on accumulation (design.md Non-Goals, Decision 5) | Implementer "helpfully" enqueues a training job, schedules one, or emits a notification that starts one when accumulation crosses a value — the exact behaviour this change and change 6 both exclude | Grep the accumulation path for any training job creation, Celery enqueue, or scheduling call. Scenario 20 must assert nothing is created, queued or submitted as the figure grows. |
| 6 | Base-model accumulation (design.md Decision 5, ADR-008) | Implementer counts spans reviewed from base-model predictions toward the tenant's accumulation figure, inflating it with material that says nothing about whether retraining the tenant's model would help | Confirm the accumulation query filters on a tenant-trained model version and that base-model-served predictions are recorded distinctly. Execute Scenario 19. |
| 7 | LLM review job queue (ADR-006) | Implementer registers the LLM review job on the GPU `training.jobs` queue, coupling I/O-bound review work to the GPU node pool and queueing it behind training runs | Grep the job registration for the queue name; it must be change 1's non-GPU queue with no GPU selector. Confirm `training_service` queue configuration is unchanged in the diff. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-008-base-model-as-default | The base model serves as the default inference model (version 0) when a tenant has no active trained model | Base-model predictions must be routed and reviewable but must not accumulate as tenant-specific training evidence | Confirm the accumulation query excludes base-model-served predictions and records them distinctly. Execute Scenario 19 against a tenant with no trained model. |
| ADR-003-model-serving-topology | Per-tenant model serving topology | Every routed prediction must record the model version that produced it, so accumulation is attributable to a version rather than to "the model" | Confirm the model version is captured at routing time from the serving response, not inferred later. Execute Scenario 7. |
| ADR-006-training-infrastructure | Async Celery + RabbitMQ; GPU workers for training specifically | The LLM review job is I/O-bound and must run on the non-GPU LLM queue established by change 1 | Grep the job registration for its queue name and confirm no GPU node-pool selector. Confirm no `training_service` queue changes in the diff. |
| ADR-001-tenant-data-isolation | Tenant isolation via separate PostgreSQL schemas | The review queue, review outcomes, and accumulation records live in the tenant schema and resolve it as existing endpoints do | Trace schema resolution for each new table against the existing pattern; confirm no cross-tenant query in the routing or accumulation paths. |
| ADR-010-per-entity-type-dataset-threshold | Dataset readiness is per entity type at 200 per type | Accumulation is a delta since last training and is a different quantity from readiness; it must not be presented as a readiness measure or compared to ADR-010's threshold | Confirm the accumulation response contains no readiness language and is not compared against the per-type threshold constant. Confirm no new readiness threshold is introduced. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1 (Business filtering unchanged): existing regression test output, unchanged
- [ ] Scenario 2 (Below-threshold retained): test output asserting the retained prediction with type, value, confidence, offsets and model version
- [ ] Scenario 3 (Retained hidden from consumers): test output asserting exactly 3 entities returned from a 3-above/2-below run
- [ ] Scenario 4 (Auto-accept): test output asserting the prediction is accepted and absent from the queue
- [ ] Scenario 5 (Queued): test output asserting queue membership with recorded confidence 0.62
- [ ] Scenario 6 (Independent thresholds): test output asserting the extraction threshold and business results are unchanged when the review threshold moves
- [ ] Scenario 7 (Model version recorded): test output asserting version 3 on every routed prediction
- [ ] Scenario 8 (Human confirm): test output asserting the confirmed outcome and human route
- [ ] Scenario 9 (Human correct offsets): test output asserting the corrected outcome at 45-58
- [ ] Scenario 10 (Reject): test output asserting the rejected outcome and no span created
- [ ] Scenario 11 (LLM outcome shape): test output asserting one of the three outcome kinds plus the LLM route
- [ ] Scenario 12 (No LLM bypass): test output asserting every span traces to a recorded outcome
- [ ] Scenario 13 (Confirmed → span): test output asserting the span at the predicted offsets
- [ ] Scenario 14 (Corrected → span): test output asserting the span at 45-58 and none at 45-53
- [ ] Scenario 15 (Rejected → no span): test output asserting no span exists
- [ ] Scenario 16 (Value correction ignored): test output asserting no span from a non-matching `corrected_value`
- [ ] Scenario 17 (Origin recorded): test output asserting the three origins are distinguishable
- [ ] Scenario 18 (Accumulation reported): test output asserting 40 against model version 3
- [ ] Scenario 19 (Base-model excluded): test output asserting the 25 base-model spans are excluded and recorded distinctly
- [ ] Scenario 20 (Nothing triggered): test output plus assertion that no training job was created, queued or submitted as accumulation grew
- [ ] Scenario 21 (Audit sample random): test output asserting random selection and persisted sampled identities
- [ ] Scenario 22 (Agreement rate recorded): test output asserting rate, sample size and audited model version stored
- [ ] Scenario 23 (Unsampled untouched): test output asserting 480 predictions retain accepted status

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Only additive schema changes were introduced; no existing table altered destructively
- [ ] Change 4's sampling and agreement-rate logic is reused for audit sampling, not reimplemented — confirmed by reading the call graph
- [ ] No training job creation, enqueue, or scheduling call exists anywhere in this change's diff

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — two distinct thresholds; routing reads the new one; business results unaffected
- [ ] Risk 2 mitigation confirmed — routing consumes existing extraction output; no new model-serving call in the routing path
- [ ] Risk 3 mitigation confirmed — span creation reads offsets only; no read of `corrected_value` in that path
- [ ] Risk 4 mitigation confirmed — LLM job writes outcomes only; span creation driven solely from outcomes
- [ ] Risk 5 mitigation confirmed — no training job creation, enqueue, or scheduling anywhere in the accumulation path
- [ ] Risk 6 mitigation confirmed — accumulation filters on a tenant-trained version; base-model predictions recorded distinctly
- [ ] Risk 7 mitigation confirmed — LLM review job on the non-GPU queue; no GPU selector; `training_service` queue config untouched

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

**Change slug:** confidence-routed-review
**Proposal:** `openspec/changes/confidence-routed-review/proposal.md`
**Spec files reviewed:**

- specs/confidence-routed-review/spec.md
- specs/extraction-service/spec.md

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

- **This change deliberately triggers nothing.** Accumulation is reported and that is all. Change 6 owns the retraining decision and it is human-gated. Reviewer should confirm no training job creation, enqueue, or scheduling call exists anywhere in the diff — this is the single easiest thing for an implementer to add "helpfully" and the single most important thing to keep out.
- **Five measurement and policy questions are unresolved and must be decided before implementation**: the review threshold value, the human-versus-LLM routing policy, how span-level confidence is aggregated from per-token probabilities (this silently determines what lands in the queue and must be stated explicitly), whether a correction re-runs extraction, and audit cadence.
- **A retention bound for below-threshold predictions is required.** This change makes extraction stop discarding them; without a bound on how long or how many are kept, storage grows unboundedly on a large corpus.
- **Unresolved and consequential**: whether a rejected prediction should produce a negative training signal. It is real information that the model was wrong, but representing it means deciding whether that region becomes an explicit `O` or is left unlabeled — which interacts directly with the partial-labeling concern that shaped change 1. Do not decide this casually during implementation.
- The LLM reviewing BERT's output is one model grading another, with potentially correlated blind spots. Recording the review route is what makes LLM-route and human-route agreement comparable; if they diverge materially, the LLM route's weight should be reconsidered.
