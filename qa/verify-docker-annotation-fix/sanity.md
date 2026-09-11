# CAP-6 Sanity Verification

## Focused portal tests

`npm test --workspace=src/portal -- --run src/components/annotation/AnnotationPage.test.tsx`

- 21 tests total; 18 passed; 3 failed.
- CAP-5 same-token click request-count assertion: PASS.
- CAP-5 multi-token drag request-count and inclusive-range assertion: PASS.
- Separate failures: three pre-existing layout-control assertions could not find `layout-btn-3pane`/`layout-btn-focus`.

## Deployed gesture trace

Not run. An authenticated browser/network trace was not available in this unattended execution. This is an environment/evidence blocker, not a CAP-5 behavior failure.
# CAP-6 Sanity Verification

- Timestamp: 2026-09-11T09:53:44Z
- Focused command: `npm test --workspace=src/portal -- --run src/components/annotation/AnnotationPage.test.tsx -t CAP-5`
- Result: PASS, 2 CAP-5 tests passed, 19 skipped.
- Same-token click: one POST assertion passed across token click and document mouseup.
- Multi-token drag: one POST assertion passed; payload assertion preserved inclusive `{char_start: 0, char_end: 11, text: "hello world"}`.
- Live authenticated browser/network verification and persisted confirmed-span counts were not captured because no authenticated session or browser automation evidence was available. No deployed gesture behavior is claimed.
- Full file separately ran 21 tests: 18 passed, 3 unrelated layout-control failures.
