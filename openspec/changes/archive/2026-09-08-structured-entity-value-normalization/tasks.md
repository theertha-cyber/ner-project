> **Mandatory infrastructure:** groups 1–7. These are the smallest set that makes deterministic structured queries work end to end.
> **Optional future enhancements:** group 9. Not required for this change to be complete; listed so they are not re-derived later.
> **Ordering prerequisite:** migration `026_document_entities.py` (change `normalized-entity-store`) must be applied before group 1.

## 1. Schema — value kind configuration (mandatory)

- [x] 1.1 Add nullable `value_kind VARCHAR(32)` and `value_unit VARCHAR(32)` to `public.entity_definitions` in a new Alembic migration; no backfill, NULL means `text`.
- [x] 1.2 Add `value_kind` and `value_unit` to `EntityDefinition` in `src/gateway/models/__init__.py`.
- [x] 1.3 Write `tests/test_migration_entity_definition_value_kind.py` covering scenarios 43 (columns added, existing rows NULL, no other column altered) and 44 (downgrade removes both columns).

## 2. Schema — typed value columns on `document_entities` (mandatory)

- [x] 2.1 Add a new Alembic migration adding nullable `value_kind TEXT`, `value_number DOUBLE PRECISION`, `value_number_high DOUBLE PRECISION`, `value_unit TEXT`, `value_date DATE`, `value_date_high DATE` to `tenant_template.document_entities`.
- [x] 2.2 Extend the same migration with the `pg_namespace` loop over `tenant\_%` schemas (pattern from `alembic/versions/026_document_entities.py`), guarded so a schema without `document_entities` is skipped rather than failing.
- [x] 2.3 Add partial indexes `(entity_type, value_number) WHERE value_number IS NOT NULL` and `(entity_type, value_date) WHERE value_date IS NOT NULL` in both the template and the per-schema loop.
- [x] 2.4 Implement `downgrade()` dropping the six columns and both indexes across template and tenant schemas.
- [x] 2.5 Write `tests/test_migration_document_entities_typed_values.py` covering scenarios 38 (template + two tenant schemas), 39 (rows preserved, new columns NULL), 40 (missing table skipped), 41 (idempotent re-run), 42 (newly provisioned tenant inherits).

## 3. Semantic normalizer module (mandatory)

- [x] 3.1 Create `src/extraction_service/services/semantic_normalizer.py` with a `StructuredValue` dataclass (`value_kind`, `number`, `number_high`, `unit`, `date`, `date_high`) and `SUPPORTED_KINDS = {"text", "number", "duration", "money", "date", "boolean"}`.
- [x] 3.2 Define the parser contract `Parser = Callable[[str, str | None], StructuredValue | None]` and the `PARSERS: dict[str, Parser]` registry, plus `normalize_value(text, kind, unit)` dispatching through it and returning `None` for `text`/unknown-kind/unparseable.
- [x] 3.3 Implement the shared numeric token reader: spelled-out numerals including fractional phrasing ("two and a half"), decimals, thousands separators, and magnitude suffixes ("k", "lakh", "crore", "million").
- [x] 3.4 Implement bound and range detection: open lower bound (`5+`, "more than three", "at least 5") sets `number` only; closed range (`3-5`, "3 to 5") sets `number` and `number_high`.
- [x] 3.5 Implement the `number` and `money` parsers on top of 3.3/3.4; `money` sets `unit` from the declared canonical unit and performs no FX conversion.
- [x] 3.6 Implement the `duration` parser with source-unit detection (`yrs`, `years`, `months`, `mos`, `days`, `weeks`) and conversion into the declared canonical unit.
- [x] 3.7 Implement the `date` parser: full dates and month-year forms resolving to the first of the month; ambiguous or relative text ("next spring") returns `None`.
- [x] 3.8 Implement the `boolean` parser (affirmative/negative surface forms) mapping onto `number` 1.0/0.0 with `value_kind = 'boolean'`.
- [x] 3.9 Confirm by review and test that no parser imports a network, database, or LLM client, and that no entity type name appears anywhere in the module.
- [x] 3.10 Write `tests/test_semantic_normalizer.py` covering scenarios 3, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17.

## 4. Wire normalization into the extraction pipeline (mandatory)

- [x] 4.1 Extend `NormalizedEntity` in `src/extraction_service/services/entity_normalizer.py` with the six nullable semantic fields, defaulting to `None`. Do not otherwise modify the module — `canonicalize()` must remain `str -> str` with an unchanged body.
- [x] 4.2 Add a tenant entity-type-config loader that reads `name`, `value_kind`, `value_unit` from `public.entity_definitions` for the tenant, keyed case-insensitively by entity type name.
- [x] 4.3 Add `apply_semantic_normalization(entities, type_config)` in `semantic_normalizer.py`, returning entities with typed fields populated and counting entities whose declared kind was non-`text` but yielded no typed value.
- [x] 4.4 Call the loader and `apply_semantic_normalization()` in `src/extraction_service/worker.py` between `reconstruct_entities()` (line 208) and `insert_document_entities()` (line 227), inside the existing transaction; log the unparseable count in the run report.
- [x] 4.5 Extend `insert_document_entities()` in `src/extraction_service/services/document_entity_store.py` to write the six new columns.
- [x] 4.6 Verify no `raise` is introduced on the normalization path — a parse failure must not fail the document or the run.
- [x] 4.7 Write `tests/test_extraction_worker_semantic_normalization.py` covering scenarios 1, 2, 5, 18, 20, 21.

## 5. Entity type configuration API (mandatory)

- [x] 5.1 Accept and persist `value_kind` and `value_unit` in `src/gateway/services/entity_service.py` create, update, and read paths; expose both in the entity types API response with `value_kind` defaulting to `text` when NULL.
- [x] 5.2 Validate `value_kind` against `SUPPORTED_KINDS` on create and update, returning 422 for an unsupported kind and creating nothing.
- [x] 5.3 Write `tests/test_entity_config_value_kind.py` covering scenarios 29, 30, 31, 32, 33.

## 6. SQL query layer (mandatory)

- [x] 6.1 Add `value_kind`, `value_number`, `value_number_high`, `value_unit`, `value_date`, `value_date_high` to `WHITELISTED_TABLES["document_entities"]` in `src/chat_api/services/sql_generator.py`.
- [x] 6.2 Add one sentence to the schema description stating that comparison and range predicates use `value_number` / `value_date` (with `CURRENT_DATE` for "today") and equality on entity text uses `normalized_value`. Make no other prompt change.
- [x] 6.3 Confirm `validate_sql()` is byte-identical to its pre-change form — SELECT-only, LIMIT, UNION, subquery, and table checks untouched.
- [x] 6.4 Write `tests/test_chat_api_structured_value_sql.py` covering scenarios 19, 22, 23, 24, 25, 34, 35, 36, 37.

## 7. Backfill (mandatory)

- [x] 7.1 Add a semantic-only mode to `scripts/backfill_document_entities.py` that reads existing `document_entities` rows, applies `apply_semantic_normalization()` to `entity_value`, and `UPDATE`s only the six semantic columns.
- [x] 7.2 Confirm the semantic mode issues no request to the model serving endpoint and never writes `entity_value`, `normalized_value`, `confidence`, `page_number`, `char_start`, or `char_end`.
- [x] 7.3 Make the mode idempotent per document and re-runnable after a parser fix.
- [x] 7.4 Write `tests/test_backfill_semantic_values.py` covering scenarios 26, 27, 28.

## 8. Extensibility check (mandatory)

- [x] 8.1 Add a throwaway test that registers a new parser for a new kind, configures a type with it, runs extraction, and asserts typed values persist — with no edit to `worker.py`, `document_entity_store.py`, the migrations, or the SQL whitelist. Covers scenario 6.
- [x] 8.2 Fill in the Verification Artifact column in `verification.md` § Spec Alignment for all 44 rows with the test file and test name that satisfies each.

## 9. Optional future enhancements (not required for this change)

- [ ] 9.1 Re-normalize stored rows automatically when an entity type's `value_kind` or `value_unit` changes, instead of requiring a manual backfill run.
- [ ] 9.2 Surface the normalized typed value in the annotation review UI alongside the raw span.
- [ ] 9.3 Add deterministic query templates for common comparison shapes so the SQL path can bypass LLM generation entirely for those questions.
- [ ] 9.4 Per-row currency override and FX-aware money comparison.
- [ ] 9.5 A JSONB overflow column for a future value kind whose shape does not fit the current typed columns (e.g. geospatial).
- [ ] 9.6 Adopt a third-party parsing library inside individual parsers where hand-rolled coverage proves insufficient.

## 10. Verification & Evidence

- [x] 10.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. (85 tests passed on a fresh `ner_test` database — see Evidence Log rows 1-7.)
- [x] 10.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 10.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 10.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 10.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 10.6 Run `openspec validate structured-entity-value-normalization --type change --strict` and confirm it exits clean before archive.
