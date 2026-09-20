## MODIFIED Requirements

### Requirement: Idempotent source version reconciliation and temporary retention

The system SHALL use a persistent source object/version ledger, run record, and durable lease to skip unchanged objects, atomically replace a changed object's prior derived outputs, and hide derived records for confirmed-missing objects.

The system SHALL retain synchronized Blob bytes only in temporary working storage and SHALL delete them after every terminal success, failure, or cancellation outcome, **except** where the tenant's content store is its own container and the tenant's retention mode is `platform_blob`, in which case the original SHALL be durably retained in that tenant's container for the life of the document. The constraint being relaxed is durable retention in *platform-operated* storage, not durable retention as such: a synchronized original SHALL NOT be durably retained in platform-operated storage under any configuration.

Accordingly, a synchronization SHALL proceed under `source_only` or `ephemeral` retention for any tenant, and additionally under `platform_blob` retention for a tenant whose content-store selection is executable and resolves to its own container. A synchronization for a tenant recording `platform_blob` whose content store resolves to platform-operated storage SHALL be refused with a finite safe reason class.

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
- **THEN** no durable original Blob copy SHALL remain in platform-operated storage
- **AND** platform-held provenance, state, and derived outputs SHALL follow the applicable outcome.

#### Scenario: A routed tenant may retain a synchronized original durably

- **GIVEN** a tenant whose content store resolves to its own container and whose retention mode is `platform_blob`
- **WHEN** a source object is synchronized and processing reaches a terminal outcome
- **THEN** the original SHALL remain in that tenant's own container
- **AND** no durable original SHALL remain in platform-operated storage

#### Scenario: Platform-stored durable retention still blocks a sync

- **GIVEN** a tenant recording `platform_blob` retention whose content store resolves to platform-operated storage
- **WHEN** a synchronization is triggered
- **THEN** it SHALL be refused with a finite safe reason class
- **AND** no source object SHALL be ingested

#### Scenario: The source container is never written to

- **GIVEN** a tenant with both an `azure_blob` source connection and an `azure_blob_content_store` connection
- **WHEN** a source object is synchronized and its original is durably retained
- **THEN** the original SHALL be written to the content-store container
- **AND** no object SHALL be written to the source container
