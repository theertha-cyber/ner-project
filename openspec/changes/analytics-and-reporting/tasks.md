## 1. Setup & Shared Infrastructure

- [ ] 1.1 Create `src/analytics-service/` package with FastAPI app entry point, shared `tenant_context` integration, and health check endpoint
- [ ] 1.2 Create database migration that adds materialized views (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`) to the `tenant_template` schema
- [ ] 1.3 Create database migration to apply materialized views to all existing tenant schemas
- [ ] 1.4 Add analytics routes to API gateway routing configuration (`/api/v1/tenants/{tid}/analytics/*`)
- [ ] 1.5 Add `analytics-service` to Docker Compose and CI workflow

## 2. Analytics Query API

- [ ] 2.1 Implement `POST /api/v1/tenants/{tid}/analytics/query` endpoint with structured filter body parser (entity_types, confidence, date_from/to, document_sources, annotators)
- [ ] 2.2 Implement filter-to-SQL translator that builds parameterized WHERE clauses scoped to the tenant schema
- [ ] 2.3 Implement validation logic for all filter parameters (entity type existence check, date format validation)
- [ ] 2.4 Implement query timeout enforcement (5s default) and return HTTP 504 on timeout
- [ ] 2.5 Implement pagination with cursor-based next_cursor and has_more fields
- [ ] 2.6 Write unit tests for filter validation, SQL generation, pagination, and timeout scenarios
- [ ] 2.7 Write integration tests for query endpoint covering entity type filter, confidence filter, date range, document source, annotator, empty results, and cross-tenant isolation

## 3. Analytics Dashboard & Materialized Views

- [ ] 3.1 Implement `GET /api/v1/tenants/{tid}/analytics/dashboard` endpoint returning all four widget data objects
- [ ] 3.2 Implement `GET /api/v1/tenants/{tid}/analytics/dashboard` per-widget endpoint returning entity coverage percentage
- [ ] 3.3 Implement `GET /api/v1/tenants/{tid}/analytics/dashboard` per-widget endpoint returning confidence distribution buckets
- [ ] 3.4 Implement `GET /api/v1/tenants/{tid}/analytics/dashboard` per-widget endpoint returning extraction volume over time (default 30d lookback)
- [ ] 3.5 Implement `GET /api/v1/tenants/{tid}/analytics/dashboard` per-widget endpoint returning per-document entity counts
- [ ] 3.6 Implement `ExtractionCompleted` event consumer that triggers async materialized view refresh for the affected tenant
- [ ] 3.7 Implement `POST /api/v1/tenants/{tid}/analytics/refresh` endpoint for on-demand materialized view refresh (returns HTTP 202)
- [ ] 3.8 Write unit tests for materialized view refresh logic, event consumption, and on-demand refresh
- [ ] 3.9 Write integration tests for dashboard endpoint returning correct widget data, empty data handling, and authentication

## 4. Analytics Export

- [ ] 4.1 Implement `POST /api/v1/tenants/{tid}/analytics/export` endpoint accepting filter body + format field (csv/json)
- [ ] 4.2 Implement CSV response serialization with proper Content-Type, Content-Disposition header, and escaping
- [ ] 4.3 Implement JSON response serialization with Content-Type: application/json
- [ ] 4.4 Implement export result size limit (10,000 rows) with `X-Result-Truncated: true` header when exceeded
- [ ] 4.5 Share filter validation logic with query API endpoint for consistent error behavior
- [ ] 4.6 Write unit tests for CSV/JSON serialization, empty export, size limit truncation
- [ ] 4.7 Write integration tests for export endpoint covering CSV, JSON, invalid filter, truncation, and authentication

## 5. Analytics UI (Portal)

- [ ] 5.1 Create `/tenants/{tid}/analytics` page route in portal with lazy-loaded Next.js dynamic import
- [ ] 5.2 Implement entity coverage widget (percentage bar chart via Recharts)
- [ ] 5.3 Implement confidence distribution widget (histogram via Recharts)
- [ ] 5.4 Implement extraction volume over time widget (line chart via Recharts)
- [ ] 5.5 Implement per-document entity counts widget (bar chart via Recharts)
- [ ] 5.6 Implement filter controls: entity type dropdown, date range picker, confidence slider
- [ ] 5.7 Implement results table with pagination controls for ad-hoc query results
- [ ] 5.8 Implement export buttons (CSV/JSON) that trigger download via export API
- [ ] 5.9 Implement loading skeleton/spinner state during data fetch
- [ ] 5.10 Implement empty state handling ("No extraction data yet", "No matching entities found")
- [ ] 5.11 Implement error banner with retry button for API errors
- [ ] 5.12 Write component tests for all widgets, filter controls, empty states, and error states
- [ ] 5.13 Write E2E tests for analytics page flow: load widget data, apply filters, paginate results, export CSV/JSON

## 6. Verification & Evidence

- [ ] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log
- [ ] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent)
- [ ] 6.6 Run `openspec validate analytics-and-reporting --type change --strict` and confirm it exits clean before archive
