# Verification Plan

**Change:** import-workflow-direct-to-training
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | import-annotation-landing | Workflow Steps | tenant_admin sees the two-step workflow in order | src/portal/.../annotate/import/page.test.tsx::"tenant_admin sees the two-step workflow — import, then train — in order" | [x] |
| 2 | import-annotation-landing | Workflow Steps | annotator sees only a single review card | src/portal/.../annotate/import/page.test.tsx::"annotator sees only a single review card, not the two-step workflow" | [x] |
| 3 | import-annotation-landing | Workflow Steps | Train model is available with nothing imported yet | src/portal/.../annotate/import/page.test.tsx::"step 2 is available even with nothing imported yet — no eligibility gate" | [x] |

Two supporting tests not tied to a named scenario: "step 1 routes to the import file picker"
and "step 2 routes straight to Models & Training scoped to import, with no review gate" —
both are covered by scenario 1's navigation assertions but kept as separate tests for a
clearer failure signal if either link regresses independently.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Silently keeping the eligibility gate | Could have kept `annotatedCount === 0` gating logic and just relabelled the banner as a "step", which would still hide "Train model" when nothing is imported — contradicting the direct instruction that there's no review/eligibility step in between | Confirmed the new "2. Train model" card is a plain `WorkCard` entry (same unconditional rendering as "1. Import annotations"), not wrapped in any eligibility check; a dedicated test (`"step 2 is available even with nothing imported yet"`) asserts it renders with `mockFiles = []` |
| 2 | Leaving dead code in `TrainModelBanner` | The `label`/`sublabel` props added for Import's now-removed banner usage could have been left in place as unused surface area | Reverted the component to its exact original form (verified by diff) since Manual is now the only caller and uses no override |
| 3 | Losing the ability to review imported rows entirely | Simplifying the *workflow* to 2 steps could be mistaken for removing the review capability itself | `/imported-documents` and its per-row `ImportedDocumentReview` screen are untouched — review remains fully available, it is just no longer presented as a mandatory step before training |

---

## 3. Pattern & ADR Compliance

- No backend or ADR-governed behavior changed — `source_scope=import` gating on
  `POST /api/v1/training-jobs` was already implemented and untouched; this change only alters
  which UI element links to it and when it's shown.

---

## 4. Evidence Log

- **Frontend — tests:** `annotate/import/page.test.tsx` (5 tests, rewritten),
  `TrainModelBanner.test.tsx` (4 tests, reverted to its pre-Import set) — all passed against the
  `ner-portal-test` container, alongside a rerun of `annotate/manual/page.test.tsx` (6 tests) to
  confirm the `TrainModelBanner` revert didn't affect Manual's usage.
- **Full regression sweep:** full portal suite — 111/117 files passed (782/792 tests), matching
  exactly the pre-existing 6-file baseline with no new regressions.
- **Docker:** rebuilt and restarted the `portal` container.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), navigated to
  `/annotate/import` — confirmed "Your workflow" shows "1. Import annotations" and "2. Train
  model" (screenshot captured). Clicked "Train model →" and confirmed it landed on
  `/training-jobs?source=import` with the Submit Training Job slide-over auto-open, showing
  "Training source: Import" as locked read-only text (screenshot captured).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
