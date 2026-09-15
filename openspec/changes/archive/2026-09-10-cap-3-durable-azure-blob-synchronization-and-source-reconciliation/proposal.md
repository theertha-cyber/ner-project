## Why

Active tenant Azure Blob connections have no synchronization path: ingestion dispatches OCR as an in-process task that cannot schedule, retry, or recover work across restarts, so FR-004–FR-008 cannot be met while leaving platform uploads unchanged.

## What Changes

- Add a contained Azure Blob provider runtime that enumerates source objects, acquires bytes into temporary working storage only, and submits each eligible object as a `NormalizedDocument` to the existing `DocumentIngestionService` common ingestion pipeline.
- Execute one tenant-bound durable Celery/RabbitMQ sync job for manual, 15-minute scheduled, retry, and one missed-schedule catch-up synchronization, guarded by a persistent source object/version ledger, run record, and durable lease.
- Reconcile source versions idempotently: skip unchanged objects, atomically replace changed objects' prior derived outputs, and hide derived records of confirmed-missing objects from retrieval without retaining Blob originals.
- Delete temporary Blob bytes on every terminal success, failure, or cancellation path and remediate touched OCR failure telemetry to safe structured error classes.

## Capabilities

### New Capabilities

- `azure-blob-source-sync`: Durable tenant-bound Blob synchronization runtime, ledger/lease/run state, version reconciliation, source-only temporary retention, and manual/scheduled sync trigger and safe status surfaces.

### Modified Capabilities

- `document-ingestion-boundary`: Admit the Azure Blob sync runtime as a configured source submitting `NormalizedDocument` through the common ingestion boundary with no Azure-specific downstream branches.
- `retrieval-core`: Exclude derived records of confirmed-missing Azure Blob source objects from retrieval results.
- `telemetry-tenant-safety`: Require safe structured error classes on the touched OCR failure paths instead of tracebacks or interpolated exception payloads.

## Impact

Affected areas include the document service sync worker and scheduler, the contained Azure Blob provider runtime, tenant-schema sync ledger migrations, the common ingestion boundary contract, retrieval source-state filtering, OCR failure telemetry, and safe structured sync-outcome metrics. Platform upload authorization, downstream OCR/NER/chunking/extraction/retrieval semantics, and the CAP-2 control plane are preserved; no durable Blob originals are stored and no S3/SharePoint providers are added.

## Open Questions

- Per-tenant customer network and governance activation evidence remains a CAP-2 prerequisite; a source without it stays inactive and never syncs.
- Live Azure Blob verification stays deferred until approved test resources exist; integration tests use fixtures/fakes per `run.provisioning`.
