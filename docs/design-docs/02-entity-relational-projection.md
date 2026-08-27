# Entity Relational Projection — Implementation Specification

**Status**: Approved for implementation pending review
**Date**: 2026-08-21
**Scope**: EAV + generated relational query surface, written from one in-memory entity state inside the existing extraction transaction.

---

## 1. Objective

Give the Text-to-SQL generator a normalized relational query surface without changing how
entities are extracted, normalized, or post-processed.

Extraction continues to produce a single final `list[NormalizedEntity]` in memory. That same
list is written to two places inside the **existing** per-document transaction: the EAV system
of record (`document_entities`, unchanged) and a set of **generated physical tables** derived
from `public.entity_definitions`.

Physical tables, not views. Not a materialized view. Not a derived projection job.

---

## 2. Architectural principles

1. **One write point per document.** The transaction at `worker.py:312` is the only place
   entity data is persisted. No second synchronization path is introduced.
2. **Post-processing stays in memory.** It runs before the transaction opens and never touches
   the database. Verified: `entity_postprocessor.py:408`.
3. **The relational layer consumes the in-memory list directly.** It never re-reads
   `document_entities`.
4. **Schema generation is separate from extraction.** DDL is emitted by the reconciler at
   entity-definition lifecycle points and once per run. The worker never emits DDL.
5. **`document_entities` remains the system of record.** The relational tables are a reduced
   query surface and are always reconstructible from it.
6. **Purity where possible.** DDL and DML generators are pure functions returning statement
   lists, matching the existing `build_role_statements` pattern.

---

## 3. Final data flow

```
model serving (BERT, fixed label space)
  └─ predictions[]
      ↓  worker.py:268  _align_predictions_with_offsets
      ↓  worker.py:269  merge_wordpieces
      ↓  worker.py:273  reconstruct_entities          → list[NormalizedEntity]   (in memory)
      ↓  worker.py:277  apply_semantic_normalization  → typed value fields       (in memory)
      ↓  worker.py:281  filter_valid_entities         → junk removed             (in memory)
      ↓  worker.py:285  collapse_duplicates           → occurrence_count set     (in memory)
      ↓  worker.py:296  postprocess_document          → outcome.entities         (in memory)
      ↓  worker.py:304  collapse_duplicates           → FINAL STATE              (in memory)
      │
      └─ worker.py:312  with engine.begin() as conn:      ◄── THE ONLY TRANSACTION
              1. delete_document_entities(...)             [NEW call, existing fn]
              2. delete_relational_entities(...)           [NEW]
              3. INSERT extracted_entities (per prediction) [unchanged, append-only]
              4. insert_document_entities(...)             [unchanged]
              5. project_document_entities(...)            [NEW]
             COMMIT
```

Steps 1–5 commit together or not at all.

---

## 4. The three persisted representations

### 4.1 `extracted_entities`

Raw per-run model output. Carries `run_id`, `entity_id` (the raw label), `value`, `confidence`,
`review_status='unreviewed'`. Append-only.

**Not purely audit.** It is the **extraction idempotency ledger**: `get_already_extracted`
(`entity_store.py:28`) joins it to `extraction_runs` on `model_version` to decide what to skip.
This coupling is load-bearing.

**Unchanged by this work. Never deleted per-document by the worker.**

### 4.2 `document_entities`

System of record for the final post-processed entity state and all provenance
(`source_entity_value`, `source_entity_type`, `postprocess_status`, `postprocess_model`,
`postprocess_prompt_version`, `postprocess_at`, `extraction_schema_version`, `occurrence_count`,
`confidence`, `page_number`, `char_start`, `char_end`, typed value columns).

Has **no** `run_id` and **no** `model_version` column. Identity is `(document_id, entity_type,
normalized_value)` by convention, not by constraint.

**Schema unchanged. Write path unchanged. Gains a delete-before-insert in the worker.**

### 4.3 Generated relational tables

Query surface only. Derived, reduced, always reconstructible. Two forms:

- **`subject`** — one row per extracted document; one column per active `cardinality='single'`
  definition.
- **`e_<slug>`** — one table per active `cardinality='multi'` definition; zero or more rows per
  document.

**They are not a source of truth.** Nothing outside the SQL generator reads them.

---

## 5. Entity definition → DDL rules

Source: `public.entity_definitions`, projected into `EntityDefinitionSpec`
(`src/shared/entity_views.py`), which already carries `name`, `sql_identifier`, `cardinality`,
`value_kind`, `is_active`, `base_label_mapping`.

### 5.1 Multi-valued (`cardinality='multi'`, `is_active=true`)

```sql
CREATE TABLE IF NOT EXISTS <schema>.<sql_identifier> (
    document_id       VARCHAR NOT NULL,
    value             TEXT    NOT NULL,
    normalized_value  TEXT    NOT NULL,
    value_number      DOUBLE PRECISION,
    value_number_high DOUBLE PRECISION,
    value_date        DATE,
    value_date_high   DATE,
    value_unit        TEXT,
    confidence        DOUBLE PRECISION NOT NULL,
    page_number       INTEGER,
    occurrence_count  INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (document_id, normalized_value)
);
CREATE INDEX IF NOT EXISTS idx_<sql_identifier>_normalized_value
    ON <schema>.<sql_identifier> (normalized_value);
```

Column list is **fixed**, never derived from `value_kind`. A fixed shape means adding a value
kind later never requires an `ALTER` on existing child tables.

`PRIMARY KEY (document_id, normalized_value)` matches `collapse_duplicates`'s dedup key
(`entity_type.upper()`, `normalized_value`) exactly, so the in-memory list is already unique on
it.

No foreign key to `documents`. Rationale: `documents` lives in the same schema, but a FK would
make the delete path in `documents.py` order-dependent and would add a lock the EAV table does
not take. Referential integrity is maintained by the delete propagation in §11.

### 5.2 Single-valued (`cardinality='single'`, `is_active=true`)

One table per tenant:

```sql
CREATE TABLE IF NOT EXISTS <schema>.subject (
    document_id VARCHAR PRIMARY KEY,
    filename    TEXT
);
```

Then one `ADD COLUMN` per active single definition, by `value_kind`:

| `value_kind` | Column type |
|---|---|
| `number`, `money`, `duration`, `boolean` | `DOUBLE PRECISION` |
| `date` | `DATE` |
| `text`, `NULL`, anything else | `TEXT` |

```sql
ALTER TABLE <schema>.subject ADD COLUMN IF NOT EXISTS <column> <type>;
```

Column name is `sql_identifier` with the `e_` prefix stripped, disambiguated against
`{document_id, filename}` and against already-taken columns using the existing `_unique_column`
rule.

`ADD COLUMN IF NOT EXISTS` with no default is metadata-only in PostgreSQL 11+. Physical tables
therefore avoid the `CREATE OR REPLACE VIEW` column-change problem entirely — this is a
**simplification** over the view design, not a new risk.

`filename` **is denormalized** onto `subject`. Resolved: it removes a join the LLM must
otherwise get right, and the extraction worker already knows the document. It is written on
every projection.

---

## 6. `entity_type` routing rules — CONFIRMED REQUIREMENT

`document_entities.entity_type` is **not** guaranteed to equal `entity_definitions.name`.

- **Fine-tuned tenants**: `entity_type` is whatever follows `B-`/`I-` in the model's BIO label,
  set at `entity_normalizer.py:248` from `_split_bio(pred["label"])`. Case is whatever the model
  emits. It corresponds to the definition name by convention, never by constraint.
- **Base-model tenants**: `entity_type` holds a CoNLL label (`PER`, `ORG`, `NUM`, …), bridged to
  the tenant's entity type through `entity_definitions.base_label_mapping`.

**Rule**: routing MUST use `entity_views._entity_type_literals(definition)`, which returns the
uppercased definition name plus every uppercased `base_label_mapping` key, sorted. Matching is
**case-insensitive** (`upper(entity_type) IN (...)`).

A direct `entity_type == name` match is forbidden — it silently produces empty tables for every
base-model tenant.

**Projection routing**: build one `dict[str, EntityDefinitionSpec]` keyed by every uppercased
literal from `_entity_type_literals`, then route each entity by
`literals_index.get(entity.entity_type.strip().upper())`.

**Collision rule**: if two active definitions claim the same literal, this is a catalog
misconfiguration. Route to the definition whose own `name` matches exactly; if neither does,
route to the first by `sql_identifier` sort order and log a warning. Never write the entity to
both tables.

**Unroutable entities** (no definition claims the literal): write to EAV, skip the relational
projection, log at debug. EAV tolerance for undefined types is deliberate and must be preserved.

---

## 7. Cardinality, selection, and value rules

### 7.1 Multi-valued

All entities routed to a multi definition are written, one row each. The in-memory list is
already unique on `(entity_type.upper(), normalized_value)` after `collapse_duplicates`, so no
further dedup is required. Use `ON CONFLICT (document_id, normalized_value) DO UPDATE` as a
safety net against a collision introduced by base-label routing (two source labels collapsing to
one definition), taking the higher-confidence row:

```sql
ON CONFLICT (document_id, normalized_value) DO UPDATE SET
    value = EXCLUDED.value,
    confidence = GREATEST(<table>.confidence, EXCLUDED.confidence),
    occurrence_count = <table>.occurrence_count + EXCLUDED.occurrence_count,
    ...
```

### 7.2 Single-valued selection

Exactly one value per document per single definition. Selection is applied **in memory**, not in
SQL, over the entities routed to that definition:

```
sort key: (-confidence, -occurrence_count, normalized_value)
take first
```

Deterministic tie-breaking is required, not optional: `collapse_duplicates` sets
`existing.confidence = min(existing.confidence, entity.confidence)`
(`entity_normalizer.py:345`), so confidence ties are common.

The discarded values remain in `document_entities`. This is the declared projection policy, not
data loss.

### 7.3 Column value written

| `value_kind` | Column receives |
|---|---|
| `number`, `money`, `duration`, `boolean` | `entity.value_number` |
| `date` | `entity.value_date` |
| `text` / `NULL` / other | `entity.entity_value` |

If a typed kind yields `NULL` (unparseable — `apply_semantic_normalization` counts these), the
column is `NULL`. Do **not** fall back to the surface text in a numeric column.

### 7.4 `normalized_value`

Never empty at persistence time. `is_valid_entity` (`entity_normalizer.py:291`) rejects any
entity whose stripped `normalized_value` is empty, and `filter_valid_entities` runs at
`worker.py:281` before the transaction. The `NOT NULL` on the child-table column is therefore an
assertion, not a filter.

### 7.5 Confidence and page number

Both propagate to child tables (`confidence NOT NULL`, `page_number` nullable). `confidence` is
also the primary single-value selection key. Neither is written to `subject` — the `subject` row
holds values, not per-value metadata; provenance queries join EAV.

### 7.6 Provenance fields — EAV only

`source_entity_value`, `source_entity_type`, `postprocess_status`, `postprocess_model`,
`postprocess_prompt_version`, `postprocess_at`, `extraction_schema_version`, `char_start`,
`char_end` are **not** projected. They live in `document_entities` and are joinable on
`(document_id, normalized_value)`.

Rationale: the relational tables are a query surface for a SQL-generating LLM. Provenance
columns widen the prompt's schema description without answering any user question.

### 7.7 Discarded and merged entities

Both resolved entirely in memory before persistence:

- **Discarded** — `outcome.discarded` entries never enter `outcome.entities`, so they reach
  neither store. Worker already logs the first three.
- **Merged** — `postprocess_document` merges candidates and the second `collapse_duplicates` at
  `worker.py:304` re-dedups. The projection sees only the merged result.

No projection-side handling required.

---

## 8. Post-processing lifecycle

**Unchanged. No file in the post-processing path is modified.**

Confirmed behaviors relied upon:

- `postprocess_document` **cannot** emit an entity type outside the configured set.
  `validate_decisions` (`entity_postprocessor.py:308`) discards any decision whose `entity_type`
  is not in `allowed_types`, where `allowed_types` is `{name.upper() for name in type_config}`
  (`worker.py:300`).
- When it changes a type it uppercases it (`entity_postprocessor.py:448`).
- It never writes to `document_entities` (`entity_postprocessor.py:408`).
- On failure it fails open: the run is marked degraded and the deterministic result is kept.

**Consequence for routing**: a post-processor type change can only ever produce an uppercased
definition **name**, never a base label. Name-keyed routing therefore always succeeds for
post-processed entities.

---

## 9. Transaction boundaries

One transaction per document — the existing `with engine.begin() as conn:` at `worker.py:312`.

Everything in §3 steps 1–5 is inside it. Nothing is added outside it.

Reconciliation runs in its **own** transaction, once per run, before the document loop. It is
never inside the per-document transaction: DDL there would take locks for the duration of the
document's writes and would couple schema state to document success.

---

## 10. Model-version re-extraction — CONFIRMED REQUIREMENT

Same-model-version re-extraction is prevented at `worker.py:205-208` via `get_already_extracted`.
**That is not a bug and requires no change.**

Because `get_already_extracted` is scoped by `model_version` (`entity_store.py:34`), a **new
model version makes every document eligible again**. This is the supported "add entity type →
retrain → re-run" workflow.

Today that path appends a second full set of rows to `document_entities` with no delete, and the
two generations are indistinguishable (no `run_id`, no `model_version`, no unique constraint).

**Strategy: full replace per document, inside the transaction.**

```python
delete_document_entities(conn, schema, doc_id)
delete_relational_entities(conn, schema, doc_id, specs)
```

- Fixes the existing EAV duplication as a side effect.
- Makes re-extraction idempotent for both stores.
- Makes manual re-runs safe.
- `extracted_entities` is **not** deleted — it is the idempotency ledger and per-run audit, and
  duplication there is meaningful.

`delete_relational_entities` deletes from every generated child table for that document and
deletes the `subject` row. It must delete from **all** existing generated tables, not only
currently-active ones, so a deactivated definition's stale rows are also removed.

---

## 11. Document deletion

`documents.py:290-309` deletes `document_chunks`, `document_text_spans`, `extracted_entities`,
`document_entities`, then sets `documents.status = 'deleted'`, in one transaction.

**Add relational propagation to that same transaction**, after the `document_entities` delete.
Without it, deleting a document orphans its relational rows and the SQL generator returns facts
about a deleted document.

This is an **async** session (`AsyncSession`), unlike the worker's sync `Connection`. The
projection module must expose a statement-building function usable from both, or a separate async
delete helper. Prefer: pure `build_relational_delete_statements(schema, document_id, specs)`
returning `list[tuple[str, dict]]`, executed by each caller in its own idiom.

---

## 12. Entity deactivation

`entity_definitions` has **no hard delete**. `soft_delete_entity_type` sets `is_active = false`
(`entity_service.py:137`) and `toggle_entity_type` flips it either way
(`entity_service.py:124`). **Reactivation is a supported, reversible operation.**

**Therefore: never drop a generated table or column on deactivation.** Dropping on a reversible
flag destroys data.

| Event | Table/column | Query surface | Writes |
|---|---|---|---|
| `is_active` → false | kept, untouched | excluded from whitelist and prompt | stop projecting |
| `is_active` → true | already exists | re-included | resume projecting |

`entity_views.py` currently **drops** views for inactive definitions. **This behavior must be
changed** when retargeting to tables.

Orphan handling changes accordingly: the reconciler no longer drops anything. A table whose
definition vanished from the catalog entirely is left in place and logged. Cleanup of genuinely
dead tables is a manual operator action, out of scope.

---

## 13. Schema reconciliation

**Invocation points** (all four `entity_definitions` write paths plus the run):

1. `EntityService.create_entity_type` — after insert, same transaction.
2. `EntityService.update_entity_type` — after update, same transaction (cardinality or
   value_kind may have changed).
3. `EntityService.toggle_entity_type` — after update, same transaction.
4. `EntityService.soft_delete_entity_type` — after update, same transaction.
5. `run_batch_extraction` — **once per run**, before the document loop, in its own transaction.

Point 5 is the safety net that makes the whole change deployable in one step: it guarantees the
tables exist before any projection runs, regardless of whether points 1–4 ever fired.

**Not per document.** DDL cannot change mid-run in a way that matters, and per-document
reconciliation would add a catalog round trip per document for no benefit.

`TenantService.create_tenant` clones `tenant_template` via
`SELECT tablename FROM pg_tables` + `CREATE TABLE ... (LIKE ...)`. Generated tables are **not**
in the template, so a new tenant starts with none. Point 5 covers this.

Reconciliation is idempotent and must remain so: `CREATE TABLE IF NOT EXISTS`,
`ADD COLUMN IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`.

---

## 14. Tenant isolation

Unchanged from the existing model (ADR-001). Every generated statement is schema-qualified with
`_schema(tenant_id)` → `tenant_<slug>`. The projection module never resolves a schema itself; the
caller passes the same `schema` string already used by `insert_document_entities`.

`entity_definitions` rows are filtered by `tenant_id` at load time, exactly as
`load_entity_type_config` already does.

---

## 15. SQL identifier safety

All identifiers come from `entity_definitions.sql_identifier`, assigned once by
`to_sql_identifier` and validated by `_checked_generated_identifier` against
`^e_[a-z0-9][a-z0-9_]*$` before entering any DDL or DML position.

Entity names are tenant-supplied free text and MUST NOT reach a statement directly. Entity type
**literals** (used in routing) are values, not identifiers, and go through `_quoted_literal`.

A definition with a `NULL` `sql_identifier` is skipped, never slugged at read time — a read-time
slug is not stable across processes.

---

## 16. Permissions and grants

`build_role_statements` (`sql_execution_role.py:47`) derives grants from `WHITELISTED_TABLES` and
guards each with `IF EXISTS (SELECT 1 FROM pg_tables ...)`.

Because the query surface is **physical tables**, `pg_tables` matches them directly — no change
to the guard is needed (it would have needed one for views).

**Required change**: the grant list must include generated tables, resolved per schema from
`entity_definitions` rather than from the static constant. `validate_sql`'s table whitelist must
resolve the same set. Both must be fed from one resolver so they cannot drift — the property
stated at `sql_execution_role.py:8` depends on it.

Inactive definitions' tables are excluded from both.

---

## 17. Failure, rollback, retry, concurrency

**Per-document failure**: unchanged. `try/except: continue` at `worker.py:333`. The transaction
rolls back; the document has zero rows in `extracted_entities`, `document_entities`, and every
relational table. `failed += 1`, run continues.

**Missing table or column at projection time**: **fail the document**. Do not skip silently.
Reconciliation at run start makes this unreachable in normal operation, so reaching it means the
catalog and schema genuinely disagree, and a visible `failed_count` is the correct signal.

**Partial batch**: already normal and correct. Each document is independently all-or-nothing.

**Retries**: `run_batch_extraction` declares `max_retries=0`. No automatic retry. Manual re-run
is the recovery path, and delete-before-insert makes it safe. No change.

**Concurrent runs over the same document**: `get_already_extracted` is read before the loop, so
two overlapping runs can both elect to process the same document. This race **pre-exists**. With
delete-before-insert plus a real primary key on child tables, the relational side becomes
last-writer-wins rather than accumulating duplicates — strictly better than today. Not otherwise
addressed here.

**Post-processing degradation**: fail-open, unchanged. A degraded run still projects; the rows
carry `postprocess_status` in EAV.

---

## 18. Empty results and zero-entity documents

**Zero entities extracted**: the document still gets a `subject` row with `document_id`,
`filename`, and all entity columns `NULL`.

Rationale: the SQL prompt instructs the model to join `subject` for candidate identity. A missing
row turns a `LEFT JOIN` into a silently truncated answer and makes "documents with no extracted
skills" unanswerable. A row of NULLs is a truthful statement that the document was processed and
nothing was found.

**Zero entities for one multi definition**: zero rows in that child table. Normal.

**Documents never extracted**: no `subject` row. Distinguishable from "extracted, found nothing"
— which is the correct distinction.

---

## 19. Existing readers and writers

**Readers of `document_entities`** — none change:

| Reader | Continues reading EAV |
|---|---|
| `chat_api/services/entity_resolver.py:159,179` | yes |
| `chat_api/services/sql_generator.py` (entity profile grounding) | yes for now |
| `document_service/api/v1/documents.py` (document detail) | yes |
| `shared/retrieval/eval/metrics.py` | comment only, no query |

No existing code assumes EAV is the only persisted representation. Migrating the SQL generator
onto the relational surface is a **separate, later change** and is out of scope here.

**Writers of `document_entities`** — three, all accounted for:

| Writer | Action |
|---|---|
| `worker.py:329` | gains delete-before-insert + projection |
| `documents.py:303` | gains relational delete propagation (§11) |
| `scripts/backfill_document_entities.py:92,93,124` | **out of scope** — operator script, see §21 |

---

## 20. Module and file changes

### Add

| Path | Contents |
|---|---|
| `src/extraction_service/services/relational_projection.py` | `build_projection_statements()` (pure), `build_relational_delete_statements()` (pure), `project_document_entities()`, `delete_relational_entities()`, `select_single_value()` |

### Modify

| Path | Change |
|---|---|
| `src/shared/entity_views.py` | Retarget view DDL → table DDL (§5). Remove drop-on-inactive (§12). Export `_entity_type_literals` as public. Keep identifier logic, `EntityDefinitionSpec`, `_unique_column`, `_ordered`, reconciler shape. |
| `src/extraction_service/services/semantic_normalizer.py` | Extend `load_entity_type_config` **or** add a sibling loader returning `list[EntityDefinitionSpec]` with `cardinality`, `sql_identifier`, `is_active`, `base_label_mapping`. Prefer a sibling — `load_entity_type_config`'s return type is consumed by `apply_semantic_normalization` and `postprocess_document`. |
| `src/extraction_service/worker.py` | Load specs once per run; reconcile once per run; add two deletes + one projection call inside the existing transaction. |
| `src/gateway/services/entity_service.py` | Reconcile after create / update / toggle / soft_delete. |
| `src/document_service/api/v1/documents.py` | Relational delete propagation in the existing delete transaction. |
| `src/chat_api/services/sql_execution_role.py` | Grants for generated tables from a shared resolver. |

### Do NOT change

- `src/extraction_service/services/entity_postprocessor.py`
- `src/extraction_service/services/entity_normalizer.py`
- `document_entity_store.insert_document_entities` (the call site changes, the function does not)
- The `extracted_entities` insert loop at `worker.py:313-328`
- `get_already_extracted` and the eligibility logic at `worker.py:205-208`
- The per-document `try/except: continue`
- `alembic/versions/037_entity_definitions_view_metadata.py`
- `document_entities` schema — no new migration

---

## 21. Migrations and data

**Migration `037` stands as written.** No new migration is required: generated tables are DDL
emitted by the reconciler, not Alembic migrations.

**No EAV → relational backfill.** Out of scope per the stated development-environment
constraint. Existing extracted documents will have empty relational tables until re-extracted
under a new model version, which is the normal workflow.

**`scripts/backfill_document_entities.py` is not updated.** It is an operator script that
rebuilds EAV rows out of band; after running it, relational tables are stale for the affected
documents. Document this limitation in the script's docstring. Making it projection-aware is a
follow-up, not part of this change.

---

## 22. Tests

### Add

| File | Covers |
|---|---|
| `tests/test_relational_projection_generator.py` | Pure generator: routing by name, routing by `base_label_mapping`, case-insensitive matching, single-value selection + tie-breaking, value-kind → column, multi dedup, unroutable entities, empty entity list, identifier injection |
| `tests/test_relational_projection_worker.py` | Integration: EAV and relational agree after a run; rollback leaves both empty; re-extraction under a new model version replaces rather than duplicates |
| `tests/test_relational_document_delete.py` | Document delete removes relational rows |
| `tests/test_entity_definition_reconcile.py` | Create/update/toggle/soft-delete each reconcile; deactivation keeps the table; reactivation restores the surface |

### Modify

| File | Change |
|---|---|
| `tests/test_entity_views_generator.py` | Retarget view assertions to table DDL; drop the drop-on-inactive assertions |
| `tests/test_entity_views_reconciler.py` | Same; add the no-drop assertion |
| `tests/test_migration_037_entity_view_metadata.py` | Unchanged unless imports move |

**Baseline note**: the suite is red on `main` (roughly 89 failed / 31 errors). Capture a baseline
before starting and diff against it. Docker Postgres is on host port **55432**.

---

## 23. Out of scope

- Migrating the SQL generator prompt onto the relational surface (separate change).
- Dynamic `WHITELISTED_TABLES` in `validate_sql` beyond what grants require.
- Historical EAV → relational seeding.
- Making `backfill_document_entities.py` projection-aware.
- Dropping genuinely dead generated tables.
- Materialized views or any refresh mechanism.
- Changes to the concurrent-run race.
- Any change to `extracted_entities`.

---

## 24. Implementation order

**One cohesive change.** See §25 for why. Ordered sub-steps:

1. **Apply migration `037`** to the dev database (already written, unapplied).
2. **`entity_views.py`** — retarget to table DDL; remove drop-on-inactive; make
   `entity_type_literals` public. Update its two existing test files.
3. **Definition loader** — sibling loader in `semantic_normalizer.py` returning
   `list[EntityDefinitionSpec]`.
4. **`relational_projection.py`** — pure generators first, with their unit tests, before any
   wiring. This is the piece everything else depends on.
5. **Worker wiring** — reconcile once per run; two deletes and one projection call inside the
   existing transaction.
6. **`entity_service`** — reconcile at all four write paths.
7. **`documents.py`** — delete propagation.
8. **Grants** — shared resolver feeding `build_role_statements`.
9. **Integration tests**.
10. **Verify** — run a batch extraction on the dev tenant; assert EAV and relational agree.

Steps 1–4 create no invalid intermediate state (nothing calls the new code). Step 5 is the point
at which behavior changes, and by then the reconciler guarantees the tables.

---

## 25. Why this is one change, not several

Assessed for genuine deployment-order dependencies:

**Does the application code require the tables to exist before it can safely start?** No. Nothing
reads the generated tables at startup. The SQL generator is not migrated in this change. The
worker creates what it needs at run start.

**Can the reconciler guarantee the tables before extraction?** Yes — §13 point 5 runs it once per
run, before the document loop, in its own transaction. This is the ordering guarantee, and it
lives inside the change rather than in a deployment sequence.

**Can DDL and application behavior land together without an invalid intermediate state?** Yes.
All DDL is `IF NOT EXISTS`. Code deployed before any table exists creates them on the first run.
Code deployed after they exist is a no-op reconcile. There is no window where the application
expects a table the reconciler has not had the opportunity to create.

**Any migration or deployment-order constraint?** Only the ordinary one: migration `037` must be
applied before code that reads `cardinality` / `sql_identifier`. That is standard
migrate-then-deploy, not a split of the implementation.

**Grants**: `build_role_statements` already guards every grant with `IF EXISTS`, so it is safe to
run before or after the tables exist.

**Conclusion**: no genuine dependency requires independently deployable steps. The change touches
six files and adds one, but the internal ordering in §24 fully handles it. Splitting would create
a half-wired state with no benefit.
