# Training Jobs

## Purpose

API for submitting, monitoring, listing, cancelling, and approving/rejecting NER fine-tuning training jobs. Jobs require System Admin approval before being enqueued for execution.

---

## Requirements

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

### Requirement: Get training job status

The system SHALL expose a status endpoint that returns the current state, hyperparameters, metrics (on completion), error details (on failure), and owning `tenant_id` for a training job. A System Admin SHALL be able to fetch any tenant's job by supplying that job's `tenant_id` as a query parameter; a System Admin request with no `tenant_id` SHALL be rejected rather than silently defaulted. A Tenant Admin SHALL continue to use their own JWT-derived tenant and SHALL NOT be able to override it via query parameter.

#### Scenario: Get status of queued job

- **GIVEN** a training job in "queued" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "queued", the submitted hyperparameters, `tenant_id`, and `created_at`

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

#### Scenario: System Admin gets a job with the correct tenant_id

- **GIVEN** a training job owned by tenant A, in any status
- **WHEN** a System Admin GETs `/api/v1/training-jobs/{job_id}?tenant_id=<tenant A id>`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `tenant_id`: `<tenant A id>` matching the job's owning tenant

#### Scenario: System Admin gets a job without providing tenant_id

- **GIVEN** a training job owned by tenant A
- **WHEN** a System Admin GETs `/api/v1/training-jobs/{job_id}` with no `tenant_id` query parameter
- **THEN** the response SHALL have status 400
- **AND** the error SHALL indicate that System Admin requests must provide `tenant_id`

#### Scenario: System Admin gets a job with the wrong tenant_id

- **GIVEN** a training job owned by tenant A
- **WHEN** a System Admin GETs `/api/v1/training-jobs/{job_id}?tenant_id=<tenant B id>`
- **THEN** the response SHALL have status 404

### Requirement: List training jobs

The system SHALL list training jobs with optional status filter and pagination. A Tenant Admin SHALL always see only their own tenant's jobs. A System Admin who supplies an explicit `tenant_id` query parameter SHALL see that tenant's jobs (identical behavior to a Tenant Admin, scoped to the given tenant). A System Admin who supplies no `tenant_id` SHALL see jobs aggregated across all active tenant schemas rather than an unconditional empty list; if no `status` filter is given in this aggregated case, the result SHALL default to `pending_approval` status jobs (the queue's actionable set). Every returned job item SHALL include its owning `tenant_id`.

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

#### Scenario: List jobs includes tenant_id on each item

- **GIVEN** a tenant with at least one training job
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs`
- **THEN** each item in the response SHALL contain `tenant_id` matching the caller's tenant

#### Scenario: System Admin lists jobs with an explicit tenant_id

- **GIVEN** tenant A has 3 training jobs and tenant B has 2 training jobs
- **WHEN** a System Admin GETs `/api/v1/training-jobs?tenant_id=<tenant A id>`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain only tenant A's 3 jobs

#### Scenario: System Admin lists jobs with no tenant_id sees an aggregated pending-approval queue

- **GIVEN** tenant A has 1 job in "pending_approval" status and tenant B has 1 job in "pending_approval" status and 1 job in "completed" status
- **WHEN** a System Admin GETs `/api/v1/training-jobs` with no `tenant_id` and no `status` query parameter
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain the 2 "pending_approval" jobs (one from tenant A, one from tenant B)
- **AND** each item SHALL contain its correct owning `tenant_id`

#### Scenario: System Admin lists jobs across tenants with an explicit status filter

- **GIVEN** tenant A has 1 job in "completed" status and tenant B has 1 job in "completed" status
- **WHEN** a System Admin GETs `/api/v1/training-jobs?status=completed` with no `tenant_id`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain both tenants' "completed" jobs

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

### Requirement: Submit form span preflight is informational only

The Training Queue's submit job form SHALL display the tenant's current confirmed span count when opened, for informational purposes only. The client SHALL NOT compute or enforce its own minimum-span threshold. The submit action SHALL be enabled or disabled based solely on hyperparameter form validation (learning rate, epochs, batch size, max sequence length) and submission-in-flight state — never on span count. Enforcement of any minimum annotated-entity threshold remains solely the responsibility of the `POST /api/v1/training-jobs` endpoint; if the backend rejects a submission for insufficient entities, that error SHALL be surfaced to the user through the existing submission error display.

#### Scenario: Submit enabled with span count below the legacy 500 threshold

- **GIVEN** a tenant with fewer than 500 confirmed spans
- **AND** the submit form's hyperparameter fields all contain valid values
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
- **AND** the form SHALL remain open with the entered hyperparameters intact

### Requirement: Hide submit job action for non-tenant-admin roles

The Training Queue UI SHALL only render the submit job button and submit job slideover for users with the `tenant_admin` role. Users with any other role (including `system_admin`, `annotator`, `business_user`) SHALL NOT see the submit job button or have access to the submit job slideover on the Training Queue page.

#### Scenario: Submit button visible for tenant_admin

- **GIVEN** an authenticated user with the `tenant_admin` role
- **WHEN** the user navigates to the Training Queue page (`/training-jobs`)
- **THEN** the `+ Submit Job` button SHALL be visible in the page header

#### Scenario: Submit button hidden for system_admin

- **GIVEN** an authenticated user with the `system_admin` role
- **WHEN** the user navigates to the Training Queue page (`/training-jobs`)
- **THEN** the `+ Submit Job` button SHALL NOT be rendered on the page
- **AND** the submit job slideover SHALL NOT be rendered on the page

#### Scenario: Submit slideover not accessible for system_admin

- **GIVEN** an authenticated user with the `system_admin` role on the Training Queue page
- **WHEN** the user inspects the page
- **THEN** no mechanism to open the submit job slideover SHALL exist in the DOM
