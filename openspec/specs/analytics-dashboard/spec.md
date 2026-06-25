# analytics-dashboard

## Purpose

Provides pre-computed dashboard widget data for tenant analytics, served from materialized views and refreshed on extraction events or on demand.

## Requirements

### Requirement: Dashboard Aggregation API

The analytics service SHALL provide a `GET /api/v1/tenants/{tenant_id}/analytics/dashboard` endpoint that returns pre-computed dashboard widget data from materialized views.

#### Scenario: Dashboard returns all widget data

- **GIVEN** a tenant with extracted entities and refreshed materialized views
- **WHEN** a GET request is sent to `/api/v1/tenants/{tenant_id}/analytics/dashboard`
- **THEN** the response SHALL contain `entity_coverage`, `confidence_distribution`, `extraction_volume`, and `document_entity_counts` objects

### Requirement: Entity Coverage Widget

The dashboard SHALL include an entity coverage widget showing the percentage of documents that have at least one extracted entity per entity type.

#### Scenario: Entity coverage returns correct percentages

- **GIVEN** 100 processed documents with 80 containing PERSON entities and 40 containing ORG entities
- **WHEN** the dashboard endpoint is called
- **THEN** the `entity_coverage` object SHALL contain `{"PERSON": 80.0, "ORG": 40.0}`

### Requirement: Confidence Distribution Widget

The dashboard SHALL include a confidence distribution widget showing the count of extracted entities per confidence bucket (0.0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0).

#### Scenario: Confidence distribution returns correct bucket counts

- **GIVEN** extracted entities with varying confidence scores
- **WHEN** the dashboard endpoint is called
- **THEN** the `confidence_distribution` object SHALL contain arrays with labels and counts for each bucket

### Requirement: Extraction Volume Over Time Widget

The dashboard SHALL include an extraction volume widget showing entity counts aggregated by day (or configurable interval) over a configurable lookback period (default 30 days).

#### Scenario: Extraction volume returns daily counts

- **GIVEN** 50 entities extracted on 2026-05-01 and 30 on 2026-05-02
- **WHEN** the dashboard endpoint is called
- **THEN** the `extraction_volume` array SHALL include entries for those dates with the correct counts

### Requirement: Per-Document Entity Counts Widget

The dashboard SHALL include a widget showing the average entity count per document, grouped by entity type.

#### Scenario: Per-document entity counts returned

- **GIVEN** 10 documents with average 3.5 PERSON entities and 1.2 ORG entities per document
- **WHEN** the dashboard endpoint is called
- **THEN** the `document_entity_counts` object SHALL contain `{"PERSON": 3.5, "ORG": 1.2}`

### Requirement: Materialized View Refresh on Extraction Event

The analytics service SHALL consume `ExtractionCompleted` events and trigger a refresh of all materialized views in the affected tenant's schema.

#### Scenario: Materialized view refreshes after extraction

- **GIVEN** a tenant with existing materialized views showing `entity_coverage.PERSON = 80.0`
- **WHEN** an `ExtractionCompleted` event for a new document that adds PERSON entities is consumed
- **THEN** the materialized views SHALL reflect the updated count within a reasonable time (< 5s)

### Requirement: On-Demand Materialized View Refresh

The analytics service SHALL provide a `POST /api/v1/tenants/{tenant_id}/analytics/refresh` endpoint to trigger on-demand materialized view refresh.

#### Scenario: On-demand refresh succeeds

- **GIVEN** a tenant with stale materialized views
- **WHEN** a POST request is sent to `/api/v1/tenants/{tenant_id}/analytics/refresh`
- **THEN** the endpoint SHALL return HTTP 202
- **AND** the materialized views SHALL be refreshed within a reasonable time

#### Scenario: Unauthenticated refresh request returns 401

- **GIVEN** no valid JWT token
- **WHEN** a POST request is sent to the refresh endpoint
- **THEN** HTTP 401 SHALL be returned
