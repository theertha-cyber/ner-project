## 1. Prerequisites

- [ ] 1.1 Confirm the three `training_eligible_at` sources exist: `annotation_tasks` (Phase 3, landed), `prelabel_batches` (`automated-annotation-guided-workflow`), `annotation_imports` (`import-annotation-training-eligibility`).
- [ ] 1.2 Confirm span provenance markers are available for manual / automated / import (batch-acceptance provenance from `seed-bootstrap`; import source marker from `import-annotation-training-eligibility`).

## 2. Accumulation service

- [ ] 2.1 `src/annotation_service/services/accumulation.py`: extend `accumulation_report` to group the unconsumed accumulated span set by source (`manual` / `automated` / `import`), reading existing provenance markers — no schema change. Guarantee `sum(by_source) == spans_accumulated`. (Spec row 3)
- [ ] 2.2 Add a helper computing the training-eligibility overview: per source, count units with `training_eligible_at` set that are not yet consumed — manual/automated via the consumed-spans record for the serving version; import via "no completed training run with `completed_at` after the file's `training_eligible_at`". Return `{count, latest_at}` per source. (Spec rows 6, 7, 9)

## 3. Decision endpoint

- [ ] 3.1 `src/annotation_service/api/v1/retraining_decision.py`: add `by_source` and `eligible_overview` to the response, additively — existing fields (`spans_accumulated`, `by_entity_type`, `serving_model_version`, `has_trained_model`, `training_run_in_flight`, no-model branch) unchanged. (Spec rows 1, 2, 4, 5)
- [ ] 3.2 Confirm the endpoint imports no readiness threshold constant and enqueues/approves nothing. (Spec rows 5, 8; Risk 2)

## 4. Tests

- [ ] 4.1 `tests/test_retraining_decision.py` / `tests/test_accumulation_reporting.py`: `test_accumulation_per_source`, `test_eligible_overview_counts`, `test_consumed_units_drop_off`, `test_overview_is_report_only`, `test_import_unconsumed_by_run_time`, plus re-run the carried-over `test_accumulation_against_serving_version`, `test_accumulation_per_entity_type`, `test_no_trained_model_distinct`, `test_accumulation_not_readiness`. (Spec rows 1–9)
- [ ] 4.2 Assert `sum(by_source.values()) == spans_accumulated` in the per-source test. (Risk 3)

## 5. Portal

- [ ] 5.1 `src/portal/src/hooks/use-retraining.ts` + `src/portal/src/types/human-gated-retraining.ts`: add `by_source` and `eligible_overview` to `RetrainingDecision`.
- [ ] 5.2 `src/portal/src/components/retraining/RetrainingDecisionPage.tsx`: render the per-source accumulation split and the eligibility overview; keep the existing per-entity-type breakdown and the "Request a retrain → System Admin approval" action.
- [ ] 5.3 `/annotate/automated/layout.tsx` stepper: derive step 4 state from `eligible_overview` (any source > 0 ⇒ retrain step is `ready`) instead of the current `spans_accumulated > 0` heuristic.
- [ ] 5.4 `/annotate/manual`, `/annotate/import`, `/annotate/automated/retrain` landing/step pages: show a consistent "Training: Eligible ({n} waiting) — [Request training]" block sourced from `eligible_overview`, with the single `POST /api/v1/training-retrain-requests` call. No "review annotations" action anywhere in this block.
- [ ] 5.5 Portal tests: `RetrainingDecisionPage.test.tsx` for the new sections; a landing-page test asserting the eligibility block and that "Request training" is always shown when a source is eligible.

## 6. Verification

- [ ] 6.1 Run `tests/test_retraining_decision.py`, `tests/test_accumulation_reporting.py`, `tests/test_no_auto_retraining.py`, and the portal retraining suite; record in verification.md §5 / §7.
- [ ] 6.2 Complete §4 structural + edge-case evidence.
- [ ] 6.3 Human reviewer signs §6.
