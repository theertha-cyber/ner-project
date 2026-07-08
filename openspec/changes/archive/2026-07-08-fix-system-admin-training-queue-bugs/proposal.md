## Why

A production-shaped repro surfaced three bugs in the same incident: an annotator imported annotations, a Tenant Admin submitted a training job for approval, and a System Admin opened the Training Queue page, selected the job, and hit a `400 Bad Request` loop instead of the job detail. Docker logs from the same window also showed a wall of `current transaction is aborted` Postgres errors from the dashboard summary endpoint. Investigation (read-only, see change history) traced these to three independent gaps, all touching the same System Admin cross-tenant surface: the job detail/list/action endpoints never receive the tenant context needed to look up a job that isn't the caller's own; the portal's query cache isn't cleared across a login/logout cycle, so stale cross-session data can render before a refetch corrects it; and the dashboard's per-tenant aggregation loop has no transaction recovery, so one bad tenant schema silently zeroes out every other tenant's stats. Fixing all three closes the incident and hardens the System Admin cross-tenant path generally, since a System Admin is the only role that must reach into another tenant's data by design.

## What Changes

- Add `tenant_id` to `TrainingJobResponse` / `TrainingJobListResponse` items (backend) and the portal's `TrainingJob` type, sourced from the existing DB column (already selected via `SELECT *`, currently dropped in `_row_to_response()`).
- Thread that `tenant_id` through the portal: `JobList` row data → selection state → `useTrainingJob` (sent as `?tenant_id=` when the viewer is `system_admin`) → `JobActions` (approve/reject/cancel use the job's own tenant, not the viewer's `user.tenantId`).
- Fix `list_training_jobs` so a System Admin can see pending/relevant jobs without every call silently degrading to an empty list: either accept a `tenant_id` filter from a minimal tenant-selector control on the Training Queue page, or aggregate pending-approval jobs across tenants for that role (decision recorded in design.md; the current behavior of unconditionally returning `items: []` with no explicit tenant is treated as a regression to close, not a feature to preserve).
- Clear the portal's React Query cache in `logout()` (`queryClient.clear()` or equivalent) so no cross-session/cross-tenant data can render after a role switch in the same tab, before the corrected fetch resolves.
- In `_system_admin_data()` (gateway dashboard summary), roll back (or use a savepoint) after each per-tenant-schema query failure so one bad schema no longer poisons the shared session for the rest of the request — every other tenant's stats SHALL still be computed and reported, and `sources` SHALL accurately reflect only the schemas that actually failed.
- **BREAKING**: `GET /api/v1/training-jobs/{job_id}` and `GET /api/v1/training-jobs` for `system_admin` change shape/behavior (response now includes `tenant_id`; list behavior for system_admin without a tenant filter changes from "always empty" to the decided design). Any existing test or client relying on the current empty-list/400 behavior needs updating.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `training-jobs`: `TrainingJobResponse`/list items gain `tenant_id`; System Admin `GET /{job_id}` and `GET /` requirements are clarified/corrected for cross-tenant access instead of leaving System Admin behavior unspecified; approve/reject/cancel continue to require the owning tenant but now receive it correctly from the UI.
- `auth-context`: `logout()` gains a requirement to clear cached query data (not just the access token and user state), so no stale cross-tenant/cross-session data can be read from cache after logout.
- `dashboard-summary-endpoint`: the per-tenant-schema aggregation loop gains a requirement that a single schema's query failure SHALL NOT prevent other schemas' data from being aggregated in the same request (transaction recovery between iterations).

## Impact

- **Backend**: `src/training_service/api/v1/schemas.py`, `src/training_service/api/v1/training_jobs.py` (`_row_to_response`, `get_training_job`, `list_training_jobs`), `src/training_service/infra/repository.py` (no schema change expected, `tenant_id` already selected).
- **Portal**: `src/portal/src/types/training-jobs.ts`, `src/portal/src/hooks/use-training-job.ts`, `src/portal/src/hooks/use-training-jobs.ts`, `src/portal/src/components/training-jobs/job-list.tsx`, `src/portal/src/app/(auth)/training-jobs/page.tsx`, `src/portal/src/components/training-jobs/job-actions.tsx`, `src/portal/src/lib/auth.tsx` (logout), possibly a new small tenant-selector component if design.md chooses that path.
- **Gateway**: `src/gateway/api/v1/dashboard.py` (`_system_admin_data`), `src/gateway/dependencies.py` (`get_db` session handling) — likely no signature change, just rollback/savepoint discipline inside the existing loop.
- **Tests**: `page.test.tsx` currently has zero `system_admin` coverage for the Training Jobs page — new tests needed. `use-training-job.test.tsx`, `use-training-jobs.test.tsx`, `job-actions.test.tsx` need `tenant_id`-aware assertions. Backend tests for `training_jobs.py` need System Admin cross-tenant scenarios. `dashboard.py` needs a test simulating one bad tenant schema alongside healthy ones.
- **Not affected**: training job execution (Celery/worker), model registry, the `remove-training-span-gate` change (unrelated, separate slideover concern already in flight).

## Open Questions

- Should System Admin's Training Queue list be a cross-tenant aggregated "pending approvals" queue (matching the page's own label), or a per-tenant view gated behind an explicit tenant selector? This determines whether `list_training_jobs` needs a schema-scanning aggregation path (like `dashboard.py` already does) or just a `tenant_id` query param wired to a new UI control. Recorded for design.md to resolve.
- Should `queryClient.clear()` on logout be unconditional, or scoped to remove only user-scoped query keys (in case some cached data, e.g. static reference data, is safe and expensive to refetch)? Recorded for design.md.
