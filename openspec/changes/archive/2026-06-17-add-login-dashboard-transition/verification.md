# Verification Plan

**Change:** add-login-dashboard-transition
**Generated:** 2026-06-17
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | login-dashboard-transition | Orb-burst overlay on successful sign-in | Successful login triggers burst | Given the user is on the login page, when they submit valid credentials and login succeeds, then a full-screen gradient overlay expands from the right-centre of the viewport and covers all content within 600 ms | Manual browser test / visual inspection | - [ ] |
| 2 | login-dashboard-transition | Orb-burst overlay on successful sign-in | Navigation deferred until burst ends | Given the burst overlay has started, when the overlay `animationend` event fires, then the browser navigates to `/dashboard` (navigation does NOT happen before animation completes) | Manual browser test: observe URL change only after burst covers screen | - [ ] |
| 3 | login-dashboard-transition | Orb-burst overlay on successful sign-in | Failed login shows no burst | Given the user submits invalid credentials, when the error is displayed, then no burst overlay is rendered and the login form remains interactive | Manual test with wrong password / unit test asserting `isTransitioning` stays false on error | - [ ] |
| 4 | login-dashboard-transition | Orb-burst overlay on successful sign-in | Login form unchanged during burst | Given the burst overlay has started, when the overlay is covering the screen, then the login form and AnimatedBackground remain in the DOM beneath the overlay | DevTools DOM inspection during burst; overlay has higher z-index than form card | - [ ] |
| 5 | login-dashboard-transition | Dashboard fade-in on entry | Dashboard fades in after burst | Given burst animation ends and navigation fires, when the `(auth)` layout mounts, then dashboard content fades from transparent to fully opaque over 400 ms | Visual inspection in browser | - [ ] |
| 6 | login-dashboard-transition | Dashboard fade-in on entry | Fade-in keyframe defined in global CSS | Given the project's `globals.css` file, when inspected, then a `@keyframes dashFadeIn` rule exists transitioning opacity from 0 to 1 | `grep -n "dashFadeIn" src/portal/src/app/globals.css` returns a match | - [ ] |
| 7 | login-dashboard-transition | No regression to login page behaviour | Login page looks identical before submit | Given the login page is loaded, when no submit action has been taken, then the page renders identically to its pre-transition state | Visual regression: side-by-side with pre-change screenshot | - [ ] |
| 8 | login-dashboard-transition | No regression to login page behaviour | Error state remains functional | Given a failed login attempt has displayed an error, when the user corrects credentials and resubmits, then the form processes normally and burst fires only on success | Manual test: fail then succeed | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Animation timing — `animationend` vs `setTimeout` | AI may revert to a hardcoded `setTimeout(navigate, 550)` instead of the `animationend` event handler, causing the navigation to fire before or after the animation visually ends | Inspect `handleSubmit` in `login/page.tsx` — confirm `router.replace` is called from an `onAnimationEnd` prop on the overlay `<div>`, not from a `setTimeout` |
| 2 | Burst origin coordinates | AI may use `50% 50%` (viewport centre) instead of the specified `75% 50%` (right-centre where the card sits), making the burst feel disconnected from the form | Inspect the `clip-path` start value in the CSS keyframe or inline style — confirm it reads `circle(0% at 75% 50%)` expanding to `circle(150% at 75% 50%)` |
| 3 | Form mutation on transition | AI may hide or unmount form components during the burst, breaking DOM integrity and potentially resetting state if the user navigates back | Check DOM during burst (DevTools) — form inputs, AnimatedBackground orbs, and card must still be present in the tree; only the overlay `<div>` is newly added |
| 4 | `isTransitioning` triggered on failed login | AI may set `isTransitioning = true` optimistically before awaiting the login response, causing a burst on error paths | Read `handleSubmit` — `setIsTransitioning(true)` must only be called inside the `try` block after `await login(...)` resolves without throwing |
| 5 | Dashboard layout fade scope | AI may apply `dashFadeIn` only to the dashboard page component rather than the `(auth)` layout wrapper, making the animation fire inconsistently on sub-page navigations | Check `src/portal/src/app/(auth)/layout.tsx` — the outermost element must carry the `animation: dashFadeIn 0.4s ease both` style, not any individual page component |
| 6 | Missing `@keyframes orbBurst` in `globals.css` | AI may define the burst animation as an inline `<style>` tag within `login/page.tsx` rather than adding it to `globals.css` alongside existing keyframes | Confirm `orbBurst` keyframe is in `globals.css`; login page should reference it by name only, not redefine it |

---

## 3. Pattern & ADR Compliance

No currently-in-force ADRs constrain this purely frontend CSS transition change (confirmed in design.md — ADR-004 and ADR-005 impose no constraints on UI animation implementation).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-004-openspec-governance | Planning artifacts live in `openspec/` | Planning artifacts must be created; implementation edits are in `src/` | Confirm all change artifacts exist in `openspec/changes/add-login-dashboard-transition/`; implementation edits are in `src/portal/src/` |
| ADR-005-opencode-agent-boundaries | Agent implementation scope rules | Implementation must be scoped to repo-local files | Confirm no files outside `C:\Users\Theertha\Documents\ner-project` were modified |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Scenario 1: Screen recording or description showing the burst overlay expands from the right-centre of the viewport within 600 ms of successful sign-in
- [ ] Scenario 2: Observation (screen recording or description) that the URL bar changes to `/dashboard` only after the burst has fully covered the screen
- [ ] Scenario 3: Test or manual observation confirming no burst overlay appears when login returns an error
- [ ] Scenario 4: DevTools screenshot or description showing the login form's DOM nodes remain present beneath the overlay during the burst
- [ ] Scenario 5: Visual observation that the dashboard content fades in from transparent after the burst
- [ ] Scenario 6: Terminal output of `grep -n "dashFadeIn" src/portal/src/app/globals.css` showing a match
- [ ] Scenario 7: Side-by-side visual comparison confirming the login page appearance is unchanged before any submit action
- [ ] Scenario 8: Manual test walkthrough: fail login → see error → correct credentials → burst fires → navigate to dashboard

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 confirmed: `router.replace` is called from `onAnimationEnd`, not `setTimeout`
- [ ] Risk 2 confirmed: burst origin is `75% 50%` in the CSS keyframe
- [ ] Risk 3 confirmed: form DOM nodes remain present during burst (DevTools check)
- [ ] Risk 4 confirmed: `setIsTransitioning(true)` only reachable on successful `await login()`
- [ ] Risk 5 confirmed: `dashFadeIn` is on the `(auth)/layout.tsx` root wrapper, not on a page component
- [ ] Risk 6 confirmed: `orbBurst` keyframe is defined in `globals.css`, not inlined in `login/page.tsx`

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | | | | |
| 2 | Functional | | | | |
| 3 | Functional | | | | |
| 4 | Structural | | | | |
| 5 | Edge Case | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** add-login-dashboard-transition
**Proposal:** `openspec/changes/add-login-dashboard-transition/proposal.md`
**Spec files reviewed:**
- specs/login-dashboard-transition/spec.md

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
