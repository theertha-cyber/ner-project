## 1. Import landing page

- [x] 1.1 Replace the "2. Review imported files" work card with "2. Train model", linking to
  `/training-jobs?source=import`; relabel step 1 to "1. Import annotations".
- [x] 1.2 Remove the separate `TrainModelBanner` usage and its eligibility-count gating from
  this page entirely.

## 2. Shared component

- [x] 2.1 Revert `TrainModelBanner` to its original, Manual-only props (drop `label`/`sublabel`,
  now unused since Import no longer renders the banner).

## 3. Tests

- [x] 3.1 Rewrite `annotate/import/page.test.tsx`: both steps render in order with the new
  titles; step 1 and step 2 each route correctly; step 2 is shown even with zero imported
  files; annotator still sees only the single review card.
- [x] 3.2 Revert the added test case in `TrainModelBanner.test.tsx`.

## 4. Verification & Evidence

- [x] 4.1 Run the updated test files against the portal test container; confirm all pass.
- [x] 4.2 Run the full portal suite; confirm the failing-file set is exactly the known
  pre-existing 6-file baseline, with no new regressions.
- [x] 4.3 Rebuild and restart the `portal` container.
- [x] 4.4 Live-verify in the browser: `/annotate/import` shows "1. Import annotations" → "2.
  Train model"; clicking "Train model →" lands on `/training-jobs?source=import` with the
  Submit Training Job panel auto-open and "Training source: Import" locked.
