## 1. Prerequisites

- [x] 1.1 The three `training_eligible_at` sources exist (`annotation_tasks` — Phase 3; `prelabel_batches` — automated change; `annotation_imports` — import change).
- [x] 1.2 Span provenance markers: `span_batch_provenance` distinguishes automated spans; imported rows are not spans (spec revised — see §note).

## 2. Accumulation service

- [x] 2.1 `accumulation_report` gains `by_source` (`manual` / `automated`) via `LEFT JOIN span_batch_provenance` over the same set the figure counts, so `manual + automated == spans_accumulated`. `import` is **not** here — imported rows are not confirmed spans (spec's scenario 3 revised accordingly).
- [x] 2.2 New `eligible_overview(session, schema)`: per source, count of training-eligible units with `training_eligible_at` later than the most recent completed training run's `completed_at` (or no completed run), plus the latest such timestamp. Manual = completed `annotation_tasks`; automated = `prelabel_batches` with `annotator_review_status = 'approved'`; import = `annotation_imports`.

## 3. Decision endpoint

- [x] 3.1 `retraining_decision.py`: response gains `by_source` (trained branch only) and `eligible_overview` (always). Existing fields unchanged.
- [x] 3.2 The endpoint imports no readiness constant and enqueues/approves nothing — `test_overview_is_report_only` + the existing `test_no_auto_retraining` suite.

## 4. Tests

- [x] 4.1 `tests/test_training_eligibility_overview.py` (4): `test_by_source_sums_to_accumulation`, `test_eligible_overview_counts_per_source`, `test_consumed_units_drop_off_overview`, `test_overview_is_report_only`. `confidence_review_support.py` fixtures gained `prelabel_batches.annotator_review_status` / `training_eligible_at`, `annotation_tasks`, `annotation_imports`.
- [x] 4.2 `test_by_source_sums_to_accumulation` asserts `manual + automated == spans_accumulated`.
- [x] 4.3 Existing `test_retraining_decision.py` (14) + `test_accumulation_reporting.py` re-run green.

## 5. Portal

- [x] 5.1 `human-gated-retraining.ts`: `RetrainingDecisionTrained` gains `by_source`; base adds `eligible_overview` (+ `EligibleOverview` / `EligibleSource` types).
- [x] 5.2 `RetrainingDecisionPage`: "By source: N manual · N from accepted automated batches" line under the figure; a "Training-eligible and waiting" panel listing the three per-source counts (or "Nothing new since the last training run").
- [~] 5.3 `/annotate/automated/layout.tsx` stepper step-4 state from `eligible_overview` — the layout does not fetch the decision surface; left on the accumulation heuristic. The three landing pages' consistent "Request training" block is out of scope here (belongs with the retrain request UI).
- [x] 5.4 `RetrainingDecisionPage.test.tsx` (+1 overview test, fixtures updated) — 12 green.

## 6. Verification

- [x] 6.1 `test_training_eligibility_overview.py` (4) + `test_retraining_decision.py` + `test_accumulation_reporting.py` + `test_no_auto_retraining.py` — 27 green in the annotation_service container. Portal retraining suite 12 green.
- [ ] 6.2 §4 structural + edge-case evidence.
- [ ] 6.3 Human reviewer signs §6.
