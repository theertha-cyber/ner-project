## 1. Prerequisites

- [x] 1.1 `src/gateway/services/entity_service.py` is the single writer of `public.entity_definitions`; schema-proposal approval already routes through it.

## 2. Database

- [x] 2.1 Migration `044`: `ALTER TABLE public.entity_definitions ADD COLUMN provenance VARCHAR(16) NOT NULL DEFAULT 'manual', ADD COLUMN provenance_ref VARCHAR(255)`. Additive; existing rows take the default.
- [x] 2.2 Added the two columns to the `entity_definitions` DDL in `scripts/setup_test_db.py` (and its RECONCILE `ALTER ... ADD COLUMN IF NOT EXISTS`), `tests/seed_bootstrap_support.py`, and `tests/test_annotation_workspace.py`.
- [ ] 2.3 Migration guard `tests/test_migration_044_*.py`.

## 3. Model + service

- [x] 3.1 `EntityDefinition` gains `provenance` (`server_default="manual"`, `nullable=False`) and `provenance_ref` (nullable).
- [x] 3.2 `_ENTITY_COLUMNS` += `provenance, provenance_ref`; `create_entity_type` reads `payload["provenance"]` (validated against `{manual, suggested, imported}`, else `manual`) plus `provenance_ref`, names them in the insert; `_row_to_dict` returns both.
- [x] 3.3 `update_entity_type` never writes `provenance` — confirmed by `test_provenance_immutable_on_update`.
- [x] 3.4 `EntityTypeCreate` has no `provenance` field (pydantic drops extras) so a client value never reaches the service; list / flat create / flat update responses carry `provenance` + `provenance_ref` via `_row_to_dict`.

## 4. Creation-path wiring

- [x] 4.1 `seed_bootstrap.approve_candidate` passes `provenance="suggested"` to `EntityService.create_entity_type`.
- [~] 4.2 The import type-map "create new" branch passes `provenance="imported"` — delivered by `import-annotation-training-eligibility`.

## 5. Portal

- [x] 5.1 `EntityType` gains `provenance` + `provenance_ref`.
- [x] 5.2 `EntityTypeCard` renders the provenance chip beside the version label (`manual`, or `suggested · {ref}` / `imported · {ref}` when a ref is set).
- [x] 5.3 `EntityTypeCard.test.tsx`: +2 chip scenarios.

## 6. Tests

- [~] 6.1 `tests/test_entity_type_provenance.py` (new, 4 tests) exercises `EntityService` directly — manual default, arbitrary string ignored, suggested/imported persist, immutable on update. (The HTTP `test_entity_config.py` scenarios 14–19 use a live-tenant-provisioning fixture the container test-DB doesn't build; its other 39 tests pass.)
- [x] 6.2 `tests/test_seed_bootstrap_proposal.py::test_approved_candidate_is_suggested_provenance`.
- [~] 6.3 List/read path covered by `test_suggested_and_imported_provenance_persist` (round-trips through `_row_to_dict`).
- [x] 6.4 Portal `EntityTypeCard` suite green (14).

## 7. Verification

- [x] 7.1 Ran `test_entity_type_provenance.py` (4), `test_seed_bootstrap_proposal.py` (13), portal `EntityTypeCard` (14) — all green; recorded in verification.md §7.
- [ ] 7.2 Complete §4 structural + edge-case evidence.
- [ ] 7.3 Human reviewer signs §6.
