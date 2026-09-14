## Context

Every tenant has its own Postgres schema (ADR-001). Inside it, `document_entities` is an EAV table: one row per extracted fact, keyed by `entity_type`, with the surface text in `entity_value` and typed values in `value_number` / `value_date` / `value_unit` (added by `029`) plus provenance columns (added by `035`). Tenant admins add entity types at runtime through `public.entity_definitions`, so this shape is not an accident — it is what lets a new entity type exist without a storage migration.

The cost lands on the read side. `src/chat_api/services/sql_generator.py` must teach an LLM the EAV shape: self-join `document_entities` to itself once per entity type, filter each join on `entity_type`, never assume a document has a row for a given type. The prompt carries a validation pass over `entity_type` literals (`_entity_type_defect`), a dedicated defect class for querying the wrong type, and a bounded retry loop. It works, but every additional entity type widens the surface the model has to reason about.

The agreed direction is to leave the write model alone and generate a **read model**: per-tenant SQL views that present the same rows as if they were normalized tables. `subject` gives one row per document with the single-valued facts pivoted into columns; `e_<entity>` gives one child table per multi-valued entity type. The LLM then writes ordinary joins.

The full rollout is six steps. **This change is steps 1 and 2**: the catalog metadata that says how each entity renders, and the pure-function DDL generator plus reconciler that renders it. Nothing calls the generator yet.

Constraints that shape the design:

- No new dependencies.
- `src/chat_api/services/sql_generator.py` and `src/chat_api/services/sql_execution_role.py` are off-limits in this change.
- `entity_definitions.name` is tenant-supplied free text and must never reach DDL unslugged.
- Dev Postgres is in Docker on host port **55432** (a native PostgreSQL 18 service occupies 5432 and returns a misleading auth failure).
- The pytest suite is already red on `main` (~89 failed / 31 errors). Work is measured against a captured baseline, not against green.

## Goals / Non-Goals

**Goals:**

- `public.entity_definitions` carries enough metadata (`cardinality`, `sql_identifier`) to render an entity type as SQL, with a backfill that is safe for every pre-existing row.
- A pure function turns a tenant schema name plus a list of definition specs into a list of idempotent DDL statements, assertable in tests with no database.
- Tenant-supplied names cannot produce invalid, colliding, or injectable identifiers.
- The generated `subject` view survives a change to its column list — the one failure mode most likely to reach production.
- A thin async reconciler applies the statements and tolerates every schema state that exists in the wild, including schemas from older templates.

**Non-Goals:**

- Wiring the reconciler into `entity_service` create/update/delete or into `TenantService.create_tenant()` (step 3).
- Making `WHITELISTED_TABLES` dynamic (step 4).
- Granting the SQL-execution role `SELECT` on the generated views (step 5).
- Rewriting the SQL generator prompt to target views (step 6).
- Backfilling `sql_identifier` for rows created *after* this migration — `entity_service` does not assign it yet, so new rows carry NULL until step 3. The partial unique index is written to tolerate that.
- Any change to how entities are extracted, normalized, or stored.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | One `tenant_<slug>` schema per tenant; isolation enforced at gateway, connection `search_path`, ORM, and object storage. `public` holds shared tables. | Views must be created **inside** the tenant schema and reference only objects in that same schema. No view may join across schemas. `sql_identifier` uniqueness is therefore per-tenant, not global — two tenants sharing `e_skill` is correct, not a collision. |
| ADR-004: OpenSpec Spec-Driven Development Governance | Changes are specified before implementation. | This artifact set is the specification; implementation follows `tasks.md`. |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | SQL generation over extracted entities, executed in read-only transactions behind a validation layer and a least-privilege role. | The view layer is a read surface for exactly that path. `WITH (security_barrier)` is set on every generated view so a future predicate pushdown cannot leak rows past a view's own filter. The role grant itself is step 5 — until then the views exist but the execution role cannot read them, which is the safe ordering. |
| ADR-009, ADR-010 | Training hyperparameters and dataset-readiness thresholds. | No interaction. |

Superseded and therefore not binding: ADR-002 (by ADR-008), the hyperparameter clause of ADR-006 (by ADR-009), and its dataset-threshold clauses (by ADR-010).

## Decisions

### Decision 1: Entity type matching is case-insensitive and includes base-model labels

**Choice:** Every generated predicate is `upper(e.entity_type) IN ('<UPPER(NAME)>', '<BASE_LABEL_1>', …)`, where the extra literals are the keys of that definition's `base_label_mapping`. Not `entity_type = 'SKILL'`.

**Rationale:** The task brief assumed `document_entities.entity_type` equals `entity_definitions.name`. Investigation says the link is real but weaker than that, in two ways.

*The link exists:* the trained label set is built from annotation tags (`src/training_service/worker.py:111-117` collects `labels.add(tag)` over the dataset), and annotation span types are seeded from `entity_definitions.name` (`src/annotation_service/api/v1/spans.py:290`). So for a tenant on its own fine-tuned model, `entity_type` is the definition name.

*But case is never assumed:* `load_entity_type_config` keys on `row.name.lower()` and looks up `entity.entity_type.lower()` (`src/extraction_service/services/semantic_normalizer.py:305-326`); `worker.py:300` passes `{name.upper() for name in type_config}`; `entity_postprocessor.py:308` compares `entity_type.strip().upper()`; `entity_resolver.py:144` adds `row[0].strip().upper()`; `sql_generator.py:158` builds `{t.upper() for t in entity_types}`. Not one comparison in the codebase is case-exact. An exact-match view would be correct only by coincidence.

*And there is a second label vocabulary:* on the base-model path the label list is `CONLL_LABELS = ["O", "B-PER", "I-PER", "B-ORG", …]` (`src/model_serving/services/inference_service.py:13`), so `entity_type` holds `PER`/`ORG`/`LOC`/`MISC` — not the tenant's name. `base_label_mapping` is the bridge, and both `entity_resolver.py:127` and `rag_orchestrator.py:202` already read it for exactly this reason. ADR-008 makes the base model the *default* inference model, so this is the common case for a new tenant, not an edge case. A name-only view would be empty for every tenant that has not trained yet.

**Alternatives considered:**

- *Exact equality on `name`* — ruled out: brittle on case, and silently empty on the base-model path, which is the default path.
- *Case-insensitive on `name` only, defer base labels to a later step* — ruled out: it makes the view layer look broken for exactly the tenants most likely to try it first, and the mapping data is already available at generation time at zero cost.
- *Normalize `entity_type` at write time instead* — ruled out: a data migration over every tenant's `document_entities` is a far larger and riskier change than an `upper()` in a view, and it would break the existing readers that expect the stored case.

**Cost:** `upper(entity_type)` is not sargable against a plain btree index on `entity_type`. There is no such index today, and view result sets are tenant- and document-scoped, so this is acceptable for now. If it becomes a problem, the fix is an expression index `ON document_entities (upper(entity_type))`, noted in Risks.

### Decision 2: `subject` is always DROP + CREATE; child views use CREATE OR REPLACE

**Choice:** The generator unconditionally emits `DROP VIEW IF EXISTS <schema>.subject CASCADE` immediately followed by `CREATE VIEW <schema>.subject …`. Child `e_*` views keep `CREATE OR REPLACE VIEW`.

**Rationale:** `CREATE OR REPLACE VIEW` in Postgres can only change a view's *body*; it cannot add a column in the middle, rename one, reorder them, or drop one. Adding a `single` entity definition changes `subject`'s column list, so a replace fails with `cannot change name of view column "x" to "y"` or `cannot drop columns from view`. That is not a rare path — it happens the first time an admin marks any entity `single`.

Drop-then-create is unconditionally correct and genuinely re-runnable. The window in which `subject` does not exist is inside the caller's transaction; Postgres DDL is transactional, so a concurrent reader either sees the old view or the new one, never a gap. `CASCADE` is required because a future dependent view (or a materialized view added later) would otherwise block the drop; today nothing depends on `subject`, so `CASCADE` is a no-op that stays correct as dependents appear.

Child views are treated differently on purpose: their column list is fixed by the generator and does not vary with the definition set, so `CREATE OR REPLACE` always succeeds and preserves the view's OID and any grants attached to it. That matters from step 5 onward, when the execution role holds `SELECT` on them — a drop would silently revoke it.

**Alternatives considered:**

- *Drop and recreate everything, uniformly* — ruled out: it churns OIDs on every reconcile and would drop the role grants that step 5 attaches to child views, turning a routine reconcile into a silent permission regression.
- *Try `CREATE OR REPLACE`, catch the error, fall back to drop* — ruled out: it forces the generator to execute SQL to know what to emit, destroying the pure-function contract that makes the whole module testable without a database.
- *`CREATE OR REPLACE` with a fixed wide column list (N placeholder columns)* — ruled out: arbitrary cap, meaningless column names, and it still breaks at N+1.

### Decision 3: `to_sql_identifier` is total — degenerate input yields `e_unnamed`, collisions get a numeric suffix

**Choice:** Slug to `^e_[a-z][a-z0-9_]*$`. On empty or fully-stripped input the base becomes `e_unnamed`. Truncate the base to 63 characters *before* any suffix; on collision against `taken`, cut the base back far enough to append `_2`, `_3`, … so the result still fits 63. Never raise.

**Rationale:** The function runs in two places that must not fail: the migration backfill (a raise aborts the migration for every tenant) and future entity creation (a raise turns a legal tenant name into a 500). A tenant can legitimately name an entity in a script with no Latin characters at all, which slugs to nothing — that must produce a usable view name, not an error. The `e_` prefix is doing three jobs at once: it guarantees the leading character is a letter (so `"2024 Revenue"` is fine), it makes every reserved word safe (`"select"` → `e_select`, no quoting needed anywhere), and it namespaces generated views away from real tables. Determinism matters because the migration backfill and the runtime generator must agree: if they disagree, the migration writes one identifier and the generator creates a view under another, orphaning it.

**Alternatives considered:**

- *Raise on degenerate input* — ruled out: makes the migration abortable on data that is already in the database and cannot be fixed before the migration runs.
- *Hash suffix instead of a counter* — ruled out: `e_skills_a3f9` is unreadable in an LLM prompt, and the whole point of this layer is that the names read naturally.
- *Quote identifiers instead of slugging* — ruled out: quoting makes injection depend on getting the escaping right everywhere forever. Slugging makes the character class the guarantee, which is checkable in one place and testable exhaustively.

### Decision 4: Module lives at `src/shared/entity_views.py`

**Choice:** `src/shared/entity_views.py`, not a service-local module.

**Rationale:** `gateway` owns entity CRUD (`entity_service.py`) and tenant provisioning (`tenant_service.py`), and will call the reconciler from both in step 3. `chat_api` needs the identifiers for the dynamic whitelist (step 4) and the prompt (step 6). `src/shared/` already holds precisely this kind of cross-service code — `config.py`, `database.py`, `tenant_context.py`, `retrieval/` — and nothing in it imports from a service package, so there is no circular-import risk.

`list_tenant_schemas()` is deliberately *not* imported from `src/chat_api/services/sql_execution_role.py`: that module imports `WHITELISTED_TABLES` from `sql_generator`, which would drag the whole chat stack into `gateway`, and it is off-limits for edits in this change. A four-line local helper is duplicated instead, with a comment naming the original so the duplication is visible rather than accidental.

**Alternatives considered:**

- *`src/gateway/services/entity_views.py`* — ruled out: `chat_api` importing from `gateway` inverts the dependency direction the repo uses today.
- *Import `list_tenant_schemas` from `sql_execution_role`* — ruled out: pulls `chat_api` into `gateway`'s import graph for a `SELECT nspname FROM pg_namespace`.

### Decision 5: A typed `single` entity projects two columns — typed and text

**Choice:** For a `single` definition whose `value_kind` is non-text, `subject` projects both `MAX(e.value_number) FILTER (…) AS years_experience` and `MAX(e.entity_value) FILTER (…) AS years_experience_text`. A text-kind definition projects one column.

**Rationale:** `value_number` / `value_date` are populated only when `apply_semantic_normalization` could parse the surface text; `semantic_normalizer.py:326-338` increments `unparseable` and leaves the typed fields NULL otherwise. Projecting only the typed column silently loses every unparseable row — the user asks "who has 5+ years" and a candidate whose résumé said "half a decade" vanishes with no signal. Projecting only the text column throws away the reason the typed columns exist: numeric comparison. Both columns cost nothing at generation time and let the LLM compare on the typed column while still being able to show or fall back to the text.

The `_text` suffix must itself be collision-checked against the rest of the projection, for the same reason the base name is.

**Alternatives considered:**

- *Typed column only* — ruled out: silent data loss on unparseable values, which are common enough that the worker logs a count of them.
- *Text column only* — ruled out: forces string comparison for numeric questions, which is the exact defect class the view layer exists to remove.
- *`COALESCE(value_number::text, entity_value)`* — ruled out: produces a text column that looks numeric, so `WHERE years_experience > 5` is a lexicographic comparison that silently returns wrong rows.

### Decision 6: `MAX()` as the single-value tie-break, `LEFT JOIN` from `documents`

**Choice:** Pivot with `MAX(<col>) FILTER (WHERE upper(e.entity_type) IN (…))`, joining `document_entities` to `documents` with `LEFT JOIN` and grouping by `d.id, d.filename`.

**Rationale for `LEFT JOIN`:** load-bearing, not incidental. An `INNER JOIN` would drop every document with zero extracted entities, so `SELECT count(*) FROM subject` would silently under-count the corpus and "documents with no email" would return nothing instead of everything. The `subject` view has to be a faithful one-row-per-document projection or it cannot be the thing the LLM counts.

**Rationale for `MAX()`:** an aggregate is required by the `GROUP BY`, and for a value declared `single` there is at most one non-NULL input per document, so `MAX` returns it. When the declaration is wrong — the admin marked a genuinely multi-valued type `single` — `MAX` returns the lexicographically greatest value and the others are invisible with no error. That is the known failure mode, and it is exactly why the migration backfills `cardinality` to `multi` rather than guessing: an entity wrongly rendered as a child view is merely inconvenient, an entity wrongly rendered as a `single` column is silently wrong. The remedy when it happens is to flip the definition to `multi` and reconcile; the underlying rows were never touched.

**Alternatives considered:**

- *`min()`* — no better, and less conventional.
- *`string_agg(DISTINCT …)`* — ruled out: turns a `single` column into a delimited list, which defeats typed comparison and makes the wrongly-declared case produce garbage rather than a defensible single value.
- *`array_agg`* — ruled out: an array column is exactly the EAV awkwardness this layer removes.

### Decision 7: Collision handling for pivot column names

**Choice:** The pivot column is `sql_identifier` minus the `e_` prefix. That candidate is checked against a reserved projection set — `{document_id, filename}` plus every name already projected, plus every `_text` variant — and on collision gets the same deterministic numeric suffix `to_sql_identifier` uses.

**Rationale:** an entity legitimately named "Document ID" or "Filename" slugs to `e_document_id` / `e_filename`, whose stripped form duplicates the identity columns. Postgres allows duplicate output column names in a view definition but the view then cannot be usefully queried by name, and `CREATE OR REPLACE` comparisons become ambiguous. Resolving it at generation time is cheap and keeps the failure impossible rather than merely unlikely.

### Decision 8: Migration `037` does not touch tenant schemas

**Choice:** `037` alters only `public.entity_definitions` — add two columns, backfill `sql_identifier`, add the CHECK and the partial unique index. No `tenant_%` loop.

**Rationale:** `entity_definitions` is a shared `public` table, so the `DO $$ … FOR schema_name IN SELECT nspname FROM pg_namespace WHERE nspname LIKE 'tenant\_%'` pattern from `026`/`029`/`035` does not apply. Deliberately, the migration also does **not** create any views: view creation is the reconciler's job, and nothing calls the reconciler in this change. That keeps `037` fast, reversible, and free of any dependency on tenant schema state.

The backfill runs in Python inside `upgrade()` rather than in SQL, ordering rows by `(tenant_id, created_at, id)` and feeding a per-tenant `taken` set through the same `to_sql_identifier` the generator uses. A pure-SQL `regexp_replace` backfill would be a second implementation of the slug rule that could drift from the first — the exact failure that orphans views.

**CHECK constraint:** added, as `ck_entity_definitions_cardinality CHECK (cardinality IN ('single','multi'))`. The alternative — a Postgres ENUM — is rejected because adding a value to an ENUM is a migration, and the repo already uses `VARCHAR` + CHECK for the same shape (`036`'s `processing_mode`).

### Decision 9: `verify_schema.py` needs no edit

**Choice:** Update only the ORM model.

**Rationale:** `src/gateway/verify_schema.py:40` builds its expectations reflectively — `declared[table.name] = {c.name for c in table.columns}` — and compares against `information_schema.columns`, reporting `declared_columns - existing_columns`. Adding the columns to `EntityDefinition` automatically extends the check. There is no hardcoded column list to keep in sync. This contradicts the task brief's assumption that `verify_schema.py` might declare columns; verified by reading the file.

## Risks / Trade-offs

- [A wrongly-declared `single` entity silently collapses values through `MAX()`] → Backfill defaults every pre-existing row to `multi`, which is never silently wrong. `cardinality` is only ever narrowed by an explicit admin action. Documented in the module docstring as the one failure mode that produces wrong answers rather than errors.
- [`upper(entity_type)` cannot use a plain btree index on `entity_type`] → Accepted for now; result sets are tenant- and document-scoped. If profiling shows it, add `CREATE INDEX … ON <schema>.document_entities (upper(entity_type))` in a later migration. Recorded here so it is a known lever, not a surprise.
- [`DROP VIEW … CASCADE` on `subject` would drop dependent objects] → Nothing depends on `subject` today. The reconciler runs inside the caller's transaction, so a failed create rolls the drop back. Step 5 must attach grants to `subject` *after* the create, not once at provisioning — noted in the module docstring.
- [Newly provisioned tenants get zero views] → `TenantService.create_tenant()` clones the template with `SELECT tablename FROM pg_tables` + `CREATE TABLE … (LIKE …)`; `pg_tables` excludes views and `LIKE` has no view form. Nothing in this change fixes it and nothing needs to, because nothing reads the views yet. The module docstring records it as a hard prerequisite for step 3 so it cannot be missed.
- [The migration backfill and the runtime generator drift apart] → Both call the same `to_sql_identifier`; the migration imports it rather than reimplementing it. A test asserts the migration's backfilled values equal what the generator would produce for the same inputs.
- [`sql_identifier` is NULL for rows created between this change and step 3] → The unique index is partial (`WHERE sql_identifier IS NOT NULL`) so NULLs are legal, and the generator skips definitions with no identifier rather than inventing one at read time (which would be non-deterministic across processes). Step 3 assigns it at create; a follow-up backfill is unnecessary because the same slug function will be used.
- [Two definitions in one tenant slug to the same identifier] → `entity_definitions.name` has no per-tenant unique constraint, so this is possible. The backfill and the generator both resolve it deterministically via `taken`; the partial unique index turns any residual case into a loud constraint violation instead of one view silently overwriting another.
- [Testing against a red suite hides a regression] → Capture a baseline `pytest` run before any edit and diff against it, per the repo's known state (~89 failed / 31 errors on `main`).

## Migration Plan

1. Capture the pytest baseline on unmodified `main` and save the summary line and the failing-test list.
2. Apply `037` against the dev database (Docker Postgres on host port **55432**). Verify: both columns exist, every pre-existing row has a non-NULL `sql_identifier` matching `^e_[a-z][a-z0-9_]*$`, every row's `cardinality` is `multi`, the CHECK and the partial unique index exist.
3. Run `downgrade()` and confirm both columns and the index are gone and `entity_definitions` is byte-identical in shape to its `036` state. Re-apply.
4. Land the generator module and its tests. The bulk of the suite needs no database.
5. Run the integration tests against a real tenant schema — create views, query them, mark a definition `single`, reconcile, assert `subject` gained the column and the old view was replaced cleanly.
6. Re-run the full suite and diff against the step-1 baseline. The only acceptable delta is new passing tests.

**Rollback:** `alembic downgrade 036` drops both columns and the index. No tenant schema was modified and no view was created by the migration, so there is nothing else to undo. If views were created manually during verification, `DROP VIEW IF EXISTS` on them touches no rows. The change is not wired into any request path, so a rollback has no user-visible effect.

## Open Questions

- **Should `entity_definitions.name` become unique per tenant?** It is not today, which is the only reason collision resolution is needed at all. Making it unique would simplify the backfill and remove a class of confusing admin state, but it is a behavioural change to entity CRUD and belongs to a different capability. Not blocking: collisions are handled deterministically and the partial unique index is the backstop.
- **Does the view layer need a `documents.status` filter?** `subject` currently projects every row in `documents`, including documents still processing or failed. The LLM would count them as subjects with all-NULL entity columns. Deferring: the correct predicate depends on the prompt rewrite in step 6, and adding it later is a view change, not a migration.
- **No in-force ADR needs revisiting.** ADR-001 and ADR-007 both hold as written; the view layer sits inside the tenant schema and inside the existing SQL-generation guardrail chain rather than around them. If step 4 or step 6 changes the guardrail model itself, that is where a superseding ADR would belong.
