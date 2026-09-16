# Verification Plan

**Change:** automated-landing-start-step-below-prereqs
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Both upload entry points are visible before step 1 | src/portal/.../annotate/automated/page.test.tsx::"shows upload entry points before step 1..." (pre-existing, unmodified) | [x] |
| 2 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Upload documents opens the uploader pre-set to Automated | Same test (pre-existing, unmodified) | [x] |
| 3 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Upload Q&A pair opens the Q&A-pair uploader | Same test (pre-existing, unmodified) | [x] |
| 4 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | The primary "Start with step 1" action is unchanged | src/portal/.../annotate/automated/page.test.tsx::"still routes to step 1 from the primary action" (navigation) + ::"places 'Start with step 1' after the 'Before you begin' cards, not beside the heading" (position) | [x] |

Supporting, capability-agnostic coverage: `AnnotateLanding.test.tsx` (3 tests) verifies the
shared component's `primaryActionPosition` prop itself — default placement, explicit
`belowWorkCards` placement (via DOM order), and that the disabled/disabledReason rendering
still works at either position. This underlies row 4 but isn't itself a spec-named scenario.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Changing the default for every landing page | Could have changed `AnnotateLanding`'s existing behavior in place instead of adding an opt-in prop, silently repositioning Manual's "＋ Assign task" and Import's "＋ Import file" too | The new prop defaults to `"top"`, the exact prior unconditional behavior; Manual's and Import's page files pass no `primaryActionPosition` and were rerun unmodified to confirm no visible change |
| 2 | Position asserted by text presence alone | A test could assert the button text exists without confirming it actually moved, silently passing even if the button were still rendered at the top | Used `compareDocumentPosition` against the "Before you begin"/"Your workflow" heading rather than a presence-only assertion, in both the generic component test and the real page test |

---

## 3. Pattern & ADR Compliance

- No backend or ADR-governed behavior changed — purely a layout/positioning change to one
  shared frontend component and one page's use of it.

---

## 4. Evidence Log

- **Frontend — tests:** `AnnotateLanding.test.tsx` (3 tests, new),
  `annotate/automated/page.test.tsx` (4 tests, +1 new) — all passed, alongside reruns of
  `annotate/manual/page.test.tsx` (6 tests) and `annotate/import/page.test.tsx` (5 tests) to
  confirm the default `"top"` position is unaffected for those two pages.
- **Full regression sweep:** full portal suite — 112/118 files passed (786/796 tests), matching
  exactly the pre-existing 6-file baseline with no new regressions.
- **Docker:** rebuilt and restarted the `portal` container.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), navigated to
  `/annotate/automated` — confirmed "Start with step 1" now renders directly below the "Before
  you begin" cards (screenshot captured), and clicking it still navigates to
  `/annotate/automated/schema`.

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
