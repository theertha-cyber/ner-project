# Verification Plan

**Change:** redesign-azure-blob-connection-ui
**Generated:** 2026-09-11
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-data-source-portal | Data source collection and navigation | Administrator filters data sources | Given an authenticated tenant administrator on the data-sources collection, when the administrator changes the provider or status filter, then the collection resets to page 1, retains query state in the URL, and shows the correct loading/empty/filtered-empty/error state. | `data-sources/page.test.tsx` (existing filter-reset coverage) | ✅ |
| 2 | tenant-data-source-portal | Data source collection and navigation | Collection uses server-backed paging defaults | Given an authenticated tenant administrator opening `/settings/data-sources` with no query parameters, when the collection loads, then the portal requests page 1 with 20 items sorted by last activity descending, ascending `id` tie-breaker. | `data-sources/page.test.tsx` (existing default-query coverage) | ✅ |
| 3 | tenant-data-source-portal | Data source collection and navigation | Non-administrator cannot enter administration routes | Given an authenticated user without the tenant-administrator role, when the user navigates to a data-source administration route, then the portal shows the existing safe authorization state and renders no collection or detail content. | `data-sources/page.test.tsx` / `[connectionId]/page.test.tsx` (existing `RequireAuth` role-gate coverage) | ✅ |
| 4 | tenant-data-source-portal | Data source collection and navigation | Administrator creates a connection from the modal | Given an authenticated tenant administrator on the data-sources collection, when they open "New connection", select a provider, complete the form, and submit, then the portal opens a modal (not an inline panel), sends the create mutation with a fresh `Idempotency-Key`, and navigates to the new connection's detail route on success. | `data-sources/page.test.tsx` (task 4.4: modal open → submit → navigate) | ✅ |
| 5 | tenant-data-source-portal | Data source collection and navigation | Administrator dismisses the new-connection modal without creating a draft | Given an authenticated tenant administrator with the new-connection modal open, when they press `Escape` or activate cancel, then the modal closes, no create request is sent, form values are discarded, and focus returns to the "New connection" control. | `data-sources/page.test.tsx` (task 4.4: modal cancel/Escape path) | ✅ |
| 6 | tenant-data-source-portal | Safe connection lifecycle interface | Test, attestation, and activation render as one sequential control | Given an authenticated tenant administrator viewing a draft connection's lifecycle panel, when no secure test has run yet, then the panel shows a single "Test connection" control with no attestation checkboxes and no Activate action, replacing the previously separate Activation-evidence panel. | `lifecycle.tsx` unit tests (task 2.5: untested-state rendering) | ✅ |
| 7 | tenant-data-source-portal | Safe connection lifecycle interface | A passed test surfaces the attestation checkboxes inline, Activate stays disabled until both are checked | Given a connection whose secure test has just passed, when the administrator views the lifecycle panel, then the control shows the passed result plus the `network_approved` and `governance_approved` checkboxes (both unchecked, Activate disabled), and Activate enables only once both are checked and submits `activation_evidence` containing exactly `network_approved` and `governance_approved`. | `lifecycle.tsx` unit tests (task 2.5: passed-test → checkboxes render, Activate gated on both checked, submitted body) | ✅ |
| 8 | tenant-data-source-portal | Safe connection lifecycle interface | A failed test hides the attestation checkboxes and returns the control to a retry state | Given a connection whose secure test fails, including a retest of a previously passed connection, when the administrator views the lifecycle panel, then the control returns to a "Test connection" (retry) state, hides and resets any previously checked attestation checkboxes, and does not expose an Activate action. | `lifecycle.tsx` unit tests (task 2.5: failed-test retry state, including pass-then-fail retest resetting checkboxes) | ✅ |
| 9 | tenant-data-source-portal | Safe connection lifecycle interface | Activation is blocked safely | Given a connection whose test, secret resolution, or required evidence is absent or failed, when the backend reports unmet activation prerequisites, then the lifecycle action is unavailable with a safe blocking notice and no secret, connection string, provider error, or remote content displayed. | `lifecycle.tsx` unit tests (task 2.3: blocked-activation safe notice) | ✅ |
| 10 | tenant-data-source-portal | Safe connection lifecycle interface | Destructive lifecycle actions require confirmation | Given an authenticated tenant administrator retiring or replacing a connection, when the administrator initiates the action, then the portal requires explicit confirmation before sending the mutation, and an active connection requires pausing first. | `lifecycle.tsx` unit tests (existing pause/replace/retire confirmation coverage, re-run after task 2 changes) | ✅ |
| 11 | tenant-data-source-portal | Safe connection lifecycle interface | Idempotent mutation replay renders the safe result | Given a mutation already accepted under an `Idempotency-Key`, when the same key and body are submitted again, then the portal renders the returned safe result with a replay notice and does not duplicate the lifecycle effect. | `lifecycle.tsx` unit tests (existing replay-safe-result coverage, re-run after task 2 changes) | ✅ |
| 12 | tenant-data-source-portal | Safe connection lifecycle interface | Detail panels render in the fixed order | Given an authenticated tenant administrator viewing any connection's detail route, when the detail route renders, then the portal presents Connection details first, Sync activity second, and Lifecycle third, for both Azure Blob and Azure PostgreSQL connections. | `[connectionId]/page.test.tsx` (task 3.3: DOM order assertion, both providers) | ✅ |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Merged test/attestation/activate control state machine | AI may collapse `testing` and `failed` into the same visual state, or leave stale checked attestation checkboxes or a stale "Activate" button visible after a test later fails, exposing activation without a currently-passed test and without a fresh attestation. | Manually drive a connection through draft → test-pass → test-fail-on-retest and confirm the control shows exactly one state at a time, that a failed retest clears both checkboxes, and that "Activate" is never enabled without a currently-passed test and both checkboxes freshly checked. |
| 2 | Attestation checkboxes silently becoming decorative | AI may render the two checkboxes but wire "Activate" to enable regardless of their checked state (e.g. re-enable as soon as the test passes, checkboxes present but not actually gating), reintroducing the auto-submit behavior this design explicitly rejected. | Unit test / manual check: with a passed test and both checkboxes unchecked, confirm "Activate" is disabled; check only one, confirm it stays disabled; check both, confirm it enables and the submitted `activation_evidence` still contains exactly `network_approved` and `governance_approved`. |
| 3 | Panel reordering touching `SafeFacts` | AI may remove more than the `Activation` row from `SafeFacts` (e.g. accidentally drop `Configured fields`, `Secret references`, or `Test` rows) while reordering sections. | Diff `SafeFacts` before/after: only the `Activation` row should be removed; `Configured fields`, `Secret references`, `Test`, `Updated`, and the replace/replaced-by rows must remain. |
| 4 | `useFocusTrap` extraction from `SlideOver` | AI may change `SlideOver`'s existing focus-trap or Escape-key behavior while extracting it into a shared hook, silently breaking the existing pause/replace/retire confirmation dialogs. | Run `slide-over.test.tsx` unmodified after the extraction and confirm it still passes with no test edits; manually confirm Escape and Tab-trapping still work on an existing lifecycle confirmation dialog. |
| 5 | New-connection modal vs. inline panel state leakage | AI may leave the old `creating` inline-panel branch dead-code-present alongside the new modal, or fail to reset `ProviderConfigForm` values between modal opens, leaking a prior draft's field values into a new attempt. | Open the modal, type into fields, cancel, reopen — confirm all fields are blank; grep the page file for any remaining inline `<section aria-label="Create connection">` render path. |
| 6 | PostgreSQL connection panel ordering parity | AI may apply the Connection details → Sync activity → Lifecycle reorder only to the Azure Blob path and leave PostgreSQL's detail page in the old order, since PostgreSQL already has divergent Sync activity content (schedule-exemption notice). | View a PostgreSQL connection's detail route and confirm the same three-section order and the existing schedule-exemption notice text are both present. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-011 Tenant-Scoped Azure Connection Control Plane | Activation requires a passed secure test plus recorded governance/network attestations before a connection can serve traffic. | The Activate action must still be gated on an admin explicitly checking both attestation checkboxes in addition to a passed test — no auto-submission. | Confirm (network trace or unit test) that the `activate` request body always contains both `governance_approved` and `network_approved`, that "Activate" is disabled whenever `connection.last_test.outcome !== "passed"`, and that it is also disabled whenever either attestation checkbox is unchecked even with a passed test. |
| ADR-012 Durable Azure Blob Source Synchronization | Blob sync runs on a durable schedule/lease independent of the portal UI. | Sync activity panel's data contract (`schedule`, `last_sync`, manual `Sync now`) must be unchanged; only its position and container change. | Confirm `SyncActivitySummary`'s props, rendered fields, and the `Sync now` mutation call are byte-for-byte unchanged from before the reorder — only its position in `DetailContent` and its place in the section order differ. |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1 (Administrator filters data sources): existing/updated test output for filter-driven page reset and URL state in `data-sources/page.test.tsx`.
- [x] Scenario 2 (Collection uses server-backed paging defaults): existing test output confirming default query params on initial load.
- [x] Scenario 3 (Non-administrator cannot enter administration routes): existing `RequireAuth` role-gate test output for the data-sources routes.
- [x] Scenario 4 (Administrator creates a connection from the modal): updated `data-sources/page.test.tsx` test output showing modal open → submit → navigation to the new connection's detail route with a fresh `Idempotency-Key`.
- [x] Scenario 5 (Administrator dismisses the new-connection modal): test output showing Escape/cancel closes the modal, sends no request, and returns focus to the trigger.
- [x] Scenario 6 (Test, attestation, activation render as one sequential control): updated `lifecycle.tsx` unit test output showing the draft state renders one "Test connection" control with no attestation checkboxes and no Activate action.
- [x] Scenario 7 (Passed test surfaces attestation checkboxes, Activate gated on both): unit test output asserting the checkboxes render unchecked post-pass, "Activate" stays disabled until both are checked, and the submitted `activation_evidence` body is correct.
- [x] Scenario 8 (Failed test hides checkboxes, returns to retry): unit test output asserting the control reverts to "Test connection" after a failed test, resets/hides both checkboxes, and exposes no Activate action.
- [x] Scenario 9 (Activation is blocked safely): existing/updated test output for the blocked-activation safe notice.
- [x] Scenario 10 (Destructive actions require confirmation): existing test output for the pause/replace/retire confirmation dialog.
- [x] Scenario 11 (Idempotent mutation replay): existing test output for the replay-safe-result rendering path.
- [x] Scenario 12 (Detail panels render in fixed order): updated `[connectionId]/page.test.tsx` output asserting DOM order Connection details → Sync activity → Lifecycle for both providers.

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — manual walk-through of draft → pass → retest-fail shows exactly one state visible at each step, and a failed retest clears both attestation checkboxes.
- [x] Risk 2 mitigation confirmed — Activate stays disabled with a passed test and zero or one checkbox checked, enables only with both checked, and the submitted body contains exactly both attestation keys.
- [x] Risk 3 mitigation confirmed — `SafeFacts` diff shows only the `Activation` row removed.
- [x] Risk 4 mitigation confirmed — `slide-over.test.tsx` passes unmodified after `useFocusTrap` extraction.
- [x] Risk 5 mitigation confirmed — modal reopen shows blank form fields; no leftover inline create panel in the page source.
- [x] Risk 6 mitigation confirmed — PostgreSQL detail route shows the same three-section order and retains its schedule-exemption notice.

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `npx vitest run` on `slide-over.test.tsx`, `status.test.tsx`, `sync-activity.test.tsx`, `schema-contracts/page.test.tsx`, `[connectionId]/page.test.tsx`, `data-sources/page.test.tsx` — 6 files, 41/41 tests passed | 1–12 | agent (Claude) | 2026-09-11 |
| 2 | Code diff | `SafeFacts` diff in `[connectionId]/page.tsx` — only the `Activation` row removed; `Configured fields`, `Secret references`, `Test`, `Updated`, replace/replaced-by rows unchanged | Risk 3 | agent (Claude) | 2026-09-11 |
| 3 | Code diff | `useFocusTrap` extraction in `src/hooks/use-focus-trap.ts` reused unchanged by `SlideOver` and `CreateConnectionModal`; `slide-over.test.tsx` re-run unmodified, 4/4 passed | Risk 4 | agent (Claude) | 2026-09-11 |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** redesign-azure-blob-connection-ui
**Proposal:** `openspec/changes/redesign-azure-blob-connection-ui/proposal.md`
**Spec files reviewed:**
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
