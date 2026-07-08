## ADDED Requirements

### Requirement: Generate Colab notebook and scoped credential on job creation

When a training job is created with `compute_backend=colab`, the system SHALL synchronously generate a self-contained Jupyter notebook (dataset-fetch cell, training cell mirroring the platform's fine-tuning logic, and callback cells) and a scoped, single-job, expiring credential, and SHALL return both to the caller. The credential SHALL be stored only as a salted hash plus a short prefix; the raw value SHALL be returned exactly once, embedded in the generated notebook.

#### Scenario: Notebook and credential generated on colab job creation

- **GIVEN** a Tenant Admin submits `POST /api/v1/training-jobs` with `compute_backend: "colab"` and valid hyperparameters
- **WHEN** the tenant has at least the configured minimum annotated entities
- **THEN** the response SHALL have status 201
- **AND** the response SHALL include a downloadable notebook (or a link to one) with the raw credential embedded in it
- **AND** the raw credential value SHALL NOT be retrievable again after this response

#### Scenario: Credential resolves to exactly one training job

- **GIVEN** a scoped credential generated for training job A
- **WHEN** the credential is presented on a callback request
- **THEN** the system SHALL resolve it to training job A and no other job
- **AND** the tenant context used for the request SHALL be training job A's owning tenant, not any value supplied by the caller

### Requirement: Callback endpoint accepts heartbeats, progress, and terminal results

The system SHALL expose a public-facing callback endpoint that accepts, for a given training job and scoped credential: heartbeat pings, progress updates (current epoch, current loss), and terminal results (completed with metrics and model artifacts, or failed with an error message). The endpoint SHALL be reachable without any of the platform's internal service-to-service credentials.

#### Scenario: Heartbeat updates last-heartbeat timestamp

- **GIVEN** a training job in `awaiting_notebook_launch` or `running` status with a valid, unexpired, unrevoked credential
- **WHEN** the notebook calls the callback endpoint with a heartbeat payload
- **THEN** the job's last-heartbeat timestamp SHALL be updated
- **AND** the job status SHALL transition to `running` if it was `awaiting_notebook_launch`

#### Scenario: Progress update reflected in job status

- **GIVEN** a colab training job in `running` status
- **WHEN** the notebook calls the callback endpoint with a progress payload (current_epoch, current_loss)
- **THEN** `GET /api/v1/training-jobs/{job_id}` SHALL reflect the updated `current_epoch` and `current_loss`

#### Scenario: Terminal success relays artifacts and metrics server-side

- **GIVEN** a colab training job in `running` status
- **WHEN** the notebook calls the callback endpoint with a completion payload (final metrics and model artifact data)
- **THEN** the system SHALL persist the artifacts to the same object-storage location convention used by platform-backed jobs
- **AND** the system SHALL register the resulting model version in the Model Registry
- **AND** the job status SHALL transition to `completed`

#### Scenario: Terminal failure reported by the notebook

- **GIVEN** a colab training job in `running` status
- **WHEN** the notebook calls the callback endpoint with a failure payload and an error message
- **THEN** the job status SHALL transition to `failed`
- **AND** `error_message` SHALL reflect the notebook-reported error

#### Scenario: Callback rejected with invalid or revoked credential

- **GIVEN** a credential that is expired, revoked, or unrecognized
- **WHEN** a callback request is made using that credential
- **THEN** the response SHALL have status 401 or 403
- **AND** no job state SHALL be modified

#### Scenario: Callback rejected when credential and job id mismatch

- **GIVEN** a valid credential scoped to training job A
- **WHEN** a callback request is made against training job B's callback URL using job A's credential
- **THEN** the response SHALL have status 403
- **AND** no job state SHALL be modified

### Requirement: Stalled colab jobs automatically fail

The system SHALL periodically check colab-backed training jobs in `awaiting_notebook_launch` or `running` status. If a job's last-heartbeat timestamp (or creation time, if no heartbeat was ever received) exceeds a configurable timeout window, the system SHALL transition the job to `failed` with an error message indicating the stall.

#### Scenario: Job never launched times out

- **GIVEN** a colab job in `awaiting_notebook_launch` status whose creation time exceeds the configured timeout window
- **WHEN** the periodic stall check runs
- **THEN** the job SHALL transition to `failed`
- **AND** `error_message` SHALL indicate no notebook launch was detected within the timeout window

#### Scenario: Running job goes silent and times out

- **GIVEN** a colab job in `running` status whose last-heartbeat timestamp exceeds the configured timeout window
- **WHEN** the periodic stall check runs
- **THEN** the job SHALL transition to `failed`
- **AND** `error_message` SHALL indicate the notebook stopped reporting within the timeout window

#### Scenario: Active job is not affected by the stall check

- **GIVEN** a colab job in `running` status whose last-heartbeat timestamp is within the configured timeout window
- **WHEN** the periodic stall check runs
- **THEN** the job's status SHALL remain unchanged

### Requirement: Colab job credential revocation on cancel

Cancelling a colab-backed training job SHALL revoke its scoped credential, so a notebook that is still running cannot successfully call back afterward.

#### Scenario: Cancelling a colab job revokes its credential

- **GIVEN** a colab job in `awaiting_notebook_launch` or `running` status
- **WHEN** a Tenant Admin cancels the job
- **THEN** the job status SHALL transition to `cancelled`
- **AND** subsequent callback requests using that job's credential SHALL be rejected
