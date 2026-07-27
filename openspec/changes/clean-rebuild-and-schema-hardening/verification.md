# Verification Plan

**Change:** clean-rebuild-and-schema-hardening
**Generated:** 2026-07-27
**Status:** 🟡 Evidence Log populated by implementing agent — Audit Record sign-off by a human reviewer is still required before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | dev-database-reset | Documented clean-rebuild procedure for the local stack | Operator follows the documented procedure on a drifted database | Given a drifted `ner_dev`, when the documented procedure is followed to completion, then `alembic_version` equals the chain head and every object the chain declares exists with the declared shape | manual: rebuild transcript + `alembic_version` query (task 8.3, 8.4) | - [x] |
| 2 | dev-database-reset | Documented clean-rebuild procedure for the local stack | The procedure declares its destructive effect before any step runs | Given the procedure document, when read, then a statement that all local tenants, users, documents, annotations, model versions, and training runs are permanently destroyed appears before the first command | manual: doc review of rebuild procedure (task 8.5) | - [x] |
| 3 | dev-database-reset | Documented clean-rebuild procedure for the local stack | Images are rebuilt before migrations run | Given a tree with migration revisions newer than the current images, when the procedure is followed, then `docker compose build` runs before stack start and the applied chain includes every revision in `alembic/versions/` | manual: rebuild transcript showing build before up (task 8.3) | - [x] |
| 4 | dev-database-reset | Post-migration schema verification | A clean rebuild passes verification | Given a database built by applying the full chain to an empty database, when verification runs, then it reports no drift and exits 0 | `tests/test_verify_schema.py::test_clean_database_passes` | - [x] |
| 5 | dev-database-reset | Post-migration schema verification | A missing public column is detected | Given `public.entity_definitions` lacking `validation_rule`, when verification runs, then it names that table and column as drifted and exits non-zero | `tests/test_verify_schema.py::test_missing_public_column_detected` | - [x] |
| 6 | dev-database-reset | Post-migration schema verification | A missing tenant_template table is detected | Given `tenant_template` lacking `documents`, when verification runs, then it reports `tenant_template.documents` missing and exits non-zero | `tests/test_verify_schema.py::test_missing_template_table_detected` | - [x] |
| 7 | dev-database-reset | Post-migration schema verification | A tenant schema that lags the template is detected | Given a `tenant_<id>` schema missing a table present in `tenant_template`, when verification runs, then it names that schema and table and exits non-zero | `tests/test_verify_schema.py::test_tenant_schema_lagging_template_detected` | - [x] |
| 8 | dev-database-reset | Drift blocks stack startup | Application services do not start on a drifted database | Given a drifted database, when `docker compose up` runs, then `db-init` exits non-zero, no application service starts, and the logs name the drifted objects | manual: drifted-copy `docker compose up` transcript (task 8.6) | - [x] |
| 9 | dev-database-reset | Drift blocks stack startup | A clean database starts the stack normally | Given a database passing verification, when `docker compose up` runs, then `db-init` exits 0 and all application services start | manual: clean `docker compose up` transcript (task 8.3) | - [x] |
| 10 | test-fixture-db-isolation | Fixture setup scripts refuse non-test databases | Script refuses to run against the development database | Given `NER_DATABASE_URL` pointing at `ner_dev`, when `setup_test_db.py` runs, then it exits non-zero naming `ner_dev` and creates no table and inserts no row | `tests/test_setup_test_db_guard.py::test_refuses_dev_database` | - [x] |
| 11 | test-fixture-db-isolation | Fixture setup scripts refuse non-test databases | Script runs against a test database | Given `NER_DATABASE_URL` pointing at `ner_test`, when the script runs, then fixture schemas, tables, and tenant rows are created and it exits 0 | `tests/test_setup_test_db_guard.py::test_allows_test_database` | - [x] |
| 12 | test-fixture-db-isolation | Fixture setup scripts refuse non-test databases | The guard reads the URL actually used, not the default | Given a test-database default URL and `NER_DATABASE_URL` set to a non-test database, when the script runs, then the guard evaluates the env-var target and the script refuses | `tests/test_setup_test_db_guard.py::test_guard_reads_env_url_not_default` | - [x] |
| 13 | test-fixture-db-isolation | Explicit opt-in override for the fixture guard | Override permits a non-standard test database name | Given a target named `ner_ci_scratch` and the override set to an affirmative value, when the script runs, then it proceeds and emits a warning naming `ner_ci_scratch` | `tests/test_setup_test_db_guard.py::test_override_permits_nonstandard_name` | - [x] |
| 14 | test-fixture-db-isolation | Explicit opt-in override for the fixture guard | Unset override leaves the guard in force | Given a target of `ner_dev` and the override unset, when the script runs, then it refuses to run | `tests/test_setup_test_db_guard.py::test_unset_override_keeps_guard` | - [x] |
| 15 | dashboard-summary-endpoint | Dashboard Summary Endpoint | system_admin summary returns role-specific data | Given a `system_admin` caller, when `GET /api/v1/dashboard/summary` is called, then the response carries the platform-control-plane kicker, 4 named stats, the approval-queue panel with 4 rows, and the platform-health side panel | `tests/test_dashboard_summary_roles.py::test_system_admin_summary` | - [x] |
| 16 | dashboard-summary-endpoint | Dashboard Summary Endpoint | tenant_admin summary returns pipeline data | Given a `tenant_admin` caller, when the endpoint is called, then the response carries the 4 pipeline stats, the pipeline-activity panel with 4 rows, and the active-model side panel with quota rows | `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary` | - [x] |
| 17 | dashboard-summary-endpoint | Dashboard Summary Endpoint | annotator summary returns task data | Given an `annotator` caller, when the endpoint is called, then the response carries the 4 annotation stats, the my-tasks panel with 4 rows, and the dataset-readiness side panel | `tests/test_dashboard_summary_roles.py::test_annotator_summary` | - [x] |
| 18 | dashboard-summary-endpoint | Dashboard Summary Endpoint | business_user summary returns extraction data | Given a `business_user` caller, when the endpoint is called, then the response carries the 4 extraction stats, the recent-extractions panel with 4 rows, and the active-model side panel with top extracted fields | `tests/test_dashboard_summary_roles.py::test_business_user_summary` | - [x] |
| 19 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unavailable training service returns null values | Given the training service erroring or timing out, when a `tenant_admin` calls the endpoint, then training-dependent stat values are `null`, `sources.training` is `false`, and the status is 200 | `tests/test_dashboard_summary_roles.py::test_training_service_unavailable` | - [x] |
| 20 | dashboard-summary-endpoint | Dashboard Summary Endpoint | unauthenticated request rejected | Given no valid JWT, when the endpoint is called, then the response is 401 | `tests/test_dashboard_summary_roles.py::test_unauthenticated_rejected` | - [x] |
| 21 | dashboard-summary-endpoint | Dashboard Summary Endpoint | one tenant schema failure does not blank out other tenants' stats | Given one active tenant's schema missing a table or column and the rest healthy, when a `system_admin` calls the endpoint, then status is 200, pending-approval and avg-F1 reflect the healthy tenants, and no later query fails with an aborted-transaction error | `tests/test_dashboard_tenant_enumeration.py::test_one_schema_failure_preserves_other_tenants` | - [x] |
| 22 | dashboard-summary-endpoint | Dashboard Summary Endpoint | The virtual system tenant is excluded from schema iteration | Given a `public.tenants` row `id = 'system'` with no `tenant_system` schema, when a `system_admin` calls the endpoint, then no query is issued against `tenant_system`, no exception is logged for it, and status is 200 | `tests/test_dashboard_tenant_enumeration.py::test_system_tenant_excluded_from_iteration` + gateway log (task 9.3) | - [x] |
| 23 | dashboard-summary-endpoint | Dashboard Summary Endpoint | Tenant rows without a backing schema are excluded from aggregates | Given active tenant rows with no corresponding schema, when a `system_admin` calls the endpoint, then those rows contribute nothing to the document, pending-approval, and model-F1 aggregates and zero missing-schema exceptions are logged | `tests/test_dashboard_tenant_enumeration.py::test_schemaless_tenants_excluded_from_aggregates` | - [x] |
| 24 | dashboard-summary-endpoint | Dashboard Summary Endpoint | A partial aggregate is not reported as a complete total | Given one existing tenant schema whose `documents` query fails, when a `system_admin` calls the endpoint, then the "Documents (all)" stat is not presented as a complete platform total and `sources.documents` is `false` | `tests/test_dashboard_tenant_enumeration.py::test_partial_aggregate_marks_source_false` | - [x] |
| 25 | tenant-schema-migrations | Per-tenant-schema DDL tolerates tenant schemas missing a table | A tenant schema missing annotation_tasks does not abort migration 022 | Given `tenant_a` complete and `tenant_b` with `documents` but no `annotation_tasks`, when migration 022 is applied, then it completes, both gain `purpose`, `tenant_a` is backfilled, and the backfill is skipped for `tenant_b` without raising | `tests/test_migration_022_guard.py::test_missing_annotation_tasks_does_not_abort` | - [x] |
| 26 | tenant-schema-migrations | Per-tenant-schema DDL tolerates tenant schemas missing a table | A tenant schema missing the target table entirely is skipped | Given a tenant schema containing none of the referenced tables, when the migration is applied, then it completes and `alembic_version` advances to that revision | `tests/test_migration_022_guard.py::test_schema_missing_all_target_tables_is_skipped` | - [x] |
| 27 | tenant-schema-migrations | Per-tenant-schema DDL tolerates tenant schemas missing a table | Re-running a guarded loop is a no-op | Given tenant schemas already in the produced shape, when the loop's DDL runs again, then no error occurs and no schema or data changes | `tests/test_migration_022_guard.py::test_guarded_loop_rerun_is_noop` | - [x] |
| 28 | tenant-schema-migrations | Existing tenant schemas are reconciled to the current template shape | A tenant schema provisioned before migration 003 gains its columns | Given a tenant `documents` table lacking `content_type`, `file_size`, and `blob_path`, when reconciliation is applied, then all three exist and upload against that tenant succeeds | `tests/test_tenant_schema_reconciliation.py::test_pre_003_tenant_gains_document_columns` | - [x] |
| 29 | tenant-schema-migrations | Existing tenant schemas are reconciled to the current template shape | A tenant schema missing a whole table gains it from the template | Given `tenant_template.documents` exists and a tenant schema without `documents`, when reconciliation is applied, then that schema has `documents` with the template's columns, defaults, constraints, and indexes | `tests/test_tenant_schema_reconciliation.py::test_missing_table_cloned_from_template` | - [x] |
| 30 | tenant-schema-migrations | Existing tenant schemas are reconciled to the current template shape | Reconciliation preserves tenant-only columns | Given a tenant table carrying a column absent from `tenant_template`, when reconciliation is applied, then that column still exists with unchanged data | `tests/test_tenant_schema_reconciliation.py::test_tenant_only_column_preserved` | - [x] |
| 31 | tenant-schema-migrations | Existing tenant schemas are reconciled to the current template shape | Reconciliation is idempotent | Given reconciliation already applied, when the same DDL runs again, then no error occurs and no schema or data changes | `tests/test_tenant_schema_reconciliation.py::test_reconciliation_is_idempotent` | - [x] |
| 32 | tenant-schema-migrations | Tenant provisioning clones the template atomically | A failed table clone rolls back the whole tenant | Given provisioning in progress, when one tenant-scoped table fails to be created, then no tenant row, schema, or user row for that tenant remains | `tests/test_tenant_provisioning_atomicity.py::test_failed_table_clone_rolls_back_tenant` | - [x] |
| 33 | tenant-schema-migrations | Tenant provisioning clones the template atomically | A provisioned tenant has the full template table set | Given `tenant_template` has N tables, when a tenant is provisioned successfully, then its schema has all N tables and listing its documents returns an empty list rather than an error | `tests/test_tenant_provisioning_atomicity.py::test_provisioned_tenant_has_full_template_table_set` | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Schema verification reference source (Decision 2) | Agent invents a hand-written expected-schema manifest or a JSON snapshot instead of introspecting, reintroducing the second-source-of-truth that Decision 2 explicitly ruled out | Read the verification implementation — confirm `public` checks derive from the migration chain and tenant-schema checks compare against live `tenant_template`, with no checked-in schema fixture file |
| 2 | Enumeration fix scope (Decision 4) | Agent hardcodes an exclusion for `'system'` rather than intersecting tenant rows with `pg_namespace`, leaving the four fixture tenants and any future schema-less tenant still failing | Grep the dashboard implementation for a literal `system` string in the enumeration path — its presence indicates the ruled-out alternative was taken |
| 3 | `sources` semantics (Decision 5) | Agent changes failure handling to return `null` or abort the loop, breaking the in-force requirement that one tenant's failure must not blank out other tenants' stats (row 21) | Run rows 21 and 24 together — 21 must still pass unchanged after the row 24 behaviour is added; confirm per-schema rollback-and-continue is intact |
| 4 | Migration guard placement (tenant-schema-migrations R1) | Agent guards only `ALTER TABLE` statements — which already carry `IF EXISTS` — and leaves the unguarded `UPDATE ... FROM %I.annotation_tasks` in migration 022 that is the actual abort source | Read migration 022's `DO` block line by line; confirm the `UPDATE` specifically is guarded, not just the `ALTER` statements around it |
| 5 | Reconciliation approach (Decision 6) | Agent retrofits per-tenant loops into migrations 003 and earlier, which never re-run on databases already past those revisions, so the fix silently applies only to databases built from scratch | Confirm a new forward revision exists and that no already-applied revision file was edited; check `git diff` touches no migration below the new one except 022's guard |
| 6 | Destructive step automation (ADR-005) | Agent scripts `docker compose down -v` into `db-init`, a hook, or a make target that runs unprompted, turning a deliberate operator action into an automatic data loss | Confirm volume removal appears only as a documented operator step; grep the repo for `down -v` outside documentation |
| 7 | Verification strictness (Risks section) | Agent fails verification on objects the chain does not declare (developer scratch tables, MLflow's own tables), making the stack unstartable for benign reasons | Create a scratch table in `public`, run verification, confirm it still passes — presence-of-declared-objects only, not exact-match |
| 8 | Untracked dependency (Risks section) | Agent rebuilds images before `src/shared/retrieval/` is tracked, producing an image where the staged `chunking_service.py` deletion has no replacement and `ocr_worker` fails to import | Run `git status --porcelain src/shared/retrieval/` before the build step — it must return nothing untracked |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant gets a dedicated Postgres schema `tenant_<id>` cloned from `tenant_template` | Verification and reconciliation operate per schema; the `tenant_system` fix must not collapse tenants into a shared schema | After rebuild, confirm each tenant row with data has its own `tenant_<id>` schema and that no cross-schema query was introduced in the dashboard enumeration path |
| ADR-003: Per-Tenant Model Serving Topology | Model serving is scoped per tenant | No global `public.model_versions` table may be reintroduced or depended on | Query `information_schema.tables` after rebuild — `public.model_versions` must be absent; grep the codebase for `public.model_versions` references |
| ADR-004: OpenSpec Spec-Driven Development Governance | Behaviour changes are specified before implementation | Dashboard and migration behaviour changes must trace to a delta spec in this change | For each behaviour change in the diff, identify the spec requirement it implements; any behaviour change without a spec row is a governance violation |
| ADR-005: OpenCode Agent Permissions and Boundaries | Agents operate within declared boundaries | Volume removal is an operator step, never automated | Grep for `down -v` and `docker volume rm` outside documentation — no automation path may invoke them |
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Training runs asynchronously via Celery workers | Hard-failing `db-init` must prevent worker startup cleanly, not deadlock it | With a deliberately drifted database, run `docker compose up` and confirm `celery_worker` and `celery_worker_extraction` exit or remain uncreated rather than hanging |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | RAG pipeline over per-tenant `document_chunks` | The rebuilt schema must carry migration 021's page-metadata and 022's purpose columns on `document_chunks` | After rebuild, inspect `tenant_template.document_chunks` — `page_number`, `char_start`, `char_end`, and `purpose` must all be present |
| ADR-008: Base Model as Default Inference Model | Base model serves when no tenant model is promoted | A freshly rebuilt empty database has no promoted model; dashboards and extraction must still function | On the rebuilt stack before any training run, load each role's dashboard and run an extraction — both must succeed with the base model |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Row 1: live rebuild — `alembic_version` = 023 (chain head), `tenant_template.documents` has `purpose`/`content_type`/`file_size`/`blob_path`, `tenant_template.document_chunks` has `page_number`/`char_start`/`char_end`/`purpose`
- [x] Row 2: `docs/local-dev.md` — "This procedure is destructive" section (lines 10-15) precedes the first command (`docker compose down -v`, line ~32)
- [x] Row 3: live rebuild transcript — `docker compose build` completed (all 12 images built) before `docker compose up`; `db-init` log lists every revision 001→023 in order
- [x] Row 4: live rebuild — `db-init` log ends "Schema verification passed: no drift detected." after seed; exit code 0
- [x] Row 5: `tests/test_verify_schema.py::test_missing_public_column_detected` passes; also reproduced live via `docker compose run --rm db-init` after dropping `validation_rule` → exit 1, "missing column 'validation_rule'"
- [x] Row 6: `tests/test_verify_schema.py::test_missing_template_table_detected` passes
- [x] Row 7: `tests/test_verify_schema.py::test_tenant_schema_lagging_template_detected` passes
- [x] Row 8: live probe — `docker compose run --rm db-init` against `ner_dev` with `validation_rule` dropped: exit code 1, drift named, all 14 other services remained in their prior state (none restarted/failed)
- [x] Row 9: live rebuild — `docker compose up` transcript: `db-init` exited 0, all 8 application services + workers started and remain `running`
- [x] Row 10: `tests/test_setup_test_db_guard.py::test_refuses_dev_database` passes (checks exit≠0, "ner_dev" named, no progress markers in output)
- [x] Row 11: `tests/test_setup_test_db_guard.py::test_allows_test_database` passes
- [x] Row 12: `tests/test_setup_test_db_guard.py::test_guard_reads_env_url_not_default` passes
- [x] Row 13: `tests/test_setup_test_db_guard.py::test_override_permits_nonstandard_name` passes
- [x] Row 14: `tests/test_setup_test_db_guard.py::test_unset_override_keeps_guard` passes
- [x] Row 15: live API trace — `GET /api/v1/dashboard/summary` as `system_admin`: 200, `kicker: "Platform control plane"`, 4 stats, `pTitle: "Approval queue"`, 4 pRows, `sideTop: "Platform health"`; also `tests/test_dashboard_summary_roles.py::test_system_admin_summary_returns_role_specific_data`
- [x] Row 16: `tests/test_dashboard_summary_roles.py::test_tenant_admin_summary_returns_pipeline_data` passes; also live trace as `tenant_admin` for `acme-verify` tenant: 200, `pTitle: "Pipeline activity"`
- [x] Row 17: `tests/test_dashboard_summary_roles.py::test_annotator_summary_returns_task_data` passes
- [x] Row 18: `tests/test_dashboard_summary_roles.py::test_business_user_summary_returns_extraction_data` passes
- [x] Row 19: `tests/test_dashboard_summary_roles.py::test_unavailable_training_service_returns_null_values` passes
- [x] Row 20: `tests/test_dashboard_summary_roles.py::test_unauthenticated_request_rejected` passes; also live trace confirms 401
- [x] Row 21: `tests/test_dashboard_tenant_enumeration.py::test_one_schema_failure_preserves_other_tenants` passes
- [x] Row 22: live trace — `GET /api/v1/dashboard/summary` as `system_admin` on rebuilt stack: 200, `docker logs ner-project-gateway-1 --since 2m | grep -c tenant_system` = 0
- [x] Row 23: `tests/test_dashboard_tenant_enumeration.py::test_schemaless_tenants_excluded_from_aggregates` passes
- [x] Row 24: `tests/test_dashboard_tenant_enumeration.py::test_partial_aggregate_marks_source_false` passes
- [x] Row 25: `tests/test_migration_022_guard.py::test_missing_annotation_tasks_does_not_abort` passes
- [x] Row 26: `tests/test_migration_022_guard.py::test_schema_missing_all_target_tables_is_skipped` passes
- [x] Row 27: `tests/test_migration_022_guard.py::test_guarded_loop_rerun_is_noop` passes
- [x] Row 28: `tests/test_tenant_schema_reconciliation.py::test_pre_003_tenant_gains_document_columns` passes (includes a successful INSERT matching document_service's upload columns)
- [x] Row 29: `tests/test_tenant_schema_reconciliation.py::test_missing_table_cloned_from_template` passes (column set, PK, and index all verified)
- [x] Row 30: `tests/test_tenant_schema_reconciliation.py::test_tenant_only_column_preserved` passes
- [x] Row 31: `tests/test_tenant_schema_reconciliation.py::test_reconciliation_is_idempotent` passes
- [x] Row 32: `tests/test_tenant_provisioning_atomicity.py::test_failed_table_clone_rolls_back_tenant` passes
- [x] Row 33: `tests/test_tenant_provisioning_atomicity.py::test_provisioned_tenant_has_full_template_table_set` passes; also live: created tenant `acme-verify`, uploaded/listed documents successfully end-to-end

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations); each of the 7 Decisions in design.md maps to a specific diff (Decision 1→rebuild procedure, 2→verify_schema.py reference source, 3→docker-compose depends_on wiring, 4→pg_namespace join, 5→docs_complete/sources flag, 6→migration 023, 7→setup_test_db.py guard)
- [x] All ADR compliance steps in Section 3 confirmed — see per-ADR notes below
- [x] No undocumented architectural patterns introduced — all changes are additive to existing patterns already in the codebase (raw-SQL Alembic migrations, per-tenant DO-block loops, FastAPI dependency-injected sessions)
- [x] No AI-invented requirements present in generated code (cross-checked against spec files) — every code change traces to a numbered requirement in specs/dev-database-reset, specs/test-fixture-db-isolation, specs/dashboard-summary-endpoint, or specs/tenant-schema-migrations

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `src/gateway/verify_schema.py` derives its reference from `Base.metadata` (public) and by regex-scanning `alembic/versions/*.py` for `CREATE TABLE tenant_template.*` (tenant-scoped); no checked-in expected-schema fixture file exists
- [x] Risk 2 mitigation confirmed — `grep -n "'system'\|\"system\"" src/gateway/api/v1/dashboard.py` returns zero hits; enumeration is a `public.tenants JOIN pg_namespace` query
- [x] Risk 3 mitigation confirmed — `test_one_schema_failure_preserves_other_tenants` and `test_partial_aggregate_marks_source_false` both pass; per-schema rollback-and-continue verified intact
- [x] Risk 4 mitigation confirmed — migration 022's `UPDATE ... FROM %I.annotation_tasks` is wrapped in a `to_regclass(...) IS NOT NULL` guard specifically, not just the surrounding `ALTER TABLE IF EXISTS` statements
- [x] Risk 5 mitigation confirmed — `023_reconcile_tenant_schemas.py` is a new file; only `022_document_purpose_scoping.py` was edited among existing migrations (added the guard), no other already-applied revision touched
- [x] Risk 6 mitigation confirmed — `grep -rln "down -v\|volume rm" --include=*.py --include=*.sh --include=*.yml --include=*.json --include=Makefile .` (excluding node_modules/venv/.git) returns zero hits; the instruction exists only in `docs/local-dev.md`
- [x] Risk 7 mitigation confirmed — `test_undeclared_scratch_table_does_not_fail` passes (a `public.developer_scratch_table` does not trigger a false positive)
- [x] Risk 8 mitigation confirmed — `git add src/shared/retrieval/` run in task 1.1; `git status --porcelain src/shared/retrieval/` returned empty before any image rebuild

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_verify_schema.py -q` → 5 passed | Rows 4-7 (verify_schema detection + clean pass), Risk 7 | claude-opus-5 | 2026-07-27 |
| 2 | Functional | `pytest tests/test_setup_test_db_guard.py -q` → 5 passed | Rows 10-14 | claude-opus-5 | 2026-07-27 |
| 3 | Functional | `pytest tests/test_dashboard_summary_roles.py -q` → 6 passed | Rows 15-20 | claude-opus-5 | 2026-07-27 |
| 4 | Functional | `pytest tests/test_dashboard_tenant_enumeration.py -q` → 4 passed | Rows 21-24 | claude-opus-5 | 2026-07-27 |
| 5 | Functional | `pytest tests/test_migration_022_guard.py -q` → 3 passed | Rows 25-27, Risk 4 | claude-opus-5 | 2026-07-27 |
| 6 | Functional | `pytest tests/test_tenant_schema_reconciliation.py -q` → 4 passed | Rows 28-31 | claude-opus-5 | 2026-07-27 |
| 7 | Functional | `pytest tests/test_tenant_provisioning_atomicity.py -q` → 2 passed | Rows 32-33 | claude-opus-5 | 2026-07-27 |
| 8 | Functional | Live rebuild transcript: `docker compose down -v` → `docker compose build` (12 images) → `docker compose up`; `db-init` log lists revisions 001→023 in order, seed output, "Schema verification passed: no drift detected.", exit 0 | Rows 1, 3, 4, 9 | claude-opus-5 | 2026-07-27 |
| 9 | Functional | Post-rebuild introspection: `alembic_version`=023; `tenant_template.documents` and `.document_chunks` column dumps; `\dt public.*` shows 6 tables, no `model_versions` | Row 1, ADR-003, ADR-007 | claude-opus-5 | 2026-07-27 |
| 10 | Functional | Live drift probe: dropped `public.entity_definitions.validation_rule`, ran `docker compose run --rm db-init` → exit 1, "Schema drift detected: - public.entity_definitions: missing column 'validation_rule'"; restored column, re-ran → exit 0, "no drift detected"; `docker compose ps` showed all 14 services still `running` throughout (untouched) | Row 8, ADR-006 | claude-opus-5 | 2026-07-27 |
| 11 | Functional | `docs/local-dev.md` review — destructive-effect section precedes first command | Row 2 | claude-opus-5 | 2026-07-27 |
| 12 | Functional | Live E2E: POST `/api/v1/tenants/demo-corp/entity-types` with `validation_rule` → 201 Created | Task 9.1 (originally-reported bug #2, "Failed to fetch") | claude-opus-5 | 2026-07-27 |
| 13 | Functional | Live E2E: created tenant `acme-verify`, uploaded PDF (`purpose=query`), listed documents → 200 with 1 document; uploaded second doc `purpose=training` → `SELECT purpose FROM tenant_....documents` shows `query`/`training` correctly | Row 33, Task 9.2/9.4 (originally-reported bug #3, "cannot upload documents") | claude-opus-5 | 2026-07-27 |
| 14 | Functional | Live E2E: `GET /api/v1/dashboard/summary` as `system_admin` → 200; `docker logs ner-project-gateway-1 --since 2m \| grep -c tenant_system` → 0 | Row 22 (originally-reported log-spam symptom) | claude-opus-5 | 2026-07-27 |
| 15 | Edge Case | Live E2E: tenant_admin dashboard for `acme-verify` (0 promoted models) → 200 with graceful nulls/"no model promoted"; `POST /api/v1/extract` → 200, `model_version: "0"` (base model) | ADR-008 | claude-opus-5 | 2026-07-27 |
| 16 | Structural | Code diff reviewed against design.md's 7 Decisions and specs' requirements; `grep` checks for Risks 1, 2, 5, 6, 8 (see Section 2 Edge Case Evidence for exact commands/output) | Hallucination Risk Register (all 8) | claude-opus-5 | 2026-07-27 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** clean-rebuild-and-schema-hardening
**Proposal:** `openspec/changes/clean-rebuild-and-schema-hardening/proposal.md`
**Spec files reviewed:**
  - specs/dev-database-reset/spec.md
  - specs/test-fixture-db-isolation/spec.md
  - specs/dashboard-summary-endpoint/spec.md
  - specs/tenant-schema-migrations/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
