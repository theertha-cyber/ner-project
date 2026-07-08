## ADDED Requirements

### Requirement: Create Materialized Views for New Tenants

When a new tenant schema is created (via seed script or Alembic migration), the system SHALL also create the four analytics materialized views in that schema: `mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, and `mv_document_entity_counts`. The views SHALL use the same SQL definitions as migration `011`.

#### Scenario: Seed script creates MVs for demo tenant

- **GIVEN** the seed script is run and no `tenant_demo_tenant` schema exists
- **WHEN** the seed script finishes creating tenant tables
- **THEN** the materialized views `mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, and `mv_document_entity_counts` SHALL exist in the `tenant_demo_tenant` schema
- **AND** each view SHALL be populated with data from existing `extracted_entities`, `documents`, and `extraction_runs` tables

#### Scenario: Seed script is idempotent for MVs

- **GIVEN** the seed script is run and `tenant_demo_tenant` schema already exists with all four MVs
- **WHEN** the seed script runs again
- **THEN** the script SHALL NOT error — MV creation SHALL use `IF NOT EXISTS`

### Requirement: Backfill Missing Materialized Views for Existing Tenants

The system SHALL provide an Alembic migration that creates any of the four analytics materialized views in every existing `tenant_*` schema that lacks them. The migration SHALL be idempotent.

#### Scenario: Migration backfills a tenant missing MVs

- **GIVEN** a `tenant_*` schema exists with all regular tables but none of the four materialized views
- **WHEN** Alembic migration `015` is applied
- **THEN** all four materialized views SHALL be created in that schema
- **AND** unique indexes SHALL be created on each view

#### Scenario: Migration skips tenants that already have MVs

- **GIVEN** a `tenant_*` schema already has all four materialized views
- **WHEN** Alembic migration `015` is applied
- **THEN** the migration SHALL NOT error or recreate the views
- **AND** existing view data SHALL be preserved

### Requirement: Refresh Materialized Views After Creation

Immediately after creating the materialized views (in both migration and seed script), the system SHALL refresh them using `REFRESH MATERIALIZED VIEW CONCURRENTLY` so that existing extraction data is visible in the analytics dashboard without waiting for the next extraction event.

#### Scenario: MVs reflect existing data after creation

- **GIVEN** a tenant schema with 75 extracted entities across 5 documents and 4 extraction runs
- **WHEN** the materialized views are created and refreshed
- **THEN** `mv_entity_coverage` SHALL contain rows with non-zero `coverage_pct` values
- **AND** `mv_confidence_distribution` SHALL contain rows with entity counts per confidence bucket
- **AND** `mv_extraction_volume` SHALL contain rows with daily entity counts
- **AND** `mv_document_entity_counts` SHALL contain rows with average entity counts per document

#### Scenario: Analytics dashboard shows populated widgets after backfill

- **GIVEN** a tenant with extracted entities but no materialized views
- **WHEN** migration `015` completes and the dashboard page is loaded
- **THEN** the `GET /api/v1/analytics/dashboard` endpoint SHALL return the four widget data objects with non-empty arrays
