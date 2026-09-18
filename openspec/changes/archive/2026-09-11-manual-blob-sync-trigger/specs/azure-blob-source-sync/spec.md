## MODIFIED Requirements

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
