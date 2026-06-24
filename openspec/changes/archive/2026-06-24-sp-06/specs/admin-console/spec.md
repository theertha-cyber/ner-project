## MODIFIED Requirements

### Requirement: Tenant Detail View

The system SHALL provide a tenant detail page at `/admin/tenants/{tenant_id}` that displays tenant metadata, current quotas and usage, a list of users belonging to this tenant, and controls to edit quotas, deactivate the tenant, or navigate to the tenant's own admin panel. The user list SHALL be loaded from `GET /api/v1/admin/tenants/{tenant_id}/users` and SHALL show each user's email, role, and status.

#### Scenario: System Admin views tenant details

- **GIVEN** an authenticated System Admin and tenant "acme-corp" with id `tid-123`
- **WHEN** they navigate to `/admin/tenants/tid-123`
- **THEN** the page SHALL display the tenant name, slug, status, created_at
- **AND** SHALL show quota usage: users (e.g., `3 / 10`), documents, storage
- **AND** SHALL list all users for this tenant with columns: email, role, status
- **AND** SHALL have an "Edit Quotas" button and a "Deactivate Tenant" button

#### Scenario: Tenant with no users shows empty state

- **GIVEN** an authenticated System Admin and a tenant with id `tid-456` that has no users other than the initial admin
- **WHEN** they navigate to `/admin/tenants/tid-456`
- **THEN** the users section SHALL render with whatever users exist (at minimum the tenant admin created at provisioning time)
