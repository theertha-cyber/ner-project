## 1. Prerequisites

- [ ] 1.1 Confirm change 5 (`confidence-routed-review`) has landed — this change writes the consumed-span record change 5 defines and reads, and surfaces the accumulation figure change 5 computes.
- [ ] 1.2 Decide who may request a retrain (Tenant Admin, System Admin, or both), consistent with the existing role model. Approval is already System Admin only, so the request may reasonably be broader.
- [ ] 1.3 Decide whether a retrain may be requested when accumulation is zero. Blocking prevents a pointless run; allowing preserves retraining after a hyperparameter change rather than a data change.
- [ ] 1.4 Decide how prominently the promotion surface conveys that metrics from runs over materially different datasets are not directly comparable, and what counts as "materially different".
- [ ] 1.5 Confirm the per-entity-type breakdown is sufficient context for the retrain decision, or determine what else the decision actually requires.

## 2. Record Consumed Spans

- [ ] 2.1 Record the set of confirmed spans consumed by a training run, keyed by tenant and by the model version the run produced, writing into the record change 5 defines. Do NOT duplicate span rows (design.md Decision 1).
- [ ] 2.2 Place the write in the run-completion path only. It MUST NOT fire at submission, at approval, or on failure (verification.md Risk 2).
- [ ] 2.3 Confirm accumulation computed by change 5 resets to zero against the newly produced version once the record is written, and is unchanged while a run is in flight.
- [ ] 2.4 Add `tests/test_consumed_spans.py` with `test_completed_run_records_consumed_spans`, `test_accumulation_resets_after_run`, `test_rejected_job_records_nothing`, `test_failed_run_records_nothing`, and `test_accumulation_unchanged_during_run`, covering Spec Alignment rows 1-5.

## 3. Retraining Decision Surface

- [ ] 3.1 Add an endpoint returning the accumulation figure for the tenant's currently serving model version, broken down per entity type, with the serving version identifier.
- [ ] 3.2 Return a distinct no-trained-model state for a tenant served by the base model, rather than an accumulation figure of zero (design.md Decision 5, ADR-008).
- [ ] 3.3 Label accumulation distinctly from dataset readiness and do not compare it against the per-entity-type readiness threshold. Introduce no new threshold constant (ADR-010).
- [ ] 3.4 Add `tests/test_retraining_decision.py` with `test_surface_reports_accumulation_and_version`, `test_accumulation_broken_down_per_entity_type`, `test_no_trained_model_shown_distinctly`, and `test_accumulation_not_presented_as_readiness`, covering Spec Alignment rows 6-9.

## 4. Manual Retrain Request

- [ ] 4.1 Add a retrain request endpoint that creates an ordinary training job through the existing submission path, landing in `pending_approval`. It MUST NOT enqueue a Celery task, MUST NOT create the job already queued, and MUST NOT bypass approval (design.md Decision 2, ADR-006).
- [ ] 4.2 Confirm the request carries no hyperparameters and that hyperparameters continue to be set at approval time (ADR-009).
- [ ] 4.3 Apply the requester-role decision from task 1.2 and the zero-accumulation decision from task 1.3.
- [ ] 4.4 Confirm the existing `training-approval` approve and reject paths handle a retrain-requested job identically to any other job, with no branching on how the job originated.
- [ ] 4.5 Add `tests/test_retrain_request.py` with `test_request_creates_pending_approval_job`, `test_requested_retrain_follows_approval_flow`, `test_requested_retrain_can_be_rejected`, and `test_request_carries_no_hyperparameters`, covering Spec Alignment rows 10-13.

## 5. No Automatic Initiation

- [ ] 5.1 Verify by inspection that no code path reachable from the accumulation figure, a threshold comparison, a schedule, or a training run completion creates, enqueues, or schedules a training job.
- [ ] 5.2 Verify that run completion does not promote the version it produced, and that the previously promoted version continues serving until a human promotes.
- [ ] 5.3 Confirm no scheduler registration, cron entry, or timer capable of initiating a training job exists in this change's diff.
- [ ] 5.4 Add `tests/test_no_auto_retraining.py` with `test_large_accumulation_creates_no_job`, `test_completion_does_not_chain_run`, `test_completion_does_not_self_promote`, and `test_promotion_requires_human_action`, covering Spec Alignment rows 14-17. These MUST exercise the real paths, not stubs.

## 6. Promotion Decision Evidence

- [ ] 6.1 Add an endpoint returning a completed version's evaluation metrics alongside the currently promoted version's, with the confirmed span count each was trained on.
- [ ] 6.2 Indicate when the two runs used materially different dataset sizes, per the definition decided in task 1.4.
- [ ] 6.3 Handle the case of no currently promoted version by returning the candidate's metrics and indicating there is nothing to compare against.
- [ ] 6.4 Confirm the response contains no comparative verdict, ranking, or promotion recommendation (design.md Decision 4).
- [ ] 6.5 Add `tests/test_promotion_evidence.py` with `test_candidate_and_current_metrics_presented`, `test_different_dataset_sizes_flagged`, `test_no_verdict_produced`, and `test_no_promoted_version_to_compare`, covering Spec Alignment rows 18-21.

## 7. Frontend Surfaces

- [ ] 7.1 Add the retraining decision surface showing the per-entity-type accumulation breakdown against the serving version, with a request-retrain action, and the distinct no-trained-model state.
- [ ] 7.2 Add the promotion decision surface showing candidate and current metrics with their dataset sizes and the comparability indication, without any recommendation.
- [ ] 7.3 Confirm the existing promote control and the existing training jobs and approval screens are unchanged.

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Grep the full diff for scheduler registrations, cron entries, timers, and any comparison of an accumulation figure against a constant, and confirm there are none.
- [ ] 8.6 Confirm `training-approval` and `model-registry` promote/demote code paths are unchanged in the diff.
- [ ] 8.7 Run one full loop end to end on a tenant: accumulate reviewed spans, observe the figure, request a retrain, approve it, let it complete, confirm the figure resets against the new version, then promote using the evidence surface.
- [ ] 8.8 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 8.9 Run `openspec validate human-gated-retraining --type change --strict` and confirm it exits clean before archive.
