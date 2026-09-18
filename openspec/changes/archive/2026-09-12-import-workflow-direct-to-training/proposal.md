## Why

The previous change (`import-annotation-training-workflow`, archived earlier this session)
gave the Import landing page a "1. Import file → 2. Review imported files" workflow plus a
separate, conditionally-shown "Train model" banner below it. Direct user feedback: imported
data already arrives pre-labelled and skips labeling entirely, so a "review" step in the
*workflow* overstates what's required before training — review remains available on
`/imported-documents` for anyone who wants it, but it is not a step on the path to training.
The correct two steps are "import" and "train," full stop, matching the mental model the user
described: "there is no need to review the annotations so just 1) import annotations 2) train
model."

## What Changes

- Replace the "2. Review imported files" workflow card with "2. Train model", linking directly
  to `/training-jobs?source=import`. Step 1 is relabelled "1. Import annotations" for symmetry.
- Remove the separate, eligibility-gated "Train model" banner entirely — "Train model" is now
  step 2 of the workflow itself, always shown, not conditioned on a training-eligible count.
- Revert `TrainModelBanner` to its original, Manual-only shape (drop the `label`/`sublabel`
  props added for Import's banner, since Import no longer uses the banner at all).

## Capabilities

### Modified Capabilities

- `import-annotation-landing`: "Workflow Steps" now describes a 2-step import-then-train
  sequence with no eligibility gate on step 2; the separate "Train Model Hand-off" requirement
  is removed, since that surface no longer exists as a distinct, conditional banner.

## Impact

- Frontend: [app/(auth)/annotate/import/page.tsx](src/portal/src/app/(auth)/annotate/import/page.tsx),
  [components/annotate/TrainModelBanner.tsx](src/portal/src/components/annotate/TrainModelBanner.tsx)
  (reverted to its pre-Import shape).
- Tests: rewrote [annotate/import/page.test.tsx](src/portal/src/app/(auth)/annotate/import/page.test.tsx)
  for the 2-step import-then-train structure; reverted the added test case in
  [TrainModelBanner.test.tsx](src/portal/src/components/annotate/TrainModelBanner.test.tsx).
- No backend changes — `/training-jobs?source=import` was already wired and gated correctly;
  this only changes what links to it and when.
