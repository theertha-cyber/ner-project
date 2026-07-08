## Context

Tenant-scoped tables (`training_jobs`, `model_versions`, `documents`, etc.) live in per-tenant Postgres schemas (`tenant_<uuid>`), cloned at tenant-creation time from a `tenant_template` schema (`src/gateway/services/tenant_service.py::create_tenant`, via `CREATE TABLE ... (LIKE tenant_template.<table> INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)`).

Direct inspection of the migration history and the live `tenant_template` schema shows the actual root cause is more specific than "one migration forgot to loop": `alembic/versions/002_tenant_template_schema.py` already created `tenant_template.training_jobs` with an early, different column set (`dataset_version`, `base_model`, `hyperparameters`, `metrics_uri`, ...). `005_training_service_tables.py` later runs `CREATE TABLE IF NOT EXISTS tenant_template.training_jobs (...)` with the intended real shape (including `hyperparams`, `metrics`, `error_message`, `current_epoch`, ...) — but because the table *already existed* from 002, `IF NOT EXISTS` made 005's `CREATE TABLE` a silent no-op against `tenant_template`. The columns 005 intended were never actually applied there. Three later migrations (`006_mlflow_tracking_columns`, `012_reconcile_training_jobs_columns`, `013_add_missing_created_at_columns`) each patched a handful of the missing columns back in via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, discovered piecemeal over time — and `012`/`013` do correctly loop over every existing `tenant_%` schema (via a hand-written `DO $$ ... FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%' ...` block) to apply the same `ALTER TABLE` there too, while `006` does not (it only touches `tenant_template`). None of 002, 005, 006, 012, or 013 ever added `error_message` — confirmed today: `tenant_template.training_jobs` itself is still missing it, not just an individual tenant's clone. That column simply fell through the cracks of 005's no-op `CREATE TABLE` and was never caught by any of the later ad-hoc reconciliation passes.

This is exactly the failure mode ADR-001's migration-compliance mandate is meant to prevent, and the codebase already contains the right instinct (012/013's per-schema loop) applied inconsistently by hand each time (006 omits it entirely; the loop body is copy-pasted rather than shared) rather than as a structural guarantee. The immediate symptom: tenant `4126ebb0-da07-4d09-bc46-df79c7c6933e`'s `training_jobs` table is missing `error_message`, causing `UndefinedColumn` when the training worker tries to record a job failure — but the same gap exists in `tenant_template` and therefore in every tenant's schema, not just this one.

Separately, `src/gateway/seed.py` maintains its own inline, hand-written `CREATE TABLE IF NOT EXISTS {schema}.training_jobs (...)` (used only for the local demo tenant), which has drifted independently from both `tenant_template` and the real column set the application code expects — a second, smaller instance of the same "duplicated schema definition, no single source of truth" problem.

Separately again, `src/training_service/worker.py` defaults `ANNOTATION_SERVICE_URL` to `http://annotation_service:8002`, but `annotation_service` listens on port `8000` inside the Docker network (`docker-compose.yml`: `command: uvicorn ... --port 8000`, `ports: "8005:8000"`). No environment variable overrides this default anywhere, so every training job's dataset-load step fails with a connection refused.

## Goals / Non-Goals

**Goals:**
- A migration that changes a tenant-scoped table shape in `tenant_template` also updates every already-provisioned active tenant schema, in the same migration run — closing the drift class of bug at the source, not just this one instance.
- The already-drifted tenant schema(s) in this environment are brought back in sync with the current template shape.
- The training worker resolves the annotation service at the correct address by default, and the address remains overridable via environment variable (for non-Docker or future topology changes).
- `seed.py`'s tenant table definitions can no longer silently diverge from `tenant_template`.

**Non-Goals:**
- Building a general-purpose schema-diffing/drift-detection tool that scans for arbitrary divergence. This fix targets the specific mechanism (template-only migrations) that causes drift, not every possible way schemas could diverge (e.g., manual `ALTER TABLE` outside of migrations is still possible and out of scope).
- Changing the tenant-schema-per-tenant isolation model itself (ADR-001's core decision is unchanged).
- Retrying/re-processing the specific training job that failed in this environment — that is an operational cleanup step, not a spec-level behavior.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schemas; **Compliance section explicitly states: "Migration scripts MUST be applied to the `public` schema (tracking) and each tenant schema."** | This design does not introduce a new requirement — it brings the migration pattern into compliance with an ADR-001 mandate that migration 005 (and implicitly the tenant-provisioning approach) was already violating. The fix must apply DDL to `tenant_template` and every active tenant schema, explicitly scoped per schema (no implicit cross-schema queries), consistent with ADR-001's isolation model. |
| ADR-006 | Training runs asynchronously via Celery workers on GPU-capable pods; workers are configured via environment variables for dependent service URLs (implicit precedent, formalized further by the `worker-network-config` spec for the extraction worker) | The `ANNOTATION_SERVICE_URL` fix must remain environment-variable-driven and must not change the async Celery execution model itself. |

## Decisions

### Decision 1: Apply tenant-scoped DDL to `tenant_template` and every active tenant schema in the same migration, via a shared helper

**Choice:** Add a small helper, `alembic/tenant_schema_ddl.py`, exposing a function such as `apply_to_all_tenant_schemas(op, ddl_template: str)` that: (a) runs `ddl_template.format(schema="tenant_template")`, then (b) queries `SELECT id FROM public.tenants` (all tenants, **regardless of `status`**) and runs `ddl_template.format(schema=f"tenant_{id.replace('-', '_')}")` for each. All DDL used with this helper must be idempotent (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) so re-running it (e.g. against a schema that already has the column) is a no-op. Future migrations that change tenant-scoped table shape use this helper instead of hand-writing `tenant_template`-only DDL.

Note this deliberately differs from the `status = 'active'`-filtered per-schema loops used elsewhere (e.g. `dashboard.py`'s reporting aggregation, this change's own `training_jobs.py` list aggregation): those loops scope to active tenants because they're producing a *runtime report* where inactive tenants' data shouldn't count. Schema migrations are a *structural consistency* concern — an inactive tenant's schema should never be allowed to silently rot, since reactivating that tenant later must not resurrect a broken schema. All tenants get the DDL.

**Rationale:** This directly satisfies ADR-001's existing "migration scripts MUST be applied to ... each tenant schema" compliance requirement, using the same per-schema-loop pattern already established elsewhere in the codebase (`dashboard.py::_all_tenant_schemas`, this change's own `training_jobs.py::_all_active_tenant_ids`) — no new architectural pattern, just applying the existing one to migrations. Making it automatic (part of authoring a migration) removes the human-memory dependency that caused this incident: a future engineer adding a column to `training_jobs` cannot forget to backfill existing tenants, because the helper does both in one call.

**Alternatives considered:**
- A standalone "sync tenant schemas" operator/admin command run manually after each migration. Ruled out as the *primary* mechanism: it reintroduces the same human-memory dependency that caused this incident (an operator has to remember to run it). It remains useful as a secondary diagnostic tool (see Decision 3) but not as the enforcement mechanism.
- Rewriting migration 005 itself to also loop over tenant schemas. Ruled out: shipped migrations are treated as immutable history; rewriting one that has already run in some environments risks divergent migration state across environments (an environment where 005 already ran once wouldn't re-run a changed 005).

### Decision 2: Ship a new remediation migration that adds the missing `error_message` column (and defensively re-verifies the rest of 005's shape) via the new helper

**Choice:** Add `alembic/versions/016_backfill_training_jobs_error_message.py` (`down_revision = "015"`, the current head) that uses the Decision 1 helper to run `ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT` against `tenant_template` and every existing tenant schema. Since 006/012/013 already back filled the rest of 005's intended columns (confirmed by inspection — only `error_message` is actually missing from `tenant_template` today), the migration only needs to add that one column, but does so defensively via the same idempotent, all-schemas helper rather than a one-off hand-written `ALTER TABLE` — both to fix the specific incident and to exercise/prove out the new Decision 1 helper on its first real use.

**Rationale:** Targeting exactly the column verified missing (rather than blindly re-running all of 005's `CREATE TABLE` DDL through the new helper) avoids re-deriving column definitions that are already correct and keeps the migration's diff minimal and easy to review. Using the new helper (instead of copy-pasting another `DO $$ ... FOR schema_name IN ...` block, as 012/013 each did independently) is itself part of closing the gap: this is the first migration written *after* the helper exists, and it should demonstrate the intended future pattern rather than adding a fourth hand-written copy of the same loop.

**Alternatives considered:**
- Hand-picking and fixing only the one tenant schema already known to be broken (`4126ebb0-...`). Ruled out: `tenant_template` itself is missing the column, so every tenant is affected, not just the one that happened to surface the bug first.
- Re-running all of migration 005's `CREATE TABLE` column list through the helper defensively, in case something else is also missing. Ruled out after direct inspection confirmed `tenant_template.training_jobs` already has every other 005-era column (via 006/012/013's prior patches) — `error_message` is the only gap, so a wider defensive re-application would only add noise without fixing anything additional.

### Decision 3: Fix `ANNOTATION_SERVICE_URL` default and set it explicitly in `docker-compose.yml`

**Choice:** Change the default in `src/training_service/worker.py` from `http://annotation_service:8002` to `http://annotation_service:8000` (matching the service's actual internal port), and additionally set `NER_ANNOTATION_SERVICE_URL`-style environment variables explicitly for the `training_service` and `celery_worker` services in `docker-compose.yml`, mirroring the existing pattern used for `NER_DOCUMENT_SERVICE_URL`/`NER_MODEL_SERVING_URL` on the extraction worker (`worker-network-config` spec).

**Rationale:** Fixing only the default would leave the worker one wrong hardcoded value away from breaking again if the service's port ever changes; setting it explicitly in `docker-compose.yml` (the same place other inter-service URLs are configured) makes the dependency visible and consistent with how every other inter-service URL in this stack is already wired.

**Alternatives considered:**
- Fixing only the code default, leaving it unset in `docker-compose.yml`. Ruled out: inconsistent with how every other inter-service dependency in `docker-compose.yml` is configured, and leaves a wrong-by-default value as the only line of defense again.

### Decision 4: Reconcile `seed.py`'s inline tenant table DDL with `tenant_template`

**Choice:** Change `src/gateway/seed.py`'s demo-tenant provisioning to clone tables from `tenant_template` the same way `tenant_service.create_tenant()` does (`CREATE TABLE ... LIKE tenant_template.<table> INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES`), instead of maintaining a second, hand-written `CREATE TABLE` statement per tenant-scoped table.

**Rationale:** Removes the second source of truth that already drifted once (seed.py's `training_jobs` definition is missing most of the real columns) and cannot drift again structurally, since it now always reflects whatever `tenant_template` currently is (kept current by migrations, including the Decision 1 helper for future changes).

**Alternatives considered:**
- Manually updating `seed.py`'s inline DDL to match the current column set. Ruled out: fixes the symptom once but leaves the same drift-prone pattern (two independent schema definitions) in place for the next migration.

## Risks / Trade-offs

- [Looping DDL across every active tenant schema inside a migration adds O(active tenants) statements to that migration's runtime] → Acceptable at current tenant counts (same scaling note already accepted in ADR-001 for the dashboard/reporting per-schema loops); idempotent `IF NOT EXISTS` DDL keeps each statement cheap.
- [A migration that partially fails partway through the per-tenant loop (e.g., one tenant schema in a bad state) could leave some tenants updated and others not] → Each per-schema statement is independently idempotent and safe to retry; a failed migration run can simply be re-run (`alembic upgrade head`) and will only apply remaining no-op-safe DDL to tenants not yet updated. Document this expectation in the migration's docstring.
- [Changing `seed.py` to clone from `tenant_template` changes the exact column set of the local demo tenant's tables] → Called out as **BREAKING** in the proposal, but scoped to local dev seed data only; no production or API-provisioned tenant is affected.

## Migration Plan

1. Add `alembic/tenant_schema_ddl.py` helper (Decision 1). No DB change from this step alone.
2. Add remediation migration `016_backfill_training_jobs_error_message.py` using the helper (Decision 2); run via `alembic upgrade head` in each environment, including this one, to backfill `error_message` onto `tenant_template` and every existing tenant schema.
3. Fix `ANNOTATION_SERVICE_URL` default and `docker-compose.yml` env vars (Decision 3); rebuild and restart `training_service` and `celery_worker` containers (same rebuild/restart step already required after the `fix-system-admin-training-queue-bugs` change).
4. Update `seed.py` to clone from `tenant_template` (Decision 4); re-seeding local dev (`db-init`) picks this up automatically on next full stack rebuild.
5. Rollback: the remediation migration's `downgrade()` is a no-op (dropping backfilled columns from schemas that may now have real data would be destructive and is not required to reverse this fix's intent); reverting the code changes (worker default, `docker-compose.yml`, `seed.py`) is a plain revert with no data implications.

## Open Questions

- Should the new `apply_to_all_tenant_schemas` helper eventually be extended with a standalone CLI/admin command for ad hoc drift detection (comparing an arbitrary tenant schema's columns against `tenant_template`), independent of authoring a new migration? Deferred as a possible small follow-up; not required to close this incident since Decision 1 prevents new drift and Decision 2 repairs existing drift.
- Should tenant schema count ever grow large enough that per-migration O(tenants) DDL loops become a real latency concern (same threshold ADR-001 already flags at >500 tenants), this may need revisiting with a batched/background-job approach instead of running inline during `alembic upgrade head`. Not a concern at current scale; flagged for a future ADR if/when tenant count approaches that threshold.
