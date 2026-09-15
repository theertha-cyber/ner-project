## 1. Navigation and data layer

- [x] 1.1 Add the tenant-admin `Data Sources` entry (`/settings/data-sources`) to `navFor` in `src/portal/src/lib/nav-config.ts` plus the `SCREEN_TITLES` key, reusing an existing icon; extend `nav-config.test.ts` for the new entry and role scoping.
- [x] 1.2 Create `src/portal/src/lib/data-sources.ts` with safe-only TypeScript types (`Connection`, `ConnectionPage`, outcome classes, reason codes), the allowlisted query builder (defaults: page 1, 20 items, `last_activity` desc + `id` asc), and `Idempotency-Key` generation; unit-test the builder defaults, bounds, and page-1 reset.
- [x] 1.3 Add data-source hooks (collection with URL-backed search/filter/sort/page, detail, mutations with idempotency headers, contract history/upload) over `authFetch` relative URLs; unit-test with fakes including replay, 409/400, and finite error codes.

## 2. SCR-1 collection screen

- [x] 2.1 Build `/settings/data-sources` page with CMP-2/CMP-4/CMP-5 from `components/ui` primitives and the new `components/data-sources` folder, styled through the installed tokens; covers loading, empty, filtered-empty, safe error, and labelled statuses.
- [x] 2.2 Add SCR-1 page/component tests: filter reset to page 1 with URL state (row 1), default paging query (row 2), out-of-range empty page, unknown-field rejection handling, keyboard-operable rows, and hostile-payload safe display.

## 3. SCR-2 lifecycle screen

- [x] 3.1 Build `/settings/data-sources/[connectionId]` page with CMP-6 closed-schema forms (Blob vs. PostgreSQL incl. `sslmode: verify-full`), CMP-7 lifecycle panel with evidence checklist and `slide-over` confirmations, CMP-8 safe notices, and CMP-9 sync summary (Blob schedule; PostgreSQL omits schedule/`last_sync`).
- [x] 3.2 Add SCR-2 tests: blocked activation safe notice (row 4), confirmation + pause-before-retire (row 5), idempotent replay and 409/400 notices (row 6), write-only values, and closed-schema submit payloads.

## 4. SCR-3 contract screen

- [x] 4.1 Build `/settings/data-sources/[connectionId]/schema-contracts` page with CMP-10 (JSON picker, validation results, publish control, version-history table at 20 per page, published-at desc, version search with page-1 reset) and drift-blocked state cross-linked to detail.
- [x] 4.2 Add SCR-3 tests: invalid JSON and semantic failures with linked field-level errors and recoverable form (row 7), drift-blocked state (row 8), and no-rows/no-SQL assertions.

## 5. Access control and contract compliance

- [x] 5.1 Add route/authz tests: unauthenticated redirect to `/login`, non-admin safe authorization state with no content (row 3), and tenant-from-auth-only (no tenant parameter in requests).
- [x] 5.2 Run `python3 incode-opencode/skills/ui-lint/scripts/ui_lint.py src/portal/src --tokens src/portal/design-system/ner-portal/tokens.css --include-p1` and fix every P0; record counts against the CAP-5 state entry.

## 6. Verification & Evidence

- [x] 6.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 6.2 Collect functional evidence (screenshot / test output / log) for each scenario — one entry per row in verification.md § Evidence Log.
- [x] 6.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 6.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 6.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required).
- [x] 6.6 Run `openspec validate cap-5-tenant-data-source-administration-portal --strict` and fix whatever it reports.
