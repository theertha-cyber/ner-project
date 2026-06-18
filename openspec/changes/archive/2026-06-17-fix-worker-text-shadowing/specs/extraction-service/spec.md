## MODIFIED Requirements

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch. For each successfully processed document the worker SHALL persist predicted entities to the `extracted_entities` table with their `run_id`, `entity_id`, `value`, and `confidence`.

#### Scenario: Trigger batch extraction

- **GIVEN** a tenant with a promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1,doc2,doc3`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"
- **AND** a subsequent GET to `/api/v1/extract-batch/{run_id}` SHALL return `status`: "queued"

#### Scenario: Batch extraction persists extracted entities

- **GIVEN** a tenant with a promoted model and one document in `processed` status
- **WHEN** batch extraction completes for that document
- **THEN** the extraction run SHALL have `processed_count = 1` and `failed_count = 0`
- **AND** one or more rows SHALL exist in `extracted_entities` linked to the `run_id`
- **AND** each row SHALL have non-null `entity_id`, `value`, and `confidence`

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
