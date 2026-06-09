## ADDED Requirements

### Requirement: Tenant-Admin User CRUD Endpoints

The system SHALL expose tenant-scoped user CRUD endpoints at `/api/v1/tenants/{slug}/users` for Tenant Admin self-service. These endpoints SHALL be gated by `resolve_tenant` (tenant slug validation + JWT tenant match) and a `tenant_admin` role check. The previous `/api/v1/admin/tenants/{tid}/users` endpoints SHALL be removed — system_admin no longer manages tenant users.

#### Scenario: Tenant Admin creates a user in their own tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/users` with `{"email": "user@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `email`, `role: "annotator"`, `status: "active"`

#### Scenario: Tenant Admin lists users in their own tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp" with existing users
- **WHEN** they GET `/api/v1/tenants/acme-corp/users`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a paginated list of users within the tenant

#### Scenario: Tenant Admin gets a specific user in their tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp" and a user with ID "user-123" in that tenant
- **WHEN** they GET `/api/v1/tenants/acme-corp/users/user-123`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain the user's `email`, `role`, and `status`

#### Scenario: Tenant Admin updates a user in their tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp" and a user "user-123" in that tenant
- **WHEN** they PUT `/api/v1/tenants/acme-corp/users/user-123` with `{"role": "business_user"}`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL reflect the updated role

#### Scenario: Tenant Admin deactivates a user in their tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp" and an active user "user-123" in that tenant
- **WHEN** they DELETE `/api/v1/tenants/acme-corp/users/user-123`
- **THEN** the response SHALL have status 200
- **AND** the user's `status` SHALL be `"inactive"`

#### Scenario: Tenant Admin cannot create users in another tenant (cross-tenant blocked)

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/other-corp/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate the tenant scope does not match

#### Scenario: Non-tenant-admin role cannot create users (role enforcement)

- **GIVEN** an authenticated `annotator` user for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate tenant admin access is required
