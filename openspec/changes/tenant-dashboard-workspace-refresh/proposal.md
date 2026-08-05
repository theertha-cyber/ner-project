## Why

The tenant admin dashboard currently reads like an internal engineering console: the hero says "Pipeline overview" / "document processing and training pipeline at a glance," and the activity feed ("Pipeline activity") surfaces raw row-level events (a document upload, a training job status flip) pulled straight from `training_jobs`, `documents`, `annotation_tasks`, and `extraction_runs`. A Tenant Admin's job is to run their AI workspace — manage datasets, models, and people — not watch a processing log. The copy and the activity feed should speak to that job.

## What Changes

- Rename the dashboard hero title from `"Pipeline overview."` to `"Workspace overview."` and rewrite the subtitle to describe the tenant admin's operational goal (monitoring the AI workspace, model performance, dataset readiness) instead of naming the underlying pipeline. Scoped to the `tenant_admin` role only — other roles' hero copy is unchanged.
- Rename the "Pipeline activity" panel to `"Recent Activity"` for the `tenant_admin` role.
- Replace the tenant admin activity feed's row selection logic so it surfaces operationally meaningful events instead of every raw table insert/status change. In scope: model training requested, training approved, training completed, training failed, model deployed/promoted, batch extraction completed, dataset reached training readiness, large document upload completed, business user added, annotator added.
- Add an `icon` key and a human-relative timestamp (`"2 hours ago"`, `"Yesterday"`, `"3 days ago"`) to each activity row returned for `tenant_admin`, and render both in `ActivityPanel`. `sub` remains optional/short descriptive text under the title.
- The `/activity` full-history endpoint (used by the "View all" slide-over) SHALL use the same event selection and shape so the expanded view stays consistent with the summary row list.

## Capabilities

### New Capabilities

(none — this refines existing dashboard behaviour, no new capability domain)

### Modified Capabilities

- `portal-dashboard`: Hero copy for `tenant_admin` changes from pipeline-framed to workspace-framed; the tenant admin activity panel is renamed and its requirement is rewritten to define curated operational event types, an icon field, and relative timestamps instead of raw row activity.
- `dashboard-summary-endpoint`: The `tenant_admin` branch of `GET /api/v1/dashboard/summary` and `GET /api/v1/dashboard/activity` change what they query and how rows are classified/labelled (event catalogue instead of raw table union), and the `ActivityRow` shape gains `icon` and a relative-time field.

## Impact

- Backend: [dashboard.py](src/gateway/api/v1/dashboard.py) — `ActivityRow` model, `_tenant_admin_data`, `_tenant_activity_rows`, `_tenant_pipeline_activity`, hero `kicker`/`title`/`line`/`pTitle` literals for the tenant_admin branch. New queries needed for events not currently tracked as first-class rows (business user added, annotator added, dataset training-readiness threshold, model deployment/promotion) — these may require joining `public.tenant_users`/tenant user tables and existing model-registry/training tables; some events may not have a dedicated audit table yet and will need to be inferred from existing state changes.
- Frontend: [types/dashboard.ts](src/portal/src/types/dashboard.ts) (`ActivityRow` type), [ActivityPanel.tsx](src/portal/src/components/dashboard/ActivityPanel.tsx) (render icon + relative timestamp, keep `sub` optional), [page.tsx](src/portal/src/app/(auth)/dashboard/page.tsx) if any hardcoded panel copy exists.
- Tests: [test_dashboard_summary_roles.py](tests/test_dashboard_summary_roles.py), [test_dashboard_summary.py](tests/test_dashboard_summary.py), [ActivityPanel.test.tsx](src/portal/src/components/dashboard/ActivityPanel.test.tsx) assert on the old "Pipeline overview"/"Pipeline activity" strings and raw row shapes and will need updates.
- Only the `tenant_admin` role's hero and activity panel are in scope. `system_admin`, `annotator`, and `business_user` dashboards are unchanged.

## Open Questions

- No dedicated audit/event log table exists today for "business user added," "annotator added," "model deployment," or "dataset reached training readiness." Design will need to decide whether to source these from existing tables (e.g. `public.tenant_users.created_at` + role, `model_versions` promotion timestamp, an annotation-count threshold check) or treat any missing signal as gracefully omitted from the feed (matching the existing "degrade gracefully" pattern used for stat cards).
- Training approval already has a workflow (see `training-approval` spec) — confirm "requested" vs "approved" map to existing status transitions on `training_jobs` rather than needing new state.
- Exact relative-timestamp wording thresholds (e.g., when "2 hours ago" flips to "Yesterday") to be fixed in design.md.
