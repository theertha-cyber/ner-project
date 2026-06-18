## MODIFIED Requirements

### Requirement: Real-time extraction

The system SHALL expose a real-time extraction endpoint that accepts a text paragraph and returns entities extracted by the tenant's active model. When no fine-tuned model is promoted, the system SHALL extract using the base model (version 0) with CoNLL labels. The response SHALL include a `model_version` field indicating which model produced the results.

#### Scenario: Extract entities from a text paragraph with fine-tuned model

- **GIVEN** a tenant with a promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract` with `{"text": "John works at Acme Corp in New York."}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `entities` array
- **AND** each entity SHALL have `entity_type`, `value`, `confidence`, `start_offset`, `end_offset`
- **AND** `model_version` SHALL be the promoted version number
- **AND** entities SHALL be sorted by descending confidence

#### Scenario: Extract entities using base model when none is promoted

- **GIVEN** a tenant with no promoted model
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract` with `{"text": "John works at Acme Corp in New York."}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain an `entities` array
- **AND** entities SHALL have CoNLL entity types (PER, ORG, LOC, MISC)
- **AND** `model_version` SHALL be "0"
- **AND** entities SHALL be sorted by descending confidence

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent). When no promoted model exists, batch extraction SHALL use version 0 (base model). Each batch run SHALL record the model version used.

#### Scenario: Trigger batch extraction with base model

- **GIVEN** a tenant with no promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/tenants/{tid}/extract-batch?documentIds=doc1,doc2`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"

#### Scenario: Batch extraction uses version 0 when no model promoted

- **GIVEN** a tenant whose most recently promoted model has been demoted
- **WHEN** batch extraction is triggered
- **THEN** the extraction SHALL proceed using version 0 (base model)
- **AND** the extraction run SHALL record model_version as "0"

### Requirement: Get extraction run status

The system SHALL expose an endpoint to query the status of a batch extraction run, including progress (documents processed, skipped, failed) and completion state. The status SHALL include the `model_version` used for the run.

#### Scenario: Get extraction run status with model version

- **GIVEN** a completed batch extraction run that used version 0
- **WHEN** a Tenant Admin GETs `/api/v1/tenants/{tid}/extract-batch/{run_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `model_version`: "0"
