## 1. Database

- [x] 1.1 Add migration `046_training_job_source_scope.py`: `source_scope VARCHAR(16)` with a
  `CHECK` constraint (`manual`, `automated`, `import`, or `NULL`) on `{schema}.training_jobs`
  across every tenant schema via `apply_to_all_tenant_schemas`.
- [x] 1.2 Run the migration against the dev database and confirm the column exists on every
  tenant schema (including `tenant_template`, so new tenants get it) and that the `CHECK`
  constraint rejects an out-of-vocabulary value.

## 2. Backend: annotation export

- [x] 2.1 Add a `source` query parameter to `GET /api/v1/annotation-export` (`manual`,
  `automated`, `import`), 422 on an unrecognized value.
- [x] 2.2 `source=automated`: INNER JOIN `span_batch_provenance`. `source=manual`: LEFT JOIN with
  `bp.span_id IS NULL`. `source=import`: skip the spans query entirely. Omitted: unchanged
  tenant-wide behavior.
- [x] 2.3 Gate the `imported_annotations` block to `source in (None, "import")`.

## 3. Backend: training-jobs submission and gating

- [x] 3.1 Add `source_scope` to `TrainingJobCreate` and `TrainingJobResponse`.
- [x] 3.2 `TrainingJobRepository.create` persists `source_scope` and returns it.
- [x] 3.3 `create_training_job` builds a source-scoped span join/clause for the entity-count and
  per-entity-type gates; both gates are skipped entirely when `source_scope == "import"`.
- [x] 3.4 `_row_to_response` includes `source_scope`.

## 4. Backend: training worker

- [x] 4.1 `fine_tune_model` reads `source_scope` alongside `status` from `training_jobs` and
  passes it to `_load_annotated_dataset`.
- [x] 4.2 `_load_annotated_dataset` forwards `source_scope` as the export call's `source` query
  parameter, omitting the parameter when `source_scope` is `None`.

## 5. Frontend: types, hook, submit slide-over

- [x] 5.1 Add `SourceScope` type and `source_scope` to the `TrainingJob` interface;
  `SubmitJobPayload` gains an optional `sourceScope`.
- [x] 5.2 `useSubmitTrainingJob` includes `source_scope` in the POST body only when given.
- [x] 5.3 `SubmitJobSlideover` gains a `sourceScope` prop: when set, shows a locked read-only
  "Training source: X" line; when unset, shows a required radio choice and keeps submit disabled
  until one is chosen. The span preflight fetch is scoped to the effective source and shows a
  neutral placeholder until one is set.
- [x] 5.4 The Training Jobs page reads `?source=` from the URL and auto-opens the slide-over with
  that source locked.

## 6. Frontend: workflow hand-offs

- [x] 6.1 Manual annotation landing's "Train model" action navigates to
  `/training-jobs?source=manual`.
- [x] 6.2 Automated flow's `BatchAcceptancePage` "Train model" action navigates to
  `/training-jobs?source=automated`.

## 7. Frontend: Manual landing three-step workflow

- [x] 7.1 Replace the Manual landing's single "Annotation workspace" work card (for
  `tenant_admin`) with three ordered cards: "1. Upload documents" → `/documents?upload=1`,
  "2. Define entity types" → `/entity-types`, "3. Annotation workspace" → `/annotation`. Leave
  the `annotator` role's single-card view unchanged.
- [x] 7.2 Add an optional `workCardsLabel` prop to `AnnotateLanding` (default "Where the work
  is") and pass "Your workflow" from the Manual landing for the `tenant_admin` case.
- [x] 7.3 The Documents page recognizes `?upload=1` and auto-opens the upload dialog on mount.

## 8. Tests

- [x] 8.1 New `tests/test_annotation_export_source_scope.py`: manual excludes promoted spans,
  automated includes only promoted spans, import returns only imported rows and skips spans,
  omitted source combines everything, invalid source is rejected.
- [x] 8.2 Extend `tests/test_training_jobs_api.py`: `source_scope` stored and returned, defaults
  to null, automated/manual scoped gates count only their own spans, import scope skips the
  span gates, invalid `source_scope` rejected. Add `source_scope`/`span_batch_provenance` to the
  file's local fixture DDL.
- [x] 8.3 Add `source_scope VARCHAR(16)` to `tests/confidence_review_support.py`'s shared
  `training_jobs` fixture DDL (13 other test files build on this fixture and now insert through
  the same column list).
- [x] 8.4 Fix `tests/test_training_worker.py`'s mocked `training_jobs` row shape
  (`(status, source_scope)` 2-tuples instead of 1-tuples) and its `_load_annotated_dataset`
  monkeypatch signatures, matching the worker's new query/call shape.
- [x] 8.5 Update/add portal tests: `submit-job-slideover.test.tsx` and
  `.readiness.test.tsx` (locked-source rendering, required-picker gating, effective-source span
  fetch), `use-submit-training-job.test.tsx` (source_scope in POST body), `job-card`/`job-list`/
  `job-detail-panel.test.tsx` fixtures (`source_scope: null`), `BatchAcceptancePage.test.tsx` and
  `annotate/manual/page.test.tsx` (new navigation targets), new `annotate/manual/page.test.tsx`
  three-step-workflow assertions, new `documents/page.test.tsx` (`?upload=1` auto-open).

## 9. Verification & Evidence

- [x] 9.1 Run every test in § 8 against a real database (postgres-test/`ner_test` for backend,
  the `ner-portal-test` container for frontend) and confirm all pass.
- [x] 9.2 Confirm no regression in the pre-existing, unrelated test baseline (6 known-failing
  frontend files; 2 known-failing training-worker environment gaps; 5 known-failing
  entity_definitions-schema-drift tests; 1 known-failing training-jobs 404-vs-500 gap) — all
  pre-date this change and are tracked separately, not introduced by it.
- [x] 9.3 Rebuild and restart `annotation_service`, `celery_worker_annotation_llm`,
  `training_service`, and `portal`; run migration `046` via `db-init`.
- [x] 9.4 Live-verify in the browser: Manual landing's three-step workflow renders in order and
  each card navigates correctly, including the upload-dialog auto-open; Manual's "Train model"
  routes to `/training-jobs?source=manual` and auto-opens the slide-over with the source locked.
- [ ] 9.5 Live-verify the Automated flow's "Train model" → `/training-jobs?source=automated`
  end-to-end in the browser (implemented and unit-tested; not yet re-confirmed live in this
  session after the latest rebuild).
- [ ] 9.6 Run `openspec validate manual-training-data-source-scoping --type change --strict`
  (done) and `openspec archive manual-training-data-source-scoping --yes`.
