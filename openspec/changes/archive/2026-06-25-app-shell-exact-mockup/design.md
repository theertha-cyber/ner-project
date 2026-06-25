## Context

The portal's `AppShell` component (sidebar + topbar in `src/portal/src/components/app-shell/`) was last updated by the `app-shell-v2` change, which aligned micro-interactions (chevron animation, backdrop, `menuPop`, `AS` demo label) with the v2 mockup. However, a pixel-level comparison of `docs/NER Platform.html` against the current implementation reveals ~10 remaining visual gaps: background surface types (glass vs solid), element sizing, border radii, layout direction, container shapes, and color semantics. Additionally, the mockup includes a Widget Keys screen that has no corresponding route in the portal.

All changes are contained within the frontend portal (`src/portal/`). No backend service changes are required; the Widget Keys screen will consume the existing embeddable-widget endpoint if available, or render a stub state if not.

## Goals / Non-Goals

**Goals:**

- Remove the frosted-glass effect from sidebar and topbar; use the solid `var(--surface-2)` token matching the mockup.
- Resize the sidebar logo block to 30×30px with `font-weight: 800`.
- Restyle the tenant pill to have a `var(--surface-3)` background, `border-radius: 12px`, and a muted-primary avatar (soft/secondary colors instead of full brand orange).
- Add `border-radius: 11px` and `padding: 7px 8px` to the user strip trigger button.
- Wrap the user strip chevron `▾` in a framed 24×24px box matching the mockup.
- Apply `color: var(--bad)` + `hover: var(--bad-soft)` to the Logout menu item.
- Change topbar title + path to horizontal `align-items: baseline` layout.
- Wrap the role-switcher chips (including `AS` label) in a single bordered pill container.
- Unify topbar element border radii to 10px (search, dark-mode toggle, avatar).
- Add a `@keyframes fadeUp` animation to `globals.css` and apply it to each authenticated screen's root wrapper.
- Add a Widget Keys screen at `/widget-keys` (tenant_admin role only) with nav item.

**Non-Goals:**

- Changing any backend services, APIs, or authentication.
- Redesigning screens other than the app shell (annotation, documents, models, etc.).
- Implementing actual widget key CRUD operations — the screen is display-only in this change.
- Adding dark-mode-specific overrides beyond what the CSS variable system already provides.
- Changing the `AppShell`'s routing or role-gating logic beyond adding the widget-keys nav item.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 | OpenSpec SDD mandatory artifacts | This change follows the spec-driven artifact pipeline. |
| ADR-005 | Role-specific agents, bounded scope | Frontend changes stay within portal boundary; no infra changes. |

ADRs 001–003, 006–008 govern infrastructure, data isolation, and model serving — no bearing on UI component styling.

## Decisions

### Decision 1: Remove glass effect; use solid surface tokens

**Choice:** Set `background: var(--surface-2)` (no `backdropFilter` or `rgba` opacity) on both sidebar and topbar, exactly as the mockup specifies.

**Rationale:** The glass effect (`rgba(255,255,255,0.85)` + `backdrop-filter: blur(16px)`) was an aesthetic enhancement added over the mockup. Reverting to the solid `var(--surface-2)` token makes the live app match the reference exactly and simplifies the CSS — no browser-capability concerns around `backdrop-filter` support.

**Alternatives considered:**
- Keep the glass effect as a deliberate improvement — ruled out because the goal of this change is exact mockup alignment, not aesthetic divergence.
- Make glass a feature-flagged variant — over-engineered for what is effectively a CSS correction.

### Decision 2: Chevron boxed container as a styled `<span>`, not an icon component

**Choice:** Wrap the `▾` character in a `<span>` with explicit `width: 24px; height: 24px; border-radius: 7px; background: var(--surface-2); border: 1px solid var(--line)` inline styles. No new icon library import.

**Rationale:** The mockup renders the chevron in a bordered square. A styled span with existing CSS tokens is the minimum-surface implementation. The `▾` character is already in use; adding a container around it doesn't change the rotation logic (the `transform: rotate(180deg)` is applied to the character itself, which lives inside the box).

**Alternatives considered:**
- Use a Lucide/Heroicon chevron component inside the box — adds a dependency for no visual gain over the `▾` character.
- Render the box as a separate sibling `div` — more DOM nodes and harder to coordinate hover states.

### Decision 3: Role-switcher container as a single `<div>` pill wrapping all chips

**Choice:** In `Topbar.tsx`, wrap the entire demo-mode block (`AS` label + four role chips) in a `<div>` with `background: var(--surface-3); border: 1px solid var(--line); border-radius: 10px; padding: 3px`. The existing `gap: 4` flex layout of the chips is preserved inside the container.

**Rationale:** The mockup renders the switcher as a single visual unit with a bounding pill. The current implementation has the chips as loose siblings in a flex div with no container border. The fix is purely additive — one wrapper `<div>`.

**Alternatives considered:**
- Apply a border to the outer flex container already in place — already what we're doing; just need to add the background and explicit padding.
- Separate each chip into its own pill — contradicts the mockup's grouped-container design.

### Decision 4: `fadeUp` keyframe in `globals.css`; applied at page root level

**Choice:** Add `@keyframes fadeUp { from { transform: translateY(8px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }` to `src/portal/app/globals.css` alongside existing `meshDrift`, `popIn`, and `menuPop` keyframes. Apply via a CSS class `.animate-fade-up` registered in `tailwind.config.ts`. Each authenticated page's root wrapper `<div>` (first non-layout div in each `page.tsx`) gets `className="animate-fade-up"`.

**Rationale:** The mockup applies `animation: fadeUp .35s ease both` to each screen's content wrapper, not the layout. Applying it per-page means it fires when navigating between screens (a Next.js route change unmounts and remounts the page component), producing the intended enter animation. An AppShell-level application would only fire on initial load.

**Alternatives considered:**
- Apply at `<main>` in `AppShell` — only fires once on app mount; doesn't animate route transitions.
- Use a Framer Motion `AnimatePresence` — correct behavior but adds a significant runtime dependency for a simple CSS animation.
- Tailwind `animate-*` via `@layer utilities` — same as chosen approach; using the `globals.css` + `tailwind.config.ts` pattern already established by `menuPop`/`ner-menu-pop`.

### Decision 5: Widget Keys screen — read-only stub, no backend dependency

**Choice:** Implement `/widget-keys` as a read-only display page showing the tenant's widget keys from `GET /api/v1/tenants/{slug}/widget-keys`. If the endpoint returns a non-2xx response (or the feature flag is not set), the page renders an empty-state illustration instead of crashing. No key creation or revocation UI in this change.

**Rationale:** The mockup shows a complete CRUD interface but adding mutation operations requires backend coordination outside the scope of this frontend-alignment change. Showing existing keys read-only is sufficient to make the screen present and visually correct. Mutation can be added as a follow-on.

**Alternatives considered:**
- Full CRUD (create, revoke) — requires backend changes; out of scope.
- Omit the screen entirely — the mockup includes it and the nav item references it; omitting creates a broken link for tenant_admin.

## Risks / Trade-offs

- [Removing glass effect may look worse in some page backgrounds] → The CSS variable system (`var(--surface-2)`) handles both light and dark mode correctly. The glass effect only visually mattered against animated gradient backgrounds (login page), which is a separate component.
- [Per-page `fadeUp` means touching every `page.tsx` in `(auth)/`] → There are ~12 authenticated routes. All get a one-line `className` addition to their root `<div>`. Low-risk repetitive change.
- [Widget Keys screen may 404 on the backend] → Empty-state handling in the component covers this; no crash risk.
- [`fadeUp` on route change causes brief visual jump if navigation is fast] → 0.35s is within acceptable UX range; the mockup uses this duration.

## Migration Plan

1. Update `globals.css`: add `@keyframes fadeUp` (prefixed `ner-fade-up`) and register `animate-fade-up` in `tailwind.config.ts`.
2. Update `Sidebar.tsx`: remove `backdropFilter`/opacity glass, resize logo, restyle tenant pill, restyle user strip button + chevron box, apply danger color to Logout.
3. Update `Topbar.tsx`: remove glass, change title layout to horizontal baseline, wrap role-switcher in pill container, unify border radii to 10px.
4. Add `animate-fade-up` class to each authenticated page's root wrapper.
5. Add `/widget-keys` route: `src/portal/src/app/(auth)/widget-keys/page.tsx`.
6. Update `nav-config.ts`: add widget-keys nav item for `tenant_admin` role.
7. No backend deploy, no database migration, no feature flag required.
8. Rollback: revert the ~15 files changed; no persistent state is affected.

## Open Questions

- Confirm with design that reverting to solid `var(--surface-2)` (removing glass) is intentional and not a regression from an approved enhancement.
- What does the widget-keys backend endpoint return exactly? Need to confirm response shape before implementing the display table.
- Should `/widget-keys` appear in `SCREEN_TITLES` for the topbar path display?
