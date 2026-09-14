## Context

`src/shared/entity_views.py` owns the generated relational surface: which relations exist, what
`subject`'s column layout is, and the DDL that maintains both. `subject_columns()` decides the
layout from the active `single` definitions and is the single source both the DDL generator and
the projection build from. `subject_column_type(value_kind)` decides each column's SQL type.

Reconciliation runs from five places, all of which go through one of two executors:
`EntityService._reconcile` after each of the four entity-definition write paths (in that
request's own transaction, before its `commit()`), and `run_batch_extraction` at run start (in
its own `engine.begin()`). Both executors delegate every decision to the pure
`_reconcile_plan(schema, definitions, existing)`.

`existing` is a `set[str]` of **table names**, read from `pg_tables`. Column types are not an
input to the plan, not an output, and not compared anywhere — no code path in the repository
reads `information_schema.columns` for a generated table. `build_subject_table_statements`
emits `ALTER TABLE … ADD COLUMN IF NOT EXISTS {col} {type}` per active `single` definition,
which is a no-op once the column exists at any type.

The catalog is free to move underneath that. `EntityService.update_entity_type` accepts
`value_kind` and its own comment records the choice: "Neither representation is migrated and
neither is dropped." That is correct for the `cardinality` case it was written about — where
two *relations* hold the two representations — and wrong for `value_kind`, where one column has
to be one type.

## Goals / Non-Goals

**Goals:**

- After any successful reconcile, every active `single` definition's `subject` column has
  exactly the type its `value_kind` declares.
- The invariant holds in both directions and for every supported kind, including kinds whose
  types PostgreSQL cannot cast between.
- Convergence can never fail on data, so it cannot brick an entity-definition edit or an
  extraction run.
- A catalog/schema divergence can never be resolved by silently skipping.
- Nothing in `document_entities` is touched, and no generated relation is dropped.

**Non-Goals:**

- Changing the accepted `value_kind` vocabulary. `duration` keeps its unit normalisation
  (`18 months` → `1.479` years), `money` and `boolean` keep working.
- Repopulating a blanked column. Re-extraction is the repopulation path, unchanged.
- Reporting the blanking through the entity-definition API.
- Column-type convergence for off-surface columns (left by a `single → multi` flip or a
  deactivation).
- Any change to the projection, the SQL generator, the EAV store, cardinality semantics, or
  tenant isolation.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Separate PostgreSQL schema per tenant | Introspection and DDL are per schema, from the schema the caller already resolved. No cross-schema read. |
| ADR-004-openspec-governance | Structured artifacts per change | This change carries proposal, design, delta spec, tasks, and verification. |
| ADR-007-chatbot-architecture | Structured SQL over extracted entities, validated and read-only | The query surface's declared types become true rather than aspirational, which is what makes a numeric comparison in generated SQL meaningful. No change to validation or execution. |

## Decisions

### Decision 1: Compare declared type against actual type, and converge in the reconciler

**Choice:** `_reconcile_plan` gains the schema's actual `subject` column types as an input.
Both executors read them from `information_schema.columns` and pass them through. A new pure
builder emits one `ALTER … TYPE` per column whose actual type differs from
`subject_column_type(definition.value_kind)`, appended after the existing create/add-column
statements.

**Rationale:** The reconciler is already the one place that decides what the physical schema
should look like, and it already runs at every moment the catalog can change — the four write
paths and the extraction run start. Putting the convergence anywhere else would add a second
place that maintains generated DDL. Keeping the comparison in the pure plan preserves the
property the module is built around: every decision is assertable without a database, which is
what the module docstring calls out as necessary because these failure modes are silent.

The statements are appended rather than interleaved because a column that does not exist yet is
created at the right type by `ADD COLUMN IF NOT EXISTS`, and there is nothing to converge; the
pre-DDL snapshot therefore stays valid for the whole statement list.

**Alternatives considered:**
- Validate at the API and reject the edit — rejected in Decision 4.
- A separate repair script — rejected: it leaves the invariant broken between runs, and the
  worker's reconcile would still be writing the wrong representation in the meantime.
- Drop and re-add the column — rejected: `DROP COLUMN` is destructive DDL this module has never
  emitted, and the module asserts that directly rather than trusting review.

### Decision 2: Always `USING NULL::<type>`, never a value-preserving cast

**Choice:** Every convergence emits
`ALTER TABLE <schema>.subject ALTER COLUMN <col> TYPE <declared> USING NULL::<declared>`.

**Rationale:** Two independent reasons, either sufficient.

*Correctness.* `document_entities` is the system of record and the `subject` column is a derived
projection. The stored value was computed by `value_for_column(entity, old_kind)`. Under the new
kind the correct value is `value_for_column(entity, new_kind)` — a different function of the
same source entity, not a function of the old column. `"5 years"` under `text` must become `5.0`
under `number`, which no cast of `"5 years"` produces; `5.0` under `number` must become
`"5 years"` under `text`, which no cast of `5.0` produces either. A cast that succeeds is
therefore still wrong, which is worse than one that fails.

*Availability.* Measured against PostgreSQL 16 on the development database, inside rolled-back
transactions:

| Transition | bare `ALTER … TYPE` | with `USING col::type` |
|---|---|---|
| `TEXT → DOUBLE PRECISION` | fails, `DatatypeMismatchError` | succeeds only if every value parses |
| `TEXT → DATE` | fails, `DatatypeMismatchError` | succeeds only if every value parses |
| `DOUBLE PRECISION → TEXT` | succeeds | — |
| `DATE → TEXT` | succeeds | — |
| `DOUBLE PRECISION → DATE` | fails | no cast exists |
| `DATE → DOUBLE PRECISION` | fails | no cast exists |
| any → any with `USING NULL::type` | — | **always succeeds** |

The `USING` requirement is a property of the type pair, not of the data: an empty table and an
all-NULL column both fail `TEXT → DOUBLE PRECISION` without it. And a value-preserving cast
aborts the whole statement on the first unparseable row — in the gateway that rolls back the
admin's edit, and in the worker it fails the entire extraction run, for data nobody chose.
`USING NULL` removes both failure modes and collapses six transitions into one code path.

**Alternatives considered:**
- Per-pair cast expressions with a pre-flight compatibility scan — rejected: it buys values that
  are semantically wrong, at the cost of a transition matrix, a data scan, and two new failure
  modes.
- Re-derive the column from `document_entities` in the same transaction — rejected here, and
  it is worth recording why it does not work as it first appears. The EAV store does not hold
  the new representation either: `apply_semantic_normalization` parses using the kind in force
  at extraction time, so a text-kind entity has `value_number = NULL`. Verified in the
  development database — of 57 entity rows, only the single `number`-kind row carries a parsed
  value. A refill would therefore have to re-run `normalize_value` per row inside a gateway
  request, and would become a second derivation path beside the projection.

### Decision 3: Blanking is the documented outcome, and it is logged

**Choice:** The converged column holds NULL until each document is re-extracted. Each
convergence emits a log line naming the schema, the column, both types, and the fact that
values were cleared.

**Rationale:** Blanking loses nothing that is not reconstructible: every value remains in
`document_entities` with its `entity_value`, `confidence`, and `occurrence_count`. What is lost
is a cache, and a cache holding values that mean something else is worse than an empty one — an
empty column reads as "not known", while `'7708888801.0'` reads as a phone number. The log line
exists because the alternative is an operator discovering the blank later and having nothing to
attribute it to.

**Alternatives considered:**
- Silent blanking — rejected: an unexplained empty column is indistinguishable from a bug.
- Blocking the edit until the tenant re-extracts — rejected: it inverts the order (you cannot
  re-extract into a column whose type is still wrong).

### Decision 4: `value_kind` stays editable

**Choice:** No new validation. The API keeps accepting a `value_kind` change on any definition.

**Rationale:** Making it immutable was considered and rejected on evidence. Reconciliation runs
on create, so a relational representation exists within milliseconds of the definition existing;
"immutable once a representation exists" is immutable in practice. That would have made the
`PHONE_NUMBER` correction impossible without direct database access — and that correction was
both necessary and right. Rejecting only "unsafe" transitions was also rejected: under
Decision 2 there is no unsafe transition left to reject, and no safe one either in the
value-preserving sense, so the check would have no content.

**Alternatives considered:**
- Immutable `value_kind` — rejected above.
- Reject transitions whose existing data will not cast — rejected: the data was never the thing
  that should carry over.

### Decision 5: Off-surface columns are left alone

**Choice:** Only columns owned by an *active* `single` definition are converged. A column left
behind by a `single → multi` flip, or by a deactivation, keeps whatever type it has.

**Rationale:** This is the same rule the module already applies to a retained child table, for
the same reason: the definition may come back, the rows are the only copy of that projection,
and nothing writes to or reads from the column while it is off-surface —
`subject_columns()` excludes it, so it is absent from the query surface and `validate_sql`
rejects a statement naming it. Converging it would blank a column nothing is asking about.

The consequence is that a definition flipped `single → multi → single` with a different
`value_kind` in between rejoins the surface with a stale column type — and is converged then,
by this same mechanism, at the reconcile that reactivates it. The invariant is stated over
on-surface columns, and it holds at every moment a column is on the surface.

**Alternatives considered:**
- Converge every generated column regardless of ownership — rejected: it blanks retained data
  for a definition nobody is querying, which is the failure mode the never-drop rule exists to
  prevent.

## Risks / Trade-offs

- [A `value_kind` edit silently empties a populated column] → Intended and documented; the log
  line and the proposal's open question 1 are the mitigations. `document_entities` keeps every
  value, and re-extraction restores the column.
- [`ALTER TABLE … TYPE` takes an `ACCESS EXCLUSIVE` lock and rewrites the table] → Bounded by
  the number of documents in one tenant's `subject`, one row per extracted document, and it
  only runs on the reconcile that follows an actual type change. A `USING NULL` rewrite is the
  cheapest form of it.
- [Introspection adds a query per reconcile] → One `information_schema.columns` read per
  reconcile, alongside the `pg_tables` read already there. Reconcile runs per
  entity-definition write and once per extraction run, not per document.
- [The type-name comparison is a string match against `information_schema`] → The mapping from
  the SQL types this module emits to their `information_schema` spelling is a single table with
  a totality test, so a new type cannot be added without a spelling for it.
- [A blanked column changes what the SQL generator's prompt samples show] → The grounding block
  reports the column with no sample values, which is truthful. The declared type is now correct,
  which it was not before.

## Migration Plan

1. Land the resolver-side change. It is behaviour-preserving for every tenant whose schema
   already agrees with its catalog — the plan emits no extra statements when nothing diverges.
2. On the first reconcile after deploy, any tenant that has diverged converges. The development
   database has no divergence left; the one instance found (`PHONE_NUMBER`) was corrected by
   hand before this change and is preserved as a regression test rather than a fix target.
3. No migration script, no backfill, no data movement.

**Rollback:** revert the change; the reconciler returns to `ADD COLUMN IF NOT EXISTS` only.
Columns already converged stay at their corrected type, which is the type the catalog declares,
so a rollback leaves the schema more correct than it found it.

## Open Questions

1. Whether the blanking should reach the API response, so the portal can warn the admin. Named
   in the proposal; deliberately out of this change's scope.
2. Whether an off-surface column should be logged the way an off-surface *table* already is.
   Cheap, and it would make Decision 5's consequence visible, but it widens the reconcile log
   for a state nothing queries.
