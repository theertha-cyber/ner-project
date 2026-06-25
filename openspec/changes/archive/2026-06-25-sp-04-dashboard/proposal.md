## Why

The interactive mockup at `docs/NER Platform.dc.html` defines a comprehensive role-specific dashboard with four distinct data shapes (system_admin, tenant_admin, annotator, business_user), Editorial/Command layout variants, stat cards, activity panels, and secondary metrics panels. The existing `portal-dashboard` spec was generated from an earlier decomposition and does not reflect the mockup's concrete data shapes, layout behaviour, or error-handling patterns. This change brings the spec in line with the mockup so that implementation produces a dashboard that matches the design exactly.

## What Changes

- **Backend**: Implement `GET /api/v1/dashboard/summary` endpoint in the gateway that returns a role-aware `DashboardData` JSON payload mirroring `dashData(role)` from the mockup. The endpoint aggregates data from tenants, training, documents, annotations, and models services with independent failure handling.
- **Frontend**: Build the dashboard page (`/dashboard`) as a self-contained component that renders the hero, 4-column stat strip, activity panel, and secondary metrics panel. Support Editorial/Command layout toggle persisted to `localStorage`. Wire all data to the summary endpoint.
- **Modified Capability**: Update `portal-dashboard` spec to reflect the mockup's exact data shapes for all four roles, layout toggle behaviour, skeleton loading, clickable activity rows, and partial-service-failure resilience.

## Capabilities

### New Capabilities

- `dashboard-summary-endpoint`: `GET /api/v1/dashboard/summary` — a role-aware composite endpoint that assembles `DashboardData` from tenant, training, document, annotation, and model services. Returns `null` for unavailable data sources with a `sources` metadata block indicating per-service availability.

### Modified Capabilities

- `portal-dashboard`: Update existing spec to match the mockup's four role-specific data shapes, Editorial/Command layout toggle with `localStorage` persistence, stat card skeleton states, clickable activity panel rows with correct route mapping, secondary metrics panel with animated progress bars, and 30-second auto-refresh via TanStack Query.

## Impact

- **Gateway** (`src/gateway/`): New route `GET /api/v1/dashboard/summary` with composite data assembly logic.
- **Portal UI** (`src/portal/`): New `DashboardPage` component, `useDashboard/` query integration.
- **Existing specs**: `portal-dashboard` spec updated with mockup-faithful scenarios.
- **No breaking changes**: The summary endpoint is additive; no existing APIs are altered.

## Open Questions

- Should the layout preference default to "Editorial" (matching mockup) or "Command" (for power users)?
Answer: editorial
- Should the system_admin see cross-tenant data (requires a multi-tenant query not yet implemented in the training service) — for MVP, pending-approval count can be hardcoded or limited to the admin's own tenant.

