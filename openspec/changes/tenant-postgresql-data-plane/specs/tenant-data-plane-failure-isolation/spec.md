## ADDED Requirements

### Requirement: An unreachable tenant store fails closed for that tenant only

When a `ready` `tenant_owned` tenant's store cannot be reached, authenticated, or times out, the system SHALL fail that tenant's content API operations with HTTP 503 and finite safe code `TENANT_DATA_PLANE_UNAVAILABLE`, and SHALL NOT serve partial results assembled from any other store. Requests for other tenants SHALL be unaffected. Error responses, logs, metrics, traces, and audit payloads SHALL contain no endpoint, credential, driver error text, SQL, or tenant content.

#### Scenario: Chat fails closed during a store outage

- **GIVEN** a `ready` residency tenant whose store is unreachable
- **WHEN** a tenant user sends a chat message
- **THEN** the response SHALL be 503 with code `TENANT_DATA_PLANE_UNAVAILABLE`
- **AND** no conversation or message row SHALL be written to the platform database

#### Scenario: Other tenants are unaffected

- **GIVEN** a residency tenant with an unreachable store and a platform tenant
- **WHEN** both tenants list documents concurrently
- **THEN** the platform tenant SHALL receive its documents with HTTP 200
- **AND** the residency tenant SHALL receive 503 `TENANT_DATA_PLANE_UNAVAILABLE`

#### Scenario: Driver error text is not exposed

- **GIVEN** a store outage that raises a driver error containing the host name
- **WHEN** the error is returned, logged, and traced
- **THEN** none of those outputs SHALL contain the host name or driver message

### Requirement: Uploads are rejected before bytes are accepted when the store is unavailable

The system SHALL verify that a `tenant_owned` tenant's store is resolvable and reachable before accepting upload bytes, and SHALL reject the upload with `TENANT_DATA_PLANE_UNAVAILABLE` otherwise, writing nothing to the platform content store or registry.

#### Scenario: Upload during outage writes nothing

- **GIVEN** a residency tenant whose store is unreachable
- **WHEN** a user uploads a document
- **THEN** the response SHALL be 503 `TENANT_DATA_PLANE_UNAVAILABLE`
- **AND** no working copy, registry row, or document row SHALL be created

### Requirement: Background tasks retry with bounded backoff and then park

Background work for a `tenant_owned` tenant (OCR processing, batch extraction, relational projection, analytics refresh, blob sync, training data loading, provisioning) that fails because the tenant store is unavailable SHALL retry with bounded exponential backoff within a configured maximum and then stop in a failed-retryable state recorded with a safe reason class. The system SHALL NOT hold tenant content (document text, spans, chunks, entities, messages) in platform queues, caches, or tables while waiting, and task payloads SHALL carry identifiers only. One tenant's parked or retrying tasks SHALL NOT consume more than a configured share of shared worker concurrency.

#### Scenario: Extraction parks after bounded retries

- **GIVEN** a batch extraction task for a residency tenant whose store stays unreachable
- **WHEN** the retry budget is exhausted
- **THEN** the task SHALL stop in a failed-retryable state with reason class `data_plane_unavailable`
- **AND** its payload SHALL contain identifiers only

#### Scenario: No content is buffered on the platform

- **GIVEN** OCR has produced text for a residency tenant's document and the store becomes unreachable before the spans are written
- **WHEN** the OCR task fails
- **THEN** the produced text SHALL be discarded, not persisted on the platform
- **AND** the document SHALL be reprocessable from its source or working copy after recovery, subject to its retention mode

### Requirement: Per-tenant store health is a content-free control-plane signal

The system SHALL record for each `tenant_owned` tenant a last health outcome class (`healthy`, `unreachable`, `auth_failed`, `timeout`) and timestamp in the control plane, updated by resolver failures and a periodic lightweight probe, and SHALL expose it to the tenant administrator and System Admin. Service `/health` readiness SHALL continue to reflect only platform dependencies and SHALL NOT become not-ready because a tenant store is unavailable.

#### Scenario: Service stays ready during a tenant outage

- **GIVEN** a residency tenant whose store is unreachable
- **WHEN** `/health` is requested on any service
- **THEN** the response SHALL be HTTP 200 if platform dependencies are reachable
- **AND** the tenant's recorded health outcome SHALL be `unreachable`

#### Scenario: Recovery is detected

- **GIVEN** a residency tenant recorded as `unreachable`
- **WHEN** its store becomes reachable and the probe runs
- **THEN** its health outcome SHALL become `healthy`
- **AND** content routes SHALL succeed again without operator action
