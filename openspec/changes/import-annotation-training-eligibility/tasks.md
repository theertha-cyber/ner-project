## 1. Prerequisites

- [ ] 1.1 Confirm nav-restructure Phase 3 landed: `annotation_imports` header table (migration 041), `src/annotation_service/services/notify.py`.
- [ ] 1.2 Confirm the `entity-type-provenance` change has landed (provides `provenance` on `entity_definitions` and the `'imported'` value).
- [ ] 1.3 Decide: does training-eligibility require `reviewed = true` per row, or only "all types mapped"? Assume the latter; record.

## 2. Database

- [ ] 2.1 Migration `043` (`apply_to_all_tenant_schemas`, additive): `imported_annotations.pending_mapping BOOLEAN NOT NULL DEFAULT FALSE`; ensure `annotation_imports` exists (idempotent with 041); backfill one `annotation_imports` header per existing distinct `source_file` with `training_eligible_at = NOW()`.
- [ ] 2.2 Update `scripts/setup_test_db.py` and the import test fixtures (`tests/test_annotation_import.py`, `tests/test_imported_annotations_*`, `tests/test_annotation_workspace.py`) with the new column and header table.
- [ ] 2.3 Migration guard test `tests/test_migration_043_*.py`.

## 3. Import endpoint

- [ ] 3.1 Apply `require_tenant_admin` to `POST /api/v1/annotation-import` (`_rbac.py`). Update existing tests that import as annotator to use a tenant_admin token. (Spec row 13)
- [ ] 3.2 Store every parsed row; set `pending_mapping = true` for rows with any unknown type; return `imported_count` (usable), `pending_count`, `unmapped_types: [{type, row_count}]`, keep `warnings` for unparseable rows and `entity_type_counts`. (Spec rows 1, 10, 11, 12)
- [ ] 3.3 Create/update the `annotation_imports` header for the file; set `training_eligible_at` when `pending_count = 0`. (Spec row 2)
- [ ] 3.4 Idempotent re-import of the same `source_file`: no duplicate rows, one header. (Risk 7)
- [ ] 3.5 Tests in `tests/test_annotation_import.py`: `test_unmapped_types_held_not_dropped`, `test_known_file_is_eligible`, `test_imported_count_backward_compatible`, `test_backend_holds_unknown_type_rows`, `test_entity_type_counts`, `test_import_requires_tenant_admin`. (Spec rows 1, 2, 10–13)

## 4. Type mapping endpoint

- [ ] 4.1 `POST /api/v1/annotation-imports/{source_file}/type-map`, `require_tenant_admin`, body maps each unmapped type → `{to: "<existing name>"}` or `{create: true}`. (Spec rows 3, 6)
- [ ] 4.2 "create": call the shared entity-config creation path with `provenance = 'imported'`; never INSERT `entity_definitions` directly. (Spec row 4, Risk 3)
- [ ] 4.3 Rewrite affected rows' tags (BIO-prefix-safe, whole-base-type match); record `{original: {to, created}}` on `annotation_imports.type_map`; recompute `pending_mapping`; set `training_eligible_at` when none remain. (Spec rows 3, 14; Risk 4)
- [ ] 4.4 Never create a type implicitly during import — only via an explicit type-map. (Spec row 5, Risk 2)
- [ ] 4.5 Idempotent re-map: second call with the same map leaves tags and header unchanged. (Risk 7)
- [ ] 4.6 Tests: `test_map_unknown_to_existing`, `test_map_unknown_creates_type`, `test_no_implicit_type_creation`, `test_type_map_requires_tenant_admin` (`tests/test_annotation_import.py`), `test_type_map_rewrite_preserves_bio` (`tests/test_bio_tags.py`). (Spec rows 3–6, 14)

## 5. Export

- [ ] 5.1 `src/annotation_service/api/v1/export.py`: include `imported_annotations` rows where `pending_mapping = false` and the file's `annotation_imports.training_eligible_at IS NOT NULL`, in the existing token/tag row shape, tagged `source: "import"`. (Spec rows 7, 8)
- [ ] 5.2 Tests in `tests/test_annotation_export_offsets.py`: `test_export_includes_eligible_imports`, `test_export_excludes_pending_import`. (Spec rows 7, 8)

## 6. Training request

- [ ] 6.1 Confirm `POST /api/v1/training-retrain-requests` needs no change — an eligible import contributes rows to the export the training job reads. Add `tests/test_retrain_request.py::test_request_training_from_import`. (Spec row 9)

## 7. Portal

- [ ] 7.1 `/imported-documents/page.tsx`: add an "Unmapped Types" tab listing each unmapped type with a per-type example row and a "Map types" dialog (map to existing / create new). Per the Page Content Spec wireframe (`09 Import Review`, `10 Uploaded Documents`).
- [ ] 7.2 Per-file training-eligibility indicator and a "Request training" action for eligible files → `POST /api/v1/training-retrain-requests`. No "review annotations" gate.
- [ ] 7.3 Add `/imported-documents/[id]/page.tsx` — single-row review, reusing `Token` / `EntityPalette` / span reducer from `components/annotation/`; "Mark Reviewed" advances to the next unreviewed row in the same file.
- [ ] 7.4 `/annotate/import` landing (Phase 2) — wire its stats to real counts (files imported, rows pending mapping, unmapped types) and its "Import file" action to the dialog.
- [ ] 7.5 Portal tests: extend `AnnotationImportPreview.test.tsx` / `imported-documents` tests for the mapping dialog, the eligibility indicator, and the single-row review route.

## 8. Filter audit

- [ ] 8.1 Grep `annotation_service` for any remaining "skip on unknown type" path in import; there must be exactly one insert path and it stores all rows.

## 9. Verification

- [ ] 9.1 Run `tests/test_annotation_import.py`, `tests/test_annotation_export_offsets.py`, `tests/test_bio_tags.py`, `tests/test_retrain_request.py`, and the portal `imported-documents` suite; record in verification.md §5 / §7.
- [ ] 9.2 Complete §4 structural + edge-case evidence.
- [ ] 9.3 Human reviewer signs §6.
