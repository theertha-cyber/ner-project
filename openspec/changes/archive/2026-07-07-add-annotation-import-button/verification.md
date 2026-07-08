# Verification Plan

**Change:** add-annotation-import-button
**Generated:** 2026-07-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-import-ui | Annotation File Import — Frontend Button | Import button visible for annotator role | Given a user with role annotator on the annotation page, when the page renders, then the Task Queue header displays an "Import" button | | - [ ] |
| 2 | annotation-import-ui | Annotation File Import — Frontend Button | Import button visible for tenant_admin role | Given a user with role tenant_admin on the annotation page, when the page renders, then the Task Queue header displays an "Import" button | | - [ ] |
| 3 | annotation-import-ui | Annotation File Import — Frontend Button | Import button hidden for business_user role | Given a user with role business_user on the annotation page, when the page renders, then the Task Queue header does NOT display an "Import" button | | - [ ] |
| 4 | annotation-import-ui | Annotation File Import — Frontend Button | File picker opens on button click | Given an "Import" button is visible in the Task Queue header, when the user clicks the button, then a native file picker opens filtered to .txt, .json, .jsonl | | - [ ] |
| 5 | annotation-import-ui | Annotation File Import — Frontend Button | Non-annotation file rejected at picker level | Given the file picker is open, when the user selects a file with extension other than .txt, .json, .jsonl, then the file is filtered out or rejected with a clear message | | - [ ] |
| 6 | annotation-import-ui | Client-Side File Preview | Preview shows CoNLL format breakdown | Given a .txt file with valid CoNLL data (5 sentences, entity types PER and ORG), when the preview slide-over opens, then it shows "Format: CoNLL", "Sentences: 5", and entity type counts for PER and ORG | | - [ ] |
| 7 | annotation-import-ui | Client-Side File Preview | Preview shows JSONL format breakdown | Given a .jsonl file with valid JSONL data (10 rows, entity types PER, ORG, DATE), when the preview slide-over opens, then it shows "Format: JSONL", "Rows: 10", and entity type counts | | - [ ] |
| 8 | annotation-import-ui | Client-Side File Preview | Preview warns about unknown entity types | Given a file containing entity type "PRODUCT" not defined in the tenant's entity types, when the preview slide-over opens, then it displays a warning about unknown entity types and indicates those rows will be skipped | | - [ ] |
| 9 | annotation-import-ui | Client-Side File Preview | Preview shows parse error for malformed file | Given a malformed CoNLL file (missing tag column), when the client-side parser attempts to parse, then the slide-over shows a parse error and the Import button is disabled | | - [ ] |
| 10 | annotation-import-ui | Client-Side File Preview | Preview shows file too large error | Given a file larger than 50MB, when the client-side checks the file size, then the slide-over shows "File exceeds the 50MB maximum" and the Import button is disabled | | - [ ] |
| 11 | annotation-import-ui | Client-Side File Preview | Preview slide-over has confirm and cancel buttons | Given a valid file has been parsed and preview is displayed, when the preview slide-over is open, then it shows Cancel and "Import N rows" buttons | | - [ ] |
| 12 | annotation-import-ui | Annotation File Upload and Backend Import | Successful import of all rows | Given a file with 100 rows (all entity types valid), when the user clicks "Import 100 rows", then the file is uploaded to POST /api/v1/annotation-import, response is 201 with imported_count: 100 and skipped_count: 0 | | - [ ] |
| 13 | annotation-import-ui | Annotation File Upload and Backend Import | Partial import with some rows skipped | Given a file with 100 rows (5 containing unknown entity types), when the backend processes the upload, then response is 201 with imported_count: 95, skipped_count: 5, and warnings array with 5 entries | | - [ ] |
| 14 | annotation-import-ui | Annotation File Upload and Backend Import | File too large returns 413 | Given a file larger than 50MB, when the backend receives the upload, then response is 413 and the frontend displays the error | | - [ ] |
| 15 | annotation-import-ui | Annotation File Upload and Backend Import | Unsupported MIME type returns 415 | Given a file with MIME type application/pdf, when the backend receives the upload, then response is 415 and the frontend displays the error | | - [ ] |
| 16 | annotation-import-ui | Backend Partial Import Support | Backend response schema change is backward-compatible | Given an existing caller that only reads imported_count, when the modified endpoint returns imported_count, skipped_count, and warnings, then the caller still sees imported_count with the correct value | | - [ ] |
| 17 | annotation-import-ui | Backend Partial Import Support | Backend skips rows with unknown entity types | Given a file with 3 rows (row 2 has unknown entity type "FOO"), when the backend processes the import, then rows 1 and 3 are inserted, row 2 is skipped, response has imported_count: 2, skipped_count: 1, and warnings for row 2 | | - [ ] |
| 18 | annotation-import-ui | Backend Partial Import Support | Backend returns entity type breakdown | Given a file with entity types PER, ORG, DATE, when the backend imports successfully, then the response includes entity_type_counts with counts for each type | | - [ ] |
| 19 | annotation-import-ui | Import Result Feedback | Result slide-over shows success | Given an import completed with 200 rows imported and 0 skipped, when the result slide-over opens, then it shows "200 rows imported" and no warnings section | | - [ ] |
| 20 | annotation-import-ui | Import Result Feedback | Result slide-over shows warnings | Given an import completed with 195 rows imported and 5 skipped, when the result slide-over opens, then it shows "195 rows imported, 5 rows skipped" and lists per-row warnings | | - [ ] |
| 21 | annotation-import-ui | Import Result Feedback | Import does not create annotation tasks | Given an import of 100 rows completes successfully, when the user views the task queue after import, then the same tasks appear as before (no new tasks created) | | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

For each area of complexity in this change, identify what an AI agent might get wrong
and how a human reviewer can detect and correct it.

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Client-side CoNLL parser | AI may implement tokenization differently from the backend parser (e.g., whitespace handling, blank line splitting), causing preview counts to differ from actual import counts | Compare parsed output of frontend parser and backend parser on the same sample file — row counts and token-tag pairs must match |
| 2 | Entity type validation | AI may hardcode entity type validation logic in the frontend instead of fetching the tenant's configured types from the API, causing stale or incorrect preview warnings | Verify the preview component fetches entity types via the existing `use-entity-types` hook, not a hardcoded list |
| 3 | Partial import error reporting | AI may silently drop skipped rows without reporting them in the response, or may report row indices incorrectly (0-indexed vs 1-indexed mismatch between frontend and backend) | Verify the backend warnings use 1-indexed row numbers matching the file's line numbers; verify the frontend renders all warnings |
| 4 | Response schema change | AI may modify the backend response shape in a way that breaks existing callers (e.g., removing the `imported_count` field, or changing its type from int to string) | Verify the modified endpoint returns `imported_count` as an integer with the same semantics as before; test with an existing caller |
| 5 | File size enforcement | AI may implement client-side file size check but skip the backend check, or implement both with different limits | Verify both frontend and backend enforce the same 50MB limit; test with a file between 50MB and 51MB |
| 6 | Role-based visibility | AI may use the wrong role string (e.g., "annotator" vs "annotation_user") or apply the guard only client-side without server-side enforcement | Verify the button visibility check uses the exact role string "annotator" from the auth context; confirm the import endpoint also enforces role server-side |

---

## 3. Pattern & ADR Compliance

List every currently-in-force ADR that constrains this change (as identified in design.md).

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate database schemas | Imported annotations must be stored in tenant's isolated schema (`tenant_{id}.imported_annotations`), not a shared table | Verify the backend stores imported rows in `{schema}.imported_annotations` (where `schema` = `tenant_{id}` with UUID dashes replaced by underscores) |
| ADR-004 | OpenSpec spec-driven development governance | All artifacts in the spec-driven-verified schema must be complete before implementation begins | Verify proposal.md, design.md, specs/**, and verification.md exist and are internally consistent before proceeding to tasks.md |

> If design.md references no constraining ADRs, state "No constraining ADRs" here.

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

*(Minimum one item per row in Section 1 — test output, screenshot, log excerpt, or API
trace proving the THEN was observed in a real execution.)*

- [ ] Scenario 1: Test output showing annotation page renders Import button for annotator role
- [ ] Scenario 2: Test output showing annotation page renders Import button for tenant_admin role
- [ ] Scenario 3: Test output showing Import button is absent for business_user role
- [ ] Scenario 4: Test output showing file picker opens with correct accept filter on button click
- [ ] Scenario 5: Test output showing non-.txt/.json/.jsonl file is rejected
- [ ] Scenario 6: Test output showing CoNLL preview with correct format, row count, entity breakdown
- [ ] Scenario 7: Test output showing JSONL preview with correct format, row count, entity breakdown
- [ ] Scenario 8: Test output showing unknown entity type warning in preview
- [ ] Scenario 9: Test output showing parse error message and disabled Import button
- [ ] Scenario 10: Test output showing file-too-large error message
- [ ] Scenario 11: Test output showing Cancel and Import N rows buttons in preview
- [ ] Scenario 12: API trace showing successful upload with imported_count: 100, skipped_count: 0
- [ ] Scenario 13: API trace showing partial import with imported_count: 95, skipped_count: 5, and warnings
- [ ] Scenario 14: API trace showing 413 response for oversized file
- [ ] Scenario 15: API trace showing 415 response for unsupported MIME type
- [ ] Scenario 16: Test output showing existing caller reads imported_count from modified response
- [ ] Scenario 17: API trace showing rows 1 and 3 inserted, row 2 skipped with warning
- [ ] Scenario 18: API trace showing entity_type_counts in response
- [ ] Scenario 19: Screenshot showing result slide-over with "200 rows imported" and no warnings
- [ ] Scenario 20: Screenshot showing result slide-over with "195 rows imported, 5 rows skipped" and warnings list
- [ ] Scenario 21: Test output showing task queue unchanged after import

### Structural Evidence

*(Code review and architectural compliance.)*

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

*(One item per Hallucination Risk from Section 2.)*

- [ ] Risk 1: Frontend and backend CoNLL parsers produce identical output on same sample file
- [ ] Risk 2: Preview component fetches entity types via use-entity-types hook, not hardcoded list
- [ ] Risk 3: Backend warnings use 1-indexed row numbers; frontend renders all warnings
- [ ] Risk 4: Backward-compatible response — existing caller reads imported_count correctly
- [ ] Risk 5: Both frontend and backend enforce 50MB limit identically
- [ ] Risk 6: Button uses exact role string "annotator"; server also enforces role

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** add-annotation-import-button
**Proposal:** openspec/changes/add-annotation-import-button/proposal.md
**Spec files reviewed:**
- specs/annotation-import-ui/spec.md

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
