## Context

FR-004–FR-008 and NFR-RELY-001 require manual and 15-minute scheduled Azure Blob synchronization with one missed-schedule catch-up, idempotent version reconciliation, and source-only original retention through the common ingestion pipeline. Today OCR dispatch is an in-process `asyncio.create_task` (`src/document_service/ingestion/dispatcher.py:18-26`) that cannot survive a restart or recover missed work; the ingestion operation already accepts pull sources (`REOPENABLE` acquisition, `source_only` retention, source identity columns) but no pull source exists and `SourceOnlyNotSupported` is raised at processing time. The CAP-2 control plane supplies active-connection gating. Azure SDK knowledge must stay contained, live Azure verification stays deferred (fixtures/fakes per `run.provisioning`), and the touched OCR failure paths must stop emitting tracebacks and interpolated exception payloads.

## Goals / Non-Goals

**Goals:**

- Run one tenant-bound durable sync use case for manual, scheduled, retry, and catch-up synchronization through Celery/RabbitMQ, using the same code path for all four triggers.
- Submit every eligible Blob object as a `NormalizedDocument` through `DocumentIngestionService.ingest()` with no Azure-specific OCR, NER, chunking, extraction, or retrieval branches.
- Keep idempotency in a tenant-schema source object/version ledger plus run record and durable lease: skip unchanged versions, atomically replace changed objects' derived outputs, hide confirmed-missing objects from retrieval.
- Hold Blob bytes in temporary working storage only and delete them on every terminal success, failure, or cancellation path.
- Remediate the touched OCR failure telemetry to safe structured error classes.

**Non-Goals:**

- S3, SharePoint, or any other source provider; persistent external originals; external vector stores.
- Platform upload, platform retrieval, or platform SQL chat changes beyond the missing-source retrieval exclusion.
- Live Azure integration activation, staging/production deployment, or a Vault resolver.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant schemas isolate content; public holds tenant-bound non-content control-plane records. | Sync state lives in the tenant schema; every operation is tenant-scoped server-side; queued payloads never assert tenant identity. |
| ADR-012 | Contained Azure runtime plus Celery/RabbitMQ jobs, ledger/lease idempotency, common ingestion, temp-only bytes. | No Azure branches downstream; unchanged skipped, changed replaced, missing hidden; bytes deleted on every terminal path. |
| ADR-006 | Celery/RabbitMQ is the durable-work precedent. | Sync jobs follow the extraction-service Celery pattern (identity-only payloads, JSON serialization). |

## Decisions

### Decision 1: One sync use case, four triggers, identity-only queued payloads

**Choice:** A `run_blob_sync(tenant_id, connection_id, trigger)` Celery task executes the whole synchronization; the beat scheduler enqueues active Azure Blob connections every 15 minutes, the gateway manual trigger enqueues the same task, retries re-enqueue it, and a catch-up check enqueues one run when the last successful run is older than two cadences. The payload carries only tenant, connection, and trigger class — bytes, references, and versions are re-read from the ledger and the provider at execution time.

**Rationale:** One path means retry and catch-up inherit the same idempotency and reconciliation semantics instead of reimplementing them; identity-only payloads make every trigger replayable after a restart, matching the dispatcher's documented precondition.

**Alternatives considered:**
- Separate tasks per trigger — ruled out because four implementations of ledger/lease handling drift apart.
- In-process asyncio scheduling — ruled out because restarts lose scheduled and in-flight work with no catch-up.

### Decision 2: Ledger, lease, and run record in the tenant schema

**Choice:** Three tenant-schema tables: `azure_blob_sync_runs` (one row per execution with trigger, outcome class, correlation timestamps), `azure_blob_source_objects` (per source object: opaque identity, last-seen version, linked document id, missing/confirmed-missing state), and `azure_blob_sync_leases` (one row per connection held via atomic compare-and-set with expiry, released on every terminal path). The lease is acquired before enumeration and blocks overlapping runs; the ledger key is `(connection_id, object_identity)` scoped by the tenant schema.

**Rationale:** Tenant-schema placement keeps sync state under ADR-001 isolation with zero cross-tenant query surface; the lease makes overlap prevention durable rather than process-local.

**Alternatives considered:**
- Public-schema sync state — ruled out because ledger rows link to tenant documents and belong with the content they describe.
- Advisory/lock-table-free overlap control — ruled out because two API replicas would double-ingest.

### Decision 3: Replace-by-reprocessing with retrieval hiding for missing objects

**Choice:** A changed version ingests a new document through the common pipeline and, in the same transaction that marks the new document live, marks the prior linked document superseded and purges its derived outputs via the existing `_purge_derived_data` path; retrieval excludes superseded and confirmed-missing documents through a source-state filter on the retrievers. Missing objects are only confirmed after two consecutive absent enumerations, then marked non-retrievable without deleting provenance.

**Rationale:** Atomic replace keeps retrieval from ever serving a mix of old and new derived data; two-confirmation missing avoids hiding documents on a transient listing failure.

**Alternatives considered:**
- In-place document update — ruled out because derived outputs (chunks, embeddings, extractions) are keyed to document identity.
- Immediate hide on first absence — ruled out because a single failed listing would silently remove live content from answers.

### Decision 4: Temporary working storage with guaranteed deletion

**Choice:** Acquired bytes are written to the working content store under a sync-scoped reference and removed in a `finally` around terminal completion; the sync job never calls the durable store and never persists a reference outside the run's scope. OCR resolves sync documents through a reopenable adapter registered for the run that re-reads from the working reference while it exists.

**Rationale:** The working store already has bounded retention/expiry as a backstop, and `finally`-scoped deletion makes "no durable original remains" a structural property rather than a per-path discipline.

**Alternatives considered:**
- Durable MinIO objects with post-run deletion — ruled out by the source-only retention constraint; a crash between write and delete would leave a durable copy.
- Passing bytes through the queued payload — ruled out by size limits and JSON serialization.

## Risks / Trade-offs

- [Listing lies: transient Azure enumeration failure looks like mass deletion] → two-confirmation missing rule plus a run-outcome class distinguishing listing failure from genuine absence.
- [Lease holder crashes] → lease expiry with a bounded TTL lets the next scheduled run proceed; the ledger makes re-execution idempotent.
- [Changed-object replace races a retry of the old version] → ledger version compare-and-set under the lease serializes decisions per connection.
- [Live Azure unavailable in this run] → provider runtime behind a seam with a fixture/fake implementation; activation tests stay deferred and the capability remains inactive until approved resources exist.
- [OCR remediation touches shared failure paths] → change only the two identified unsafe emissions to structured classes; no behavior change to success paths.

## Migration Plan

1. Add tenant-schema sync ledger/run/lease tables via an additive alembic migration; no backfill (new tables, empty by definition).
2. Deploy the provider runtime, sync task, and scheduler with no active connections: nothing enqueues until CAP-2 activation marks a Blob connection active.
3. Keep the capability inactive (no live Azure) until connection test and activation evidence pass per CAP-2.
4. Roll forward with compatible migrations; destructive rollback of ledger tables is not assumed — rerun reconciliation instead.

## Open Questions

- Live Azure Blob activation tests require approved test resources; until then the sync path is verified with fixtures/fakes and stays inactive.
- Exact beat-schedule deployment topology (worker/scheduler placement) is settled in CAP-6's Compose delivery.
