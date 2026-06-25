# analytics-query-api

## Purpose

Provides a structured, filterable query API for tenant-scoped entity analytics, with parameter validation, pagination, tenant isolation, and query timeout enforcement.

## Requirements

### Requirement: Structured Query API

The analytics service SHALL provide a `POST /api/v1/tenants/{tenant_id}/analytics/query` endpoint that accepts a JSON filter body and returns paginated entity results scoped to the requesting tenant's schema.

#### Scenario: Successful query with entity type and date range filter

- **GIVEN** a tenant with extracted entities of types `PERSON` and `ORG` in the date range `2026-01-01` to `2026-06-01`
- **WHEN** a POST request is sent to `/api/v1/tenants/{tenant_id}/analytics/query` with body `{"entity_types": ["PERSON", "ORG"], "date_from": "2026-01-01", "date_to": "2026-06-01"}`
- **THEN** the response SHALL contain a `results` array with only entities of type `PERSON` or `ORG` whose extraction date falls within the range
- **AND** the response SHALL include a `pagination` object with `next_cursor` and `has_more` fields

#### Scenario: Query with confidence filter

- **GIVEN** a tenant with extracted entities at various confidence scores
- **WHEN** a POST request is sent with body `{"confidence": {"min": 0.8, "max": 1.0}}`
- **THEN** only entities with confidence score >= 0.8 AND <= 1.0 SHALL be returned

#### Scenario: Query with document source and annotator filter

- **GIVEN** entities extracted from documents with source "invoice_123.pdf" by annotator "alice"
- **WHEN** a POST request is sent with body `{"document_sources": ["invoice_123.pdf"], "annotators": ["alice"]}`
- **THEN** only entities matching both filters SHALL be returned

#### Scenario: Query returns empty results for non-matching filters

- **GIVEN** no entities match the filter criteria
- **WHEN** a POST request is sent with any filter
- **THEN** the response SHALL contain an empty `results` array

#### Scenario: Query timeouts gracefully

- **GIVEN** a filter that would trigger a long-running query
- **WHEN** the query exceeds the 5-second timeout
- **THEN** the endpoint SHALL return HTTP 504 with an error indicating the query timed out

### Requirement: Query Parameter Validation

The analytics service SHALL validate all query filter parameters before execution and reject invalid values with HTTP 422.

#### Scenario: Invalid entity type returns 422

- **GIVEN** an entity type that does not exist in the tenant's entity type configuration
- **WHEN** a POST request includes that entity type in `entity_types`
- **THEN** the endpoint SHALL return HTTP 422 with a validation error detail

#### Scenario: Invalid date format returns 422

- **GIVEN** a `date_from` value in an invalid format
- **WHEN** a POST request is sent
- **THEN** the endpoint SHALL return HTTP 422 with a validation error

### Requirement: Tenant-scoped Query Execution

Every analytics query SHALL execute within the requesting tenant's isolated database schema and SHALL NOT access data from other tenants.

#### Scenario: Query filters by tenant schema

- **GIVEN** two tenants with different extracted entities
- **WHEN** the same filter body is sent for each tenant
- **THEN** each response SHALL contain only that tenant's entities
- **AND** no cross-tenant data SHALL be visible in either response

#### Scenario: Unauthenticated request returns 401

- **GIVEN** no valid JWT token
- **WHEN** a POST request is sent to the analytics query endpoint
- **THEN** HTTP 401 SHALL be returned
