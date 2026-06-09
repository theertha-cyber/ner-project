## ADDED Requirements

### Requirement: Tenant Creation

The system SHALL allow a System Admin to create a new tenant by providing a name and optional slug. The system SHALL auto-generate a slug if not provided. The system SHALL create an isolated PostgreSQL schema `tenant_{tid}` and apply all tenant-scoped table migrations to it. The system SHALL create blob storage prefixes for documents and models. The system SHALL return the tenant record with `status: "active"` upon successful completion.

#### Scenario: System Admin creates a tenant with valid data

- **GIVEN** an authenticated System Admin user
- **WHEN** they POST to `/api/v1/admin/tenants` with `{"name": "Acme Corp"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `tenant` object with `id`, `name`, `slug`, `status: "active"`, `created_at`
- **AND** a PostgreSQL schema `tenant_{id}` SHALL exist
- **AND** the schema SHALL contain all tenant-scoped tables (tenant_user, document, etc.)

#### Scenario: System Admin creates a tenant with duplicate slug

- **GIVEN** a tenant with slug "acme-corp" exists
- **WHEN** the System Admin POSTs to `/api/v1/admin/tenants` with `{"name": "Acme Corp 2", "slug": "acme-corp"}`
- **THEN** the response SHALL have status 409
- **AND** the error message SHALL indicate the slug is already taken

### Requirement: Tenant Quotas

The system SHALL allow a System Admin to set resource quotas on a tenant during creation or update: `max_users`, `max_documents`, `max_storage_gb`, `max_model_versions`. The system SHALL reject operations that would exceed any quota with a 429 status code.

#### Scenario: Tenant exceeds user quota

- **GIVEN** a tenant with `max_users: 5` and 5 active users
- **WHEN** a System Admin attempts to create a 6th user for this tenant
- **THEN** the response SHALL have status 429
- **AND** the error message SHALL indicate the user quota is exceeded

### Requirement: Tenant Listing and Detail

The system SHALL allow a System Admin to list all tenants with pagination, view a single tenant by ID, update tenant metadata (name, quotas), and deactivate a tenant. Deactivation SHALL set `status: "inactive"` and reject all tenant-scoped API requests.

#### Scenario: System Admin lists tenants with pagination

- **GIVEN** 25 tenants exist in the system
- **WHEN** the System Admin GETs `/api/v1/admin/tenants?page=1&per_page=10`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain an array of 10 tenant objects
- **AND** the response SHALL include `total: 25`, `page: 1`, `per_page: 10`

#### Scenario: System Admin deactivates a tenant

- **GIVEN** an active tenant with id `tid-123`
- **WHEN** the System Admin POSTs to `/api/v1/admin/tenants/tid-123/deactivate`
- **THEN** the response SHALL have status 200
- **AND** `status` SHALL be `"inactive"`
- **WHEN** any user from that tenant attempts any API request
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate the tenant is deactivated
