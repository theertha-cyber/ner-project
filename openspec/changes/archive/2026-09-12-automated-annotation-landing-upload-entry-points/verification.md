# Verification Plan

**Change:** automated-annotation-landing-upload-entry-points
**Generated:** 2026-09-12
**Status:** 🟡 Automated evidence collected this session; Audit Record sign-off still needs a human reviewer.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Verification Artifact | Status |
|---|-----------|-------------|----------|------------------------|--------|
| 1 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Both upload entry points are visible before step 1 | src/portal/.../annotate/automated/page.test.tsx::"shows upload entry points before step 1..." | [x] |
| 2 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Upload documents opens the uploader pre-set to Automated | same test (asserts navigation to `/documents?upload=1&purpose=training&mode=automated`); dialog state live-verified in the browser | [x] |
| 3 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | Upload Q&A pair opens the Q&A-pair uploader | same test (asserts navigation to `/documents?upload=1&purpose=qa_pair`); dialog state live-verified in the browser | [x] |
| 4 | automated-annotation-landing | Pre-Step-1 Upload Entry Points | The primary "Start with step 1" action is unchanged | src/portal/.../annotate/automated/page.test.tsx::"still routes to step 1 from the primary action" | [x] |
| 5 | portal-documents | Upload deep link | Arriving with ?upload=1 opens the uploader | src/portal/.../documents/page.test.tsx::"auto-opens the uploader when linked with ?upload=1" (pre-existing, unmodified) | [x] |
| 6 | portal-documents | Upload deep link | Arriving with no upload parameter leaves the uploader closed | src/portal/.../documents/page.test.tsx::"keeps the uploader closed by default" (pre-existing, unmodified) | [x] |
| 7 | portal-documents | Upload deep link | An unrelated query parameter does not open the uploader | src/portal/.../documents/page.test.tsx::"does not auto-open..." (pre-existing, unmodified) | [x] |
| 8 | portal-documents | Upload deep link | purpose=qa_pair opens the Q&A-pair uploader | src/portal/.../documents/page.test.tsx::"opens the uploader pre-set to qa_pair when linked with ?upload=1&purpose=qa_pair" | [x] |
| 9 | portal-documents | Upload deep link | mode=automated seeds the annotation-mode selector | src/portal/.../documents/page.test.tsx::"opens the uploader pre-set to Automated when linked with ?upload=1&purpose=training&mode=automated" | [x] |
| 10 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector is shown for training uploads | src/portal/.../DocumentUpload.annotationMode.test.tsx::"shows_selector_for_training_purpose" (pre-existing, unmodified) | [x] |
| 11 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector is not shown for query uploads | src/portal/.../DocumentUpload.annotationMode.test.tsx::"hides_selector_for_query_purpose" (pre-existing, unmodified) | [x] |
| 12 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector resets to Manual after a batch completes | src/portal/.../DocumentUpload.annotationMode.test.tsx::"resets_to_manual_after_batch" (pre-existing, unmodified) | [x] |
| 13 | annotation-mode-selection | Annotation Mode Selector Visibility | Selector seeds its initial selection from the caller | src/portal/.../DocumentUpload.annotationMode.test.tsx::"seeds the initial selection from defaultAnnotationMode" | [x] |
| 14 | annotation-mode-selection | Annotation Mode Selector Visibility | A seeded Automated selection still resets to Manual after a batch | src/portal/.../DocumentUpload.annotationMode.test.tsx::"resets to Manual after a batch even when seeded as Automated" | [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|--------------------|-----------------------|
| 1 | Per-batch reset invariant | Seeding a default could be implemented by changing the post-batch reset target too (resetting to the seeded default instead of always "manual"), silently defeating the existing opt-in-per-batch safety property | Read `DocumentUpload.tsx` directly: the post-batch `setAnnotationMode("manual")` call is untouched — only the `useState` initializer changed. A dedicated test (`resets to Manual after a batch even when seeded as Automated`) asserts this explicitly |
| 2 | Query-param leakage across unrelated uploads | The Documents page's in-page "Upload documents"/"Upload Q&A pair" buttons could inherit a `mode=automated` left over from a previous deep-linked visit if `uploadMode` state isn't reset | Confirmed both in-page buttons explicitly call `setUploadMode(undefined)` before opening; the state is only ever set from the query-param effect or cleared by those buttons |
| 3 | Q&A-pair uploads showing the annotation-mode selector | `defaultAnnotationMode` could be mistakenly wired to show even when `purpose === "qa_pair"`, where the selector is meaningless (Q&A pairs are never annotated) | The selector's visibility condition (`purpose === "training"`) in `DocumentUpload.tsx` is untouched by this change; `defaultAnnotationMode` only affects the initial value of a state variable, not whether the selector renders |

---

## 3. Pattern & ADR Compliance

- No backend, database, or ADR-governed behavior is touched by this change — it is a
  frontend-only addition of navigation entry points and a seed-value prop.
- Consistent with the `manual-annotation-landing` capability's existing pattern (workflow-step
  cards linking to the exact page/dialog state a new user needs next).

---

## 4. Evidence Log

- **Frontend — new/updated tests:** `annotate/automated/page.test.tsx` (2 tests),
  `documents/page.test.tsx` (5 tests, 2 new), `DocumentUpload.annotationMode.test.tsx` (18 tests,
  2 new) — all run against the `ner-portal-test` container; 25/25 passed.
- **Frontend — regression sweep:** full `src/components/documents` suite — 52/55 passed; the 3
  failures are in `StatusFilterTabs.test.tsx`, part of the pre-existing 6-file baseline
  unrelated to this change.
- **Docker:** rebuilt and restarted the `portal` container with the current code.
- **Live browser verification:** logged in as `tenant_admin` (demo-corp), navigated to
  `/annotate/automated` — confirmed the "Before you begin" section renders both cards above
  "Start with step 1" (screenshot captured). Clicked "Upload documents" — landed on
  `/documents?upload=1&purpose=training&mode=automated` with the Upload Documents dialog open and
  "Automated" selected in the annotation-mode radio (screenshot captured). Clicked "Upload Q&A
  pair" — landed on `/documents?upload=1&purpose=qa_pair` with the Upload Q&A Pair dialog open
  (screenshot captured).

---

## 5. Audit Record

- [ ] Human reviewer has re-run the test suites above independently.
- [ ] Human reviewer sign-off: ______________________ Date: ______________
