## MODIFIED Requirements

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch.

#### Scenario: Trigger batch extraction

- **GIVEN** a tenant with a promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1,doc2,doc3`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"
- **AND** a subsequent GET to `/api/v1/extract-batch/{run_id}` SHALL return `status`: "queued"

#### Scenario: Batch extraction skips already-extracted documents

- **GIVEN** a document that has been extracted with the current active model version
- **WHEN** batch extraction is triggered
- **THEN** the document SHALL be skipped
- **AND** the extraction run report SHALL indicate it was skipped

#### Scenario: Batch extraction for tenant with no promoted model

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch`
- **THEN** the response SHALL have status 202
- **AND** the run status SHALL eventually become "failed"
- **AND** the error SHALL be queryable via the status endpoint

### Requirement: Get extraction run status

The system SHALL expose an endpoint to query the status of a batch extraction run, including progress (documents processed, skipped, failed) and completion state. The run record SHALL be stored in the `extraction_runs` table with all status fields populated.

#### Scenario: Get extraction run status

- **GIVEN** a batch extraction run in "running" status
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`

#### Scenario: Get extraction run status of completed run

- **GIVEN** a completed batch extraction run
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "completed" and `completed_at`
