# Proposal: Remove Settings Placeholder Copy

## Problem Statement

The Settings page currently renders the shared `PlaceholderScreen`, which displays the heading "Settings" and the supporting copy "This screen is coming soon." The requested behavior is to remove that supporting copy from the user settings page.

Because `PlaceholderScreen` is shared by multiple placeholder routes, changing it globally could unintentionally remove placeholder copy from other pages. The safer scope is the Settings route itself.

## Proposed Solution

Update the Settings page so it no longer renders the shared placeholder message. The page should continue to show the Settings title and preserve the existing centered placeholder layout and fade-up animation, but the exact text "This screen is coming soon." must not appear on `/settings`.

## Impact

- **Scope**: `src/portal/src/app/(auth)/settings/page.tsx`
- **Risk**: Low. This is a copy-only UI change for one route.
- **No new dependencies**: Uses existing React and styling conventions.
