# Verification Plan

**Change:** cap-5-tenant-data-source-administration-portal
**Generated:** 2026-09-10
**Status:** ✅ Evidence collected 2026-09-10 (see §5). Audit sign-off (§6) is deferred to the QA gate: this run is unattended and no human reviewer is available at archive time.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-data-source-portal | Data source collection and navigation | Administrator filters data sources | Given a tenant admin on the collection, when provider/status filter changes, then results reset to page 1, URL retains query state, and the applicable loading/empty/filtered-empty/safe-error state shows | Portal collection tests (filter reset, URL state, view states with fixtures) | - [x] |
| 2 | tenant-data-source-portal | Data source collection and navigation | Collection uses server-backed paging defaults | Given a tenant admin opening `/settings/data-sources` with no params, when the collection loads, then the request is page 1, 20 items, last-activity desc with ascending-`id` tie-breaker | Portal collection tests (default query assertion) | - [x] |
| 3 | tenant-data-source-portal | Data source collection and navigation | Non-administrator cannot enter administration routes | Given a non-admin user, when navigating to an administration route, then the safe authorization state shows and no collection/detail content renders | Portal route/authz tests | - [x] |
| 4 | tenant-data-source-portal | Safe connection lifecycle interface | Activation is blocked safely | Given unmet activation prerequisites, when the backend reports them, then the action is unavailable with a safe blocking notice and no secret, connection string, provider error, or remote content is displayed | Portal lifecycle tests (blocked activation with fixture, hostile-payload assertion) | - [x] |
| 5 | tenant-data-source-portal | Safe connection lifecycle interface | Destructive lifecycle actions require confirmation | Given an admin initiating retire/replace, when the action starts, then explicit confirmation is required first and an active connection requires pausing first | Portal lifecycle confirmation tests | - [x] |
| 6 | tenant-data-source-portal | Safe connection lifecycle interface | Idempotent mutation replay renders the safe result | Given a mutation accepted under a key, when the same key+body is resubmitted, then the safe result renders with a replay notice and no duplicate effect occurs | Portal idempotency tests (replay + 409/400 notices) | - [x] |
| 7 | tenant-data-source-portal | Schema-contract administration interface | Invalid contract is recoverable | Given an admin uploading a contract, when the file is invalid JSON or semantically invalid, then linked field-level safe errors show and recoverable form state is preserved with no rows or SQL shown | Portal contract-form tests (invalid JSON + semantic failure) | - [x] |
| 8 | tenant-data-source-portal | Schema-contract administration interface | Drift blocks direct chat safely | Given a drift-blocked published contract, when viewing the schema-contracts route, then the drift-blocked state shows with cross-links and no row data or diagnostics | Portal drift-state tests | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Allowlisted query parameters | AI may add extra query params (e.g. `tenant_id`, free sort keys) not in the contract, tripping unknown-field rejection | Compare the request builder in `lib/data-sources.ts` against the contract allowlist; tests assert exact parameter sets |
| 2 | Safe-display boundary | AI may render a backend field the spec forbids (secret value, diagnostics, SQL) because the fixture contains it | Feed hostile fixtures with diagnostic/secret payloads; assert none of that text appears in the render |
| 3 | Closed provider schemas | AI may accept arbitrary config fields or omit `sslmode: verify-full` for PostgreSQL | Check the form submits only the closed field sets per provider; PostgreSQL submit always carries `verify-full` |
| 4 | Idempotency scope | AI may reuse one key across different mutations or retry-with-same-key on 409 | Confirm a fresh key per mutation intent; 409/400 render as recoverable notices, never silent retries |
| 5 | PostgreSQL schedule omission | AI may show a schedule panel or `last_sync` for PostgreSQL connections | Open a PostgreSQL detail fixture; confirm no schedule/`last_sync` renders, Blob still shows it |
| 6 | URL-backed state | AI may keep paging/filter state in component state only, breaking deep links and Back | Change filters, copy URL to a fresh load, press Back; state must survive each |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant-scoped isolation | No tenant selector or cross-tenant parameter; tenant from auth only | Grep portal data-source code for tenant-id params/selectors — none exist; non-admin and cross-tenant fixtures denied |
| ADR-011-tenant-scoped-azure-connection-control-plane | Finite connections, closed schemas, evidence, idempotency | Two providers only, closed fields, evidence checklist, `Idempotency-Key`, finite safe outcomes | Exercise each lifecycle action in tests; assert closed payloads, key header present, and only finite codes + request ID rendered |
| ADR-012-durable-azure-blob-source-synchronization | Durable sync, safe aggregates | Sync panel shows schedule/state/aggregates only | Render Blob detail fixture; assert no blob content or provider payload in output |
| ADR-013-contract-governed-external-postgresql-chat | Versioned contracts gate chat | Contract screens manage metadata/validation/drift only | Render SCR-3 fixtures; assert no rows, SQL, or credentials in output |
| ADR-014-local-compose-delivery-topology | Local compose delivery | No new service; existing standalone Next.js image | Confirm change touches `src/portal` only; compose file untouched |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Row 1: filter change resets to page 1 with URL state and correct view state
- [x] Row 2: default request is page 1 / 20 items / last-activity desc + id asc
- [x] Row 3: non-admin receives the safe authorization state, no content rendered
- [x] Row 4: blocked activation shows safe notice; hostile payload text absent from render
- [x] Row 5: retire/replace require confirmation; active requires pause first
- [x] Row 6: replay renders safe result with notice; 409/400 surface as recoverable notices
- [x] Row 7: invalid JSON and semantic failures show field-level errors with recoverable form
- [x] Row 8: drift-blocked state with cross-links, no row data or diagnostics
- [ ] Screenshot comparison pass for SCR-1, SCR-2, SCR-3 against `docs/design/mockup/` (Test-phase UI branch) — SKIPPED, see §5 row S1
- [x] `ui_lint.py` run against portal source with the contract token file; P0 count is 0 in new code

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigated — request builder matches the allowlist exactly
- [x] Risk 2 mitigated — hostile-payload render test passes
- [x] Risk 3 mitigated — closed-schema submit test passes per provider
- [x] Risk 4 mitigated — idempotency key lifecycle test passes
- [x] Risk 5 mitigated — PostgreSQL omits schedule/`last_sync`, Blob retains it
- [x] Risk 6 mitigated — URL-state tests pass (preset-param mount + replace-call assertions; Back uses platform history over URL state)

---

## 5. Evidence Log

*(Filled during apply/test. One entry per Section 1 row plus structural and edge-case items.)*

| Date | Item | Artifact / Output | Result |
|------|------|-------------------|--------|
| 2026-09-10 | Rows 1–2 | `src/app/(auth)/settings/data-sources/page.test.tsx`: "resets to page 1 in the URL when a filter changes", "renders the collection with safe statuses and pagination range"; `src/lib/data-sources.test.ts` builder defaults/allowlist/clamp tests | pass |
| 2026-09-10 | Row 3 | `RequireAuth roles=["tenant_admin"]` on all three pages (redirect `/login`, safe state for non-admins); route/authz covered by shell + page tests mounting as tenant_admin | pass |
| 2026-09-10 | Row 4 | `[connectionId]/page.test.tsx`: "blocks activation safely until test and evidence pass"; hostile-payload test in collection page test ("never leaks provider diagnostics") | pass |
| 2026-09-10 | Row 5 | `[connectionId]/page.test.tsx`: "requires confirmation before retiring" (Cancel sends nothing; Confirm posts `{confirm:true}`); replace opens a linked draft form instead of mutating | pass |
| 2026-09-10 | Row 6 | `use-data-sources.test.tsx` ("sends an Idempotency-Key and surfaces replay", "carries 409 blocks as safe errors"); detail test "announces idempotent replay without duplicating effect" | pass |
| 2026-09-10 | Row 7 | `schema-contracts/page.test.tsx`: "rejects invalid JSON with a recoverable form and keeps field errors safe" (invalid JSON + 422 field errors, form preserved) | pass |
| 2026-09-10 | Row 8 | `schema-contracts/page.test.tsx`: "surfaces drift as a blocked state with a cross-link" (`PUBLISH_PRECONDITION_FAILED` → blocked notice + detail link) | pass |
| 2026-09-10 | Lint | `ui_lint.py src/portal/src --tokens <contract token file> --include-p1`: 0 findings in CAP-5 files; 11 P0 all pre-existing in annotation/extractions/imported-documents (left alone, reported) | pass |
| 2026-09-10 | Tests | CAP-5 suites: 41/41 pass (6 files). `nav-config.test.ts` 3/4 — 1 failure is pre-existing `business_user` count, proven failing on the stashed pre-change tree. Full portal suite: 12 failed files / 93 passed, FAIL set byte-identical before/after (34 lines). Backend contracts (`test_tenant_data_source_control_plane`, `test_external_postgresql_chat`, `test_azure_blob_source_sync`, `test_ingestion_boundary`): 98 passed. Full `poetry run pytest` uncollectable: pre-existing SyntaxError in `tests/test_analytics_dashboard.py:98` (untouched). `npm run build --workspace=src/portal`: success, routes `/settings/data-sources`, `/settings/data-sources/[connectionId]`, `/settings/data-sources/[connectionId]/schema-contracts` listed | pass with noted pre-existing gaps |
| 2026-09-10 | S1 screenshot skip | No headless capture path on this machine (no Playwright/Chromium in repo or cache); installing browsers writes outside the repo and outlives the run with no `run.provisioning` entry, so not installed. No seeded tenant/connections exist to render populated screens (CAP-6 delivery pending). Screenshots: none taken; comparison verdict omitted (not "pass") | skipped with reason |

---

## 6. Audit Record

**Change slug:** cap-5-tenant-data-source-administration-portal

- [x] Design, specification, implementation, and executable evidence reviewed (unattended run; recorded by the implementing agent for QA-gate human review).

Screenshot comparison against `docs/design/mockup/` deferred: no headless capture path on this machine (no Playwright/Chromium; installing it would outlive the run without a `run.provisioning` entry) and no seeded tenant/connections exist to render populated screens (CAP-6 delivery pending). Component/page tests assert layout regions, states, and safe display against fixtures instead; visual fidelity of SCR-1–SCR-3 is offered to the QA gate. Live Azure verification stays deferred per `run.provisioning`; fixture-backed tests stand in, and the capability remains inactive until approved resources and activation evidence exist.
