## ADDED Requirements

### Requirement: Approve training job

The system SHALL allow a System Admin to approve a training job that is in "pending_approval" status. Upon approval, the system SHALL enqueue the job to Celery and SHALL transition the job status to "queued".

#### Scenario: Approve a pending training job

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `status`: "queued"
- **AND** a Celery task SHALL be enqueued for processing

#### Scenario: Approve a job that is not pending_approval

- **GIVEN** a training job in "queued" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/approve`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the job cannot be approved in its current state

#### Scenario: Approve as non-system-admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/approve`
- **THEN** the response SHALL have status 403

### Requirement: Reject training job

The system SHALL allow a System Admin to reject a training job that is in "pending_approval" status. The system MAY accept an optional rejection reason. Upon rejection, the system SHALL transition the job status to "rejected".

#### Scenario: Reject a pending training job

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/reject` with `{"reason": "GPU cluster at capacity"}`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `status`: "rejected"
- **AND** the response body SHALL contain `error_message`: "GPU cluster at capacity"

#### Scenario: Reject a pending training job without reason

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/reject` with no body
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `status`: "rejected"
- **AND** the response body SHALL contain `error_message`: null

#### Scenario: Reject a job that is not pending_approval

- **GIVEN** a training job in "completed" status
- **WHEN** a System Admin POSTs to `/api/v1/training-jobs/{job_id}/reject`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the job cannot be rejected in its current state

#### Scenario: Reject as non-system-admin

- **GIVEN** a training job in "pending_approval" status
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs/{job_id}/reject`
- **THEN** the response SHALL have status 403
