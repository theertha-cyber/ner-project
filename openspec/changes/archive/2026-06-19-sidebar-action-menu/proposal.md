## Why

The logout button at the bottom of the sidebar is a single-action control that takes up space without providing additional utility. Settings lives as a nav item in every role's sidebar, contributing to nav clutter. Moving both actions into a floating action menu triggered from the user strip reduces sidebar noise and groups user-account actions in one spot — a pattern users expect from modern UIs (Gmail, Slack, GitHub, etc.).

## What Changes

- Replace the standalone `⎋` logout button in the sidebar user strip with a `⋮` (vertical ellipsis) trigger that opens a floating action menu.
- The menu contains two items: **Settings** (navigates to `/settings`) and **Logout** (calls `logout()` then redirects to `/login`).
- The menu opens **upward** from the trigger with a 150ms fade-in/out transition.
- Remove the **Settings** nav item from all four role arrays in `nav-config.ts` (it now lives in the floating menu).
- The `/settings` route itself is unchanged — still a valid placeholder page.

## Capabilities

### New Capabilities

*(None — this change modifies existing capabilities, no new capability is introduced.)*

### Modified Capabilities

- `app-shell`: The sidebar user strip requirement changes — the `⎋` logout button is replaced with a `⋮` trigger and floating menu holding both Settings and Logout. Scenario for logout redirect updated accordingly. Scenario for annotator nav item count changes (Settings removed, so 4 → 3 items).
- `nav-config`: The Settings nav entry is removed from all four role arrays. Role → nav mapping scenarios updated to reflect the new item counts.

## Impact

| File | Change |
|---|---|
| `src/portal/src/components/app-shell/Sidebar.tsx` | Replace logout button with floating action menu. Add `useState`, `useEffect`, `useRef` for menu state and click-outside handling. |
| `src/portal/src/lib/nav-config.ts` | Remove Settings nav entries for all four roles. |
| `openspec/specs/app-shell/spec.md` | Update sidebar user strip requirement and the annotator-nav-item-count scenario. |
| `openspec/specs/nav-config/spec.md` | Remove Settings from all role→nav mapping tables and scenarios. Update scenario item counts. |

No API, dependency, or backend changes. No new dependencies required.

## Open Questions

- Should the settings route itself stay as `/settings` or should it change? (No change proposed — keeping `/settings` as-is.)
- For `system_admin` role: the nav label was "Platform Settings" — should the floating menu also show "Platform Settings" for that role, or just "Settings" for all? (Leaning: just "Settings" for simplicity — the menu label doesn't need role differentiation.)
