## 1. Shared tenant-schema migration helper

- [x] 1.1 Add `tenant_schema_ddl.py` exposing `apply_to_all_tenant_schemas(op, ddl_template: str)`: applies DDL to `tenant_template`, then queries `pg_namespace` for existing `tenant_%` schemas (matching the established codebase pattern from migrations 012/013/015) and applies DDL to each.
- [x] 1.2 Verification: add a migration-focused test (e.g. `tests/test_tenant_schema_migrations.py`) covering scenarios 1–3 (new column propagates to an existing tenant schema; an inactive tenant's schema is still updated; re-running the DDL is a no-op). Record this file as the Verification Artifact for rows 1–3 in verification.md § Spec Alignment.

## 2. Remediation migration for `training_jobs.error_message`

- [x] 2.1 Add `alembic/versions/016_backfill_training_jobs_error_message.py` (`down_revision = "015"`) using the Decision 1 helper to run `ALTER TABLE {schema}.training_jobs ADD COLUMN IF NOT EXISTS error_message TEXT` against `tenant_template` and every existing tenant schema.
- [x] 2.2 Run `alembic upgrade head` in this environment and confirm via `\d tenant_template.training_jobs` and `\d tenant_<affected-id>.training_jobs` that `error_message` is now present, with existing rows unaffected.
- [x] 2.3 Verification: extend the test file from 1.2 (or add a dedicated one) to cover scenarios 4–5 (tenant_template and existing tenants gain the missing column; a schema that already has the column is unaffected — run the migration twice against the same fixture to prove idempotency). Record this file as the Verification Artifact for rows 4–5.

## 3. Fix training worker's annotation service URL

- [x] 3.1 In `src/training_service/worker.py`, change the `ANNOTATION_SERVICE_URL` default from `http://annotation_service:8002` to `http://annotation_service:8000`.
- [x] 3.2 In `docker-compose.yml`, add an explicit `ANNOTATION_SERVICE_URL: "http://annotation_service:8000"` environment entry under both the `training_service` and `celery_worker` services, matching the existing `NER_DOCUMENT_SERVICE_URL`/`NER_MODEL_SERVING_URL` pattern already used for the extraction worker.
- [x] 3.3 Verification: add/extend a worker unit test asserting (a) the default URL is used when `ANNOTATION_SERVICE_URL` is unset, and (b) a request goes to the overridden URL when the env var is set — covering scenarios 8–9. Confirm scenarios 6–7 (existing dataset-load happy path / empty-dataset failure path) still pass unchanged. Record the test file as the Verification Artifact for rows 6–9.

## 4. Reconcile `seed.py` with `tenant_template`

- [x] 4.1 In `src/gateway/seed.py`, replace the demo tenant's inline `CREATE TABLE IF NOT EXISTS {schema}.training_jobs (...)` / `model_versions` (and any other tenant-scoped table) definitions with `CREATE TABLE {schema}.<table> (LIKE tenant_template.<table> INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES)`, matching `tenant_service.create_tenant()`'s approach.
- [ ] 4.2 Manually verify: run `docker compose run --rm db-init` (or rebuild the stack) and confirm the demo tenant's `training_jobs` table now matches `tenant_template`'s shape (including `error_message`).

## 5. Live remediation for the already-affected environment

- [ ] 5.1 Confirm (already done during investigation) that tenant `4126ebb0-da07-4d09-bc46-df79c7c6933e` gains `error_message` after migration 016 runs in this environment, via `\d tenant_4126ebb0_da07_4d09_bc46_df79c7c6933e.training_jobs`.
- [ ] 5.2 Rebuild and restart `training_service` and `celery_worker` containers so they pick up the `ANNOTATION_SERVICE_URL` fix (`docker compose build training_service celery_worker && docker compose up -d --no-deps training_service celery_worker`).
- [ ] 5.3 Manually retry the training job that originally failed (or submit a new one) and confirm it no longer fails at the dataset-load step, and that a subsequent failure (if any, for unrelated reasons) can now be recorded via `error_message` without an `UndefinedColumn` error.

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 6.6 Run `openspec validate fix-tenant-schema-drift-and-training-worker-config --type change --strict` and confirm
         it exits clean before archive.
