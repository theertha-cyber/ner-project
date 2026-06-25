## Context

Tenants across Wave 5 (Extraction Engine) will have structured entity data accumulating in their isolated PostgreSQL schemas. Currently there is no way to query, visualize, or export this data beyond raw database access. The analytics service fills this gap by providing ad-hoc query, dashboard widgets, and export capabilities — all scoped to the requesting tenant's schema per ADR-001.

The portal already has a dashboard (portal-dashboard spec) and chat UI (chat-ui spec); the analytics page will slot into the existing app shell and share the same auth-context and tenant-context middleware.

## Goals / Non-Goals

**Goals:**
- Provide a structured query API that maps filter JSON to parameterized SQL within the tenant schema
- Pre-compute aggregation views for dashboard widgets (entity coverage, confidence distribution, extraction volume over time, per-document counts)
- Support CSV and JSON export of filtered entity results
- Provide a frontend dashboard page in the portal with chart widgets
- Ensure all queries are read-only, tenant-scoped, and time-bounded

**Non-Goals:**
- Cross-tenant aggregation or System Admin analytics (future)
- Scheduled/delivered reports (email PDF/CSV) — deferred from MVP
- Real-time streaming analytics — all queries are request-response over pre-aggregated or indexed data
- Ad-hoc chart builder (drag-and-drop chart configuration) — fixed widget set only
- Natural-language query interface — that is SM-06's domain

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Separate PostgreSQL schemas per tenant with `search_path` enforcement | All analytics queries MUST execute within the requesting tenant's schema; no cross-schema or cross-tenant data access |
| ADR-004 | OpenSpec SDD with mandatory artifact gates (proposal → design → spec → tasks → evidence → archive) | This change follows the full pipeline; all artifacts must be created and verified before implementation |
| ADR-008 | Base model serves as default inference model when no tenant model is promoted | Not directly constraining; analytics queries extracted entities regardless of which model produced them. Entity storage includes model_version for traceability but analytics does not require a promoted model |

## Decisions

### Decision 1: Dedicated analytics service vs. in-gateway endpoint

**Choice:** New `analytics-service/` as a lightweight FastAPI service

**Rationale:** The analytics query translator and materialized view management have different scaling characteristics from the API gateway. Separation avoids coupling gateway availability to analytics query latency. The service shares the `tenant_context` module from `src/shared/`.

**Alternatives considered:**
- In-gateway endpoints — simpler deployment but couples request throughput and lifecycle management
- Extension of the extraction service — conceptually adjacent but the extraction service focuses on model inference, not query; mixing concerns creates deployment coupling

### Decision 2: Materialized views vs. live aggregation queries

**Choice:** Materialized views (`mv_entity_coverage`, `mv_confidence_distribution`, `mv_extraction_volume`, `mv_document_entity_counts`) refreshed on `ExtractionCompleted` event consumption

**Rationale:** Dashboard widgets display aggregate metrics that change only when new extractions complete. Live aggregation over large entity tables would introduce unpredictable query latency (especially as entity counts grow). Materialized views provide sub-100ms reads.

**Alternatives considered:**
- Live `GROUP BY` queries — no storage overhead but query time scales with data volume
- Periodic batch refresh (hourly cron) — simpler but dashboard shows stale data between extraction events
- Redis counters — fast but loses the ability to filter by custom ranges without additional data structures

### Decision 3: Query filter format

**Choice:** Structured JSON filter body (`POST /api/v1/tenants/{tid}/analytics/query`) with explicit filter fields

**Rationale:** A structured filter is type-safe, easy to validate, and maps directly to SQL `WHERE` clauses. Avoids the complexity and risk of a natural-language or DSL-based query interface.

**Alternatives considered:**
- SQL fragments in request body — flexible but dangerous; would require extensive SQL injection prevention with little benefit
- Natural language → SQL — that is SM-06's lane; out of scope for this service

### Decision 4: Frontend charting library

**Choice:** Recharts (React-native charting library already compatible with the portal's React/Next.js stack)

**Rationale:** The portal uses React/Next.js (App Router). Recharts is declarative, tree-shakeable, and works well with server-side rendering. No new external dependency beyond what the project already tolerates.

**Alternatives considered:**
- Chart.js with react-chartjs-2 — more feature-rich but heavier bundle; adds a wrapper dependency
- D3.js — most flexible but significantly steeper learning curve and more verbose for simple chart widgets

## Risks / Trade-offs

- [Materialized view staleness between ExtractionCompleted event and refresh completion] → The event-driven refresh is near-real-time (< 1s lag). Acceptable for dashboard use. The refresh API also exposes an on-demand refresh endpoint for manual sync.
- [Aggregation performance at scale >1M entities per tenant] → Materialized views stay fast because they aggregate at write time. If entity volume grows beyond millions, add partitioning by month on the entity table and partition-wise aggregation refresh.
- [Query API could be abused for large unindexed scans] → Enforce a query timeout (5s default) and maximum result set size (5000 rows default, configurable). The query builder always injects `LIMIT` and `tenant_id` filter.
- [Frontend bundle size increase from chart library] → Lazy-load the analytics page and chart components via Next.js dynamic imports. Recharts tree-shakes unused chart types.

## Migration Plan

1. Create `src/analytics-service/` package with FastAPI app entry point
2. Add analytics routes to the API gateway routing configuration
3. Run migration script to create materialized views in all existing tenant schemas
4. Add `ExtractionCompleted` event consumer to the analytics service to trigger materialized view refresh
5. Deploy service to staging; verify against existing extracted entities
6. Add analytics page route to portal with lazy-loaded chart components
7. Test with sample data in staging; promote to production

**Rollback:** Disable the analytics routes at the gateway level. Materialized views are read-heavy and do not affect extraction pipeline. The portal analytics page will 404 if the service is removed.

## Open Questions

- Should the analytics service share the same database connection pool as the extraction service, or have its own pool? (Trade-off: sharing reduces connections, separate avoids resource contention during heavy queries.)
Answer: share
- Should materialized views be refreshed synchronously (inline in the ExtractionCompleted handler) or asynchronously via a background task? (Trade-off: sync ensures freshness on next query; async avoids blocking the event handler.)
Answer: async
