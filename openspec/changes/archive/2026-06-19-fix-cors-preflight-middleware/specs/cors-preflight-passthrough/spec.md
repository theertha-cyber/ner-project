## ADDED Requirements

### Requirement: OPTIONS requests bypass authentication middleware

The `TenantContextMiddleware` in both the document service and the annotation service SHALL allow HTTP OPTIONS requests to pass through to the next middleware handler without performing token validation or tenant context checks.

#### Scenario: Browser preflight to document service succeeds

- **GIVEN** the annotation workspace is open and the browser has no cached CORS preflight for the document service (port 8001)
- **WHEN** the annotator clicks a task, triggering `GET /api/v1/documents/{id}/text` with an `Authorization` header
- **THEN** the browser's OPTIONS preflight to port 8001 receives a 2xx response with `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers` headers
- **AND** the subsequent `GET` request is sent and receives document text data

#### Scenario: Browser preflight to annotation service succeeds without cache

- **GIVEN** the annotation service (port 8005) has no cached CORS preflight in the browser
- **WHEN** the browser sends an OPTIONS preflight to `/api/v1/documents/{id}/spans`
- **THEN** the preflight receives a 2xx response with the required CORS headers
- **AND** the subsequent span request is sent and processed normally

#### Scenario: Non-OPTIONS requests still require authentication

- **GIVEN** an HTTP request with method GET, POST, PATCH, or DELETE arrives at the document or annotation service
- **WHEN** the request has no `Authorization` header
- **THEN** `TenantContextMiddleware` returns 401 with `AUTH_ERROR` code
- **AND** the request does not reach the route handler

#### Scenario: OPTIONS request receives X-Request-ID response header

- **GIVEN** an OPTIONS preflight arrives at either service
- **WHEN** `TenantContextMiddleware` passes it through
- **THEN** the response includes an `X-Request-ID` header for traceability
