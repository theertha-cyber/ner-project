## Why

Manually verifying the System Admin training-approval flow (from the `fix-system-admin-training-queue-bugs` change) surfaced two infrastructure defects that make approved training jobs fail: the training worker's `ANNOTATION_SERVICE_URL` default points at the wrong port, so the annotation-export call is refused for every job; and a tenant's `training_jobs` table is missing the `error_message` column, so the worker can't even record why the job failed. Investigation traced the second issue to a structural gap, not a one-off mistake: `alembic/versions/005_training_service_tables.py` only applies its `CREATE TABLE` to the `tenant_template` schema used for *future* tenants — there is no mechanism that propagates a template-schema migration to tenant schemas that already exist. Any tenant provisioned before a template-changing migration silently drifts out of sync forever, and the same class of bug will recur on the next such migration unless the migration pattern itself is fixed.

## What Changes

- Add a reusable migration helper that, when a migration alters a tenant-scoped table in `tenant_template`, applies the equivalent (idempotent) DDL to every already-provisioned active tenant schema in the same migration — not just the template used for future tenants.
- Add a remediation migration that backfills the already-drifted tenant schemas in this environment (at minimum, the missing `training_jobs`/`model_versions` columns from migration 005) using the new helper.
- Fix `ANNOTATION_SERVICE_URL`'s default in `src/training_service/worker.py` to match the annotation service's actual internal port, and set the variable explicitly in `docker-compose.yml` for `training_service` and `celery_worker` (mirroring the existing `worker-network-config` pattern already used for the extraction worker).
- Reconcile `src/gateway/seed.py`'s inline, out-of-sync `training_jobs`/`model_versions` `CREATE TABLE` statements so local demo-tenant seeding can't drift from `tenant_template` the way it did here — **BREAKING** for local dev seed data shape only (demo tenant's schema will be recreated from the template instead of the old hardcoded columns); no production/API-created tenant is affected by this specific fix.

## Capabilities

### New Capabilities

- `tenant-schema-migrations`: defines how a schema change to `tenant_template` propagates to already-provisioned tenant schemas, so a tenant's schema shape never permanently drifts from the template after a migration ships.

### Modified Capabilities

- `training-worker`: add a requirement for how the worker resolves the annotation service's base URL (environment-variable driven, with a default that matches the service's actual configured port), matching the existing `worker-network-config` requirement pattern already applied to the extraction worker.

## Impact

- **Migrations**: `alembic/` — new shared helper (e.g. `alembic/tenant_schema_utils.py` or similar) for applying DDL to all active tenant schemas; a new remediation migration; migration 005 itself is not rewritten (migrations are immutable once shipped), the new pattern applies going forward and the remediation migration closes the gap it left behind.
- **Backend**: `src/training_service/worker.py` (`ANNOTATION_SERVICE_URL` default), `src/gateway/seed.py` (align inline tenant table definitions with `tenant_template`).
- **Infra**: `docker-compose.yml` — explicit `ANNOTATION_SERVICE_URL` env var for `training_service` and `celery_worker`.
- **Tests**: new migration/backfill test coverage (a migration that alters `tenant_template` also updates an existing tenant schema fixture); a worker config test asserting the corrected default and env-var override; `tests/test_training_jobs.py`/worker tests should not need changes to existing passing cases.
- **Not affected**: the `fix-system-admin-training-queue-bugs` change (already shipped) — this change fixes a downstream, unrelated pair of bugs that change exposed during manual verification, not a defect in that change's own code.

## Open Questions

- Should the new tenant-schema-migration helper run automatically as part of every future migration that touches `tenant_template` (opt-in per migration, via the helper), or should there also be a standalone "sync tenant schemas" operator command for ad hoc drift detection/repair independent of a new migration being authored? Recorded for design.md to resolve; leaning toward the automatic, migration-time approach as the primary mechanism since it removes the human-memory dependency that caused this incident, with a standalone diagnostic/detection command as a smaller follow-up if needed.
- Should the remediation migration target only the specific tenant(s) already known to be missing columns, or defensively re-apply the migration-005 DDL (via `ADD COLUMN IF NOT EXISTS` / `CREATE TABLE IF NOT EXISTS`) to *every* active tenant schema regardless of whether they're currently known to be affected, in case other undetected drift exists? Leaning toward the defensive/idempotent approach — recorded for design.md.
