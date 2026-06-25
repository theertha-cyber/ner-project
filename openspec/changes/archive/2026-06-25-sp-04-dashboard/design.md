## Context

The portal dashboard (`/dashboard`) must present role-specific KPIs, activity feeds, and model/service health metrics to four user roles (system_admin, tenant_admin, annotator, business_user). The interactive mockup at `docs/NER Platform.dc.html` defines exact data shapes per role in its `dashData(role)` method. Currently no dashboard summary endpoint exists — each consuming screen fetches from individual microservices. This design specifies how to compose a single dashboard-summary endpoint on the gateway and build the frontend component to match the mockup.

## Goals / Non-Goals

**Goals:**
- Expose `GET /api/v1/dashboard/summary` on the gateway returning a role-aware `DashboardData` payload matching `dashData(role)` from the mockup.
- Build the frontend `<DashboardPage>` component matching the mockup's hero, 4-column stat strip, activity panel, and secondary metrics panel.
- Support Editorial/Command layout toggle persisted to `localStorage`.
- Implement skeleton loading, graceful degradation on per-service failure, and 30-second auto-refresh.
- Use TanStack Query for all data fetching.

**Non-Goals:**
- Real-time WebSocket updates (polling is sufficient for MVP).
- Cross-tenant aggregations for system_admin beyond what existing endpoints support.
- Command palette or ⌘K search overlay (placeholder only).
- Exposing the summary endpoint publicly or without authentication.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Schema-per-tenant data isolation | Dashboard queries must filter by tenant_id; system_admin queries may aggregate across schemas |
| ADR-003 | Shared model-serving pool with tenant-aware routing | Active model data in the summary comes from the model registry service, not the serving layer directly |
| ADR-004 | OpenSpec SDD governance | All artifacts (proposal, design, spec, verification, tasks) must be created before implementation |
| ADR-005 | Bounded agent tool access | Implementation follows the task list; no ad-hoc changes without spec coverage |
| ADR-006 | Celery + RabbitMQ for async GPU jobs | Training job status data (running/pending_approval counts) fetched from the training-orchestrator service |

## Decisions

### Decision 1: Gateway composite endpoint vs. client-side aggregation

**Choice:** Gateway composite endpoint (`GET /api/v1/dashboard/summary`).

**Rationale:** A single gateway call reduces network round-trips (1 instead of 3–5 per dashboard load), centralises role-aware assembly logic, and hides service topology from the frontend. The frontend simply renders the shape it receives.

**Alternatives considered:**
- Client-side aggregation via `Promise.allSettled()` — makes N requests per load, couples frontend to service topology, complicates error handling.
- GraphQL gateway — overkill for a single read-only screen; adds BFF complexity.

### Decision 2: Per-service failure isolation with `sources` metadata

**Choice:** The endpoint calls each downstream service independently with short timeouts (5s connect, 10s read). Failed/unavailable services yield `null` values for their data fields plus `sources.<service>: false`. The frontend renders `—` for nulls in stat cards and hides affected activity rows.

**Rationale:** Ensures the dashboard never shows a full-page error when one of 3+ backing services is down. The `sources` block lets the frontend show contextual "data unavailable" messages per panel.

**Alternatives considered:**
- Fail-fast: any downstream failure returns 502 — bad UX, violates the mockup's partial-failure tolerance.
- Service-level caching with stale-while-revalidate — adds complexity without clear MVP benefit.

### Decision 3: Role-to-service routing via JWT claims

**Choice:** The endpoint decodes the JWT to extract `role` and `tenant_id`. It queries only the services relevant to that role (e.g., annotation service only for annotators and tenant_admins). Service URLs are configured via environment variables with short connect/read timeouts.

**Rationale:** Avoids unnecessary downstream calls. The role-to-service mapping is static (as defined by `dashData(role)` in the mockup) and fits a simple lookup table.

### Decision 4: Editorial/Command layout as pure CSS concern

**Choice:** The layout toggle is a `localStorage`-persisted string preference (`"A"` or `"B"`). It does not trigger any API call. The `heroWrapStyle` and typography styles switch between two CSS class sets defined in the component. Stat cards and panels are unaffected — only the hero section changes.

**Rationale:** Matches the mockup implementation (state variable `dashVariant`). Keeps the layout switch instant with zero network traffic.

## Risks / Trade-offs

- [Cross-tenant queries for system_admin] → The training service currently supports only per-tenant job queries. For MVP, the system_admin dashboard shows pending-approval count for their own tenant only, or uses a hardcoded placeholder. The endpoint structure supports adding cross-tenant aggregation later without shape changes.
- [30-second polling generates load on downstream services] → Each poll calls the gateway which fans out to 2–5 services. Acceptable for MVP; if load becomes a concern, implement server-side caching (Redis, TTL 15s) on the summary endpoint.
- [Stat cards with null values look broken] → The frontend explicitly renders `—` for null values and disables the delta indicator. Skeleton placeholders during loading follow the mockup's shimmer pattern.

## Migration Plan

1. Create `GET /api/v1/dashboard/summary` route in the gateway with role-based routing logic.
2. Wire tenant count source (DB query) for system_admin; all other sources return `null` with `sources.*: false`.
3. Build frontend `<DashboardPage>` component with Editorial/Command layout, stat cards, activity panel, and secondary panel.
4. Integrate TanStack Query with 30s refetch interval.
5. Add skeleton loading states.
6. Future specs (SP-06 onward) wire additional data sources by filling in the query logic — response shape stays stable.

## Open Questions

- Should layout preference sync to server for cross-device persistence? (Deferred — `localStorage` only for MVP.)
- Should system_admin see cross-tenant data or only their own tenant? (Deferred — MVP shows simple counts.)
