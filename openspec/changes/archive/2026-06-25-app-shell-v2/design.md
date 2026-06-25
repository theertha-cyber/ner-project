## Context

The portal's `AppShell` component (sidebar + topbar) and the `DashboardPage` component were built against the v1 mockup. The v2 mockup ships three categories of change: (1) sidebar user-menu micro-interactions (trigger icon, animation, outside-close mechanism), (2) a topbar demo-mode label, and (3) a role-driven hero variant for the dashboard. All changes are contained within the frontend portal (`src/portal/`). No backend, API, or auth changes are required.

The existing implementation uses a `⋮` icon button with a `useClickOutside` hook pattern and a CSS opacity transition for the user menu.

## Goals / Non-Goals

**Goals:**

- Align the sidebar user-strip trigger, menu animation, and outside-close with the v2 mockup.
- Add the `AS` demo-mode label to the topbar role-switcher pill.
- Add a role-driven **Variant B** hero (dark animated mesh gradient) for `system_admin` on the dashboard.

**Non-Goals:**

- Redesigning the annotation workspace, documents, or any other screen.
- Changing routing, auth, or API behaviour.
- Replacing the Editorial/Command layout toggle — it remains in place and is orthogonal to the hero variant.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 | OpenSpec SDD mandatory artifacts | This change follows the spec-driven artifact pipeline. |
| ADR-005 | Role-specific agents, bounded scope | Frontend changes stay within portal boundary; no infra changes. |

All other ADRs (001–003, 006–008) are infrastructure/data/model decisions with no bearing on UI component implementation.

## Decisions

### Decision 1: Chevron rotation via CSS `transform` on a single element

**Choice:** Keep a single `▾` character in the DOM and rotate it 180° via `transform: rotate(180deg)` when the menu is open. State is driven by a local `userMenuOpen` boolean.

**Rationale:** The mockup expresses open state via `transform:rotate({{ userMenuChevron }})`. A single element with a conditional CSS class is simpler than swapping two icon components. It avoids a layout shift.

**Alternatives considered:**
- Swap between `▾` and `▴` characters — adds two branches in JSX for no visual gain.
- Use a Lucide/Heroicon chevron component — avoids Unicode characters but adds dependency; overkill for a single icon.

### Decision 2: Fixed-overlay backdrop for outside-close

**Choice:** Render a `position:fixed; inset:0; z-index:60` transparent `<div onClick={close}>` beneath the menu panel (z-index 61) when the menu is open.

**Rationale:** The mockup explicitly shows this pattern. It handles both outside-click and naturally plays well with touch events. It is simpler than a `useEffect` + `document.addEventListener` hook, requires no ref forwarding, and avoids the event-propagation subtleties that caused bugs in the v1 `useClickOutside` hook.

**Alternatives considered:**
- `useClickOutside` hook with `ref` — removed; the existing implementation had click-propagation bugs on mobile.
- `onBlur` on the trigger button — does not cover clicking arbitrary non-focusable elements outside the menu.

### Decision 3: `menuPop` keyframe in global CSS

**Choice:** Define `@keyframes menuPop` in `src/portal/app/globals.css` (or the Tailwind base layer) and apply it as a utility class `animate-menu-pop`.

**Rationale:** The `meshDrift` and `popIn` keyframes for the dashboard hero already live in globals.css. Keeping `menuPop` in the same file maintains a single source of truth for named animations and lets Tailwind's purge/safelist work correctly.

**Alternatives considered:**
- Inline `style={{ animation: 'menuPop ...' }}` — works but bypasses Tailwind's purge and cannot be reused.
- CSS Modules per component — too heavyweight for a single animation.

### Decision 4: Role-driven hero variant via a `heroVariant` helper

**Choice:** Introduce a pure function `heroVariant(role: UserRole): 'a' | 'b'` in `src/portal/lib/dashboard.ts`. `system_admin` returns `'b'`; all other roles return `'a'`. The `DashboardHero` component receives the variant as a prop.

**Rationale:** Keeps the variant logic testable in isolation. The component remains dumb — it renders what it receives. Editorial/Command layout density is a separate axis and continues to be read from `localStorage`.

**Alternatives considered:**
- Read `user.role` directly inside `DashboardHero` — couples UI to auth context; harder to test.
- A config object keyed by role — over-engineered for a binary flag.

### Decision 5: `AS` label is a hardcoded string in demo mode

**Choice:** Render the static string `"AS"` as a JetBrains Mono 10px label inside the role-switcher pill, guarded by the same `NEXT_PUBLIC_DEMO_MODE === "true"` condition as the role chips.

**Rationale:** The mockup shows `AS` as a static prefix. Until the product team confirms the intended meaning, a hardcoded constant avoids premature generalisation.

**Alternatives considered:**
- Derive from `userInitials` — would make the label dynamic but the mockup shows a static `AS` regardless of the logged-in user.

## Risks / Trade-offs

- [Fixed backdrop adds a full-viewport DOM node when menu is open] → Node is `pointer-events: auto` only for the click target; rendering cost is negligible and it is unmounted when the menu closes.
- [`menuPop` keyframe name might collide with a future Tailwind plugin] → Use a prefixed name `ner-menu-pop` in the keyframe declaration and alias it to `animate-menu-pop` in `tailwind.config.ts`.
- [Hero Variant B dark gradient looks similar to the login page background] → Intentional brand coherence; confirmed by mockup author (assumption — flag in Open Questions if not confirmed).

## Migration Plan

1. Add `@keyframes menuPop` (prefixed `ner-menu-pop`) to `globals.css` and register `animate-menu-pop` in Tailwind config.
2. Update `AppShell` sidebar user-strip: replace `⋮` button with chevron trigger + backdrop + `menuPop` animation.
3. Update topbar role-switcher: add `AS` label chip inside the demo-mode pill container.
4. Add `heroVariant()` helper to `src/portal/lib/dashboard.ts`.
5. Update `DashboardHero` (or `DashboardPage`) to accept and render `variant: 'a' | 'b'`.
6. No data-migration, no backend deploy, no feature flag required.
7. Rollback: revert the five files touched above; no database state is changed.

## Open Questions

- What does `AS` stand for in the topbar role-switcher? (Assumed "Active Session" for now — a comment in the code should explain this assumption.)
- Should Hero Variant B (dark mesh) also collapse differently in Command layout mode, or does it always render the full large treatment? (Assumed: variant drives only the background/colour; Editorial/Command still controls text size and layout density.)
