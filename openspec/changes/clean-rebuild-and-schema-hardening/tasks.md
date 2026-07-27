## 1. Tree Hygiene (must precede any image rebuild)

- [x] 1.1 Track `src/shared/retrieval/` in git (`git add src/shared/retrieval/`) so the staged `chat_api/services/chunking_service.py` deletion has its replacement, and confirm `git status --porcelain src/shared/retrieval/` returns empty.
- [x] 1.2 Verify `src/document_service/services/ocr_worker.py` and `src/chat_api/services/rag_orchestrator.py` import cleanly from `src.shared.retrieval` with no leftover references to the deleted `chunking_service` (`python -c "import src.document_service.services.ocr_worker"`).

## 2. Dashboard Tenant Enumeration

- [x] 2.1 Rewrite `_all_tenant_schemas` in `src/gateway/api/v1/dashboard.py` to return only schemas that exist, by intersecting `public.tenants` rows with `pg_namespace` in a single query. Do not add a literal `'system'` exclusion (design.md Decision 4).
- [x] 2.2 In `_system_admin_data`, set the relevant `sources` entry to `false` when a query against an existing tenant schema fails, so a partial aggregate is not labelled complete (design.md Decision 5). Leave the per-schema rollback-and-continue behaviour unchanged.
- [x] 2.3 Add `tests/test_dashboard_tenant_enumeration.py::test_system_tenant_excluded_from_iteration` — asserts no query is issued against `tenant_system` and no exception is logged for it (verification row 22).
- [x] 2.4 Add `tests/test_dashboard_tenant_enumeration.py::test_schemaless_tenants_excluded_from_aggregates` — asserts schema-less tenant rows contribute nothing and log zero missing-schema exceptions (verification row 23).
- [x] 2.5 Add `tests/test_dashboard_tenant_enumeration.py::test_partial_aggregate_marks_source_false` — asserts `sources.documents` is `false` when an existing schema's `documents` query fails (verification row 24).
- [x] 2.6 Add `tests/test_dashboard_tenant_enumeration.py::test_one_schema_failure_preserves_other_tenants` — regression guard that row 21's existing behaviour still holds after 2.2 (verification row 21).
- [x] 2.7 Add `tests/test_dashboard_summary_roles.py` covering the four role responses, the unavailable-training-service case, and the unauthenticated case (verification rows 15–20).

## 3. Migration Robustness

- [x] 3.1 Guard the `UPDATE %I.documents ... WHERE id IN (SELECT document_id FROM %I.annotation_tasks)` statement in `alembic/versions/022_document_purpose_scoping.py` so a tenant schema without `annotation_tasks` skips it instead of aborting the `DO` block. Do not edit any revision below 022.
- [x] 3.2 Add `tests/test_migration_022_guard.py::test_missing_annotation_tasks_does_not_abort` — two fixture schemas, one incomplete; asserts migration completes, both gain `purpose`, complete schema is backfilled (verification row 25).
- [x] 3.3 Add `tests/test_migration_022_guard.py::test_schema_missing_all_target_tables_is_skipped` — asserts completion and `alembic_version` advance (verification row 26).
- [x] 3.4 Add `tests/test_migration_022_guard.py::test_guarded_loop_rerun_is_noop` — asserts re-running the loop DDL raises nothing and changes nothing (verification row 27).

## 4. Tenant Schema Reconciliation

- [x] 4.1 Write a new forward Alembic revision (`023_reconcile_tenant_schemas`) that walks every `tenant_<id>` schema, creates tables present in `tenant_template` but absent there via `LIKE ... INCLUDING DEFAULTS INCLUDING CONSTRAINTS INCLUDING INDEXES`, and adds columns present in the template's copy but absent from the tenant's. Must be idempotent and must not drop or alter tenant-only columns.
- [x] 4.2 Confirm 4.1 covers migration `003`'s template-only columns: `documents.content_type`, `documents.file_size`, `documents.blob_path`, `documents.updated_at`, and `document_text_spans.span_index`, `.char_start`, `.char_end`, `.page_number`, `.created_at`.
- [x] 4.3 Add `tests/test_tenant_schema_reconciliation.py::test_pre_003_tenant_gains_document_columns` — includes a successful upload against the reconciled tenant (verification row 28).
- [x] 4.4 Add `tests/test_tenant_schema_reconciliation.py::test_missing_table_cloned_from_template` — asserts columns, defaults, constraints, and indexes match the template (verification row 29).
- [x] 4.5 Add `tests/test_tenant_schema_reconciliation.py::test_tenant_only_column_preserved` — asserts the extra column and its data survive (verification row 30).
- [x] 4.6 Add `tests/test_tenant_schema_reconciliation.py::test_reconciliation_is_idempotent` — asserts a second run raises nothing and produces an empty schema diff (verification row 31).

## 5. Tenant Provisioning Atomicity

- [x] 5.1 Make `TenantService.create_tenant` in `src/gateway/services/tenant_service.py` roll back the tenant row, schema, and admin user together if any table clone fails, so no partially-provisioned tenant can survive.
- [x] 5.2 Add `tests/test_tenant_provisioning_atomicity.py::test_failed_table_clone_rolls_back_tenant` — forces a table-creation failure and asserts no residual tenant row, schema, or user row (verification row 32).
- [x] 5.3 Add `tests/test_tenant_provisioning_atomicity.py::test_provisioned_tenant_has_full_template_table_set` — asserts table-count parity with `tenant_template` and that listing documents returns an empty list, not an error (verification row 33).

## 6. Fixture Script Guard

- [x] 6.1 Add a database-name guard to `scripts/setup_test_db.py` that resolves the name from the URL actually used (including the `NER_DATABASE_URL` override), refuses anything not ending in `_test`, exits non-zero naming the rejected database, and performs no DDL or DML before exiting.
- [x] 6.2 Add an opt-in override environment variable that permits a non-standard name and emits a warning naming the target. Its absence must never weaken the guard.
- [x] 6.3 Add `tests/test_setup_test_db_guard.py::test_refuses_dev_database` — asserts non-zero exit, `ner_dev` named, and no object created (verification row 10).
- [x] 6.4 Add `tests/test_setup_test_db_guard.py::test_allows_test_database` — asserts fixtures created and exit 0 (verification row 11).
- [x] 6.5 Add `tests/test_setup_test_db_guard.py::test_guard_reads_env_url_not_default` — asserts the env-var target is what gets evaluated (verification row 12).
- [x] 6.6 Add `tests/test_setup_test_db_guard.py::test_override_permits_nonstandard_name` — asserts it proceeds and warns (verification row 13).
- [x] 6.7 Add `tests/test_setup_test_db_guard.py::test_unset_override_keeps_guard` — asserts refusal (verification row 14).

## 7. Schema Verification Step

- [x] 7.1 Write `src/gateway/verify_schema.py` — introspects the live database and checks: `public` tables carry the columns the migration chain declares; `tenant_template` contains every tenant-scoped table the chain declares; each `tenant_<id>` schema's table set matches `tenant_template`. Check presence of declared objects only; extra undeclared objects must not fail (design.md Risks, Hallucination Risk 7).
- [x] 7.2 Make `verify_schema` exit non-zero on drift with a message naming each drifted schema, table, and column.
- [x] 7.3 Wire `python -m src.gateway.verify_schema` into the `db-init` command in `docker-compose.yml`, after `alembic upgrade head` and the seed step, so drift blocks `db-init` completion and therefore all dependent services.
- [x] 7.4 Add `tests/test_verify_schema.py::test_clean_database_passes` — asserts no drift reported and exit 0 (verification row 4).
- [x] 7.5 Add `tests/test_verify_schema.py::test_missing_public_column_detected` — drops `validation_rule`, asserts the column is named and exit is non-zero (verification row 5).
- [x] 7.6 Add `tests/test_verify_schema.py::test_missing_template_table_detected` — drops `tenant_template.documents`, asserts it is reported and exit is non-zero (verification row 6).
- [x] 7.7 Add `tests/test_verify_schema.py::test_tenant_schema_lagging_template_detected` — asserts the schema and table are named and exit is non-zero (verification row 7).
- [x] 7.8 Add `tests/test_verify_schema.py::test_undeclared_scratch_table_does_not_fail` — creates an extra `public` table and asserts verification still passes (Hallucination Risk 7).

## 8. Clean Rebuild Procedure

- [x] 8.1 Document the clean-rebuild procedure in `README.md` (or `docs/local-dev.md` if the README is already long), with the destructive-effect statement placed above the first command, followed by the ordered steps: `docker compose down -v`, `docker compose build`, `docker compose up`.
- [x] 8.2 Confirm the destructive step appears only as an operator instruction — grep the repo for `down -v` and `docker volume rm` and confirm no script, hook, or make target invokes them (ADR-005, Hallucination Risk 6).
- [x] 8.3 Execute the procedure: `docker compose down -v`, then `docker compose build`, then `docker compose up`. Capture the full terminal transcript (verification rows 1, 3, 9).
- [x] 8.4 Confirm post-rebuild state by query: `alembic_version` at chain head, `tenant_template.documents` present, `public.entity_definitions` carrying all declared columns, `public.model_versions` absent, `tenant_template.document_chunks` carrying `page_number`/`char_start`/`char_end`/`purpose` (verification row 1; ADR-003 and ADR-007 compliance).
- [x] 8.5 Capture the procedure-document excerpt showing the destructive warning above the first command (verification row 2).
- [x] 8.6 Run `docker compose up` against a deliberately drifted copy and capture the transcript showing `db-init` non-zero exit, no application service started, drifted objects named, and Celery workers exiting rather than hanging (verification row 8; ADR-006 compliance).

## 9. End-to-End Confirmation of the Reported Bugs

- [x] 9.1 Create an entity type through the portal against the rebuilt stack and confirm it succeeds — closes the `column "validation_rule" does not exist` failure.
- [x] 9.2 Create a new tenant, upload a document to it, and list its documents — closes the `relation "tenant_<id>.documents" does not exist` failure.
- [x] 9.3 Load the `system_admin` dashboard and capture the gateway log showing zero `tenant_system` entries alongside the 200 response (verification row 22).
- [x] 9.4 Upload one `query` document and one `training` document and confirm the `purpose` column is populated — proves migration 022 applied and the staged document-purpose-scoping work is exercisable.
- [x] 9.5 With no promoted model present on the fresh database, load each role's dashboard and run one extraction — both must succeed via the base model (ADR-008 compliance).

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate clean-rebuild-and-schema-hardening --type change --strict` and confirm it exits clean before archive.
