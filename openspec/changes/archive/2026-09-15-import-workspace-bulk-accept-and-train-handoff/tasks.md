## 1. Backend

- [x] 1.1 Add `_unmapped_types_for_file` and include `unmapped_types` per file in
  `GET /api/v1/annotation-imports`.
- [x] 1.2 Add a regression test asserting `unmapped_types` for both a pending and a fully-mapped
  file.

## 2. Imported-files list — bulk accept + train hand-off

- [x] 2.1 Add the "Accept all as new types" button, wired to `useImportTypeMap` with a
  `{create: true}` mapping built from the file's `unmapped_types`.
- [x] 2.2 Replace the "Request training" button with "Train model", routing to
  `/training-jobs?source=import` via `router.push` instead of `useRequestRetrain().mutate()`;
  remove the now-unused `useRequestRetrain` import.
- [x] 2.3 `useImportTypeMap` also invalidates the `import-files` query on success so the list
  reflects a bulk-accept immediately.

## 3. Remove the auto-open deep link

- [x] 3.1 Delete the `?import=1`-triggered `useEffect` from `ImportedDocumentsList` entirely
  (and the now-unused `useSearchParams`/`usePathname` imports).
- [x] 3.2 Update the Import landing page's two `/imported-documents?import=1` hrefs to plain
  `/imported-documents`.

## 4. Tests

- [x] 4.1 `ImportedDocuments.test.tsx`: bulk-accept submits every unmapped type in one call; the
  picker never auto-opens on mount regardless of how the page was reached; "Train model" routes
  to `/training-jobs?source=import`.
- [x] 4.2 `AnnotationImportFlow.test.tsx`, `annotate/import/page.test.tsx`: updated mocks/
  assertions for the dropped `?import=1`.
- [x] 4.3 `test_annotation_import.py`: `unmapped_types` present and correct on both a pending and
  a fully-mapped file.

## 5. Verification & Evidence

- [x] 5.1 Ran the updated backend suite (36/36) and the updated portal suite (13/13) against the
  test containers.
- [x] 5.2 Rebuilt and restarted the `annotation_service` and `portal` Docker images (both are
  `build:`-based, not live-mounted — a code change needs a rebuild to take effect).
- [x] 5.3 Live-verified in the browser (demo-corp tenant): bulk-accept flips a file to
  training-eligible in one click (network trace showed the `type-map` POST returning 201); the
  picker no longer reopens after Review → Back (instrumented
  `HTMLInputElement.prototype.click` call count stayed at 0); "Train model" lands on
  `/training-jobs?source=import` with the submit panel pre-scoped to "Imported annotations".
