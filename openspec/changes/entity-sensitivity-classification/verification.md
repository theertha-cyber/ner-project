# Verification Plan

**Change:** entity-sensitivity-classification
**Generated:** 2026-09-17
**Status:** ✅ Implemented and self-verified by the implementing agent. Human review and Audit
Record sign-off still pending (§ 6).

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | entity-config | Entity Type Definition | Tenant Admin creates an entity type | Given a Tenant Admin POSTs a new entity type, when created, then it returns 201 with `version: 1`, `value_kind: "text"`, and `sensitivity: "open"` | pytest: `test_entity_config_value_kind.py::test_create_entity_type_defaults_value_kind_to_text` + `test_entity_config_sensitivity.py::test_new_entity_types_default_to_open` | - [x] |
| 2 | entity-config | Entity Type Definition | Tenant Admin updates an entity type | Given an existing entity type, when its description is updated, then version increments and description changes | pytest: `test_entity_config_value_kind.py::test_update_entity_type_increments_version` | - [x] |
| 3 | entity-config | Entity Type Definition | Tenant Admin adds QA pairs to an entity type | Given an entity type with no QA pairs, when QA pairs are added, then they are stored and version increments | | - [ ] |
| 4 | entity-config | Entity Type Definition | Entity type with no QA pairs remains valid | Given a create request with no `qa_examples`, when created, then it succeeds with an empty/null `qa_examples` | | - [ ] |
| 5 | entity-config | Entity Type Definition | Tenant Admin declares a structured value kind | Given a create request with `value_kind: "duration"`, when created, then the type stores that value_kind and value_unit | pytest: `test_entity_config_value_kind.py::test_declare_structured_value_kind` | - [x] |
| 6 | entity-config | Entity Type Definition | Unsupported value kind is rejected | Given a create request with `value_kind: "geo"`, when submitted, then it returns 422 and creates nothing | pytest: `test_entity_config_value_kind.py::test_unsupported_value_kind_rejected` | - [x] |
| 7 | entity-config | Entity Type Definition | Existing entity types keep working | Given entity types created before `value_kind` existed, when read, then they report `value_kind: "text"` and behave as before | pytest: `test_entity_config_value_kind.py::test_existing_entity_types_default_to_text` | - [x] |
| 8 | entity-config | Entity Type Definition | An entity type predating the view layer defaults to multi | Given a pre-037 row, when migration 037 applies, then `cardinality` is `multi` and `sql_identifier` is valid | pytest: `test_migration_037_entity_view_metadata.py::TestUpgrade::test_preexisting_row_defaults_to_multi_with_identifier` | - [x] |
| 9 | entity-config | Entity Type Definition | Cardinality is constrained to the two known values | Given the post-037 table, when a row is written with `cardinality = 'many'`, then it is rejected by a CHECK constraint | pytest: `test_migration_037_entity_view_metadata.py::TestConstraints::test_cardinality_check_constraint_rejects_unknown` | - [x] |
| 10 | entity-config | Entity Type Definition | Two tenants may share an sql_identifier | Given tenant A has `sql_identifier = 'e_skill'`, when tenant B creates one that also slugs to `e_skill`, then it succeeds, but a duplicate within tenant A is rejected | pytest: `test_migration_037_entity_view_metadata.py::TestConstraints::test_sql_identifier_unique_per_tenant_not_globally` | - [x] |
| 11 | entity-config | Entity Type Definition | An entity type predating sensitivity classification defaults to open | Given a pre-049 row, when migration 049 applies, then `sensitivity` is `open` and LLM pre-labeling treatment is unchanged | Manual verification against real `ner_dev`: `SELECT sensitivity, count(*) ... GROUP BY sensitivity` → 51/51 rows `open`; also `test_entity_config_sensitivity.py::test_existing_entity_types_backfill_to_open` | - [x] |
| 12 | entity-config | Entity Type Sensitivity Classification | Tenant Admin classifies a type as pattern with a validation rule | Given a create request with `sensitivity: "pattern"` and a `validation_rule`, when submitted, then it returns 201 with `sensitivity: "pattern"` | pytest: `test_entity_config_sensitivity.py::test_pattern_with_a_validation_rule_is_accepted` | - [x] |
| 13 | entity-config | Entity Type Sensitivity Classification | A pattern-sensitivity type without a validation rule is rejected | Given a create request with `sensitivity: "pattern"` and no `validation_rule`, when submitted, then it returns 422 naming the requirement and creates nothing | pytest: `test_entity_config_sensitivity.py::test_pattern_without_a_validation_rule_is_rejected` (+ `test_update_to_pattern_without_a_validation_rule_is_rejected` for the update path) | - [x] |
| 14 | entity-config | Entity Type Sensitivity Classification | Tenant Admin classifies a type as local_only with no extra configuration | Given a create request with `sensitivity: "local_only"` and no `validation_rule`, when submitted, then it returns 201 | pytest: `test_entity_config_sensitivity.py::test_local_only_needs_no_extra_configuration` | - [x] |
| 15 | entity-config | Entity Type Sensitivity Classification | An unsupported sensitivity value is rejected | Given a create request with `sensitivity: "confidential"`, when submitted, then it returns 422 and creates nothing | pytest: `test_entity_config_sensitivity.py::test_unsupported_sensitivity_is_rejected` | - [x] |
| 16 | entity-config | Entity Type Sensitivity Classification | Sensitivity can be changed on an existing entity type | Given an `open` entity type at version 1, when PUT with `sensitivity: "local_only"`, then it returns 200 with the new sensitivity and incremented version | pytest: `test_entity_config_sensitivity.py::test_sensitivity_is_mutable_on_update` | - [x] |
| 17 | entity-config | Entity Type Sensitivity Classification | New entity types default to open | Given a create request with no `sensitivity` field, when submitted, then the created type has `sensitivity: "open"` | pytest: `test_entity_config_sensitivity.py::test_new_entity_types_default_to_open` | - [x] |

Rows 1-10 restate the canonical `Entity Type Definition` requirement's existing scenario set in
full, per the archive tool's rule that a MODIFIED requirement replaces its entire scenario set —
they are regression coverage for this change (confirming the new field does not disturb existing
behavior), not new assertions. Row 11 and rows 12-17 are the new behavior this change introduces.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Enum surface for `sensitivity` | Implementing with different values than `open` / `pattern` / `local_only` (e.g. adding a fourth tier, or naming them `public`/`restricted`) not specified anywhere in design.md | Confirm the CHECK constraint in migration `049` and the API-layer validator both enumerate exactly `('open', 'pattern', 'local_only')` |
| 2 | Mutability | Copying the nearby `provenance` field's immutability pattern (added in `entity-type-provenance`) onto `sensitivity` by analogy, when design.md explicitly says it must stay mutable | Confirm the PUT/update endpoint accepts and changes `sensitivity` on an existing entity type, and that no immutability check was added |
| 3 | Validation scope | Checking "`validation_rule` is required" globally instead of only when `sensitivity == "pattern"`, breaking `open`/`local_only` type creation with no `validation_rule` | Confirm scenario 14 (local_only with no validation_rule) and a plain `open` creation with no `validation_rule` both still return 201 |
| 4 | Validation timing | Enforcing the pattern-requires-validation_rule check only on create, not on update (allowing a PUT that flips an existing type to `sensitivity: "pattern"` while leaving `validation_rule` null) | Add and confirm a test that PUTs `sensitivity: "pattern"` onto an entity type with no existing `validation_rule` and expects 422 |
| 5 | Downstream dependency silently unmet | Forgetting to add `sensitivity` to the SELECT list in `load_active_entity_config` / `load_active_entity_config_sync` (`src/shared/entity_config_version.py`), which the follow-up `automated-annotation-pii-masking` change depends on reading from the same call site | Confirm both functions' SELECT statements include `sensitivity` and that a call against a `local_only` type returns it in the result dict |
| 6 | Backfill default | Defaulting the migration's backfill to something other than `open` (e.g. defensively choosing `local_only` for all existing rows), which would silently change LLM pre-labeling's prompt content for every existing tenant the moment this migration runs, before the follow-up change even exists | Confirm the migration's column default and backfill both resolve to `open`, and confirm no other code path reads `sensitivity` yet (this change has no consumer) |
| 7 | Backward compatibility of the create/update API | Making `sensitivity` a required request field with no default, breaking any existing caller (tests, scripts, the portal build predating this change) that constructs an entity type payload without it | Confirm scenario 17: a create request with no `sensitivity` field returns 201 with `sensitivity: "open"`, not a 422 for a missing required field |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| — | No constraining ADRs | This is an additive, non-breaking data-modeling change following the same precedent as the existing `value_kind` and `provenance` columns; it introduces no new architectural pattern and no ADR-worthy durable commitment on its own | N/A |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenarios 1-2, 5-10 (Entity Type Definition, regression): pytest, `test_entity_config_value_kind.py` + `test_migration_037_entity_view_metadata.py`, all passing
- [ ] Scenarios 3-4 (QA pairs): not exercised this session — pre-existing behavior this change does not touch; no regression evidence collected either way
- [x] Scenario 11 (migration backfill defaults to open): direct DB assertion against real `ner_dev` (51/51 rows) + `test_entity_config_sensitivity.py::test_existing_entity_types_backfill_to_open`
- [x] Scenarios 12-13 (pattern sensitivity + validation_rule requirement): pytest, `test_entity_config_sensitivity.py` (create and update paths both covered)
- [x] Scenario 14 (local_only requires no extra config): pytest
- [x] Scenario 15 (unsupported sensitivity rejected): pytest
- [x] Scenario 16 (sensitivity mutable via update): pytest
- [x] Scenario 17 (defaults to open when omitted): pytest
- [x] Frontend: entity-types create/edit form sensitivity selector — `DefineEntityTypeSlideOver.sensitivity.test.tsx`, 9/9, covering default selection, pattern-requires-validation_rule client-side check, and round-tripping on edit

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (three-tier enum, `validation_rule` reuse for `pattern`, `open` default and backfill, mutability)
- [ ] No constraining ADRs (§ 3) — nothing to confirm beyond absence of a new undocumented pattern; left for human sign-off
- [x] No AI-invented requirements present in generated code (cross-checked against this change's spec delta)
- [x] Migration `049` reviewed and verified against a real database for a correct CHECK constraint and default

### Edge Case Evidence

- [x] Risk 1 (enum surface) confirmed against migration DDL and API validator, and exercised by scenario 15's 422 test
- [x] Risk 2 (mutability) confirmed by `test_sensitivity_is_mutable_on_update`
- [x] Risk 3 (validation scope) confirmed by `test_local_only_needs_no_extra_configuration` and by every `open`-sensitivity creation test succeeding with no `validation_rule`
- [x] Risk 4 (validation timing on update) confirmed by `test_update_to_pattern_without_a_validation_rule_is_rejected`
- [x] Risk 5 (downstream SELECT) confirmed both by code reading and transitively: `automated-annotation-pii-masking`'s own tests depend on `sensitivity` being present in `load_active_entity_config`'s output and pass
- [x] Risk 6 (backfill default) confirmed against real migration DDL and the live row count
- [x] Risk 7 (API backward compatibility) confirmed by `test_new_entity_types_default_to_open` (no `sensitivity` field sent)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `vitest run src/components/entity-types/DefineEntityTypeSlideOver.sensitivity.test.tsx`: 9/9 passed | Client-side mirror of 12, 13, 14, 16 | Claude (implementing agent) | 2026-09-17 |
| 2 | Functional | `vitest run src/hooks/use-create-entity-type.test.tsx src/components/entity-types/`: 69/70 passed. The 1 failure (`EntityTypesPage.test.tsx`, asserting text `"/api/v1/entity-types"`) is pre-existing and unrelated — confirmed by `grep` that this string does not appear anywhere in `EntityTypesPage.tsx` | Regression check, entity-types component suite | Claude (implementing agent) | 2026-09-17 |
| 3 | Structural | `tsc --noEmit -p tsconfig.json`, grepped for `entity-type`/`entity_type`: zero matches, after fixing a pre-existing gap in `use-create-entity-type.test.tsx`'s shared `payload` fixture (missing `qa_examples` before this change too; `sensitivity`/`validation_rule` added alongside it) | Type-safety regression, scoped to touched files | Claude (implementing agent) | 2026-09-17 |
| 4 | Structural | `alembic upgrade head` against real `ner_dev` via `docker compose up db-init`: migration `049` applied cleanly on top of `048`; `db-init`'s own `verify_schema` step reported "no drift detected" | Migration correctness, scenario 11 | Claude (implementing agent) | 2026-09-17 |
| 5 | Functional | Direct psql against `ner_dev`: `\d public.entity_definitions` shows `sensitivity VARCHAR(16) NOT NULL DEFAULT 'open'` and `ck_entity_definitions_sensitivity CHECK (sensitivity IN ('open','pattern','local_only'))`; `SELECT sensitivity, count(*) ... GROUP BY sensitivity` → `open: 51` (100% of pre-existing rows) | Scenario 11, Risk 6 | Claude (implementing agent) | 2026-09-17 |
| 6 | Functional | `pytest tests/test_entity_config_sensitivity.py -v` in an ad-hoc container (`ner-project-gateway` image + pip-installed pytest, source `docker cp`-ed in) against real Postgres (`ner_test`): 8/8 passed | Scenarios 1, 11-17 | Claude (implementing agent) | 2026-09-17 |
| 7 | Functional | `pytest tests/test_entity_config_value_kind.py tests/test_migration_037_entity_view_metadata.py tests/test_migration_042_045_guards.py tests/test_migration_entity_definition_value_kind.py -v`: 26/26 passed | Scenarios 1, 2, 5-10 (regression) | Claude (implementing agent) | 2026-09-17 |
| 8 | Functional | `pytest tests/test_pii_masking_wiring.py tests/test_llm_prelabel_*.py -v` (from the dependent `automated-annotation-pii-masking` change): all passed, which transitively confirms `sensitivity` is correctly readable from `load_active_entity_config` end to end (Risk 5) | Risk 5 (cross-change) | Claude (implementing agent) | 2026-09-17 |

**A real, unrelated gap found during this work** (not part of this change, not fixed as part of it): two test-fixture files (`tests/test_llm_prelabel_api.py`, `tests/seed_bootstrap_support.py`) maintain hand-rolled copies of `public.entity_definitions`'s DDL for isolation, and both were missing the new `sensitivity` column — they would have 500'd the moment any code path selected it. Patched with a defensive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, the same self-healing pattern `db-init`'s real migrations already use. Also found: the ORM model `EntityDefinition` (`src/gateway/models/__init__.py`) was itself missing the `sensitivity` column declaration (task 2.5) — without it, `Base.metadata.create_all`, which the pytest fixture database is built from, would never have created the column at all, independent of any migration.

---

## 6. Audit Record

**Change slug:** entity-sensitivity-classification
**Proposal:** `openspec/changes/entity-sensitivity-classification/proposal.md`
**Spec files reviewed:**
  - specs/entity-config/spec.md

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

**Archive approved by:** _(pending — not yet implemented)_

**Date:** _(pending)_

**Caveats carried into the archive:** _(none yet — this is a pre-implementation verification plan)_
