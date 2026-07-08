## Why

Bulk-imported annotations (`{tenant_schema}.imported_annotations`) are write-only today: a file is parsed, rows are validated and stored, and the only way they resurface is through `annotation-export`. No one can see what was actually imported, confirm the BIO tags are correct, or fix them before the data gets used (e.g. for training). Annotators need a way to review imported rows document-by-document, see every token with its label applied, and correct entity types or spans — without disturbing the interactive annotation workspace or the existing "import is staging-only" guarantee.

## What Changes

- Add a new "Imported Documents" review surface: a paginated, document-wise list of `imported_annotations` rows (filterable by `source_file` and entity type), where each row opens into a token-level editor.
- In the editor, every token from the row is rendered; tokens tagged `O` render unselected/plain, and contiguous `B-<TYPE>`/`I-<TYPE>` token runs render as a single selected span colored by that entity type (reusing the existing client-side entity-color scheme).
- Annotators can retype a span's entity type, delete a span (tokens revert to `O`), or select a new token range and assign it an entity type — validated against the tenant's configured entity types, same as import-time validation.
- Edits are saved back onto the row's own `tags` array (no new storage shape) plus a new reviewed marker.
- Add a `reviewed` status field (and `reviewed_at`/`reviewed_by`) to `imported_annotations` so progress across a large batch is trackable.
- **Not changed**: `imported_annotations` rows are still never converted into `documents`, `annotation_tasks`, or `spans`. The existing `annotation-import-ui` requirement that "import does not create annotation tasks" continues to hold — this change adds a way to view/edit staged rows in place, it does not graduate them into the interactive workspace pipeline.

## Capabilities

### New Capabilities

- `annotation-import-review`: Document-wise browsing and token-level editing of bulk-imported annotation rows, independent of the interactive annotation workspace.

### Modified Capabilities

(none — `annotation-import-ui` behavior is unchanged; this is purely additive on top of the same `imported_annotations` table)

## Impact

- **Database**: new migration adding `reviewed` (bool or status text), `reviewed_at`, `reviewed_by` columns to `imported_annotations` in `tenant_template` and all existing `tenant_*` schemas (following the pattern in `alembic/versions/012_reconcile_training_jobs_columns.py`).
- **Backend** (`src/annotation_service`): new endpoints — list imported rows (paginated, filtered by `source_file`/entity type/reviewed state) and update a row's `tags` + reviewed status. Reuses existing entity-type validation (`get_known_entity_types_lower`) from `import_.py`.
- **Frontend** (`src/portal`): new list page/tab for browsing imported rows, and a new token-range edit reducer (parallel to, not reusing, `span-reducer.ts`, since this operates on token indices rather than character offsets). Reuses `Token.tsx` for rendering and the existing client-side entity-color computation (`buildEntityColors` pattern from `AnnotationPage.tsx`).
- **Not affected**: `documents`, `annotation_tasks`, `spans` tables and the interactive annotation workspace (`AnnotationPage.tsx`, `span-reducer.ts`) — untouched.
- **Permissions**: same role gate as import itself — visible to `annotator` and `tenant_admin`, not `business_user`.

## Open Questions

- Exact filter set on the list view beyond `source_file`/entity type (e.g. reviewed-state filter) — left to design.md to finalize alongside the list endpoint's query params.
- Whether `reviewed` is a simple boolean or a richer status (e.g. to allow "flagged for follow-up") — design.md will pick the minimal shape that satisfies progress-tracking without over-engineering.
