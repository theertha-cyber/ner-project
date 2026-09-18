## MODIFIED Requirements

### Requirement: Submit training job

The system SHALL accept training job submissions from Tenant Admin users. The submission body SHALL accept an optional `source_scope` field (`manual`, `automated`, or `import`) naming which of the three independent annotation workflows this job trains on; a training job SHALL NOT blend data across workflows. The system SHALL validate the tenant has at least the configured minimum annotated entities, scoped to `source_scope` when one is given, before accepting a job: `automated` counts only spans carrying a `span_batch_provenance` row (promoted from an accepted automated batch), `manual` counts only spans without one, `import` skips this entity-count gate and the per-entity-type gate entirely (imported data lives in `imported_annotations`, not `spans`), and an omitted `source_scope` counts the tenant's full corpus as before this field existed. The system SHALL create the job in "pending_approval" status with the submitted `source_scope` persisted on it and SHALL NOT enqueue a Celery task. The system SHALL return a 201 status with the created job, including its `source_scope`.

#### Scenario: Submit a valid training job

- **GIVEN** a tenant with at least the minimum annotated entities across their corpus
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with an empty (or hyperparameter-free) body
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain `id`, `status` ("pending_approval"), `created_at`, `hyperparams: null`, and `source_scope: null`
- **AND** the response body SHALL NOT contain `celery_task_id`
- **AND** no Celery task SHALL be enqueued

#### Scenario: Submit training job with insufficient entities

- **GIVEN** a tenant with fewer than the configured minimum annotated entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 422
- **AND** the error SHALL indicate the minimum entity threshold is not met

#### Scenario: Submit training job as non-admin

- **GIVEN** an authenticated annotator user
- **WHEN** the annotator POSTs to `/api/v1/training-jobs`
- **THEN** the response SHALL have status 403

#### Scenario: Submit training job with invalid hyperparameters

- **GIVEN** a tenant with sufficient entities
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with a body containing hyperparameter fields (`learning_rate`, `num_epochs`, `batch_size`, or `max_seq_length`)
- **THEN** the response SHALL have status 422, since the submission body accepts only `source_scope` and rejects unrecognized fields

#### Scenario: Automated-scoped submission gates only on promoted spans

- **GIVEN** a tenant whose only promoted-automated span count is below the configured minimum, while its manual span count alone would clear it
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"source_scope": "automated"}`
- **THEN** the response SHALL have status 422
- **AND** the reported entity count SHALL reflect only the promoted-automated spans

#### Scenario: Manual-scoped submission excludes promoted spans from its gate

- **GIVEN** the same tenant as the previous scenario
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"source_scope": "manual"}`
- **THEN** the response SHALL have status 201, since the manual-only count clears the minimum

#### Scenario: Import-scoped submission skips the span-based gates entirely

- **GIVEN** a tenant with zero spans and a configured minimum well above zero
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"source_scope": "import"}`
- **THEN** the response SHALL have status 201, since import-scoped jobs are not gated on `spans` at all

#### Scenario: An invalid source_scope value is rejected

- **GIVEN** any tenant
- **WHEN** a Tenant Admin POSTs to `/api/v1/training-jobs` with `{"source_scope": "bogus"}`
- **THEN** the response SHALL have status 422
