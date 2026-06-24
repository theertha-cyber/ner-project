## ADDED Requirements

### Requirement: CSV Export Endpoint

The analytics service SHALL provide a `POST /api/v1/tenants/{tenant_id}/analytics/export` endpoint that accepts the same filter body as the query API and returns a downloadable CSV file.

#### Scenario: Export returns valid CSV

- **GIVEN** a tenant with extracted entities matching filter criteria
- **WHEN** a POST request is sent to `/api/v1/tenants/{tenant_id}/analytics/export` with a valid filter body and `format: "csv"`
- **THEN** the response SHALL have `Content-Type: text/csv`
- **AND** the response SHALL include a `Content-Disposition` header with a filename
- **AND** the body SHALL be well-formed CSV with a header row and matching data rows

#### Scenario: Empty export returns header-only CSV

- **GIVEN** no entities match the filter criteria
- **WHEN** an export request is sent
- **THEN** the response SHALL contain only the CSV header row with no data rows

### Requirement: JSON Export Endpoint

The analytics service SHALL provide a `POST /api/v1/tenants/{tenant_id}/analytics/export` endpoint that returns a downloadable JSON file when `format: "json"` is specified.

#### Scenario: Export returns valid JSON

- **GIVEN** a tenant with extracted entities matching filter criteria
- **WHEN** a POST request is sent with `format: "json"`
- **THEN** the response SHALL have `Content-Type: application/json`
- **AND** the body SHALL be a valid JSON array of entity objects

### Requirement: Export Filter Validation

The export endpoint SHALL validate filter parameters identically to the query API and reject invalid values with HTTP 422.

#### Scenario: Invalid export filter returns 422

- **GIVEN** an invalid entity type in the filter body
- **WHEN** an export request is sent
- **THEN** HTTP 422 SHALL be returned with a validation error

### Requirement: Export Result Size Limit

The export endpoint SHALL enforce a maximum result set of 10,000 rows per export request.

#### Scenario: Export exceeds size limit

- **GIVEN** more than 10,000 entities match the filter criteria
- **WHEN** an export request is sent
- **THEN** the response SHALL contain only the first 10,000 rows
- **AND** the response SHALL include a header `X-Result-Truncated: true`
