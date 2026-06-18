## Why

After SP-03 (portal-shell), every authenticated route lands on a bare `PlaceholderScreen`. The dashboard is the first screen a user sees after login and the primary orientation point for all four roles — without it, the shell has no useful entry point and the platform's role-differentiated value proposition is invisible.

## What Changes

- Replace `app/(auth)/dashboard/page.tsx` placeholder with a fully implemented role-specific dashboard page.
- Implement four distinct dashboard data shapes (system_admin, tenant_admin, annotator, business_user) matching the mockup's `dashData(role)` method exactly: hero kicker/title/line, 4 stat cards, a primary activity panel, and a secondary metrics/quota panel.
- Implement two layout variants — **Editorial** (large typographic hero) and **Command** (compact info-dense header) — toggled by a `SegmentControl` whose preference is persisted in `localStorage`.
- Fetch live data where APIs exist; display skeleton cards (not spinners) while fetching; degrade gracefully per stat card when a service is unavailable.
- Add a `GET /api/v1/dashboard/summary` gateway endpoint that aggregates the data each role needs into a single response, reducing the number of client-side parallel fetches and isolating service failures server-side.
- Wire `refetchInterval: 30_000` for counts that change frequently (pending approvals, running jobs).

## Capabilities

### New Capabilities

- `portal-dashboard`: The `DashboardPage` component — role-aware data fetching, hero section, stat strip, two-panel grid, Editorial/Command layout toggle. Includes the `useDashboardData` hook and `DashboardSkeleton`.

### Modified Capabilities

- `app-shell`: The `DashboardRouter` in `(auth)/dashboard/page.tsx` currently redirects `system_admin` to `/admin`. After this change, all roles (including `system_admin`) land on the dashboard proper — the redirect is removed. This is a behaviour change to the existing `auth-layout` capability.

## Impact

- **Files changed**: `src/portal/src/app/(auth)/dashboard/page.tsx` (full rewrite)
- **Files added**: `src/portal/src/app/(auth)/dashboard/` subdirectory components, `src/portal/src/hooks/use-dashboard-data.ts`
- **Backend added**: `GET /api/v1/dashboard/summary` in `src/gateway/api/v1/dashboard.py` — aggregates tenant count (for system_admin), document count, training job counts, model status from whichever services are available; returns partial results with a `sources` map indicating which calls succeeded
- **Dependency**: `@tanstack/react-query` must be installed in the portal package — verify before implementing; add if missing
- **No migrations** — all data is read-only from existing service tables

## Open Questions

- None outstanding. The `system_admin` redirect-to-`/admin` removal is confirmed by the mockup (system_admin has its own hero/stat layout on the dashboard). The single `/api/v1/dashboard/summary` endpoint approach is chosen over multiple parallel client-side fetches to simplify error isolation and reduce waterfall risk.
