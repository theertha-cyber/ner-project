## MODIFIED Requirements

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
