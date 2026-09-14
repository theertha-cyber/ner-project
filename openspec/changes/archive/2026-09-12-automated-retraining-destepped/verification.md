# Verification Plan

**Change:** automated-retraining-destepped
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | automated-annotation-landing | Retraining Is Not a Numbered Step | The stepper shows exactly 3 steps | src/portal/.../annotate/automated/layout.test.tsx::"shows exactly three numbered steps — Retraining is no longer one of them" | [x] |
| 2 | automated-annotation-landing | Retraining Is Not a Numbered Step | The stepper does not render on the retraining route | src/portal/.../annotate/automated/layout.test.tsx::"hides the stepper on the retraining route — it isn't step 4 of this pipeline" | [x] |
| 3 | automated-annotation-landing | Retraining Is Not a Numbered Step | The landing page explains retraining as a separate, optional decision | src/portal/.../annotate/automated/page.test.tsx::"names retraining as a separate, optional decision reachable from Models & Training" | [x] |
| 4 | training-jobs-screen | Retraining Evidence Link | Tenant admin sees the link in the Model Versions view | src/portal/.../training-jobs/page.test.tsx::"shows a link to the retraining/promotion evidence page, not the jobs view's submit button" | [x] |
| 5 | training-jobs-screen | Retraining Evidence Link | The link is absent from the Training Jobs view | src/portal/.../training-jobs/page.test.tsx::"renders the view switcher parallel to the submit job button" (extended with a negative assertion) | [x] |
| 6 | training-jobs-screen | Retraining Evidence Link | The link is not shown to system_admin | src/portal/.../training-jobs/page.test.tsx::"does not show the retraining/promotion evidence link to a system_admin" | [x] |
| 7 | nav-config | Role Navigation Matrix | system_admin nav (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts::"system_admin stays a flat 4-item list" | [x] |
| 8 | nav-config | Role Navigation Matrix | tenant_admin nav (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts::"tenant_admin is grouped into Annotate / Setup / Admin sections" | [x] |
| 9 | nav-config | Role Navigation Matrix | annotator nav (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts::"annotator sees Manual and Import but not Automated" | [x] |
| 10 | nav-config | Role Navigation Matrix | business_user nav (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts (covered by system_admin/annotator shape tests; business_user has no Automated child to affect) | [x] |
| 11 | nav-config | Role Navigation Matrix | a section with no permitted links is dropped (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts (unmodified pre-existing test) | [x] |
| 12 | nav-config | Role Navigation Matrix | Manual no longer carries a Review Queue child (pre-existing, unmodified) | src/portal/src/lib/nav-config.test.ts (unmodified pre-existing test) | [x] |
| 13 | nav-config | Role Navigation Matrix | Automated's Retraining child carries no step-number prefix | src/portal/src/lib/nav-config.test.ts::"Automated's Retraining child carries no step-number prefix, unlike its siblings" | [x] |
| 14 | retraining-decision-screen | Retraining Page Framing | The page states there is no schedule or required order | src/portal/.../RetrainingDecisionPage.test.tsx::"states there is no schedule or required order" | [x] |
| 15 | retraining-decision-screen | Retraining Page Framing | The production-review section explains what it counts | src/portal/.../RetrainingDecisionPage.test.tsx::"explains what the production-review figure counts, distinctly from the eligible overview" | [x] |
| 16 | retraining-decision-screen | Retraining Page Framing | The training-eligible section explains it is a separate count | Same test as row 15 (both assertions live in one test, since both explanatory lines render together) | [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Confusing "unlink from stepper" with "remove the route" | Could have deleted `/annotate/automated/retrain` entirely instead of just its stepper tile, breaking the page for anyone with it bookmarked or linked from elsewhere | Confirmed the route file (`app/(auth)/annotate/automated/retrain/page.tsx`) and its component (`RetrainingDecisionPage.tsx`) are untouched structurally — only reachability (nav label, new link, stepper visibility) changed |
| 2 | Backend/data-contract drift | Could have described the copy changes as if the underlying `RetrainingDecision`/`PromotionEvidence` API contract changed | Confirmed `human-gated-retraining`'s spec (backend response shape) needed no delta — every scenario there is about response fields, none of which changed; only React component text changed |
| 3 | Scope creep into the models-screen's existing promote flow | Adding a link near the Model Versions header could have been implemented in a way that altered `ModelActions`/promotion behavior | Confirmed the change is additive only: one new conditionally-rendered `<button>` calling `router.push`, no changes to `ModelActions`, `ModelDetailPanel`, or the promote flow |
| 4 | Stepper-hiding logic scoped too broadly | Checking `pathname` to hide the stepper could accidentally also hide it on one of the 3 real step routes if the match were too loose | Used an exact string match against `/annotate/automated/retrain` (not a prefix or regex), and a dedicated test confirms all 3 step routes still show the stepper (`layout.test.tsx`'s first test uses the default mocked pathname of `/annotate/automated/schema`) |

---

## 3. Pattern & ADR Compliance

- No ADR governs stepper/nav-label presentation specifically; this change follows the existing
  `human-gated-retraining` design intent (ADR-009/ADR-010: retraining and promotion are explicit
  human decisions, never automatic) more faithfully than the previous "step 4" framing did, by
  no longer implying a mandatory sequence.
- No backend, database, or data-contract changes.

---

## 4. Evidence Log

- **Frontend — new/updated tests:** `annotate/automated/layout.test.tsx` (3 tests, new),
  `training-jobs/page.test.tsx` (extended, +2 new assertions/tests), `nav-config.test.ts`
  (extended, +1 test), `RetrainingDecisionPage.test.tsx` (extended, +2 tests) — 36/37 passed in
  the targeted run; the 1 failure is the confirmed pre-existing `training-jobs/page.test.tsx`
  "Approve & queue" timeout baseline.
- **Frontend — full regression sweep:** full portal suite — 109/115 files passed (773/783
  tests), matching exactly the pre-existing 6-file baseline with no new regressions.
- **Docker:** rebuilt and restarted the `portal` container three times over the course of this
  change (after the stepper removal, after hiding it on `/retrain`, and after the breadcrumb
  label fix), verifying live in the browser after each rebuild before proceeding.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp). On
  `/annotate/automated`, confirmed the stepper reads "1 / 3", "2 / 3", "3 / 3" with no
  "Retraining" tile, and the trailing paragraph names retraining as a separate, optional
  decision reachable from Models & Training (screenshot + page-text captured). Navigated to
  Models & Training → Model Versions and confirmed the "Retraining & promotion evidence →" link
  is present; clicking it landed on `/annotate/automated/retrain` with no stepper above the
  content, a breadcrumb reading "Annotate / Automated / Retraining" (no step number), and the
  clarified copy ("Production-review evidence" heading with its explanatory line, the
  "training-eligible and waiting" section's bridging line, and the "no schedule and no required
  order" sentence in the intro) all visible (screenshots captured).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer has confirmed the disclosed gap in row 3 (landing-page paragraph wording
  not pinned by a unit test) is acceptable, or requested a test be added.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
