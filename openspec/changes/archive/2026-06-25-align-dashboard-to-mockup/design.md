## Context

The SP-04 dashboard (`src/portal/src/app/(auth)/dashboard/page.tsx`) is currently implemented with inline styles that diverge from the NER Platform mockup (`docs/NER Platform.html`). The mockup defines a refined design system for the dashboard with updated typography, spacing, grid layout, and component styling. All changes are frontend-only — the backend API (`GET /api/v1/dashboard/summary`) and TypeScript data shapes (`DashboardData`) remain unchanged.

The mockup uses Design Components (`x-dc` custom elements with a React runtime) to render a template-driven UI. The current implementation uses plain React components with inline style objects. This change keeps the React component architecture and only adjusts style values and minor structural markup.

## Goals / Non-Goals

**Goals:**
- Match the mockup's dashboard page layout, spacing, and visual styling exactly
- Update all five dashboard components: `page.tsx`, `DashboardHero`, `StatCard`, `ActivityPanel`, `MetricsPanel`
- Remove the Editorial/Command SegmentControl from the dashboard (layout variant is determined by role, not user toggle)
- Keep the existing `heroVariant(role)` function for determining Variant A vs B by role

**Non-Goals:**
- No changes to backend API response shape or data fetching
- No changes to the sidebar, topbar, or app shell layout (covered by separate `app-shell-exact-mockup` change)
- No changes to the analytics dashboard (`/analytics`)
- No changes to design tokens or CSS variable system

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 OpenSpec Governance | All changes require spec → tasks → verification pipeline | This design follows the pipeline via the current change |
| ADR-005 OpenCode Agent Boundaries | Role-specific agents with bounded tool access | Frontend-only changes; no infra/backend modification needed |

## Decisions

### Decision 1: Keep inline styles vs adopt CSS modules

**Choice:** Keep inline style objects (no CSS modules).

**Rationale:** The existing codebase uses inline `style` objects consistently across all dashboard and app-shell components. Switching to CSS modules or Tailwind for just these components would introduce inconsistency and extra build configuration. The mockup values are directly translatable to inline style adjustments.

**Alternatives considered:**
- CSS modules — ruled out because it would introduce a new styling pattern for a small visual delta
- Tailwind utility classes — not used elsewhere in the codebase; would require config changes

### Decision 2: Remove SegmentControl entirely (not just hide)

**Choice:** Delete the SegmentControl import, state hook, and JSX from `dashboard/page.tsx`. The `useLayoutPreference` hook becomes unused and should also be removed from the dashboard page.

**Rationale:** The mockup has no layout toggle — hero variant is selected by role only (`heroVariant(role)`). Keeping dead code adds maintenance burden.

**Alternatives considered:**
- Hiding it with CSS — dead code still compiles and clutters the component
- Keeping it for future use — no requirement; can be reintroduced from git history

### Decision 3: Activity row indicator — dot + right-aligned tag

**Choice:** Replace the left-aligned tag badge with a colored dot indicator on the left and move the tag text to a right-aligned position (after title/sub).

**Rationale:** The mockup shows a small colored dot (`<div>` with borderRadius: 50%) as the row indicator, with the status tag appearing as a right-aligned badge. This matches common activity-feed patterns and improves scannability.

**Alternatives considered:**
- Keeping the current left-aligned tag — doesn't match the mockup
- Removing tags entirely — loses status context

### Decision 4: Stat card grid — replace flex-wrap with explicit 4-column grid

**Choice:** Change the stat cards container from `display: flex; gap: 14px; flex-wrap: wrap` to `display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px`.

**Rationale:** The mockup always shows exactly 4 equal-width stat cards. The flex-wrap approach could wrap to 2+2 on narrower viewports, which doesn't match the intended design. A grid ensures consistent 4-column layout.

**Alternatives considered:**
- Keeping flex with fixed widths — more fragile
- CSS subgrid — overengineered for 4 items

## Risks / Trade-offs

- [Stat card delta position change may affect test assertions] → Update `StatCard.test.tsx` and `MetricsPanel.test.tsx` assertions to match new DOM structure and style values
- [Removing SegmentControl removes the ability to switch layouts] → Users who preferred "Command" layout lose that option. However, the mockup doesn't include this toggle — and admin users (who saw Variant B) already had a distinct layout by role
- [Page max-width reduction 1280px → 1240px may cause content shift] → Minimal (40px). The dashboard is centered with `margin: 0 auto`, so the shift is evenly split at 20px on each side

## Migration Plan

1. Update `DashboardHero.tsx` — adjust font sizes, border-radius, padding values
2. Update `StatCard.tsx` — restructure layout to place label+delta inline, change hover effect
3. Update `ActivityPanel.tsx` — add dot indicator, move tag to right side
4. Update `MetricsPanel.tsx` — stack title/meta, increase bar height, inline side metrics
5. Update `dashboard/page.tsx` — change padding/max-width, add breadcrumb, switch to grid, remove SegmentControl
6. Delete unused `useLayoutPreference` import from dashboard page
7. Update component tests to reflect new DOM structure

Rollback: Revert the changed files; no data migration needed.

## Open Questions

None.
