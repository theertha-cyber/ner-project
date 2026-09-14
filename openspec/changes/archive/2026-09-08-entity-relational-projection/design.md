## Context

Extraction today ends in one place. `worker.py` walks a document through `_align_predictions_with_offsets` → `merge_wordpieces` → `reconstruct_entities` → `apply_semantic_normalization` → `filter_valid_entities` → `collapse_duplicates` → `postprocess_document` → `collapse_duplicates`, and at line 304 holds a single final `list[NormalizedEntity]` in memory. At line 312 it opens one transaction, writes `extracted_entities` and `document_entities`, and commits.

Three representations exist or will exist, and they are not interchangeable:

| Store | Role | Identity | Lifecycle |
|---|---|---|---|
| `extracted_entities` | Per-run raw model output **and the extraction idempotency ledger** — `get_already_extracted` (`entity_store.py:28`) joins it to `extraction_runs` on `model_version` | `run_id` + `document_id` + `entity_id` | Append-only, never deleted per document |
| `document_entities` | System of record: post-processed values plus all provenance | `(document_id, entity_type, normalized_value)` **by convention only** — no `run_id`, no `model_version`, no unique constraint | Replaced per document by this change |
| Generated tables | Query surface for the SQL-generating LLM | Real primary keys | Derived; always reconstructible from EAV |

`entity-view-layer-foundation` shipped the catalog (`entity_definitions.cardinality`, `sql_identifier`, migration `037`) and `src/shared/entity_views.py`, which currently emits **view** DDL. Nothing calls it from the running system yet, which is what makes retargeting it cheap now and expensive later.

It shipped the *columns* but not the path to them. `entity_service.create_entity_type` inserts an explicit column list naming neither, `update_entity_type`'s `allowed_fields` excludes `cardinality`, both `SELECT` lists and `_row_to_dict` omit both, `entity_types.py` takes an untyped `payload: dict`, and the portal's `EntityType` type and entity-type form know about neither. Decision 11 covers what that implies and why it is inside this change.

Constraints that shape everything below:

- Tenant admins add entity types at runtime, so the relational shape is catalog-derived, not migration-derived.
- `document_entities.entity_type` is not the definition name. On fine-tuned tenants it is whatever follows `B-`/`I-` in the model's BIO label (`entity_normalizer.py:248`); on base-model tenants it is a CoNLL label bridged by `base_label_mapping`.
- `is_active` is a **reversible** flag — `toggle_entity_type` (`entity_service.py:124`) flips it either way, and `soft_delete_entity_type` (`entity_service.py:137`) only sets it false.
- Development environment. No production data to migrate, no backfill required.

## Goals / Non-Goals

**Goals:**

- Give the SQL generator a normalized relational surface that is always consistent with `document_entities`, written from the same in-memory list, in the same transaction.
- Make re-extraction under a new model version idempotent for both stores, fixing the existing silent duplication in `document_entities`.
- Keep extraction, normalization, and post-processing behaviour bit-for-bit unchanged.
- Keep DDL and DML generation pure and testable without a database.
- Preserve tenant isolation exactly as ADR-001 defines it.
- Make the catalog properties the architecture depends on — `cardinality`, `sql_identifier`, `value_kind` — actually reachable: assigned at create, editable where they should be, returned by the API, and configurable by a tenant admin who does not know the generated schema.

**Non-Goals:**

- Migrating the SQL generator prompt onto the relational surface. Separate change.
- Backfilling existing `document_entities` rows into relational tables.
- Making `scripts/backfill_document_entities.py` projection-aware.
- Dropping genuinely dead generated tables — a manual operator action.
- Materialized views, refresh jobs, or any second synchronization path.
- Fixing the pre-existing concurrent-run race in `get_already_extracted`.
- Any change to `extracted_entities`.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant data is isolated by separate Postgres schemas (`tenant_<slug>`) | Every generated statement is schema-qualified with the `schema` string the caller already passes to `insert_document_entities`. The projection module never resolves a schema itself. `entity_definitions` rows are filtered by `tenant_id` at load. |
| ADR-003-model-serving-topology | Per-tenant model serving with version pinning and rollback | A new model version is a normal, expected event that makes every document eligible again. Full-replace-per-document is what makes that safe. |
| ADR-004-openspec-governance | Spec-driven delivery; changes traceable through OpenSpec artifacts | This change's specs are the contract; `entity-view-layer`'s view requirements are replaced rather than silently contradicted. |
| ADR-007-chatbot-architecture | Full RAG with guardrails: whitelist-validated SQL, read-only execution, tenant-scoped, citations required | Grants and `validate_sql`'s whitelist must both cover the generated tables and must be fed from one resolver so they cannot drift. Inactive definitions are excluded from both. |
| ADR-008-base-model-as-default | Base model is version 0 and the default when no tenant model is promoted | Base-model tenants are the **common** case, not an edge case. Routing on `name` equality alone would produce empty tables for all of them. |

ADR-002 is partially superseded by ADR-008; ADR-006 is partially superseded by ADR-009 and ADR-010. None of the superseded clauses bear on this design. No ADR needs revisiting.

## Decisions

### Decision 1: Physical tables, not views

**Choice:** The generated query surface is `CREATE TABLE`, written by the worker, not `CREATE VIEW` over `document_entities`.

**Rationale:** Three separate problems collapse at once.

1. `CREATE OR REPLACE VIEW` cannot add, rename, or reorder columns, so every new `single` definition forced `DROP VIEW … CASCADE` + `CREATE VIEW` on `subject`. With a table, `ADD COLUMN IF NOT EXISTS` with no default is metadata-only in PostgreSQL 11+ — no rewrite, no cascade, no window where a reader sees a missing relation.
2. `build_role_statements` (`sql_execution_role.py:47`) guards each grant with `IF EXISTS (SELECT 1 FROM pg_tables …)`. `pg_tables` excludes views, so the view design needed that guard changed. Tables match it directly.
3. A table can carry `PRIMARY KEY (document_id, normalized_value)`, which gives the projection an `ON CONFLICT` target and makes concurrent writers last-writer-wins instead of duplicate-accumulating.

The cost is that the surface must be written rather than derived, which is exactly what §Decision 2 addresses.

**Alternatives considered:**
- **Views (the shipped foundation design)** — ruled out for the three reasons above. Also re-derives a `FILTER`-heavy pivot on every LLM query.
- **Materialized views with a refresh job** — ruled out: introduces a second synchronization path and a staleness window, which is the thing this design most wants to avoid.

### Decision 2: One write point, inside the existing transaction

**Choice:** The projection is written at `worker.py:312`, in the transaction that already exists, from the same in-memory `list[NormalizedEntity]` that `insert_document_entities` receives. It never re-reads `document_entities`.

**Rationale:** Consistency between EAV and relational becomes structural rather than eventual. Either both commit or neither does. A document that fails leaves zero rows in `extracted_entities`, `document_entities`, and every generated table, and the existing `try/except: continue` at `worker.py:333` keeps the run going.

Reading back from `document_entities` to build the projection would add a round trip, would couple the projection to the EAV write succeeding in a particular shape, and would tempt a future "just run the projection separately" refactor. Consuming the in-memory list forecloses that.

**Alternatives considered:**
- **A post-commit projection step** — ruled out: creates a window where EAV and relational disagree, and a crash in that window leaves no record that projection was owed.
- **A trigger on `document_entities`** — ruled out: hides the write from the code that reasons about the transaction, and per-row triggers make the single-valued selection (which is a whole-document decision) impossible to express.
- **A periodic reconciliation job** — ruled out as a second synchronization path with its own failure modes.

### Decision 3: Routing by entity-type literal set, never by name equality

**Choice:** Build one `dict[str, EntityDefinitionSpec]` keyed by every uppercased literal that `entity_type_literals(definition)` returns — the uppercased definition name plus every uppercased `base_label_mapping` key — and route each entity by `literals_index.get(entity.entity_type.strip().upper())`. The same helper feeds the DDL generator, so routing and schema can never disagree about which entity belongs where.

**Rationale:** Per ADR-008 the base model is the default, and on that path `entity_type` holds `PER`/`ORG`/`NUM`/… rather than the tenant's entity name. A `entity_type == name` comparison compiles, passes any test written with fine-tuned fixtures, and silently produces **empty tables for every base-model tenant** — the worst possible failure shape, because it looks like "no entities found."

Case-insensitivity is not defensive padding: the fine-tuned path takes the case straight from the model's label, and nothing in the codebase asserts stored case matches the definition.

Two consequences follow and are specified rather than left to chance:
- **Collision** (two active definitions claiming the same literal) is a catalog misconfiguration. Route to the definition whose own `name` matches exactly; failing that, the first by `sql_identifier` sort order, with a warning. Never write the entity to both tables — that would double-count in aggregates.
- **Unroutable** entities (no definition claims the literal) go to EAV only, skipped at debug level. The EAV store deliberately tolerates undefined types and that tolerance must survive.

Post-processing cannot break this: `validate_decisions` (`entity_postprocessor.py:308`) discards any decision whose type is outside `allowed_types`, and a type change is uppercased (`entity_postprocessor.py:448`), so a post-processed entity can only ever carry a definition **name**.

**Alternatives considered:**
- **`entity_type == name`** — ruled out; see above.
- **Case-insensitive name match without `base_label_mapping`** — ruled out: fixes the fine-tuned path only, still empty for base-model tenants.
- **Resolving base labels at query time in the view predicate** — this is what the view design did; it moves the same logic into SQL where it cannot be unit-tested and must be re-derived per query.

### Decision 4: Full replace per document; `extracted_entities` untouched

**Choice:** Inside the transaction, `delete_document_entities(...)` then `delete_relational_entities(...)` before the inserts. `extracted_entities` is never deleted by the worker.

**Rationale:** `get_already_extracted` is scoped by `model_version` (`entity_store.py:34`), so a new model version legitimately makes every document eligible again — that is the supported "add entity type → retrain → re-run" workflow. Today that path appends a second full generation of `document_entities` rows with no delete, and because the table has no `run_id`, no `model_version`, and no unique constraint, the two generations are **indistinguishable**. Delete-before-insert fixes that as a side effect of making projection idempotent, and makes manual re-runs safe.

`extracted_entities` is excluded deliberately: it is load-bearing as the idempotency ledger and as per-run audit, where duplication across runs is the point.

`delete_relational_entities` must clear **every existing** generated table for that document, not only the currently-active ones — otherwise deactivating a definition strands its rows where the surface can still be re-exposed on reactivation.

**Alternatives considered:**
- **Leave EAV append-only, replace relational only** — ruled out: the two stores then disagree after re-extraction, and EAV is the system of record, so the disagreement is unresolvable.
- **Add `model_version` to `document_entities` and keep generations** — ruled out: schema change, and every existing reader would need a generation filter it does not have today.
- **Block same-version re-extraction harder** — already the behaviour at `worker.py:205-208`, and it is not the problematic path.

### Decision 5: Never drop a table or column on deactivation

**Choice:** `is_active = false` keeps the table and its rows, stops projection, and removes the table from the whitelist, grants, and prompt. `is_active = true` resumes projection against data that was never destroyed. An orphaned table — one whose definition vanished from the catalog entirely — is logged and left in place.

**Rationale:** `entity_definitions` has no hard delete. `soft_delete_entity_type` sets a flag and `toggle_entity_type` flips it both ways, so deactivation is explicitly reversible. Destroying data on a reversible flag turns an "undo" button into a data-loss event. Because the surface is derived and reconstructible, keeping a stale table costs disk and nothing else, while dropping one costs the rows.

`entity_views.py` currently drops views for inactive definitions — cheap and correct when the object holds no rows, wrong the moment the object *is* the rows. That behaviour is removed as part of the retarget.

**Alternatives considered:**
- **Drop on deactivate (current view behaviour)** — ruled out: destructive on a reversible flag.
- **Drop after a grace period** — ruled out: adds a scheduler and a policy question for no benefit in a derived store.
- **Rename to `_deleted_<slug>`** — ruled out: churns identifiers, and the identifier is meant to be assigned once and never changed.

### Decision 6: Reconcile once per run and at definition write paths — never per document

**Choice:** DDL is emitted at five points: after each of `create_entity_type`, `update_entity_type`, `toggle_entity_type`, `soft_delete_entity_type` (each in that call's own existing transaction), and **once per run** in `run_batch_extraction`, before the document loop, in its own transaction. The worker never emits DDL inside the per-document transaction.

**Rationale:** Point 5 is the safety net that makes the change deployable in one step: the tables are guaranteed to exist before any projection runs, regardless of whether points 1–4 ever fired — which matters because `TenantService.create_tenant` clones `tenant_template` via `pg_tables` + `CREATE TABLE … (LIKE …)`, so a brand-new tenant starts with zero generated tables.

DDL inside the per-document transaction would hold schema locks for the duration of that document's writes and would couple schema state to a single document's success. Per-document reconciliation would also add a catalog round trip per document to detect a condition that cannot change mid-run.

All reconciliation DDL is idempotent (`CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`) and must stay that way.

**Alternatives considered:**
- **Reconcile per document** — ruled out: lock duration and per-document catalog round trip, no benefit.
- **Reconcile only at definition write paths** — ruled out: leaves a fresh tenant, or a tenant whose definitions predate this change, with no tables and a run that fails every document.
- **An Alembic migration that creates the tables** — ruled out: the table set is tenant-specific and catalog-derived, so it cannot be expressed as a static migration.

### Decision 7: Fixed child column list; `subject` typed by `value_kind`; `filename` denormalized

**Choice:** `e_<slug>` tables have a fixed column list regardless of `value_kind`. `subject` gets one column per active `single` definition, typed `DOUBLE PRECISION` for `number`/`money`/`duration`/`boolean`, `DATE` for `date`, `TEXT` otherwise, and carries a denormalized `filename`.

**Rationale:** A fixed child shape means introducing a new `value_kind` later never requires an `ALTER` on existing child tables — the columns are already there and simply stay `NULL`. On `subject`, a typed column is the whole point: the LLM must be able to write `WHERE years_experience > 5` without a cast.

If a typed kind yields `NULL` because the value was unparseable, the column stays `NULL`. Falling back to surface text in a numeric column is worse than absent data — it makes comparisons wrong rather than empty.

`filename` on `subject` removes a join the LLM must otherwise get right, and the worker already has it in hand. Provenance columns (`source_entity_value`, `source_entity_type`, `postprocess_*`, `extraction_schema_version`, `char_start`, `char_end`) are deliberately **not** projected: they widen the schema description in every prompt without answering any user question, and they remain joinable from EAV on `(document_id, normalized_value)`.

**Alternatives considered:**
- **Child columns derived from `value_kind`** — ruled out: turns a `value_kind` change into an `ALTER` on a populated table.
- **Projecting typed value *and* `<col>_text` on `subject`** (what the view design did) — ruled out here: doubles the column count the prompt must describe; the surface text is one EAV join away.
- **A `documents` FK on the child tables** — ruled out: makes the delete path in `documents.py` order-dependent and adds a lock the EAV table does not take. Integrity comes from delete propagation instead.

### Decision 8: Deterministic single-value selection, in memory

**Choice:** For each `single` definition, sort the routed entities by `(-confidence, -occurrence_count, normalized_value)` and take the first. Selection happens in Python, before the statements are built.

**Rationale:** `collapse_duplicates` sets `existing.confidence = min(existing.confidence, entity.confidence)` (`entity_normalizer.py:345`), so confidence ties are common, not rare. Without the second and third sort keys the chosen value would depend on list order and could change between runs over identical input — which makes the surface untrustworthy in exactly the way a query layer must not be.

Doing it in memory keeps it unit-testable without a database and keeps the emitted SQL a plain parameterized insert. The values not chosen remain in `document_entities`; that is the declared projection policy, and it is why the EAV store stays the system of record.

**Alternatives considered:**
- **`DISTINCT ON` / window function in SQL** — ruled out: untestable without a database, and pushes a policy decision into generated SQL.
- **Confidence alone** — ruled out: non-deterministic under the tie distribution the pipeline actually produces.

### Decision 9: Pure statement builders returning `list[tuple[str, dict]]`

**Choice:** `build_projection_statements()` and `build_relational_delete_statements()` are pure functions returning parameterized statements. `project_document_entities()` and `delete_relational_entities()` are thin executors.

**Rationale:** The worker holds a **sync** `Connection`; `documents.py` holds an **async** `AsyncSession`. A shared pure builder lets each caller execute in its own idiom without duplicating the statement logic — and duplicated statement logic between the write path and the delete path is precisely how a document ends up half-deleted. It also matches the established `build_role_statements` contract and makes the bulk of the test suite database-free.

Identifier safety rides on this too: every identifier comes from `entity_definitions.sql_identifier`, validated against `^e_[a-z0-9][a-z0-9_]*$` before entering any DDL or DML position; a definition with a `NULL` `sql_identifier` is **skipped, never slugged at read time**, because a read-time slug is not stable across processes. Entity type *literals* are values, not identifiers, and go through parameter binding.

**Alternatives considered:**
- **Two implementations, one sync and one async** — ruled out: guaranteed drift between the write and delete paths.
- **An ORM-model-based projection** — ruled out: the tables do not exist at import time and their shape is per-tenant.

### Decision 10: Missing table or column fails the document

**Choice:** If projection hits a missing relation or column, the document fails (`failed_count += 1`, transaction rolls back, run continues). It is not skipped silently.

**Rationale:** Run-start reconciliation makes this unreachable in normal operation, so reaching it means the catalog and the physical schema genuinely disagree. That is a condition an operator needs to see, and `failed_count` is the signal the run report already surfaces. A silent skip would produce a run that reports success while writing an incomplete query surface — the LLM would then answer confidently from missing data.

**Alternatives considered:**
- **Skip and log** — ruled out: silent wrong answers downstream.
- **Reconcile lazily on failure and retry the document** — ruled out: DDL inside the per-document transaction is exactly what Decision 6 rejects.

### Decision 11: Close the configuration path before the projection goes live

**Choice:** `create_entity_type` assigns `sql_identifier` at insert; `cardinality` becomes writable on create and update, readable on every read path, typed in the API schemas, and selectable in the entity-type form.

**Rationale:** An audit of the full path — form → payload → endpoint → service → column — found the architecture's central admin-configurable property reachable from nowhere:

| Layer | `cardinality` | `sql_identifier` |
|---|---|---|
| `DefineEntityTypeSlideOver.tsx` | absent | absent (correctly — system-assigned) |
| `use-create-entity-type.ts` / `use-update-entity-type.ts` payloads | absent | absent |
| `types/entity-types.ts` `EntityType` | absent | absent |
| `entity_types.py` | untyped `payload: dict`, no validation | — |
| `entity_service.create_entity_type` INSERT column list | **omitted** — server default `'multi'` always wins | **omitted** — always NULL |
| `entity_service.update_entity_type` `allowed_fields` | **omitted** — unchangeable | correctly omitted |
| both `SELECT` lists and `_row_to_dict` | **omitted** — never returned | **omitted** |
| `public.entity_definitions` | present since `037` | present since `037` |

Two consequences, both silent:

1. **Every entity type created since `037` has a NULL `sql_identifier`.** The projection skips NULL-identifier definitions by design (Decision 9 — a read-time slug is not stable across processes), so such an entity type extracts into `document_entities` normally and is absent from the entire relational surface with no error anywhere. Migration `037` backfilled only rows that already existed. The foundation change named this deferral explicitly; this change is where it comes due.
2. **`single` is unreachable.** Not settable at create, not settable at update, not even readable. Every entity type is `multi` forever, so the `subject`-column half of the architecture — Decisions 7 and 8, the typed columns, the deterministic selection — is dead code the moment it ships.

Neither is a projection bug. Both would make the projection correct and useless. Closing them is inside this change because shipping the write path without the configuration path produces exactly the failure mode this design is most concerned with: a query surface that looks healthy and answers from missing data.

`value_kind` is included on the same grounds but one step weaker: the backend already accepts and returns it, so only the form control is missing. Without it every `single` entity type lands in a `TEXT` column and Decision 7's typed comparison is unreachable through the product.

**Alternatives considered:**
- **Ship the projection now, fix configuration in a follow-up** — ruled out: every entity type created in the interval is permanently invisible to the relational layer until someone notices and backfills, and the symptom is an empty table rather than an error.
- **Slug `sql_identifier` lazily at read time when NULL** — ruled out by Decision 9: a read-time slug is not stable across processes, so two workers could disagree about a table's name.
- **Backfill `sql_identifier` for NULL rows in a migration and leave create alone** — ruled out: repairs the past, guarantees the same gap reopens with the next entity type created.

### Decision 12: Cardinality stays editable, behind a confirmation

**Choice:** `cardinality` is mutable after creation. Changing it on an existing entity type prompts the admin with what the change means, then updates the catalog and reconciles. No rows are migrated between representations and nothing is dropped.

**Rationale:** Immutable-after-create is simpler and needs no dialog, but entity types have no hard delete — `soft_delete_entity_type` only sets `is_active = false` — so an admin who chose wrong would be permanently stuck with a wrong query surface and no way to correct it.

Under Decision 5 the change is not destructive: `multi` → `single` leaves the child table and its rows in place and adds a `subject` column that starts NULL; `single` → `multi` leaves the column and adds an empty child table. The real hazard is that the operation *looks* instant while the new representation stays empty until the affected documents are re-extracted. That is a communication problem, not a data problem, which is why the mitigation is a dialog that says so rather than a migration.

Create mode does not prompt — there is nothing yet to be inconsistent with — and an edit that leaves cardinality unchanged does not prompt either.

**Alternatives considered:**
- **Immutable after create** — ruled out: no delete path means no recovery from a wrong choice.
- **Migrate rows between representations on change** — ruled out: it is a second write path into the relational store, which Decision 2 exists to prevent, and the data is reconstructible from EAV by re-extraction anyway.
- **Change it silently with no dialog** — ruled out: the admin would reasonably read a successful save as "the query surface now reflects this", and it does not until re-extraction.

## Risks / Trade-offs

- [**Routing regression reintroduces name-equality matching**, silently emptying every base-model tenant's tables] → Routing and DDL share one `entity_type_literals()` helper; unit tests cover base-label routing and case-insensitive matching explicitly, with a base-model fixture that would fail loudly.
- [**Full replace deletes EAV rows a caller did not expect to lose** — e.g. an operator re-runs extraction while inspecting `document_entities`] → The delete is scoped to one `document_id` inside the transaction that immediately re-inserts, so the row set is only ever momentarily absent and never absent on commit. `extracted_entities` retains the full per-run history.
- [**`scripts/backfill_document_entities.py` leaves relational tables stale**] → Explicitly out of scope; the limitation is recorded in the script's docstring. Re-extraction under a new model version repairs it.
- [**Single-valued selection discards values users can see in the document detail view**] → Discarded values remain in `document_entities`, which is what the document-detail endpoint reads. Only the SQL surface is reduced, and that reduction is the declared policy.
- [**Orphaned tables accumulate**, since nothing is ever dropped] → Accepted. Disk cost only; they are excluded from grants, whitelist, and prompt, so they are invisible to the LLM. Cleanup is a documented manual operator action.
- [**Concurrent runs over the same document**] → Pre-existing race, not introduced here. Real primary keys plus delete-before-insert make the relational side last-writer-wins rather than duplicate-accumulating — strictly better than today's behaviour.
- [**Grants and `validate_sql`'s whitelist drift apart**, exposing or hiding a table in one but not the other] → Both resolve from one shared resolver. The property is asserted in tests rather than left to review discipline.
- [**Retargeting `entity_views.py` breaks the two test files from the foundation change**] → Expected and planned: both files are updated in the same change, and the drop-on-inactive assertions are replaced with a no-drop assertion.
- [**Baseline suite is red** (~89 failed / 31 errors on `main`), so a regression can hide in the noise] → Capture and diff against a recorded baseline before starting; do not chase pre-existing failures.
- [**Entity types created between migration `037` and this change already carry a NULL `sql_identifier`** and will stay invisible to the relational layer even after the create path is fixed] → Verify the affected rows on the dev database during task 1.4 and assign identifiers to them as part of the end-to-end verification. In a development environment the set is small and enumerable; a production rollout would need a one-off backfill, which is called out rather than assumed away.
- [**An admin changes cardinality and reads the successful save as "the surface now reflects this"**, when the new representation stays empty until re-extraction] → The confirmation dialog states the re-extraction requirement in plain language before the request is sent; the old representation is never dropped, so nothing is lost while the admin works out what happened.
- [**The portal is built against an API that does not yet return `cardinality`**, rendering a control that silently resets to the default on every save] → Backend read paths land before the form in the implementation order, and a frontend test asserts the persisted value is reflected in edit mode rather than only that the control renders.
- [**`scripts/setup_test_db.py` creates `entity_definitions` without the two columns**, so backend tests pass against a schema the migration would never produce] → The DDL is brought in line in the same change, and the new API tests assert on both columns, which fails loudly against a stale test schema.

## Migration Plan

Ordered sub-steps within one cohesive change. Steps 1–4 create no invalid intermediate state because nothing calls the new code yet; step 5 is where behaviour changes, and by then the reconciler guarantees the tables.

1. **Apply migration `037`** to the dev database (already written, unapplied). Ordinary migrate-then-deploy — code that reads `cardinality` / `sql_identifier` must not run before it.
2. **`entity_views.py`** — retarget to table DDL, remove drop-on-inactive, make `entity_type_literals` public. Update `tests/test_entity_views_generator.py` and `tests/test_entity_views_reconciler.py`.
3. **Definition loader** — sibling loader in `semantic_normalizer.py` returning `list[EntityDefinitionSpec]`, leaving `load_entity_type_config`'s return type untouched.
4. **`relational_projection.py`** — pure generators first, with their unit tests, before any wiring. Everything else depends on this.
5. **Worker wiring** — reconcile once per run; two deletes and one projection call inside the existing transaction.
6. **`entity_service`** — assign `sql_identifier` at create; make `cardinality` writable and readable; validate it; reconcile at all four definition write paths.
7. **`entity_types.py`** — typed Pydantic request models replacing `payload: dict`.
8. **Portal** — types, payload interfaces, then the form control, value-kind select, mapping preservation, and confirmation dialog. After step 6, so the form is built against an API that already returns the fields.
9. **`documents.py`** — delete propagation.
10. **Grants** — shared resolver feeding `build_role_statements` and `validate_sql`.
11. **Integration and UI tests.**
12. **Verify** — run a batch extraction on the dev tenant and assert EAV and relational agree; separately create a `single` entity type through the UI and confirm it reaches `subject` as a typed column.

**Rollback:** Revert the code. The generated tables are derived and can be left in place — nothing outside the SQL generator reads them, and the SQL generator is not migrated in this change. `document_entities` and `extracted_entities` are unaffected by a revert, since neither's schema changes. Migration `037` need not be reversed, but `downgrade()` exists if it must be.

**Why not split into independently deployable changes:** Nothing reads the generated tables at startup. All DDL is `IF NOT EXISTS`, so code deployed before any table exists creates them on the first run and code deployed after is a no-op reconcile. Grants are already `IF EXISTS`-guarded and safe in either order. Run-start reconciliation is the ordering guarantee, and it lives inside the change rather than in a deployment runbook. Splitting would produce a half-wired state with no benefit.

## Open Questions

None blocking. Every question raised during design was investigated against the code and resolved; the resolutions are recorded in the proposal's Open Questions section and encoded as decisions above.

Deferred to follow-up changes, deliberately:

- Migrating the SQL generator's prompt and grounding onto the relational surface — the change that makes this one pay off.
- Whether `document_entities` should eventually gain a real unique constraint on `(document_id, entity_type, normalized_value)` now that the worker guarantees it by delete-before-insert. Not needed for this change; worth revisiting once no other writer appends.
- Making `backfill_document_entities.py` projection-aware.
- A cleanup path for genuinely dead generated tables.

No in-force ADR needs revisiting.
