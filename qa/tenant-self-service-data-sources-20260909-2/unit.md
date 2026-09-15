# Unit -- tenant-self-service-data-sources-20260909-2

Scope: changed-logic coverage for the 73-file change set (`60db8d0^..4dd49e5`), via the repository's own runners.

## Results

| Area | Current Coverage | Missing Case | Test Added/Recommended |
|---|---|---|---|
| Control plane (service/store/resolver/lifecycle/providers/testing, gateway routes) | 38/38 pass | none | none — includes idempotency replay/key-reuse, lifecycle transitions, tenant scoping negatives |
| Blob sync + ingestion boundary | 26/26 pass (within combined 107) | none | none — idempotency, replacement, deleted-source hiding covered |
| External-PG chat (validator/connector/drift/contract/index) | 98-file module pass (within combined 107) | validator hardening for `SELECT *` / `alias.*` / unresolvable columns (SEC-002) and locking-clause/literal/OFFSET gaps (SEC-003) | **recommended**: default-deny bare `*`, expand `alias.*` against contract columns, reject locking clauses, cap OFFSET |
| Delivery evidence (migration chain, compose contract, metric labels, perf fixture) | 107-module pass incl. 10-sequential fixture check | none | none |
| Portal data-sources (pages/components/hooks/lib) | 44/45 pass | `business_user` nav count is a stale pre-existing expectation (4 items before and after CAP-5) | fix the stale test to 4 (out of scope for this gate; recorded as follow-up) |
| Portal remainder | 658 passed / 49 failed workspace-wide; all 49 pre-existing and outside the change set | tracked above | follow-up only |

## Decision

Changed logic is covered by meaningful, passing tests. The single recommended addition (validator negative tests for SEC-002/SEC-003) is medium/low severity against currently-dead code and is follow-up work, not a blocker.
