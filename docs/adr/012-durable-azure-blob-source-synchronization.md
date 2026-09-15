# 012. Durable Azure Blob Source Synchronization

## Status
Accepted

## Context

FR-004 through FR-008 require manual and 15-minute scheduled Azure Blob synchronization, one missed-schedule catch-up, source-only original retention, replacement semantics, and common downstream processing. Current ingestion is normalized but dispatches OCR via an in-process task, which cannot reliably schedule or recover work. RabbitMQ/Celery is an existing project constraint.

## Decision

Use a contained Azure Blob runtime plus Celery/RabbitMQ source-sync jobs. Jobs use a tenant-bound source object/version ledger and lease for idempotency, invoke existing `NormalizedDocument`/`DocumentIngestionService` common ingestion, and delete temporary Blob bytes on every terminal path. Unchanged versions are skipped; changed versions atomically replace prior derived outputs; missing objects hide their derived records from retrieval. The same job handles manual, scheduled, retry, and catch-up synchronization.

## Alternatives Considered

| Option | Why not chosen |
|---|---|
| Keep in-process asyncio dispatch | Restarts lose scheduled work and no durable catch-up exists. |
| Azure-specific OCR/chunking/extraction paths | Duplicates the common pipeline and violates FR-004. |
| Persist Blob originals durably in MinIO | Violates source-only retention. |

## Consequences

The platform gains durable, observable background work and a contained future-provider seam, at the cost of queue/scheduler operation, ledger migrations, reconciliation, and Azure integration tests. OCR must receive reopenable temporary bytes without retaining originals.

## Related
- Requirement(s): FR-004, FR-005, FR-006, FR-007, FR-008; NFR-RELY-001, NFR-OPS-001
- Supersedes / Superseded by: Depends on `006-training-infrastructure.md` for Celery/RabbitMQ precedent; does not supersede it.

## Revision History

- 2026-09-10 (redo after wind-back): Re-saved unchanged; durable Blob sync decision remains valid. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
