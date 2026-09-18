## 1. Gateway Manual Sync Route

- [x] 1.1 Add `POST /api/v1/data-sources/{connection_id}/sync` to `src/gateway/api/v1/data_sources.py` through the existing `_mutate` wrapper with `require_tenant_admin` + `resolve_tenant_from_jwt`, Blob-provider and active-status checks, broker enqueue with identity-only `(tenant, connection, manual)` payload, and finite safe outcome codes.
- [x] 1.2 Register the new `INACTIVE_CONNECTION` / `UNSUPPORTED_PROVIDER` (and `SYNC_UNAVAILABLE` if needed) codes in `_CODE_STATUS` / `_CODE_HINTS` using safe, non-sensitive wording only.

## 2. Portal Sync-Now Control

- [x] 2.1 Add the "Sync now" control to `SyncActivitySummary` in `src/portal/src/components/data-sources/lifecycle.tsx` (Blob only, enabled iff `status === "active"`), with pending / enqueued / already-running / blocked / safe-error states and a last-run refresh after trigger.
- [x] 2.2 Add the `sync` lifecycle action to `src/portal/src/hooks/use-data-sources.ts` (fresh `Idempotency-Key` per click) and the supporting client contract in `src/portal/src/lib/data-sources.ts`.

## 3. Acceptance-Criteria Tests

- [x] 3.1 Row 1 — regression-run `tests/test_azure_blob_source_sync.py` ingestion path (new object enters the common pipeline, no Azure-specific branches).
- [x] 3.2 Row 2 — new `tests/test_manual_blob_sync_trigger.py::test_manual_trigger_enqueues_despite_recent_sync` (active connection synced moments ago still enqueues with manual class; no cadence block).
- [x] 3.3 Row 3 — regression-run `test_scheduler_cadence_and_catchup_decisions` (exactly one catch-up after two missed cadences).
- [x] 3.4 Row 4 — new `test_manual_blob_sync_trigger.py::test_inactive_connection_enqueues_nothing` (scheduler evaluation + manual trigger on inactive enqueue nothing).
- [x] 3.5 Row 5 — lease test in `tests/test_azure_blob_source_sync.py` (second trigger during held lease skips ingest, records lease-held).
- [x] 3.6 Row 6 — new gateway test `test_manual_sync_enqueues_manual_trigger` (202, identity-only manual enqueue, safe body only).
- [x] 3.7 Rows 7–8 — new gateway tests for inactive-connection and PostgreSQL-provider safe rejections with zero enqueues.
- [x] 3.8 Rows 9–10 — new gateway tests for non-admin denial and cross-tenant connection-not-found with no disclosure.
- [x] 3.9 Row 11 — new gateway test for same key+body replay (replay marker, no duplicate enqueue).
- [x] 3.10 Rows 12–15 — new portal Vitest for `SyncActivitySummary` + sync mutation (active pending→success+refresh, inactive disabled with zero requests, PostgreSQL absent, lease-held notice).

## 4. Verification & Evidence

- [ ] 4.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [ ] 4.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 4.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [ ] 4.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 4.6 Run `openspec validate manual-blob-sync-trigger --type change --strict` and confirm
         it exits clean before archive.
