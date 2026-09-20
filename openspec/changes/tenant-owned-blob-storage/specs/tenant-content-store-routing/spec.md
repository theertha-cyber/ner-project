## ADDED Requirements

### Requirement: The content store is resolved per tenant at write time

The system SHALL resolve which content store serves a write from the tenant whose request produced the bytes. Resolution SHALL consult the tenant's integration-profile `content_store_adapter` selection and whether that selection is executable for that tenant. A selection of `tenant_azure_blob` that is executable SHALL resolve to a content store backed by that tenant's own container; every other outcome SHALL resolve to the platform content store. Resolution SHALL occur on `put` only; `open` and `delete` SHALL route by the recorded backend kind as governed by `content-store-backend-attribution`.

The resolved store SHALL be bound to the tenant that resolution was performed for. The system SHALL NOT serve one tenant's bytes from a store resolved for another tenant.

#### Scenario: A tenant with an active content-store connection writes to its own container

- **GIVEN** a tenant whose profile records `content_store_adapter = tenant_azure_blob` and which holds an active `azure_blob_content_store` connection
- **WHEN** a document is uploaded for that tenant
- **THEN** the bytes SHALL be written to that tenant's container
- **AND** no put SHALL have been performed against platform MinIO

#### Scenario: A recorded selection without an active connection does not route

- **GIVEN** a tenant whose profile records `content_store_adapter = tenant_azure_blob` and which holds no active `azure_blob_content_store` connection
- **WHEN** a document is uploaded for that tenant
- **THEN** the bytes SHALL be written to the platform content store
- **AND** the recorded selection SHALL have no effect

#### Scenario: A tenant's store never serves another tenant

- **GIVEN** two tenants, each with an active content-store connection naming a different container
- **WHEN** a document is uploaded for each
- **THEN** each document's bytes SHALL be written only to its own tenant's container

#### Scenario: Resolution is unaffected by the data-plane mode

- **GIVEN** a tenant whose data-plane mode is `platform` and which holds an active `azure_blob_content_store` connection with `content_store_adapter = tenant_azure_blob`
- **WHEN** a document is uploaded for that tenant
- **THEN** the bytes SHALL be written to that tenant's container

### Requirement: Both the durable and the working store follow the tenant

The system SHALL resolve the durable content store and the working content store for the same tenant to the same backend. When a tenant's content store resolves to its own container, a `platform_blob` document's durable original and an `ephemeral` document's working copy SHALL both be written there, under separate prefixes, and neither SHALL be written to platform storage.

#### Scenario: An ephemeral working copy goes to the tenant's container

- **GIVEN** a tenant with an active content-store connection and `ephemeral` retention
- **WHEN** a document is uploaded and processing begins
- **THEN** the working copy SHALL have been written to that tenant's container
- **AND** no put SHALL have been performed against the platform working store

#### Scenario: Durable and working bytes are separated within the container

- **GIVEN** a tenant with an active content-store connection
- **WHEN** one `platform_blob` document and one `ephemeral` document are stored
- **THEN** the two objects SHALL be written under different prefixes within the container

#### Scenario: A chat attachment follows the same routing

- **GIVEN** a tenant with an active content-store connection
- **WHEN** a file is attached to a chat conversation
- **THEN** its bytes SHALL be written to that tenant's container
- **AND** no put SHALL have been performed against platform MinIO

### Requirement: Failure is closed, with no fallback to platform storage

When a tenant's content store is resolved to its own container and that container cannot be reached, the system SHALL fail the operation. The system SHALL NOT write the bytes to platform storage, SHALL NOT buffer the bytes platform-side for later retry, and SHALL NOT retry the write against a different backend. An upload SHALL be rejected before its bytes are accepted. A content read SHALL fail with a finite, safe error that is distinguishable from a platform fault and that names no container, account, endpoint, or credential.

Service readiness SHALL continue to reflect only platform dependencies; one tenant's unreachable container SHALL NOT mark the service unready or affect any other tenant's requests.

#### Scenario: An upload is rejected before bytes are accepted

- **GIVEN** a tenant with an active content-store connection whose container is unreachable
- **WHEN** an upload is attempted for that tenant
- **THEN** the request SHALL be rejected with a finite safe unavailable error
- **AND** no bytes SHALL have been written to any platform store

#### Scenario: There is no fallback write

- **GIVEN** the tenant from the preceding scenario and an instrumented platform content store
- **WHEN** the upload is rejected
- **THEN** no put SHALL have been performed against the platform content store

#### Scenario: The error names no storage configuration

- **GIVEN** a failed content operation against an unreachable tenant container
- **WHEN** the error returned to the caller is inspected
- **THEN** it SHALL NOT contain a container name, account name, endpoint, region, or credential

#### Scenario: One tenant's outage does not affect another tenant

- **GIVEN** two tenants with active content-store connections, one of whose containers is unreachable
- **WHEN** a document is uploaded for each
- **THEN** the affected tenant's upload SHALL be rejected
- **AND** the other tenant's upload SHALL succeed

#### Scenario: Readiness reflects only platform dependencies

- **GIVEN** a tenant whose container is unreachable
- **WHEN** the service readiness endpoint is queried
- **THEN** it SHALL NOT report the service as unready on account of that tenant's container

### Requirement: Resolved tenant content stores are cached within a bounded size

The system SHALL cache resolved tenant content stores so that a client is not constructed per operation, and SHALL bound the number of cached stores so that the count of tenants does not determine resource consumption without limit. Retiring, pausing, or replacing a tenant's content-store connection SHALL invalidate that tenant's cached store, so that no operation is served by a store built from a credential that is no longer active.

#### Scenario: Repeated writes reuse one resolved store

- **GIVEN** a tenant with an active content-store connection
- **WHEN** several documents are uploaded in succession
- **THEN** the tenant's content store SHALL have been constructed once

#### Scenario: Retiring a connection invalidates the cached store

- **GIVEN** a tenant with a cached, resolved tenant content store
- **WHEN** its content-store connection is retired
- **THEN** a subsequent write for that tenant SHALL resolve to the platform content store
- **AND** SHALL NOT be served by the cached tenant store

### Requirement: Model artifacts and experiment tracking are excluded from content-store routing

Fine-tuned model artifacts produced by training and the artifacts of experiment-tracking runs SHALL remain in platform-operated storage for every tenant, regardless of that tenant's content-store selection or data-plane mode. They are platform operational output rather than tenant-submitted content. The system SHALL NOT route them through the tenant content store, and this exclusion SHALL be stated in tenant-facing residency documentation rather than left implicit.

#### Scenario: Training artifacts stay in platform storage

- **GIVEN** a tenant with an active content-store connection
- **WHEN** a training job for that tenant completes and writes its model artifacts
- **THEN** the artifacts SHALL be written to platform-operated storage
- **AND** no artifact SHALL be written to the tenant's container

#### Scenario: A model is served from platform storage for a routed tenant

- **GIVEN** the tenant and trained model version from the preceding scenario
- **WHEN** that model version is loaded for serving
- **THEN** its artifacts SHALL be read from platform-operated storage
