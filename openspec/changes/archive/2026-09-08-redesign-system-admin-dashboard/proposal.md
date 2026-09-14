## Why

The System Admin dashboard today (`_system_admin_data` in [dashboard.py](src/gateway/api/v1/dashboard.py)) is a thin copy of the Tenant Admin dashboard: it shows "Documents (all)", "Avg model F1", an "Approval queue" limited to pending items, and a "Platform health" card hard-coded to `—` for SLA/p95/GPU metrics that no service actually reports. A System Admin governs the platform (tenants, users, service uptime, approvals), not any one tenant's model quality — the current layout can't answer "is the platform healthy" or "what happened recently across tenants," and it exposes a tenant-scoped metric (model F1) that isn't the System Admin's job to judge.

## What Changes

- Hero copy (kicker/title/line) rewritten to frame the page as a platform control center: tenant/approval/operations language, no mention of training pipelines or document processing.
- Top stat cards: keep **Active Tenants** and **Pending Approvals**; replace **Documents (all)** with **Active Users** (`public.tenant_users` where `status = 'active'`); replace **Avg Model F1** with **Training Jobs Running** (sum, across tenant schemas, of `training_jobs` with `status = 'running'`) — a real-time platform-load signal, distinct from the Pending Approvals queue-depth stat, computed with the exact same schema-iteration pattern already used for Pending Approvals.
- **Platform Activity** replaces the **Approval Queue** panel: the most recent `public.audit_events` rows across all tenants, ordered chronologically. This is a generic "recent platform audit events" feed, not a fixed list of event types — whatever actions the audit log records (tenant lifecycle, user onboarding, training approvals, model promotions, and any future event type) SHALL appear without a spec change. Examples in this proposal and design.md are illustrative, not an exhaustive contract.
- **Platform Health** card redesigned with a deterministic, rules-based overall status computed purely from per-service reachability (never manually assigned):
  - **Healthy** — every one of Gateway, Chat API, Extraction Service, Training Service, and Model Serving is reachable.
  - **Degraded** — one or more of the non-critical services (Chat API, Extraction Service, Training Service) is unreachable, but both critical services (Gateway, Model Serving) are reachable.
  - **Critical** — Gateway or Model Serving (the platform's shared, single-point inference layer per ADR-003) is unreachable, regardless of the other services' state.
  Each service is checked via its existing `/health` endpoint, concurrently, with a short per-service timeout; a timeout or failed check marks only that service unavailable and never fails the dashboard endpoint itself. SLA/p95/GPU placeholders removed.
- **BREAKING**: `DashboardSummaryResponse.data` for `role=system_admin` changes stat labels/order, `pTitle`/`pRows` semantics (activity feed instead of approval queue), and `sideTop`/`sideMetrics`/`sideRows` content (service health instead of SLA/GPU). Any client hard-coded to the old system_admin shape must update. No changes to `tenant_admin`, `annotator`, or `business_user` payloads.
- **No new dashboard layout or component library**: this change introduces zero new frontend components and zero new layout structure. `StatCard`, `ActivityPanel`, and `MetricsPanel` are reused exactly as they exist today, unmodified in structure — only the data contract (values, labels, and copy) fed into them for `role=system_admin` changes.

## Capabilities

### New Capabilities

(none — this reshapes an existing capability's requirements rather than introducing a new one)

### Modified Capabilities

- `dashboard-summary-endpoint`: `system_admin` branch of `GET /api/v1/dashboard/summary` returns different stats, activity feed, and health-card content, sourced from `audit_events`, `tenant_users`, and per-service `/health` checks instead of tenant-schema F1/SLA placeholders.
- `portal-dashboard`: system_admin dashboard page data-shape expectations (stat labels, activity panel semantics, health-card semantics) updated to match; hero copy updated.

## Impact

- **Backend**: `src/gateway/api/v1/dashboard.py` — `_system_admin_data` rewritten; new helper(s) to read the most recent `audit_events` rows generically (no per-action allowlist) and to fan out concurrent `/health` checks to `chat_api_url`, `extraction_service_url`, `training_service_url`, `model_serving_url`, plus a hard-coded Online status for the gateway (no self HTTP call), then derive the deterministic Healthy/Degraded/Critical status from those results.
- **Frontend**: no component changes expected (reuses `StatCard`, `ActivityPanel`, `MetricsPanel` as-is, unmodified in structure — see "No new dashboard layout or component library" above); `src/portal/src/app/(auth)/dashboard/page.tsx` hero/messaging strings only if not already data-driven.
- **Tests**: `tests/test_dashboard_summary.py` and `tests/test_dashboard_summary_roles.py` system_admin cases need rewriting to match the new stats/activity/health shape.
- **Specs**: delta specs for `dashboard-summary-endpoint` and `portal-dashboard` covering only the system_admin scenarios that change; tenant_admin/annotator/business_user requirements untouched.

## Open Questions

- Should the "Platform Activity" feed also expose a full-history endpoint (mirroring `/api/v1/dashboard/activity`, currently tenant_admin-only) so the panel can be `expandable` for system_admin too, or is the summary's fixed recent-N feed sufficient for v1? (Design leans toward extending it since `audit_service.list_events` already supports pagination.)
