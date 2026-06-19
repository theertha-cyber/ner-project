## Context

Today the sidebar user strip (pinned to the bottom of the left nav) renders the user's avatar, email, role, and a single `⎋` logout button. Settings is a standalone nav item in every role's sidebar — it appears in the scrollable nav area above the user strip, alongside Dashboard, Documents, etc. This means user-account actions (logout, settings) are split across two separate UI regions.

The change consolidates both actions into a single floating action menu triggered from the user strip, removing Settings from the nav entirely.

## Goals / Non-Goals

**Goals:**

- Replace the `⎋` logout button with a `⋮` trigger that opens a floating action menu.
- The menu presents two items: **Settings** (navigates to `/settings`) and **Logout** (calls `logout()`, redirects to `/login`).
- Menu opens upward with a 150ms CSS opacity fade-in/out transition.
- Menu closes on outside click and Escape key.
- Remove the Settings nav entry from `navFor()` for all four roles.
- All changes confined to two files: `Sidebar.tsx` and `nav-config.ts`.

**Non-Goals:**

- No changes to the `/settings` page or route — it remains a placeholder.
- No changes to the Topbar or its dark mode toggle.
- No new dependencies (UI library, state management, animation library).
- No changes to the auth context or logout API call.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| None | — | This is a strictly frontend-presentation change. No in-force ADR constrains sidebar layout or nav item selection. |

## Decisions

### Decision 1: Menu positioning — upward, absolutely positioned

**Choice:** The menu is rendered as an absolutely-positioned `div` inside the user strip container (which gets `position: relative`). It anchors to `bottom: 100%` of the container so it floats upward from the trigger.

**Rationale:** The user strip is at the very bottom of a 100vh sidebar. An upward-opening menu avoids overflow below the viewport. No scroll or repositioning logic is needed.

**Alternatives considered:**
- **Portal to `document.body`**: Unnecessary complexity for a menu that stays within the sidebar. No z-index conflicts exist.
- **Downward opening**: Would overflow below the viewport since the strip is at bottom of screen. Ruled out.
- **CSS `anchor()` positioning**: Not yet widely supported. `absolute` + `bottom: 100%` works in all evergreen browsers.

### Decision 2: Fade transition via CSS opacity

**Choice:** Use `opacity: 0 → 1` with `transition: opacity 0.15s ease`, gated by `pointerEvents: "auto" / "none"` to prevent ghost clicks during closed state.

**Rationale:** CSS transitions are zero-dependency, composable, and GPU-accelerated. The 150ms duration is short enough to feel instant, long enough to register as a deliberate animation.

**Alternatives considered:**
- **CSS `visibility` + `opacity`**: `visibility: hidden` prevents interaction but doesn't animate well. `pointerEvents` is cleaner.
- **Framer Motion / `react-spring`**: Overkill for a single opacity transition. No other animations in the app use these libraries.
- **`display: none` toggling**: Cannot animate `display`. Ruled out.

### Decision 3: Trigger icon — vertical ellipsis `⋮`

**Choice:** Use `⋮` (U+22EE, vertical ellipsis) as the trigger button icon.

**Rationale:** The vertical ellipsis is a widely-recognized pattern for overflow/action menus (Chrome, VS Code, Slack, GitHub). It signals "more actions" without requiring a label.

**Alternatives considered:**
- **`…` (horizontal ellipsis)**: Less commonly associated with vertical action menus.
- **`▼` (chevron)**: Usually indicates an expandable section, not a menu.
- **`☰` (hamburger)**: Associated with sidebar toggle, not action menus.
- **`⚙` (gear)**: Too specific to Settings — doesn't represent Logout.
- **Keep `⎋`**: Doesn't communicate that multiple actions exist.

### Decision 4: Click-outside detection via `mousedown` listener

**Choice:** A `useEffect` registers a `mousedown` handler on `document` that checks if the target is outside both `menuRef` and `triggerRef`. Escape key is handled via `keydown` listener.

**Rationale:** This is a standard, battle-tested pattern used in virtually every dropdown/menu implementation. Two refs (one for the menu, one for the trigger) prevent the menu from closing when clicking the trigger to toggle it.

**Alternatives considered:**
- **`<dialog>` element**: Native modal behavior, but requires `show()`/`close()` imperative API and has default backdrop styling. Too heavy.
- **A third-party hook like `useClickAway`**: Adds a dependency for 5 lines of code. Not justified.

### Decision 5: Settings label unified to "Settings" for all roles

**Choice:** The menu item reads "Settings" for all roles, including `system_admin` (who previously saw "Platform Settings" in the nav).

**Rationale:** The menu is tighter/contextual — the label can be shorter. The role differentiation in the sidebar nav was useful for scannability among many items, but with only two menu items the full label is unnecessary.

## Risks / Trade-offs

- **[Screen reader accessibility]** → Add `aria-haspopup="true"` and `aria-expanded` to the trigger button. Menu items should be focusable. Escape closes the menu.
- **[Touch targets]** → The `⋮` button is 32×32 px minimum (current style is `padding: 4px` around the icon, roughly 24×24). This meets WCAG 2.1 target size (24×24) but may be tight on mobile. Mitigation: the sidebar isn't used on mobile viewports.
- **[Flicker on first render]** → Menu starts with `opacity: 0` and never mounts conditionally — no flicker. The transition only runs when `opacity` changes.

## Migration Plan

1. Update `nav-config.ts` — remove Settings entries for all four roles. This is safe to deploy independently (Settings still works via direct URL navigation).
2. Update `Sidebar.tsx` — add the floating menu. The change is additive: the old logout button is replaced entirely.
3. No rollback concerns — revert the two files to restore the old behavior.

## Open Questions

- Should the settings route label differentiate "Platform Settings" for `system_admin`? (Design decision: no — "Settings" for all.)
