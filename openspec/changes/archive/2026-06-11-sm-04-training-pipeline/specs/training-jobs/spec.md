## ADDED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The system SHALL validate the tenant has at least 500 annotated entities before accepting a job. The system SHALL enqueue the job to Celery upon validation and SHALL return a 201 status with the created job.

#### Scenario: Submit a valid training job

- **GIVEN** a tenant with at least 500 annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `status` ("queued"), `created_at`, and the submitted hyperparameters
- **AND** a Celery task SHALL be enqueued for processing

#### Scenario: Submit training job with insufficient entities

- **GIVEN** a tenant with fewer than 500 annotated entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with any valid hyperparameters
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the minimum entity threshold is not met

#### Scenario: Submit training job as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 403

#### Scenario: Submit training job with invalid hyperparameters

- **GIVEN** a tenant with sufficient entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"num_epochs": -1}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL describe which parameter is invalid

### Requirement: Get training job status

The system SHALL expose a status endpoint that returns the current state, hyperparameters, metrics (on completion), and error details (on failure) for a training job.

#### Scenario: Get status of queued job

- **GIVEN** a training job in "queued" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "queued", the submitted hyperparameters, and `created_at`

#### Scenario: Get status of running job

- **GIVEN** a training job in "running" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "running", `current_epoch`, `current_loss`, and `started_at`

#### Scenario: Get status of completed job

- **GIVEN** a training job in "completed" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "completed", `metrics` (final loss, eval F1, precision, recall), `model_version`, and `completed_at`

#### Scenario: Get status of failed job

- **GIVEN** a training job in "failed" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "failed", `error_message`, and `failed_at`

#### Scenario: Get training job as non-owner tenant

- **GIVEN** a training job owned by tenant A
- **WHEN** a user from tenant B (with valid JWT for tenant B) GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 404
- **AND** the error SHALL not reveal the existence of the job

### Requirement: List training jobs

The system SHALL list training jobs for the tenant with optional status filter and pagination.

#### Scenario: List jobs with status filter

- **GIVEN** a tenant with jobs in "queued", "running", and "completed" statuses
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs?status=running`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain only jobs with `status`: "running"

#### Scenario: List jobs paginated

- **GIVEN** a tenant with 25 training jobs
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs?page=2&per_page=10`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain 10 jobs
- **AND** the response SHALL contain `total`: 25, `page`: 2, `per_page`: 10

### Requirement: Cancel training job

The system SHALL allow cancellation of a training job that is in "queued" or "running" status. The Celery task SHALL be revoked.

#### Scenario: Cancel a queued job

- **GIVEN** a training job in "queued" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/cancel`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "cancelled"

#### Scenario: Cancel a completed job returns 422

- **GIVEN** a training job in "completed" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/cancel`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the job cannot be cancelled in its current state
