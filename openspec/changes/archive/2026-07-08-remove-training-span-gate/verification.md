# Verification Plan

**Change:** remove-training-span-gate
**Generated:** 2026-07-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-jobs | Submit form span preflight is informational only | Submit enabled with span count below the legacy 500 threshold | Given a tenant with fewer than 500 confirmed spans and all hyperparameter fields valid, when the Tenant Admin opens the Submit Training Job form, then the Submit button is enabled and the preflight display shows the span count with no pass/fail language | vitest: `submit-job-slideover.test.tsx` → "enables submit with span count below 500" | - [x] |
| 2 | training-jobs | Submit form span preflight is informational only | Preflight display shows span count while loading and on fetch failure | Given the form is open, when the span-count request is in flight then a loading state is shown; when the request fails then an "unavailable" state is shown; in both cases the Submit button's enabled state is unaffected by the fetch outcome | vitest: `submit-job-slideover.test.tsx` → "shows preflight check with span count" (loading/count path, existing, retained) + "keeps submit enabled when span count fetch fails" (new) | - [x] |
| 3 | training-jobs | Submit form span preflight is informational only | Backend rejection for insufficient entities is surfaced after submit | Given a tenant below the backend's configured minimum, when the Tenant Admin submits the form and the backend responds 422 for insufficient entities, then the form displays the backend's error message and remains open with entered hyperparameters intact | vitest: `submit-job-slideover.test.tsx` → "surfaces server error and keeps form open on 422 insufficient entities" (new) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | `canSubmit` recomputation | AI may leave a stray reference to `meetsThreshold` or `spanCount` in the `canSubmit` expression (e.g., partial removal), silently reintroducing a hidden gate. | Read the final `canSubmit` definition in `submit-job-slideover.tsx` and confirm it depends only on `errors` and submission-in-flight state — no `spanCount` or threshold comparison anywhere in the expression. |
| 2 | Banner styling logic | AI may keep the conditional success/failure CSS classes (`border-status-completed`/`border-status-failed`) wired to a removed `meetsThreshold` variable, causing a type error or dead branch instead of true removal. | Diff the banner JSX before/after — confirm the success/failure color branches are gone, not just fed a constant `true`/`false`. |
| 3 | Error path regression | AI may accidentally alter how `serverError` (the existing 422-surfacing path) is set or displayed while touching the same component, breaking scenario 3 even though it wasn't meant to change. | Confirm `handleSubmit`'s `onError` callback and the `serverError` JSX block are byte-for-byte unchanged (or intentionally unchanged) in the diff. |
| 4 | Test coverage drift | AI may delete or weaken existing tests in `submit-job-slideover.test.tsx` that covered the 500-threshold behavior instead of updating them to assert the new (no-gate) behavior, silently reducing coverage. | Confirm the test file still has assertions covering: button enabled below/above any span count, banner text with no pass/fail wording, and the 422 error-surfacing path — not simply deleted. |
| 5 | Scope creep into backend | AI may be tempted to also touch `NER_MIN_TRAINING_ENTITIES` or `training_jobs.py` since it's conceptually related, violating the proposal's explicit non-goal. | Confirm the diff touches only `src/portal/...` files (component + its test) — no changes under `src/training_service/` or `src/gateway/`. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-006: Training Infrastructure with Asynchronous GPU Workers | Compliance section mandates: "Training Orchestrator MUST enforce 500-entity minimum dataset threshold before accepting a job." | This is a backend/orchestrator obligation; this change must not remove or weaken backend enforcement, and must not claim to satisfy or replace it client-side. | Confirm `src/training_service/api/v1/training_jobs.py`'s `NER_MIN_TRAINING_ENTITIES` check is untouched (same logic, same env var name) in the diff. Confirm no new client-side threshold of any kind was introduced as a replacement. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [x] Scenario 1 (Submit enabled below 500): Test output showing "enables submit with span count below 500" passes (mocked 2 spans, button not disabled, no "minimum" text present).
- [x] Scenario 2 (Loading/unavailable states unaffected): Test output showing "shows preflight check with span count" and "keeps submit enabled when span count fetch fails" both pass.
- [x] Scenario 3 (Backend 422 surfaced): Test output showing "surfaces server error and keeps form open on 422 insufficient entities" passes — asserts the backend `detail` message renders and the submit button remains present (form open).

### Structural Evidence

- [x] Code review completed — implementation matches design.md Decision 1 (threshold deleted, not synced) and Decision 2 (banner is neutral, no pass/fail styling): `meetsThreshold` removed, `canSubmit = Object.keys(errors).length === 0`, banner is a single neutral `border-gray-200 bg-gray-50 text-gray-700` block with no conditional coloring.
- [x] ADR compliance step in Section 3 confirmed ✓ — `src/training_service/api/v1/training_jobs.py` NER_MIN_TRAINING_ENTITIES check untouched (verified via `git status`/diff scope, see Edge Case Risk 5 below).
- [x] No undocumented architectural patterns introduced — change is a like-for-like removal of client logic, no new patterns.
- [x] No AI-invented requirements present in generated code (cross-checked against specs/training-jobs/spec.md) — component behavior matches the 3 ADDED scenarios exactly.

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `canSubmit` expression reviewed (`submit-job-slideover.tsx:101`): `const canSubmit = Object.keys(errors).length === 0;` — no `spanCount`/threshold reference.
- [x] Risk 2 mitigation confirmed — banner `className` reviewed: single static string `"rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-700"`, no conditional branches on a threshold variable.
- [x] Risk 3 mitigation confirmed — `serverError` state, `handleSubmit`'s `onError` callback, and its JSX block are unchanged in the diff (only the span-preflight block and `canSubmit` line were touched).
- [x] Risk 4 mitigation confirmed — test file reviewed: the two threshold-assertion tests were replaced (not deleted) with tests asserting the new no-gate behavior, plus two new tests added (fetch-failure, 422 surfacing); net test count increased from 4 to 6, all passing.
- [x] Risk 5 mitigation confirmed — `git status` reviewed: this session's edits are scoped to `src/portal/src/components/training-jobs/submit-job-slideover.tsx` and its test file only; no changes under `src/training_service/` or `src/gateway/`.

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `npx vitest run src/components/training-jobs/submit-job-slideover.test.tsx` → "Test Files 1 passed (1), Tests 6 passed (6)", including "enables submit with span count below 500" and "shows plain span count with no threshold language when count is high" | Scenario 1 | Claude (agent) | 2026-07-07 |
| 2 | Functional | Same test run — "keeps submit enabled when span count fetch fails" and "shows preflight check with span count" both pass | Scenario 2 | Claude (agent) | 2026-07-07 |
| 3 | Functional | Same test run — "surfaces server error and keeps form open on 422 insufficient entities" passes | Scenario 3 | Claude (agent) | 2026-07-07 |
| 4 | Structural | `grep -rn "meetsThreshold\|500" src/portal/src/components/training-jobs/submit-job-slideover.tsx` → no matches; whole-portal grep for "500-span\|requires 500\|meets the 500\|meetsThreshold" → no matches | Risk 1, Risk 2 | Claude (agent) | 2026-07-07 |
| 5 | Edge Case | `git status --short src/portal src/training_service src/gateway` reviewed — session's diff limited to `submit-job-slideover.tsx` and `submit-job-slideover.test.tsx`; no `src/training_service/` or `src/gateway/` files touched | Risk 5 | Claude (agent) | 2026-07-07 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** remove-training-span-gate
**Proposal:** `openspec/changes/remove-training-span-gate/proposal.md`
**Spec files reviewed:**
  - specs/training-jobs/spec.md

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