# azure-blob-source-sync Specification

## Purpose
TBD - created by archiving change cap-3-durable-azure-blob-synchronization-and-source-reconciliation. Update Purpose after archive.
## Requirements
### Requirement: Common durable Blob ingestion

The system SHALL execute manual, 15-minute scheduled, retry, and one missed-schedule catch-up Azure Blob synchronization through one tenant-bound durable job that submits each eligible object as a `NormalizedDocument` to `DocumentIngestionService`. A manual synchronization SHALL be triggerable through `POST /api/v1/data-sources/{connection_id}/sync` and SHALL bypass the 15-minute cadence check while keeping all other guards. Derived document outputs SHALL be stored in the platform tenant schema without Azure-specific OCR, NER, chunking, extraction, or retrieval branches. Only connections with an active CAP-2 lifecycle state SHALL be synchronized, and the queued payload SHALL carry only tenant, connection, and trigger identity.

#### Scenario: New object is synchronized

- **GIVEN** an active tenant Blob connection with a newly discovered supported object
- **WHEN** the sync job processes that object
- **THEN** its bytes SHALL enter the existing common ingestion pipeline
- **AND** derived document outputs SHALL be stored in the platform tenant schema without Azure-specific downstream branches.

#### Scenario: Manual trigger runs the same job as the schedule

- **GIVEN** an active tenant Blob connection
- **WHEN** a tenant administrator calls `POST /api/v1/data-sources/{connection_id}/sync`
- **THEN** the system SHALL enqueue the same durable sync job the scheduler uses with a manual trigger class
- **AND** the cadence check SHALL NOT block the manual run.

#### Scenario: Scheduled cadence with missed-schedule catch-up

- **GIVEN** an active tenant Blob connection whose last successful run is older than two 15-minute cadences
- **WHEN** the scheduler evaluates that connection
- **THEN** the system SHALL enqueue exactly one catch-up run for it.

#### Scenario: Inactive connection never syncs

- **GIVEN** a tenant Blob connection without an active lifecycle state
- **WHEN** the scheduler evaluates or a manual trigger names that connection
- **THEN** no sync job SHALL execute for it.

#### Scenario: Overlapping runs are prevented by the durable lease

- **GIVEN** a sync run holding the connection lease
- **WHEN** a second trigger fires for the same connection
- **THEN** the second run SHALL NOT enumerate or ingest
- **AND** it SHALL record a finite lease-held outcome.

### Requirement: Idempotent source version reconciliation and temporary retention

The system SHALL use a persistent source object/version ledger, run record, and durable lease to skip unchanged objects, atomically replace a changed object's prior derived outputs, and hide derived records for confirmed-missing objects. The system SHALL retain Blob bytes only in temporary working storage and SHALL delete them after every terminal success, failure, or cancellation outcome.

#### Scenario: Retry or unchanged object

- **GIVEN** a source object whose ledger version matches the enumerated version
- **WHEN** a synchronization retries or observes that unchanged version
- **THEN** it SHALL not create duplicate documents, provenance, spans, chunks, embeddings, or extraction outputs.

#### Scenario: Changed object is atomically replaced

- **GIVEN** a source object whose enumerated version differs from the ledger version
- **WHEN** the sync job processes that object
- **THEN** the new version SHALL be ingested as a new document through the common pipeline
- **AND** the prior linked document's derived outputs SHALL be purged and hidden in the same transaction that relinks the ledger to the new document.

#### Scenario: Deleted source object

- **GIVEN** a previously synchronized source object confirmed missing across two consecutive successful enumerations
- **WHEN** reconciliation records the confirmation
- **THEN** its derived records SHALL be excluded from retrieval
- **AND** its provenance SHALL be retained.

#### Scenario: Single absence does not hide content

- **GIVEN** a previously synchronized source object absent from one enumeration that followed or preceded a listing failure
- **WHEN** reconciliation evaluates that absence
- **THEN** its derived records SHALL remain retrievable until a second consecutive successful enumeration confirms the absence.

#### Scenario: Processing reaches a terminal outcome

- **GIVEN** an acquired Blob object whose processing finishes, fails, or is cancelled
- **WHEN** the terminal outcome is recorded
- **THEN** no durable original Blob copy SHALL remain in MinIO
- **AND** platform-held provenance, state, and derived outputs SHALL follow the applicable outcome.

### Requirement: Tenant-scoped safe sync status

The system SHALL record per-run trigger, outcome class, and correlation timestamps on the tenant-bound sync run record, SHALL expose only finite safe outcome classes and identifiers on sync status reads, and SHALL emit declared finite structured telemetry for every terminal sync outcome without content, endpoints, credentials, provider diagnostics, or raw exceptions.

#### Scenario: Sync status exposes only safe classes

- **GIVEN** a completed sync run with any outcome
- **WHEN** its status is read
- **THEN** the response SHALL contain only finite outcome classes, identifiers, and correlation timestamps.

#### Scenario: Failed listing records a distinct outcome

- **GIVEN** a sync run whose source enumeration fails
- **WHEN** the run terminates
- **THEN** it SHALL record a listing-failure outcome class distinct from genuine absence
- **AND** no object SHALL be marked missing on that run.

