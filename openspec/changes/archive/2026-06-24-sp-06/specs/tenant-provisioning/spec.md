## ADDED Requirements

### Requirement: System Admin Tenant User Listing

The system SHALL expose `GET /api/v1/admin/tenants/{tenant_id}/users` for System Admins to retrieve all users belonging to a specific tenant. The endpoint SHALL require system-admin authentication. The response SHALL include each user's `id`, `email`, `role`, `status`, and `created_at`. The endpoint SHALL return 404 if the tenant does not exist.

#### Scenario: System Admin lists users of a tenant

- **GIVEN** an authenticated System Admin and a tenant with id `tid-123` that has 3 users
- **WHEN** they GET `/api/v1/admin/tenants/tid-123/users`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a `users` array with 3 entries
- **AND** each entry SHALL include `id`, `email`, `role`, `status`, `created_at`

#### Scenario: System Admin requests users for non-existent tenant

- **GIVEN** no tenant exists with id `tid-nonexistent`
- **WHEN** a System Admin GETs `/api/v1/admin/tenants/tid-nonexistent/users`
- **THEN** the response SHALL have status 404

#### Scenario: Non-system-admin cannot access the endpoint

- **GIVEN** an authenticated `tenant_admin` user
- **WHEN** they GET `/api/v1/admin/tenants/tid-123/users`
- **THEN** the response SHALL have status 403
