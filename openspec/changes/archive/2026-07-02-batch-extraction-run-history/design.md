## Context

The extraction service already implements `POST /api/v1/extract-batch` and `GET /api/v1/extract-batch/{run_id}` in `src/extraction_service/api/v1/extraction.py`, both querying the tenant-scoped `extraction_runs` table via raw SQL with an f-string schema prefix (`_schema(tenant_id)` → `tenant_<uuid>`). The gateway proxies these paths without a `{tid}` segment, per the existing "Gateway Extraction Proxy" requirement. The portal's `use-batch-runs.ts` hook already calls `GET /api/v1/extract-batch` expecting `{ runs: [...] }`; that route doesn't exist, so the call 405s and run history is lost on every reload. This is a small, additive change: one new read-only endpoint plus one new gateway proxy route.

## Goals / Non-Goals

**Goals:**
- Add `GET /api/v1/extract-batch` returning the tenant's extraction runs, most recent first, in the shape the frontend already expects.
- Add the matching gateway proxy route.
- Keep the response shape compatible with `BatchRunStatus` plus `run_id`, so the existing `BatchRun` frontend type needs no change.

**Non-Goals:**
- No new database tables or migrations — this reads the existing `extraction_runs` table as-is.
- No change to run creation, worker processing, or the single-run status endpoint.
- No cursor-based pagination — a simple `LIMIT` is sufficient given expected run volume per tenant.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant's data lives in its own `tenant_<uuid>` schema; queries must be scoped to that schema. | The new list query MUST scope to `_schema(tenant_id)` exactly as the existing batch endpoints do — no cross-tenant reads. |
| ADR-008: Base Model as Default | Batch extraction may run with `model_version: "0"` when no model is promoted. | The list response's `model_version` field must pass through whatever value is stored on the run row, including "0", without special-casing. |

## Decisions

### Decision 1: Follow the existing raw-SQL-with-schema-prefix pattern, not a new query abstraction

**Choice:** Implement the list query the same way `get_extraction_run` and the existing endpoints do — a raw parameterized SQL `SELECT` against `{schema}.extraction_runs`, added as a new function in `src/extraction_service/services/entity_store.py`.

**Rationale:** The extraction service has no query-builder or repository abstraction; every existing read (`get_extraction_run`, batch trigger's document lookup) uses this same pattern. Introducing a new abstraction for one query would be inconsistent with the surrounding code and add a layer nobody else uses.

**Alternatives considered:**
- Add an ORM model for `extraction_runs` — ruled out; no ORM layer exists for this table anywhere in the service, and adding one for a single query is disproportionate.

### Decision 2: Cap the list with `LIMIT 50`, no pagination params

**Choice:** The endpoint returns up to the 50 most recent runs for the tenant, ordered by `started_at DESC`, with no `page`/`cursor` query parameters.

**Rationale:** Batch runs are triggered manually per tenant and are not expected to accumulate at high volume (unlike `extracted_entities`, which already has pagination). A fixed cap avoids unbounded response size without the complexity of a pagination contract the frontend doesn't ask for.

**Alternatives considered:**
- Full pagination (`page`, `per_page`, `total`) matching the `/api/v1/entities` pattern — ruled out for now as over-engineering relative to actual run volume; noted as an open question in case usage patterns change.

### Decision 3: Response shape mirrors `BatchRunStatus` plus `run_id`

**Choice:** New Pydantic model `BatchRunListItem(BatchRunStatus)` (or equivalent) adding `run_id: str`, wrapped in `BatchRunListResponse { runs: list[BatchRunListItem] }`.

**Rationale:** The frontend's `BatchRun` type already expects exactly these fields (it's populated today from the trigger response plus polled single-run status merges). Reusing `BatchRunStatus` avoids field drift between the single-run and list endpoints.

**Alternatives considered:**
- Define a wholly separate list-item schema — ruled out; would risk the two endpoints silently diverging in field names over time.

## Risks / Trade-offs

- [A tenant with very old stuck "queued" runs (e.g., the ones with the pre-existing `version_number` bug) will always appear at the top of history once this ships, since they never reach a terminal state] → Acceptable; this is a true reflection of past state and not something this change needs to clean up. Not in scope.
- [Unbounded `LIMIT 50` with no pagination could hide older runs from tenants with heavy batch usage] → Acceptable trade-off for now per Decision 2; revisit if usage data shows otherwise.

## Migration Plan

No data migration needed — purely additive read endpoint. Deploy extraction_service and gateway together (or gateway can deploy slightly ahead/behind since the new proxy route is additive and doesn't affect existing routes). Rollback is a plain revert of both services; no state to unwind.

## Open Questions

- Should list results eventually support pagination matching `/api/v1/entities`? Deferred per Decision 2 — revisit if a tenant's run count grows large enough that `LIMIT 50` starts hiding relevant history.