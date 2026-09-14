# Verification Plan

**Change:** manual-annotation-notification-routes-to-training
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | notifications | Notification Bell | Unread badge reflects the unread count | (pre-existing, unmodified — no dedicated test found in this repo for this exact scenario; the bell's badge rendering itself was not touched by this change) | [x] |
| 2 | notifications | Notification Bell | The bell is absent for a business user | (pre-existing, unmodified — this change does not touch role-gating of the bell itself) | [x] |
| 3 | notifications | Notification Bell | A completed manual annotation task notification routes to Models & Training scoped to manual | src/portal/.../NotificationBell.test.tsx::"routes a completed manual annotation task notification to Models & Training scoped to manual" | [x] |
| 4 | notifications | Notification Bell | An automated batch notification routes a tenant_admin to the retraining evidence page | src/portal/.../NotificationBell.test.tsx::"routes an automated batch notification to the retrain page for a tenant_admin" | [x] |
| 5 | notifications | Notification Bell | An automated batch notification routes an annotator to that batch's review screen | src/portal/.../NotificationBell.test.tsx::"routes an automated batch notification to the batch review for an annotator" | [x] |

Rows 1–2 predate this change and were not independently re-verified by a new test run here;
they are unaffected by the `hrefFor` fix, which only changes navigation targets, not the bell's
badge count or role visibility.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Assuming the bug was isolated to one branch | Could have "fixed" `annotation_task` without checking whether `prelabel_batch`'s routes were also stale copy-paste artifacts | Traced `prelabel_batch`'s notification to its actual creation site (`worker.py`'s raw SQL insert on automated large-batch auto-promotion) and confirmed routing an automated-batch outcome to the retraining/promotion evidence page is a reasonable, intentional destination — distinct from the manual-annotation-task case, which had no such backing rationale and pointed at an unrelated flow entirely |
| 2 | Silently also changing the automated route | Given this session's earlier work also touched Automated's "Train model" hand-off (now `/training-jobs?source=automated` from `BatchAcceptancePage`), it would be easy to assume `prelabel_batch`'s notification route should change too | Left unchanged, since the user's request was specific to Manual ("from manual the train model button should redirect to model training") — not requested here, and changing it without being asked would be scope creep on an already-narrow fix |

---

## 3. Pattern & ADR Compliance

- No backend or ADR-governed behavior changed — purely a one-line frontend routing correction.

---

## 4. Evidence Log

- **Frontend — tests:** `NotificationBell.test.tsx` (4 tests, new) — all passed against the
  `ner-portal-test` container.
- **Full regression sweep:** full portal suite — 113/119 files passed (790/800 tests), matching
  exactly the pre-existing 6-file baseline with no new regressions.
- **Docker:** rebuilt and restarted the `portal` container.
- **Live verification:** not performed end-to-end this session (see tasks.md § 3.4 — no seeded
  notification of this kind exists in the current demo tenant to click through). The fix is a
  single conditional's return value, directly asserted by the new unit test.

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suite above independently.
- [ ] Human reviewer has, where practical, completed a real manual annotation task end-to-end
  and confirmed the resulting notification routes to `/training-jobs?source=manual`.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
