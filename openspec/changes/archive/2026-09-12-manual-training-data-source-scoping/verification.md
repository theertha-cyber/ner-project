# Verification Plan

**Change:** manual-training-data-source-scoping
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | annotation-workspace | Annotation Export | Export annotation dataset | tests/test_annotation_export_offsets.py, tests/test_annotation_export_windowing.py (pre-existing, unmodified) | [x] |
| 2 | annotation-workspace | Annotation Export | A document exceeding the window budget produces multiple records | tests/test_annotation_export_windowing.py::test_long_document_produces_multiple_records | [x] |
| 3 | annotation-workspace | Annotation Export | Consecutive windows overlap | tests/test_annotation_export_windowing.py::test_consecutive_windows_overlap | [x] |
| 4 | annotation-workspace | Annotation Export | An entity crossing a window boundary is complete in at least one window | tests/test_annotation_export_windowing.py::test_boundary_entity_complete_in_one_window | [x] |
| 5 | annotation-workspace | Annotation Export | Tags align correctly across a newline separator | tests/test_annotation_export_offsets.py::test_tags_align_across_newline | [x] |
| 6 | annotation-workspace | Annotation Export | Tags align correctly across repeated spaces and tabs | tests/test_annotation_export_offsets.py::test_tags_align_across_tabs_and_double_spaces | [x] |
| 7 | annotation-workspace | Annotation Export | Export ignores a stale stored bio_tags value | tests/test_annotation_export_offsets.py::test_stored_bio_tags_ignored | [x] |
| 8 | annotation-workspace | Annotation Export | Export with entity type filter | (pre-existing, unmodified by this change) | [x] |
| 9 | annotation-workspace | Annotation Export | Export for specific documents only | (pre-existing, unmodified by this change) | [x] |
| 10 | annotation-workspace | Annotation Export | Imported annotation rows are passed through unwindowed | tests/test_annotation_export_windowing.py::test_imported_rows_not_windowed | [x] |
| 11 | annotation-workspace | Annotation Export | Manual source excludes automated-promoted spans | tests/test_annotation_export_source_scope.py::test_manual_source_excludes_automated_promoted_spans | [x] |
| 12 | annotation-workspace | Annotation Export | Automated source includes only promoted spans | tests/test_annotation_export_source_scope.py::test_automated_source_includes_only_promoted_spans | [x] |
| 13 | annotation-workspace | Annotation Export | Import source returns only imported rows and skips spans entirely | tests/test_annotation_export_source_scope.py::test_import_source_returns_only_imported_rows_and_skips_spans | [x] |
| 14 | annotation-workspace | Annotation Export | Omitting source combines every source | tests/test_annotation_export_source_scope.py::test_omitted_source_combines_everything | [x] |
| 15 | annotation-workspace | Annotation Export | An invalid source value is rejected | tests/test_annotation_export_source_scope.py::test_invalid_source_is_rejected | [x] |
| 16 | training-jobs | Submit training job | Submit a valid training job | tests/test_training_jobs_api.py::test_submit_valid_job_returns_run_number_and_run_name | [x] |
| 17 | training-jobs | Submit training job | Submit training job with insufficient entities | tests/test_training_jobs_api.py::test_submit_insufficient_entities_422 | [x] |
| 18 | training-jobs | Submit training job | Submit training job as non-admin | tests/test_training_jobs_api.py::test_submit_as_non_admin_403 | [x] |
| 19 | training-jobs | Submit training job | Submit training job with invalid hyperparameters | tests/test_training_jobs_api.py::test_submit_with_hyperparameters_is_ignored_or_rejected | [x] |
| 20 | training-jobs | Submit training job | Automated-scoped submission gates only on promoted spans | tests/test_training_jobs_api.py::test_automated_scope_gate_counts_only_promoted_spans | [x] |
| 21 | training-jobs | Submit training job | Manual-scoped submission excludes promoted spans from its gate | tests/test_training_jobs_api.py::test_manual_scope_gate_excludes_promoted_spans | [x] |
| 22 | training-jobs | Submit training job | Import-scoped submission skips the span-based gates entirely | tests/test_training_jobs_api.py::test_import_scope_skips_span_gates_entirely | [x] |
| 23 | training-jobs | Submit training job | An invalid source_scope value is rejected | tests/test_training_jobs_api.py::test_invalid_source_scope_rejected | [x] |
| 24 | training-worker | Load annotated dataset | Dataset loads successfully | tests/test_training_worker.py::TestLoadAnnotatedDataset::test_parses_jsonl_lines (pre-existing, unmodified) | [x] |
| 25 | training-worker | Load annotated dataset | Export returns no data | tests/test_training_worker.py::TestLoadAnnotatedDataset::test_empty_response_raises_error (pre-existing, unmodified) | [x] |
| 26 | training-worker | Load annotated dataset | Dataset too small to form an evaluation split | tests/test_training_worker.py::TestDatasetSplitGuard::test_guard_fails_the_job_before_any_training | [x] |
| 27 | training-worker | Load annotated dataset | Dataset large enough to split proceeds | tests/test_training_worker.py::TestDatasetSplitGuard (pre-existing unit test, unmodified) | [x] |
| 28 | training-worker | Load annotated dataset | Annotation service URL defaults to the correct internal port | tests/test_training_worker.py::test_default_url_used_when_env_var_unset (pre-existing, unmodified) | [x] |
| 29 | training-worker | Load annotated dataset | Annotation service URL is overridable via environment variable | tests/test_training_worker.py::test_override_url_via_env_var (pre-existing, unmodified) | [x] |
| 30 | training-worker | Load annotated dataset | The job's source_scope is forwarded to the export call | tests/test_training_worker.py::TestFineTuneRetryGuard (make_mock_engine now asserts on the `(status, source_scope)` row shape); exercised indirectly by TestLabelListPersistedInMetrics and TestDatasetSplitGuard, which both now pass `source_scope` through their `_get_sync_engine`/`_load_annotated_dataset` mocks | [x] |
| 31 | training-worker | Load annotated dataset | A job with no source_scope combines every source | Same tests as row 30, with `source_scope=None` (the default in every existing fixture not explicitly setting one) | [x] |
| 32 | training-jobs-screen | Submit slide-over source scope | Locked source shows read-only text, not a picker | src/portal/.../submit-job-slideover.test.tsx::"shows a locked source label with no picker when sourceScope is given" | [x] |
| 33 | training-jobs-screen | Submit slide-over source scope | Generic entry point requires an explicit source choice | src/portal/.../submit-job-slideover.test.tsx::"requires a source choice before submitting when none is given" | [x] |
| 34 | training-jobs-screen | Submit slide-over source scope | Choosing a source unlocks the preflight check and submission | src/portal/.../submit-job-slideover.test.tsx::"unlocks submit and the span preflight once a workflow is picked" | [x] |
| 35 | training-jobs-screen | Submit slide-over source scope | Submitting sends the effective source_scope | src/portal/.../use-submit-training-job.test.tsx (all 3 tests) + submit-job-slideover.test.tsx::"renders no hyperparameter inputs and submits a hyperparameter-free body" (asserts `source_scope: "automated"` in the POST body) | [x] |
| 36 | training-jobs-screen | Submit slide-over source scope | Arriving with a source query parameter auto-opens the slide-over | Implemented in src/portal/src/app/(auth)/training-jobs/page.tsx (`lockedSourceScope` + `useEffect`); verified live in the browser (§ Evidence Log) — no dedicated unit test written for the page-level auto-open effect | [~] |
| 37 | manual-annotation-landing | Workflow Steps | only the workspace card is shown (annotator) | src/portal/.../annotate/manual/page.test.tsx::"annotator sees only the workspace card, not the upload/entity-type steps" | [x] |
| 38 | manual-annotation-landing | Workflow Steps | tenant_admin sees the three-step workflow in order | src/portal/.../annotate/manual/page.test.tsx::"tenant_admin sees the three-step workflow in order..."; live-verified in the browser (§ Evidence Log) | [x] |
| 39 | manual-annotation-landing | Train Model Hand-off | CTA appears once training material exists | src/portal/.../annotate/manual/page.test.tsx::"tenant_admin sees the Train model CTA and it routes to /training-jobs" | [x] |
| 40 | manual-annotation-landing | Train Model Hand-off | CTA is absent with nothing annotated | src/portal/.../annotate/manual/page.test.tsx (pre-existing scenario, unmodified) | [x] |
| 41 | manual-annotation-landing | Train Model Hand-off | CTA is never shown to an annotator | src/portal/.../annotate/manual/page.test.tsx::"annotator sees only their own completed count..." | [x] |
| 42 | seed-bootstrap | Batch Pre-labeling Screen Shows Both Stages Persistently | Both stages remain visible once the initial batch is approved and a large batch exists | src/portal/.../BatchAcceptancePage.test.tsx::"shows a Train model action once the large batch finishes..." | [x] |
| 43 | seed-bootstrap | (same requirement) | The large-batch section is visible but locked before the initial batch is approved | src/portal/.../BatchAcceptancePage.test.tsx::"does not unlock stage 2 while the initial batch is unreviewed" | [x] |
| 44 | seed-bootstrap | (same requirement) | The large-batch section unlocks its picker once the initial batch is approved | src/portal/.../BatchAcceptancePage.test.tsx::"keeps the approved initial batch's status visible while unlocking the large-batch picker" | [x] |
| 45 | seed-bootstrap | (same requirement) | A notification fires when each stage completes | src/portal/.../BatchAcceptancePage.test.tsx::"toasts exactly once, on the transition to annotator-approved..." | [x] |
| 46 | seed-bootstrap | (same requirement) | The large-batch picker stays available after a previous large batch has already completed | src/portal/.../BatchAcceptancePage.test.tsx::"shows a Train model action once the large batch finishes..." (same test asserts "Most recent large batch" heading + picker) | [x] |
| 47 | seed-bootstrap | (same requirement) | Starting another large batch is disabled while one is already running | src/portal/.../BatchAcceptancePage.test.tsx::"disables starting another large batch while one is already running..." | [x] |
| 48 | seed-bootstrap | (same requirement) | Train model navigates to the Automated flow's own training entry point | src/portal/.../BatchAcceptancePage.test.tsx::"shows a Train model action once the large batch finishes..." (asserts `mockPush` called with `/training-jobs?source=automated`) | [x] |
| 49 | portal-documents | Upload deep link | Arriving with ?upload=1 opens the uploader | src/portal/.../documents/page.test.tsx::"auto-opens the uploader when linked with ?upload=1" | [x] |
| 50 | portal-documents | Upload deep link | Arriving with no upload parameter leaves the uploader closed | src/portal/.../documents/page.test.tsx::"keeps the uploader closed by default" | [x] |
| 51 | portal-documents | Upload deep link | An unrelated query parameter does not open the uploader | src/portal/.../documents/page.test.tsx::"does not auto-open the uploader for an unrelated query param" | [x] |

> Row 36 is marked `[~]` (partial): the page-level `?source=` → auto-open wiring is implemented
> and was confirmed live in the browser (both `?source=manual` and clicking through from the
> Manual landing page), but no dedicated unit test isolates the `useEffect` itself — the existing
> page test suite for `/training-jobs` doesn't cover query-param-driven auto-open. Documented as
> a disclosed gap rather than a fabricated pass.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Span provenance classification (`span_batch_provenance`) | Assuming a span with no provenance row is "manual" without checking that every non-automated origin (workspace annotation, review-queue confirmation) truly leaves no such row | Confirmed by reading `039_seed_bootstrap.py`'s own migration docstring ("Absence of a row means individual review, which is what every pre-existing span is") and by `accumulation.py`'s pre-existing `by_source` breakdown using the identical join — this change does not invent a new classification, it reuses the one already in production |
| 2 | Import data never touching `spans` | Assuming `imported_annotations` is a wholly separate table rather than a view or trigger-populated mirror of `spans` | Confirmed by reading `014_add_imported_annotations_table.py` — it is a standalone table with its own `tokens`/`tags` array columns, never joined to or populated from `spans` |
| 3 | `NER_MIN_TRAINING_ENTITIES` / `NER_MIN_ENTITIES_PER_TYPE` defaults | Assuming these env vars default to some specific nonzero number (e.g. the spec's old, stale "500") | Read directly from `training_jobs.py`: both default to `"0"` via `os.environ.get(..., "0")`, i.e. inert unless explicitly configured; the spec delta says "the configured minimum," not a hardcoded number |
| 4 | Backward compatibility of omitted `source_scope` | Assuming existing jobs/rows with `source_scope IS NULL` silently break | Verified: every gate and the export filter explicitly branch on `None`/absent to mean "combine everything," matching pre-change behavior exactly; the migration adds the column as nullable with no backfill required |
| 5 | Test fixture drift across 13 files sharing `confidence_review_support.py` | Adding a NOT NULL or defaulted column to the shared fixture's `training_jobs` DDL could silently change other tests' assertions | Added `source_scope VARCHAR(16)` as nullable with no default; reran all 13 dependent test files (`test_accumulation_reporting.py` through `test_training_eligibility_overview.py`) and confirmed the only failures are 5 pre-existing, unrelated `entity_definitions.value_kind`-missing-column failures (tracked separately) |
| 6 | Readiness panel scoping | Implying the per-entity-type readiness panel in the submit slide-over is scoped to the chosen source | It is explicitly NOT scoped — the panel predates source scoping (ADR-010) and stays tenant-wide; the slide-over UI shows a disclaimer line ("Tenant-wide readiness (not scoped to the workflow above)") and this is called out as an accepted limitation in the proposal, not silently glossed over |
| 7 | `system-admin-sets-training-params` overlap | The "Submit training job" requirement this change modifies already reflects hyperparameter-free submission (per an unarchived-but-implemented prior change) — risk of silently re-introducing stale hyperparameter-accepting text | The MODIFIED delta in this change was written against the actual running code (verified: `submit-job-slideover.tsx` renders zero hyperparameter inputs, `TrainingJobCreate` accepts only `source_scope`), not against the stale canonical spec text; the unarchived prior change is flagged separately for its own archive |

---

## 3. Pattern & ADR Compliance

- **ADR-009 (human-gated training approval):** `source_scope` is set at submission time by the
  tenant admin; hyperparameters remain a System Admin concern set at approval time. This change
  adds no field to the approval request and does not touch `approve_training_job`.
- **ADR-010 (per-entity-type readiness is advisory, not a gate):** The submit slide-over's
  per-entity-type readiness panel is left tenant-wide and non-blocking; this change does not
  convert it into a hard gate or scope it to source, consistent with ADR-010's "advisory only"
  stance.
- **Manual/Automated/Import independence (explicit product direction this session):** every
  gate, export filter, and hand-off link in this change resolves to exactly one of the three
  workflows or "all," never a partial/ambiguous blend.

---

## 4. Evidence Log

- **Backend — annotation-export source filter:** `tests/test_annotation_export_source_scope.py`
  (5 new tests) plus the pre-existing `tests/test_annotation_export_offsets.py` (3 tests) and
  `tests/test_annotation_export_windowing.py` (4 tests) — 12/12 passed against a real
  `postgres-test`/`ner_test` database, run inside the `annotation_service` container after
  rebuilding it with the current `export.py`.
- **Backend — training-jobs gating:** `tests/test_training_jobs_api.py` — 28/29 passed (the one
  failure, `test_system_admin_get_job_with_wrong_tenant_id_404`, is a pre-existing gap unrelated
  to source scoping — the endpoint 500s instead of 404ing when a system_admin passes a
  never-created tenant_id — tracked separately).
- **Backend — training worker:** `tests/test_training_worker.py` — 22/24 passed in isolation.
  The 2 remaining failures (`TestOnnxExport::test_onnx_export_mock_verifies_export_call`,
  `TestMlflowModelLogging::test_mlflow_transformers_log_model_succeeds`) are pre-existing
  environment gaps (module-level `torch` not imported in `worker.py`; missing `tensorflow`/
  `transformers` Flax class in this container's dependency set) — confirmed unrelated by
  inspecting both tests, neither references `training_jobs`, `source_scope`, or the export
  endpoint.
- **Backend — shared fixture regression sweep:** all 13 test files depending on
  `tests/confidence_review_support.py` (`test_accumulation_reporting.py`,
  `test_annotation_export_source_scope.py`, `test_audit_sampling.py`, `test_confidence_routing.py`,
  `test_consumed_spans.py`, `test_extraction_confidence_filtering.py`, `test_no_auto_retraining.py`,
  `test_promotion_evidence.py`, `test_retrain_request.py`, `test_retraining_decision.py`,
  `test_review_outcomes.py`, `test_review_queue.py`, `test_training_eligibility_overview.py`) —
  121/126 passed; the 5 failures are a pre-existing, unrelated `entity_definitions.value_kind`
  missing-column gap in the fixture schema (tracked separately), confirmed by grep to have zero
  reference to `training_jobs`/`source_scope`/`annotation-export`.
- **Frontend:** targeted vitest run of every touched/added file
  (`training-jobs/*`, `submit-job-slideover*`, `use-submit-training-job`, `BatchAcceptancePage`,
  `annotate/manual/page`, `documents/page`) — 0 failures after fixes; full portal suite —
  106/112 files passed, matching exactly the pre-existing 6-file baseline
  (`AnnotationImportPreview.test.tsx`, `AnnotationPage.test.tsx`, `AssignTaskForm.test.tsx`,
  `StatusFilterTabs.test.tsx`, `EntityTypesPage.test.tsx`, `training-jobs/page.test.tsx`'s
  "Approve & queue" timeout) with no new regressions.
- **Migration:** `046_training_job_source_scope.py` applied via `db-init` against the dev
  database; confirmed `source_scope` present on all 6 tenant schemas (including
  `tenant_template`) and the `CHECK` constraint rejects an invalid value (tested with a raw
  `INSERT ... VALUES (..., 'bogus')`, which raised
  `training_jobs_source_scope_check` as expected).
- **Docker:** rebuilt and restarted `annotation_service`, `celery_worker_annotation_llm`,
  `training_service`, and `portal` with the current code; confirmed via
  `grep SOURCE_IMPORT /app/src/.../export.py` inside the running `annotation_service` container
  that the deployed code matches the source under review.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), navigated to
  `/annotate/manual` — confirmed the "Your workflow" section renders "1. Upload documents",
  "2. Define entity types", "3. Annotation workspace" in order; clicking each card navigated to
  `/documents?upload=1` (with the upload dialog visibly open), `/entity-types`, and `/annotation`
  respectively (screenshot captured). Not independently re-verified live this session: the
  Automated flow's `/training-jobs?source=automated` hand-off end-to-end (covered by a passing
  unit test instead — see tasks.md § 9.5).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer has confirmed the 4 disclosed pre-existing/unrelated failure groups
  (training-jobs 404-vs-500 gap, hard-reload auth redirect, entity_definitions schema drift,
  system-admin-sets-training-params archive backlog) are tracked as separate follow-ups, not
  silently absorbed into this change's scope.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
