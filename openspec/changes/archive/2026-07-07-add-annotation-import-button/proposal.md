## Why

The annotation service already exposes a `/api/v1/annotation-import` endpoint that accepts CoNLL and JSONL files, parses them into token/tag rows, and stages the data in the `imported_annotations` table — but there is no UI to trigger it. This forces users (annotators and tenant admins) to use curl or direct API calls, breaking the UX workflow from the portal. Adding an import button with file preview and upload feedback closes this gap and makes the platform self-contained.

## What Changes

- Add an "Import" button in the Task Queue header of the annotation page, visible to `annotator` and `tenant_admin` roles.
- On click, open a native file picker accepting `.txt` (CoNLL), `.json`, and `.jsonl` files.
- Client-side pre-parsing shows a preview slide-over with entity type breakdown and any unknown type warnings before uploading.
- On user confirmation, POST the file to `/api/v1/annotation-import`.
- Show a result slide-over with imported count, skipped rows, and entity type summary.
- Support partial import: rows with unknown entity types are skipped with per-row warnings, valid rows are imported.

## Capabilities

### New Capabilities

- `annotation-import-ui`: Frontend UI for importing annotation files (CoNLL/JSONL) — upload button, client-side file preview, upload feedback, partial import with warnings. Backend changes to support partial import with per-row warning reporting.

### Modified Capabilities

*(None — the existing `annotation-workspace` spec requirements are unchanged.)*

## Impact

- **Frontend** (`src/portal/`): New components for the import button, preview slide-over, and result slide-over. New hook for client-side CoNLL/JSONL parsing. Minor addition to the annotation page layout.
- **Annotation Service** (`src/annotation_service/`): The existing import endpoint needs modification to return entity type breakdown and support partial import (skip unknown entity type rows instead of rejecting the whole file).
- **No API contract breakage**: The import endpoint's interface changes (richer response) but remains backward-compatible for existing callers.
- **No new dependencies**: Client-side parsing uses built-in APIs; no additional npm packages.
- **Roles**: `annotator` and `tenant_admin` gain import capability; `business_user` and `system_admin` see no change.

## Open Questions

- Should the import accept `.txt` extension ambiguity (CoNLL vs plain text)? Current backend treats any non-`.json`/`.jsonl` as CoNLL. This is fine for MVP.
- Maximum file size: 50MB (already enforced by backend). Should frontend also enforce this pre-upload? Worth a client-side guard for UX.
- Should the backend endpoint's response schema change to include entity type breakdown, or should the frontend use the pre-parsed data for the summary and only use the backend response for `imported_count`? The pre-parse client-side approach (discussed) means the frontend already has the breakdown — the backend mainly needs to return per-row warnings for partial import scenarios.
