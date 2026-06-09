## MODIFIED Requirements

### Requirement: Tenant-Scoped User Management

The system SHALL allow a Tenant Admin to create, read, update, and deactivate users within their own tenant scope. Users SHALL have one of these roles: `tenant_admin`, `business_user`, `annotator`. The system SHALL prevent cross-tenant user operations — a Tenant Admin from tenant A MUST NOT be able to create users in tenant B.

#### Scenario: Tenant Admin creates a user in their own tenant

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/acme-corp/users` with `{"email": "user@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `email`, `role: "annotator"`, `status: "active"`

#### Scenario: Tenant Admin attempts cross-tenant user creation

- **GIVEN** an authenticated Tenant Admin for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/tenants/other-corp/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate the tenant scope does not match
