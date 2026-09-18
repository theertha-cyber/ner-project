## Why

Manual, Automated, and Import are three independent annotation workflows — a tenant chooses
one and works entirely within it. Training did not honor that separation: `TrainingJobCreate`
took no source information at all, so a training run submitted from any workflow trained on
every confirmed span and every imported row tenant-wide, blending manual annotations with
automated-batch-promoted spans and imported data regardless of which workflow the admin was
actually working in. The "Train model" hand-offs on the Manual landing page and the Automated
batch-acceptance screen both pointed at the same undifferentiated `/training-jobs` entry point,
reinforcing the blend.

Separately, the Manual annotation landing page's "Where the work is" section showed only the
"Annotation workspace" card, leaving a new user with no visible path to the two prerequisites —
uploading documents and defining entity types — before they can annotate anything.

## What Changes

- Add a `source_scope` (`manual` | `automated` | `import` | null) column to `training_jobs`,
  set at submission time by the tenant admin (never at approval time — hyperparameters stay a
  System Admin concern per ADR-009).
- `POST /api/v1/training-jobs` gates its entity-count and per-entity-type minimums against only
  the submitted job's `source_scope`: `automated` counts only spans with a
  `span_batch_provenance` row, `manual` counts only spans without one, `import` skips the
  span-based gates entirely (imported data lives in `imported_annotations`, not `spans`), and an
  omitted `source_scope` keeps today's tenant-wide count.
- `GET /api/v1/annotation-export` gains a `source` query parameter (`manual` | `automated` |
  `import`) with the same filtering rule, so the training worker's dataset actually matches the
  gate that let the job through.
- The training worker reads the job's stored `source_scope` and passes it through to the export
  call it makes to build the training dataset.
- The Manual annotation landing page's "Train model" action and the Automated flow's
  batch-acceptance "Train model" action each link to `/training-jobs` with their own
  `?source=manual` / `?source=automated`. The Training Jobs screen auto-opens the submit
  slide-over with that source locked (shown as read-only text, not a choice) when arriving via
  either link; the generic "+ Submit job" entry point instead requires the tenant admin to pick
  exactly one of the three workflows before the slide-over will submit.
- The Manual annotation landing page's single "Annotation workspace" card is replaced with a
  three-step "Your workflow" sequence — Upload documents, Define entity types, Annotation
  workspace — so a new tenant admin sees the path to their first annotation before they take it.
  "Upload documents" links to `/documents?upload=1`, which now auto-opens the upload dialog on
  arrival instead of only opening from its own in-page button.

## Capabilities

### New Capabilities

(none — this scopes existing training submission/export and reworks two existing landing-page
sections; no new capability domain)

### Modified Capabilities

- `training-jobs`: `POST /api/v1/training-jobs` gains a `source_scope` field on the request and
  response, and its entity-count / per-type gates are scoped to that source instead of always
  reading the tenant's full corpus.
- `annotation-workspace`: `GET /api/v1/annotation-export` gains a `source` query parameter that
  restricts the export to one workflow's data.
- `training-worker`: the worker's dataset-loading step passes the job's `source_scope` through
  to the export call.
- `training-jobs-screen`: the submit slide-over gains a source-scope requirement — locked and
  read-only when opened via a workflow's own hand-off link, a required radio choice otherwise —
  and the page auto-opens the slide-over with the locked source when arriving via `?source=`.
- `manual-annotation-landing`: the single "Annotation workspace" work card is replaced by a
  three-step workflow sequence, and the "Train model" hand-off now links to
  `/training-jobs?source=manual` instead of the undifferentiated `/training-jobs`.
- `seed-bootstrap`: the Automated flow's "Train model" action (on the Batch Pre-labeling screen)
  now links to `/training-jobs?source=automated` instead of the undifferentiated `/training-jobs`.
- `portal-documents`: the Documents page recognizes a new `?upload=1` deep link that auto-opens
  the upload dialog on arrival.

## Impact

- Backend: [alembic/versions/046_training_job_source_scope.py](alembic/versions/046_training_job_source_scope.py)
  (new column), [src/training_service/api/v1/schemas.py](src/training_service/api/v1/schemas.py),
  [src/training_service/infra/repository.py](src/training_service/infra/repository.py),
  [src/training_service/api/v1/training_jobs.py](src/training_service/api/v1/training_jobs.py),
  [src/training_service/worker.py](src/training_service/worker.py),
  [src/annotation_service/api/v1/export.py](src/annotation_service/api/v1/export.py).
- Frontend: [types/training-jobs.ts](src/portal/src/types/training-jobs.ts),
  [hooks/use-submit-training-job.ts](src/portal/src/hooks/use-submit-training-job.ts),
  [components/training-jobs/submit-job-slideover.tsx](src/portal/src/components/training-jobs/submit-job-slideover.tsx),
  [app/(auth)/training-jobs/page.tsx](src/portal/src/app/(auth)/training-jobs/page.tsx),
  [app/(auth)/annotate/manual/page.tsx](src/portal/src/app/(auth)/annotate/manual/page.tsx),
  [components/annotate/AnnotateLanding.tsx](src/portal/src/components/annotate/AnnotateLanding.tsx),
  [app/(auth)/documents/page.tsx](src/portal/src/app/(auth)/documents/page.tsx),
  [components/seed-bootstrap/BatchAcceptancePage.tsx](src/portal/src/components/seed-bootstrap/BatchAcceptancePage.tsx).
- Tests: new [tests/test_annotation_export_source_scope.py](tests/test_annotation_export_source_scope.py);
  extended [tests/test_training_jobs_api.py](tests/test_training_jobs_api.py) and
  [tests/confidence_review_support.py](tests/confidence_review_support.py) (added `source_scope`
  column to the shared fixture's local `training_jobs` DDL); extended
  [tests/test_training_worker.py](tests/test_training_worker.py) fixtures for the worker's
  `SELECT status, source_scope` query shape; new/updated portal component and page tests.
- Not in scope: the per-entity-type readiness panel in the submit slide-over stays tenant-wide
  (it predates source scoping and is advisory only, per ADR-010) — it is not scoped to the
  chosen source in this change.
