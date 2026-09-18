## 1. Shared component

- [x] 1.1 Add `primaryActionPosition?: "top" | "belowWorkCards"` to `AnnotateLanding`, defaulting
  to `"top"`. Extract the primary-action button into a shared value rendered at either position.

## 2. Automated landing page

- [x] 2.1 Pass `primaryActionPosition="belowWorkCards"` from `/annotate/automated`'s page, so
  "Start with step 1" renders after the "Before you begin" cards.

## 3. Tests

- [x] 3.1 New `AnnotateLanding.test.tsx`: default position renders beside the heading; explicit
  `belowWorkCards` renders after the work-cards section (asserted via DOM order, not just
  presence); the disabled/disabledReason rendering still works at either position.
- [x] 3.2 Extend `annotate/automated/page.test.tsx`: "Start with step 1" is positioned after
  "Before you begin" in the real page, not just in the generic component test.

## 4. Verification & Evidence

- [x] 4.1 Run the new/updated test files against the portal test container; confirm all pass.
- [x] 4.2 Rerun Manual's and Import's landing-page tests unmodified, confirming the default
  `"top"` position (their unchanged behavior) still holds.
- [x] 4.3 Run the full portal suite; confirm the failing-file set is exactly the known
  pre-existing 6-file baseline, with no new regressions.
- [x] 4.4 Rebuild and restart the `portal` container.
- [x] 4.5 Live-verify in the browser: "Start with step 1" renders directly below the "Before you
  begin" cards on `/annotate/automated`, and still navigates to `/annotate/automated/schema`
  when activated.
