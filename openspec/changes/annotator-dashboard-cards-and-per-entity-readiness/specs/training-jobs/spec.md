## ADDED Requirements

### Requirement: Per-Entity-Type Minimum Dataset Gate

Training job submission SHALL support an optional per-entity-type minimum, configured via the `NER_MIN_ENTITIES_PER_TYPE` environment variable. The variable SHALL default to `0`, at which the gate is inert and submission behaviour is unchanged.

When the configured value is greater than zero, the system SHALL count confirmed spans per entity type for the tenant, evaluate every active entity definition for that tenant, and reject the submission with `422` if any active entity type has fewer spans than the configured minimum. Entity types with no spans at all SHALL count as zero and SHALL trigger rejection. The rejection detail SHALL name the entity types that fall short together with their current counts, so the caller can act on it without a second query.

This gate SHALL be evaluated independently of the existing total-count gate (`NER_MIN_TRAINING_ENTITIES`). Both SHALL apply when both are configured, and neither SHALL change the other's meaning or default.

#### Scenario: gate is inert at its default

- **GIVEN** `NER_MIN_ENTITIES_PER_TYPE` is unset and the tenant has 3 spans across 1 entity type
- **WHEN** a tenant admin submits a training job
- **THEN** the job is accepted with status `201`

#### Scenario: submission rejected when one entity type falls short

- **GIVEN** `NER_MIN_ENTITIES_PER_TYPE` is `200`
- **AND** the tenant's active entity types have counts `PROGRAMMING_LANGUAGE: 400`, `JOB_TITLE: 210`, `CONTACT_DETAILS: 40`
- **WHEN** a tenant admin submits a training job
- **THEN** the response status is `422`
- **AND** the detail names `CONTACT_DETAILS` and its count of `40`
- **AND** the detail does not name `PROGRAMMING_LANGUAGE` or `JOB_TITLE`

#### Scenario: entity type with zero spans blocks submission

- **GIVEN** `NER_MIN_ENTITIES_PER_TYPE` is `200`
- **AND** the tenant has an active entity definition `EDUCATION` with no spans recorded
- **WHEN** a tenant admin submits a training job
- **THEN** the response status is `422`
- **AND** the detail names `EDUCATION` with a count of `0`

#### Scenario: submission accepted when every active type meets the minimum

- **GIVEN** `NER_MIN_ENTITIES_PER_TYPE` is `200`
- **AND** every active entity type for the tenant has at least 200 confirmed spans
- **WHEN** a tenant admin submits a training job
- **THEN** the job is accepted with status `201`

#### Scenario: inactive entity types are excluded from the gate

- **GIVEN** `NER_MIN_ENTITIES_PER_TYPE` is `200`
- **AND** the tenant has an entity definition `LEGACY_FIELD` with `is_active = false` and 0 spans
- **AND** every active entity type has at least 200 confirmed spans
- **WHEN** a tenant admin submits a training job
- **THEN** the job is accepted with status `201`

#### Scenario: both gates apply independently

- **GIVEN** `NER_MIN_TRAINING_ENTITIES` is `500` and `NER_MIN_ENTITIES_PER_TYPE` is `200`
- **AND** the tenant has 900 total spans but one active entity type holds only 50
- **WHEN** a tenant admin submits a training job
- **THEN** the response status is `422`
- **AND** the detail identifies the per-entity-type shortfall
