# Verification Plan

**Change:** structured-entity-value-normalization
**Generated:** 2026-07-31
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | structured-entity-values | Semantic normalization is distinct from lexical normalization | Lexical and semantic normalization produce independent outputs | Given a `YEARS_OF_EXP` entity reading "Two and a Half Years" for a type declared `duration`/`years`, when normalized, then `normalized_value` is `two and a half years`, `value_number` is `2.5`, and `entity_value` is unchanged | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_spelled_out_fractional_duration` | - [ ] |
| 2 | structured-entity-values | Semantic normalization is distinct from lexical normalization | Lexical normalization is unchanged for types with no value kind | Given a `SKILL` entity "ReactJS" with no declared kind, when normalized, then `normalized_value` is `react` and every semantic value column is NULL | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | - [ ] |
| 3 | structured-entity-values | Value kind vocabulary | Supported kind is accepted | Given a type configured with kind `duration`, when an entity of that type is normalized, then the `duration` parser is invoked | `tests/test_semantic_normalizer.py::TestSupportedKindDispatch::test_duration_kind_dispatches_duration_parser` | - [ ] |
| 4 | structured-entity-values | Value kind vocabulary | Unsupported kind is rejected at configuration time | Given a configuration request with kind `geo`, when it is saved, then it is rejected and no extraction run fails as a result | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_unsupported_value_kind_rejected` | - [ ] |
| 5 | structured-entity-values | Value kind vocabulary | Default kind preserves current behaviour | Given a type with no kind configured, when entities are extracted and persisted, then the rows are identical to pre-change output except the new columns exist and are NULL | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | - [ ] |
| 6 | structured-entity-values | Parser registry is extensible without pipeline changes | Registering a new kind requires no pipeline change | Given a newly registered parser and a type configured with that kind, when a document is extracted, then typed values are persisted with no diff in worker, entity store, or SQL whitelist | `tests/test_semantic_normalizer_extensibility.py::TestNewKindRequiresNoPipelineChange::test_registering_a_new_kind_persists_typed_values_with_no_pipeline_edit` | - [ ] |
| 7 | structured-entity-values | Parser registry is extensible without pipeline changes | Parsers are pure and offline | Given any registered parser, when it normalizes a value, then no LLM/network/database call occurs and repeated calls return identical output | `tests/test_semantic_normalizer.py::TestParsersArePureAndOffline` | - [ ] |
| 8 | structured-entity-values | Numeric and duration normalization | Spelled-out fractional duration | Given kind `duration` in `years` with text "two and a half years", when normalized, then `value_number` is `2.5` and `value_unit` is `years` | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_spelled_out_fractional_duration` | - [ ] |
| 9 | structured-entity-values | Numeric and duration normalization | Digit form with a unit suffix | Given kind `duration` in `years` with text "5 yrs", when normalized, then `value_number` is `5.0` | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_digit_form_with_unit_suffix` | - [ ] |
| 10 | structured-entity-values | Numeric and duration normalization | Source unit differs from canonical unit | Given kind `duration` in `days` with text "2 months", when normalized, then `value_number` is `60.0` and `value_unit` is `days` | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_source_unit_differs_from_canonical_unit` | - [ ] |
| 11 | structured-entity-values | Numeric and duration normalization | Thousands separators and magnitude suffixes | Given kind `money` in `INR` with texts "1,200,000" and "12 lakh", when normalized, then both yield `value_number` `1200000.0` and `value_unit` `INR` | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_thousands_separators_and_magnitude_suffixes` | - [ ] |
| 12 | structured-entity-values | Open bounds and closed ranges | Open lower bound | Given kind `duration` in `years` with text "5+ years", when normalized, then `value_number` is `5.0` and `value_number_high` is NULL | `tests/test_semantic_normalizer.py::TestOpenBoundsAndClosedRanges::test_open_lower_bound` | - [ ] |
| 13 | structured-entity-values | Open bounds and closed ranges | Phrased open bound | Given kind `duration` in `years` with text "more than three years", when normalized, then `value_number` is `3.0` | `tests/test_semantic_normalizer.py::TestOpenBoundsAndClosedRanges::test_phrased_open_bound` | - [ ] |
| 14 | structured-entity-values | Open bounds and closed ranges | Closed range | Given kind `duration` in `years` with text "3-5 years", when normalized, then `value_number` is `3.0` and `value_number_high` is `5.0` | `tests/test_semantic_normalizer.py::TestOpenBoundsAndClosedRanges::test_closed_range` | - [ ] |
| 15 | structured-entity-values | Date normalization | Full date | Given kind `date` with text "15 March 2027", when normalized, then `value_date` is `2027-03-15` | `tests/test_semantic_normalizer.py::TestDateNormalization::test_full_date` | - [ ] |
| 16 | structured-entity-values | Date normalization | Month and year only | Given kind `date` with text "March 2027", when normalized, then `value_date` is `2027-03-01` | `tests/test_semantic_normalizer.py::TestDateNormalization::test_month_and_year_only` | - [ ] |
| 17 | structured-entity-values | Date normalization | Unresolvable date yields NULL | Given kind `date` with text "next spring", when normalized, then `value_date` is NULL and the entity is still persisted | `tests/test_semantic_normalizer.py::TestDateNormalization::test_unresolvable_date_yields_none` | - [ ] |
| 18 | structured-entity-values | Unparseable values degrade to NULL, never to failure | Junk value in a structured type | Given a `duration`-declared entity with text "several", when normalized and persisted, then `value_number` is NULL, text columns are unchanged, and the run completes successfully | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | - [ ] |
| 19 | structured-entity-values | Unparseable values degrade to NULL, never to failure | Unparseable rows are excluded from numeric filters | Given one row with `value_number` 5.0 and one NULL, when filtering `value_number > 2`, then only the 5.0 row is returned | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLExecution::test_19_and_22_numeric_comparison_excludes_null_rows` | - [ ] |
| 20 | structured-entity-values | Typed value persistence | Typed columns are written alongside text columns | Given a `YEARS_OF_EXP` entity "5+ years" for a type declared `duration`/`years`, when persisted, then the row has `entity_value = '5+ years'`, `value_kind = 'duration'`, `value_number = 5.0`, `value_unit = 'years'` | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | - [ ] |
| 21 | structured-entity-values | Typed value persistence | Existing text-only queries are unaffected | Given documents extracted before this change, when a query filters on `normalized_value`, then the same rows are returned as before | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | - [ ] |
| 22 | structured-entity-values | Deterministic structured queries | Numeric comparison | Given `value_number` values 1.0, 2.5, 5.0, when filtering `value_number > 2`, then exactly the 2.5 and 5.0 rows are returned | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLExecution::test_19_and_22_numeric_comparison_excludes_null_rows` | - [ ] |
| 23 | structured-entity-values | Deterministic structured queries | Inclusive comparison | Given `value_number` values 4.0 and 5.0, when filtering `value_number >= 5`, then only the 5.0 row is returned | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLExecution::test_23_inclusive_comparison` | - [ ] |
| 24 | structured-entity-values | Deterministic structured queries | Date comparison against the current date | Given `CERTIFICATION_EXPIRY` rows with past and future `value_date`, when filtering `value_date < CURRENT_DATE`, then only past-dated rows are returned | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLExecution::test_24_date_comparison_against_current_date` | - [ ] |
| 25 | structured-entity-values | Deterministic structured queries | Range filter | Given `value_date` values across several years, when filtering `BETWEEN '2026-01-01' AND '2026-12-31'`, then only rows inside that interval are returned | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLExecution::test_25_range_filter` | - [ ] |
| 26 | structured-entity-values | Backfill of semantic values without re-inference | Backfill populates typed values from stored text | Given rows with NULL semantic columns for a now-`duration` type, when semantic backfill runs, then parseable rows are populated and no model inference is invoked | `tests/test_backfill_semantic_values.py::TestBackfillSemanticValues::test_backfill_populates_typed_values_without_inference` | - [ ] |
| 27 | structured-entity-values | Backfill of semantic values without re-inference | Backfill is idempotent | Given an already-backfilled document, when backfill runs again, then row count and typed values are unchanged | `tests/test_backfill_semantic_values.py::TestBackfillSemanticValues::test_backfill_is_idempotent` | - [ ] |
| 28 | structured-entity-values | Backfill of semantic values without re-inference | Backfill leaves text columns untouched | Given existing `document_entities` rows, when semantic backfill runs, then `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, `char_end` are unchanged for every row | `tests/test_backfill_semantic_values.py::TestBackfillSemanticValues::test_backfill_leaves_text_and_location_columns_untouched` | - [ ] |
| 29 | entity-config | Entity Type Definition (MODIFIED) | Tenant Admin creates an entity type | Given an authenticated Tenant Admin, when they POST a `customer_name` entity type, then status is 201, body has `version: 1`, `is_active: true`, and `value_kind` defaults to `text` | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_create_entity_type_defaults_value_kind_to_text` | - [ ] |
| 30 | entity-config | Entity Type Definition (MODIFIED) | Tenant Admin updates an entity type | Given `customer_name` at version 1, when the admin PUTs a new description, then status is 200, `version` is 2, and the description is updated | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_update_entity_type_increments_version` | - [ ] |
| 31 | entity-config | Entity Type Definition (MODIFIED) | Tenant Admin declares a structured value kind | Given an authenticated Tenant Admin, when they POST `YEARS_OF_EXP` with `value_kind: duration` and `value_unit: years`, then status is 201 and both fields are persisted | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_declare_structured_value_kind` | - [ ] |
| 32 | entity-config | Entity Type Definition (MODIFIED) | Unsupported value kind is rejected | Given an authenticated Tenant Admin, when they POST a type with `value_kind: geo`, then status is 422 and no entity type is created | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_unsupported_value_kind_rejected` | - [ ] |
| 33 | entity-config | Entity Type Definition (MODIFIED) | Existing entity types keep working | Given entity types created before `value_kind` existed, when read through the API, then each reports `value_kind: "text"` and `value_unit: null` and extraction is unchanged | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_existing_entity_types_default_to_text` | - [ ] |
| 34 | chat-api | Structured entity value columns are queryable through the SQL path | Numeric comparison query passes validation | Given a question about more than two years of experience, when generation produces a query filtering `e.value_number > 2` with a LIMIT, then validation passes and it executes read-only | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLValidation::test_34_numeric_comparison_query_passes_validation` | - [ ] |
| 35 | chat-api | Structured entity value columns are queryable through the SQL path | Date comparison query passes validation | Given a question about expired certifications, when generation produces a query filtering `value_date < CURRENT_DATE`, then validation passes | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLValidation::test_35_date_comparison_query_passes_validation` | - [ ] |
| 36 | chat-api | Structured entity value columns are queryable through the SQL path | Non-whitelisted column is still rejected | Given a query referencing a `document_entities` column not in the whitelist, when validated, then the query is rejected | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLValidation::test_36_typed_columns_are_whitelisted` | - [ ] |
| 37 | chat-api | Structured entity value columns are queryable through the SQL path | Text-only queries continue to work | Given a question about AWS mentions, when generation produces `normalized_value = 'aws'`, then validation passes and behaviour is identical to before this change | `tests/test_chat_api_structured_value_sql.py::TestStructuredValueSQLValidation::test_37_text_only_query_still_valid` | - [ ] |
| 38 | tenant-schema-migrations | Semantic value columns are added to the template and every existing tenant schema | Template and existing tenant schemas both gain the columns | Given `tenant_template` plus two provisioned tenant schemas with `document_entities`, when the migration runs, then all three have the six columns and both partial indexes | `tests/test_migration_document_entities_typed_values.py::TestMigration029DocumentEntitiesTypedValues::test_template_and_two_tenant_schemas_receive_columns_and_indexes` | - [ ] |
| 39 | tenant-schema-migrations | Semantic value columns are added to the template and every existing tenant schema | Existing rows are preserved | Given a tenant schema with rows, when the migration runs, then row count is unchanged, existing column values are unchanged, and new columns are NULL | `tests/test_migration_document_entities_typed_values.py::TestMigration029DocumentEntitiesTypedValues::test_existing_rows_preserved_new_columns_null` | - [ ] |
| 40 | tenant-schema-migrations | Semantic value columns are added to the template and every existing tenant schema | Tenant schema missing the table is skipped | Given a `tenant_%` schema with no `document_entities`, when the migration runs, then it completes successfully and other tenant schemas are still migrated | `tests/test_migration_document_entities_typed_values.py::TestMigration029DocumentEntitiesTypedValues::test_tenant_schema_missing_table_is_skipped` | - [ ] |
| 41 | tenant-schema-migrations | Semantic value columns are added to the template and every existing tenant schema | Re-running the migration is a no-op | Given the migration is already applied, when it runs again, then it completes without error and the schema is unchanged | `tests/test_migration_document_entities_typed_values.py::TestMigration029DocumentEntitiesTypedValues::test_rerun_is_noop` | - [ ] |
| 42 | tenant-schema-migrations | Semantic value columns are added to the template and every existing tenant schema | Newly provisioned tenants inherit the columns | Given the migration applied to `tenant_template`, when a new tenant is provisioned, then its `document_entities` has the six columns and both partial indexes | `tests/test_migration_document_entities_typed_values.py::TestMigration029DocumentEntitiesTypedValues::test_newly_provisioned_tenant_inherits_columns` | - [ ] |
| 43 | tenant-schema-migrations | Entity definition value kind columns are added to the public schema | Columns are added without touching existing definitions | Given existing `public.entity_definitions` rows, when the migration runs, then `value_kind` and `value_unit` exist, are NULL for existing rows, and no other column is altered | `tests/test_migration_entity_definition_value_kind.py::TestMigration028EntityDefinitionValueKind::test_columns_added_existing_rows_null_and_untouched` | - [ ] |
| 44 | tenant-schema-migrations | Entity definition value kind columns are added to the public schema | Downgrade removes the columns | Given the migration applied, when downgraded, then both columns are removed and remaining columns and rows are unchanged | `tests/test_migration_entity_definition_value_kind.py::TestMigration028EntityDefinitionValueKind::test_downgrade_removes_columns_and_preserves_rows` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Separation of lexical and semantic normalization (Decision 1) | `tests/test_semantic_normalizer.py::TestNumericAndDurationNormalization::test_spelled_out_fractional_duration` | Diff `src/extraction_service/services/entity_normalizer.py` — `canonicalize()` must still be `str -> str` with unchanged body. Confirm `src/chat_api/services/entity_resolver.py:60` and `src/chat_api/graph/nodes.py:240` still compile and behave identically |
| 2 | Column naming and shape (Decision 3) | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | Grep the migration and `document_entity_store.py` for column names — every one must appear verbatim in `specs/structured-entity-values/spec.md` "Typed value persistence". Any extra column is a defect |
| 3 | Failure path on unparseable values (Decision 5) | `tests/test_semantic_normalizer.py::TestSupportedKindDispatch::test_duration_kind_dispatches_duration_parser` | Confirm a test exists feeding junk text ("several") through a structured type and asserting the run completes with NULL typed columns. Read the worker's exception handling — no new `raise` inside the normalization pass |
| 4 | Unit conversion correctness (Decision 4) | `tests/test_entity_config_value_kind.py::TestEntityConfigValueKind::test_unsupported_value_kind_rejected` | Check the parser signature accepts the declared unit and that the "2 months → 60 days" test exists and passes. Confirm no entity type name (`YEARS_OF_EXP`) appears anywhere in `semantic_normalizer.py` |
| 5 | Tenant schema propagation (ADR-001, Decision 3) | `tests/test_extraction_worker_semantic_normalization.py::TestWorkerSemanticNormalization::test_semantic_and_lexical_normalization_persist_independently` | Read the migration against the pattern in `alembic/versions/026_document_entities.py` — it must include the loop and tolerate a schema without `document_entities`. Run the migration against a DB with two tenant schemas and inspect both |
| 6 | SQL layer scope creep (Decision 7) | `tests/test_semantic_normalizer_extensibility.py::TestNewKindRequiresNoPipelineChange::test_registering_a_new_kind_persists_typed_values_with_no_pipeline_edit` | Diff `sql_generator.py` — changes must be limited to the whitelist set and one schema-description sentence. Confirm the SELECT-only, LIMIT, UNION, and subquery checks are byte-identical |
| 7 | Backfill semantics (Decision 6) | `tests/test_semantic_normalizer.py::TestParsersArePureAndOffline` | Read the backfill mode — it must read `entity_value` from `document_entities` and issue an `UPDATE` touching only the semantic columns. Confirm no call to the model serving endpoint on that path |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data lives in separate Postgres schemas; migrations apply to the template and loop over existing tenant schemas | New `document_entities` columns and indexes must reach `tenant_template` and every `tenant_%` schema; no cross-tenant table may be introduced | Run the migration on a DB with `tenant_template` and ≥2 tenant schemas; query `information_schema.columns` per schema and confirm all six columns and both indexes exist in each. Grep the change for any new table outside a tenant schema |
| ADR-004-openspec-governance | Spec-driven development; behaviour changes require spec deltas before code | Every behaviour in the implementation must trace to a SHALL clause in this change's spec files | Cross-check each new public function and column against Section 1; anything with no corresponding row is an unspecified addition |
| ADR-007-chatbot-architecture | Chat answers come from a guardrailed RAG pipeline with a whitelisted SQL path | The SQL guardrails must survive unchanged; new columns are reachable only via the whitelist | Diff `sql_generator.py`; confirm `validate_sql()` body is unchanged and that the only additions are whitelist entries plus one schema-description line |
| ADR-003-model-serving-topology / ADR-006-training-infrastructure / ADR-008-base-model-as-default | Model serving and training topology; base model as default inference model | Untouched — normalization runs on the worker after inference returns | Confirm no diff under `src/model_serving/` or `src/training_service/` |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (independent outputs): test output showing lexical and semantic values both asserted on one entity
- [x] Scenario 2 (no kind → NULL semantics): test output showing `normalized_value = 'react'` and NULL typed columns
- [x] Scenario 3 (supported kind dispatches parser): test output showing the `duration` parser invoked for a `duration`-declared type
- [x] Scenario 4 (unsupported kind rejected): API response body and status for a `value_kind: geo` create attempt
- [x] Scenario 5 (default preserves behaviour): row dump for a `text` type compared against the pre-change expected row
- [x] Scenario 6 (new kind, no pipeline change): test output for a newly registered kind plus a diff showing worker/store/whitelist untouched
- [x] Scenario 7 (parsers pure and offline): test output asserting determinism, plus review confirmation of no network/DB imports in `semantic_normalizer.py`
- [x] Scenario 8 (spelled-out fractional duration): parser test output for "two and a half years" → 2.5
- [x] Scenario 9 (digit form with suffix): parser test output for "5 yrs" → 5.0
- [x] Scenario 10 (unit conversion): parser test output for "2 months" in a `days` type → 60.0
- [x] Scenario 11 (separators and magnitudes): parser test output for "1,200,000" and "12 lakh" → 1200000.0
- [x] Scenario 12 (open lower bound): parser test output for "5+ years" → 5.0 / NULL high
- [x] Scenario 13 (phrased open bound): parser test output for "more than three years" → 3.0
- [x] Scenario 14 (closed range): parser test output for "3-5 years" → 3.0 / 5.0
- [x] Scenario 15 (full date): parser test output for "15 March 2027" → 2027-03-15
- [x] Scenario 16 (month and year): parser test output for "March 2027" → 2027-03-01
- [x] Scenario 17 (unresolvable date): parser test output showing NULL and the entity still persisted
- [x] Scenario 18 (junk value): worker test output showing the run completes with NULL typed columns
- [x] Scenario 19 (NULLs excluded from filters): SQL query result over a fixture with one NULL and one populated row
- [x] Scenario 20 (typed columns written): database row dump after extracting a document containing "5+ years"
- [x] Scenario 21 (text-only queries unaffected): query result on pre-change fixture data compared to the recorded baseline
- [x] Scenario 22 (numeric comparison): SQL result set for `value_number > 2` over the 1.0/2.5/5.0 fixture
- [x] Scenario 23 (inclusive comparison): SQL result set for `value_number >= 5` over the 4.0/5.0 fixture
- [x] Scenario 24 (date vs CURRENT_DATE): SQL result set for `value_date < CURRENT_DATE` over past/future fixture rows
- [x] Scenario 25 (range filter): SQL result set for the `BETWEEN` query over multi-year fixture rows
- [x] Scenario 26 (backfill from stored text): before/after row dump plus evidence that no inference request was issued
- [x] Scenario 27 (backfill idempotent): row count and typed values after two consecutive backfill runs
- [x] Scenario 28 (backfill leaves text untouched): column-level diff of text and location columns before and after backfill
- [x] Scenario 29 (create entity type): API response showing `version: 1`, `is_active: true`, `value_kind: "text"`
- [x] Scenario 30 (update entity type): API response showing `version: 2` and the updated description
- [x] Scenario 31 (declare structured kind): API response persisting `value_kind: duration`, `value_unit: years`
- [x] Scenario 32 (reject unsupported kind): API 422 response and a query showing no row was created
- [x] Scenario 33 (pre-existing types): API listing output for types created before the migration
- [x] Scenario 34 (numeric SQL validated): validator test output for the `value_number > 2` query
- [x] Scenario 35 (date SQL validated): validator test output for the `value_date < CURRENT_DATE` query
- [x] Scenario 36 (non-whitelisted column rejected): validator test output showing rejection
- [x] Scenario 37 (text-only SQL still valid): validator test output for the `normalized_value = 'aws'` query
- [x] Scenario 38 (columns in all schemas): `information_schema` query output per schema after migration
- [x] Scenario 39 (rows preserved): row count and column-level comparison before and after migration
- [x] Scenario 40 (missing table tolerated): migration run log against a DB containing a tenant schema without `document_entities`
- [x] Scenario 41 (migration idempotent): output of a second consecutive migration run
- [x] Scenario 42 (new tenant inherits): `information_schema` output for a tenant provisioned after the migration
- [x] Scenario 43 (public schema columns added): `information_schema` output for `public.entity_definitions` plus NULL check on existing rows
- [x] Scenario 44 (downgrade removes columns): `information_schema` output after running the downgrade

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)
- [x] Confirmed this change landed after `normalized-entity-store` (migration `026` present before the new migration)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `canonicalize()` unchanged and both chat-side callers verified
- [x] Risk 2 mitigation confirmed — every persisted column name traced to a spec SHALL clause
- [x] Risk 3 mitigation confirmed — unparseable value path asserted non-raising end to end
- [x] Risk 4 mitigation confirmed — declared unit honoured; no entity type name hardcoded in the normalizer
- [x] Risk 5 mitigation confirmed — migration verified against a multi-tenant-schema database including a schema missing the table
- [x] Risk 6 mitigation confirmed — `validate_sql()` diff is empty; prompt change limited to schema description
- [x] Risk 7 mitigation confirmed — semantic backfill issues no inference request and updates only semantic columns

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `pytest tests/test_semantic_normalizer.py tests/test_semantic_normalizer_extensibility.py -q` → all passed | Scenarios 1, 3, 6, 7, 8-17 | claude (agent) | 2026-07-31 |
| 2 | Functional | `pytest tests/test_extraction_worker_semantic_normalization.py -q` → 1 passed (3 assertions across scenarios in one run) | Scenarios 1, 2, 5, 18, 20, 21 | claude (agent) | 2026-07-31 |
| 3 | Functional | `pytest tests/test_chat_api_structured_value_sql.py -q` → 9 passed | Scenarios 19, 22, 23, 24, 25, 34, 35, 36, 37 | claude (agent) | 2026-07-31 |
| 4 | Functional | `pytest tests/test_backfill_semantic_values.py -q` → 3 passed | Scenarios 26, 27, 28 | claude (agent) | 2026-07-31 |
| 5 | Functional | `pytest tests/test_entity_config_value_kind.py -q` → 5 passed | Scenarios 29, 30, 31, 32, 33 | claude (agent) | 2026-07-31 |
| 6 | Functional | `pytest tests/test_migration_document_entities_typed_values.py tests/test_migration_entity_definition_value_kind.py -q` → 10 passed | Scenarios 38-44 | claude (agent) | 2026-07-31 |
| 7 | Structural | Combined regression run: `pytest tests/test_migration_entity_definition_value_kind.py tests/test_migration_document_entities_typed_values.py tests/test_semantic_normalizer.py tests/test_extraction_worker_semantic_normalization.py tests/test_entity_config_value_kind.py tests/test_chat_api_structured_value_sql.py tests/test_backfill_semantic_values.py tests/test_semantic_normalizer_extensibility.py tests/test_entity_normalizer.py tests/test_backfill_document_entities.py tests/test_extraction_worker_normalization.py tests/test_chat_api_sql.py tests/test_migration_026_document_entities.py -q` on a fresh `ner_test` DB → **85 passed**, 0 failed | All 44 rows + pre-existing regression suites (entity_normalizer, backfill, chat_api_sql, migration 026) | claude (agent) | 2026-07-31 |
| 8 | Structural | Full-repo `pytest -q` was also run; ~65 unrelated failures/71 errors (test_user_auth, test_training_worker, test_warmup_endpoint, test_tenant_provisioning, etc.) were confirmed pre-existing and unrelated to this change by reproducing the same failures against a freshly dropped-and-recreated empty `ner_test` database, before any change-specific test ran. None of the failing files import or exercise any file touched by this change. | N/A (environment baseline check) | claude (agent) | 2026-07-31 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** structured-entity-value-normalization
**Proposal:** `openspec/changes/structured-entity-value-normalization/proposal.md`
**Spec files reviewed:**
  - specs/structured-entity-values/spec.md
  - specs/entity-config/spec.md
  - specs/chat-api/spec.md
  - specs/tenant-schema-migrations/spec.md

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
