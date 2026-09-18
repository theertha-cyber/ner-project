# Integration -- tenant-self-service-data-sources-20260909-2

Scope: API contracts, inter-service calls, persistence and C4 container assumptions against the deployed dev system at http://localhost:8000, plus migration evidence. Authenticated checks ran as the seeded tenant admin.

## Results

| Contract/Boundary | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| `GET /api/v1/data-sources` list contract | safe `ConnectionPage` (`items/page/page_size/total/total_pages/sort/order`) | exact shape, `total: 0`, `sort: last_activity`, `order: desc` | pass | live API |
| Pagination bounds | `page_size` 1–100 | `page_size=200` returns 422 `INVALID_REQUEST` (`'page_size' must be 1-100`) | pass | live API |
| Closed query grammar | unknown fields rejected | `?bogus=1` returns 422 `INVALID_REQUEST` (not accepted query parameter) | pass | live API |
| Single-record lookup, malformed id | safe 404, no metadata | `/not-a-uuid` returns 404 `CONNECTION_NOT_FOUND` with request id | pass | live API |
| Auth boundary | no token means no data | 401 `AUTH_ERROR`; wrong-shaped JSON login returns validation detail, no stack | pass | live API |
| CAP-2 lifecycle + CAP-4 contract routes live | 9 routes in OpenAPI | `/api/v1/data-sources`, `/{id}`, `/test`, `/activate`, `/pause`, `/replace`, `/retire`, `/{id}/contracts`, `/contracts/{version}/publish` all registered (44 paths total) | pass | live `/openapi.json` |
| Migration chain 038–042 | linear, single head, healthy post-deploy | deployer verified: stamp `037`→`042`, `Schema verification passed: no drift`, 20/20 services Up | pass | `docs/deploy/tenant-self-service-data-sources-20260909-2-dev.md` |
| Tenant isolation at runtime | cross-tenant id yields 404 | covered by unit/integration tests (38 control-plane tests incl. isolation negatives); **not** re-proven live — doing so needs two tenants' JWTs and was not attempted | not run (covered by suite) | `tests/test_tenant_data_source_control_plane.py` |
| Write-path lifecycle live (create/test/activate/pause/replace/retire) | exercised | **not exercised live** — creating junk connections would pollute the demo tenant; covered by the 38 passing control-plane tests including idempotency replay/key-reuse and `ACTIVE_PROVIDER_EXISTS` races | not run (deliberate; suite covers) | same suite |
| Azure live sync / external-PG drift against real tenants | active capability | **inactive by design**: `run.provisioning` defers both Azure test resources (`skip`); capabilities stay inactive until approved resources and activation evidence exist | not applicable | `.ralph/state.json` provisioning |

## Decision

Contracts hold live; persistence and deployment sequencing verified. No contract drift found. The two deliberate live gaps (second-tenant isolation probe, junk-creating write path) are named conditions, both covered by passing suites.
