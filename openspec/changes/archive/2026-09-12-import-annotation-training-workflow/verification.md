# Verification Plan

**Change:** import-annotation-training-workflow
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | import-annotation-landing | Workflow Steps | tenant_admin sees the two-step workflow in order | src/portal/.../annotate/import/page.test.tsx::"tenant_admin sees the two-step workflow in order, each routing correctly" | [x] |
| 2 | import-annotation-landing | Workflow Steps | annotator sees only a single review card | src/portal/.../annotate/import/page.test.tsx::"annotator sees only a single review card, not the two-step workflow" | [x] |
| 3 | import-annotation-landing | Train Model Hand-off | CTA appears once training-eligible files exist | src/portal/.../annotate/import/page.test.tsx::"shows the Train model CTA once files are training-eligible, routing to /training-jobs?source=import" | [x] |
| 4 | import-annotation-landing | Train Model Hand-off | CTA is absent with nothing training-eligible | src/portal/.../annotate/import/page.test.tsx::"hides the Train model CTA when nothing is training-eligible yet" | [x] |
| 5 | import-annotation-landing | Train Model Hand-off | CTA is never shown to an annotator | src/portal/.../annotate/import/page.test.tsx::"never shows the Train model CTA to an annotator" | [x] |
| 6 | annotation-import-ui | Import Deep Link | Arriving with ?import=1 opens the file picker | src/portal/.../ImportedDocuments.test.tsx::"opens the file picker when linked with ?import=1" | [x] |
| 7 | annotation-import-ui | Import Deep Link | Arriving with no import parameter leaves the picker closed | src/portal/.../ImportedDocuments.test.tsx::"does not open the file picker with no import parameter" | [x] |
| 8 | annotation-import-ui | Import Deep Link | A role that cannot import does not get the picker opened for it | src/portal/.../ImportedDocuments.test.tsx::"does not open the file picker for a role that cannot import" | [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Confusing "type mapping" with a separate step | Could have invented a distinct "map entity types" landing-page step/screen that doesn't exist — mapping actually happens inline while reviewing a specific row in `ImportedDocumentReview` | Read `ImportedDocuments.tsx` directly: there is no dedicated mapping UI separate from the per-row review screen (`handleRetype`), so the workflow is described here as 2 steps (import, review), not 3 |
| 2 | `TrainModelBanner` default text changing for existing Manual call site | Adding `label`/`sublabel` props could have made them required, breaking Manual's existing usage or its copy | Both new props are optional with the original hardcoded strings kept as the default branch; `TrainModelBanner.test.tsx`'s 4 pre-existing tests (zero/singular/plural/onTrain) were rerun unmodified and still pass |
| 3 | The pre-existing "Request training" per-file button | Could have silently assumed it already does what the new source-scoped hand-off does, or silently removed/changed it | Read `use-retraining.ts` and confirmed it calls a different endpoint (`POST /api/v1/training-retrain-requests`, no `source_scope`) than the new hand-off (`/training-jobs?source=import` → `POST /api/v1/training-jobs` with `source_scope: "import"`); left untouched and the discrepancy is flagged as an open question in proposal.md rather than silently resolved either way |
| 4 | Regression in an unrelated, pre-existing test file | Adding a new hook call (`useSearchParams`) to a shared component could break other tests of that component that don't expect it | Ran the full portal suite before and after; caught exactly one new failure (`AnnotationImportFlow.test.tsx`, which renders `ImportedDocumentsList` via the page and didn't mock `next/navigation`) and fixed it by adding the mock, confirmed by rerunning both that file and the full suite |

---

## 3. Pattern & ADR Compliance

- Matches the established pattern from `manual-annotation-landing` and
  `automated-annotation-landing`: a numbered workflow-step section for `tenant_admin` only, a
  single review-only card for `annotator`, and a source-scoped "Train model" hand-off to
  `/training-jobs?source=<scope>`.
- No backend or ADR-governed behavior changed — `source_scope` gating (ADR-adjacent, established
  earlier this session) was already implemented; this change only reaches the existing
  `?source=import` entry point from a new place in the UI.

---

## 4. Evidence Log

- **Frontend — new/updated tests:** `annotate/import/page.test.tsx` (5 tests, new),
  `ImportedDocuments.test.tsx` (3 tests, new), `TrainModelBanner.test.tsx` (extended, +1 test) —
  all passed against the `ner-portal-test` container.
- **Regression caught and fixed:** the full portal suite run after this change first showed 7
  failing files (one more than the known 6-file baseline) — `AnnotationImportFlow.test.tsx`,
  a real regression from the new `useSearchParams` call in `ImportedDocumentsList`. Fixed by
  adding the missing `next/navigation` mock; rerunning the full suite afterward showed exactly
  the known 6-file baseline again (783 total tests passing, up from 770 before this change).
- **Docker:** rebuilt and restarted the `portal` container.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), navigated to
  `/annotate/import` — confirmed the "Your workflow" section shows "1. Import file" and "2.
  Review imported files" in order (screenshot captured), and that the Train Model banner is
  correctly absent (this tenant has 0 training-eligible imported files). Clicked "Import file →"
  and confirmed navigation landed on `/imported-documents?import=1` with the page rendering
  correctly (the OS-native file picker itself cannot be screenshotted by browser automation;
  its opening is confirmed by the passing `ImportedDocuments.test.tsx` unit tests instead).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer has decided what to do about the "Open Question" in proposal.md (the
  pre-existing unscoped per-file "Request training" button on `/imported-documents` coexisting
  with this change's properly-scoped hand-off).
- [ ] Human reviewer sign-off: ______________________ Date: ______________
