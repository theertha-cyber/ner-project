## MODIFIED Requirements

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
