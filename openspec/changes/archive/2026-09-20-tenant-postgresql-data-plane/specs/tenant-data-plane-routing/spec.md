## ADDED Requirements

### Requirement: Every tenant has exactly one data plane recorded in the control plane

The system SHALL record, for every tenant, exactly one data-plane record in `public.tenant_data_planes` holding the tenant id, a `mode` of `platform` or `tenant_owned`, a `status` of `awaiting_store`, `provisioning`, `provisioning_failed`, `ready`, `migration_required`, `paused`, or `store_retired`, the bound data-plane connection id (`tenant_owned` only), the store's recorded schema revision, and a finite safe status reason. The record SHALL contain no endpoint, credential, provider diagnostic, or tenant content. The `mode` SHALL be immutable after creation. Every tenant existing before this change SHALL be backfilled as `mode = platform`, `status = ready`.

#### Scenario: Existing tenants are backfilled to the platform plane

- **GIVEN** tenants provisioned before this change
- **WHEN** the migration introducing `public.tenant_data_planes` is applied
- **THEN** each tenant SHALL have one data-plane record with `mode = platform` and `status = ready`
- **AND** no tenant SHALL lack a data-plane record

#### Scenario: Mode cannot be changed

- **GIVEN** a tenant with `mode = platform`
- **WHEN** any API or service attempts to set its `mode` to `tenant_owned`
- **THEN** the system SHALL reject the change with finite safe code `DATA_PLANE_MODE_IMMUTABLE`
- **AND** the record SHALL be unchanged

#### Scenario: Data-plane record carries no sensitive values

- **GIVEN** a `tenant_owned` tenant with an active data-plane connection
- **WHEN** its data-plane record is read through any API
- **THEN** the response SHALL contain mode, status, reason class, schema revision, and timestamps only
- **AND** it SHALL NOT contain a host, database name, username, secret reference value, or provider error text

### Requirement: Tenant data engines are resolved per tenant with no platform fallback

The system SHALL obtain every engine or session used to read or write a tenant schema through the shared engine resolver, keyed by the server-derived tenant id. For a `platform` tenant the resolver SHALL return the platform engine. For a `tenant_owned` tenant with `status = ready` it SHALL return a per-tenant engine built from the tenant's active `azure_postgresql_data_plane` connection and resolved secret, with TLS `verify-full`, a bounded pool, and connect and statement timeouts. For a `tenant_owned` tenant in any other status, or whose connection cannot be resolved, the resolver SHALL raise a typed data-plane error and SHALL NOT return the platform engine. No service or worker SHALL construct an engine for tenant-schema access from `settings.database_url` or `settings.database_url_sync` directly.

#### Scenario: Platform tenant resolves to the platform engine

- **GIVEN** a tenant with `mode = platform`
- **WHEN** the resolver is asked for that tenant's engine
- **THEN** it SHALL return the platform engine

#### Scenario: Residency tenant resolves to its own store

- **GIVEN** a tenant with `mode = tenant_owned`, `status = ready`, and an active data-plane connection
- **WHEN** a document-service request for that tenant reads its documents
- **THEN** the query SHALL execute against the tenant's store
- **AND** no statement for that tenant SHALL execute against the platform database

#### Scenario: Residency tenant never falls back to the platform engine

- **GIVEN** a `tenant_owned` tenant whose connection is paused or whose secret cannot be resolved
- **WHEN** any service or worker requests that tenant's engine
- **THEN** the resolver SHALL raise a typed data-plane error
- **AND** the platform engine SHALL NOT be returned

#### Scenario: Workers use the resolver

- **GIVEN** the extraction, training, analytics, OCR, and blob-sync workers
- **WHEN** their tenant-schema database access is inspected by an automated source check
- **THEN** no tenant-schema access SHALL construct an engine from the platform database URL directly

#### Scenario: Engine cache is invalidated on connection change

- **GIVEN** a cached engine for a `tenant_owned` tenant
- **WHEN** that tenant's data-plane connection is paused, replaced, or retired
- **THEN** the cached engine SHALL be disposed before the next resolution
- **AND** the next resolution SHALL reflect the new connection state

### Requirement: Tenant content routes are gated on data-plane readiness

The system SHALL reject every tenant content API operation (documents, extraction, annotation, training, analytics, chat, widget chat, blob sync execution) for a `tenant_owned` tenant whose data-plane status is not `ready` with HTTP 409 and finite safe code `TENANT_DATA_PLANE_NOT_READY` carrying the status class. Tenant user administration, data-source settings, and data-plane status SHALL remain available.

#### Scenario: Awaiting-store tenant cannot upload

- **GIVEN** a `tenant_owned` tenant in `awaiting_store`
- **WHEN** a tenant user uploads a document
- **THEN** the response SHALL be 409 with code `TENANT_DATA_PLANE_NOT_READY` and status class `awaiting_store`
- **AND** no bytes SHALL be written to any platform or tenant store

#### Scenario: Awaiting-store tenant administrator can configure the store

- **GIVEN** a `tenant_owned` tenant in `awaiting_store`
- **WHEN** its tenant administrator opens data-source settings and creates a data-plane connection draft
- **THEN** the operation SHALL succeed

### Requirement: Fleet operations enumerate tenants from the control plane

Operations that act on every tenant schema — entity-view reconciliation, chat query-role provisioning, schema verification, analytics refresh, and system-admin summaries — SHALL enumerate tenants from `public.tenants` joined to `public.tenant_data_planes` and SHALL resolve each tenant's engine, rather than enumerating `pg_namespace` on the platform database. A tenant whose engine cannot be resolved SHALL be skipped with a safe per-tenant outcome class and SHALL NOT abort the operation for other tenants.

#### Scenario: Reconciler reaches a residency tenant

- **GIVEN** one `platform` tenant and one `ready` `tenant_owned` tenant, each with an active entity definition
- **WHEN** the entity-view reconciler runs
- **THEN** generated entity tables SHALL be reconciled in the platform schema for the first tenant and in the tenant store for the second

#### Scenario: One unreachable store does not abort the fleet run

- **GIVEN** three tenants, one of which is `tenant_owned` with an unreachable store
- **WHEN** chat query-role provisioning runs
- **THEN** the other two tenants SHALL be provisioned
- **AND** the unreachable tenant SHALL be reported with a safe outcome class only
