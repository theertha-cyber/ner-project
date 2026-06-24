## Why

The training jobs backend APIs and Celery worker are fully implemented, but the portal `/training-jobs` page is a placeholder stub. Tenant admins cannot submit jobs, monitor progress, or manage training runs, and system admins have no training queue UI to approve or reject requests.

## What Changes

- Implement the full `/training-jobs` portal page for tenant admins: filterable job list, detail panel with live epoch progress polling, submit-job slide-over with hyperparameter form, and cancel action
- Implement the same `/training-jobs` page for system admins with additional approve/reject actions on `pending_approval` jobs
- Add training job status filter tabs to the list view
- Add live epoch/loss polling for running jobs (5s interval)
- No backend or API changes — all consumed endpoints are already implemented

## Capabilities

### New Capabilities

- `training-jobs-ui`: Full training job management portal page at `/training-jobs` — filterable job list with status tabs, detail panel showing status timeline, epoch progress, hyperparameters, evaluation metrics (bar charts), dataset→job→model lineage strip, MLflow run deep link, role-gated actions (submit/cancel/approve/reject), and a submit slide-over with hyperparameter form and span-count preflight check

### Modified Capabilities

- (none)

## Impact

- **Portal frontend only**: Changes confined to `src/portal/src/app/(auth)/training-jobs/page.tsx` (rewrite from placeholder) and new component/hook files under `src/portal/src/`
- **APIs consumed**: `GET/POST /api/v1/training-jobs`, `GET /api/v1/training-jobs/{id}`, `POST .../cancel`, `POST .../approve`, `POST .../reject`, `GET /api/v1/annotation-export` (span preflight)
- **Auth**: Page gated by `tenant_admin` and `system_admin` roles; nav-config already routes both roles to `/training-jobs`
- No backend, migration, or infrastructure changes

## Open Questions

- Does `GET /api/v1/training-jobs/{id}` return `tenant_id` for cross-tenant system admin approve/reject flows? The mockup assumes system_admin can approve any tenant's job; the `tenant_id` is needed for the `?tenant_id=` query param on approve/reject endpoints.
- Is there a dedicated span count endpoint, or should the frontend fetch `GET /api/v1/annotation-export` and count lines for the preflight check?
