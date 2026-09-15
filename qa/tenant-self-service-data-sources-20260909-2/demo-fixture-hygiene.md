# Demo & Fixture Hygiene -- tenant-self-service-data-sources-20260909-2

Scope: the primary admin surface's actual persisted contents on the deployed dev system (a human evaluator sees exactly what is there).

## Results

| Surface | Expected Dataset | Actual Contents | Status | Evidence |
|---|---|---|---|---|
| Data Sources list (tenant `demo-tenant`, via API as tenant admin) | curated: seeded demo connections or clean empty | **empty page** (`items: []`, `total: 0`) — no test-run debris, no `<capability>-test-<hash>` rows, no hex/timestamp-suffixed names | pass | live `GET /api/v1/data-sources` |
| Data Sources page (tenant admin UI) | curated empty state, not debris | "No data sources yet" with safe recovery copy; filters render labelled | pass | `../evidences/tenant-self-service-data-sources-20260909-2/accessibility/data-sources.png` |
| Reference scenarios RS-001/RS-003 | findable admin flow | "New connection" + "Configure the first connection" actions lead into the lifecycle; no volume buries them | pass | same screenshot |
| Azure-backed capabilities | inactive until approved resources + activation evidence | inactive; matches `run.provisioning` (`skip` entries) and the deployment record | pass | `.ralph/state.json` |

## Decision

**Clean.** No fixture pollution; nothing to remove.
