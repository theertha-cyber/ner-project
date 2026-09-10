# Run report — tenant-self-service-data-sources-20260909-2 (final)

**Run:** tenant-self-service-data-sources-20260909-2
**Integration branch:** external-tenant-data-sources
**Date (UTC, system clock):** 2026-09-10T15:03:58Z
**Outcome:** queue exhausted — 5/5 selected items completed, 0 blocked, 0 skipped. All specs archived (5/5).

This dispatch processed the final queued item, CAP-6. CAP-2 through CAP-5 were already complete and archived on the integration branch. Toolchain: `openspec 1.6.0`, matching recorded `run.openspecVersion` — no version drift. Handoff checks passed (version 1, non-empty selectedItems/integrationBranch/items with CAP-n ids, slugs, phases; no `.iris/workspace.json` — single-repository project).

## Items completed

- **CAP-2 cap-2-tenant-scoped-connection-control-plane** — branch `change/cap-2-tenant-scoped-connection-control-plane`, commit `60db8d0` (merged). Spec archived.
- **CAP-3 cap-3-durable-azure-blob-synchronization-and-source-reconciliation** — branch `change/cap-3-durable-azure-blob-synchronization-and-source-reconciliation`, commit `1a69e58` (merged). Spec archived.
- **CAP-4 cap-4-contract-governed-external-postgresql-query-path** — branch `change/cap-4-contract-governed-external-postgresql-query-path`, commit `5f72d53` (merged). Spec archived.
- **CAP-5 cap-5-tenant-data-source-administration-portal** — branch `change/cap-5-tenant-data-source-administration-portal`, commit `a6143e6` (merged). Spec archived.
- **CAP-6 cap-6-local-compose-delivery-migration-and-operational-evidence** — branch `change/cap-6-local-compose-delivery-migration-and-operational-evidence`, commit `4dd49e5` (merged as `3bea6ad`). Spec `local-compose-data-source-delivery` archived (+2, ~0, -0). Observer verdict: COMPLETE (after one incomplete round addressing unticked verification boxes, telemetry point-in-time variance note, and a new negative chain test).

CAP-6 implementation (no runtime behavior change — delivery procedure plus verification only):

- `tests/test_local_compose_delivery_evidence.py` — 9 hermetic tests: linear migration chain 039→040→041→042 with single head; additive-only upgrades; compose sequencing/readiness contract (`db-init` gating, healthchecks, unique host ports); declared finite-label metric contract for the four terminal-outcome families; branched/broken-link negative; 10-sequential fixture direct-query perf check (0 errors, p95 ≤ 10 s dev target).
- `docs/runbooks/tenant-data-sources-local-delivery.md` — rolling deployment sequence, migration order, health/readiness checklist, safe-telemetry reference, compatible rollback/roll-forward procedure (30-minute dev target), activation gate, explicit out-of-scope list.
- Live evidence: `alembic heads` → `042 (head)`; 20/20 compose services Up; `/health` 200 on :8000–:8007; `telemetry_scan.py --dry-run` self-check PASS and live `--skip-flow` exit 0 (332 logs / 200 spans / 61 metrics at capture; later re-captures 342/355 logs — expected growth on a live stack, verdict stable); recovery exercise `docker compose restart gateway` 14:45:24Z → healthy 14:45:33Z (9 s).
- Combined regression: 107/107 passing across the CAP-2, CAP-3, CAP-4, ingestion-boundary, and delivery-evidence modules. (First combined run showed one transient cross-module temp-bytes failure in `test_temporary_bytes_deleted_on_success`; it passes standalone, in the single-module run 26/26, and on repeat — no source change in this capability.)

## Items blocked

None.

## Items skipped

None.

## Spec rewrites

- **CAP-2** — Delta renamed two baseline scenarios, so `openspec archive` refused to merge rather than drop them. → Restored baseline scenario headers in the delta (A non-default selection cannot be activated; Tenant users cannot modify profiles) with reconciled bodies encoding the approved-Azure exception. Reason: archive guard demanded it; matches the decomposition instruction to amend those scenarios via delta.
- **CAP-4** — Delta typed external-postgresql-chat requirements as ADDED, but the baseline already carried them from a prior unrecorded archive of this same change, so `openspec archive` aborted with 'already exists'. → Re-typed the delta section to MODIFIED Requirements with identical requirement headers and bodies; archive then merged idempotently (+0, ~4, -0). Reason: archive guard demanded it; no requirement substance changed.
- **CAP-6** — none. The delta used ADDED Requirements for the new `local-compose-data-source-delivery` capability; no baseline requirement was altered.

## Demo/seed data reconciliation

Checked as required because CAP-5 cites reference scenarios (RS-001, RS-003). Read-only queries against the running dev database (`ner_dev` on the compose postgres, alembic version 037 — stack images predate the CAP-2 merge):

- `public.external_pg_contracts`: 0 rows.
- `public.tenant_data_source_connections`: table absent in this database vintage (expected — 040 not yet applied here).
- No `<capability>-test-<hash>`-style rows, no test leftovers anywhere in the data-source tables.

Verdict: clean — nothing to remove. Test suites run against `ner_test` with teardown; the portal ships with no seeded tenant/connections (recorded at CAP-5).

## UI Design Contract

- Resolved design system: **Clean — existing portal override** (`docs/design/ui-contract.md`).
- Target platform: **web** (Next.js/React in `src/portal`).
- Theme file: `src/portal/design-system/ner-portal/tokens.css`, loaded as the first import of `src/portal/src/app/globals.css`. No tokens were added (no value was missing).
- No new assets; craft bindings: anti-ai-slop, accessibility-baseline, state-coverage, animation-discipline, form-validation, typography, typography-hierarchy, laws-of-ux.

### Per-capability UI verification

- **CAP-2** — backend only; no UI verification applicable.
- **CAP-3** — backend only; no UI verification applicable.
- **CAP-4** — backend only; no UI verification applicable.
- **CAP-5 Tenant Data Source Administration Portal** — screens SCR-1, SCR-2, SCR-3 (CMP-1…CMP-10 per decomposition). Lint: P0 0, P1 0. Screenshots: none taken — comparison skipped because there is no headless capture path on this machine (no Playwright/Chromium installed; installing it would outlive the run with no `run.provisioning` entry) and no seeded tenant/connections exist to render populated screens. Offered to the QA gate. Portal unit tests: 41/41 passing (recorded at CAP-5).
- **CAP-6** — deployment capability; decomposition records Demonstrates Reference Scenarios as not applicable (no screen, no UI code). No UI verification applicable.

## Anything noticed but deliberately left alone

- The running dev stack's images predate the CAP-2 merge (built ~2 days ago; `ner_dev` at alembic 037, gateway restart test notwithstanding). A fresh `docker compose build && up` will apply 039→040→041→042 via `db-init`. Rebuilding the shared running stack mid-run was out of scope and risky; the runbook documents the sequence instead.
- `public.external_pg_contracts` exists (empty) in `ner_dev` at alembic 037, i.e. created outside the migration chain by earlier capability verification. Left as-is: empty, harmless, and converge on rebuild.
- `docker-compose.yml` retains the obsolete top-level `version` key (compose warns, ignores). Cosmetic; untouched to keep the CAP-6 diff behavior-free.
- Working tree still carries uncommitted prior-run artifacts outside this run's change sets (tracked edits to `.gitignore`, `docs/adr/001`, `docs/architecture/*`, `docs/requirement/*`, `src/portal/src/app/globals.css`; untracked ADRs 011–014, design docs, decomposition, earlier archive dirs, portal design-system). They were left untouched — CAP-6 staged and committed only its own 9 files. A follow-up should commit or discard that residue.
- Azure live verification remains deferred/inactive per `run.provisioning` (`skip` entries for `azure-blob-test-account` and `azure-postgres-test-instance`): fixtures/fakes only. Capabilities stay inactive until approved resources and activation evidence exist.
