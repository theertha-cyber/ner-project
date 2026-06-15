## Context

The training service currently allows any tenant admin to submit a training job that immediately gets enqueued to Celery (`send_task` called in the POST handler). There is no approval step. The system admin role already exists in the auth system (`src/gateway/models/__init__.py` defines `system_admin`, middleware decodes the role from JWT, and gateway already has `require_system_admin`). The training service is a separate FastAPI service that uses its own copy of the role-checking logic.

The `training_jobs` table currently has `status VARCHAR(20)`, which accommodates both new statuses (`pending_approval` = 17 chars, `rejected` = 8 chars). The statuses used today are: `queued`, `running`, `completed`, `failed`, `cancelled`.

## Goals / Non-Goals

**Goals:**
- Tenant admin submits a training job → it lands in `pending_approval` (no Celery task enqueued)
- System admin approves → job moves to `queued` and Celery task is enqueued
- System admin rejects → job moves to `rejected` (with optional reason)
- System admin can view all `pending_approval` jobs across all tenants
- Cancel endpoint also works for `pending_approval` (clean up without a Celery task)

**Non-Goals:**
- Not adding email/push notifications when jobs need approval
- Not adding auto-approval rules or SLAs for system admin review time
- Not building a dedicated admin UI — the API endpoints suffice for now
- Not modifying the Celery worker — it only reads `queued` jobs, unchanged

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Per-tenant database schemas | Training service uses tenant-scoped schema queries; approve/reject must operate within the same schema |
| ADR-004 | OpenSpec SDD with mandatory artifacts | This change follows the full pipeline |
| ADR-006 | Celery-based async GPU workers | Celery task enqueue moves from POST to approve handler; worker behaviour unchanged |

## Decisions

### Decision 1: System admin guard reuses existing role pattern

**Choice:** Add a `require_system_admin` dependency in `training_jobs.py` (not imported from gateway — the training service is a separate microservice).

**Rationale:** The training service already has a local `require_tenant_admin` function. Adding a parallel `require_system_admin` keeps the service self-contained and consistent. The gateway's version is not importable (it's in a different service's package tree).

**Alternatives considered:**
- Import from `src.gateway.dependencies` — creates a cross-service dependency, not clean for separate deployments
- Extract shared auth into `src.shared` — out of scope for this change

### Decision 2: Approve/reject endpoints are tenant-scoped but system-admin-guarded

**Choice:** The endpoints are `POST /api/v1/training-jobs/{job_id}/approve` and `POST /api/v1/training-jobs/{job_id}/reject`. They require `system_admin` role. They take a `tenant_id` query parameter (since the system admin is not scoped to one tenant in their JWT).

**Rationale:** The system admin JWT likely has no `tenant_id` or has `tenant_id: "system"`. The middleware enforces a valid tenant_id lookup. Rather than refactor the middleware, we let the endpoint accept an explicit `tenant_id` parameter. Alternatively, for simplicity, system admin can impersonate a tenant by calling with a tenant-scoped token.

**Alternatives considered:**
- System admin has `tenant_id: null` in JWT and we special-case it — more complex middleware change
- Use a query param `?tenant_id=...` to scope the approve/reject — clearest approach

### Decision 3: `pending_approval` is cancellable by tenant admin

**Choice:** The cancel endpoint already allows `queued` and `running`. We extend it to also allow `pending_approval`. For `pending_approval`, there's no Celery task to revoke, so we skip the `celery_app.control.revoke` call.

**Rationale:** Tenant admins should be able to withdraw a submission before it's approved. This is mirrored in the existing cancel flow — just a status update, no task revocation needed.

### Decision 4: List endpoint shows `pending_approval` and `rejected` jobs alongside others

**Choice:** No change to the list endpoint — it already accepts a `status` query param. System admin can filter by `status=pending_approval` to see all pending jobs. The endpoint is tenant-scoped, so a system admin would need to iterate tenants or use a future cross-tenant admin endpoint.

**Rationale:** Minimal code change, and the existing filter + pagination already works. A cross-tenant "show all pending" endpoint is out of scope for this change.

## Risks / Trade-offs

- [System admin JWT may lack `tenant_id` for the middleware check] → Use a dedicated token or add a `X-System-Admin` bypass in middleware. The simplest path: issue the system admin a token with `tenant_id` set to their own tracking tenant (e.g. a "system" tenant).
- [Existing tests need updating for new status transitions] → All existing test scenarios that assert `queued` directly after POST must be updated to assert `pending_approval` and follow with an approve call.
- [Status enum widening could break downstream consumers] → No existing consumers beyond the API; the response model already uses a freeform `str` field.

## Migration Plan

1. Add `require_system_admin` to training_jobs.py
2. Modify `create_training_job` to NOT call `celery_app.send_task` — insert with `status='pending_approval'` and `celery_task_id=NULL`
3. Add `POST /approve` endpoint — validates status is `pending_approval`, calls `send_task`, updates status to `queued` with the task ID
4. Add `POST /reject` endpoint — validates status is `pending_approval`, updates status to `rejected` with optional reason
5. Update cancel endpoint to also accept `pending_approval`
6. Update tests — all existing scenarios, plus approve/reject scenarios
7. Add `rejection_reason` column to `training_jobs` table (nullable TEXT)
8. Add migration for existing tenant schemas

## Open Questions

- Should the system admin JWT have `tenant_id=null` (no tenant) or a specific tracking tenant? This affects how the middleware validates. Currently the middleware returns 401 if `tenant_id` is missing. We may need a middleware exemption for system admin tokens.
