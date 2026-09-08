# Verification Plan

**Change:** subject-column-type-convergence
**Generated:** 2026-08-24
**Status:** 🟡 Implementation verified — every scenario has a passing acceptance test and the Evidence Log is populated. Outstanding before archive: the full-suite baseline diff (task 6.6) and the human Audit Record below.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | A column created under one kind converges when the kind changes | Given a `subject` column physically `TEXT`, when its definition's `value_kind` changes to one declaring `DOUBLE PRECISION` and the schema is reconciled, then the column is `DOUBLE PRECISION` | `tests/test_entity_views_reconciler.py` (task 3.2) | - [x] |
| 2 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | Convergence works in the reverse direction | Given a column physically `DOUBLE PRECISION`, when the kind changes to one declaring `TEXT` and the schema is reconciled, then the column is `TEXT` | `tests/test_entity_views_reconciler.py` (task 3.2) | - [x] |
| 3 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | Convergence works between types with no PostgreSQL cast | Given a column physically `DOUBLE PRECISION`, when the kind changes to `date` and the schema is reconciled, then the column is `DATE` and nothing raises | `tests/test_entity_views_reconciler.py` (task 3.2) | - [x] |
| 4 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | A kind change cannot fail on the data the column holds | Given a `TEXT` column holding unparseable values, when the kind changes to one declaring `DOUBLE PRECISION` and the schema is reconciled, then reconciliation succeeds and the column is `DOUBLE PRECISION` | `tests/test_entity_views_reconciler.py` (task 3.3) | - [x] |
| 5 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | An already-correct column is left untouched | Given a schema whose columns all match, when it is reconciled, then no column-type statement is emitted and repeated runs change nothing | `tests/test_entity_views_generator.py` + `tests/test_entity_views_reconciler.py` (tasks 1.3, 3.4) | - [x] |
| 6 | entity-view-layer | A generated `subject` column's physical type equals the type its definition declares | A newly created column needs no convergence | Given a `single` definition whose column does not exist, when the schema is reconciled, then the column is created at its declared type and no column-type statement is emitted for it | `tests/test_entity_views_generator.py` (task 1.3) | - [x] |
| 7 | entity-view-layer | Converging a column preserves the system of record and destroys no relation | The entity store is untouched by a type change | Given a tenant with `document_entities` rows, when a `value_kind` changes and the schema is reconciled, then `document_entities` is unchanged in content and shape | `tests/test_entity_views_reconciler.py` (task 3.5) | - [x] |
| 8 | entity-view-layer | Converging a column preserves the system of record and destroys no relation | The column is cleared rather than cast | Given a `TEXT` column holding `'5 years'`, when the kind changes to one declaring `DOUBLE PRECISION` and the schema is reconciled, then the column holds NULL and a log line names the column and both types | `tests/test_entity_views_reconciler.py` (tasks 2.4, 3.5) | - [x] |
| 9 | entity-view-layer | Converging a column preserves the system of record and destroys no relation | No generated relation is dropped by a type change | Given any definitions and any schema state, when the statements are generated, then they contain no `DROP TABLE`, `DROP COLUMN`, `DELETE`, or `TRUNCATE` | `tests/test_entity_views_generator.py` (task 1.3) | - [x] |
| 10 | entity-view-layer | Converging a column preserves the system of record and destroys no relation | The projection writes the new representation after convergence | Given a converged column, when a document carrying that entity is extracted, then the column holds the representation the new `value_kind` selects | `tests/test_relational_projection_worker.py` (task 5.1) | - [x] |
| 11 | entity-view-layer | A column no active `single` definition owns is left at its existing type | A deactivated definition's column keeps its type and rows | Given an active `single` definition whose column holds values, when it is deactivated and the schema is reconciled, then the column retains its type and its values | `tests/test_entity_views_reconciler.py` (task 3.6) | - [x] |
| 12 | entity-view-layer | A column no active `single` definition owns is left at its existing type | A column reclaimed by a reactivated definition converges | Given a deactivated definition whose column type no longer matches its `value_kind`, when it is reactivated and the schema is reconciled, then the column matches its declared type | `tests/test_entity_views_reconciler.py` (task 3.6) | - [x] |
| 13 | entity-view-layer | A failed convergence leaves the catalog and the physical schema consistent | A failing reconciliation rolls back the definition change | Given an update changing `value_kind`, when reconciliation raises while applying the schema change, then the update is not committed and the persisted `value_kind` still matches the column's physical type | `tests/test_entity_definition_reconcile.py` (task 4.2) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Type-name comparison (design Decision 1) | Comparing the emitted SQL type (`DOUBLE PRECISION`) against `information_schema`'s spelling (`double precision`) and concluding every column diverges — which would blank every column on every reconcile | Read the mapping table and its totality test. Assert that reconciling an unchanged schema emits zero column-type statements, and that a second consecutive reconcile does too |
| 2 | Conversion expression (design Decision 2) | Emitting a value-preserving cast for the pairs where one exists, so behaviour differs by transition and fails on unparseable data | Grep the generated statements for `USING NULL::`; confirm one statement shape for all six transitions, and that the unparseable-data test passes |
| 3 | Statement ordering (design Decision 1) | Emitting the `ALTER … TYPE` before the `ADD COLUMN IF NOT EXISTS`, so a column created in the same run is immediately blanked, or a convergence targets a column that does not exist yet | Inspect the statement list order for a schema that both gains a column and converges another |
| 4 | Off-surface columns (design Decision 5) | Converging every generated column rather than only those an active `single` definition owns, blanking retained data for a deactivated or `multi`-flipped definition | Assert a deactivated definition's column keeps both its type and its rows through a reconcile |
| 5 | Scope creep into the projection | "Fixing" the mismatch by making `value_for_column` inspect the physical column type, hiding the schema bug instead of repairing the schema | Confirm `relational_projection.py` carries no diff |
| 6 | Transaction boundary | Catching the reconciliation error inside `EntityService` so the catalog write commits over a schema that did not converge | Confirm no new `try`/`except` around `_reconcile`; assert the rollback test |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Separate PostgreSQL schema per tenant | Introspection and DDL are per schema, from the schema the caller resolved; no cross-schema read | Confirm the introspection query is parameterised by schema and called once per reconcile with the caller's schema |
| ADR-004-openspec-governance | Structured artifacts per change | Proposal, design, delta spec, tasks, and verification present and consistent | `openspec validate subject-column-type-convergence --type change --strict` |
| ADR-007-chatbot-architecture | Structured SQL over extracted entities, validated and read-only | The declared column type becomes true, which is what makes a generated numeric comparison meaningful; validation and execution unchanged | Confirm no diff in `sql_generator.py`; confirm the query surface reports the same type the database now holds |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Rows 1–3: test output showing all six type-changing transitions converge, including both no-cast pairs
- [x] Row 4: test output showing a column of unparseable text converges without raising
- [x] Rows 5, 6: test output showing zero column-type statements for a matching schema, for a newly created column, and on a second consecutive reconcile
- [x] Rows 7, 8: test output showing the converged column holds NULL, `document_entities` is unchanged, and the convergence was logged with both types
- [x] Row 9: test output asserting the generated script contains no destructive keyword for any definition set
- [x] Row 10: test output showing the projection writes the new representation after a kind change and a re-extraction
- [x] Rows 11, 12: test output showing a deactivated definition's column is untouched and a reactivated one converges
- [x] Row 13: test output showing a raising reconciliation leaves catalog and schema in agreement
- [x] Full-suite run diffed against the repo's recorded baseline, with no new failures attributable to this change

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] Scope boundary confirmed: no change to `relational_projection.py`, `worker.py`, `sql_generator.py`, the entity-definition API contract, the `document_entities` schema, or any migration
- [x] No change to the accepted `value_kind` vocabulary — `duration`, `money`, and `boolean` behave exactly as before

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — type-name mapping is total and an unchanged schema emits nothing
- [x] Risk 2 mitigation confirmed — one statement shape for every transition
- [x] Risk 3 mitigation confirmed — convergence statements follow the create/add-column statements
- [x] Risk 4 mitigation confirmed — off-surface columns keep their type and rows
- [x] Risk 5 mitigation confirmed — the projection carries no diff
- [x] Risk 6 mitigation confirmed — the reconciliation error is not caught, and the rollback test passes

---

## 5. Evidence Log

All runs executed 2026-08-24 against the local PostgreSQL test database
(`venv/Scripts/python -m pytest <file> -q`). Counts are each run's own summary line.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test run | `tests/test_entity_views_generator.py` — 97 passed. `TestSubjectColumnTypeConvergence` asserts one `ALTER … USING NULL::<type>` per diverging column and none for a matching, absent, or off-surface one; that all three directions are reported with both types; that the script stays free of `DROP`/`DELETE`/`TRUNCATE`; that `_INFORMATION_SCHEMA_TYPE` is total over `subject_column_type`'s range; and that `number`/`money`/`duration`/`boolean` still declare `DOUBLE PRECISION` so a kind change within one type class emits no DDL | 1, 2, 3, 5, 6, 9, 11 | agent | 2026-08-24 |
| 2 | Test run | `tests/test_entity_views_reconciler.py` — 34 passed against a real tenant schema. `TestSubjectColumnTypeConverges` covers `TEXT → DOUBLE PRECISION`, `DOUBLE PRECISION → TEXT`, `TEXT ↔ DATE`, and both no-cast pairs `DOUBLE PRECISION ↔ DATE`; a column holding `'unknown'` converging without raising; an unchanged schema emitting no `ALTER COLUMN` and keeping its values; a newly created column never also retyped; convergence ordered after the `ADD COLUMN` statements; a deactivated definition's column keeping type and rows, and converging on reactivation; the `PHONE_NUMBER` regression in both directions; the sync executor converging identically; and `duration` still declaring `DOUBLE PRECISION` | 1, 2, 3, 4, 5, 6, 7, 8, 11, 12 | agent | 2026-08-24 |
| 3 | Test run | `tests/test_entity_definition_reconcile.py` — 16 passed. `TestValueKindChangeConvergesTheColumn` drives the real `EntityService.update_entity_type`: a kind change converges the column in the same call, in both directions; the persisted `value_kind` and the physical type agree after each of three successive changes; an unrelated description edit retypes nothing. The existing create / cardinality-flip / toggle / soft-delete / no-drop tests pass unchanged | 1, 2, 13 | agent | 2026-08-24 |
| 4 | Test run | `tests/test_relational_projection_worker.py::TestProjectionAfterAValueKindChange` — 4 passed. The full chain: catalog change → run-start reconcile converges the column → the next extraction writes the representation the new kind selects. `text` projects `'7708888801'`, `number` projects `7708888801.0` into a `DOUBLE PRECISION` column, changing back restores `'7708888801'` rather than the `'7708888801.0'` the live misconfiguration produced, and `document_entities` is unchanged throughout | 7, 10 | agent | 2026-08-24 |
| 5 | Test run | Combined run of `test_entity_views_generator`, `test_entity_views_reconciler`, `test_entity_definition_reconcile`, `test_relational_projection_worker`, `test_relational_projection_generator`, `test_entity_type_view_metadata_api`, `test_entity_definition_spec_loader`, `test_sql_execution_privileges` — **274 passed** | all | agent | 2026-08-24 |
| 6 | Measurement | PostgreSQL cast behaviour probed on the dev database inside rolled-back transactions, before the design was fixed: bare `ALTER … TYPE` fails `TEXT → DOUBLE PRECISION` and `TEXT → DATE` (`DatatypeMismatchError`) even for an empty or all-NULL column; no cast exists in either direction between `DOUBLE PRECISION` and `DATE`; a casting `USING` aborts on the first unparseable row; `USING NULL::<type>` succeeds for every pair. This is the evidence behind design Decision 2 | Risk 2 | agent | 2026-08-24 |
| 7 | Measurement | Divergence scan across every tenant schema in the dev database: no `subject` column type mismatches remain (the one instance, `PHONE_NUMBER`, was corrected by hand before this change and is preserved as a regression test), and all 13 child tables carry the fixed 11-column shape, confirming `multi` definitions cannot diverge | 11 | agent | 2026-08-24 |
| 8 | Static check | Scope boundary: `git status` shows no diff in `relational_projection.py`, `worker.py`, `sql_generator.py`, `entity_service.py`, the entity-definition API, the `document_entities` schema, or `alembic/` attributable to this change. The only source file modified is `src/shared/entity_views.py` | Structural | agent | 2026-08-24 |
| 9 | Static check | Vocabulary unchanged: `SUPPORTED_KINDS` is untouched, and `test_every_supported_value_kind_has_a_declared_type` pins all six kinds to their existing declared types. `duration` keeps its unit normalisation (`18 months` → 1.479 years, measured) | Structural | agent | 2026-08-24 |
| 5b | Suite run | Full suite, `pytest -q --tb=no -rf --continue-on-collection-errors -p no:randomly`: **91 failed, 1802 passed, 29 skipped, 32 errors**. The failing-test set is byte-identical to the pre-change baseline captured earlier the same day — `comm` over the two sorted FAILED/ERROR lists reports zero new and zero disappeared — while passes rose 1763 → 1802, the 39 tests this change adds. Zero failures in any file it touches | task 6.6 | agent | 2026-08-24 |
| 10 | Note | Two findings surfaced while implementing, both out of scope and reported separately rather than fixed here: (a) the shared `engine` fixture in `tests/conftest.py` is created with `isolation_level="AUTOCOMMIT"`, so no test bound to it can observe a transaction boundary — the rollback test builds its own transactional engine for that reason; (b) an entity type whose name is a SQL reserved word (`When`, `Order`, `Select`) generates a `subject` column of that bare name, and the `ADD COLUMN` for it is a syntax error that fails reconciliation for the whole tenant | — | agent | 2026-08-24 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.**

**Change slug:** subject-column-type-convergence
**Proposal:** `openspec/changes/subject-column-type-convergence/proposal.md`
**Spec files reviewed:**

- specs/entity-view-layer/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
