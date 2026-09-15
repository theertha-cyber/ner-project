# Verification Plan

**Change:** manual-blob-sync-trigger
**Generated:** 2026-09-11
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | azure-blob-source-sync | Common durable Blob ingestion | New object is synchronized | Given an active Blob connection with a newly discovered object, when the sync job processes it, then its bytes enter the common ingestion pipeline with no Azure-specific downstream branches | Task 3.1: `tests/test_azure_blob_source_sync.py` ingestion-path regression | - [ ] |
| 2 | azure-blob-source-sync | Common durable Blob ingestion | Manual trigger runs the same job as the schedule | Given an active Blob connection, when a tenant admin calls the manual sync action, then the same durable job the scheduler uses is enqueued with manual trigger class and no cadence block | Task 3.2: `tests/test_manual_blob_sync_trigger.py::test_manual_trigger_enqueues_despite_recent_sync` | - [ ] |
| 3 | azure-blob-source-sync | Common durable Blob ingestion | Scheduled cadence with missed-schedule catch-up | Given an active connection whose last success is older than two 15-minute cadences, when the scheduler evaluates it, then exactly one catch-up run is enqueued | Task 3.3: `test_scheduler_cadence_and_catchup_decisions` regression | - [ ] |
| 4 | azure-blob-source-sync | Common durable Blob ingestion | Inactive connection never syncs | Given a Blob connection without active lifecycle state, when the scheduler evaluates or a manual trigger names it, then no sync job executes | Task 3.4: `tests/test_manual_blob_sync_trigger.py::test_inactive_connection_enqueues_nothing` | - [ ] |
| 5 | azure-blob-source-sync | Common durable Blob ingestion | Overlapping runs are prevented by the durable lease | Given a run holding the connection lease, when a second trigger fires for the same connection, then the second run does not enumerate or ingest and records a finite lease-held outcome | Task 3.5: lease test in `tests/test_azure_blob_source_sync.py` | - [ ] |
| 6 | tenant-data-source-control-plane | Manual Blob sync trigger action | Administrator triggers a manual sync on an active Blob connection | Given an authenticated tenant admin with an active Blob connection, when they call POST /sync with a fresh Idempotency-Key, then the durable blob_sync_run job with manual trigger is enqueued and the response carries only the safe outcome, identifiers, and timestamps | Task 3.6: gateway `test_manual_sync_enqueues_manual_trigger` | - [ ] |
| 7 | tenant-data-source-control-plane | Manual Blob sync trigger action | Manual sync on an inactive connection is rejected safely | Given a Blob connection without active state, when an admin calls the manual sync action, then the request is rejected with a finite safe outcome class and nothing is enqueued | Task 3.7: gateway inactive-rejection test | - [ ] |
| 8 | tenant-data-source-control-plane | Manual Blob sync trigger action | Manual sync on a PostgreSQL connection is rejected | Given a PostgreSQL connection, when an admin calls the manual sync action, then the request is rejected with a finite safe outcome class and nothing is enqueued | Task 3.7: gateway PostgreSQL-rejection test | - [ ] |
| 9 | tenant-data-source-control-plane | Manual Blob sync trigger action | Non-administrator is denied | Given an authenticated non-admin user, when they call the manual sync action, then the operation is denied and nothing is enqueued | Task 3.8: gateway non-admin-denial test | - [ ] |
| 10 | tenant-data-source-control-plane | Manual Blob sync trigger action | Cross-tenant manual sync is denied | Given a connection owned by tenant A and an admin of tenant B, when the tenant B admin calls the manual sync action, then access is denied with the connection-not-found class and no metadata is disclosed | Task 3.8: gateway cross-tenant test | - [ ] |
| 11 | tenant-data-source-control-plane | Manual Blob sync trigger action | Idempotent manual sync replay renders the safe result | Given a manual sync accepted under an Idempotency-Key, when the same key and body are resubmitted, then the original safe result is replayed with a replay marker and no duplicate job is enqueued | Task 3.9: gateway same-key replay test | - [ ] |
| 12 | tenant-data-source-portal | Manual sync-now control | Administrator triggers a manual sync from the detail view | Given an admin viewing an active Blob connection detail, when they click "Sync now", then the portal calls the manual sync action with a fresh Idempotency-Key and shows pending then safe enqueued-success with refreshed last-run status | Task 3.10: portal `SyncActivitySummary` + sync-mutation Vitest | - [ ] |
| 13 | tenant-data-source-portal | Manual sync-now control | Sync-now is unavailable for inactive connections | Given a Blob connection without active state, when the admin views the Sync activity panel, then the control is disabled with a safe blocked notice and no request is sent | Task 3.10: portal `SyncActivitySummary` + sync-mutation Vitest | - [ ] |
| 14 | tenant-data-source-portal | Manual sync-now control | Sync-now is absent for PostgreSQL connections | Given a PostgreSQL connection detail view, when the admin views the Sync activity panel, then no "Sync now" control is presented and the schedule-exemption notice is retained | Task 3.10: portal `SyncActivitySummary` + sync-mutation Vitest | - [ ] |
| 15 | tenant-data-source-portal | Manual sync-now control | Lease-held manual sync surfaces a safe retry notice | Given a Blob connection with a run already in progress, when the admin clicks "Sync now" and the backend reports lease-held, then a safe "sync already running" notice is shown with no diagnostics or raw errors | Task 3.10: portal `SyncActivitySummary` + sync-mutation Vitest | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | New route response codes and body fields | AI may invent error codes or response fields (e.g., `sync_id`, `RUNNING`) not in the spec or the control-plane `_CODE_STATUS` registry | Compare the new route's codes and response keys against specs + `data_sources.py` `_CODE_STATUS`; any code or field not named in either is suspect |
| 2 | Cadence vs. manual trigger semantics | AI may apply `evaluate_connection` cadence gating to the manual path, reintroducing the wait the change removes | Verify the route contains no cadence check and test that a recently-synced active connection still enqueues on manual trigger |
| 3 | Broker enqueue vs. inline execution | AI may run `run_sync` inline in the gateway request instead of enqueueing through the broker | Confirm the route calls only the enqueue seam (`enqueue_sync`/Celery send_task) and awaits no sync work; check request latency stays bounded |
| 4 | Portal control visibility rules | AI may show "Sync now" for PostgreSQL connections or enable it for inactive statuses | Render Blob-active, Blob-paused, and PostgreSQL detail views; assert control enabled / disabled-absent / absent respectively |
| 5 | Safe telemetry and logging in the new route | AI may log the connection id payload by interpolation, log exceptions directly, or emit non-declared metric labels | Run `scripts/telemetry_scan.py` over the diff; confirm structured `extra={...}` fields only and no new metric family |
| 6 | Idempotency semantics | AI may reuse one key for all clicks (blocking legitimate retriggers) or skip the `_mutate` wrapper | Click twice with fresh keys → two enqueues (or lease-held); resubmit same key+body → replay marker with no second enqueue |

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-011-tenant-scoped-azure-connection-control-plane | JWT tenant binding, tenant-admin-only mutations, idempotency, finite safe outcomes | Route must bind tenant from JWT, require tenant admin, use `_mutate`, return only finite safe codes | Exercise route as non-admin, cross-tenant, missing-key, and replayed-key; assert 403/404/400/replay-marker with the exact safe error shape |
| ADR-012-durable-azure-blob-source-synchronization | One durable Celery/RabbitMQ job, ledger + lease, identity-only payload | Manual path must enqueue the same `blob_sync_run` task with identity-only args; lease/active checks stay in the worker | Assert enqueued task name and args are `[tenant, connection, manual]` strings only; hold the lease and assert the second run records lease-held without ingesting |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Row 1: test output showing a newly discovered object enters the common ingestion pipeline with no Azure-specific downstream branches
- [ ] Row 2: API trace showing POST /sync on an active connection enqueues `blob_sync_run` with manual trigger class despite recent scheduled success
- [ ] Row 3: test output showing `evaluate_connection` still yields exactly one catch-up after two missed cadences (no regression)
- [ ] Row 4: test output showing scheduler evaluation and manual trigger on an inactive connection enqueue nothing
- [ ] Row 5: test output showing a lease-held second run skips enumeration/ingest and records the finite lease-held outcome
- [ ] Row 6: API trace showing 202 on POST /sync with safe outcome/identifiers/timestamps only
- [ ] Row 7: API trace showing safe 409-class rejection and zero enqueues for an inactive connection
- [ ] Row 8: API trace showing safe 409-class rejection and zero enqueues for a PostgreSQL connection
- [ ] Row 9: API trace showing a non-admin caller is denied with no state change
- [ ] Row 10: API trace showing a cross-tenant caller receives connection-not-found with no metadata disclosure
- [ ] Row 11: API trace showing same key+body replay returns the replay marker with no duplicate enqueue
- [ ] Row 12: screenshot/test showing "Sync now" pending → enqueued-success with refreshed last-run status on an active Blob detail
- [ ] Row 13: screenshot/test showing disabled control with blocked notice and zero requests for an inactive connection
- [ ] Row 14: screenshot/test showing no "Sync now" control and retained exemption notice on a PostgreSQL detail
- [ ] Row 15: screenshot/test showing the "sync already running" notice on a lease-held manual trigger with no diagnostics

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1 mitigation confirmed — route codes and response keys cross-checked against spec and `_CODE_STATUS`
- [ ] Risk 2 mitigation confirmed — manual trigger enqueues despite recent sync; no cadence check on the manual path
- [ ] Risk 3 mitigation confirmed — route enqueues only; no inline sync execution in the request path
- [ ] Risk 4 mitigation confirmed — control visibility matrix (Blob-active / Blob-inactive / PostgreSQL) verified by render
- [ ] Risk 5 mitigation confirmed — telemetry scan passes on the diff; no new metric family
- [ ] Risk 6 mitigation confirmed — fresh-key double click vs. same-key replay behave per spec

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** manual-blob-sync-trigger
**Proposal:** `openspec/changes/manual-blob-sync-trigger/proposal.md`
**Spec files reviewed:**
  - specs/azure-blob-source-sync/spec.md
  - specs/tenant-data-source-control-plane/spec.md
  - specs/tenant-data-source-portal/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Any observations, caveats, or follow-up items for future changes. -->
