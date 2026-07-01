## Why

The dashboard shows `"—"` and `"service unavailable"` for all non-system_admin roles (tenant_admin, annotator, business_user) because their data handlers return hardcoded placeholder values. The endpoint conforms to the graceful-degradation spec, but no real queries were ever wired — only the system_admin tenant count works.

## What Changes

- Add `db` session and `tenant_id` parameters to `_tenant_admin_data`, `_annotator_data`, and `_business_user_data` handlers in `src/gateway/api/v1/dashboard.py`
- Write real SQL queries against tenant-scoped tables for each stat, activity row, and side metric
- Add `tenant_id` dependency to the route handler and pass it along with `db` to all role handlers (currently only system_admin receives `db`)
- Update the `portal-dashboard` spec with concrete scenarios for each role showing real data from wired sources
- Reconcile the schema drift between migration 002 and 005 for `training_jobs`/`model_versions` columns

## Capabilities

### New Capabilities

- `dashboard-query-wiring`: Backend SQL queries for the three unwired dashboard roles — tenant_admin (documents, annotation %, model F1, training), annotator (tasks, spans, suggestions), business_user (extractions, entities, confidence)

### Modified Capabilities

- `portal-dashboard`: Add concrete scenarios for each role's real-data behavior when services are available; update `sources` map to include `"extraction"`

## Impact

- `src/gateway/api/v1/dashboard.py`: All four handler signatures change; route dispatch adds `tenant_id` dependency
- `src/gateway/dependencies.py`: No changes needed (tenant_id already available via `get_request_tenant_id`)
- `openspec/specs/portal-dashboard/spec.md`: New scenarios added
- Database schema: Migration to reconcile 002/005 column drift for `training_jobs.metrics` JSONB column and `model_versions.metrics` JSONB column
- No frontend changes — the UI already handles `null` → `"—"` rendering correctly

## Open Questions

- Should schema reconciliation (002 vs 005 drift) be a separate change or included here? Included for now since dashboard queries depend on `metrics` JSONB columns.
- What exact columns should the seed script populate to make the dashboard useful after wiring?
