## MODIFIED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The submission payload SHALL NOT include hyperparameters (`learning_rate`, `num_epochs`, `batch_size`, `max_seq_length`) — hyperparameters are set later by a System Admin at approval time. The system SHALL validate the tenant has at least 500 annotated entities before accepting a job. The system SHALL create the job in "pending_approval" status with `hyperparams: null` and SHALL NOT enqueue a Celery task. The system SHALL return a 201 status with the created job.

#### Scenario: Submit a valid training job

- **GIVEN** a tenant with at least 500 annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with an empty (or hyperparameter-free) body
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `status` ("pending_approval"), `created_at`, and `hyperparams: null`
- **AND** the response body SHALL NOT contain `celery_task_id`
- **AND** no Celery task SHALL be enqueued

#### Scenario: Submit training job with insufficient entities

- **GIVEN** a tenant with fewer than 500 annotated entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the minimum entity threshold is not met

#### Scenario: Submit training job as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 403

#### Scenario: Submit training job body with hyperparameters is ignored or rejected

- **GIVEN** a tenant with sufficient entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with a body containing `learning_rate`, `num_epochs`, `batch_size`, or `max_seq_length`
- **THEN** the response SHALL have status 201 with those fields ignored (extra/unknown fields are not accepted as hyperparameters), or the endpoint SHALL reject unknown fields with 422 — either way, the created job's `hyperparams` SHALL be `null`, never populated from this request

### Requirement: Approve training job

The system SHALL allow a System Admin to approve a training job that is in "pending_approval" status by supplying `learning_rate`, `num_epochs` (1-50), `batch_size`, and `max_seq_length` (32-512) in the request body. The system SHALL validate these hyperparameters using the same bounds previously enforced on tenant submission. Upon successful validation, the system SHALL persist the supplied hyperparameters onto the job's `hyperparams`, enqueue the job to Celery using those values, and transition the job status to "queued".

#### Scenario: Approve a pending training job with valid hyperparameters

- **GIVEN** a training job in "pending_approval" status with `hyperparams: null`
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve` with `{"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `status`: "queued" and `hyperparams` matching the submitted values
- **AND** a Celery task SHALL be enqueued using those hyperparameters

#### Scenario: Approve without supplying hyperparameters

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve` with an empty body
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate hyperparameters are required to approve

#### Scenario: Approve with invalid hyperparameters

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve` with `{"num_epochs": -1}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL describe which parameter is invalid
- **AND** the job SHALL remain in "pending_approval" status with `hyperparams` unchanged

#### Scenario: Approve a job that is not pending_approval

- **GIVEN** a training job in "queued" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve` with valid hyperparameters
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the job cannot be approved in its current state

#### Scenario: Approve as non-system-admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/approve` with valid hyperparameters
- **THEN** the response SHALL have status 403

### Requirement: Submit form span preflight is informational only

The Training Queue's submit job form SHALL display the tenant's current confirmed span count when opened, for informational purposes only. The client SHALL NOT compute or enforce its own minimum-span threshold. Since the submit form no longer collects hyperparameters, the submit action SHALL be enabled or disabled based solely on submission-in-flight state — never on span count and never on hyperparameter validity (there is no hyperparameter form on submit). Enforcement of any minimum annotated-entity threshold remains solely the responsibility of the `POST /api/v1/training-jobs` endpoint; if the backend rejects a submission for insufficient entities, that error SHALL be surfaced to the user through the existing submission error display.

#### Scenario: Submit enabled with span count below the legacy 500 threshold

- **GIVEN** a tenant with fewer than 500 confirmed spans
- **WHEN** the Tenant Admin opens the Submit Training Job form
- **THEN** the Submit button SHALL be enabled
- **AND** the preflight display SHALL show the confirmed span count without any pass/fail language or threshold comparison

#### Scenario: Preflight display shows span count while loading and on fetch failure

- **GIVEN** the Tenant Admin opens the Submit Training Job form
- **WHEN** the span count request is in flight
- **THEN** the preflight display SHALL show a loading state
- **WHEN** the span count request fails
- **THEN** the preflight display SHALL indicate the count is unavailable
- **AND** the Submit button's enabled state SHALL NOT be affected by the span count fetch succeeding, failing, or being unavailable

#### Scenario: Backend rejection for insufficient entities is surfaced after submit

- **GIVEN** a tenant whose annotated entity count is below the backend's configured minimum
- **WHEN** the Tenant Admin submits the Submit Training Job form
- **AND** `POST /api/v1/training-jobs` responds with a 422 indicating insufficient annotated entities
- **THEN** the form SHALL display the backend's error message to the user
- **AND** the form SHALL remain open
