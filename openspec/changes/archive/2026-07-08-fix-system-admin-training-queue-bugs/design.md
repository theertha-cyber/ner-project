## Context

Training jobs live in per-tenant Postgres schemas (`tenant_<uuid>.training_jobs`), per ADR-001. Every training-job endpoint (`training_jobs.py`) resolves its schema from a `tenant_id` it either reads off the caller's own JWT (Tenant Admin) or accepts as an explicit query parameter (System Admin, since System Admins have no home tenant to default to). That query-parameter path was implemented on the backend (`get_training_job`, `list_training_jobs` both branch on `role == "system_admin"`) but never wired up on the frontend: `TrainingJobResponse` doesn't return `tenant_id`, so nothing in the portal has a value to send back. The result: System Admin list always degrades to `items: []`, and System Admin detail always 400s.

Separately, the portal keeps a single page-level `QueryClient` (`layout.tsx`) that outlives login/logout, and `logout()` never clears it — meaning cached data from one session (any role, any tenant) can render in the next session until a background refetch overwrites it.

Separately again, `dashboard.py`'s `_system_admin_data()` already follows ADR-001's expectation that "cross-tenant reporting requires explicit cross-schema queries" — it loops over tenant schemas directly. But it has no per-iteration transaction recovery, so one bad schema poisons the shared `AsyncSession` for the rest of the request; every later query (across all tenants, across all three metrics it computes) silently fails via a blanket `except: pass`. ADR-001 also notes a "dedicated reporting schema with controlled cross-schema access" as the intended mitigation for System Admin reporting — that schema does not exist in this codebase today, and introducing it is out of scope for this bug fix (see Open Questions).

## Goals / Non-Goals

**Goals:**
- System Admin can open a training job's detail from the Training Queue page without a 400.
- System Admin can approve/reject/cancel a job using that job's actual owning tenant, not their own (empty) tenant.
- System Admin's Training Queue list shows real jobs, not an unconditional empty list.
- A role/session switch in the same browser tab cannot render another session's cached data.
- One tenant schema failing a query during dashboard aggregation does not blank out every other tenant's stats.

**Non-Goals:**
- Building the "dedicated reporting schema" ADR-001 gestures at for System Admin cross-tenant reads. This fix keeps the existing per-schema-loop pattern (already used by `dashboard.py`) and applies it consistently; introducing a reporting schema is a larger architectural change tracked as an open question, not part of this fix.
- General React Query cache strategy overhaul (e.g., per-key TTLs, selective invalidation policy). This fix only ensures logout leaves no stale data behind.
- Changing the underlying tenant schema-per-tenant isolation model.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via per-tenant Postgres schemas; System Admin cross-tenant reads require explicit cross-schema queries; no query may omit tenant scope | The `tenant_id` fix must keep the schema resolved from an explicit tenant value at every call site — never a query that spans schemas implicitly. The list-endpoint fix (aggregation or selector) must still issue one explicitly-scoped query per tenant schema, matching the existing `dashboard.py` pattern. |

## Decisions

### Decision 1: Surface `tenant_id` on the training job response and thread it end-to-end

**Choice:** Add `tenant_id: str` to `TrainingJobResponse` and `TrainingJobListResponse` items (backend), add it to the portal's `TrainingJob` type, and use it as the source of truth for the job's owning tenant everywhere downstream: `useTrainingJob(id, tenantId?)` appends `?tenant_id=` only when the caller is `system_admin` (Tenant Admin keeps using their own JWT-derived tenant, unchanged), and `JobActions` receives the tenant id from the selected job row instead of from `useAuth()`.

**Rationale:** The data already exists in the DB row (`SELECT *` includes it) and is dropped only at the response-serialization boundary. This is the minimal, most direct fix — no new lookups, no new tables, no schema change.

**Alternatives considered:**
- Look up the owning tenant server-side by scanning all tenant schemas for the job id (a "find which schema has this row" query). Ruled out: this is exactly the kind of implicit cross-schema query ADR-001 warns against, is O(tenants) per detail request, and duplicates work the DB already did once when the job was created.
- Store a global (non-schema-scoped) `job_id → tenant_id` index table. Ruled out as overkill for this fix's scope; revisit only if System Admin cross-tenant lookups become a frequent, latency-sensitive pattern.

### Decision 2: System Admin Training Queue list aggregates pending-approval jobs across tenants by default

**Choice:** When `role == "system_admin"` and no `tenant_id` query param is given, `list_training_jobs` aggregates jobs across all active tenant schemas (same per-schema-loop pattern as `dashboard.py`), scoped by default to actionable statuses (at minimum `pending_approval`, since that's what a "queue" implies) with pagination applied after aggregation. Passing an explicit `tenant_id` still narrows to one tenant's full job history, preserving today's override behavior. Each per-tenant list item carries its own `tenant_id` (Decision 1), so selecting a row always has enough context for the detail/action calls.

**Rationale:** The page is literally labeled "Training Queue" for System Admins (`nav-config.ts`) and "Training Jobs" for Tenant Admins — the product intent is clearly a cross-tenant approval queue for the System Admin role, not a single-tenant view with no way to pick a tenant. The current "always empty" behavior is a regression/gap, not a deliberate design, confirmed by zero System Admin test coverage on this page.

**Alternatives considered:**
- Add a tenant-selector dropdown and keep `list_training_jobs` single-tenant-only. Ruled out as the primary path: it adds new UI surface for a page whose label already promises a cross-tenant queue, and doesn't address the "System Admin needs to review approvals across all tenants at a glance" use case implied by the incident (the admin was reviewing one specific pending job, but the queue's value is seeing all of them). A per-tenant filter can still be layered on top of the aggregated view later (e.g., a filter chip) without conflicting with this decision.
- Leave list behavior unchanged and only fix the detail/action endpoints. Ruled out: it would leave the System Admin queue permanently empty, which is the more visible half of the reported symptom (the user's mental model was "the job showed up in the queue"), and leaves the "how do I even see the job to select it" question unanswered.

### Decision 3: Roll back the shared session after each per-tenant-schema query failure in `_system_admin_data`

**Choice:** Wrap each per-schema query in the existing `try/except` and, on exception, call `await db.rollback()` before continuing to the next schema (or next metric block). This restores the session to a usable state so subsequent queries — same metric, next schema, or a later metric block entirely — are not silently doomed by an earlier failure.

**Rationale:** `rollback()` on an `AsyncSession` is cheap, synchronous-feeling (single round trip), and doesn't require SAVEPOINT bookkeeping since these are read-only `SELECT`s with no partial writes to preserve. It's the smallest change that fixes the cascade.

**Alternatives considered:**
- Use a `SAVEPOINT` per iteration (`session.begin_nested()`) instead of a full rollback. Ruled out: adds nesting complexity with no benefit here since there's no outer write transaction whose earlier work needs preserving — every query in this function is a read.
- Open a fresh `AsyncSession` per tenant schema. Ruled out: much larger blast radius (connection churn, pool pressure under many tenants) for a problem `rollback()` solves directly.

## Risks / Trade-offs

- [Aggregating jobs across all tenant schemas on every System Admin list call adds O(active tenants) queries to a request that previously was O(1) (return empty) or O(1) (single tenant)] → Bound it to the same schemas `dashboard.py` already iterates (active tenants only), and cap/paginate after aggregation; revisit with a real index/materialized view if tenant count grows large enough to matter (same scaling note already in ADR-001).
- [Changing System Admin list semantics from "empty unless tenant_id given" to "aggregated by default" is a breaking behavior change for anything relying on today's shape] → Called out as **BREAKING** in the proposal; audit is limited to this page's own tests (currently zero System Admin coverage) and any e2e/smoke tests touching this endpoint.
- [`queryClient.clear()` on logout discards all cached data, including anything harmless/expensive-to-refetch] → Accepted for this fix per proposal's scope; if refetch cost becomes a UX problem, a follow-up can move to selective key removal instead of a blanket clear.
- [`rollback()` between iterations still leaves the *first* failing query's root cause invisible if the blanket `except: pass` also swallows logging] → Out of scope to fully solve here, but the fix should at minimum keep (or add) error logging on catch so the root cause of a schema failure is diagnosable next time, even though the aggregate response still degrades gracefully.

## Migration Plan

- Backend and frontend changes ship together (the frontend cannot send `tenant_id` until the backend returns it; the frontend cannot show an aggregated queue until the backend supports it) — no phased rollout needed within this change.
- No data migration required — `tenant_id` already exists on every `training_jobs` row.
- Rollback: revert the change; the current (buggy) behavior returns cleanly since no schema/data changes are involved.

## Open Questions

- Should the aggregated System Admin queue eventually move to ADR-001's suggested "dedicated reporting schema with controlled cross-schema access" instead of a live per-request per-schema loop, once tenant count grows? Flagged for a future ADR rather than resolved here — this design keeps the existing (already-precedented) loop pattern.
- Should the aggregated list default to `pending_approval` only, or all statuses with `pending_approval` sorted first? Left as an implementation detail for tasks.md / apply time, informed by what the page's filter tabs already expect (`job-filter-tabs.tsx`).
