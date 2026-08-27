## Why

`entity_definitions.value_kind` decides the SQL type of the `subject` column a `single` entity
definition owns, but the reconciler only ever emits `ADD COLUMN IF NOT EXISTS`, which does
nothing when the column already exists. A `value_kind` edit therefore changes the catalog and
leaves the physical column at its original type, and every consumer downstream trusts the
catalog: the projection writes the representation the new kind implies, and the query-surface
resolver declares the new type to the SQL generator.

The failure is silent and data-dependent. A live instance was found in the development
database: `PHONE_NUMBER` carried `value_kind = number` while `subject.phone_number` was
physically `TEXT`, so the projection wrote `value_number` into a text column and stored
`'7708888801.0'` where the extracted value was `'7708888801'`. The reverse direction — a text
value written into a `DOUBLE PRECISION` column — succeeds for `'5'` and raises
`invalid input syntax` for `'unknown'`, failing some documents of a run and not others.

## What Changes

- The reconciler learns the *actual* column types of `subject` and converges any column whose
  physical type disagrees with the type its definition's `value_kind` declares.
- Convergence is a single statement shape for every transition —
  `ALTER TABLE … ALTER COLUMN … TYPE <declared> USING NULL::<declared>` — which always succeeds
  and never depends on what the column holds.
- The converged column is **blanked**, deliberately: the stored value is a projection computed
  under the old kind, and the correct value under the new kind is a different projection of the
  same source entity, not a cast of the old one. `document_entities` remains the system of
  record and loses nothing; the column repopulates on the next extraction of each document.
- The convergence is logged per column, naming both types, so a blanked column is visible
  rather than discovered later.
- No change to the accepted `value_kind` vocabulary. `duration`, `money`, and `boolean` keep
  working exactly as they do today.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `entity-view-layer`: reconciliation gains an invariant it does not currently state or hold —
  after a successful reconcile, every generated `subject` column's physical type equals the
  type its definition's `value_kind` declares.

## Impact

- `src/shared/entity_views.py` — `_reconcile_plan` and both executors; one new pure builder and
  one new introspection query.
- `tests/test_entity_views_generator.py`, `tests/test_entity_views_reconciler.py`,
  `tests/test_entity_definition_reconcile.py`.
- No change to `relational_projection.py`, the extraction worker, the SQL generator, the EAV
  schema, the entity-definition API contract, cardinality semantics, or any migration.
- Every caller of `reconcile_entity_tables` / `reconcile_entity_tables_sync` benefits without
  changing: the four entity-definition write paths in `EntityService` and the extraction
  worker's run-start reconcile.

## Open Questions

1. Should a blanked column be reported in the entity-definition API response, so the portal can
   tell an admin their column is empty until re-extraction? Out of scope here — it is a
   contract change — but it is the natural follow-up.
2. Re-extraction is the only repopulation path, and `get_already_extracted` is scoped by
   `model_version`, so repopulating requires promoting a version. Same constraint the
   relational surface already documents; not introduced by this change.
3. A column left behind by a `single → multi` flip keeps its old type and is not covered by the
   invariant, because no active `single` definition claims it. It is off-surface for the same
   reason a retained child table is. Left alone deliberately; see design.md.
