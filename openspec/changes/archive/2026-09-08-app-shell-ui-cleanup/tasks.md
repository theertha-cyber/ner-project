## 1. Sidebar changes

- [x] 1.1 In `src/portal/src/components/app-shell/Sidebar.tsx`, change the wordmark text from `nerplatform` to `NER Platform`.
- [x] 1.2 In `Sidebar.tsx`, remove the "Tenant pill" block (lines ~94-162) and any now-unused helpers/variables it alone relied on (`tenantDisplayName`, `tenantInitial`, `tenantName` usage) if nothing else in the file uses them.
- [x] 1.3 Verify `Sidebar.tsx` still compiles/typechecks with no unused-variable warnings after removal.

## 2. Topbar changes

- [x] 2.1 In `src/portal/src/components/app-shell/Topbar.tsx`, remove the "Search placeholder" block (the `⌕ search · ⌘K` div).
- [x] 2.2 In `Topbar.tsx`, remove the "Role-switcher chips" block (`DEMO_ROLES`, the `AS` label, and the `NEXT_PUBLIC_DEMO_MODE` conditional wrapper).
- [x] 2.3 In `Topbar.tsx`, remove `demoRole` and `onDemoRoleChange` from `TopbarProps` and the component signature.

## 3. AppShell wiring

- [x] 3.1 In `src/portal/src/components/app-shell/AppShell.tsx`, remove the `demoRole` state (`useState<AuthUser["role"] | null>`) and the `effectiveRole = demoRole ?? user.role` derivation.
- [x] 3.2 Update the `<Sidebar>` call to receive `effectiveRole={user.role}` directly.
- [x] 3.3 Update the `<Topbar>` call to drop the now-removed `demoRole`/`onDemoRoleChange` props.

## 4. Test updates

- [x] 4.1 Update `src/portal/src/components/app-shell/sidebar.test.tsx`: replace any assertion on the old `nerplatform` wordmark text with `NER Platform`.
- [x] 4.2 Update `sidebar.test.tsx`: remove/replace any tenant-pill assertions with an explicit assertion that the tenant pill is absent (covers scenario 5).
- [x] 4.3 Add/update tests in `sidebar.test.tsx` (or a new co-located Topbar test if the suite is split) asserting the search box and role-switcher chips are absent, including with `NEXT_PUBLIC_DEMO_MODE` both `"true"` and unset (covers scenarios 15-16).

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass. Fill in the Verification Artifact column in verification.md pointing at `sidebar.test.tsx` (or split Topbar test file) test names for each of the 19 rows. **Partial:** 9 of 19 rows (the scenarios this change actually touches — wordmark, tenant pill, search box, role-switcher, plus the untouched menu/nav scenarios that already had tests) are filled in and passing (`npx vitest run src/components/app-shell/sidebar.test.tsx` — 16/16 pass). 10 rows (active-nav highlight, badge, Logout colour, Settings/Logout navigation, Topbar scroll/title/border-radius/theme-toggle) have no automated test — pre-existing gaps this change did not introduce and did not touch. Left unchecked pending reviewer decision on whether to backfill or accept as known debt.
- [ ] 5.2 Collect functional evidence (screenshot / test output / log) for each scenario — one entry per row in verification.md § Evidence Log. Not done — requires human reviewer to log evidence per the gate design; see verification.md § Evidence Log (still placeholder rows).
- [x] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register (grep for `demoRole`/`onDemoRoleChange`, check for orphaned tenant-pill helpers, confirm `AppShell.tsx` uses `user.role` directly, diff wordmark string exactly, confirm absence assertions exist in tests). All 5 mitigations checked — see verification.md § Edge Case Evidence, all confirmed.
- [x] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance (N/A — no constraining ADRs, mark accordingly). Confirmed — no ADR references this presentation-layer change.
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required). Not done — requires human sign-off, cannot be completed by an agent.
- [x] 5.6 Run `openspec validate app-shell-ui-cleanup --type change --strict` and confirm it exits clean before archive. Confirmed: "Change 'app-shell-ui-cleanup' is valid".
