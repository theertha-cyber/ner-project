## Why

Azure Blob connections sync on a 15-minute scheduled cadence with no operator-initiated path. When a tenant administrator adds or fixes source content, the only recourse is to wait for the next tick, which slows validation, troubleshooting, and time-sensitive ingestion.

## What Changes

- Add a tenant-admin-only manual sync trigger: `POST /api/v1/data-sources/{connection_id}/sync` that enqueues the same durable `blob_sync_run` job the scheduler uses with trigger class `manual`.
- Enforce existing guards on the manual path: active-lifecycle gating, tenant binding from JWT, durable lease overlap protection (lease-held returns a finite outcome, no duplicate enumeration), and identity-only enqueue payload.
- Return and record only finite safe outcome classes, identifiers, and correlation timestamps; emit the existing declared `manual`-trigger telemetry; no bytes, endpoints, credentials, provider diagnostics, or raw exceptions on any path.
- Add a "Sync now" control on the connection detail Sync activity panel with pending, success, lease-held, blocked (inactive), and safe-error states; reuse the existing idempotency-key and safe-error conventions.

## Capabilities

### New Capabilities

- None. This change wires up behavior already specified (`azure-blob-source-sync` requires the manual trigger) through existing surfaces.

### Modified Capabilities

- `azure-blob-source-sync`: clarify the manual trigger's enqueue, lease-held, and inactive-connection semantics now that a real caller exists.
- `tenant-data-source-control-plane`: add the tenant-admin-only manual sync action with tenant binding, idempotency, and safe outcome codes.
- `tenant-data-source-portal`: add the "Sync now" control and its safe pending/success/blocked/error states to the connection detail view.

## Impact

- Affected code: `src/gateway/api/v1/data_sources.py` (new route), `src/document_service/blob_sync/sync.py` + `tasks.py` (enqueue wiring), portal `lifecycle.tsx`, `use-data-sources.ts`, `data-sources.ts` lib.
- APIs: one new endpoint `POST /api/v1/data-sources/{id}/sync`; no changes to existing routes, migrations, ledger schema, or scheduler cadence.
- Dependencies/systems: reuses the existing Celery/RabbitMQ `blob_sync_run` task and `blob_sync` telemetry family; no new infra.

## Open Questions

- Should the manual trigger require an `Idempotency-Key` like other mutations, or return 202 with a run identifier for status polling? (Assumption: follow the existing `_mutate` idempotency wrapper and return the safe run/trigger outcome.)
- Should a manual trigger bypass the 15-minute cadence check entirely (always enqueue, lease permitting)? (Assumption: yes — cadence gating applies to the scheduler only; manual always enqueues when active and lease-free.)
