# Design: Remove Settings Placeholder Copy

## Context

`src/portal/src/app/(auth)/settings/page.tsx` currently imports `PlaceholderScreen` from `@/components/ui` and renders `<PlaceholderScreen title="Settings" />`. The shared component in `src/portal/src/components/ui/placeholder-screen.tsx` always renders the copy "This screen is coming soon."

## Decision

Replace the Settings page's use of `PlaceholderScreen` with route-local markup that matches the existing placeholder layout but omits the paragraph copy.

## Rationale

This keeps the change local to `/settings`. Other pages that still intentionally use `PlaceholderScreen` can continue to show the coming-soon message.

## Implementation Notes

- Remove the unused `PlaceholderScreen` import from the Settings page.
- Render the existing outer `animate-fade-up` wrapper.
- Render a centered layout with the Settings heading only.
- Do not edit `PlaceholderScreen` unless a future change asks to remove the copy from every placeholder page.

## Verification

Add or update a focused portal test that renders the Settings page and asserts:

- The "Settings" heading is present.
- The exact text "This screen is coming soon." is absent.
