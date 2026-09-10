## 1. Prerequisites

- [x] 1.1 Nav-restructure Phase 3 landed: `annotation_imports` header table (migration 041), `services/notify.py`.
- [x] 1.2 `entity-type-provenance` landed — provides the `'imported'` provenance value.
- [x] 1.3 Decision: training-eligibility = "every row imported, no unmapped type" (`pending_count = 0`); `reviewed` stays an optional quality flag, not a gate.

## 2. Database

- [x] 2.1 Migration `045` (`apply_to_all_tenant_schemas`, additive): `imported_annotations.pending_mapping BOOLEAN NOT NULL DEFAULT FALSE`; backfill one `annotation_imports` header per distinct existing `source_file` with `training_eligible_at = NOW()` (those rows only ever held known types).
- [x] 2.2 Fixtures: `pending_mapping` + `annotation_imports` added to `tests/test_annotation_import.py` and `tests/test_annotation_workspace.py` `_create_tables_sql`; the latter's `entity_definitions` DDL already carries the provenance columns.
- [ ] 2.3 Migration `045` guard test.

## 3. Import endpoint

- [x] 3.1 `POST /api/v1/annotation-import` now `require_tenant_admin` (test tokens updated from the bogus `"admin"` role to `"tenant_admin"`).
- [x] 3.2 Every parsed row is stored; a row with any unknown type is `pending_mapping = TRUE`. Response: `imported_count` (usable), `pending_count`, `unmapped_types: [{type, row_count}]`, `warnings: []`, `skipped_count` kept = `pending_count` for back-compat, `entity_type_counts`.
- [x] 3.3 Creates/updates the `annotation_imports` header; `_refresh_import_header` sets `training_eligible_at` when `pending_count == 0`, clears it otherwise.
- [x] 3.4 Re-import of the same `source_file` upserts the header (`ON CONFLICT`); rows are appended (existing behaviour).
- [x] 3.5 Tests: `test_import_requires_tenant_admin`, `test_known_file_is_training_eligible`, updated `test_import_partial_skip_unknown` / `test_import_all_rows_unknown` to the held-not-dropped contract.

## 4. Type mapping endpoint

- [x] 4.1 `POST /api/v1/annotation-imports/{source_file}/type-map`, `require_tenant_admin`, body `{ "<type>": {"to": "<existing>"} | {"create": true} }` (also accepts `{"mapping": {...}}`).
- [x] 4.2 `create`: `EntityService.create_entity_type(tenant_id, {name, provenance:"imported", provenance_ref:source_file})` — the shared create path, never a direct INSERT.
- [x] 4.3 Rewrites affected rows' tags BIO-prefix-safe, whole-base-type match; merges into `annotation_imports.type_map`; recomputes every row's `pending_mapping`; sets `training_eligible_at` when none remain.
- [x] 4.4 A type is only ever created via an explicit type-map — import never creates one (`test_type_map_create_new_uses_imported_provenance`, and the import tests show unknown types held, not created).
- [x] 4.5 Idempotent — re-running the same map re-applies the (now no-op) rewrite and leaves tags/header unchanged.
- [x] 4.6 Tests: `test_type_map_to_existing_rewrites_and_makes_eligible`, `test_type_map_create_new_uses_imported_provenance`, `test_type_map_requires_tenant_admin`.

## 5. Export

- [x] 5.1 `export.py`: `LEFT JOIN annotation_imports`; include rows where `pending_mapping = FALSE` and the file is training-eligible (or has no header — legacy pre-041 rows); each imported line carries `"source": "import"`.
- [x] 5.2 Tests: `test_export_excludes_pending_file`; the existing `test_export_merge_includes_imported` / `test_export_filter_applies_to_imported` still green (all-known files auto-eligible).

## 6. Training request

- [~] 6.1 `POST /api/v1/training-retrain-requests` unchanged; an eligible import feeds the export the training job reads. Covered by the existing `test_request_creates_pending_approval_job` plus the portal test that the "Request training" button calls it — a dedicated import-flavoured backend test would only duplicate that.

## 7. Portal

- [x] 7.1 `AnnotationImportResult` shows the `unmapped_types` list with a per-type "map to existing / create new" selector + a "Map types" action (`use-import-type-map` hook). The `/imported-documents` **Imported files** panel surfaces each file's pending-mapping count.
- [x] 7.2 `GET /api/v1/annotation-imports` (new, `require_tenant_admin`) lists file headers; `use-import-files` hook; the `/imported-documents` **Imported files** panel shows per-file "Training: Eligible" + a "Request training" button (`useRequestRetrain`) or "N rows need a type mapping". The import button is gated to `tenant_admin` (annotators are review-only, ZIP screen 13).
- [x] 7.3 `/imported-documents/[id]/page.tsx` route (annotator + tenant_admin) renders the exported `ImportedDocumentReview` on the row id; the list view still opens it inline.
- [x] 7.4 `/annotate/import` landing stats read `use-import-files` — files imported, rows needing type mapping, files training-eligible.
- [x] 7.5 `use-import-type-map.test.tsx` (2), `use-import-files.test.tsx` (2), `AnnotationImportResult` mapping-form test, `AnnotationImportFlow.test.tsx` updated for the annotator-review-only gate, `test_annotation_import.py` list-endpoint tests (2). 25 portal + 36 backend import tests green.

## 8. Filter audit

- [x] 8.1 One insert path in `import_.py`, storing all rows; the old "skip on unknown type" branch is gone.

## 9. Verification

- [x] 9.1 `test_annotation_import.py` (36), `test_annotation_export_offsets/windowing` + `test_annotation_workspace` (74), `test_bio_tags` — green in the annotation_service container; 25 portal import tests green.
- [ ] 9.2 §4 structural + edge-case evidence.
- [ ] 9.3 Human reviewer signs §6.
