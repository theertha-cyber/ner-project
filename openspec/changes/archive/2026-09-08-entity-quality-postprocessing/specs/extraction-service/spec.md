## MODIFIED Requirements

### Requirement: Batch extraction

The system SHALL support batch extraction on existing documents. Batch extraction SHALL accept a **processing mode** in the request body, one of `bert_only` or `bert_llm_postprocess`, defaulting to `bert_only` when absent. The mode SHALL be validated server-side and SHALL be passed to the worker as a task argument, which SHALL enforce it; the worker SHALL NOT re-read a tenant setting to decide the mode. Each batch run SHALL record the processing mode actually used, and when post-processing ran, the post-processor model and prompt version. Batch extraction SHALL process documents in `processed` status and SHALL skip documents already extracted with the current active model version (idempotent); the processing mode SHALL NOT affect this skip decision, so changing the mode SHALL NOT cause existing extraction results to be reprocessed. When no promoted model exists, batch extraction SHALL use version 0 (base model). Each batch run SHALL record the model version used. Idempotency SHALL be determined by checking `extracted_entities` for existing rows with matching `document_id` and `model_version` — NOT by querying `extraction_runs.document_id`, which is NULL for batch runs. Batch extraction SHALL run asynchronously via a Celery task. The system SHALL persist a batch extraction run record in the database before processing begins, and the run SHALL be immediately queryable via the status endpoint after dispatch. For each successfully processed document the worker SHALL persist predicted entities to the `extracted_entities` table with their `run_id`, `document_id`, `entity_id`, `value`, and `confidence`. When no explicit `documentIds` are provided, batch extraction SHALL only consider documents with `purpose='query'`; when explicit `documentIds` are provided, no `purpose` filtering SHALL be applied.

#### Scenario: Trigger batch extraction

- **GIVEN** a tenant with a promoted model and documents in `processed` status
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch` with body `{"documentIds": ["doc1", "doc2", "doc3"]}`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"
- **AND** a subsequent GET to `/api/v1/extract-batch/{run_id}` SHALL return `status`: "queued"

#### Scenario: Omitted processing mode defaults to BERT-only

- **GIVEN** a batch extraction request with no `processing_mode` field
- **WHEN** the request is accepted
- **THEN** the run SHALL record `processing_mode = 'bert_only'`
- **AND** no post-processing call SHALL be made for any document in the run

#### Scenario: Requested processing mode reaches and is enforced by the worker

- **GIVEN** a batch extraction request with `processing_mode = 'bert_llm_postprocess'`
- **WHEN** the Celery task is dispatched
- **THEN** the mode SHALL be present in the task arguments
- **AND** the worker SHALL run post-processing for that run regardless of any tenant setting changed after dispatch

#### Scenario: Unknown processing mode is rejected

- **GIVEN** a batch extraction request with `processing_mode = 'llm_only'`
- **WHEN** the request is validated
- **THEN** the response SHALL have status 422
- **AND** no extraction run SHALL be created

#### Scenario: Post-processing requested without configuration is rejected, not silently downgraded

- **GIVEN** a deployment with no post-processor configured
- **WHEN** a request specifies `processing_mode = 'bert_llm_postprocess'`
- **THEN** the response SHALL have status 422
- **AND** no extraction run SHALL be created

#### Scenario: Changing the mode does not reprocess existing results

- **GIVEN** a document already extracted under the current active model version in `bert_only` mode
- **WHEN** batch extraction is triggered for that document with `processing_mode = 'bert_llm_postprocess'`
- **THEN** the document SHALL be skipped
- **AND** its existing entities SHALL NOT be modified or deleted

#### Scenario: The run records the mode actually used

- **GIVEN** a completed run dispatched with `processing_mode = 'bert_llm_postprocess'`
- **WHEN** its status is queried
- **THEN** the response SHALL report the processing mode used
- **AND** when post-processing ran, the post-processor model and prompt version SHALL be reported

#### Scenario: A run degraded by post-processing failure is reported as such

- **GIVEN** a run in `bert_llm_postprocess` mode where every post-processing call failed
- **WHEN** its status is queried
- **THEN** `status` SHALL be `completed`
- **AND** a degraded indicator SHALL be reported
- **AND** `processed_count` SHALL reflect the documents whose entities were persisted

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
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch` with body `{"documentIds": ["doc1", "doc2"]}`
- **THEN** the response SHALL have status 202
- **AND** the response SHALL contain `run_id` and `status`: "queued"

#### Scenario: Batch extraction uses version 0 when no model promoted

- **GIVEN** a tenant whose most recently promoted model has been demoted
- **WHEN** batch extraction is triggered
- **THEN** the extraction SHALL proceed using version 0 (base model)
- **AND** the extraction run SHALL record model_version as "0"

#### Scenario: Default batch extraction excludes training-purpose documents

- **GIVEN** a tenant with 2 `processed` documents with `purpose='query'` and 1 `processed` document with `purpose='training'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch` with no document ids
- **THEN** the batch run's `total_documents` SHALL be `2`
- **AND** the `purpose='training'` document SHALL NOT be processed

#### Scenario: Explicit documentIds bypasses purpose filtering

- **GIVEN** a tenant with a `processed` document with `purpose='training'`
- **WHEN** a Tenant Admin POSTs to `/api/v1/extract-batch` naming that document
- **THEN** the response SHALL have status 202
- **AND** that document SHALL be included in the batch run

#### Scenario: The documentIds query parameter remains accepted for one release

- **GIVEN** an existing client that sends `documentIds` as a query parameter and no request body
- **WHEN** it POSTs to `/api/v1/extract-batch`
- **THEN** the request SHALL be accepted
- **AND** the run SHALL use the default processing mode

### Requirement: Post-processing confidence filtering

The system SHALL apply a configurable confidence threshold during extraction. Entities below the threshold SHALL be excluded from results. The default threshold SHALL be 0.50. The threshold SHALL be compared against a **calibrated confidence in `[0, 1]`** as returned by the model-serving inference endpoint; it SHALL NOT be compared against a raw logit, against which a threshold of 0.50 excludes nothing.

#### Scenario: Low-confidence entities are filtered out

- **GIVEN** a confidence threshold of 0.50
- **WHEN** extraction runs on text containing a predicted entity with calibrated confidence 0.30
- **THEN** that entity SHALL NOT appear in the results

#### Scenario: The threshold is meaningful against the returned scale

- **GIVEN** any extraction result returned by the real-time extraction endpoint
- **WHEN** its entities are inspected
- **THEN** every returned entity's confidence SHALL lie in `[0, 1]`
- **AND** every returned entity's confidence SHALL be greater than or equal to the configured threshold
