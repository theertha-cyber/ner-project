# Verification Plan

**Change:** entity-view-layer-foundation
**Generated:** 2026-08-19
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | Punctuation and spacing are slugged | Given the name `Skills & Tools` and an empty taken set, when `to_sql_identifier` runs, then it returns exactly `e_skills_tools` | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_punctuation_slugged` | - [ ] |
| 2 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | A reserved word is neutralized by the prefix | Given the name `select`, when `to_sql_identifier` runs, then it returns `e_select` and the result is usable unquoted in generated DDL | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_reserved_word_prefixed` | - [ ] |
| 3 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | A name starting with a digit is still valid | Given the name `2024 Revenue`, when `to_sql_identifier` runs, then the result matches `^e_[a-z0-9][a-z0-9_]*$` | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_leading_digit_valid` | - [ ] |
| 4 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | An over-length name is truncated before suffixing | Given a 200-character name and a taken set already holding its un-suffixed slug, when `to_sql_identifier` runs, then the result is ≤63 characters and is not in taken | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_overlong_truncated_before_suffix` | - [ ] |
| 5 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | Collisions resolve deterministically | Given `Vendor Name` then `vendor-name` slugged in order accumulating into taken, when both run, then the two identifiers differ and repeating the sequence yields the identical pair | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_collisions_deterministic` | - [ ] |
| 6 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | Degenerate input yields a valid fallback | Given the name `""`, `---`, or a name that slugs to nothing, when `to_sql_identifier` runs, then it returns a value matching `^e_[a-z0-9][a-z0-9_]*$` without raising | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_degenerate_input_fallback` | - [ ] |
| 7 | entity-view-layer | Tenant-supplied names are slugged into safe SQL identifiers | An injection attempt produces an inert identifier | Given the name `"; DROP TABLE documents; --"`, when the identifier is used to build view DDL, then no generated statement contains `DROP TABLE`, `;`, or `--` outside a quoted literal and the identifier matches `^e_[a-z0-9][a-z0-9_]*$` | unit test: `tests/test_entity_views_generator.py::TestToSqlIdentifier::test_injection_name_inert` | - [ ] |
| 8 | entity-view-layer | View DDL is produced by a pure function | The generator touches no database | Given specs and a schema name with no database configured or reachable, when `build_entity_view_statements` is called, then it returns a statement list without error | unit test: `tests/test_entity_views_generator.py::TestPureGeneration::test_no_database_required` | - [ ] |
| 9 | entity-view-layer | View DDL is produced by a pure function | Generation is idempotent | Given identical inputs, when `build_entity_view_statements` is called twice, then the two returned lists are equal | unit test: `tests/test_entity_views_generator.py::TestPureGeneration::test_generation_idempotent` | - [ ] |
| 10 | entity-view-layer | View DDL is produced by a pure function | The schema name is validated | Given a schema argument that is not a bare SQL identifier, when the generator is called, then it raises instead of emitting the statement | unit test: `tests/test_entity_views_generator.py::TestPureGeneration::test_invalid_schema_raises` | - [ ] |
| 11 | entity-view-layer | Each active multi-valued entity gets a child view | A multi definition produces its child view | Given an active spec `name=SKILL, sql_identifier=e_skill, cardinality=multi`, when statements are generated for `tenant_acme`, then the output contains `CREATE OR REPLACE VIEW tenant_acme.e_skill` including `WITH (security_barrier)` and selecting from `tenant_acme.document_entities` | unit test: `tests/test_entity_views_generator.py::TestChildViews::test_single_multi_definition` | - [ ] |
| 12 | entity-view-layer | Each active multi-valued entity gets a child view | Many multi definitions each get their own view | Given three active multi specs with distinct identifiers, when statements are generated, then exactly three child-view `CREATE OR REPLACE VIEW` statements are emitted | unit test: `tests/test_entity_views_generator.py::TestChildViews::test_three_multi_definitions` | - [ ] |
| 13 | entity-view-layer | Entity type matching is case-insensitive and covers base-model labels | Stored case differing from definition case still matches | Given a definition named `Skill` and rows stored with `entity_type='SKILL'`, when the child view is queried, then those rows are returned | integration test: `tests/test_entity_views_reconciler.py::test_mixed_case_entity_type_matches` | - [ ] |
| 14 | entity-view-layer | Entity type matching is case-insensitive and covers base-model labels | A base-model label maps into the view | Given a definition named `Employer` whose `base_label_mapping` has key `ORG`, when the child view is generated, then the emitted predicate admits both `EMPLOYER` and `ORG` | unit test: `tests/test_entity_views_generator.py::TestPredicate::test_base_label_mapping_included` | - [ ] |
| 15 | entity-view-layer | Entity type matching is case-insensitive and covers base-model labels | A definition without a base label mapping matches on name alone | Given a definition whose `base_label_mapping` is NULL or empty, when the child view is generated, then the predicate admits only the uppercased name | unit test: `tests/test_entity_views_generator.py::TestPredicate::test_no_mapping_matches_name_only` | - [ ] |
| 16 | entity-view-layer | Each tenant gets a subject view pivoting its single-valued entities | A single definition becomes a subject column | Given an active spec `sql_identifier=e_email, cardinality=single`, when `subject` is generated, then it projects a column named `email` | unit test: `tests/test_entity_views_generator.py::TestSubjectView::test_single_definition_becomes_column` | - [ ] |
| 17 | entity-view-layer | Each tenant gets a subject view pivoting its single-valued entities | Zero single definitions still yields a valid view | Given a definition list with no active single specs, when `subject` is generated, then the statement is valid SQL projecting `document_id` and `filename` | unit test: `tests/test_entity_views_generator.py::TestSubjectView::test_zero_singles_still_valid` | - [ ] |
| 18 | entity-view-layer | Each tenant gets a subject view pivoting its single-valued entities | A document with no entities still appears | Given a document row with no matching `document_entities` rows, when `subject` is queried, then one row is returned for that document with NULL entity columns | integration test: `tests/test_entity_views_reconciler.py::test_entityless_document_still_appears` | - [ ] |
| 19 | entity-view-layer | Each tenant gets a subject view pivoting its single-valued entities | A pivot column name colliding with an identity column is disambiguated | Given an active single spec with `sql_identifier` of `e_filename` or `e_document_id`, when `subject` is generated, then no projected column duplicates `filename`/`document_id` and the statement is valid SQL | unit test: `tests/test_entity_views_generator.py::TestSubjectView::test_identity_column_collision_disambiguated` | - [ ] |
| 20 | entity-view-layer | Each tenant gets a subject view pivoting its single-valued entities | A typed single entity projects both typed and textual columns | Given an active single spec with a non-text `value_kind` and `sql_identifier=e_years_experience`, when `subject` is generated, then it projects `years_experience` and `years_experience_text` | unit test: `tests/test_entity_views_generator.py::TestSubjectView::test_typed_single_projects_both_columns` | - [ ] |
| 21 | entity-view-layer | The subject view is dropped and recreated, never replaced in place | The drop precedes the create | Given any definition list, when statements are generated, then the output contains `DROP VIEW IF EXISTS <schema>.subject CASCADE` and the matching `CREATE VIEW <schema>.subject` appears after it | unit test: `tests/test_entity_views_generator.py::TestSubjectView::test_drop_precedes_create` | - [ ] |
| 22 | entity-view-layer | The subject view is dropped and recreated, never replaced in place | Adding a single definition changes the column list cleanly | Given a schema whose `subject` already has one pivot column, when a second single definition is added and statements re-applied, then no `cannot change name of view column` error occurs and `subject` projects both pivot columns | integration test: `tests/test_entity_views_reconciler.py::test_added_single_changes_column_list_cleanly` | - [ ] |
| 23 | entity-view-layer | The subject view is dropped and recreated, never replaced in place | Re-applying an unchanged definition list is a no-op in effect | Given a schema whose views already match the definition list, when statements are applied again, then they succeed and the resulting view definitions are unchanged | integration test: `tests/test_entity_views_reconciler.py::test_reapply_unchanged_is_noop` | - [ ] |
| 24 | entity-view-layer | Views for inactive or deleted definitions are dropped without touching rows | An inactive definition gets no child view but does get a drop | Given a spec with `is_active=false, cardinality=multi`, when statements are generated, then no `CREATE OR REPLACE VIEW` is emitted for its identifier and a `DROP VIEW IF EXISTS` is | unit test: `tests/test_entity_views_generator.py::TestDropStatements::test_inactive_definition_drops_not_creates` | - [ ] |
| 25 | entity-view-layer | Views for inactive or deleted definitions are dropped without touching rows | Dropping a view leaves the underlying rows intact | Given a schema with a populated `document_entities` and an existing child view, when the drop statement executes, then the view is gone and the `document_entities` row count is unchanged | integration test: `tests/test_entity_views_reconciler.py::test_drop_view_leaves_rows_intact` | - [ ] |
| 26 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | A missing view is created | Given a tenant schema with `document_entities` and no entity views, when the reconciler runs with one active multi definition, then the child view exists and is queryable | integration test: `tests/test_entity_views_reconciler.py::test_missing_view_created` | - [ ] |
| 27 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | A stale view is repaired | Given a schema whose `subject` predates a newly added single definition, when the reconciler runs with the updated list, then `subject` projects the new pivot column | integration test: `tests/test_entity_views_reconciler.py::test_stale_subject_repaired` | - [ ] |
| 28 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | An orphaned view is dropped | Given a schema with a child view whose definition was deactivated, when the reconciler runs, then that view no longer exists | integration test: `tests/test_entity_views_reconciler.py::test_orphaned_view_dropped` | - [ ] |
| 29 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | A schema without document_entities is skipped | Given a tenant schema from a template predating `document_entities`, when the reconciler runs, then it returns without raising and creates no views there | integration test: `tests/test_entity_views_reconciler.py::test_schema_without_document_entities_skipped` | - [ ] |
| 30 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | A tenant with no definitions still gets subject | Given a tenant schema with `document_entities` and an empty definition list, when the reconciler runs, then `<schema>.subject` exists, is queryable, and projects `document_id` and `filename` | integration test: `tests/test_entity_views_reconciler.py::test_no_definitions_still_gets_subject` | - [ ] |
| 31 | entity-view-layer | The reconciler applies generated DDL idempotently per tenant schema | Running twice changes nothing the second time | Given a reconciled tenant schema, when the reconciler runs again with the same definitions, then it succeeds and the set of views in the schema is identical | integration test: `tests/test_entity_views_reconciler.py::test_second_run_changes_nothing` | - [ ] |
| 32 | entity-config | Entity Type Definition (MODIFIED) | Tenant Admin creates an entity type | Given an authenticated Tenant Admin for `acme-corp`, when they POST a new entity type, then the response is 201 with `name`, `version: 1`, `is_active: true` | existing suite (regression only): `tests/test_entity_config.py` create path, diffed against the task 1.2 baseline | - [ ] |
| 33 | entity-config | Entity Type Definition (MODIFIED) | Tenant Admin updates an entity type | Given entity type `customer_name` at version 1, when the admin PUTs a new description, then the response is 200 with `version: 2` and the updated description | existing suite (regression only): `tests/test_entity_config.py` update path, diffed against the task 1.2 baseline | - [ ] |
| 34 | entity-config | Entity Type Definition (MODIFIED) | An entity type predating the view layer defaults to multi | Given a row created before the view-layer metadata existed, when `037` is applied, then its `cardinality` is `multi` and its `sql_identifier` is a valid identifier derived from `name` | migration test: `tests/test_migration_037_entity_view_metadata.py::test_preexisting_row_defaults_to_multi_with_identifier` | - [ ] |
| 35 | entity-config | Entity Type Definition (MODIFIED) | Cardinality is constrained to the two known values | Given `public.entity_definitions` after `037`, when a row is written with `cardinality='many'`, then the write is rejected by a CHECK constraint | migration test: `tests/test_migration_037_entity_view_metadata.py::test_cardinality_check_constraint_rejects_unknown` | - [ ] |
| 36 | entity-config | Entity Type Definition (MODIFIED) | Two tenants may share an sql_identifier | Given tenant A has `sql_identifier='e_skill'`, when tenant B writes the same identifier the write succeeds, and when tenant A writes a second row with `e_skill` the partial unique index rejects it | migration test: `tests/test_migration_037_entity_view_metadata.py::test_sql_identifier_unique_per_tenant_not_globally` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Entity type predicate (design Decision 1) | Reverting to the naive `WHERE entity_type = 'SKILL'` from the task brief's SQL sketch, dropping either the `upper()` or the `base_label_mapping` literals. Views then silently return zero rows for base-model tenants or for any case mismatch — no error, just an empty result. | Read every generated `WHERE` clause in the module. Each must be `upper(...entity_type) IN (...)`. Confirm a definition with a non-empty `base_label_mapping` contributes its keys as extra literals, and that the keys are uppercased and slugged/escaped, not interpolated raw. |
| 2 | `subject` replace strategy (design Decision 2) | Emitting `CREATE OR REPLACE VIEW … subject` because it matches the child-view code path, or applying drop-and-create uniformly to child views too. The first breaks the moment a `single` definition is added; the second silently revokes the grants step 5 will attach. | Grep the generated statement list: `subject` must be preceded by `DROP VIEW IF EXISTS … CASCADE`; every `e_*` view must use `CREATE OR REPLACE` and must **not** appear in any drop for an active definition. |
| 3 | Typed vs. text projection (design Decision 5) | Projecting only the typed column for a non-text `value_kind`, silently dropping every row `apply_semantic_normalization` could not parse; or emitting `COALESCE(value_number::text, entity_value)` which makes numeric comparison lexicographic. | For a non-text `value_kind` spec, confirm two distinct columns (`x` and `x_text`) with `MAX(value_number)` and `MAX(entity_value)` respectively. Confirm no `::text` cast or `COALESCE` appears in the pivot. |
| 4 | Identifier slugging totality (design Decision 3) | Raising on empty or non-Latin input instead of falling back, or truncating to 63 *after* appending the collision suffix so a suffixed identifier exceeds the limit. Either bug aborts the migration backfill mid-run. | Read `to_sql_identifier` directly. Confirm no `raise` on degenerate input, and that truncation happens before suffixing. Run the 200-character + collision case and measure `len()` of the result. |
| 5 | Migration backfill drift (design Decision 8) | Reimplementing the slug rule as a SQL `regexp_replace` inside the migration instead of importing `to_sql_identifier`. The two implementations then drift and the migration writes identifiers the generator will never create views for — orphaned views, invisible in tests that exercise only one side. | Confirm `037` imports `to_sql_identifier` from `src/shared/entity_views.py` and calls it. Confirm no `regexp_replace` or `lower(` slug logic appears in the migration SQL. |
| 6 | Reconciler failure tolerance (spec: reconciler requirement) | Letting the "schema lacks `document_entities`" case raise instead of skipping, so one legacy tenant schema aborts reconciliation for every tenant after it. Also: dropping the wrong thing — emitting `DROP TABLE` or an unqualified `DROP VIEW` without `IF EXISTS`. | Confirm the existence guard mirrors the `IF EXISTS (SELECT 1 FROM information_schema.tables …)` pattern used in `029`/`035`. Grep the whole module for `DROP TABLE`, `DELETE`, `TRUNCATE` — there must be zero matches. |
| 7 | Scope creep into steps 3–6 | Wiring the reconciler into `entity_service` or `TenantService.create_tenant()`, adding view names to `WHITELISTED_TABLES`, or touching the generator prompt — all explicitly out of scope and all off-limits files. | `git diff --stat` must show no change to `src/chat_api/services/sql_generator.py`, `src/chat_api/services/sql_execution_role.py`, `src/gateway/services/entity_service.py`, or `src/gateway/services/tenant_service.py`. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | One `tenant_<slug>` schema per tenant; `public` holds shared tables; isolation enforced at every layer. | Views are created inside the tenant schema and reference only objects in that same schema. No generated statement may name two different schemas. `sql_identifier` uniqueness is per-tenant, never global. | Read every generated statement: each must qualify its objects with exactly one schema, and that schema must be the function's `schema` argument. Confirm the `037` unique index is on `(tenant_id, sql_identifier)`, not `sql_identifier` alone. Confirm no generated view references `public.` |
| ADR-004: OpenSpec Spec-Driven Development Governance | Changes are specified before implementation. | Implementation follows this change's `tasks.md`; deviations are recorded, not silently taken. | Confirm every task in `tasks.md` is checked off or explicitly marked skipped with a reason, and that no implementation file exists outside the Impact list in `proposal.md`. |
| ADR-007: Chatbot Architecture with Full RAG and Guardrails | SQL over extracted entities runs in read-only transactions behind a validation layer and a least-privilege role. | Generated views carry `WITH (security_barrier)`. The execution role gets no grant on them in this change — views exist but are unreadable by the restricted role until step 5, which is the safe ordering. | Confirm every `CREATE [OR REPLACE] VIEW` includes `WITH (security_barrier)`. Confirm `git diff` shows no change to the grant list in `sql_execution_role.py` and no `GRANT` statement in the new module. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenarios 1–7 (identifier slugging): pytest output showing the `to_sql_identifier` test class passing, including the 200-char, collision, degenerate-input, and injection cases, with the asserted return values visible
- [ ] Scenarios 8–10 (pure function): pytest output for the generator tests, collected and passing in a run with no database available, plus the raising case for an invalid schema name
- [ ] Scenarios 11–12 (child views): the generated statement list for one and for three `multi` specs, captured verbatim from a test assertion or a REPL transcript
- [ ] Scenarios 13–15 (entity type predicate): the generated `WHERE` clause for a definition with and without `base_label_mapping`, plus a query result against a real schema proving mixed-case rows are returned
- [ ] Scenarios 16–20 (subject pivot): the generated `subject` statement for zero, one text, one typed, and one identity-colliding `single` spec; plus a query result showing an entity-less document still yielding a row
- [ ] Scenarios 21–23 (drop-and-create): the emitted statement order, plus a real-schema transcript adding a second `single` definition and re-applying without a `cannot change name of view column` error
- [ ] Scenarios 24–25 (drops): the generated drop for an inactive definition, plus before/after `count(*)` on `document_entities` around a real drop
- [ ] Scenarios 26–31 (reconciler): integration test output covering create, repair, orphan drop, legacy-schema skip, empty-definition `subject`, and a second identical run
- [ ] Scenarios 32–33 (entity CRUD unchanged): existing entity-types API tests still passing at their baseline status after the model change
- [ ] Scenario 34 (backfill): a `SELECT id, name, cardinality, sql_identifier FROM public.entity_definitions` transcript from the dev database after `037`, showing non-NULL identifiers and `cardinality='multi'` on every pre-existing row
- [ ] Scenarios 35–36 (constraints): the exact Postgres error text from attempting `cardinality='many'` and from a duplicate `(tenant_id, sql_identifier)` insert, plus the successful cross-tenant duplicate
- [ ] Baseline diff: the pre-change pytest summary and the post-change summary side by side, showing no newly failing test

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] `alembic downgrade 036` executed and confirmed to remove both columns and the index; `upgrade` re-applied cleanly
- [ ] Module docstring records the `TenantService.create_tenant()` view-cloning gap as a step-3 prerequisite

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — every generated predicate inspected; all use `upper(...) IN (...)` and include base-label keys where present
- [ ] Risk 2 mitigation confirmed — `subject` uses DROP+CREATE, child views use CREATE OR REPLACE, verified in the emitted statement list
- [ ] Risk 3 mitigation confirmed — typed `single` specs project both `x` and `x_text`; no `COALESCE` or `::text` in the pivot
- [ ] Risk 4 mitigation confirmed — `to_sql_identifier` never raises on degenerate input; truncation precedes suffixing, verified by the 200-char collision case
- [ ] Risk 5 mitigation confirmed — `037` imports and calls `to_sql_identifier`; no duplicated slug logic in the migration
- [ ] Risk 6 mitigation confirmed — legacy-schema skip verified against a real schema lacking `document_entities`; zero matches for `DROP TABLE`/`DELETE`/`TRUNCATE` in the module
- [ ] Risk 7 mitigation confirmed — `git diff --stat` shows no change to the four out-of-scope files

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |
| 4 | | | | | |
| 5 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** entity-view-layer-foundation
**Proposal:** `openspec/changes/entity-view-layer-foundation/proposal.md`
**Spec files reviewed:**

- `specs/entity-view-layer/spec.md`
- `specs/entity-config/spec.md`

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
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
