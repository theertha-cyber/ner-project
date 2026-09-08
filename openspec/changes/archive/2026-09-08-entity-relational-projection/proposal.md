## Why

The `entity-view-layer-foundation` change gave us a catalog (`entity_definitions.cardinality`, `sql_identifier`) and a pure DDL generator, but it renders the query surface as **views over `document_entities`**. Views re-derive the pivot on every query, make `subject`'s column list a `DROP … CASCADE` problem every time a `single` definition is added, and make the drop-on-deactivation path destructive-looking against a flag (`is_active`) that `toggle_entity_type` flips **both ways**.

Physical tables remove all three problems at once: `ADD COLUMN IF NOT EXISTS` with no default is metadata-only in PostgreSQL 11+, `pg_tables` matches the generated relations directly so `build_role_statements`' `IF EXISTS` grant guard needs no change, and a deactivated definition's table can simply be left alone instead of dropped.

The remaining gap is that nothing writes them. Extraction already produces exactly one final `list[NormalizedEntity]` in memory at `worker.py:304`, and already opens exactly one transaction per document at `worker.py:312`. This change projects that same in-memory list into the generated tables **inside that existing transaction**, so the relational surface is either consistent with `document_entities` or absent — never partially written, never reconciled by a second job.

Doing so also fixes an existing correctness defect: a new model version makes every document eligible again (`get_already_extracted` is scoped by `model_version`, `entity_store.py:34`), and today that appends a **second full generation** of rows to `document_entities` with no delete and no way to tell the generations apart — `document_entities` has no `run_id`, no `model_version`, and no unique constraint.

## What Changes

- **New module `src/extraction_service/services/relational_projection.py`** — pure `build_projection_statements()` and `build_relational_delete_statements()` returning `list[tuple[str, dict]]`, plus thin `project_document_entities()` / `delete_relational_entities()` executors and `select_single_value()`. The pure/executor split mirrors `build_role_statements()` and is what lets the sync worker (`Connection`) and the async document-delete path (`AsyncSession`) share one statement builder.

- **`src/shared/entity_views.py` retargets from views to physical tables** (**BREAKING** for the not-yet-archived `entity-view-layer` capability):
  - `e_<slug>` child views become `CREATE TABLE IF NOT EXISTS` with a **fixed** column list (`document_id`, `value`, `normalized_value`, `value_number`, `value_number_high`, `value_date`, `value_date_high`, `value_unit`, `confidence`, `page_number`, `occurrence_count`), `PRIMARY KEY (document_id, normalized_value)`, plus an index on `normalized_value`. Fixed shape means a future `value_kind` never forces an `ALTER` on existing child tables.
  - The `subject` pivot view becomes `CREATE TABLE IF NOT EXISTS <schema>.subject (document_id VARCHAR PRIMARY KEY, filename TEXT)` plus one `ADD COLUMN IF NOT EXISTS` per active `single` definition, typed by `value_kind`. The `DROP VIEW … CASCADE` + `CREATE VIEW` dance is deleted outright.
  - `filename` is denormalized onto `subject` — it removes a join the LLM must otherwise get right, and the worker already has it.
  - **Deactivation no longer drops anything.** `is_active = false` means: keep the table, stop projecting, exclude from the whitelist and grants. Reactivation resumes projection against data that was never destroyed. Orphaned tables are logged, never dropped.
  - `_entity_type_literals` becomes public so the projection router and the DDL generator share one definition of "which `entity_type` values belong to this definition".

- **`src/extraction_service/worker.py`** — load `list[EntityDefinitionSpec]` once per run, reconcile the tenant schema once per run in its **own** transaction before the document loop, then inside the existing per-document transaction: `delete_document_entities`, `delete_relational_entities`, the unchanged `extracted_entities` insert loop, `insert_document_entities`, `project_document_entities`. All five commit together or not at all.

- **Full replace per document.** `document_entities` and every generated table are cleared for that `document_id` before insert. `extracted_entities` is **not** cleared — it is the extraction idempotency ledger that `get_already_extracted` joins against, and duplication there is meaningful per-run audit.

- **Routing is by entity-type literal, never by `name` equality.** `document_entities.entity_type` holds whatever follows `B-`/`I-` in the model's BIO label on fine-tuned tenants and a CoNLL label (`PER`, `ORG`, `NUM`, …) on base-model tenants. Routing builds a `dict` keyed by every uppercased literal from `entity_type_literals()` and looks up `entity.entity_type.strip().upper()`. A direct name match silently produces empty tables for every base-model tenant.

- **Zero-entity documents still get a `subject` row** — `document_id`, `filename`, every entity column `NULL`. A missing row would turn the prompt's `LEFT JOIN` into a silently truncated answer and make "documents where nothing was found" unanswerable. A document that was never extracted has no row at all, which is the distinction worth keeping.

- **Missing table or column at projection time fails the document** (`failed_count += 1`), rather than skipping silently. Run-start reconciliation makes this unreachable in normal operation, so reaching it means the catalog and the schema genuinely disagree.

- **`src/document_service/api/v1/documents.py`** — the existing delete transaction gains relational delete propagation after the `document_entities` delete, so a deleted document cannot keep answering questions.

- **`src/gateway/services/entity_service.py`** — reconcile after `create_entity_type`, `update_entity_type`, `toggle_entity_type`, and `soft_delete_entity_type`, each in its own existing transaction.

- **`sql_identifier` is assigned at create** (**previously missing — blocking**). `create_entity_type`'s `INSERT` column list names neither `sql_identifier` nor `cardinality`, so every entity type created since migration `037` carries a NULL identifier. Since a NULL-identifier definition is skipped by both the reconciler and the projection, such an entity type extracts correctly into `document_entities` while being **silently absent from the entire relational surface**. The foundation change deferred this explicitly ("new rows get `NULL` until step 3"); this is step 3.

- **`cardinality` becomes reachable end to end** (**previously missing**). It is currently settable by nothing: absent from the create `INSERT`, absent from `update_entity_type`'s `allowed_fields`, absent from both `SELECT` lists and `_row_to_dict`, absent from the API payload types, and absent from the portal. Every entity type is therefore `multi` forever, and the `subject`-column half of this architecture is unreachable through the product. This change adds it to the create insert, the update whitelist, every read path, the typed request schemas, and the entity-type form.

- **`value_kind` gains a UI control.** The backend already validates and returns it, but the portal never sends it, so every entity type is `text`. A `single` entity type's whole purpose is a typed `subject` column the LLM can compare and order — leaving it `text` makes `WHERE years_experience > 5` impossible. One select in the existing form closes it.

- **The entity-type form gains a cardinality control and a schema-change confirmation.** Two options — "Single value" / "Multiple values" — each with a one-line explanation in query terms, defaulting to "Multiple values". Changing cardinality on an **existing** entity type prompts for confirmation stating that already-extracted values stay in the previous representation and that re-extraction is required to populate the new one. No representation is migrated and nothing is dropped, consistent with the never-drop rule.

- **The edit form stops discarding base label mapping keys** (**pre-existing bug, now load-bearing**). `buildPayload` rebuilds the mapping as `{ [selectedChip]: [name] }` from a four-way single-select chip row, so an entity type mapping two base labels loses one on any save. Routing indexes on the full key set, so a dropped key silently empties part of a base-model tenant's query surface.

- **Entity-type endpoints get typed request schemas.** `src/gateway/api/v1/entity_types.py` currently takes `payload: dict` on POST, PUT, and PATCH with no Pydantic model, so an invalid `cardinality` would reach the `037` CHECK constraint and surface as a 500, and `PATCH` with an empty body raises `KeyError`. Both become 422.

- **`src/chat_api/services/sql_execution_role.py`** — the grant list resolves generated tables per schema from `entity_definitions`. `validate_sql`'s table whitelist resolves the **same** set from the **same** resolver so the two cannot drift.

- **No new migration.** Migration `037` stands as written; generated tables are reconciler DDL, not Alembic DDL. **No EAV → relational backfill** — existing documents have empty relational tables until re-extracted under a new model version, which is the normal workflow.

- **Not changed**: `entity_postprocessor.py`, `entity_normalizer.py`, `insert_document_entities` itself, the `extracted_entities` insert loop, `get_already_extracted` and the eligibility check, the per-document `try/except: continue`, and the `document_entities` schema.

## Capabilities

### New Capabilities

- `entity-relational-projection`: Writing the final in-memory entity list into the generated relational tables inside the existing per-document extraction transaction — entity-type routing via definition literals, single-value selection and tie-breaking, `value_kind` → column value, multi-value conflict resolution, full-replace-per-document semantics, delete propagation on document delete, and the failure/rollback contract.

### Modified Capabilities

- `entity-view-layer`: The generated query surface becomes **physical tables** rather than views — table DDL with a fixed child column list and a real primary key, `subject` as a table extended by `ADD COLUMN IF NOT EXISTS`, no drop on deactivation or orphaning, and a public entity-type-literal helper. This capability's spec currently lives in the unarchived `entity-view-layer-foundation` change; its requirements on view DDL, `CREATE OR REPLACE`, `DROP VIEW … CASCADE`, and drop-on-inactive are all replaced.
- `extraction-service`: Batch extraction reconciles the tenant's generated schema once per run before the document loop, and each document's transaction persists both the EAV record and the relational projection atomically. Re-extraction under a new model version replaces a document's entity rows instead of appending a second generation.
- `document-ingestion`: Document deletion propagates to the generated relational tables in the same transaction that clears `document_entities`.
- `chat-api`: The SQL execution role's grants and `validate_sql`'s table whitelist are both resolved from `entity_definitions` through one shared resolver, and exclude inactive definitions. The generator prompt itself is unchanged in this change.
- `entity-types-backend`: Creating an entity type assigns its `sql_identifier`; create and update accept and validate `cardinality`; every read path returns `cardinality` and `sql_identifier`; all four definition write paths reconcile the tenant's generated schema; request bodies are validated by typed schemas instead of an untyped `dict`.
- `entity-types-screen`: The define/edit slide-over gains a cardinality control and a value-kind select, submits both, preserves the full `base_label_mapping` across an edit, and confirms before changing the cardinality of an existing entity type.

## Impact

**Code — add**

- `src/extraction_service/services/relational_projection.py`

**Code — modify**

- `src/shared/entity_views.py` — view DDL → table DDL; remove drop-on-inactive; export `entity_type_literals`. Identifier logic, `EntityDefinitionSpec`, `_unique_column`, `_ordered`, and the reconciler shape are kept.
- `src/extraction_service/services/semantic_normalizer.py` — add a **sibling** loader returning `list[EntityDefinitionSpec]`. Not an extension of `load_entity_type_config`, whose return type is consumed by `apply_semantic_normalization` and `postprocess_document`.
- `src/extraction_service/worker.py` — per-run spec load + reconcile; two deletes and one projection call inside the existing transaction.
- `src/gateway/services/entity_service.py` — assign `sql_identifier` in the create `INSERT`; add `cardinality` to the create `INSERT`, to `update_entity_type`'s `allowed_fields`, to both `SELECT` lists and to `_row_to_dict` alongside `sql_identifier`; validate `cardinality`; reconcile at all four definition write paths.
- `src/gateway/api/v1/entity_types.py` — replace `payload: dict` with typed Pydantic request models on POST, PUT, and PATCH.
- `src/document_service/api/v1/documents.py` — relational delete propagation.
- `src/chat_api/services/sql_execution_role.py` — grants from the shared resolver.
- `src/portal/src/types/entity-types.ts` — `EntityType` gains `cardinality`, `value_kind`, `sql_identifier`.
- `src/portal/src/hooks/use-create-entity-type.ts`, `src/portal/src/hooks/use-update-entity-type.ts` — payload types gain `cardinality` and `value_kind`.
- `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.tsx` — cardinality control, value-kind select, mapping preservation, cardinality-change confirmation.

**Deliberately not changed in the portal**

- `EntityTypeCard.tsx` gets no cardinality badge. Showing it at a glance would be useful, but the admin can already see and change the value in the edit form, which is what the architecture requires. Adding it is a separate UI improvement.
- `scripts/setup_test_db.py:110` creates `public.entity_definitions` without `cardinality` or `sql_identifier`, so the test database diverges from the migrated shape. Bringing it in line is part of this change's task list because the new backend tests need it.

**Data**

- No migration. `document_entities`, `extracted_entities`, and `entity_definitions` schemas are all unchanged. Tenant schemas gain generated tables the first time the reconciler runs; `TenantService.create_tenant` clones `tenant_template` via `pg_tables` + `CREATE TABLE … (LIKE …)`, which will not carry generated tables, so run-start reconciliation is what covers a fresh tenant.
- **Behavioral data change**: re-extraction now deletes a document's `document_entities` rows before re-inserting. Values discarded by single-valued selection remain in `document_entities` — the relational table holds one, the EAV record holds all. That is the declared projection policy, not data loss.

**Downstream — deliberately unaffected**

- `chat_api/services/entity_resolver.py`, the SQL generator's entity-profile grounding, and `document_service`'s document-detail endpoint all keep reading `document_entities`. Migrating the SQL generator prompt onto the relational surface is a separate, later change.
- `scripts/backfill_document_entities.py` rebuilds EAV rows out of band and is **not** made projection-aware; after it runs, the relational tables are stale for the affected documents. This limitation gets recorded in the script's docstring.

**Tests**

- Add `tests/test_relational_projection_generator.py`, `tests/test_relational_projection_worker.py`, `tests/test_relational_document_delete.py`, `tests/test_entity_definition_reconcile.py`.
- Add `tests/test_entity_type_view_metadata_api.py` — `sql_identifier` assigned at create and stable across updates, per-tenant identifier collision, `cardinality` accepted on create and update, invalid `cardinality` returns 422 not 500, both fields present in every read path, a client-supplied `sql_identifier` ignored, `PATCH` without `is_active` returns 422.
- Add `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.cardinality.test.tsx` — create-mode default, edit-mode reflection of the persisted value, payload inclusion on both create and edit, value-kind default and reflection, `sql_identifier` never submitted, confirmation shown in both change directions, confirm sends / cancel sends nothing, no prompt on unchanged cardinality or in create mode, multi-key `base_label_mapping` preserved across an unrelated edit.
- Modify `tests/test_entity_views_generator.py` and `tests/test_entity_views_reconciler.py` — retarget view assertions to table DDL, delete the drop-on-inactive assertions, add a no-drop assertion.
- Modify `src/portal/src/components/entity-types/DefineEntityTypeSlideOver.test.tsx` and `src/portal/src/hooks/use-create-entity-type.test.tsx` for the widened payload shape.
- Modify `scripts/setup_test_db.py` — add `cardinality` and `sql_identifier` to the `entity_definitions` DDL so the test database matches the migrated shape.
- The suite is red on `main` (~89 failed / 31 errors). Capture a baseline first and diff against it. Docker Postgres is on host port **55432**.

## Open Questions

All of the following were investigated against the code before this proposal was written. They are recorded because the answers are load-bearing and each one contradicts the naive reading.

- **Does `document_entities.entity_type` equal `entity_definitions.name`?** No, and assuming it does is silently wrong for a whole tenant class. On the fine-tuned path `entity_type` is set at `entity_normalizer.py:248` from `_split_bio(pred["label"])` in whatever case the model emits; on the base-model path it is a CoNLL label bridged by `base_label_mapping`. **Resolved**: routing uses `entity_type_literals(definition)` with case-insensitive matching, and a direct name match is forbidden.
- **What happens when two active definitions claim the same literal?** A catalog misconfiguration rather than a data condition. **Resolved**: route to the definition whose own `name` matches exactly; if neither does, route to the first by `sql_identifier` sort order and log a warning. Never write the entity to both tables.
- **What about an entity whose type no definition claims?** **Resolved**: write it to EAV, skip the projection, log at debug. The EAV store's tolerance for undefined types is deliberate and must survive this change.
- **Is single-valued tie-breaking actually needed, or is confidence enough?** Needed. `collapse_duplicates` sets `existing.confidence = min(existing.confidence, entity.confidence)` (`entity_normalizer.py:345`), so ties are common rather than rare. **Resolved**: sort by `(-confidence, -occurrence_count, normalized_value)` and take the first, so the selection is deterministic across runs.
- **Is same-model-version re-extraction blocking a bug that should be fixed here?** No. The block at `worker.py:205-208` is correct and stays. The eligibility path that matters is a **new** model version, which is the supported "add entity type → retrain → re-run" workflow, and that is what full-replace makes idempotent.
- **Does `delete_relational_entities` need to know which definitions are active?** No — and scoping it to active ones would leave stale rows behind. **Resolved**: it deletes from every **existing** generated table for that document, not only currently-active ones.
- **Should cardinality be editable after creation, or immutable like `sql_identifier`?** **Resolved: editable, behind a confirmation.** Immutable is simpler and needs no dialog, but there is no hard delete for entity types — only `is_active = false` — so an admin who picks the wrong cardinality would be stuck with a permanently wrong query surface and no way out. The change is not destructive under the never-drop rule: the old relation keeps its rows, the new one starts empty, and re-extraction populates it. The risk is that it looks instantaneous while actually requiring a re-extraction, which is exactly what the confirmation dialog says out loud.
- **Should `value_kind` get a UI control in this change, given it is not `cardinality`?** **Resolved: yes, minimally.** It is one select in a form that is already being edited, and without it every `single` entity type lands in a `TEXT` column, which defeats the typed-column decision this architecture rests on. If the reviewer wants the scope narrower, this is the one item that can be cut without breaking the architecture — the cost is that typed `subject` columns stay unreachable until a follow-up.
- **Should this be split into independently deployable changes?** Assessed and rejected. Nothing reads the generated tables at startup, all DDL is `IF NOT EXISTS`, grants are already `IF EXISTS`-guarded, and run-start reconciliation is the ordering guarantee — so there is no window in which the code expects a table the reconciler has not had the chance to create. The only ordering constraint is the ordinary migrate-then-deploy of `037`. Splitting would produce a half-wired state with no benefit.

  Re-assessed after the configuration-path audit, with the same answer. The portal work depends on the API returning `cardinality` and `sql_identifier`, and the API work depends on nothing new — the columns have existed since `037`. A portal built against an API that does not yet return the fields would render an empty control, so backend precedes frontend **within** the change, which the implementation order already handles. Shipping the projection without the configuration path would be worse than either half alone: the reconciler and projection would be live while every entity type created through the UI carried a NULL `sql_identifier` and was silently skipped.
