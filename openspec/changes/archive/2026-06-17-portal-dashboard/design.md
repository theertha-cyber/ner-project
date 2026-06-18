## Context

SP-03 (portal-shell) delivered the authenticated layout: sidebar navigation, topbar, and placeholder screens. The dashboard placeholder currently shows "Welcome, {email} · Coming soon" for all roles except `system_admin`, which is hard-redirected to `/admin`. This change replaces that placeholder with the full role-specific dashboard defined in the mockup.

The gateway exposes `GET /api/v1/admin/tenants` (system admin only). No dashboard-relevant aggregation endpoints exist yet. The training, document, annotation, and model services run as separate microservices and are not currently proxied through the gateway. The dashboard must degrade gracefully when services are unreachable.

TanStack Query (`@tanstack/react-query`) is **not** currently installed in the portal package — it must be added as part of this change.

## Goals / Non-Goals

**Goals:**
- Role-specific hero (kicker, title, line) matching the mockup's `dashData(role)` output exactly.
- Four stat cards per role with value, unit, sub-label, delta, and direction indicator.
- Primary activity panel: 4 rows with tag, title, sub-text, and a click-to-navigate handler.
- Secondary metrics panel: a big-number gauge with progress bar, three metric rows, and a mini bar chart section.
- Editorial / Command layout toggle persisted in `localStorage`; no data re-fetch on toggle.
- Skeleton card loading states (no full-page spinner).
- Single backend aggregation endpoint `GET /api/v1/dashboard/summary` that returns partial results with a per-source success map.
- Remove the `system_admin` → `/admin` redirect; all roles land on the dashboard.

**Non-Goals:**
- Live API data from training, document, or annotation services — those microservices are not yet wired to the gateway. Stats that cannot be fetched return a `null` value; the card renders `—` in place of the number.
- Pagination or filtering within the activity panel rows.
- Charting libraries — the progress bar and mini-bar are pure CSS/inline style.
- Notification badges or real-time websocket updates.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via separate DB schemas | Dashboard summary endpoint must only return data scoped to the caller's tenant; system_admin receives cross-tenant aggregates via the existing admin APIs |
| ADR-004 | OpenSpec spec-driven governance | Dashboard component and gateway endpoint implemented under this change's reviewed spec only |
| ADR-005 | Agent permission boundaries | No ambient developer UI in production; demo role-switcher already gated behind `NEXT_PUBLIC_DEMO_MODE` |

## Decisions

### Decision 1: Single `/api/v1/dashboard/summary` endpoint instead of multiple parallel client fetches

**Choice:** Add one aggregation endpoint to the gateway that assembles all role-relevant stats and returns them as a single JSON blob with a `sources` field indicating per-service success/failure.

**Rationale:** The dashboard needs 3–5 data points per role from different sources. Multiple parallel `useQuery` calls each with their own loading state produce a visually fragmented skeleton that pops in piece by piece. A single endpoint lets the gateway handle service fan-out, returns partial results atomically, and gives the client a single loading state to manage.

**Alternatives considered:**
- Multiple `useQuery` hooks per stat — ruled out: produces fragmented loading UI and exposes the client to cascading fetch waterfalls; also couples frontend directly to microservice topology.
- GraphQL — ruled out: overkill for a single screen; adds a dependency (Apollo or urql) not justified by scope.

### Decision 2: TanStack Query (`@tanstack/react-query`) for data fetching

**Choice:** Install `@tanstack/react-query` v5 and wrap the portal in a `QueryClientProvider`. Use `useQuery` with `placeholderData: keepPreviousData` and `refetchInterval: 30_000` for the dashboard hook.

**Rationale:** The NFR requires no full-page spinner and stale-while-revalidate behaviour on a 30s interval. These are exactly the use cases `useQuery` was built for. The portal has no existing data-fetching layer; this establishes the project standard for SP-05+.

**Alternatives considered:**
- `useSWR` — comparable feature set, but TanStack Query v5 has better TypeScript ergonomics and is already the implied choice in the decomposition doc.
- Manual `useEffect` + `useState` fetch — ruled out: requires reimplementing caching, deduplication, background refetch, and error retry manually.

### Decision 3: Layout toggle stored in `localStorage`, not URL or server state

**Choice:** Persist `"portal-layout"` key in `localStorage`. Read on mount with a `useEffect`; write on toggle. Default to `"editorial"`.

**Rationale:** Layout preference is a personal UI setting, not a navigable state. URL params would pollute bookmarks; server-side persistence requires an endpoint and auth round-trip not warranted for a visual toggle.

**Alternatives considered:**
- URL query param `?layout=command` — ruled out: changes the URL on toggle, affects Back button behaviour.
- Cookie — ruled out: unnecessary complexity for a frontend-only preference.

### Decision 4: Static `dashData(role)` shape for mockup-faithful content, with real values substituted where APIs exist

**Choice:** Define a `DashboardData` TypeScript type that mirrors the mockup's `dashData` shape exactly. The gateway endpoint returns the same shape with real values for fields it can populate and `null` for fields from unavailable services. The frontend renders `—` for null numeric values.

**Rationale:** Keeps the component tree stable regardless of which services are up. The shape is fixed by the mockup spec; only the values change as services come online in SP-05+.

**Alternatives considered:**
- Separate types per role — ruled out: leads to four divergent code paths for the same component tree; the mockup uses a single shape for all roles.

## Risks / Trade-offs

- [Gateway aggregation adds a new Python file with per-service try/except blocks] → Each service call is wrapped independently; partial failure returns what's available with `sources.{service}: false`.
- [TanStack Query v5 adds ~45 kB to the JS bundle] → Acceptable — this is the project's only data-fetching library; no duplication.
- [system_admin redirect removal changes existing behaviour] → The old DashboardRouter redirect (`system_admin` → `/admin`) is removed; system_admin now sees the dashboard. The Tenants page is still reachable from the sidebar nav. Verified by smoke test 8.2 in SP-03.
- [`localStorage` SSR hazard] → Layout preference is read inside `useEffect` (client-only), so no hydration mismatch.

## Migration Plan

1. Install `@tanstack/react-query` in `src/portal`.
2. Wrap `AuthProvider` in `QueryClientProvider` in `app/layout.tsx`.
3. Add `src/gateway/api/v1/dashboard.py` with the summary endpoint and register in `main.py`.
4. Rewrite `app/(auth)/dashboard/page.tsx` with the full dashboard component.
5. No database migrations. No breaking URL changes. Rollback: revert steps 3–4; restore placeholder page.

## Open Questions

- None outstanding.
