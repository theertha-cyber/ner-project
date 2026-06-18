## MODIFIED Requirements

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). Idempotency SHALL be determined by checking `extracted_entities` for existing rows with matching `document_id` and `model_version` — NOT by querying `extraction_runs.document_id`, which is NULL for batch runs. Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch. For each successfully processed document the worker SHALL persist predicted entities to the `extracted_entities` table with their `run_id`, `document_id`, `entity_id`, `value`, and `confidence`.

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

### Requirement: Query extracted entities

The system SHALL expose an endpoint to query extracted entities with filters for document, entity type, confidence range, and review status. Results SHALL be paginated. The `documentId` filter SHALL be resolved directly against the `document_id` column on `extracted_entities`.

#### Scenario: Query entities by document after batch extraction

- **GIVEN** a document that has been processed by batch extraction
- **WHEN** a Tenant Admin GETs `/api/v1/entities?documentId=<that document's id>`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the entities extracted from that document
- **AND** the response SHALL include pagination metadata (`page`, `per_page`, `total`)

#### Scenario: Query entities by type

- **GIVEN** extracted entities of various types
- **WHEN** a Tenant Admin GETs `/api/v1/entities?type=ORG`
- **THEN** the response SHALL contain only entities with `entity_type`: "ORG"

#### Scenario: Query entities by confidence threshold

- **GIVEN** extracted entities with varying confidence scores
- **WHEN** a Tenant Admin GETs `/api/v1/entities?minConfidence=0.8`
- **THEN** the response SHALL contain only entities with `confidence` >= 0.8

#### Scenario: Query entities unreviewed

- **GIVEN** entities with different review_statuses
- **WHEN** a Tenant Admin GETs `/api/v1/entities?reviewStatus=unreviewed`
- **THEN** the response SHALL contain only entities with `review_status`: "unreviewed"

#### Scenario: Query entities as annotator

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator GETs `/api/v1/entities`
- **THEN** the response SHALL have status 200

#### Scenario: Query entities cross-tenant 404

- **GIVEN** entities for tenant A
- **WHEN** tenant B requests entities for a document belonging to tenant A
- **THEN** the response SHALL have status 404
