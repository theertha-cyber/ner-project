# Verification Plan

**Change:** batch-extraction-run-history
**Generated:** 2026-07-01
**Status:** 🟡 Evidence collected by AI agent — Audit Record sign-off still required by a human reviewer before archive. Scenario 8 has a known unresolved discrepancy (see row 8): actual gateway behavior is 401, not the spec's stated 403; this predates this change and this change does not touch gateway auth. A human reviewer should decide whether to fix the code, correct the spec, or accept as-is before archiving.

**Environment notes from this verification pass:**
- `tenant_demo_tenant.extraction_runs` (dev DB) was missing `total_documents`/`processed_count`/`skipped_count`/`failed_count` columns present on other tenants (e.g. `tenant_6ad974a3_...`) — pre-existing schema drift unrelated to this change, patched via additive `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` so the existing (already-shipped) `POST /api/v1/extract-batch` and the new list endpoint could be exercised for `demo-tenant`.
- Manual browser verification hit a pre-existing, app-wide auth-bootstrap race: on a hard page reload, `RequireAuth` evaluates `user === null` (via `src/portal/src/components/require-auth.tsx`) before the `/api/v1/auth/refresh` cookie call resolves, so a reload can flash through `/login` before landing back on a real page. Unrelated to this change (affects all authenticated routes, not just Batch Runs); worked around in the verification script by waiting and re-navigating. Worth a separate bug report.
- `gateway` and `extraction_service` containers had to be rebuilt (`docker compose build` + `up -d --no-deps`) to pick up this change's code, since neither container mounts source as a volume or runs with `--reload`.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | extraction-service | List extraction runs | List batch extraction runs for a tenant | Given a tenant with a completed, a queued, and a failed run, when a Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with a `runs` array containing all three, each including `run_id`, `status`, `total_documents`, `processed_count`, `skipped_count`, `failed_count`, `started_at`, `completed_at`, and `model_version` | tests/test_batch_extraction.py::test_list_batch_runs_returns_all_fields (task 3.1) — PASSED | - [x] |
| 2 | extraction-service | List extraction runs | Runs are ordered most-recent-first | Given a tenant with runs started at different times, when a Tenant Admin GETs `/api/v1/extract-batch`, then the `runs` array is ordered by `started_at` descending | tests/test_batch_extraction.py::test_list_batch_runs_ordered_desc (task 3.1) — PASSED | - [x] |
| 3 | extraction-service | List extraction runs | List is scoped to the requesting tenant | Given tenant A has runs and tenant B has none, when tenant B's Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with an empty `runs` array | tests/test_batch_extraction.py::test_list_batch_runs_tenant_isolated (task 3.1) — PASSED | - [x] |
| 4 | extraction-service | List extraction runs | List returns empty array when no runs exist | Given a tenant with no extraction runs, when a Tenant Admin GETs `/api/v1/extract-batch`, then the response is 200 with an empty `runs` array | tests/test_batch_extraction.py::test_list_batch_runs_empty_for_new_tenant (task 3.1) — PASSED | - [x] |
| 5 | extraction-service | List extraction runs | List entities as non-admin business user | Given an authenticated `business_user`, when they GET `/api/v1/extract-batch`, then the response is 200 | tests/test_batch_extraction.py::test_list_batch_runs_business_user_allowed (task 3.1) — PASSED | - [x] |
| 6 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy forwards single extraction request without tid in URL | Given a valid JWT with `tenant_id` and `role: business_user`, when a POST is sent to gateway `/api/v1/extract` with `{"text": "Acme Corp"}`, then the response is 200 with extracted entities and the proxy forwarded to the extraction service at `/api/v1/extract` | tests/test_extraction_gateway_proxy.py::test_gateway_proxies_extract_without_tid (task 3.2) — PASSED, no pre-existing suite found so a new one was created | - [x] |
| 7 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy forwards batch run list request without tid in URL | Given a valid JWT with `tenant_id` and `role: business_user`, when a GET is sent to gateway `/api/v1/extract-batch`, then the response is 200 with a `runs` array and the proxy forwarded to the extraction service at `/api/v1/extract-batch` | tests/test_extraction_gateway_proxy.py::test_gateway_proxies_extract_batch_list (task 3.2) — PASSED | - [x] |
| 8 | extraction-service | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy returns 403 when JWT is missing | Given no JWT token, when a POST is sent to gateway `/api/v1/extract` with `{"text": "test"}`, then the response is 403 | tests/test_extraction_gateway_proxy.py::test_gateway_rejects_missing_jwt — DISCREPANCY: actual gateway behavior returns **401**, not 403. Confirmed via direct call to the real gateway. Pre-existing mismatch in `TenantContextMiddleware`, predates this change (this change does not touch gateway auth); test pins current (401) behavior rather than the unmet spec text | - [ ] |
| 9 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Batch Runs tab lists existing runs | Given the user switches to or reloads on the Batch Runs tab, when the tab mounts, then a `GET /api/v1/extract-batch` request is sent, every run in the response's `runs` array appears as a card, and the most recent run is selected by default | Manual browser verification (Playwright-driven Chromium against the running portal + rebuilt gateway/extraction_service) — network trace showed `GET /api/v1/extract-batch`, 49 run cards rendered, no empty state, most recent auto-selected. Screenshot: `01-batch-runs-on-mount.png` (task 4.1) — PASSED | - [x] |
| 10 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Run history persists across page reload | Given a batch run previously completed, when the page is reloaded and the Batch Runs tab mounts, then the completed run appears in the list and the empty state ("No batch runs yet") is not shown | Manual browser verification — full page reload, re-fetch confirmed via network trace, 49 cards still present, no empty state. Screenshot: `02-after-reload.png` (task 4.2) — PASSED. Note: hit a pre-existing, unrelated auth-bootstrap race on hard reload (see Notes) that had to be worked around | - [x] |
| 11 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Selecting a batch run shows detail | Given multiple run cards are visible, when the user clicks a card, then it receives a primary border highlight and the right panel shows that run's stats and progress percentage | Manual browser verification — clicked second card, border highlight moved, detail panel updated to that run's id/stats. Screenshot: `03-card-selected.png` (task 4.3) — PASSED | - [x] |
| 12 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Triggering a new batch run | Given the Batch Runs tab is active, when the user clicks "New batch run", then a `POST /api/v1/extract-batch` request is sent and on 202 the new run appears at the top of the list as "queued" and is auto-selected | Manual browser verification — network trace showed `POST /api/v1/extract-batch`, new run appeared at top with "queued" pill, auto-selected. Screenshot: `04-new-run-triggered.png` (task 4.3) — PASSED | - [x] |
| 13 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | In-progress runs poll for status updates | Given one or more runs have status "running" or "queued", when the tab is mounted and active, then the system polls `GET /api/v1/extract-batch/{run_id}` every 3 seconds per in-flight run until it reaches a terminal state | Manual browser verification — network trace showed `GET /api/v1/extract-batch/{run_id}` ~3.2s after trigger, card/detail updated queued→completed; separate 10s observation window showed exactly 1 poll (stopped after reaching terminal state). Screenshot: `05-after-poll-wait.png` (task 4.3) — PASSED | - [x] |
| 14 | portal-extraction-page | Batch Runs Tab — Batch Extraction Management | Status pills use correct visual styles | Given runs with various statuses, when the list renders, then "completed" uses the good color token, "running"/"queued" use the warning token, and "failed" uses the bad token | Manual browser verification — "completed" rendered green, "queued" rendered amber/warning, FAILED stat value rendered red, consistent across all screenshots (task 4.3) — PASSED | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Tenant scoping on the new list query (ADR-001) | AI may write the list query without scoping to `_schema(tenant_id)`, or interpolate `tenant_id` unsafely, risking a cross-tenant data leak | Read the new query in `entity_store.py`/`extraction.py`; confirm it targets `{schema}.extraction_runs` using the same `_schema()` helper as existing endpoints, and confirm scenario 3 (tenant isolation) passes with two distinct tenants |
| 2 | Response field drift from `BatchRunStatus` | AI may invent extra fields (e.g., `document_id`) or rename existing ones instead of reusing `BatchRunStatus` fields plus `run_id` | Diff the new response schema against `BatchRunStatus` in `schemas.py`; confirm no fields exist beyond those named in the "List extraction runs" requirement |
| 3 | Gateway proxy route wiring | AI may add the new proxy route with the wrong HTTP method, forget to forward the `Authorization` header, or accidentally shadow the existing `/api/v1/extract-batch/{run_id}` route (path collision with the no-ID list route) | Manually call `GET /api/v1/extract-batch` and `GET /api/v1/extract-batch/{run_id}` through the gateway and confirm both route correctly and both forward the JWT |
| 4 | Ordering and cap correctness | AI may omit `ORDER BY started_at DESC` or implement an unbounded query instead of the agreed `LIMIT 50` | Insert runs with distinct `started_at` values and confirm response order; confirm a `LIMIT` clause exists in the query |
| 5 | `model_version` passthrough for base-model runs (ADR-008) | AI may special-case `model_version = "0"` (e.g., convert to `null` or omit it) instead of passing it through as-is | Trigger or seed a run with `model_version = "0"` and confirm it appears unmodified in the list response |
| 6 | Scope creep into frontend code | Proposal states no frontend code change is needed since `use-batch-runs.ts` already calls the endpoint; AI may unnecessarily modify the hook or components anyway | Diff review: confirm `src/portal/src/hooks/use-batch-runs.ts` and `BatchRunsTab.tsx` are unchanged (or changes are justified against a real discrepancy found during implementation) |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001: Tenant Data Isolation via Separate Database Schemas | Each tenant's data lives in its own `tenant_<uuid>` schema | The new list query must scope to `_schema(tenant_id)`, with no cross-tenant reads | Run scenario 3 (list is scoped to the requesting tenant) with two tenants that both have runs; confirm each tenant only sees its own |
| ADR-008: Base Model as Default | Batch runs may legitimately use `model_version: "0"` | The list response must pass through `model_version` unmodified, including `"0"` | Run scenario with a base-model run (`model_version = "0"`) through the list endpoint and confirm the value is `"0"` in the response, not `null` or omitted |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (List batch extraction runs for a tenant): API trace or test output showing `GET /api/v1/extract-batch` returning 200 with all three runs and required fields
- [x] Scenario 2 (Runs ordered most-recent-first): test output or trace showing correct descending order
- [x] Scenario 3 (List scoped to requesting tenant): test output showing tenant B's list is empty despite tenant A having runs
- [x] Scenario 4 (Empty array when no runs exist): test output showing empty `runs` array for a fresh tenant
- [x] Scenario 5 (business_user can list): test output showing 200 for a `business_user` role
- [x] Scenario 6 (proxy forwards `/extract` without tid): existing test/trace re-confirmed unaffected by this change
- [x] Scenario 7 (proxy forwards list request without tid): API trace showing gateway `GET /api/v1/extract-batch` reaching the extraction service and returning `runs`
- [ ] Scenario 8 (proxy 403 without JWT): NOT MET — actual gateway behavior is 401, not 403 (pre-existing, unrelated to this change; see Spec Alignment row 8)
- [x] Scenario 9 (Batch Runs tab lists existing runs): screenshot or browser trace showing populated run list on tab mount, with network trace of `GET /api/v1/extract-batch`
- [x] Scenario 10 (Run history persists across reload): screenshot before and after a manual page reload showing the completed run still listed, no "No batch runs yet" message
- [x] Scenario 11 (Selecting a run shows detail): screenshot showing selected card highlight and matching detail panel
- [x] Scenario 12 (Triggering a new run): screenshot/trace showing new "queued" run appended to top of list and auto-selected
- [x] Scenario 13 (In-progress runs poll): network trace showing 3-second polling of `GET /api/v1/extract-batch/{run_id}` that stops at a terminal state
- [x] Scenario 14 (Status pill colors): screenshot showing correct color tokens for each status

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed ✓
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — tenant-scoping check performed with two tenants, no cross-tenant leakage observed
- [x] Risk 2 mitigation confirmed — response schema diffed against `BatchRunStatus`, no extraneous or renamed fields
- [x] Risk 3 mitigation confirmed — both `/api/v1/extract-batch` and `/api/v1/extract-batch/{run_id}` gateway routes verified to route correctly with no collision
- [x] Risk 4 mitigation confirmed — ordering and `LIMIT 50` verified against seeded data
- [x] Risk 5 mitigation confirmed — `model_version: "0"` run verified to pass through unmodified
- [x] Risk 6 mitigation confirmed — frontend hook/component diff reviewed, no unnecessary changes (no frontend files modified)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `pytest tests/test_batch_extraction.py` — 9/9 passed (4 pre-existing + 5 new), including tenant-isolation fixture that provisions/tears down ephemeral schemas for isolation/empty-tenant cases | 1, 2, 3, 4, 5 | AI agent (Claude) | 2026-07-01 |
| 2 | Test output | `pytest tests/test_extraction_gateway_proxy.py` (new file — no pre-existing gateway proxy suite existed) — 3/3 passed | 6, 7, 8 (8 pinned to actual 401 behavior, not spec's stated 403 — see row 8 note) | AI agent (Claude) | 2026-07-01 |
| 3 | Manual test | `model_version: "0"` passthrough — inserted a run row with `model_version='0'` directly, confirmed `GET /api/v1/extract-batch` returns it unmodified as `"0"` | ADR-008 compliance (ties to scenario 1) | AI agent (Claude) | 2026-07-02 |
| 4 | Browser trace + screenshots | Playwright-driven Chromium against the running portal (localhost:3000) + rebuilt gateway/extraction_service containers, logged in as `bizuser@democorp.io` (demo-tenant). Screenshots in scratchpad: `01-batch-runs-on-mount.png`, `02-after-reload.png`, `03-card-selected.png`, `04-new-run-triggered.png`, `05-after-poll-wait.png`. Network traces confirmed `GET`/`POST /api/v1/extract-batch` and `GET /api/v1/extract-batch/{run_id}` calls at each step | 9, 10, 11, 12, 13, 14 | AI agent (Claude) | 2026-07-02 |
| 5 | Manual test | Polling-stop check — triggered a run, watched network for 10s, observed exactly 1 poll GET (matches the run reaching "completed" terminal state, no further polling) | 13 | AI agent (Claude) | 2026-07-02 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** batch-extraction-run-history
**Proposal:** `openspec/changes/batch-extraction-run-history/proposal.md`
**Spec files reviewed:**
  - specs/extraction-service/spec.md
  - specs/portal-extraction-page/spec.md

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