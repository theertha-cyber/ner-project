## 1. Database

- [x] 1.1 Migration `053_entity_type_sensitivity.py`: add `sensitivity TEXT NOT NULL DEFAULT
      'open'` to `public.entity_definitions` with a CHECK constraint restricting it to
      `('open', 'pattern', 'local_only')`
- [x] 1.2 Verified against a real `ner_dev` database (docker compose `postgres-test` +
      `db-init`): migration applies cleanly on top of 048, `\d public.entity_definitions` shows
      the column and `ck_entity_definitions_sensitivity` CHECK constraint, and all 51
      pre-existing rows backfilled to `sensitivity = 'open'` (`SELECT sensitivity, count(*) ...
      GROUP BY sensitivity`). `db-init`'s own `verify_schema` step also passed ("no drift
      detected").

## 2. Backend — entity-type API

- [x] 2.1 `EntityTypeCreate` / `EntityTypeUpdate` (`src/gateway/api/v1/entity_types.py`): add
      `sensitivity: Sensitivity | None = None`, validated (via `_validate_sensitivity` in
      `entity_service.py`) against the same three-value set as the CHECK constraint
- [x] 2.2 Reject a create/update where `sensitivity == "pattern"` and `validation_rule` is null or
      empty, with 422 and a message naming the requirement (`_validate_pattern_requires_
      validation_rule`, checked against the resolved value on update so it also catches a PUT
      that changes only one of the two fields)
- [x] 2.3 Entity-type read/list responses include `sensitivity` (`_ENTITY_COLUMNS`,
      `_row_to_dict`)
- [x] 2.4 `load_active_entity_config` / `load_active_entity_config_sync`
      (`src/shared/entity_config_version.py`) select `sensitivity` alongside the existing fields
      (added to `_SELECT_ACTIVE` and `normalize_entity_config`; deliberately left out of
      `CONFIG_FIELDS`, so the cache-key hash is unaffected until `automated-annotation-pii-masking`)
- [x] 2.5 (found during backend test verification, not in the original task list) The
      SQLAlchemy ORM model `EntityDefinition` (`src/gateway/models/__init__.py`) was missing a
      `sensitivity` column entirely — `entity_service.py`'s raw SQL referenced it, but nothing
      declared it for `Base.metadata.create_all`, so the pytest fixture database (built from the
      ORM model, not migrations) would 500 on every entity-type read. Added
      `sensitivity = Column(String(16), server_default="open", default="open", nullable=False)`,
      matching the existing `cardinality`/`provenance` pattern exactly.

## 3. Frontend — entity-types screen

- [x] 3.1 Create/edit form: sensitivity selector (`Open` / `Pattern` / `Local only`), defaulting to
      `Open` (`DefineEntityTypeSlideOver.tsx`)
- [x] 3.2 Selecting `Pattern` reveals a pattern (regex) input and requires it to be filled before
      submit; client-side validation mirrors the 422 the backend would return
- [x] 3.3 List/detail view displays each entity type's sensitivity (`EntityTypeCard.tsx`, pill
      shown for `pattern`/`local_only`, hidden for the unremarkable `open` default)

## 4. Verification & Evidence

- [x] 4.1 Ran every scenario: portal vitest (`DefineEntityTypeSlideOver.sensitivity.test.tsx`,
      9/9), `tsc --noEmit` (clean for every entity-type file touched), and — once Docker became
      available — a new backend suite (`tests/test_entity_config_sensitivity.py`, 8/8) against a
      real Postgres (`ner_test`), plus the pre-existing `test_entity_config_value_kind.py` and
      migration-guard suites confirmed unaffected (26/26). Migration `053` itself verified
      against a real `ner_dev`: column, CHECK constraint, and full 51/51-row backfill to `open`.
- [x] 4.2 Functional evidence collected — see verification.md § Evidence Log
- [x] 4.3 Hallucination Risk Register: risks 1, 3, 4, 6, 7 confirmed directly by the new backend
      tests (enum surface, validation scope, validation timing on update, backfill default, API
      backward compatibility); risk 2 (mutability) confirmed by
      `test_sensitivity_is_mutable_on_update`; risk 5 (downstream SELECT) confirmed by code
      reading `entity_config_version.py` and by the fact that `automated-annotation-pii-masking`'s
      own tests depend on it and pass
- [ ] 4.4 No constraining ADRs (§ 3) — nothing to confirm beyond absence of a new undocumented
      pattern; left unchecked pending human sign-off per the schema's own instruction
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record — requires a human
      reviewer, not the implementing agent
- [x] 4.6 Ran `openspec validate entity-sensitivity-classification --type change --strict` —
      passes
