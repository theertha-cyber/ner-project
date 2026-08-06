## Context

`GET /api/v1/dashboard/summary` (`src/gateway/api/v1/dashboard.py`) dispatches on `role` to one of four private builders returning a shared `DashboardData` shape (`stats`, `pTitle`/`pRows`, `sideTop`/`big`/`bigUnit`/`bar`/`sideMetrics`/`sideRows`). `_system_admin_data` currently:

- Counts `public.tenants` for "Active tenants".
- Iterates every tenant schema (via `_all_tenant_schemas`, itself gated on `public.tenants.status = 'active'` joined against `pg_namespace` per ADR-001's schema-per-tenant isolation) to sum `documents` ("Documents (all)"), sum `training_jobs WHERE status = 'pending_approval'`, and average the latest `promoted` `model_versions.metrics->>'f1'` ("Avg model F1").
- Hard-codes `pRows` as an empty "Approval queue" placeholder and `sideMetrics`/`big`/`bar` as `—` placeholders labeled SLA/p95/err/GPU — no code path ever populates these.

This design was revised after stakeholder review of the first draft. Three changes from that review are load-bearing throughout this document: (1) the fourth stat card is "Training Jobs Running," not "Active Models" — a platform-load signal was judged more actionable for a System Admin than a deployment-presence count; (2) Platform Health's overall status is a deterministic function of per-service reachability with three named tiers (Healthy/Degraded/Critical), not a free-text summary string; (3) Platform Activity's contract is "the most recent audit events, generically" — the spec does not enumerate which `audit_events.action` values must appear, so the feed stays extensible as new action types are logged, without a spec change.

Separately, `public.audit_events` (`src/gateway/models/__init__.py`, backed by `AuditService` in `src/gateway/services/audit_service.py`) already records `tenant.create`, `tenant.deactivate`, `user.create`, `training_job.submit`, `training_job.approve`, `training_job.reject`, and `model_version.promote` with `actor`, `role`, `action`, `target`, `kind`, `tenant_id`, `created_at` — a ready-made, cross-tenant, chronological audit trail that nothing in the dashboard currently reads. Every backing service (`gateway`, `chat_api`, `extraction_service`, `training_service`, `model_serving`) exposes a `/health` endpoint (`src/shared/readiness.py` pattern, already consumed by `_fetch_assistant_health` for the business_user dashboard).

Stakeholders: System Admins (primary viewer), Tenant Admins (whose dashboard must stay visually/behaviorally unchanged — this change touches only the `system_admin` branch).

## Goals / Non-Goals

**Goals:**

- Make `_system_admin_data` answer "is the platform healthy," "how many tenants/users," "what needs my attention," and "what happened recently" using data sources that already exist (`public.tenants`, `public.tenant_users`, `public.audit_events`, per-service `/health`).
- Reuse `StatCard`, `ActivityPanel`, `MetricsPanel` and the existing `DashboardData`/`StatItem`/`ActivityRow`/`SideMetric`/`SideRow` types verbatim — zero new frontend components, zero type changes.
- Remove tenant-model-quality metrics (F1) and unpopulated infra placeholders (SLA/p95/GPU) from the system_admin view entirely.

**Non-Goals:**

- No change to `tenant_admin`, `annotator`, or `business_user` dashboard data, components, or types.
- No new dashboard layout or component library: `StatCard`, `ActivityPanel`, and `MetricsPanel` are reused exactly as they exist today, structurally unmodified (the one exception, Decision 5's few-line `statusColor()` extension, adds color cases to an existing function — it is not a new component). Only the data contract, displayed metrics, and copy for `role=system_admin` change.
- No new database tables, columns, or migrations — `audit_events`, `tenant_users.status`, and `training_jobs.status` already exist.
- No general-purpose audit-log UI (filtering, search, pagination controls) — only a curated recent-activity feed, matching the existing `ActivityPanel` capability level used by tenant_admin.
- No enumerated allowlist of `audit_events.action` values as part of the spec contract — Platform Activity is generically "the most recent audit events, chronological" (Decision 2); which actions exist is entirely up to the audit log, not this dashboard.
- No SLA/latency/GPU monitoring — replaced by a deterministic, rules-based Healthy/Degraded/Critical status derived from binary service reachability, not a metrics/observability integration.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|---------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant's operational data lives in its own `tenant_<id>` schema; cross-tenant aggregation must iterate schemas derived from what actually exists, not assumed from `public.tenants` rows alone. | The "Training Jobs Running" count and any other per-tenant aggregation MUST reuse `_all_tenant_schemas` (or equivalent existence-checked schema list), matching the pattern the current pending-approval code already uses. Must not query a tenant schema that doesn't exist. |
| ADR-003: Per-Tenant Model Serving Topology | A single shared Model Serving Layer serves all tenants (strategy b) — not one deployment per tenant. | The "Model Serving" row in Platform Health is ONE `/health` check against `settings.model_serving_url`, not per-tenant checks. |
| ADR-004: OpenSpec Spec-Driven Development Governance | Requirement changes need delta specs before implementation. | This change ships delta specs for `dashboard-summary-endpoint` and `portal-dashboard` scoped to system_admin scenarios only. |

ADR-002, 005, 006, 007, 008, 009 concern base-model strategy, agent tooling boundaries, training worker internals, chat/RAG architecture, and hyperparameter approval flow — none constrain a dashboard read-model reshape.

## Decisions

### Decision 1: Platform Activity feed reads `public.audit_events` directly, not through `AuditService`

**Choice:** `_system_admin_data` issues its own `SELECT ... FROM public.audit_events ORDER BY created_at DESC LIMIT :n` (mirroring `AuditService.list_events`'s query) rather than instantiating `AuditService`.

**Rationale:** `AuditService.list_events` returns its own dict shape (`{events, total, page, per_page}`) and is designed for a future dedicated audit endpoint, not the dashboard's `ActivityRow` shape (`title`/`sub`/`tag`/`tk`/`go`/`icon`/`time`). Mapping happens in the dashboard layer regardless; querying directly avoids an unnecessary intermediate dict-to-dict translation and keeps the dashboard module's existing self-contained query style (every other `_xxx_data` function issues raw SQL in-module).

**Alternatives considered:**
- Call `AuditService.list_events` and re-map — adds an indirection layer for no behavioral benefit; the dashboard module doesn't otherwise depend on `services/`.
- Add a `kind`/`action`-based filter at the SQL level to exclude noisy events — deferred; see Open Questions on `training_job.submit`.

### Decision 2: Platform Activity is a generic "most recent audit_events" feed — the friendly-title map is an implementation convenience, not part of the contract

**Choice:** `_system_admin_data` selects the most recent `public.audit_events` rows (`ORDER BY created_at DESC LIMIT :n`) across all tenants with no `action`/`kind` filter — every action type the audit log records is eligible to appear. A module-level `_SYSTEM_ACTIVITY_TITLES: dict[str, str]` maps *known* `action` values (e.g. `tenant.create` → "Tenant created", `user.create` → "User onboarded", `model_version.promote` → "Model promoted" — illustrative, not exhaustive) to friendlier display titles as a presentation nicety; `tk`/`icon` derive from `kind` via the existing `_activity_tag_colour`-style mapping. Any `action` not present in the dict SHALL still appear in the feed, titled via a humanized fallback of the raw string (`action.replace('_', ' ').replace('.', ': ')`) — the map only improves copy for known actions, it never gates which events are shown.

**Rationale:** Per stakeholder review, Platform Activity must not be specified as a fixed list of event categories — the spec's contract is "recent platform audit events, chronological," full stop, so that a new `audit_events.action` introduced by a future change appears in the feed automatically, without revisiting this spec. The friendly-title dict is purely cosmetic and lives entirely in code, not in the requirement text. This also matches how `_tenant_curated_activity` already maps `training_jobs.status`/`model_versions` events to `ActivityRow` fields — same technique, different source table.

**Alternatives considered:**
- Specify the exact set of `action` values that must produce a friendly title as a normative requirement — rejected per stakeholder direction: this would force a spec update every time a new audit action type is added, undermining the point of building on a generic audit log.
- Store the display title in `audit_events` at write time — rejected: would require touching four write sites (`tenant_service.py`, `user_service.py`, `training_jobs.py`, `models.py`) for a read-side concern, and couples audit-log semantics to one dashboard's copy.

### Decision 3: The fourth stat card is "Training Jobs Running," not a model-deployment count

**Choice:** Sum, across all tenant schemas (via `_all_tenant_schemas`), `COUNT(*) FROM {schema}.training_jobs WHERE status = 'running'` — the same schema-iteration pattern already used for the Pending Approvals stat, run in the same loop pass (one query per schema returns both counts).

**Rationale:** Per stakeholder review, "Active Models" (tenants with a currently-promoted model) was judged not genuinely actionable for a System Admin — it doesn't change day-to-day and doesn't prompt a decision. "Training Jobs Running" is a real-time signal of platform load/utilization: it complements Pending Approvals (which shows queue depth — jobs waiting) with active-work depth (jobs in flight), giving the System Admin a live read on how busy the platform's training pipeline is right now, without duplicating Active Tenants or Active Users. It is also simpler to implement than the deployment-presence check it replaces: a straight `COUNT` in the same query pass as Pending Approvals, not a separate per-schema `EXISTS` check.

**Alternatives considered:**
- **Active Models** (tenants with a `promoted` model version) — rejected per stakeholder direction: not judged actionable enough; conflates "is a model deployed" (mostly static) with the platform-health question this section is meant to answer.
- **Total Users** — rejected: too similar to the Active Users card already on the strip (both user-count-flavored), weak differentiation across the 4 cards.
- **Models Awaiting Approval** — rejected: promotion is a manual action taken after a training job completes, not a tracked "awaiting approval" state in the current data model (no `model_versions` status represents "ready to promote, pending decision"); would require a new status value, out of scope for a read-model-only change.
- **Recently Active Tenants** (tenants with activity in the last N days) — rejected: conceptually redundant with the existing Active Tenants card; doesn't add a distinct signal.

### Decision 4: Health checks run concurrently with a short per-service timeout; overall status is a deterministic function of reachability, not a free-text summary

**Choice:** `asyncio.gather` fires `/health` GETs (via `httpx.AsyncClient`) at `chat_api_url`, `extraction_service_url`, `training_service_url`, `model_serving_url` concurrently, each with its own 3-second timeout; the gateway's own health is reported as `"Online"` unconditionally (the request already reached this code inside the gateway process, so a self-HTTP-call would be redundant and could itself be a failure point). A service is `"Online"` on HTTP 200 within the timeout, `"Offline"` on any other status, exception, or timeout — a timeout or failed request marks **only that service** unavailable and SHALL NOT raise, propagate, or otherwise fail the dashboard endpoint itself; the endpoint always returns 200 regardless of how many backing services are down.

The overall status is computed, never manually assigned, from a fixed rule over the five reachability results:
- **Healthy** — all five services (Gateway, Chat API, Extraction Service, Training Service, Model Serving) are `"Online"`.
- **Degraded** — Gateway and Model Serving are both `"Online"`, but at least one of Chat API, Extraction Service, or Training Service is `"Offline"`.
- **Critical** — Gateway or Model Serving is `"Offline"` (regardless of the other three), because per ADR-003 Model Serving is the single shared inference layer every tenant depends on, and Gateway is the entry point for every request.

**Rationale:** Sequential checks would add up to 4 × request-timeout to every system_admin dashboard load in the worst case; parallel fan-out bounds added latency to roughly one timeout period. A rules-based tri-state status (rather than a hand-picked string or a raw "N of 5 down" count) gives the System Admin an unambiguous, always-computed severity signal that maps directly to what's actually broken, per stakeholder review. Designating Gateway and Model Serving as the two "critical" dependencies follows directly from ADR-003 (Model Serving is the one shared, non-redundant layer every tenant's inference depends on) and from the trivial observation that no request reaches this code at all if the Gateway itself is down. Reuses the exact try/except-around-httpx pattern `_fetch_assistant_health` already established for business_user, so no new error-handling idiom is introduced.

**Alternatives considered:**
- A free-text overall status string (e.g. `"All Services Operational"` / `"{n} of 5 services degraded"`) — rejected per stakeholder review: not deterministic/rule-based, and "N of 5" implies a precision (every service equally weighted) that isn't true — a Chat API outage and a Model Serving outage are not equally severe.
- Treat gateway health via a real HTTP round-trip to itself — rejected: adds a network hop with no new information (if the request handler is running, the gateway is up).
- Cache health-check results for N seconds to avoid re-checking every page load — deferred; out of scope for a first pass, noted as a possible follow-up if latency proves an issue in practice.
- Weight all 5 services equally with no "critical" tier (binary Healthy/Unhealthy only) — rejected: loses the distinction between "one nice-to-have service is down" and "the platform's shared inference layer is down," which is exactly the actionable signal a System Admin needs.

### Decision 5: `sideMetrics` (3 fixed slots) carries Gateway/Chat API/Extraction Service; `sideRows` carries Training Service/Model Serving

**Choice:** No changes to `MetricsPanel.tsx`, `DashboardData`, or `SideMetric`/`SideRow` types. `sideMetrics: [SideMetric,SideMetric,SideMetric]` holds `{k:"gateway", v:"Online"|"Offline"}`, `{k:"chat api", v:...}`, `{k:"extraction", v:...}` — `MetricsPanel`'s existing `statusColor()` already colors literal `"Online"`/`"Offline"` values green/red with zero code changes. `sideRows` (unbounded list, already rendered as label/value/progress-bar rows) holds Training Service and Model Serving, using `pct: 100` + `c: "var(--color-delta-up)"` when Online and `pct: 0` + `c: "var(--bad)"` when Offline — the progress bar fully fills or empties as a secondary visual signal, but the `val` text ("Online"/"Offline") is the primary signal.

**Rationale:** Directly satisfies the "reuse existing dashboard components where possible" design principle — this is the only decision in this design that could plausibly need a new component (a "service status list"), and it doesn't. `big`/`bigUnit` carries the deterministic overall status from Decision 4 (`"Healthy"`, `"Degraded"`, or `"Critical"`). `MetricsPanel.tsx`'s existing `statusColor()` function gains three additional string-match cases (`"Healthy"` → green, `"Degraded"` → amber, `"Critical"` → red) alongside its existing `"Online"`/`"Offline"` cases — a few-line extension of an existing color-mapping function, not a new component, prop, or layout structure, so it stays within this change's "no new dashboard layout or component library" boundary.

**Alternatives considered:**
- Extend `sideMetrics` to a variable-length array to fit all 5 services in one row — rejected: `DashboardData.sideMetrics` is typed as an exact 3-tuple (`types/dashboard.ts`) consumed by `tenant_admin`/`annotator` too; changing the type is a wider blast radius than reusing the two existing reusable slots (`sideMetrics` + `sideRows`).
- Add a dedicated `ServiceHealthCard` component — rejected per design principle; not needed once slots are reused this way.
- Leave `"Degraded"`/`"Critical"` in the default brand color with no severity-specific coloring — rejected: the whole point of a deterministic tri-state status is to be immediately understandable at a glance; a same-colored "Critical" and "Healthy" headline undercuts that, for a one-time, few-line extension of a function this design already touches.

## Risks / Trade-offs

- [`audit_events` has no index on `created_at` beyond default primary-key ordering guarantees, and the table has unbounded growth as more actions are logged] → `ORDER BY created_at DESC LIMIT :n` with a small `n` (e.g. 6–10 rows for the summary view) keeps the query cheap without an index for the data volumes this platform runs at today; revisit with an index if the table grows large enough to matter.
- [Because Platform Activity is now generic (Decision 2), an audit action a System Admin doesn't care about (e.g. a very high-frequency future event type) could crowd out more meaningful recent events in a small fixed-`n` feed] → Accepted trade-off per stakeholder direction favoring genericity over curation; the humanized-fallback title still makes any such row informative rather than confusing, and `n` can be tuned or true filtering added later without a spec change (the contract only requires "most recent, chronological").
- [Parallel health checks still add up to ~3s of latency to the system_admin dashboard load if a service is down/unreachable] → 3s timeout bounds the worst case; `asyncio.gather` runs all 4 outbound calls concurrently so the added latency is one timeout period, not four; a timeout/failure marks only that one service Offline and never fails the endpoint itself (Decision 4).
- [Designating Gateway and Model Serving as the only two "critical" services is itself a judgment call — a different platform might consider Extraction Service equally critical] → Documented explicitly in Decision 4 with its ADR-003-backed rationale so the choice is auditable and revisitable; not hidden inside an opaque scoring function.

## Migration Plan

1. Add the generic audit-event feed helper (with its cosmetic title map), the per-service health-check helper, and the Healthy/Degraded/Critical status-derivation function to `src/gateway/api/v1/dashboard.py` (additive, no shared code touched).
2. Rewrite `_system_admin_data` to call the new helpers and assemble the new `stats` (including "Training Jobs Running" computed in the same schema-iteration pass as Pending Approvals), `pRows`, `sideTop`/`sideMetrics`/`sideRows` values, replacing the F1/SLA placeholder logic. `_null_sources()` gains no new keys — health/activity/users read from tables/services already covered by existing source flags (`tenants`, `training`) or reuse them; `tenant_users` reads fold into the existing `tenants` source flag since both live in the `public` schema.
3. Update hero copy (`kicker`/`title`/`line`) in the same function.
4. Extend `MetricsPanel.tsx`'s `statusColor()` with `"Healthy"`/`"Degraded"`/`"Critical"` cases (Decision 5) — the only frontend code change in this migration.
5. Update `src/portal/src/app/(auth)/dashboard/page.tsx` only if any system_admin-specific copy is hard-coded there rather than sourced from `data.kicker`/`data.title`/`data.line` (current read of `page.tsx` shows it already renders whatever the API returns — likely no further frontend edit needed).
6. Rewrite the system_admin cases in `tests/test_dashboard_summary.py` and `tests/test_dashboard_summary_roles.py` to assert the new shape.
7. No feature flag — this is a same-endpoint, same-shape-contract (typed) response change gated by `role == "system_admin"`, and only System Admins consume this branch, so a direct cutover is low-risk. Rollback is a straight revert of the `_system_admin_data` function (and the small `statusColor()` addition, which is additive and harmless to leave in place regardless).

## Open Questions

- Should `/api/v1/dashboard/activity` (currently `if role != "tenant_admin": return DashboardActivityResponse(rows=[])`) be extended to serve system_admin's full `audit_events` history too, making `ActivityPanel`'s `expandable` prop meaningful for system_admin? Leaning yes since `AuditService.list_events` already paginates — but deferred to confirm scope with the proposal's open question before committing tasks.
