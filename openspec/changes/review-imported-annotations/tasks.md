## 1. Database Migration

- [ ] 1.1 Add Alembic migration adding `reviewed BOOLEAN NOT NULL DEFAULT FALSE`, `reviewed_at TIMESTAMPTZ NULL`, `reviewed_by VARCHAR NULL` to `imported_annotations`, following the multi-schema `DO $$ ... FOR schema_name IN ...` loop pattern from `alembic/versions/012_reconcile_training_jobs_columns.py`.
- [ ] 1.2 Apply the migration to `tenant_template` and confirm it also runs against existing `tenant_*` schemas in the local dev stack.

## 2. Backend: List Endpoint

- [ ] 2.1 Add `GET /api/v1/imported-annotations` in `src/annotation_service` — paginated, filterable by `source_file`, entity type, and `reviewed` state. Returns per-row summary (id, source_file, row_index, distinct entity types, reviewed).
- [ ] 2.2 Gate the endpoint to `annotator`/`tenant_admin` roles (403 for `business_user`), matching the existing import endpoint's role check.
- [ ] 2.3 Add `test_imported_annotations_list.py` covering: visibility for annotator/tenant_admin, 403 for business_user, pagination, source_file filter, entity type filter, reviewed-state filter.

## 3. Backend: Detail & Update Endpoints

- [ ] 3.1 Add `GET /api/v1/imported-annotations/{id}` returning full `tokens[]`/`tags[]` for one row.
- [ ] 3.2 Add `PATCH /api/v1/imported-annotations/{id}` accepting an updated `tags[]` array (or a set of span edits translated server-side into `tags[]`), reusing `get_known_entity_types_lower` from `import_.py` to validate entity types before persisting.
- [ ] 3.3 On successful `PATCH`, set `reviewed = true`, `reviewed_at = now()`, `reviewed_by = <current user>`.
- [ ] 3.4 Add a `POST /api/v1/imported-annotations/{id}/mark-reviewed` endpoint (or equivalent) for marking a row reviewed without changing `tags[]`.
- [ ] 3.5 Add `test_imported_annotations_update.py` covering: retype span, delete span, create span, reject unknown entity type (tags unchanged), reviewed set on save, reviewed set via explicit mark-reviewed with tags unchanged, and confirming no `documents`/`annotation_tasks`/`spans` rows are created as a side effect of any of the above.

## 4. Frontend: Imported Documents List View

- [ ] 4.1 Add a new "Imported Documents" list page/tab in `src/portal` fetching from `GET /api/v1/imported-annotations`, with pagination controls and filters for `source_file`, entity type, and reviewed state.
- [ ] 4.2 Gate visibility to `annotator`/`tenant_admin` roles, consistent with the existing Import button's role gate in `AnnotationPage.tsx`.

## 5. Frontend: Token-Level Review & Edit

- [ ] 5.1 Add a token-range edit reducer (parallel to `span-reducer.ts` but operating on token indices, not char offsets) with actions for load, retype span, delete span, create span from a token range.
- [ ] 5.2 Reuse `Token.tsx` for rendering; derive highlight state per token by converting `tags[]` into token-range spans (contiguous `B-X`/`I-X*` runs) and mapping through the reducer's current state.
- [ ] 5.3 Reuse the existing client-side entity-color computation (`buildEntityColors` pattern from `AnnotationPage.tsx`, backed by `useEntityTypes()`) so colors match the interactive workspace exactly.
- [ ] 5.4 Wire span creation (click/drag token-range selection + entity type assignment), retype (via an entity palette or inspector), and delete actions to `PATCH /api/v1/imported-annotations/{id}`, with unknown-entity-type rejections surfaced as inline errors.
- [ ] 5.5 Add a "Mark reviewed" action wired to the mark-reviewed endpoint for rows viewed but not edited.
- [ ] 5.6 Add `token-rendering.test.tsx` covering: O tokens render unselected, B/I run renders as a single colored span.

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log, including the manual color-parity screenshot for Scenario 8.
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [ ] 6.6 Run `openspec validate review-imported-annotations --type change --strict` before archive.
