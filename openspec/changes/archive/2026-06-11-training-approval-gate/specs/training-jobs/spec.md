## MODIFIED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The system SHALL validate the tenant has at least 500 annotated entities before accepting a job. The system SHALL create the job in "pending_approval" status and SHALL NOT enqueue a Celery task. The system SHALL return a 201 status with the created job.

#### Scenario: Submit a valid training job

- **GIVEN** a tenant with at least 500 annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `status` ("pending_approval"), `created_at`, and the submitted hyperparameters
- **AND** the response body SHALL NOT contain `celery_task_id`
- **AND** no Celery task SHALL be enqueued

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

### Requirement: Cancel training job

The system SHALL allow cancellation of a training job that is in "pending_approval", "queued", or "running" status. If the job has an associated Celery task, the task SHALL be revoked.

#### Scenario: Cancel a pending_approval job

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/cancel`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "cancelled"

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
