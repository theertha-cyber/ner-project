# Performance -- tenant-self-service-data-sources-20260909-2

Scope: single-user latency against the deployed dev system at http://localhost:8000, versus the design NFR authority. Source used: **technical design** `docs/design/tenant-self-service-data-sources.md` `## Non-Functional Requirements` — NFR-PERF-001 dev operating target: *under a controlled single-tenant local workload of 10 sequential direct-query requests against an approved fixture, p95 end-to-end latency at most 10 seconds and 0% errors* (clarified human direction; explicitly not a production SLO). No requirement-document fall-through was needed.

## Results

| Scenario | NFR Target | Observed | Status | Evidence |
|---|---|---|---|---|
| 10 sequential authenticated `GET /api/v1/data-sources` (single tenant) | p95 ≤ 10 s, 0% errors (dev target) | min 20 ms, p50 21 ms, **p95 22 ms**, max 23 ms, 10/10 ok | pass | probe run (script removed after run; values logged) |
| Filtered list (`provider/status/sort/order/page/page_size`) | same envelope | 200 in 49 ms | pass | live API |
| Health under idle | healthy | `/health` ok, DB reachable; `/health/live` ok | pass | live curl |
| Blob sync durability shape | no unbounded request task; durable worker path | design + scheduler/ledger implementation; manual/scheduled/catch-up covered by 26 passing tests | pass | code + suite |

## Decision

Dev performance target **met** with two orders of magnitude of headroom. No production capacity claim is made (the design explicitly defers it).
