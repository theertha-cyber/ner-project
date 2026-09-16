## 1. Prerequisites

- [x] 1.1 Confirm change 4 (`seed-bootstrap`) has landed — a trained tenant model must exist for routing to be meaningful, and this change reuses change 4's random sampling and agreement-rate logic for audit sampling.
- [x] 1.2 Decide the review threshold value and confirm it is configured independently of the business-facing extraction threshold. These answer different questions and must not share a knob.
- [x] 1.3 Decide how span-level confidence is aggregated from BERT's per-token probabilities (minimum, mean, first-token, or other). State the choice explicitly — it silently determines which predictions land in the review queue, and boundary behaviour differs materially between the options.
- [x] 1.4 Decide the human-versus-LLM routing policy (always-LLM-first with human escalation, a confidence band split, or a per-tenant switch).
- [x] 1.5 Decide a retention bound for retained below-threshold predictions — by age, by queue size, or by discarding once reviewed and converted. Unbounded retention is a real storage cost on a large corpus.
- [x] 1.6 Decide whether a rejected prediction produces a negative training signal, and if so whether that region becomes an explicit `O` or is left unlabeled. This interacts directly with the partial-labeling concern from change 1 — do not settle it casually.
- [x] 1.7 Decide the audit sample cadence and volume for the auto-accept path.

## 2. Retain Below-Threshold Predictions

- [x] 2.1 Persist below-threshold predictions with entity type, value, confidence, character offsets, and serving model version, instead of dropping them. Implemented in `run_batch_extraction` in `src/extraction_service/worker.py` rather than `src/extraction_service/api/v1/extraction.py` — see design.md Decision 14 for why the originally named file cannot carry this.
- [x] 2.2 Confirm retained below-threshold predictions remain excluded from extraction results, entity queries, the entity projection, analytics, and chat retrieval. Business consumers must see exactly what they see today. Includes confirming the ad-hoc `/extract` endpoint's filtering behaviour is untouched (design.md Decision 14).
- [x] 2.3 Apply the retention bound decided in task 1.5.
- [x] 2.4 Add `test_below_threshold_predictions_retained` and `test_retained_predictions_hidden_from_consumers` to `tests/test_extraction_confidence_filtering.py`, covering Spec Alignment rows 2-3. Confirm the existing filtering regression suite, `tests/test_extract_confidence_threshold.py`, still passes — that is the file row 1 covers; it was previously misnamed in both artifacts.

## 3. Confidence Routing

- [x] 3.1 Add the review threshold as configuration independent of `settings.confidence_threshold` (design.md Decision 1).
- [x] 3.2 Implement routing over the predictions the extraction run already produced — no second inference pass and no new model-serving call (design.md Decision 2).
- [x] 3.3 Record the serving model version on every routed prediction, captured from the serving response at routing time (ADR-003).
- [x] 3.4 Add a review queue table in the tenant schema holding queued predictions with their offsets, type, confidence, and model version.
- [x] 3.5 Add `tests/test_confidence_routing.py` with `test_high_confidence_auto_accepted`, `test_low_confidence_enters_queue`, `test_review_threshold_independent`, and `test_routed_predictions_record_model_version`, covering Spec Alignment rows 4-7.

## 4. Review Queue Resolution

- [x] 4.1 Add endpoints for a human reviewer to resolve a queued prediction as confirmed, corrected (new offsets and/or entity type), or rejected.
- [x] 4.2 Add an LLM review job on change 1's non-GPU queue — never `training.jobs`, no GPU node-pool selector (ADR-006). It MUST write review outcomes only; it MUST NOT write spans directly (design.md Decision 4).
- [x] 4.3 Record the review route (human or LLM) on every outcome, so route agreement can be compared later.
- [x] 4.4 Implement the routing policy decided in task 1.4.
- [x] 4.5 Add `tests/test_review_queue.py` with `test_human_confirms_prediction`, `test_human_corrects_offsets`, `test_reviewer_rejects_prediction`, `test_llm_review_outcome_structure`, and `test_llm_review_does_not_bypass_outcome_path`, covering Spec Alignment rows 8-12.

## 5. Outcomes Become Spans

- [x] 5.1 Create confirmed spans from confirmed and corrected outcomes, defined by character offsets over the document text. The span-creation path MUST NOT read `corrected_value` (design.md Decision 3).
- [x] 5.2 Record production-review origin on each created span, distinguishable from manual annotation and from change 4's batch acceptance.
- [x] 5.3 Create no span from a rejected outcome, subject to the negative-signal decision from task 1.6.
- [x] 5.4 Add `tests/test_review_outcomes.py` with `test_confirmed_outcome_creates_span`, `test_corrected_outcome_uses_corrected_offsets`, `test_rejected_outcome_creates_no_span`, `test_value_correction_does_not_create_span`, and `test_span_origin_is_recorded`, covering Spec Alignment rows 13-17. The value-correction test MUST supply a `corrected_value` that does not match the document text at those offsets.

## 6. Accumulation Reporting

- [x] 6.1 Record which spans have been included in which training run, so accumulation can be computed as a delta since the current model version was trained. Do NOT create a separate pool table duplicating spans (design.md Decision 5).
- [x] 6.2 Exclude base-model-served predictions from the tenant accumulation figure and record them distinctly (ADR-008).
- [x] 6.3 Add an endpoint reporting the accumulation figure against the current model version. It MUST NOT be presented as, or compared against, dataset readiness (ADR-010).
- [x] 6.4 Verify by inspection that no code path in this change creates, enqueues, schedules, or notifies to start a training job. This is the single most likely unwanted addition (verification.md Risk 5).
- [x] 6.5 Add `tests/test_accumulation_reporting.py` with `test_accumulation_against_current_version`, `test_base_model_spans_excluded`, and `test_accumulation_triggers_no_training`, covering Spec Alignment rows 18-20.

## 7. Auto-Accept Audit Sampling

- [x] 7.1 Implement periodic random sampling over auto-accepted predictions, reusing change 4's sampling and agreement-rate logic rather than reimplementing it.
- [x] 7.2 Route sampled predictions through the same review flow and record the resulting agreement rate with the sample size and audited model version.
- [x] 7.3 Confirm audit sampling never changes the accepted status of predictions outside the drawn sample.
- [x] 7.4 Apply the cadence and volume decided in task 1.7.
- [x] 7.5 Add `tests/test_audit_sampling.py` with `test_audit_sample_random_and_recorded`, `test_audit_agreement_rate_recorded`, and `test_audit_does_not_alter_unsampled`, covering Spec Alignment rows 21-23.

## 8. Frontend Surface

- [x] 8.1 Add a review queue screen listing queued predictions with document context, predicted type, offsets, and confidence, and controls to confirm, correct offsets or type, or reject.
- [x] 8.2 Surface the accumulation figure against the current model version, presented distinctly from dataset readiness so the two are not confused.
- [x] 8.3 Confirm the existing extraction value-correction UI is unchanged and continues to work for its own purpose.

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 9.5 Grep the full diff for training job creation, Celery enqueue to a training queue, or scheduling calls, and confirm there are none.
- [x] 9.6 Confirm business-facing extraction output is byte-identical before and after this change for a fixed document and model version.
- [x] 9.7 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.8 Run `openspec validate confidence-routed-review --type change --strict` and confirm it exits clean before archive.
