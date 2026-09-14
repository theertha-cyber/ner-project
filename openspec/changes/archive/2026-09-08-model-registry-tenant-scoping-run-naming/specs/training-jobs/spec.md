## MODIFIED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The system SHALL validate the tenant has at least 500 annotated entities before accepting a job. The system SHALL create the job in "pending_approval" status, SHALL assign it a per-tenant sequential `run_number` (starting at 1, monotonically increasing, never reused even if the job is later cancelled, rejected, or fails), and SHALL NOT enqueue a Celery task. The system SHALL return a 201 status with the created job, including its `run_number` and a derived `run_name` of the form `run-{run_number:03d}-{created_at:%Y%m%d}`.

#### Scenario: Submit a valid training job

- **GIVEN** a tenant with at least 500 annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"learning_rate": 2e-5, "num_epochs": 3, "batch_size": 8, "max_seq_length": 128}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `status` ("pending_approval"), `created_at`, `run_number`, `run_name`, and the submitted hyperparameters
- **AND** the response body SHALL NOT contain `celery_task_id`
- **AND** no Celery task SHALL be enqueued

#### Scenario: Submit training job with insufficient entities

- **GIVEN** a tenant with fewer than 500 annotated entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with any valid hyperparameters
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the minimum entity threshold is not met
- **AND** no `run_number` SHALL be consumed for the rejected submission

#### Scenario: Submit training job as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 403

#### Scenario: Submit training job with invalid hyperparameters

- **GIVEN** a tenant with sufficient entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"num_epochs": -1}`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL describe which parameter is invalid

#### Scenario: Sequential run numbers assigned per tenant, starting at 1

- **GIVEN** a tenant with no prior training jobs
- **WHEN** a Tenant Admin submits three valid training jobs in sequence
- **THEN** the jobs SHALL receive `run_number` 1, 2, and 3 respectively
- **AND** each job's `run_name` SHALL use its `created_at` date, e.g. `run-001-20260729`, `run-002-20260729`, `run-003-20260729`

#### Scenario: Run numbers are not reused after cancellation, rejection, or failure

- **GIVEN** a tenant whose most recent training job has `run_number: 4` and is subsequently cancelled
- **WHEN** the Tenant Admin submits a new training job
- **THEN** the new job SHALL receive `run_number: 5`, not `4`

### Requirement: Get training job status

The system SHALL expose a status endpoint that returns the current state, hyperparameters, metrics (on completion), error details (on failure), `run_number`, `run_name`, and owning `tenant_id` for a training job. A System Admin SHALL be able to fetch any tenant's job by supplying that job's `tenant_id` as a query parameter; a System Admin request with no `tenant_id` SHALL be rejected rather than silently defaulted. A Tenant Admin SHALL continue to use their own JWT-derived tenant and SHALL NOT be able to override it via query parameter.

#### Scenario: Get status of queued job

- **GIVEN** a training job in "queued" status
- **WHEN** a Tenant Admin GETs `/api/v1/training-jobs/{job_id}`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL contain `status`: "queued", the submitted hyperparameters, `tenant_id`, `created_at`, `run_number`, and `run_name`

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

## ADDED Requirements

### Requirement: Model version reuses its training job's run number

When a training job completes and creates a `ModelVersion` row, the system SHALL copy the owning training job's `run_number` onto the model version rather than computing an independent naming value, so the model's `run_name` matches the training job's `run_name` exactly.

#### Scenario: Completed job's model version shares the job's run name

- **GIVEN** a training job with `run_number: 7`, `run_name: "run-007-20260729"` that completes successfully
- **WHEN** the worker creates the resulting `ModelVersion`
- **THEN** the model version's `run_number` SHALL be 7
- **AND** the model version's `run_name` SHALL be `"run-007-20260729"`, matching the training job
