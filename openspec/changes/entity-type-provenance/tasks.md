## 1. Prerequisites

- [ ] 1.1 Confirm `src/gateway/services/entity_service.py` is the single writer of `public.entity_definitions` (schema-proposal approval already routes through it).

## 2. Database

- [ ] 2.1 Migration `044`: `ALTER TABLE public.entity_definitions ADD COLUMN provenance VARCHAR(16) NOT NULL DEFAULT 'manual', ADD COLUMN provenance_ref VARCHAR(255)`. Additive; existing rows take the default.
- [ ] 2.2 Add `provenance` / `provenance_ref` to the `entity_definitions` DDL in `scripts/setup_test_db.py` and to the inline `entity_definitions` DDLs in `tests/test_annotation_workspace.py` and any other test that creates the table directly.
- [ ] 2.3 Migration guard `tests/test_migration_044_*.py`.

## 3. Model + service

- [ ] 3.1 `src/gateway/models/__init__.py`: add `provenance` (`server_default="manual"`, `nullable=False`) and `provenance_ref` (nullable) to `EntityDefinition`.
- [ ] 3.2 `entity_service.create`: accept optional `provenance` (default `"manual"`) and `provenance_ref`; name them in the explicit insert column list. Expose both on all read/serialise paths.
- [ ] 3.3 `entity_service.update`: confirm it does not carry `provenance` / `provenance_ref`. (Risk 3)
- [ ] 3.4 `src/gateway/api/v1/entity_types.py`: the `POST` request schema has no `provenance` field; the flat create/update responses and the list/single GET responses include `provenance` + `provenance_ref`. (Spec rows 5–7)

## 4. Creation-path wiring

- [ ] 4.1 `src/annotation_service/services/schema_proposal.py` (candidate approval): call the entity-type creation path with `provenance="suggested"` and `provenance_ref=<schema version label if available>`. (Spec row 2)
- [ ] 4.2 The import type-map "create new" branch (from `import-annotation-training-eligibility`): create with `provenance="imported"`, `provenance_ref=<source filename>`. (Spec row 3) — coordinate with that change.

## 5. Portal

- [ ] 5.1 `src/portal/src/types/entity-types.ts`: add `provenance: "manual" | "suggested" | "imported"` and `provenance_ref: string | null` to `EntityType`.
- [ ] 5.2 `src/portal/src/components/entity-types/EntityTypeCard.tsx`: render the provenance chip next to the version label — `manual` / `suggested` / `imported`, or `suggested · {ref}` / `imported · {ref}` when `provenance_ref` is set. (Spec rows 8–10)
- [ ] 5.3 `EntityTypeCard.test.tsx`: add the three chip scenarios; update the "all fields" fixture to include `provenance`.

## 6. Tests

- [ ] 6.1 `tests/test_entity_config.py`: `test_manual_create_provenance`, `test_provenance_immutable_on_update`, `test_create_response_includes_provenance`, `test_client_provenance_ignored`. (Spec rows 1, 4, 6, 7)
- [ ] 6.2 `tests/test_seed_bootstrap_proposal.py::test_approved_candidate_is_suggested_provenance`. (Spec row 2)
- [ ] 6.3 `tests/test_entity_type_view_metadata_api.py::test_list_includes_provenance`. (Spec row 5)
- [ ] 6.4 Portal `EntityTypeCard` suite. (Spec rows 8–10)

## 7. Verification

- [ ] 7.1 Run the entity-config, seed-bootstrap-proposal, entity-type-view-metadata suites + the portal entity-types suite; record in verification.md §5 / §7.
- [ ] 7.2 Complete §4 structural + edge-case evidence.
- [ ] 7.3 Human reviewer signs §6.
