## MODIFIED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The system SHALL validate the tenant has at least 500 annotated entities before accepting a job. The submission MAY include an optional `compute_backend` field with value `platform` (default) or `colab`. For `compute_backend: platform` (or when omitted), the system SHALL create the job in "pending_approval" status and SHALL NOT enqueue a Celery task, exactly as today. For `compute_backend: colab`, the system SHALL create the job directly in "awaiting_notebook_launch" status, SHALL NOT enqueue a Celery task, and SHALL NOT require System Admin approval. The system SHALL return a 201 status with the created job.

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

#### Scenario: Submit a valid training job with compute_backend colab

- **GIVEN** a tenant with at least 500 annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with valid hyperparameters and `"compute_backend": "colab"`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `status`: "awaiting_notebook_launch"
- **AND** the response body SHALL NOT contain `celery_task_id`
- **AND** no Celery task SHALL be enqueued
- **AND** no System Admin approval SHALL be required for this job to proceed

#### Scenario: Submit a colab training job with insufficient entities

- **GIVEN** a tenant with fewer than 500 annotated entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `"compute_backend": "colab"` and any valid hyperparameters
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the minimum entity threshold is not met, identically to the platform-backend path

#### Scenario: compute_backend defaults to platform when omitted

- **GIVEN** a tenant with sufficient entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` without a `compute_backend` field
- **THEN** the job SHALL be created with `compute_backend`: "platform"
- **AND** the job SHALL behave exactly as it does today (pending_approval, no Celery task yet)

### Requirement: Cancel training job

The system SHALL allow cancellation of a training job that is in "pending_approval", "awaiting_notebook_launch", "queued", or "running" status. If the job has an associated Celery task (`compute_backend: platform`), the task SHALL be revoked. If the job is colab-backed (`compute_backend: colab`), its scoped callback credential SHALL be revoked instead.

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

#### Scenario: Cancel a colab job in awaiting_notebook_launch status

- **GIVEN** a colab-backed training job in "awaiting_notebook_launch" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/cancel`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "cancelled"
- **AND** the job's scoped callback credential SHALL be revoked
- **AND** no Celery revoke call SHALL be attempted for this job

#### Scenario: Cancel a colab job in running status

- **GIVEN** a colab-backed training job in "running" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/cancel`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "cancelled"
- **AND** the job's scoped callback credential SHALL be revoked
- **AND** a subsequent callback request using that credential SHALL be rejected
