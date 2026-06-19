## MODIFIED Requirements

### Requirement: Tenant-Admin User CRUD Endpoints

The system SHALL expose tenant-scoped user CRUD endpoints at `/api/v1/users` for Tenant Admin self-service. These endpoints SHALL be gated by `resolve_tenant_from_jwt` (JWT-only tenant validation — no URL slug required) and a `tenant_admin` role check. The authenticated tenant admin's JWT claim determines the tenant scope; no `{tenant_id}` path parameter is needed or accepted.

#### Scenario: Tenant Admin creates a user in their own tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/users` with `{"email": "user@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `email`, `role: "annotator"`, `status: "active"`

#### Scenario: Tenant Admin lists users in their own tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp" with existing users
- **WHEN** they GET `/api/v1/users`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a list of users scoped to the tenant from the JWT

#### Scenario: Tenant Admin gets a specific user in their tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp" and a user with ID "user-123" in that tenant
- **WHEN** they GET `/api/v1/users/user-123`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain the user's `email`, `role`, and `status`

#### Scenario: Tenant Admin updates a user in their tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp" and a user "user-123" in that tenant
- **WHEN** they PUT `/api/v1/users/user-123` with `{"role": "business_user"}`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL reflect the updated role

#### Scenario: Tenant Admin deactivates a user in their tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp" and an active user "user-123" in that tenant
- **WHEN** they DELETE `/api/v1/users/user-123`
- **THEN** the response SHALL have status 200
- **AND** the user's `status` SHALL be `"inactive"`

#### Scenario: Non-tenant-admin role cannot access user endpoints (role enforcement)

- **GIVEN** an authenticated `annotator` user for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate tenant admin access is required

#### Scenario: Unauthenticated request is rejected

- **GIVEN** a request with no Bearer token
- **WHEN** they POST to `/api/v1/users`
- **THEN** the response SHALL have status 401
