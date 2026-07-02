# Extraction Service

## Purpose

Exposes real-time and batch NER extraction endpoints for tenants. Routes inference through the model-serving layer and stores extracted entities with confidence scores and span offsets.

---

## Requirements

### Requirement: Real-time extraction

The system SHALL expose a real-time extraction endpoint that accepts a text paragraph and returns entities extracted by the tenant's active model. When no fine-tuned model is promoted, the system SHALL extract using the base model (version 0) with CoNLL labels. The response SHALL include a `model_version` field indicating which model produced the results. The endpoint SHALL resolve tenant_id from the JWT token and route the inference request through the model-serving internal endpoint. The system SHALL return extracted entities with confidence scores and source span offsets.

#### Scenario: Extract entities from a text paragraph with fine-tuned model

- **GIVEN** a tenant with a promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract` with `{"text": "John works at Acme Corp in New York."}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `entities` array
- **AND** each entity SHALL have `entity_type`, `value`, `confidence`, `start_offset`, `end_offset`
- **AND** `model_version` SHALL be the promoted version number
- **AND** entities SHALL be sorted by descending confidence

#### Scenario: Extract entities using base model when none is promoted

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract` with `{"text": "John works at Acme Corp in New York."}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `entities` array
- **AND** entities SHALL have CoNLL entity types (PER, ORG, LOC, MISC)
- **AND** `model_version` SHALL be "0"
- **AND** entities SHALL be sorted by descending confidence

#### Scenario: Extract entities as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/extract`
- **THEN** the response SHALL have status 403

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). When no promoted model exists, batch extraction SHALL use version 0 (base model). Each batch run SHALL record the model version used. Idempotency SHALL be determined by checking `extracted_entities` for existing rows with matching `document_id` and `model_version` — NOT by querying `extraction_runs.document_id`, which is NULL for batch runs. Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch. For each successfully processed document the worker SHALL persist predicted entities to the `extracted_entities` table with their `run_id`, `document_id`, `entity_id`, `value`, and `confidence`.

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

### Requirement: Get extraction run status

The system SHALL expose an endpoint to query the status of a batch extraction run, including progress (documents processed, skipped, failed) and completion state. The status SHALL include the `model_version` used for the run. The run record SHALL be stored in the `extraction_runs` table with all status fields populated.

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

#### Scenario: Get extraction run status with model version

- **GIVEN** a completed batch extraction run that used version 0
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `model_version`: "0"

### Requirement: List extraction runs

The system SHALL expose an endpoint to list a tenant's batch extraction runs, most recently started first. The endpoint SHALL return up to 50 runs. Each run in the list SHALL include the same fields as the single-run status endpoint (`status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `completed_at`, `started_at`, `model_version`) plus `run_id`. The endpoint SHALL scope results to the requesting tenant's schema.

#### Scenario: List batch extraction runs for a tenant

- **GIVEN** a tenant with three extraction runs: one "completed", one "queued", one "failed"
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain a `runs` array with all three runs
- **AND** each run SHALL include `run_id`, `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `started_at`, `completed_at`, and `model_version`

#### Scenario: Runs are ordered most-recent-first

- **GIVEN** a tenant with runs started at three different times
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the `runs` array SHALL be ordered by `started_at` descending

#### Scenario: List is scoped to the requesting tenant

- **GIVEN** tenant A has extraction runs and tenant B has none
- **WHEN** tenant B's Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the `runs` array SHALL be empty

#### Scenario: List returns empty array when no runs exist

- **GIVEN** a tenant with no extraction runs
- **WHEN** a Tenant Admin GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200
- **AND** the `runs` array SHALL be empty

#### Scenario: List entities as non-admin business user

- **GIVEN** an authenticated `business_user`
- **WHEN** the user GETs `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200

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

### Requirement: Review and correct entities

The system SHALL expose an endpoint to update the review status and corrected value of an extracted entity. Corrections SHALL be logged with the correcting user and timestamp.

#### Scenario: Correct an extracted entity

- **GIVEN** an extracted entity with `review_status`: "unreviewed" and `value`: "AcmeCorp"
- **WHEN** a Tenant Admin PATCHs `/api/v1/entities/{entity_id}` with `{"review_status": "corrected", "corrected_value": "Acme Corp"}`
- **THEN** the response SHALL have status 200
- **AND** `review_status` SHALL be "corrected"
- **AND** `corrected_value` SHALL be "Acme Corp"
- **AND** `corrected_by` SHALL be set to the requesting user

#### Scenario: Correct entity as annotator

- **GIVEN** an extracted entity
- **WHEN** an annotator PATCHs the entity
- **THEN** the response SHALL have status 200
- **AND** the correction SHALL be applied

### Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure

The gateway extraction proxy SHALL use URL paths without `{tid}`. The proxy SHALL forward the JWT `Authorization` header (already present from the inbound request) transparently to the extraction service.

The following proxy endpoint paths SHALL change:

| Old Path | New Path |
|----------|----------|
| `POST /api/v1/tenants/{tid}/extract` | `POST /api/v1/extract` |
| `POST /api/v1/tenants/{tid}/extract-batch` | `POST /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/extract-batch/{run_id}` | `GET /api/v1/extract-batch/{run_id}` |
| `GET /api/v1/tenants/{tid}/extract-batch` (list) | `GET /api/v1/extract-batch` |
| `GET /api/v1/tenants/{tid}/entities` | `GET /api/v1/entities` |
| `PATCH /api/v1/tenants/{tid}/entities/{entity_id}` | `PATCH /api/v1/entities/{entity_id}` |

#### Scenario: Proxy forwards single extraction request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: business_user`
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "Acme Corp"}`
- **THEN** the response SHALL have status 200 with extracted entities
- **AND** the proxy SHALL have forwarded the request to the extraction service at `/api/v1/extract`

#### Scenario: Proxy forwards batch run list request without tid in URL

- **GIVEN** a valid JWT with `tenant_id` and `role: business_user`
- **WHEN** a GET request is sent to external gateway `/api/v1/extract-batch`
- **THEN** the response SHALL have status 200 with a `runs` array
- **AND** the proxy SHALL have forwarded the request to the extraction service at `/api/v1/extract-batch`

#### Scenario: Proxy returns 403 when JWT is missing

- **GIVEN** no JWT token
- **WHEN** a POST request is sent to external gateway `/api/v1/extract` with `{"text": "test"}`
- **THEN** the response SHALL have status 403

---

### Requirement: Callers Construct URLs Without {tid}

All internal callers that construct URLs to the extraction service or model serving service SHALL omit `{tid}` from the URL path. The tenant_id SHALL continue to be sent via the JWT token in the `Authorization` header.

Affected callers:
- `extraction_engine.py`: constructs inference URL to model serving → SHALL NOT include tenant_id in path; SHALL forward JWT from the incoming request
- `worker.py`: constructs inference URL for batch extraction → SHALL NOT include tenant_id in path (JWT already forwarded)
- `models.py` (`_warmup_model`): constructs warmup URL → SHALL NOT include tenant_id in path (JWT already forwarded)

#### Scenario: Extraction engine forwards request without tid in URL

- **GIVEN** the synchronous extract endpoint receives a request with a valid JWT
- **WHEN** `extraction_engine.infer()` is called
- **THEN** the HTTP POST to model serving SHALL use URL `/internal/v1/infer` (without `{tid}`)
- **AND** the request SHALL include the `Authorization` header from the incoming request

#### Scenario: Worker constructs inference URL without tid in path

- **GIVEN** a batch extraction run is processing documents
- **WHEN** the worker sends an inference request to model serving
- **THEN** the URL SHALL be `/internal/v1/infer` (without `{tid}`)
- **AND** the request SHALL include a valid JWT with the tenant_id

#### Scenario: Training service constructs warmup URL without tid in path

- **GIVEN** a model is being promoted
- **WHEN** `_warmup_model()` sends a warmup request to model serving
- **THEN** the URL SHALL be `/internal/v1/warmup` (without `{tid}`)
- **AND** the request SHALL include a valid JWT with the tenant_id

---

### Requirement: Post-processing confidence filtering

The system SHALL apply a configurable confidence threshold during extraction. Entities below the threshold SHALL be excluded from results. The default threshold SHALL be 0.50.

#### Scenario: Low-confidence entities are filtered out

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with confidence 0.30
- **THEN** that entity SHALL NOT appear in the results
