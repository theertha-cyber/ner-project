## Why

The mockup for the NER Platform has been updated with refined App Shell interaction details and a role-adaptive dashboard hero. The existing `app-shell` and `portal-dashboard` specs were written against an earlier design; without updating them, implementation will diverge from the new mockup in visible, user-facing ways (wrong animation, wrong icon, wrong hero treatment for system admins).

## What Changes

- **Sidebar – user strip trigger**: The `⋮` ellipsis button is replaced by a rotating `▾` chevron that animates to `▴` when the menu is open. The trigger button is now full-width with state-driven border and background variables (`userMenuBorder`, `userMenuBg`).
- **Sidebar – user menu animation**: The "150ms fade-in/out opacity" is replaced by a `menuPop .18s cubic-bezier(.16,1,.3,1)` spring animation originating from `transform-origin: bottom center`.
- **Sidebar – user menu outside-close**: The menu now uses a `position:fixed;inset:0` backdrop div (z-index 60) that intercepts outside clicks; the menu panel sits at z-index 61 above it. This replaces any `useClickOutside` hook approach.
- **Sidebar – logout icon**: The Logout menu item uses the `⎋` (escape) icon instead of a generic logout glyph.
- **Sidebar – tenant pill**: A `▾` caret is appended to the pill (visual only; pill remains display-only with no navigation or modal behaviour).
- **Topbar – demo role switcher**: In demo mode, the role-switcher pill container now prefixes an `AS` session-label chip (JetBrains Mono 10px, ink-3 colour) before the four role chips.
- **Dashboard – hero Variant B** (new): `system_admin` users get a dark-background hero with two animated mesh gradients (orange radial + slate radial, `meshDrift` animation). All other roles continue to use the existing light-background (Variant A) hero layout. The heroIsB flag is role-driven, not a user preference toggle.

## Capabilities

### New Capabilities

_(none — all changes are refinements to existing capabilities)_

### Modified Capabilities

- `app-shell`: Sidebar user strip trigger (chevron replaces ⋮), user menu animation (`menuPop` cubic-bezier), backdrop outside-close, logout icon (`⎋`), tenant pill caret, topbar demo role-switcher `AS` label.
- `portal-dashboard`: Hero section gains a role-driven **Variant B** (dark animated mesh) for `system_admin`; other roles remain on Variant A. The Editorial/Command layout toggle is unaffected and still applies within each variant.

## Impact

- `src/portal/components/AppShell.tsx` (or equivalent sidebar/topbar component) — user strip, menu, topbar.
- `src/portal/app/(auth)/dashboard/page.tsx` (or `DashboardHero` component) — hero variant logic.
- CSS/Tailwind: `menuPop` keyframe must be present in global styles.
- No API changes. No breaking changes to routes or auth flow.

## Open Questions

- Should the `AS` label in the topbar role-switcher stand for "Active Session", the current user's initials, or something else? Assuming it is a static demo-mode label for now; implementation should make the copy configurable.
- Does the Editorial/Command layout toggle interact with Variant B? (e.g., in Command mode, does the dark mesh hero still appear, or does it collapse to a compact treatment?) Assumed: Variant B applies to the hero background/typography only; the Editorial/Command toggle still controls layout density.
