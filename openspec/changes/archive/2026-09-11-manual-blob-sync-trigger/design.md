## Context

Azure Blob synchronization runs only on the scheduler's 15-minute per-connection cadence (`src/document_service/blob_sync/scheduler.py`, `tasks.py:blob_sync_tick`). The durable job itself already supports a `manual` trigger class (`sync.py:trigger_manual_sync`, `TRIGGER_MANUAL`), and the spec already requires that a manual trigger enqueues the same job — but no gateway route or portal control calls it, so the helper is unwired dead code. Tenant administrators who add or fix source content must wait for the next tick.

Constraints: tenant isolation and safe-telemetry invariants (AGENTS.md §2.3–2.4) apply to every new surface; the control-plane conventions in `src/gateway/api/v1/data_sources.py` (JWT tenant binding, `require_tenant_admin`, `_mutate` idempotency wrapper, finite safe error codes) must be followed; no new migrations or metric families are desired.

## Goals / Non-Goals

**Goals:**

- Tenant-admin-only `POST /api/v1/data-sources/{id}/sync` that enqueues the existing durable `blob_sync_run` job with trigger class `manual`.
- Portal "Sync now" control on the Blob connection detail Sync activity panel with safe pending/success/blocked/error states.
- Full reuse of existing guards: active-lifecycle gating, durable lease overlap protection, identity-only payload, declared `manual`-trigger telemetry.

**Non-Goals:**

- No scheduler cadence change; no automatic catch-up semantics change.
- No new ledger/run-record schema or migration.
- No sync for PostgreSQL connections (contract state governs chat; schedule already exempt).
- No status polling loop or "sync all connections" bulk action.
- No new Prometheus metric families (the existing `blob_sync` family already labels by trigger class).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-011-tenant-scoped-azure-connection-control-plane | Tenant-scoped control plane: JWT tenant binding, tenant-admin-only mutations, idempotency, atomic one-active-per-provider, finite safe outcomes | New sync action MUST bind tenant from JWT, require tenant admin, use the `_mutate` idempotency wrapper, and return only finite safe codes |
| ADR-012-durable-azure-blob-source-synchronization | One durable Celery/RabbitMQ sync job with ledger, lease, identity-only payload for manual/scheduled/retry/catch-up | Manual trigger MUST enqueue the same `blob_sync_run` task with identity-only args; lease and active checks stay in the worker |
| ADR-006-training-infrastructure (Proposed) | Celery + RabbitMQ async worker precedent | Gateway enqueues through the broker; execution stays in the worker, never inline in the request |

## Decisions

### Decision 1: Gateway route enqueues via broker, never runs inline

**Choice:** `POST /api/v1/data-sources/{connection_id}/sync` validates (tenant binding, admin role, Blob provider, active status) then calls the existing `enqueue_sync(tenant_id, connection_id, TRIGGER_MANUAL)` path (`tasks.py:43`) and returns 202 with the safe trigger outcome. Execution — including the authoritative active re-check and lease acquisition — stays in `run_sync`.

**Rationale:** Preserves ADR-012 durability (survives gateway restart) and keeps request latency bounded; the route stays free of Azure SDK knowledge and broker topology beyond the existing send-task seam.

**Alternatives considered:**
- Run sync inline in the request — ruled out: unbounded latency, loses durability, duplicates worker logic in the gateway.
- Synchronous lease pre-check in the route to return lease-held immediately — ruled out: racy (lease is worker-side state); the execution-side lease record plus status read is the source of truth.

### Decision 2: Manual bypasses cadence, keeps every other guard

**Choice:** The route performs no `evaluate_connection` cadence check. Active-lifecycle gating is checked twice: fast rejection at the route (safe inactive code) and authoritatively in `run_sync` (defense in depth against state races). Lease-held at execution records the finite lease-held outcome visible via the existing status read.

**Rationale:** Cadence exists to pace the scheduler, not to rate-limit an explicit operator intent; every safety guard (active, lease, identity-only payload, safe telemetry) is orthogonal to cadence and stays on.

**Alternatives considered:**
- Apply cadence to manual too (reject if recently synced) — ruled out: defeats the purpose (operator just fixed source content); lease already prevents overlap abuse.

### Decision 3: Reuse the `_mutate` idempotency wrapper and safe-code shape

**Choice:** The new route goes through `_mutate` (fresh `Idempotency-Key` per trigger intent; same key+body replays without a duplicate enqueue) and the `_CODE_STATUS`/`_CODE_HINTS` safe-error shape. New finite codes: `INACTIVE_CONNECTION` (409) and `UNSUPPORTED_PROVIDER` (409) for the two rejection paths; broker-unavailable maps to the existing `CONNECTION_TEST_UNAVAILABLE`-style 503 pattern with a new `SYNC_UNAVAILABLE` code if needed.

**Rationale:** Zero new auth/error conventions for clients and reviewers to learn; consistent with every other control-plane mutation.

**Alternatives considered:**
- Key-optional trigger endpoint — ruled out: inconsistent with control-plane contract; double-clicks would enqueue duplicates up to the lease.

### Decision 4: Portal control is a thin caller with refreshed status, no polling

**Choice:** "Sync now" button in `SyncActivitySummary` (Blob only, enabled iff `status === "active"`), one fresh `Idempotency-Key` per click via the existing `useDataSourceMutation` pattern, then a single status refresh. States: pending → enqueued / already-running (lease-held) / blocked / safe error. No polling loop.

**Rationale:** Matches the existing lifecycle-panel UX patterns with minimal new state; the sync itself is async and its progress is already visible via last-run status.

**Alternatives considered:**
- Polling run status to completion — ruled out: no run-streaming API exists; adds timer/UX complexity out of proportion to the need.

## Risks / Trade-offs

- [Rapid repeated clicks enqueue repeated runs up to the lease] → Fresh idempotency key per click plus worker-side lease serializes execution; extras record lease-held without ingesting.
- [Operator confuses lease-held with failure] → Portal maps the lease-held outcome to an explicit "sync already running" notice, distinct from error styling.
- [Broker down at trigger time] → Route returns the finite 503 safe code; nothing is partially enqueued (validation precedes enqueue).
- [Race: connection paused between route check and worker start] → Worker re-checks active state and skips with the inactive outcome; safe by construction.

## Migration Plan

1. Deploy worker + gateway together (route references the existing task name; no ordering hazard beyond normal rollout).
2. Deploy portal; button appears only on Blob detail views.
3. Rollback: revert gateway route and portal control independently — scheduler, ledger, and existing routes are untouched. No data migration in either direction.

## Open Questions

- Exact 202 response body shape (run descriptor vs. trigger-accepted envelope) — propose `{ connection_id, trigger: "manual", outcome: "enqueued", ...timestamps }` reusing `read_sync_status` fields; confirm in review.
- Whether `SYNC_UNAVAILABLE` needs a new declared code or reuses an existing 503 code — confirm against the control-plane code registry in review.
- No in-force ADR revisits proposed.
