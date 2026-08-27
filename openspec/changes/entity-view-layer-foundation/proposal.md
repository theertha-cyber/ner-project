## Why

Extracted entities live in one EAV-shaped table per tenant schema (`tenant_<slug>.document_entities`), because tenant admins add entity types at runtime and storage must not migrate when they do. The Text-to-SQL LLM has to query that shape directly, so the generator prompt in `src/chat_api/services/sql_generator.py` carries a long tail of EAV workarounds — self-joins per entity type, `entity_type` literal validation, a whole defect class for querying the wrong type — and still produces wrong SQL often enough to need a retry loop.

The agreed direction is to keep EAV as the **write** model and add a generated per-tenant **view** layer as the **read** model, so the LLM eventually sees normalized-looking tables (`subject`, `e_skill`, `e_employer`). Adding an entity type then emits cheap view DDL instead of migrating storage. This change lays the two foundations that everything else depends on: the catalog metadata that says how an entity renders, and the pure-function DDL generator that renders it.

## What Changes

- Migration `037` adds two columns to `public.entity_definitions`:
  - `cardinality VARCHAR(16) NOT NULL DEFAULT 'multi'` — decides whether an entity becomes a column on the tenant's `subject` view (`single`) or its own child view (`multi`). `multi` is the safe backfill for every pre-existing row: a multi-valued entity rendered as a child view is always correct, whereas wrongly marking one `single` silently collapses values through the pivot's aggregate.
  - `sql_identifier VARCHAR(63)` — the Postgres identifier for that entity's view, assigned once at create and never changed, so renaming an entity's display name does not rename or drop its view.
- Backfill of `sql_identifier` for every existing row, derived from `name` by the same slug function the generator uses, with per-tenant collision resolution; plus a partial unique index on `(tenant_id, sql_identifier) WHERE sql_identifier IS NOT NULL` and a CHECK constraint restricting `cardinality` to `single`/`multi`.
- The `EntityDefinition` SQLAlchemy model at `src/gateway/models/__init__.py` gains both columns. `src/gateway/verify_schema.py` derives its expectations from the ORM models (`declared[table.name] = {c.name for c in table.columns}`), so it needs no edit — updating the model automatically extends the check.
- A new module `src/shared/entity_views.py`:
  - `to_sql_identifier(name, taken)` — deterministic, collision-free, `<=63` chars, always matching `^e_[a-z][a-z0-9_]*$`. Tenant-supplied free text never reaches DDL unslugged.
  - `build_entity_view_statements(schema, definitions)` — a pure function returning a `list[str]` of idempotent DDL statements, executing nothing, following the `build_role_statements()` contract in `src/chat_api/services/sql_execution_role.py`.
  - `build_drop_view_statements(...)` — `DROP VIEW IF EXISTS` for entities that went inactive or were deleted. Dropping a view never touches rows.
  - `reconcile_entity_views(session, schema, definitions)` — a thin async wrapper that executes what the pure function produced, mirroring `provision_role()`.
- Tests for both, the bulk of them requiring no database at all.

**Not in this change** (steps 3–6 of the rollout): wiring the reconciler into `entity_service` or `TenantService.create_tenant()`, making `WHITELISTED_TABLES` dynamic, granting the execution role `SELECT` on the views, and rewriting the SQL generator prompt. After this change the views are generatable and tested, but **nothing in the running system calls the generator**. `src/chat_api/services/sql_generator.py` and `src/chat_api/services/sql_execution_role.py` are not modified.

No new dependencies. No breaking changes: both new columns are additive and defaulted or nullable, and every existing reader of `entity_definitions` uses an explicit `SELECT` list.

## Capabilities

### New Capabilities

- `entity-view-layer`: Generation of the per-tenant SQL view layer over the EAV entity store — identifier slugging, child (`e_*`) view DDL, the `subject` pivot view DDL, drop statements, and the idempotent reconciler that applies them to a tenant schema.

### Modified Capabilities

- `entity-config`: The entity type definition gains `cardinality` and `sql_identifier`. `cardinality` is a tenant-settable property of a definition; `sql_identifier` is system-assigned and immutable. This changes the persisted shape of an entity type, which the existing "Entity Type Definition" requirement enumerates.

## Impact

**Code**

- `alembic/versions/037_entity_definitions_view_metadata.py` (new) — head moves `036` → `037`.
- `src/gateway/models/__init__.py` — `EntityDefinition` gains two columns.
- `src/shared/entity_views.py` (new) — chosen over a service-local module because both `gateway` (which owns entity CRUD and tenant provisioning) and `chat_api` (which will later need the identifiers for the whitelist and prompt) must import it, and `src/shared/` already holds exactly that kind of cross-service code (`config.py`, `database.py`, `tenant_context.py`).
- `tests/test_entity_views_generator.py`, `tests/test_entity_views_reconciler.py`, `tests/test_migration_037_entity_view_metadata.py` (new).

**Data**

- `public.entity_definitions` gains two columns and one partial unique index. Tenant schemas are untouched by the migration; only the reconciler creates views, and only when called — which nothing does yet in this change.

**Downstream, deliberately unaffected in this change**

- `src/chat_api/services/sql_generator.py` (`WHITELISTED_TABLES`, prompt, `entity_type` defect detection), `src/chat_api/services/sql_execution_role.py` (grant list), `src/gateway/services/entity_service.py` (does not yet assign `sql_identifier` — existing rows get one from the migration backfill, new rows get `NULL` until step 3).

**Known dependency for step 3**: `TenantService.create_tenant()` clones the template schema with `SELECT tablename FROM pg_tables WHERE schemaname = 'tenant_template'` + `CREATE TABLE ... (LIKE ...)`. `pg_tables` excludes views and `LIKE` has no view form, so a newly provisioned tenant gets **zero** entity views. The reconciler is the only thing that can fix that; the module docstring must record this so step 3 does not miss it.

## Open Questions

Both questions below were investigated and answered before writing this proposal; they are recorded because the answers are load-bearing and contradict the naive reading of the schema.

- **Does `document_entities.entity_type` equal `entity_definitions.name`?** Confirmed with two corrections. (1) The link is real: training labels are built from annotation tags (`src/training_service/worker.py:111-117`), and annotation span types come from `entity_definitions.name` (`src/annotation_service/api/v1/spans.py:290`). (2) **Matching is case-insensitive everywhere** — `load_entity_type_config` keys on `name.lower()` and looks up `entity.entity_type.lower()` (`src/extraction_service/services/semantic_normalizer.py:305-326`), while `worker.py:300`, `entity_postprocessor.py:308`, `entity_resolver.py:144` and `sql_generator.py:158` all uppercase before comparing. Nothing in the codebase assumes stored case equals definition case. (3) On the **base-model path** `entity_type` holds a CoNLL label (`PER`/`ORG`/`LOC`/`MISC`, `src/model_serving/services/inference_service.py:13`), not the tenant's name; `base_label_mapping` is what ties a definition to those labels (`entity_resolver.py:127`, `rag_orchestrator.py:202`). **Resolution (user-confirmed):** the generated predicate is `upper(entity_type) IN (<upper(name)>, <every key of base_label_mapping>)`, so views are correct on both the fine-tuned and base-model paths.
- **How is `subject` re-created when its column list changes?** `CREATE OR REPLACE VIEW` cannot add, rename, or reorder columns; adding a `single` definition changes `subject`'s column list and would fail with `cannot change name of view column` / `cannot drop columns from view`. **Resolution (user-confirmed):** the generator always emits `DROP VIEW IF EXISTS <schema>.subject CASCADE` followed by `CREATE VIEW`, inside the caller's transaction, so no reader observes a missing view. Child `e_*` views keep `CREATE OR REPLACE` because their column list is fixed by the generator and never varies with the definition set.

Remaining assumption, not blocking: `entity_definitions.name` is not currently constrained unique per tenant, so two definitions can slug to the same identifier. The migration backfill and the generator both resolve collisions deterministically against a `taken` set; the partial unique index makes any residual collision a loud failure rather than a silently overwritten view.
