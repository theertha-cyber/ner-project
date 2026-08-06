## ADDED Requirements

### Requirement: System Admin Cross-Tenant User Creation Endpoint

The system SHALL expose `POST /api/v1/admin/tenants/{tenant_id}/users` for System Admin onboarding of users into any tenant. This endpoint SHALL be gated by a `system_admin` role check. The `tenant_id` SHALL be taken explicitly from the URL path — never inferred from the caller's JWT. The endpoint SHALL accept the same request body shape as the Tenant Admin creation endpoint (`email`, `password`, `role`) and SHALL apply the same validation, `max_users` quota enforcement, and per-tenant email-uniqueness rules as `POST /api/v1/users`. The `role` field SHALL accept `tenant_admin`, `business_user`, or `annotator`.

#### Scenario: System Admin creates a Business User in a specific tenant

- **GIVEN** an authenticated System Admin and an active tenant "acme-corp" with id `tid-123`
- **WHEN** they POST to `/api/v1/admin/tenants/tid-123/users` with `{"email": "biz@acme.com", "password": "secure-password", "role": "business_user"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `email: "biz@acme.com"`, `role: "business_user"`, `status: "active"`
- **AND** the created user SHALL belong to tenant `tid-123`

#### Scenario: System Admin creates a Tenant Admin in a specific tenant

- **GIVEN** an authenticated System Admin and an active tenant "acme-corp" with id `tid-123`
- **WHEN** they POST to `/api/v1/admin/tenants/tid-123/users` with `{"email": "admin2@acme.com", "password": "secure-password", "role": "tenant_admin"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `role: "tenant_admin"`

#### Scenario: System Admin creates an Annotator in a specific tenant

- **GIVEN** an authenticated System Admin and an active tenant "acme-corp" with id `tid-123`
- **WHEN** they POST to `/api/v1/admin/tenants/tid-123/users` with `{"email": "ann@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 201
- **AND** the response body SHALL contain a `user` object with `role: "annotator"`

#### Scenario: System Admin targets a nonexistent tenant

- **GIVEN** an authenticated System Admin and no tenant exists with id `tid-ghost`
- **WHEN** they POST to `/api/v1/admin/tenants/tid-ghost/users` with a valid user payload
- **THEN** the response SHALL have status 404
- **AND** the error message SHALL indicate the tenant was not found

#### Scenario: System Admin request exceeds the target tenant's user quota

- **GIVEN** a tenant with `max_users: 5` and 5 active users
- **WHEN** a System Admin POSTs to that tenant's `/api/v1/admin/tenants/{tenant_id}/users` with a valid new-user payload
- **THEN** the response SHALL have status 429
- **AND** the error message SHALL indicate the user quota is exceeded

#### Scenario: System Admin request duplicates an email already used in that tenant

- **GIVEN** a tenant "acme-corp" with an existing active user "user@acme.com"
- **WHEN** a System Admin POSTs to that tenant's `/api/v1/admin/tenants/{tenant_id}/users` with `{"email": "user@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 409
- **AND** the error message SHALL indicate the email is already taken

#### Scenario: Non-system-admin role cannot access the cross-tenant creation endpoint

- **GIVEN** an authenticated `tenant_admin` user for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/admin/tenants/{any_tenant_id}/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate system admin access is required

#### Scenario: Unauthenticated request is rejected

- **GIVEN** a request with no Bearer token
- **WHEN** they POST to `/api/v1/admin/tenants/{tenant_id}/users`
- **THEN** the response SHALL have status 401

#### Scenario: System Admin targets a tenant that is inactive

- **GIVEN** an authenticated System Admin and a tenant "acme-corp" with id `tid-123` whose `status` is `"inactive"`
- **WHEN** they POST to `/api/v1/admin/tenants/tid-123/users` with a valid user payload
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate the tenant is deactivated
- **AND** no user SHALL be created

#### Scenario: Target tenant is deactivated between form load and submission

- **GIVEN** an authenticated System Admin who loaded the create-user form for an active tenant "acme-corp" with id `tid-123`
- **WHEN** the tenant is deactivated before the System Admin submits, and the POST to `/api/v1/admin/tenants/tid-123/users` reaches the server after deactivation
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate the tenant is deactivated
- **AND** no user SHALL be created

### Requirement: Tenant Admin Onboarding Flow Remains Unchanged

The system SHALL continue to expose `POST /api/v1/users` for Tenant Admin self-service user creation, scoped to the caller's own tenant via JWT, exactly as specified in the `tenant-user-mgmt` capability. This endpoint's authorization (`tenant_admin` role only), tenant resolution (JWT-derived, no path or body tenant parameter), request/response shape, and status codes SHALL NOT change as a result of introducing the System Admin creation path.

#### Scenario: Tenant Admin still creates users only in their own tenant

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/users` with `{"email": "user@acme.com", "password": "secure-password", "role": "annotator"}`
- **THEN** the response SHALL have status 201
- **AND** the created user SHALL belong to the tenant from the Tenant Admin's JWT, not any other tenant

#### Scenario: Tenant Admin cannot target another tenant via this endpoint

- **GIVEN** an authenticated Tenant Admin whose JWT contains `tenant_id` for tenant "acme-corp"
- **WHEN** they POST to `/api/v1/users` with a payload that includes an unrelated tenant identifier
- **THEN** the tenant identifier in the payload SHALL be ignored
- **AND** the created user SHALL belong to the tenant resolved from the Tenant Admin's JWT

### Requirement: Shared User Creation Business Logic

The system SHALL use a single shared service implementation for user-creation business logic (password validation, per-tenant `max_users` quota enforcement, per-tenant email uniqueness, target-tenant active-status validation) for both the Tenant Admin (`POST /api/v1/users`) and System Admin (`POST /api/v1/admin/tenants/{tenant_id}/users`) creation paths, so that validation, quota, and tenant-status behavior cannot diverge between the two entry points.

#### Scenario: Quota enforcement is identical regardless of creating role

- **GIVEN** a tenant with `max_users: 1` and 1 active user
- **WHEN** a System Admin POSTs a new user to that tenant via `/api/v1/admin/tenants/{tenant_id}/users`
- **THEN** the response SHALL have status 429, identical to the quota-exceeded response a Tenant Admin would receive via `/api/v1/users` under the same quota condition

#### Scenario: Password validation is identical regardless of creating role

- **GIVEN** a password that fails the platform's password policy
- **WHEN** a System Admin POSTs a new user with that password via `/api/v1/admin/tenants/{tenant_id}/users`
- **THEN** the response SHALL be rejected with the same validation error a Tenant Admin would receive submitting the same password via `/api/v1/users`

#### Scenario: Tenant-active validation is identical regardless of creating role

- **GIVEN** an inactive tenant
- **WHEN** a System Admin POSTs a new user to that tenant via `/api/v1/admin/tenants/{tenant_id}/users`
- **THEN** the response SHALL have status 403, the same status and error code a Tenant Admin's request would receive if their own tenant became inactive

### Requirement: User Creation Is Audited

The system SHALL record an audit event whenever a user is created, via either `POST /api/v1/users` or `POST /api/v1/admin/tenants/{tenant_id}/users`. The audit event SHALL capture the actor's email, the actor's role (`tenant_admin` or `system_admin`), the action (`user.create`), the created user's email as the target, and the tenant the user was created in.

#### Scenario: Audit event recorded when System Admin creates a user

- **GIVEN** an authenticated System Admin with email "platform-admin@example.com"
- **WHEN** they POST a valid user payload to `/api/v1/admin/tenants/tid-123/users` and the user is created successfully
- **THEN** an audit event SHALL be recorded with `actor: "platform-admin@example.com"`, `role: "system_admin"`, `action: "user.create"`, `target` equal to the new user's email, and `tenant_id: "tid-123"`

#### Scenario: Audit event recorded when Tenant Admin creates a user

- **GIVEN** an authenticated Tenant Admin with email "admin@acme.com" whose JWT `tenant_id` is `tid-123`
- **WHEN** they POST a valid user payload to `/api/v1/users` and the user is created successfully
- **THEN** an audit event SHALL be recorded with `actor: "admin@acme.com"`, `role: "tenant_admin"`, `action: "user.create"`, `target` equal to the new user's email, and `tenant_id: "tid-123"`

### Requirement: Admin Console Cross-Tenant User Creation UI

The admin console's tenant detail page SHALL provide a "Create User" control, using the same label and form heading as the existing Tenant Admin onboarding page, that opens a user-creation form scoped to the currently-viewed tenant. The form SHALL collect `email`, `password`, and `role` (one of `tenant_admin`, `business_user`, `annotator`), SHALL display the target tenant's name and slug so the acting System Admin can confirm the destination tenant before submitting, and SHALL submit to `POST /api/v1/admin/tenants/{tenant_id}/users` for the tenant currently being viewed.

#### Scenario: System Admin creates a user from the tenant detail page

- **GIVEN** an authenticated System Admin viewing `/admin/tenants/tid-123` for tenant "Acme Corp" (slug `acme-corp`)
- **WHEN** they click "Create User", fill in a valid email, password, and role "business_user", and submit
- **THEN** the form SHALL display "Acme Corp (acme-corp)" as the target tenant before submission
- **AND** the request SHALL be sent to `/api/v1/admin/tenants/tid-123/users`
- **AND** on success the new user SHALL appear in the tenant's user list on the same page without a full page reload

#### Scenario: Create User form surfaces quota and duplicate-email errors

- **GIVEN** an authenticated System Admin viewing a tenant at its user quota limit
- **WHEN** they submit the Create User form with a valid new-user payload
- **THEN** the form SHALL display an error indicating the quota is exceeded
- **AND** the user SHALL NOT be added to the visible user list

#### Scenario: Create User form surfaces a deactivated-tenant error

- **GIVEN** an authenticated System Admin viewing a tenant whose status becomes `"inactive"` after the page was loaded
- **WHEN** they submit the Create User form with a valid new-user payload
- **THEN** the form SHALL display an error indicating the tenant is deactivated
- **AND** the user SHALL NOT be added to the visible user list
