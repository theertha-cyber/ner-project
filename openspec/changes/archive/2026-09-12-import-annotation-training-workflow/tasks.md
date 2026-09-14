## 1. Shared banner

- [x] 1.1 Add optional `label: (count: number) => string` and `sublabel: string` props to
  `TrainModelBanner`, defaulting to the existing Manual-facing copy so Manual's call site needs
  no change.

## 2. Import deep link

- [x] 2.1 `ImportedDocumentsList`: read `useSearchParams()` and, when `import=1` and the caller
  can import, click the hidden file input on mount — the same handler the visible "Import file"
  button already uses.

## 3. Import landing page

- [x] 3.1 Replace the single "Imported files" work card (for `tenant_admin`) with two ordered
  cards: "1. Import file" → `/imported-documents?import=1`, "2. Review imported files" →
  `/imported-documents`. Leave the `annotator` role's single-card view unchanged.
- [x] 3.2 Add a `TrainModelBanner` keyed to `eligibleFiles`, with Import-specific
  `label`/`sublabel` text, navigating to `/training-jobs?source=import`.

## 4. Tests

- [x] 4.1 New `annotate/import/page.test.tsx`: two-step workflow order and routing for
  `tenant_admin`; single card for `annotator`; Train Model CTA appears/routes correctly when
  eligible, is absent at zero, and is never shown to an annotator.
- [x] 4.2 New `ImportedDocuments.test.tsx`: the file picker opens on `?import=1` for a role that
  can import, and stays closed with no parameter or for a role that cannot.
- [x] 4.3 Extend `TrainModelBanner.test.tsx`: a custom `label`/`sublabel` renders instead of the
  default "annotated" copy.
- [x] 4.4 Fix the regression this change caused in `AnnotationImportFlow.test.tsx` (added a
  `next/navigation` mock for the new `useSearchParams` call).

## 5. Verification & Evidence

- [x] 5.1 Run every new/updated test file against the portal test container; confirm all pass.
- [x] 5.2 Run the full portal suite; confirm the failing-file set is exactly the known
  pre-existing 6-file baseline, with no new regressions (this caught and required fixing task
  4.4 above).
- [x] 5.3 Rebuild and restart the `portal` container.
- [x] 5.4 Live-verify in the browser: `/annotate/import`'s "Your workflow" section shows the
  two ordered steps; activating "Import file" navigates to `/imported-documents?import=1` and
  the page loads without error (the native OS file picker itself is outside what browser
  automation can screenshot, so this is confirmed by the passing unit test plus the page
  reaching the right URL with no console errors); the Train Model banner is correctly absent
  for a tenant with zero training-eligible imported files.
