## ADDED Requirements

### Requirement: Content-free document registry in the control plane

The system SHALL maintain `public.tenant_document_registry` with one row per document for every tenant on either data plane, holding only: document id, tenant id, source type, status, file size in bytes, checksum, retention mode, created and updated timestamps. The registry SHALL NOT hold filename, MIME-derived names, storage references, error messages, OCR text, or any derived content. Existing documents in platform tenant schemas SHALL be backfilled.

#### Scenario: Registry schema holds no content columns

- **GIVEN** the migration creating `public.tenant_document_registry`
- **WHEN** its columns are inspected
- **THEN** it SHALL contain no `filename`, `storage_uri`, `blob_path`, `error_message`, or text-content column

#### Scenario: Existing documents are backfilled

- **GIVEN** a platform tenant with 5 documents before this change
- **WHEN** the migration is applied
- **THEN** the registry SHALL contain 5 rows for that tenant with matching id, status, size, and checksum

### Requirement: The registry follows the tenant store, which stays authoritative

The system SHALL write or update the registry row after the corresponding tenant-store document write commits, on ingestion, every status transition, and deletion. The tenant-store `documents` row SHALL remain authoritative. A periodic reconciliation SHALL correct registry rows that disagree with a reachable tenant store and SHALL skip unreachable stores without deleting their registry rows.

#### Scenario: Status transitions reach the registry

- **GIVEN** a residency tenant's document moving from `processing` to `processed`
- **WHEN** the OCR worker commits the status in the tenant store
- **THEN** the registry row SHALL show `processed`

#### Scenario: Drift is reconciled

- **GIVEN** a registry row showing `processing` for a document whose tenant-store row is `processed`
- **WHEN** reconciliation runs with the store reachable
- **THEN** the registry row SHALL be updated to `processed`

#### Scenario: Unreachable store does not erase registry rows

- **GIVEN** a residency tenant whose store is unreachable
- **WHEN** reconciliation runs
- **THEN** that tenant's registry rows SHALL be unchanged

### Requirement: Quotas and fleet counts use the registry

Document quota enforcement, system-admin tenant document counts, and tenant dashboard document totals SHALL be computed from the registry, so they are available without querying a tenant store. Views that display filenames SHALL read them from the tenant store and SHALL fail closed per the failure-isolation rules when it is unavailable.

#### Scenario: System admin sees counts during a tenant outage

- **GIVEN** a residency tenant with 12 registered documents and an unreachable store
- **WHEN** the System Admin views the tenant list
- **THEN** the tenant's document count SHALL be 12

#### Scenario: Quota uses the registry

- **GIVEN** a residency tenant at `max_documents` according to the registry
- **WHEN** a user uploads another document
- **THEN** the upload SHALL be rejected by quota before any tenant-store write
