## 1. Baseline

- [x] 1.1 Confirm Docker Postgres is reachable on host port **55432** (not 5432 — a native PostgreSQL 18 service occupies 5432 and returns a misleading auth failure). Record the connection string used.
- [x] 1.2 Run the full pytest suite on unmodified `main` and save the summary line plus the sorted list of failing/erroring test ids to a scratch file. This is the baseline; the suite is expected red (~89 failed / 31 errors). Do not chase pre-existing failures.
- [x] 1.3 Apply migration `037` against the dev database and confirm `alembic current` reports `037`. It is written but unapplied; nothing that reads `cardinality` or `sql_identifier` may run before this.
- [x] 1.4 Record which tenant schemas already exist and which of them contain `document_entities`, so the "schema without `document_entities` is skipped" path can be exercised against a real case.
- [x] 1.5 Query `SELECT tenant_id, name FROM public.entity_definitions WHERE sql_identifier IS NULL` and record the result. These are entity types created after `037` through the current create path, which assigns no identifier; they are invisible to the reconciler and the projection until repaired in task 13.7.

## 2. Retarget the generator from views to tables

- [x] 2.1 In `src/shared/entity_views.py`, rename `build_entity_view_statements` to `build_entity_table_statements` and replace child-view DDL with `CREATE TABLE IF NOT EXISTS <schema>.<sql_identifier>` carrying the fixed column list (`document_id VARCHAR NOT NULL`, `value TEXT NOT NULL`, `normalized_value TEXT NOT NULL`, `value_number DOUBLE PRECISION`, `value_number_high DOUBLE PRECISION`, `value_date DATE`, `value_date_high DATE`, `value_unit TEXT`, `confidence DOUBLE PRECISION NOT NULL`, `page_number INTEGER`, `occurrence_count INTEGER NOT NULL DEFAULT 1`), `PRIMARY KEY (document_id, normalized_value)`, and no `REFERENCES` clause. Verifies rows 44, 46, 47.
- [x] 2.2 Emit `CREATE INDEX IF NOT EXISTS idx_<sql_identifier>_normalized_value ON <schema>.<sql_identifier> (normalized_value)` alongside each child table. Verifies row 44.
- [x] 2.3 Replace the `subject` view builder with `CREATE TABLE IF NOT EXISTS <schema>.subject (document_id VARCHAR PRIMARY KEY, filename TEXT)` plus one `ALTER TABLE … ADD COLUMN IF NOT EXISTS <column> <type>` per active `single` definition, typed `DOUBLE PRECISION` for `number`/`money`/`duration`/`boolean`, `DATE` for `date`, `TEXT` otherwise. Emit exactly one column per single definition — no `_text` companion. Verifies rows 48, 50, 51.
- [x] 2.4 Delete the `DROP VIEW IF EXISTS <schema>.subject CASCADE` emission and every code path that produced it. Verifies row 69.
- [x] 2.5 Delete `build_drop_view_statements` and every drop emission for inactive or absent definitions. Add a module-level assertion (test or construction) that the module emits no `DROP`, `DELETE`, or `TRUNCATE`. Verifies rows 43, 70.
- [x] 2.6 Keep the existing `_unique_column` disambiguation for the `subject` column name — `sql_identifier` minus the `e_` prefix, checked against `{document_id, filename}` and already-taken columns. Verifies row 52.
- [x] 2.7 Keep the zero-`single`-definitions path emitting the bare `subject` table. Verifies row 49.
- [x] 2.8 Promote `_entity_type_literals` to a public `entity_type_literals(definition)` returning the sorted uppercased name plus uppercased `base_label_mapping` keys. Keep an alias only if an existing import needs it. Verifies rows 54, 55, 56, 57, 58.
- [x] 2.9 Keep `to_sql_identifier`, `EntityDefinitionSpec`, `_ordered`, the schema-argument validation, and the deterministic `sql_identifier` ordering unchanged. Confirm generation is byte-identical across calls. Verifies rows 39, 40, 41, 42, 45.
- [x] 2.10 Rename the reconciler to `reconcile_entity_tables(session, schema, definitions)`, keep the `document_entities`-missing skip, keep the bare-`subject` creation for a tenant with no definitions, and remove every drop it previously applied. Add a log line naming any generated table whose definition is absent from the catalog. Verifies rows 59, 60, 61, 62, 63, 68.
- [x] 2.11 Update the module docstring: replace the view rationale with the table rationale (metadata-only `ADD COLUMN`, `pg_tables` grant guard, real primary key), record that deactivation never drops, and keep the `TenantService.create_tenant` note that a cloned tenant starts with zero generated tables.
- [x] 2.12 Rewrite `tests/test_entity_views_generator.py`: retarget every view assertion to table DDL, delete the drop-on-inactive and `DROP VIEW … CASCADE` assertions, add the no-destructive-statement assertion, add the value-kind-independent column-list case, the `DATE` case, the no-`REFERENCES` case, and the public-`entity_type_literals` case. Verifies rows 39–58, 69, 70.
- [x] 2.13 Rewrite `tests/test_entity_views_reconciler.py`: retarget to tables, add the assertion that a deactivated definition's table and rows survive reconciliation, and the later-added-column preservation case. Verifies rows 53, 59–63, 65.

## 3. Definition loader

- [x] 3.1 Add a **sibling** loader in `src/extraction_service/services/semantic_normalizer.py` returning `list[EntityDefinitionSpec]` with `name`, `sql_identifier`, `cardinality`, `value_kind`, `is_active`, `base_label_mapping`, filtered by `tenant_id`. Do not change `load_entity_type_config`'s return type — `apply_semantic_normalization` and `postprocess_document` consume it.
- [x] 3.2 Skip any definition whose `sql_identifier` is NULL. Do not slug at read time — a read-time slug is not stable across processes. Verifies row 35.
- [x] 3.3 Unit-test the loader: definitions are returned filtered by tenant, NULL-identifier rows are omitted, and ordering is deterministic by `sql_identifier`.

## 4. Projection module — pure generators

- [x] 4.1 Create `src/extraction_service/services/relational_projection.py` with a docstring stating: the single-write-point rule, that the module consumes the in-memory list and never re-reads `document_entities`, that it emits no DDL, and that its pure builders exist so the sync worker and the async delete path share one implementation.
- [x] 4.2 Implement the routing index: a `dict[str, EntityDefinitionSpec]` keyed by every uppercased literal from `entity_type_literals`, looked up by `entity.entity_type.strip().upper()`. Verifies rows 6, 7, 8, 9.
- [x] 4.3 Implement collision resolution: exact uppercased `name` match wins; otherwise the first definition by `sql_identifier` sort order; log a warning naming both. Never index one literal to two definitions. Verifies rows 10, 11, 12.
- [x] 4.4 Implement the unroutable path: entities whose literal no active definition claims are skipped at debug level and never fail the document. Verifies row 13.
- [x] 4.5 Implement `select_single_value(entities)` sorting by `(-confidence, -occurrence_count, normalized_value)` and taking the first. Docstring must record that `collapse_duplicates` sets confidence to the `min` of merged values, which is why the second and third keys are required rather than defensive. Verifies rows 16, 17, 18.
- [x] 4.6 Implement the value-kind mapping: `value_number` for `number`/`money`/`duration`/`boolean`, `value_date` for `date`, surface value otherwise; NULL stays NULL with no fallback to surface text in a typed column. Verifies rows 19, 20, 21.
- [x] 4.7 Implement `build_projection_statements(schema, document_id, filename, entities, specs) -> list[tuple[str, dict]]`: one `subject` upsert always (even with zero entities), one child-table insert per routed multi entity with `ON CONFLICT (document_id, normalized_value) DO UPDATE` taking `GREATEST` confidence and summing `occurrence_count`. Pure — executes nothing, opens nothing, emits no DDL. Verifies rows 4, 14, 15, 22, 24, 32.
- [x] 4.8 Write `filename` onto the `subject` row on every projection. Verifies row 22.
- [x] 4.9 Project `confidence` and `page_number` to child tables only; project no provenance field to either relation. Verifies rows 33, 34.
- [x] 4.10 Implement `build_relational_delete_statements(schema, document_id, specs) -> list[tuple[str, dict]]` clearing every **existing** generated child table for the document plus its `subject` row — not only currently-active definitions. Pure. Verifies rows 27, 28, 30.
- [x] 4.11 Validate every identifier against `^e_[a-z0-9][a-z0-9_]*$` before it enters a statement; pass entity-type literals as bound parameters, never interpolated. Verifies rows 35, 36.
- [x] 4.12 Take the tenant schema from the caller's argument. Add no schema-resolution helper to this module. Verifies rows 37, 38.
- [x] 4.13 Write `tests/test_relational_projection_generator.py` covering rows 4, 6–21, 22, 24, 28, 30, 32–38 — all database-free.

## 5. Projection module — executors

- [x] 5.1 Implement `project_document_entities(conn, schema, document_id, filename, entities, specs)` executing the built statements on the caller's connection. It must not open a connection or begin a transaction.
- [x] 5.2 Implement `delete_relational_entities(conn, schema, document_id, specs)` the same way.
- [x] 5.3 Let a missing relation or column propagate rather than catching it, so the document fails and the transaction rolls back. Verifies row 31.
- [x] 5.4 Add a test asserting the worker's delete statement list and the document-delete path's delete statement list are equal for the same document. Verifies row 29.

## 6. Worker wiring

- [x] 6.1 In `src/extraction_service/worker.py`, load `list[EntityDefinitionSpec]` once per run, before the document loop.
- [x] 6.2 Call `reconcile_entity_tables` once per run, before the document loop, in its **own** transaction — never inside a per-document transaction. Verifies rows 79, 80, 84.
- [x] 6.3 Inside the existing `with engine.begin() as conn:` at `worker.py:312`, add `delete_document_entities(conn, schema, doc_id)` and `delete_relational_entities(conn, schema, doc_id, specs)` before the inserts, and `project_document_entities(...)` after `insert_document_entities`. Order: EAV delete, relational delete, `extracted_entities` insert, EAV insert, projection. Verifies rows 1, 25, 81.
- [x] 6.4 Confirm no delete against `extracted_entities` is added — it is the idempotency ledger `get_already_extracted` joins against. Verifies row 26.
- [x] 6.5 Leave the `extracted_entities` insert loop, `get_already_extracted`, the eligibility check at `worker.py:205-208`, and the per-document `try/except: continue` untouched. Verifies rows 2, 71–78, 82.
- [x] 6.6 Confirm no file in the post-processing path is modified: `entity_postprocessor.py`, `entity_normalizer.py`, and `insert_document_entities` itself stay unchanged. Verifies row 5.
- [x] 6.7 Write `tests/test_relational_projection_worker.py` covering rows 1, 2, 5, 13, 14, 15, 22, 23, 24, 25, 26, 27, 31, 79, 80, 81, 82, 83, 84.
- [x] 6.8 Run `tests/test_batch_extraction.py` and `tests/test_batch_extraction_eligibility.py` against the baseline and confirm no new failures. Verifies rows 71–78.

## 7. Entity definition service — configuration path

- [x] 7.1 In `create_entity_type`, load the tenant's already-used `sql_identifier` values, call `to_sql_identifier(payload["name"], taken)`, and add `sql_identifier` to the `INSERT` column list and parameters. Verifies rows 102, 103, 105.
- [x] 7.2 Add `cardinality` to the same `INSERT`, defaulting to `'multi'` when the payload omits it. Verifies rows 106, 107.
- [x] 7.3 Add a `_validate_cardinality` helper mirroring `_validate_value_kind`, rejecting anything outside `{'single','multi'}` with a `ValidationError` naming both values. Call it from create and update **before** the write — the `037` CHECK constraint is the backstop, not the validation path. Verifies row 109.
- [x] 7.4 Add `cardinality` to `update_entity_type`'s `allowed_fields`. Do **not** add `sql_identifier` — it is assigned once and never changed. Verifies rows 104, 108.
- [x] 7.5 Add `cardinality` and `sql_identifier` to both `SELECT` column lists (`list_entity_types` and `_get_by_name`) and to `_row_to_dict`. Verifies rows 110, 111, 112.
- [x] 7.6 Ignore a client-supplied `sql_identifier` in create and update rather than failing the request. Verifies row 113.
- [x] 7.7 Confirm `to_sql_identifier` is imported from `src/shared/entity_views.py` — do not reimplement the slug rule, which would drift from the one migration `037` used. Verifies row 103.
- [x] 7.8 Add `cardinality VARCHAR(16) NOT NULL DEFAULT 'multi'` and `sql_identifier VARCHAR(63)` to the `public.entity_definitions` DDL in `scripts/setup_test_db.py:110` so the test database matches the migrated shape.
- [x] 7.9 Write `tests/test_entity_type_view_metadata_api.py` covering rows 102–113.

## 8. Entity definition service — reconciliation

- [x] 8.1 Call `reconcile_entity_tables` after `create_entity_type`, in the same transaction as the insert. Verifies row 114.
- [x] 8.2 Call it after `update_entity_type`, in the same transaction — `cardinality` or `value_kind` may have changed. Verifies row 115.
- [x] 8.3 Call it after `toggle_entity_type`, in the same transaction, in both directions. Verifies rows 65, 67.
- [x] 8.4 Call it after `soft_delete_entity_type`, in the same transaction. Verifies rows 65, 116.
- [x] 8.5 Confirm none of the four paths drops a table or column, in either flag direction. Verifies rows 65, 68, 116.
- [x] 8.6 Confirm a `multi` to `single` update adds the `subject` column while leaving the child table and its rows intact, and that the reverse leaves the `subject` column in place. Verifies row 115.
- [x] 8.7 Write `tests/test_entity_definition_reconcile.py` covering rows 64, 65, 66, 67, 68, 114, 115, 116.

## 9. Entity types API schemas

- [x] 9.1 In `src/gateway/api/v1/entity_types.py`, replace `payload: dict` on POST with a Pydantic create model carrying `name`, `description`, `examples`, `validation_rule`, `target_table`, `base_label_mapping`, `required_flag`, `value_kind`, `value_unit`, and `cardinality`. Verifies row 117.
- [x] 9.2 Replace `payload: dict` on PUT with an update model whose fields are all optional, including `cardinality`.
- [x] 9.3 Replace `payload: dict` on PATCH with a model requiring `is_active`, so an empty body returns 422 rather than raising `KeyError`. Verifies row 118.
- [x] 9.4 Confirm an invalid `cardinality` produces 422 with a message naming `single` and `multi`, not a 500 from the CHECK constraint. Verifies row 109.

## 10. Portal — types and hooks

- [x] 10.1 Add `cardinality: "single" | "multi"`, `value_kind: string`, and `sql_identifier: string | null` to `EntityType` in `src/portal/src/types/entity-types.ts`. Verifies row 135.
- [x] 10.2 Add `cardinality` and `value_kind` to `CreateEntityTypePayload` in `src/portal/src/hooks/use-create-entity-type.ts`. Do not add `sql_identifier`. Verifies rows 128, 132.
- [x] 10.3 Add `cardinality` and `value_kind` to `UpdateEntityTypePayload` in `src/portal/src/hooks/use-update-entity-type.ts`. Do not add `sql_identifier`. Verifies rows 129, 132.
- [x] 10.4 Update `src/portal/src/hooks/use-create-entity-type.test.tsx` for the widened payload.

## 11. Portal — entity type form

- [x] 11.1 Add a `cardinality` state to `DefineEntityTypeSlideOver.tsx`, defaulting to `"multi"` in create mode and seeded from `editTarget.cardinality` in the existing `useEffect`. Verifies rows 126, 127.
- [x] 11.2 Render a CARDINALITY two-option control between BASE MODEL LABEL and Required flag, labelled "Single value" and "Multiple values", each with a one-line explanation in query terms ("one value per document" / "many values per document"). Match the existing chip-row styling rather than introducing a new control pattern. Verifies rows 126, 127.
- [x] 11.3 Add a `value_kind` state defaulting to `"text"`, seeded from `editTarget.value_kind` in edit mode, rendered as a VALUE KIND select over the supported kinds. Verifies rows 130, 131.
- [x] 11.4 Include `cardinality` and `value_kind` in `buildPayload` for both create and edit. Verifies rows 128, 129, 131.
- [x] 11.5 Confirm `buildPayload` never emits `sql_identifier`. Verifies row 132.
- [x] 11.6 Change `buildPayload` to merge the chip selection into the persisted `base_label_mapping` rather than replacing it, so an entity type mapping more than one base label keeps every key across an edit. Verifies rows 142, 143.
- [x] 11.7 Write `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.cardinality.test.tsx` covering rows 126–132, 142, 143.
- [x] 11.8 Update `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.test.tsx` for the widened payload and the two new controls.

## 12. Portal — cardinality change confirmation

- [x] 12.1 In edit mode, compare the selected `cardinality` against `editTarget.cardinality` on submit. When they differ, show a confirmation dialog before calling the mutation. Verifies rows 136, 137.
- [x] 12.2 Word the dialog for the actual direction of the change, stating that already-extracted values remain in the previous representation and that documents must be re-extracted for the new one to be populated. Verifies rows 136, 137.
- [x] 12.3 On confirm, send the PUT and show the usual success toast. Verifies row 138.
- [x] 12.4 On cancel, send nothing and leave the slide-over open with the newly selected cardinality still shown. Verifies row 139.
- [x] 12.5 Do not prompt in create mode, nor on an edit that leaves cardinality unchanged. Verifies rows 140, 141.
- [x] 12.6 Cover rows 136–141 in the cardinality test file.

## 13. Document delete propagation

- [x] 13.1 In `src/document_service/api/v1/documents.py:290-309`, execute `build_relational_delete_statements` output after the `document_entities` delete, inside the same transaction, via the `AsyncSession` idiom. Verifies rows 89, 90.
- [x] 13.2 Confirm the endpoint imports the shared builder rather than reimplementing the statements. Verifies row 29.
- [x] 13.3 Confirm the delete tolerates a document with no `subject` row and no child rows. Verifies row 92.
- [x] 13.4 Write `tests/test_relational_document_delete.py` covering rows 89, 90, 91, 92.
- [x] 13.5 Run `tests/test_document_ingestion.py` against the baseline and confirm no new failures. Verifies rows 85–88.
- [x] 13.6 Run the portal entity-types test suite against the baseline and confirm no new failures beyond the files updated in tasks 10.4 and 11.8.
- [x] 13.7 Assign `sql_identifier` to the dev-database rows recorded in task 1.5, using the same `to_sql_identifier` rule and per-tenant `taken` set, so entity types created before this change become visible to the reconciler. Record what was changed; this is a dev-environment repair, not a migration.

## 14. Grants and query whitelist

- [x] 14.1 Add one shared resolver returning the generated table names for a schema from `entity_definitions`, excluding definitions whose `is_active` is false or whose `sql_identifier` is NULL. Verifies rows 66, 98, 99.
- [x] 14.2 Feed `build_role_statements` (`src/chat_api/services/sql_execution_role.py`) from that resolver instead of the static constant. Leave the existing `IF EXISTS (SELECT 1 FROM pg_tables …)` guard unchanged — `pg_tables` matches physical tables directly. Verifies rows 97, 101.
- [x] 14.3 Feed `validate_sql`'s table whitelist from the **same** resolver. Verifies rows 98, 99, 100.
- [x] 14.4 Confirm the role receives `SELECT` only on generated tables — no `INSERT`, `UPDATE`, or `DELETE` grant.
- [x] 14.5 Extend `tests/test_sql_execution_privileges.py` with rows 97, 98, 99, 100, 101 — including the set-equality assertion between grants and whitelist.
- [x] 14.6 Run the existing chat-api SQL validation tests against the baseline and confirm no new failures. Verifies rows 93–96.
- [x] 14.7 Confirm the SQL generator prompt is **not** migrated in this change — `src/chat_api/services/sql_generator.py`'s prompt and entity-profile grounding stay as they are.

## 15. Documentation and out-of-scope guards

- [x] 15.1 Add to `scripts/backfill_document_entities.py`'s docstring that it rebuilds EAV rows out of band and leaves the generated relational tables stale for affected documents, repaired only by re-extraction. Do not make it projection-aware.
- [x] 15.2 Confirm no new Alembic migration was added and migration `037` is unmodified.
- [x] 15.3 Confirm the `document_entities` schema is unchanged.
- [x] 15.4 Confirm `EntityTypeCard.tsx` was not modified — a cardinality badge on the card is deliberately out of scope.

## 16. End-to-end verification

- [x] 16.1 Run a batch extraction on the dev tenant against Docker Postgres on port 55432 and confirm the run completes with `failed_count` 0.
- [x] 16.2 For each processed document, assert `document_entities` and the generated tables agree: every routed entity appears in its child table, every `single` definition's chosen value matches the deterministic selection rule, and every processed document has a `subject` row.
- [x] 16.3 Re-run extraction under a bumped model version and confirm `document_entities` row counts are unchanged while `extracted_entities` grows. Verifies rows 25, 26, 83.
- [x] 16.4 Run the same verification on a **base-model** tenant (no promoted model, version 0) and confirm its generated tables are non-empty. This is the single highest-value check in the change — it is the assertion that catches name-equality routing. Verifies rows 7, ADR-008 compliance.
- [x] 16.5 Delete one extracted document via the API and confirm its rows are gone from every generated table and from `subject`. Verifies rows 89, 91.
- [x] 16.6 Through the portal, create a new entity type with cardinality "Single value" and a numeric value kind. Confirm the persisted row has a non-NULL `sql_identifier` and `cardinality = 'single'`, that `subject` gains a `DOUBLE PRECISION` column for it, and that re-opening the edit form shows the persisted cardinality and value kind rather than the defaults. Verifies rows 102, 106, 126–131.
- [x] 16.7 Through the portal, change an existing entity type's cardinality, confirm the dialog appears and describes the direction correctly, confirm it, and verify the previous representation still holds its rows. Verifies rows 115, 136–138.
- [x] 16.8 Run the full pytest suite and diff against the task 1.2 baseline. No test that passed on `main` may fail now.

## 17. Verification & Evidence

- [x] 17.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 17.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 17.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 17.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 17.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 17.6 Run `openspec validate entity-relational-projection --type change --strict` and confirm it exits clean before archive.
