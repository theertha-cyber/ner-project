## 1. Backend: shape and hero copy

- [x] 1.1 Add `icon: str` and `time: str` fields to the `ActivityRow` Pydantic model in [dashboard.py](src/gateway/api/v1/dashboard.py).
- [x] 1.2 Update `_tenant_admin_data`'s hero literals: `title="Workspace overview."`, and rewrite `line` to describe monitoring the AI workspace, model performance, and dataset readiness (no "pipeline"/"processing" wording). Change `pTitle` from `"Pipeline activity"` to `"Recent Activity"`.
- [x] 1.3 Add a shared relative-time formatter helper (e.g. `_relative_time(dt: datetime) -> str`) producing `"just now"`, `"N minutes/hours ago"`, `"Yesterday"`, `"N days ago"` per the boundary rules to be fixed here (e.g. <1h → minutes, <24h → hours, 24-48h → "Yesterday", >48h → "N days ago").

## 2. Backend: curated tenant_admin event catalogue

- [x] 2.1 Define the large-document-upload size/page threshold and the dataset-training-readiness threshold as named constants in `dashboard.py`; reuse the existing 500-span constant already used for the annotator "Dataset readiness" panel for the readiness threshold (do not introduce a second number).
- [x] 2.2 Replace the `tenant_admin` call path from `_tenant_activity_rows`/`_tenant_pipeline_activity` (raw UNION over training_jobs/documents/annotation_tasks/extraction_runs) with a new `_tenant_curated_activity(db, schema, tenant_id, limit)` that queries and classifies exactly the ten event kinds from the proposal:
  - training_jobs.status == 'pending_approval' → "Model training requested" (icon `training`, go `training`)
  - training_jobs.status == 'queued' AND started_at IS NULL (post-approval, per design.md Decision 2) → "Model training approved" (icon `approval`, go `training`)
  - training_jobs.status == 'completed' → "Model training completed" (icon `training`, go `training`)
  - training_jobs.status == 'failed' → "Model training failure" (icon `failure`, go `training`, tk mapped to failed/error colour)
  - model_versions.status == 'promoted' (ordered by `promoted_at`) → "Model deployment" (icon `deploy`, go `models`)
  - extraction_runs representing a batch run with status == 'completed' → "Batch extraction completed" (icon `batch`, go `extractions`)
  - annotation completion count crossing the readiness threshold from 2.1 → "Dataset reached training readiness" (icon `dataset`, go `annotation`)
  - documents.status != 'error' AND size/page count above the large-upload threshold from 2.1 → "Large document upload completed" (icon `upload`, go `documents`)
  - public.tenant_users WHERE tenant_id = :tenant_id AND role == 'business_user', ordered by created_at → "Business User added" (icon `user`, go `users`)
  - public.tenant_users WHERE tenant_id = :tenant_id AND role == 'annotator', ordered by created_at → "Annotator added" (icon `user`, go `users`)
- [x] 2.3 Each classified row SHALL include `time` computed via the helper from 1.3 against the row's relevant timestamp.
- [x] 2.4 Order the unioned, classified rows by timestamp descending, cap at `limit`, and pad with `{title: "—", sub: "—", tag: "—", tk: "queued", go: "documents", icon: "—", time: "—"}` placeholders up to 4 rows when fewer curated events exist (mirrors existing `_tenant_pipeline_activity` padding behaviour).
- [x] 2.5 Wire `_tenant_admin_data` to call `_tenant_curated_activity(..., limit=4)` for `pRows` instead of `_tenant_pipeline_activity`.
- [x] 2.6 Update `GET /api/v1/dashboard/activity` (tenant_admin branch) to call `_tenant_curated_activity(..., limit=200)` instead of `_tenant_activity_rows`, so the "View all" slide-over stays consistent with the summary panel.
- [x] 2.7 Remove or scope `_tenant_activity_rows`/`_tenant_pipeline_activity` so they are no longer reachable from the `tenant_admin` path (delete if no other caller remains after 2.5/2.6; confirm `system_admin`/`annotator`/`business_user` code paths are untouched per design.md Decision 3).

## 3. Frontend: types and rendering

- [x] 3.1 Add `icon: string` and `time: string` to the `ActivityRow` interface in [types/dashboard.ts](src/portal/src/types/dashboard.ts).
- [x] 3.2 Add an icon lookup map in [ActivityPanel.tsx](src/portal/src/components/dashboard/ActivityPanel.tsx) (mirroring the existing `TAG_COLOURS` pattern) mapping each backend icon key (`training`, `approval`, `deploy`, `failure`, `batch`, `dataset`, `upload`, `user`) to a `lucide-react` icon component, with a sensible fallback icon for unknown keys.
- [x] 3.3 Render the icon to the left of the title/sub text column in `ActivityRowList`, and render `row.time` (e.g. to the right of or under `row.sub`) without breaking the existing ellipsis/overflow layout.
- [x] 3.4 Confirm `row.sub` continues to render correctly when empty/short for curated events that have little descriptive text.

## 4. Verification tasks (spec scenario coverage)

- [x] 4.1 Add/update `tests/test_dashboard_summary_roles.py` and `tests/test_dashboard_summary.py`: assert `system_admin` `kicker`/`pTitle`/stat shape unchanged (covers verification.md rows 1, 12).
- [x] 4.2 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_workspace_overview_copy` asserting `title == "Workspace overview."`, `line` excludes "pipeline"/"processing", `pTitle == "Recent Activity"`, and every row has non-empty `icon`/`time` (covers rows 2, 13).
- [x] 4.3 Reuse/extend existing training-service-unavailable test in `tests/test_dashboard_summary.py` to assert HTTP 200 + `sources.training: false` still holds after the refactor (covers row 3).
- [x] 4.4 Confirm existing unauthenticated-request test still passes unmodified (covers row 4).
- [x] 4.5 Confirm existing system_admin partial-schema-failure tests (`tests/test_dashboard_summary.py`) still pass unmodified — they exercise `system_admin` code paths untouched by this change (covers rows 5, 6, 7, 8).
- [x] 4.6 Add a portal type-check test/build step asserting `DashboardData`/`ActivityRow` compile with the new fields, and a negative case (row missing `icon`/`time` fails to type-check) via a `// @ts-expect-error` fixture or equivalent (covers rows 9, 10, 11).
- [x] 4.7 Confirm existing annotator/business_user dashboard-shape tests pass unmodified (covers rows 14, 15).
- [x] 4.8 Confirm existing partial-failure "—" rendering test/story for stat cards still passes unmodified (covers row 16).
- [x] 4.9 Confirm existing `ActivityPanel.test.tsx` row-click-navigation and tag-colour tests still pass, updated only for any prop-shape changes (covers rows 17, 18).
- [x] 4.10 Add `ActivityPanel.test.tsx::renders icon and relative timestamp` for a row with `icon: "deploy"`, `time: "2 hours ago"` (covers row 19).
- [x] 4.11 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_curated_activity_excludes_raw_rows` seeding 50 documents + 1 completed training job, asserting the returned `pRows` do not contain 50 "document uploaded"-style rows (covers row 20).
- [x] 4.12 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_business_user_added_event` seeding a `business_user` row in `public.tenant_users`, asserting a `"Business User added"` row with `go == "users"` (covers row 21).
- [x] 4.13 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_annotator_added_event` seeding an `annotator` row, asserting an `"Annotator added"` row with `go == "users"` (covers row 22).
- [x] 4.14 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_model_deployment_event` seeding a `model_versions` row with `status="promoted"`, asserting a `"Model deployment"` row with `go == "models"` (covers row 23).
- [x] 4.15 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_training_failure_event` seeding a `training_jobs` row with `status="failed"`, asserting a `"Model training failure"` row with the failed/error `tk` (covers row 24).
- [x] 4.16 Add `tests/test_dashboard_summary_roles.py::test_tenant_admin_activity_pads_placeholders` seeding fewer than 4 curated events, asserting the response still has 4 rows with `title == "—"` placeholders (covers row 25).
- [x] 4.17 Fill in the "Verification Artifact" column in verification.md § Spec Alignment for rows 1-25 with the test names from 4.1-4.16 (and existing test names reused unmodified).

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 5.6 Run `openspec validate tenant-dashboard-workspace-refresh --type change --strict` before archive.
