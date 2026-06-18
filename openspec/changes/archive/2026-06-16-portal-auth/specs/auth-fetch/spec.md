## ADDED Requirements

### Requirement: Auth Fetch Interceptor

The system SHALL provide an `authFetch(url: string, init?: RequestInit): Promise<Response>` function that wraps all portal API calls. The function SHALL prepend the correct service base URL based on the URL path prefix before forwarding the request. The function SHALL inject `Authorization: Bearer <accessToken>` on every outgoing request if an access token is available. The function SHALL accept absolute URLs (beginning with `http`) unchanged (no base URL prepended).

Service URL routing rules (checked in order):
- Paths starting with `/api/v1/admin` or `/api/v1/auth` or `/api/v1/tenants` → `NEXT_PUBLIC_GATEWAY_URL`
- Paths starting with `/api/v1/document` → `NEXT_PUBLIC_DOCUMENT_URL`
- Paths starting with `/api/v1/annotation` → `NEXT_PUBLIC_ANNOTATION_URL`
- Paths starting with `/api/v1/training` or `/api/v1/models` → `NEXT_PUBLIC_TRAINING_URL`
- Paths starting with `/api/v1/extraction` → `NEXT_PUBLIC_EXTRACTION_URL`
- All other paths → `NEXT_PUBLIC_GATEWAY_URL` (fallback)

#### Scenario: authFetch prepends gateway URL for admin routes

- **GIVEN** `NEXT_PUBLIC_GATEWAY_URL` is set to `http://localhost:8000`
- **WHEN** `authFetch("/api/v1/admin/tenants")` is called
- **THEN** the underlying `fetch` SHALL be called with `http://localhost:8000/api/v1/admin/tenants`

#### Scenario: authFetch prepends document service URL for document routes

- **GIVEN** `NEXT_PUBLIC_DOCUMENT_URL` is set to `http://localhost:8001`
- **WHEN** `authFetch("/api/v1/documents/123")` is called
- **THEN** the underlying `fetch` SHALL be called with `http://localhost:8001/api/v1/documents/123`

#### Scenario: authFetch passes absolute URLs through unchanged

- **GIVEN** a caller passes an absolute URL `https://external.example.com/api/data`
- **WHEN** `authFetch("https://external.example.com/api/data")` is called
- **THEN** the underlying `fetch` SHALL be called with `https://external.example.com/api/data` unchanged

#### Scenario: authFetch injects Bearer token on authenticated requests

- **GIVEN** a user is authenticated with access token `"tok-abc123"`
- **WHEN** `authFetch("/api/v1/documents")` is called
- **THEN** the outgoing request SHALL include header `Authorization: Bearer tok-abc123`

### Requirement: Auth Fetch 401 Silent Refresh

When the server responds with HTTP 401, `authFetch` SHALL attempt exactly one silent refresh before failing. The refresh MUST use a module-level pending-promise singleton so that concurrent calls that all receive 401 result in exactly one `POST /api/v1/auth/refresh` request. After a successful refresh, `authFetch` SHALL retry the original request with the new token. If the refresh also fails with 401, `authFetch` SHALL redirect the user to `/login` and throw an error. The pending-promise singleton SHALL be cleared after the refresh resolves or rejects.

#### Scenario: 401 triggers one silent refresh and retries

- **GIVEN** a user is authenticated with an expired access token
- **AND** the server returns 401 on the first request
- **AND** `POST /api/v1/auth/refresh` succeeds and returns a new `access_token`
- **WHEN** `authFetch("/api/v1/documents")` is called
- **THEN** exactly one `POST /api/v1/auth/refresh` SHALL be issued
- **AND** the original request SHALL be retried with the new `Authorization: Bearer <new-token>` header
- **AND** the retried response SHALL be returned to the caller

#### Scenario: Concurrent 401s produce only one refresh request

- **GIVEN** a user has an expired access token
- **AND** three `authFetch` calls are made concurrently, all receiving 401
- **WHEN** all three 401 responses are detected simultaneously
- **THEN** exactly one `POST /api/v1/auth/refresh` SHALL be issued (not three)
- **AND** all three original requests SHALL be retried after the single refresh resolves

#### Scenario: Refresh failure redirects to login

- **GIVEN** a user has an expired access token and an expired refresh cookie
- **WHEN** `authFetch` calls `POST /api/v1/auth/refresh` and receives 401
- **THEN** the user SHALL be redirected to `/login`
- **AND** `authFetch` SHALL throw an error (no response returned to the original caller)

#### Scenario: Second 401 after refresh does not trigger another refresh

- **GIVEN** a silent refresh has just succeeded and returned a new token
- **WHEN** the retried request also returns 401 (e.g. authorisation failure, not token expiry)
- **THEN** `authFetch` SHALL NOT trigger another refresh
- **AND** the 401 response SHALL be returned to the caller as-is
