## Context

The training pipeline backend (SM-04) and training approval gate (training-approval-gate) are fully implemented and archived. The training service at `src/training_service/` exposes `GET/POST /api/v1/training-jobs`, `GET /api/v1/training-jobs/{id}`, `POST .../cancel`, `POST .../approve`, and `POST .../reject`. The portal already has routing in `auth-fetch.ts` for `/api/v1/training/*` to `TRAINING_URL`, nav entries in `nav-config.ts` for both `tenant_admin` ("Training Jobs") and `system_admin` ("Training Queue"), and a dashboard integration mapping `training` data source to `/training-jobs`. The page at `src/portal/src/app/(auth)/training-jobs/page.tsx` is a placeholder stub rendering `<PlaceholderScreen title="Training Jobs" />`.

Shared UI primitives already exist: Badge, Spinner, SlideOver, SegmentControl, MiniBar, StatCard. The project uses TanStack Query for server state management and Tailwind CSS for styling.

## Goals / Non-Goals

**Goals:**

- Implement the full `/training-jobs` portal page with filterable job list and detail panel
- Add a submit-job slide-over with hyperparameter form and span-count preflight check
- Add live epoch/loss polling for running jobs (5s refetch interval)
- Add role-gated actions: cancel (tenant_admin), approve/reject (system_admin)
- Wire dashboard `training` data source redirect to `/training-jobs`

**Non-Goals:**

- No backend API changes — all consumed endpoints are already implemented
- No changes to the training pipeline, Celery worker, or model registry
- No changes to nav-config, auth-fetch, or dashboard routing (already configured)
- No mobile-responsive layout (out of scope for this sprint)

## Currently-In-Force ADRs

All ADRs are Proposed. The following constrain this frontend-only change:

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-004 — OpenSpec Governance | Spec-Driven Development with mandatory gates | This change follows the full SDD pipeline: proposal → specs → design → adr → verification → tasks |
| ADR-006 — Training Infrastructure | Celery + RabbitMQ async workers on K8s GPU node pools | The frontend relies on job statuses (`pending_approval`, `queued`, `running`, `completed`, `failed`, `cancelled`, `rejected`) that are managed by the async training worker — no synchronous wait |
| ADR-005 — OpenCode Agent Boundaries | Role-specific agents with bounded tool access | Implementation is scoped to portal frontend only; no backend or infra changes |

## Decisions

### Decision 1: Single page with split-panel layout (list + detail)

**Choice:** A single-page split layout with filterable job list on the left (narrow column) and detail panel on the right (wider column). On mobile/tablet, the detail panel replaces the list view with a back button.

**Rationale:** Matches the established portal UI pattern (used in annotation workspace, documents) and the frontend-ui decomposition document. A single page avoids route complexity and makes state management simpler — the selected job ID is URL search param `?selected=<uuid>`, filter status is `?status=<value>`.

**Alternatives considered:**
- Separate route per job (`/training-jobs/{id}`) — ruled out because it adds navigation overhead and breaks the detail-panel-in-list UX from the mockup.
- Modal/overlay for detail — ruled out because the mockup shows a persistent side panel that stays open while browsing the list.

### Decision 2: Client-side polling with TanStack Query for running jobs

**Choice:** `useQuery` with `refetchInterval: 5000` when the selected job has status `"running"`, and `refetchInterval: false` otherwise.

**Rationale:** The project already uses TanStack Query. Conditional polling is a first-class pattern (`refetchInterval` accepts a function) and avoids custom `setInterval` logic. The 5s interval matches the mockup and decomposition document. Polling stops automatically when the job leaves `running` status.

**Alternatives considered:**
- WebSocket push — overengineered for a polling use case; would require backend changes.
- SSE (Server-Sent Events) — not supported by the existing training API.

### Decision 3: Status timeline derived client-side from job status

**Choice:** A pure function `getTimeline(status: string): TimelineStep[]` that maps the job status to a fixed ordered array of timeline steps with completed/active/pending states. The function encodes the lifecycle: `pending_approval → queued → running → completed | failed`, with `cancelled` and `rejected` as terminal diversion states.

**Rationale:** The timeline is purely presentational — no additional API data needed. A pure function is easy to test and keeps the component simple. The mockup (`dTimeline`) uses the same approach.

**Alternatives considered:**
- Server-returned timeline array — would require backend schema change; unnecessary since the status lifecycle is deterministic.
- Hardcoded timeline in component — harder to test and maintain.

### Decision 4: Span-count preflight via annotation-export endpoint

**Choice:** Fetch `GET /api/v1/annotation-export` and count JSONL lines to determine annotated entity count for the preflight check. Cache the result for the session duration.

**Rationale:** The annotation-export endpoint already exists and returns JSONL with one entity per line. A line count is a reasonable proxy for entity count. The result is cached client-side so repeated opens of the submit slide-over don't re-fetch.

**Alternatives considered:**
- Dedicated span count endpoint — not currently implemented; would require backend work.
- Skip preflight (rely on server-side 422) — worse UX; the mockup explicitly shows the preflight banner before submission.

## Risks / Trade-offs

- [Large JSONL response for tenants with many annotations] → Add a client-side line limit (count first N lines only) or use a HEAD request if the annotation service supports content-length. The preflight is a UX hint only — server-side validation is authoritative.
- [Polling creates load on the training service] → 5s interval for a single selected job is negligible. If the portal has many concurrent users monitoring the same job, consider increasing interval or adding backend caching — out of scope for this change.
- [tenant_id not returned by GET /training-jobs/{id}] → System admin approve/reject may need `tenant_id`. Flagged as open question — if missing, the backend must add it or the system_admin must select a tenant context first.

## Migration Plan

This is a frontend-only change with no database migrations or infrastructure changes. Deploy as part of the standard portal release.

1. Implement the training jobs page component tree and hooks
2. Add unit tests for `getTimeline()` utility, form validation, and query hooks
3. Add component tests for job list, detail panel, submit slide-over
4. Deploy portal build — page is gated by role, no impact on existing users

**Rollback:** Revert the `page.tsx` to the placeholder stub.

## Open Questions

- Does `GET /api/v1/training-jobs/{id}` return `tenant_id`? Needed for approve/reject `?tenant_id=` query param when system_admin acts on another tenant's job.
- Should the span preflight use a dedicated count endpoint or count lines from `GET /api/v1/annotation-export`? Assumption: line count from export for now.
- What is the MLflow tracking URI for the `mlflow_run_url` deep link? Assumption: it's computed server-side and returned in the job response.
