## ADDED Requirements

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

The system SHALL provide a tenant detail page at `/admin/tenants/{tenant_id}` that displays tenant metadata, current quotas and usage, a list of users belonging to this tenant, and controls to edit quotas, deactivate the tenant, or navigate to the tenant's own admin panel.

#### Scenario: System Admin views tenant details

- **GIVEN** an authenticated System Admin and tenant "acme-corp" with id `tid-123`
- **WHEN** they navigate to `/admin/tenants/tid-123`
- **THEN** the page SHALL display the tenant name, slug, status, created_at
- **AND** SHALL show quota usage: users (e.g., `3 / 10`), documents, storage
- **AND** SHALL list all users for this tenant
- **AND** SHALL have an "Edit Quotas" button and a "Deactivate Tenant" button

### Requirement: GPU Job Monitoring

The system SHALL display a read-only list of training jobs across all tenants in the admin console. Each job entry SHALL show tenant name, job status, model version (if completed), duration, and F1 score (if available). This is a read-only view — job management happens per-tenant.

#### Scenario: System Admin views all training jobs

- **GIVEN** 3 training jobs exist across 2 tenants (1 running, 2 completed)
- **WHEN** the System Admin navigates to `/admin/jobs`
- **THEN** the page SHALL display 3 job rows
- **AND** each row SHALL show `tenant`, `status`, `model_version`, `duration`, `f1_score`
- **AND** the view SHALL be read-only (no create/edit/delete controls)
