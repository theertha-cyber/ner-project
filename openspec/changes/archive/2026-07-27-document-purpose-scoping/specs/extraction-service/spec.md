## MODIFIED Requirements

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). When no promoted model exists, batch extraction SHALL use version 0 (base model). Each batch run SHALL record the model version used. Idempotency SHALL be determined by checking `extracted_entities` for existing rows with matching `document_id` and `model_version` — NOT by querying `extraction_runs.document_id`, which is NULL for batch runs. Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch. For each successfully processed document the worker SHALL persist predicted entities to the `extracted_entities` table with their `run_id`, `document_id`, `entity_id`, `value`, and `confidence`. When no explicit `documentIds` are provided, batch extraction SHALL only consider documents with `purpose='query'`; when explicit `documentIds` are provided, no `purpose` filtering SHALL be applied.

#### Scenario: Trigger batch extraction

- **GIVEN** a tenant with a promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1,doc2,doc3`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"
- **AND** a subsequent GET to `/api/v1/extract-batch/{run_id}` SHALL return `status`: "queued"

#### Scenario: Batch extraction persists extracted entities with document linkage

- **GIVEN** a tenant with a promoted model and one document in `processed` status
- **WHEN** batch extraction completes for that document
- **THEN** the extraction run SHALL have `processed_count = 1` and `failed_count = 0`
- **AND** one or more rows SHALL exist in `extracted_entities` linked to the `run_id`
- **AND** each row SHALL have non-null `entity_id`, `value`, `confidence`, and `document_id`
- **AND** `document_id` SHALL match the source document's ID

#### Scenario: Batch extraction skips already-extracted documents

- **GIVEN** a document whose entities have already been persisted in `extracted_entities` for the current active model version
- **WHEN** batch extraction is triggered for that document
- **THEN** the document SHALL be skipped
- **AND** the extraction run report SHALL indicate it was skipped

#### Scenario: Batch extraction for tenant with no promoted model

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch`
- **THEN** the response SHALL have status 202
- **AND** the run status SHALL eventually become "failed"
- **AND** the error SHALL be queryable via the status endpoint

#### Scenario: Trigger batch extraction with base model

- **GIVEN** a tenant with no promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=doc1,doc2`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"

#### Scenario: Batch extraction uses version 0 when no model promoted

- **GIVEN** a tenant whose most recently promoted model has been demoted
- **WHEN** batch extraction is triggered
- **THEN** the extraction SHALL proceed using version 0 (base model)
- **AND** the extraction run SHALL record model_version as "0"

#### Scenario: Default batch extraction excludes training-purpose documents

- **GIVEN** a tenant with 2 `processed` documents with `purpose='query'` and 1 `processed` document with `purpose='training'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch` with no `documentIds` query parameter
- **THEN** the batch run's `total_documents` SHALL be `2`
- **AND** the `purpose='training'` document SHALL NOT be processed

#### Scenario: Explicit documentIds bypasses purpose filtering

- **GIVEN** a tenant with a `processed` document with `purpose='training'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch?documentIds=<that document's id>`
- **THEN** the response SHALL have status 202
- **AND** that document SHALL be included in the batch run
