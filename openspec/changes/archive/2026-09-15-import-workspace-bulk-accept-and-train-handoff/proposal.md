## Why

Three usability bugs surfaced today from a Tenant Admin's real import (`annotations (1).jsonl`,
1106 rows, all entity types unmapped):

1. Clicking through Import → "1. Import annotations" reopened the OS file picker every time
   `/imported-documents` remounted without the URL changing — notably after using the per-row
   Review screen's "← Back" button, since that screen swaps in via local component state and
   never touches the URL. The picker's auto-open was gated only on a `?import=1` query string
   that was never cleared after firing, so it kept firing on every later remount.
2. A file whose entity types aren't yet defined for the tenant — the common case for a first
   import — required opening and type-mapping unmapped types one row at a time before the file
   could become training-eligible. There was no way to say "these N unmapped types are all new"
   in one action, which is impractical for a 1106-row file.
3. The per-file "Request training" action for an eligible import went through the Manual/
   Automated workflow's human-gated retrain-request-and-approve path
   (`POST /api/v1/training-retrain-requests`), even though imported data already skips review
   entirely and the Import landing page's own "2. Train model" step already hands off straight
   to Models & Training (`/training-jobs?source=import`). The two surfaces disagreed about what
   "eligible, Tenant Admin decides to train" means for imported data.

## What Changes

- `GET /api/v1/annotation-imports` now returns each file's `unmapped_types` (type name + row
  count), computed the same way the import-time response already computes it.
- The `/imported-documents` file-summary list gets an "Accept all as new types" button on any
  file with pending rows. One click submits every currently-unmapped type as `{"create": true}`
  in a single `POST .../type-map` call — no per-type dropdown, no per-row review.
- Removed the `?import=1` auto-open-the-picker mechanic entirely. The file picker now opens only
  in direct response to clicking the page's own "Import file" button — never from navigation,
  and never from a component remount.
- The per-file "Request training" button is replaced with "Train model", which navigates to
  `/training-jobs?source=import` instead of calling the retrain-request endpoint — matching the
  Import landing page's own hand-off exactly. No System-Admin-approval request is created by
  the click itself; submitting the job remains an explicit, separate step on that screen.
- The Import landing page's "1. Import annotations" step now links to plain
  `/imported-documents` (the `?import=1` it used to carry no longer does anything, since the
  mechanic it triggered is gone).

## Capabilities

### Modified Capabilities

- `annotation-import-ui`: "Request Training From an Import" now hands off to Models & Training
  directly instead of the retrain-request-and-approve flow. A new "Bulk-Accept Unmapped Types"
  requirement covers the per-file bulk action and the `unmapped_types` field it depends on.
  "Import Deep Link" is removed — see below.
- `import-annotation-landing`: "Workflow Steps" step 1 now links to plain `/imported-documents`.

### Removed Requirements

- `annotation-import-ui` — "Import Deep Link": the `?import=1` auto-open mechanic is gone; the
  picker opens only on an explicit click.

## Impact

- Backend: [import_.py](src/annotation_service/api/v1/import_.py) — `list_import_files` computes
  and returns `unmapped_types`; added a `_unmapped_types_for_file` helper.
- Frontend: [ImportedDocuments.tsx](src/portal/src/components/imported-documents/ImportedDocuments.tsx)
  — removed the `?import=1` effect; added the bulk-accept button and handler; replaced the
  retrain-request button with a `router.push` hand-off.
- Frontend: [use-import-files.ts](src/portal/src/hooks/use-import-files.ts) — `ImportFile` type
  gains `unmapped_types`.
- Frontend: [use-import-type-map.ts](src/portal/src/hooks/use-import-type-map.ts) — the mutation
  now also invalidates the `import-files` query.
- Frontend: [annotate/import/page.tsx](src/portal/src/app/(auth)/annotate/import/page.tsx) — both
  `/imported-documents?import=1` hrefs (the "1. Import annotations" card and the header
  "+ Import file" primary action) now point at plain `/imported-documents`.
- Tests: [test_annotation_import.py](tests/test_annotation_import.py),
  [ImportedDocuments.test.tsx](src/portal/src/components/imported-documents/ImportedDocuments.test.tsx),
  [AnnotationImportFlow.test.tsx](src/portal/src/app/(auth)/imported-documents/AnnotationImportFlow.test.tsx),
  [annotate/import/page.test.tsx](src/portal/src/app/(auth)/annotate/import/page.test.tsx).
- No database migration — `unmapped_types` is computed from existing columns
  (`imported_annotations.pending_mapping`, `imported_annotations.tags`), not stored.
