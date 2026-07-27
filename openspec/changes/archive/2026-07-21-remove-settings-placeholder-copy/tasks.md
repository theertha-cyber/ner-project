# Tasks: Remove Settings Placeholder Copy

## Overview

Remove the coming-soon copy from the Settings page without changing shared placeholder behavior elsewhere.

## Task 1: Update Settings page ✓

**File**: `src/portal/src/app/(auth)/settings/page.tsx`

**What to change**:
- Remove the `PlaceholderScreen` import.
- Replace `<PlaceholderScreen title="Settings" />` with route-local JSX that renders only the Settings heading.
- Preserve the existing `animate-fade-up` wrapper and centered placeholder styling.

**Acceptance Criteria**:
- Navigating to `/settings` shows the "Settings" heading.
- The text "This screen is coming soon." does not appear on `/settings`.
- Other routes that use `PlaceholderScreen` are not changed.

## Task 2: Add focused verification ✓

**File**: Add or update the most appropriate portal test near the Settings route.

**What to verify**:
- Rendering the Settings page shows the "Settings" heading.
- Rendering the Settings page does not show "This screen is coming soon."

## Verification

After implementation:
1. Run the focused portal test for the Settings page.
2. Run the relevant portal test suite if available.
