## Why

The `/annotate/automated` page rendered "Start with step 1" beside the heading, above the
"Before you begin" upload cards. Direct user feedback: this reads as the thing to click first,
while the two upload cards beneath it are actually prerequisites for step 1 to succeed (Step 1
needs seed documents already in the library). Two competing "click me first" signals on the
same screen is exactly the confusion the "Before you begin" section exists to prevent.

## What Changes

- Add a `primaryActionPosition` prop to the shared `AnnotateLanding` component (`"top" |
  "belowWorkCards"`, defaulting to `"top"` so Manual's and Import's existing pages are
  unaffected).
- Move `/annotate/automated`'s "Start with step 1" action to render below the "Before you begin"
  work cards instead of beside the heading, using the new prop.

## Capabilities

### Modified Capabilities

- `automated-annotation-landing`: "Pre-Step-1 Upload Entry Points" now describes the work cards
  as appearing above "Start with step 1", not below it.

## Impact

- Frontend: [components/annotate/AnnotateLanding.tsx](src/portal/src/components/annotate/AnnotateLanding.tsx)
  (new optional prop, backward-compatible default),
  [app/(auth)/annotate/automated/page.tsx](src/portal/src/app/(auth)/annotate/automated/page.tsx).
- Tests: new [AnnotateLanding.test.tsx](src/portal/src/components/annotate/AnnotateLanding.test.tsx);
  extended [annotate/automated/page.test.tsx](src/portal/src/app/(auth)/annotate/automated/page.test.tsx).
  Manual's and Import's landing-page tests rerun unmodified to confirm the default position is
  unaffected.
- No backend changes.
