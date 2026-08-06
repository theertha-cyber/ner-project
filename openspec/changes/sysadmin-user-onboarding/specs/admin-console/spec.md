## MODIFIED Requirements

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
