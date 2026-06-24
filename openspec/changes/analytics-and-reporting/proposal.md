## Why

Tenants need visibility into their extracted entity data — coverage, confidence distributions, extraction volumes, and per-document breakdowns. Without analytics, extracted data is opaque and the platform's core value (automated entity extraction at scale) cannot be measured or explored. This change adds a structured analytics and reporting layer so tenants can query, visualize, and export their extraction results.

## What Changes

- New **Analytics Service** (`analytics-service/`) with query, dashboard, and export endpoints
- Ad-hoc query API allowing tenants to filter extracted entities by date range, entity type, confidence score, document source, and annotator
- Pre-built dashboard widgets: entity coverage %, confidence distribution histogram, extraction volume over time, per-document entity counts
- Report export in CSV and JSON formats
- Materialized views in each tenant schema for pre-computed aggregations (refreshed on extraction completion or on-demand)
- New frontend dashboard page in the portal under the analytics section
- No cross-tenant aggregation — all queries scoped to the requesting tenant's schema

## Capabilities

### New Capabilities

- `analytics-query-api`: Ad-hoc structured query API that translates filter JSON into parameterized SQL scoped to the tenant schema
- `analytics-dashboard`: Pre-built aggregation widgets with materialized view support
- `analytics-export`: CSV and JSON export of filtered entity data
- `analytics-ui`: Portal dashboard page with chart widgets and export controls

### Modified Capabilities

*(None — no existing spec requirements are changing)*

## Impact

- **New service**: `src/analytics-service/` — Python/FastAPI service for analytics query processing
- **Database**: New materialized views in each tenant schema (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`); refresh trigger via extraction-complete event
- **Portal**: New `/tenants/{tid}/analytics` route with chart components (Recharts or Chart.js)
- **Events**: Consumes `ExtractionCompleted` to trigger materialized view refresh
- **No changes** to existing extraction or entity storage schemas

## Open Questions

- Should scheduled report delivery (email PDF/CSV) be included in MVP or deferred?
- Are there performance concerns with on-demand materialized view refresh vs. periodic refresh (e.g., hourly cron)?
- Should dashboard widgets support custom time ranges or fixed windows (last 7d, 30d, all time)?
