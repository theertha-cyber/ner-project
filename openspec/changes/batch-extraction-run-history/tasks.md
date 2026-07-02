## 1. Backend — Extraction Service

- [x] 1.1 Add `list_extraction_runs(db, tenant_id, limit=50)` to `src/extraction_service/services/entity_store.py`, querying `{schema}.extraction_runs` ordered by `started_at DESC` with `LIMIT 50`, scoped via the existing `_schema(tenant_id)` pattern.
- [x] 1.2 Add `BatchRunListItem` and `BatchRunListResponse` schemas to `src/extraction_service/api/v1/schemas.py` (`BatchRunListItem` extends `BatchRunStatus` with `run_id: str`; `BatchRunListResponse` wraps `runs: list[BatchRunListItem]`).
- [x] 1.3 Add `GET /api/v1/extract-batch` route handler in `src/extraction_service/api/v1/extraction.py`, calling `list_extraction_runs` and returning `BatchRunListResponse`. Ensure it's registered so it doesn't collide with the existing `GET /api/v1/extract-batch/{run_id}` route.
- [x] 1.4 Restrict access consistent with existing extraction endpoints (any authenticated tenant user, per scenario 5 — no additional role check needed beyond tenant context).

## 2. Backend — Gateway Proxy

- [x] 2.1 Add the `GET /api/v1/extract-batch` proxy route in `src/gateway/api/v1/extraction_proxy.py`, forwarding the `Authorization` header and returning the extraction service's response body and status code unchanged.

## 3. Backend Tests

- [x] 3.1 Add tests to `tests/test_batch_extraction.py` for: list returns all runs with correct fields (scenario 1), most-recent-first ordering (scenario 2), tenant isolation — empty list for a tenant with no runs while another tenant has runs (scenario 3), empty array for a fresh tenant (scenario 4), and 200 response for a `business_user` role (scenario 5).
- [x] 3.2 Add or update a gateway proxy test (in the existing gateway test suite covering `extraction_proxy.py`) for: proxy forwards `GET /api/v1/extract-batch` to the extraction service and returns the `runs` array (scenario 7), and re-run existing tests covering scenarios 6 and 8 to confirm they still pass unaffected by the new route.

## 4. Frontend Verification

- [x] 4.1 Manually verify in the running portal that the Batch Runs tab fetches `GET /api/v1/extract-batch` on mount and lists existing runs (scenario 9) — no code change expected in `use-batch-runs.ts` or `BatchRunsTab.tsx`; if a mismatch is found between the actual response shape and what the hook expects, fix the mismatch on the backend (schemas.py/entity_store.py), not the frontend.
- [x] 4.2 Manually verify run history persists across a full page reload after a completed run (scenario 10).
- [x] 4.3 Manually verify selecting a run card updates the detail panel (scenario 11), triggering a new run adds it to the top as "queued" and auto-selects it (scenario 12), in-progress runs poll every 3 seconds and stop at a terminal state (scenario 13), and status pill colors match good/warn/bad tokens per status (scenario 14).

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
         13/14 pass; scenario 8 does NOT pass as specced (gateway returns 401, not
         403, for a missing JWT — pre-existing, unrelated to this change). Left
         unchecked pending a human decision (fix code / fix spec / accept as-is).
- [x] 5.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [x] 5.6 Run `openspec validate batch-extraction-run-history --type change --strict` and confirm
         it exits clean before archive. Result: "Change 'batch-extraction-run-history' is valid".