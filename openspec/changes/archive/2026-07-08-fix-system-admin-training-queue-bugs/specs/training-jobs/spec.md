## MODIFIED Requirements

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
