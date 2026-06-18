# User Auth

## Purpose

JWT-based user authentication, token lifecycle management, and tenant context middleware. Tenant-scoped user management is handled by Tenant Admins directly via tenant-scoped endpoints.

---

## Requirements

### Requirement: User Authentication

The system SHALL authenticate users via email and password. On successful authentication, the system SHALL return a JWT access token (15-minute TTL) and SHALL set an `httpOnly` cookie named `refresh_token` containing the refresh token (7-day TTL). The access token SHALL contain custom claims: `sub` in format `{tenant_id}:{user_id}`, `tenant_id`, and `role`. The system SHALL reject requests with expired or malformed tokens with status 401. The system SHALL support token refresh via a `POST /api/v1/auth/refresh` endpoint that reads the refresh token exclusively from the `refresh_token` cookie (not from the request body). The `Set-Cookie` header SHALL use the attributes: `HttpOnly; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=604800`. The `Secure` attribute SHALL be included when `ENVIRONMENT == "production"`.

#### Scenario: User logs in with valid credentials and receives cookie

- **GIVEN** a user with email "admin@acme.com" and password "correct-password" exists in tenant "acme-corp"
- **WHEN** they POST to `/api/v1/auth/login` with `{"email": "admin@acme.com", "password": "correct-password"}`
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain `access_token` and `token_type: "bearer"`
- **AND** the response SHALL include a `Set-Cookie` header setting `refresh_token` with `HttpOnly; SameSite=Strict; Path=/api/v1/auth/refresh; Max-Age=604800`
- **AND** the decoded access_token SHALL contain `sub: "{tenant_id}:{user_id}"`, `tenant_id`, and `role`
- **AND** the response body SHALL NOT contain the `refresh_token` string value

#### Scenario: User logs in with incorrect password

- **GIVEN** a user with email "admin@acme.com" and password "correct-password"
- **WHEN** they POST to `/api/v1/auth/login` with `{"email": "admin@acme.com", "password": "wrong-password"}`
- **THEN** the response SHALL have status 401
- **AND** the error message SHALL indicate invalid credentials

#### Scenario: User accesses API with expired token

- **GIVEN** an expired JWT access token
- **WHEN** the user sends a request to any protected endpoint with `Authorization: Bearer <expired-token>`
- **THEN** the response SHALL have status 401
- **AND** the error message SHALL indicate the token is expired

#### Scenario: Token refresh via cookie succeeds and sets new cookie

- **GIVEN** a valid `refresh_token` httpOnly cookie is present in the request
- **WHEN** the user POSTs to `/api/v1/auth/refresh` (no body required)
- **THEN** the response SHALL have status 200
- **AND** the response body SHALL contain a new `access_token`
- **AND** the response SHALL include a new `Set-Cookie` header rotating the `refresh_token` cookie with the same attributes

#### Scenario: Token refresh with no cookie returns 401

- **GIVEN** no `refresh_token` cookie is present in the request
- **WHEN** the user POSTs to `/api/v1/auth/refresh`
- **THEN** the response SHALL have status 401
- **AND** no `Set-Cookie` header SHALL be present in the response

#### Scenario: Logout clears the refresh token cookie

- **GIVEN** a user with a valid `refresh_token` cookie and a valid access token
- **WHEN** they POST to `/api/v1/auth/logout` with `Authorization: Bearer <access_token>`
- **THEN** the response SHALL have status 200
- **AND** the response SHALL include a `Set-Cookie` header that clears the `refresh_token` cookie (`Max-Age=0` or `expires` in the past)

### Requirement: Tenant-Scoped User Management

The system SHALL allow a Tenant Admin to create, read, update, and deactivate users within their own tenant scope via `/api/v1/tenants/{slug}/users` endpoints. Users SHALL have one of these roles: `tenant_admin`, `business_user`, `annotator`. The system SHALL prevent cross-tenant user operations — a Tenant Admin from tenant A MUST NOT be able to create users in tenant B.

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

### Requirement: Tenant Context Middleware

The system SHALL extract tenant identity from URL path prefix `/api/v1/tenants/{tenant_slug}/` on every request. The middleware SHALL decode the JWT, validate `tenant_id` matches the resolved tenant from the URL, and inject `{tenant_id, user_id, role}` into the request scope. If the tenant slug does not resolve to an active tenant, the middleware SHALL return 404. If the JWT tenant_id does not match the URL tenant, the middleware SHALL return 403.

#### Scenario: Request with valid tenant and matching token

- **GIVEN** an active tenant "acme-corp" and a valid JWT with matching `tenant_id`
- **WHEN** the user GETs `/api/v1/tenants/acme-corp/entity-types` with `Authorization: Bearer <valid-token>`
- **THEN** the request SHALL be forwarded to the downstream handler
- **AND** the request context SHALL contain `tenant_id`, `user_id`, and `role`

#### Scenario: Request with non-existent tenant slug

- **GIVEN** no tenant exists with slug "ghost-tenant"
- **WHEN** the user GETs `/api/v1/tenants/ghost-tenant/entity-types`
- **THEN** the response SHALL have status 404
- **AND** the error message SHALL indicate the tenant was not found

#### Scenario: Request with tenant mismatch between URL and token

- **GIVEN** a valid JWT with `tenant_id` for "acme-corp"
- **WHEN** the user GETs `/api/v1/tenants/other-corp/entity-types`
- **THEN** the response SHALL have status 403
- **AND** the error message SHALL indicate a tenant mismatch
