# Admin Console

## Purpose

System Admin SPA for managing tenants, viewing tenant details, editing quotas, and monitoring GPU training jobs across all tenants.

---
## Requirements
### Requirement: Tenant Management Dashboard

The system SHALL provide a System Admin SPA at `/admin/*` that displays a paginated list of all tenants with their status, user count, document count, and storage usage. The dashboard SHALL allow the System Admin to create new tenants, view tenant details, edit tenant metadata and quotas, and deactivate tenants.

#### Scenario: System Admin views tenant dashboard

- **GIVEN** an authenticated System Admin user and 3 tenants exist
- **WHEN** the System Admin navigates to `/admin/tenants`
- **THEN** the page SHALL display a table with 3 tenant rows
- **AND** each row SHALL show `name`, `slug`, `status`, `user_count`, `created_at`
- **AND** a "Create Tenant" button SHALL be visible

#### Scenario: System Admin creates tenant via UI

- **GIVEN** an authenticated System Admin on `/admin/tenants`
- **WHEN** they click "Create Tenant", fill in `name: "Acme Corp"`, and submit
- **THEN** the page SHALL navigate to the new tenant detail view
- **AND** show a success message "Tenant created successfully"
- **AND** the tenant SHALL have `status: "active"`

### Requirement: Tenant Detail View

The system SHALL provide a tenant detail page at `/admin/tenants/{tenant_id}` that displays tenant metadata, current quotas and usage, a list of users belonging to this tenant, and controls to edit quotas, deactivate the tenant, create a new user in this tenant, or navigate to the tenant's own admin panel.

#### Scenario: System Admin views tenant details

- **GIVEN** an authenticated System Admin and tenant "acme-corp" with id `tid-123`
- **WHEN** they navigate to `/admin/tenants/tid-123`
- **THEN** the page SHALL display the tenant name, slug, status, created_at
- **AND** SHALL show quota usage: users (e.g., `3 / 10`), documents, storage
- **AND** SHALL list all users for this tenant
- **AND** SHALL have an "Edit Quotas" button, a "Deactivate Tenant" button, and a "Create User" button

#### Scenario: System Admin creates a user in the tenant from this view

- **GIVEN** an authenticated System Admin on `/admin/tenants/tid-123` for tenant "acme-corp"
- **WHEN** they click "Create User", fill in email, password, and role, and submit
- **THEN** the request SHALL be sent to `POST /api/v1/admin/tenants/tid-123/users`
- **AND** on success the new user SHALL appear in the tenant's user list on the page
- **AND** the users quota usage indicator SHALL update to reflect the new count

### Requirement: GPU Job Monitoring

The system SHALL display a read-only list of training jobs across all tenants in the admin console. Each job entry SHALL show tenant name, job status, model version (if completed), duration, and F1 score (if available). This is a read-only view — job management happens per-tenant.

#### Scenario: System Admin views all training jobs

- **GIVEN** 3 training jobs exist across 2 tenants (1 running, 2 completed)
- **WHEN** the System Admin navigates to `/admin/jobs`
- **THEN** the page SHALL display 3 job rows
- **AND** each row SHALL show `tenant`, `status`, `model_version`, `duration`, `f1_score`
- **AND** the view SHALL be read-only (no create/edit/delete controls)

### Requirement: System Admin chooses and observes the tenant data plane

The Create Tenant form SHALL offer a data-plane choice of "Platform database" (default) or "Tenant-owned Azure PostgreSQL", stating that the choice cannot be changed after creation and that tenant-owned tenants must use temporary or source-only original retention. The tenant list and detail views SHALL show each tenant's data-plane mode and status class and, for tenant-owned tenants, the last store health outcome class. Document counts and document quota usage SHALL be taken from the content-free document registry. No view SHALL display tenant store endpoints, credentials, or provider diagnostics.

#### Scenario: System Admin creates a tenant-owned tenant

- **GIVEN** an authenticated System Admin on `/admin/tenants`
- **WHEN** they click "Create Tenant", enter a name, select "Tenant-owned Azure PostgreSQL", and submit
- **THEN** the request SHALL include `data_plane_mode: "tenant_owned"`
- **AND** the tenant detail view SHALL show data plane "Tenant-owned" with status "Awaiting store"

#### Scenario: Document counts remain visible during a tenant outage

- **GIVEN** a tenant-owned tenant with an unreachable store and 12 registered documents
- **WHEN** the System Admin views the tenant detail page
- **THEN** document quota usage SHALL show 12
- **AND** store health SHALL show "Unreachable"
