## ADDED Requirements

### Requirement: Real-time extraction

The system SHALL expose a real-time extraction endpoint that accepts a text paragraph and returns entities extracted by the tenant's promoted model. The endpoint SHALL route the inference request through the model-serving internal endpoint. The system SHALL return extracted entities with confidence scores and source span offsets.

#### Scenario: Extract entities from a text paragraph

- **GIVEN** a tenant with a promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract` with `{"text": "John works at Acme Corp in New York."}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `entities` array
- **AND** each entity SHALL have `entity_type`, `value`, `confidence`, `start_offset`, `end_offset`
- **AND** entities SHALL be sorted by descending confidence

#### Scenario: Extract entities when no model is promoted

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract` with any text
- **THEN** the response SHALL have status 400
- **AND** the error SHALL indicate no active model is available

#### Scenario: Extract entities as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/tenants/{tid}/extract`
- **THEN** the response SHALL have status 403

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). Batch extraction SHALL run asynchronously via a Celery task.

#### Scenario: Trigger batch extraction

- **GIVEN** a tenant with a promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract-batch?documentIds=doc1,doc2,doc3`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"

#### Scenario: Batch extraction skips already-extracted documents

- **GIVEN** a document that has been extracted with the current active model version
- **WHEN** batch extraction is triggered
- **THEN** the document SHALL be skipped
- **AND** the extraction run report SHALL indicate it was skipped

#### Scenario: Batch extraction for tenant with no promoted model

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract-batch`
- **THEN** the response SHALL have status 400
- **AND** the error SHALL indicate no active model is available

### Requirement: Get extraction run status

The system SHALL expose an endpoint to query the status of a batch extraction run, including progress (documents processed, skipped, failed) and completion state.

#### Scenario: Get extraction run status

- **GIVEN** a batch extraction run in "running" status
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`

#### Scenario: Get extraction run status of completed run

- **GIVEN** a completed batch extraction run
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "completed" and `completed_at`

### Requirement: Query extracted entities

The system SHALL expose an endpoint to query extracted entities with filters for document, entity type, confidence range, and review status. Results SHALL be paginated.

#### Scenario: Query entities by document

- **GIVEN** extracted entities for a document
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/entities?documentId=doc1`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain entities belonging to that document
- **AND** the response SHALL include pagination metadata (`page`, `per_page`, `total`)

#### Scenario: Query entities by type

- **GIVEN** extracted entities of various types
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/entities?type=ORG`
- **THEN** the response SHALL contain only entities with `entity_type`: "ORG"

#### Scenario: Query entities by confidence threshold

- **GIVEN** extracted entities with varying confidence scores
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/entities?minConfidence=0.8`
- **THEN** the response SHALL contain only entities with `confidence` >= 0.8

#### Scenario: Query entities unreviewed

- **GIVEN** entities with different review_statuses
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/entities?reviewStatus=unreviewed`
- **THEN** the response SHALL contain only entities with `review_status`: "unreviewed"

#### Scenario: Query entities as annotator

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator GETs `/api/v1/tenants/{tid}/entities`
- **THEN** the response SHALL have status 200

#### Scenario: Query entities cross-tenant 404

- **GIVEN** entities for tenant A
- **WHEN** tenant B requests entities for a document belonging to tenant A
- **THEN** the response SHALL have status 404

### Requirement: Review and correct entities

The system SHALL expose an endpoint to update the review status and corrected value of an extracted entity. Corrections SHALL be logged with the correcting user and timestamp.

#### Scenario: Correct an extracted entity

- **GIVEN** an extracted entity with `review_status`: "unreviewed" and `value`: "AcmeCorp"
- **WHEN** a Tenant Admin PATCHs `/api/v1/tenants/{tid}/entities/{entity_id}` with `{"review_status": "corrected", "corrected_value": "Acme Corp"}`
- **THEN** the response SHALL have status 200
- **AND** `review_status` SHALL be "corrected"
- **AND** `corrected_value` SHALL be "Acme Corp"
- **AND** `corrected_by` SHALL be set to the requesting user

#### Scenario: Correct entity as annotator

- **GIVEN** an extracted entity
- **WHEN** an annotator PATCHs the entity
- **THEN** the response SHALL have status 200
- **AND** the correction SHALL be applied

### Requirement: Post-processing confidence filtering

The system SHALL apply a configurable confidence threshold during extraction. Entities below the threshold SHALL be excluded from results. The default threshold SHALL be 0.50.

#### Scenario: Low-confidence entities are filtered out

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that entity SHALL NOT appear in the results
