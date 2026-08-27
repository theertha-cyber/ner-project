## 1. Type comparison in the pure layer

- [x] 1.1 Add `_INFORMATION_SCHEMA_TYPE`, mapping each SQL type `subject_column_type` can return (`TEXT`, `DOUBLE PRECISION`, `DATE`) to its `information_schema.columns.data_type` spelling. Placed beside `_COLUMN_TYPE_BY_TYPED_FIELD` so a type added there cannot be added without a spelling here.
- [x] 1.2 Add `build_subject_column_type_statements(schema, definitions, actual_types)` — one `ALTER TABLE … ALTER COLUMN … TYPE <declared> USING NULL::<declared>` per active `single` definition whose column exists with a different type. No statement for a column that matches, one that does not exist, or one no active `single` definition owns (design Decision 5).
- [x] 1.3 Tests in `tests/test_entity_views_generator.py`: a statement per diverging column and none for a matching, absent, or off-surface one (spec scenarios 1, 5, 6, 12); the statement carries `USING NULL::<type>`; the generated script still contains no `DROP`/`DELETE`/`TRUNCATE` (scenario 11); the type-name mapping is total over every value `subject_column_type` can return.

## 2. Introspection and the reconcile plan

- [x] 2.1 Add `_SUBJECT_COLUMN_TYPES_QUERY` over `information_schema.columns` for one schema's `subject` table.
- [x] 2.2 Extend `_reconcile_plan` to take the actual column types and append the convergence statements after the create/add-column statements, so a column created in this same run is never also converged.
- [x] 2.3 Read the column types in `reconcile_entity_tables` and `reconcile_entity_tables_sync` and pass them to the plan. Both executors keep sharing one plan — the sync/async split stays a difference of `execute` only.
- [x] 2.4 Log each convergence: schema, column, from-type, to-type, and that values were cleared (spec scenario 10).

## 3. Reconciler behaviour against a real schema

- [x] 3.1 Tests in `tests/test_entity_views_reconciler.py`: each supported `value_kind` creates its declared type, `duration` included (unchanged behaviour).
- [x] 3.2 Every type-changing transition converges: `TEXT → DOUBLE PRECISION`, `DOUBLE PRECISION → TEXT`, `TEXT → DATE`, `DATE → TEXT`, and both no-cast pairs `DOUBLE PRECISION ↔ DATE` (scenarios 1, 2, 3).
- [x] 3.3 A column holding values no cast could convert still converges, and the statement does not raise (scenario 4).
- [x] 3.4 Reconciling an already-correct schema emits no column-type statement and is idempotent across runs (scenario 5).
- [x] 3.5 The converged column holds NULL and `document_entities` is unchanged in content and shape (scenarios 8, 9).
- [x] 3.6 A deactivated definition's column keeps its type and its values; reactivating it with a changed `value_kind` converges it (scenarios 13, 14).
- [x] 3.7 The `PHONE_NUMBER` regression: physical `TEXT`, catalog changed to `number`, reconcile — the schema must not remain mismatched.

## 4. The entity-definition write paths

- [x] 4.1 Test in `tests/test_entity_definition_reconcile.py`: `update_entity_type` changing `value_kind` converges the column in the same call.
- [x] 4.2 Test that a reconciliation raising mid-DDL leaves the catalog's `value_kind` and the column's physical type in agreement — the update is not committed (scenario 15).
- [x] 4.3 Confirm the existing reconcile tests still pass unchanged: create, cardinality flips, toggle, soft delete, and the no-drop assertion.

## 5. Projection

- [x] 5.1 Test in `tests/test_relational_projection_worker.py`: after a `value_kind` change and a re-extraction, the column holds the representation the new kind selects — `7708888801`, not `7708888801.0` (scenario 16).
- [x] 5.2 Confirm `relational_projection.py`, `worker.py`, and the EAV schema carry no diff.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (test output / log excerpt) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 6.6 Run the full suite and diff the failing-test set against the recorded baseline for this repo; no new failures attributable to this change.
- [x] 6.7 Run `openspec validate subject-column-type-convergence --type change --strict` and confirm it exits clean before archive.
