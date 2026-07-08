# Verification Plan

**Change:** review-imported-annotations
**Generated:** 2026-07-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | annotation-import-review | Imported Documents List View | List view visible to annotator and tenant_admin | Given a user with role annotator or tenant_admin, when they open the Imported Documents view, then the list renders one entry per imported_annotations row for their tenant | `test_imported_annotations_list.py::test_list_visible_to_annotator_and_tenant_admin` | - [ ] |
| 2 | annotation-import-review | Imported Documents List View | List view hidden for business_user role | Given a user with role business_user, when they attempt to access the Imported Documents view, then access is denied (view hidden / API 403) | `test_imported_annotations_list.py::test_list_hidden_for_business_user` | - [ ] |
| 3 | annotation-import-review | Imported Documents List View | List is paginated | Given a tenant with 3,000 imported rows, when the list is requested, then a bounded page of results is returned with pagination metadata | `test_imported_annotations_list.py::test_list_pagination` | - [ ] |
| 4 | annotation-import-review | Imported Documents List View | Filter by source file | Given rows from two different source files, when the list is filtered by source_file, then only matching rows are returned | `test_imported_annotations_list.py::test_filter_by_source_file` | - [ ] |
| 5 | annotation-import-review | Imported Documents List View | Filter by entity type | Given rows with mixed entity types, when the list is filtered by entity type "ORG", then only rows containing a B-ORG/I-ORG tag are returned | `test_imported_annotations_list.py::test_filter_by_entity_type` | - [ ] |
| 6 | annotation-import-review | Token-Level Rendering with Entity Colors | O tokens render unselected | Given a row with tags ["O","B-PER","O"], when opened for review, then tokens 1 and 3 render as plain unselected text | `token-rendering.test.tsx::renders_O_tokens_unselected` | - [ ] |
| 7 | annotation-import-review | Token-Level Rendering with Entity Colors | B/I run renders as one colored span | Given tokens ["Jane","Doe","works"] with tags ["B-PER","I-PER","O"], when opened for review, then "Jane Doe" renders as one colored span in the PER color and "works" renders plain | `token-rendering.test.tsx::renders_BI_run_as_single_colored_span` | - [ ] |
| 8 | annotation-import-review | Token-Level Rendering with Entity Colors | Entity color matches the interactive workspace | Given "PER" is colored #6366f1 in the interactive workspace, when a PER span is rendered in the review surface, then it uses the same #6366f1 color | Manual screenshot comparison: `evidence/color-parity.png` | - [ ] |
| 9 | annotation-import-review | Editing Imported Row Annotations | Retype a span's entity type | Given a PER span over tokens 0-1, when the user retypes it to ORG, then tags[0:2] become ["B-ORG","I-ORG"] | `test_imported_annotations_update.py::test_retype_span` | - [ ] |
| 10 | annotation-import-review | Editing Imported Row Annotations | Delete a span | Given a PER span over tokens 0-1, when the user deletes it, then tags[0:2] become ["O","O"] | `test_imported_annotations_update.py::test_delete_span` | - [ ] |
| 11 | annotation-import-review | Editing Imported Row Annotations | Create a new span from unselected tokens | Given tokens 3-4 tagged ["O","O"], when the user selects them and assigns DATE, then tags[3:5] become ["B-DATE","I-DATE"] | `test_imported_annotations_update.py::test_create_span` | - [ ] |
| 12 | annotation-import-review | Editing Imported Row Annotations | Reject unknown entity type on edit | Given "PRODUCT" is not a configured entity type, when the user assigns it to a token range, then the edit is rejected with a validation error and tags[] is unchanged | `test_imported_annotations_update.py::test_reject_unknown_entity_type` | - [ ] |
| 13 | annotation-import-review | Review Progress Tracking | Saving an edit marks the row reviewed | Given an unreviewed row, when the user saves a tag edit, then reviewed becomes true and reviewed_at/reviewed_by are set | `test_imported_annotations_update.py::test_save_edit_marks_reviewed` | - [ ] |
| 14 | annotation-import-review | Review Progress Tracking | Marking reviewed without edits | Given an unreviewed row with no changes, when the user explicitly marks it reviewed, then reviewed becomes true and tags[] is unchanged | `test_imported_annotations_update.py::test_mark_reviewed_without_edits` | - [ ] |
| 15 | annotation-import-review | Review Progress Tracking | Filter list by reviewed state | Given a mix of reviewed and unreviewed rows, when the list is filtered to unreviewed only, then only rows with reviewed=false are returned | `test_imported_annotations_list.py::test_filter_by_reviewed_state` | - [ ] |
| 16 | annotation-import-review | Imported Rows Remain Decoupled from the Annotation Task Pipeline | Editing an imported row does not create a task | Given a row with no associated task, when the user edits and saves it via this surface, then no new documents/annotation_tasks/spans rows are created | `test_imported_annotations_update.py::test_no_task_or_document_created_on_edit` | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change appears above (16/16). A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Token-to-tag index alignment | AI may off-by-one the token range when converting a BIO run to a span (e.g. include/exclude the boundary token), corrupting adjacent tags on save | Manually create a span spanning tokens at both edges of a row (index 0 and the last index) and confirm only the intended indices change in tags[] |
| 2 | Materialization boundary | AI may take a shortcut and reuse existing `documents`/`annotation_tasks`/`spans` code paths (e.g. to reuse Token.tsx's existing data-fetching hooks) and accidentally create real documents/tasks | Grep the implementation for calls to `POST /api/v1/documents`, `POST /api/v1/annotation-tasks`, or `POST /api/v1/documents/{id}/spans` from the new review surface's code paths — none should exist |
| 3 | Entity type validation reuse | AI may reimplement entity-type validation from scratch instead of reusing `get_known_entity_types_lower` from `import_.py`, causing the review surface to accept/reject differently than import does | Compare the validation logic used by the new update endpoint against `import_.py`'s validation function; confirm they reference the same tenant entity-type source and case-insensitivity behavior |
| 4 | Reviewed-state side effects | AI may set `reviewed=true` on read (e.g. whenever a row is opened) rather than only on explicit save/mark-reviewed actions, making the reviewed filter meaningless | Open several rows without editing or explicitly marking them reviewed; confirm `reviewed` stays false until an explicit save or mark-reviewed action occurs |
| 5 | Migration scope | AI may add the new columns only to `tenant_template` and miss applying them to existing `tenant_*` schemas, following the pattern in migration 012 incompletely | After migration, query `imported_annotations` in at least one pre-existing tenant schema (not just `tenant_template`) and confirm the new columns exist with correct defaults |
| 6 | Color scheme drift | AI may hardcode a new/different color palette in the review surface instead of reusing the exact `buildEntityColors` computation from `AnnotationPage.tsx`, causing colors to diverge between the two surfaces | Compare the same entity type's rendered color side-by-side in the interactive workspace and the new review surface for the same tenant |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-------------------|---------------------------|--------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via per-tenant Postgres schema (`tenant_<uuid>`); migrations applied uniformly across `tenant_template` and all existing tenant schemas | New `reviewed`/`reviewed_at`/`reviewed_by` columns and new endpoints must stay within the existing schema-per-tenant boundary; no cross-tenant queries; migration must apply to every existing tenant schema, not just the template | Confirm the new migration follows the `DO $$ ... FOR schema_name IN ...` loop pattern (as in `alembic/versions/012_reconcile_training_jobs_columns.py`) and run it against a multi-tenant test DB to confirm all schemas gain the columns; confirm new endpoints scope all queries through the existing tenant_context/search_path mechanism |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test or manual trace showing an annotator/tenant_admin sees the Imported Documents list populated with their tenant's rows
- [ ] Scenario 2: Test showing a business_user request to the list endpoint/view returns 403 or the view is not rendered
- [ ] Scenario 3: Test output showing a paginated response (page/per_page/total) for a large row count
- [ ] Scenario 4: Test output showing source_file filtering returns only matching rows
- [ ] Scenario 5: Test output showing entity-type filtering returns only matching rows
- [ ] Scenario 6: Screenshot or DOM snapshot showing O-tagged tokens rendered plain
- [ ] Scenario 7: Screenshot or DOM snapshot showing a B/I run rendered as one colored span
- [ ] Scenario 8: Screenshot comparison showing identical color for the same entity type across both surfaces
- [ ] Scenario 9: Test output showing tags[] updated correctly after a retype
- [ ] Scenario 10: Test output showing tags[] reverts to O after a delete
- [ ] Scenario 11: Test output showing tags[] updated correctly after creating a new span
- [ ] Scenario 12: Test output showing a validation error and unchanged tags[] for an unknown entity type
- [ ] Scenario 13: Test output showing reviewed/reviewed_at/reviewed_by set after saving an edit
- [ ] Scenario 14: Test output showing reviewed set to true via explicit mark-reviewed action with tags[] unchanged
- [ ] Scenario 15: Test output showing the reviewed-state filter returns only unreviewed rows
- [ ] Scenario 16: Test output / DB query confirming no new documents/annotation_tasks/spans rows after editing an imported row

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — boundary-index span creation/edit tested at both ends of a row
- [ ] Risk 2 mitigation confirmed — grep confirms no calls into documents/annotation_tasks/spans creation endpoints from the review surface
- [ ] Risk 3 mitigation confirmed — validation logic confirmed to reuse `get_known_entity_types_lower`
- [ ] Risk 4 mitigation confirmed — opening/viewing a row without action confirmed not to set reviewed=true
- [ ] Risk 5 mitigation confirmed — new columns confirmed present in a pre-existing (non-template) tenant schema after migration
- [ ] Risk 6 mitigation confirmed — entity color visually confirmed identical between interactive workspace and review surface

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** review-imported-annotations
**Proposal:** `openspec/changes/review-imported-annotations/proposal.md`
**Spec files reviewed:**
  - specs/annotation-import-review/spec.md

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
