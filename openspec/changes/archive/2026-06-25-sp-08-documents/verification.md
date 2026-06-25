# Verification Plan

**Change:** sp-08-documents
**Generated:** 2026-06-25
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | portal-documents | Document Upload Zone | Drag a valid PDF onto the zone | Given a user on /documents, when they drop a valid PDF on the upload zone, then POST /api/v1/documents is called and a new row appears with status "pending" | vitest: `DocumentUpload.test.tsx` — `given_drop_valid_pdf_when_uploaded_then_row_appears` | - [ ] |
| 2 | portal-documents | Document Upload Zone | Click to browse and select a valid PNG | Given a user on /documents, when they click the upload zone and select a PNG, then the file is uploaded and a new row appears | vitest: `DocumentUpload.test.tsx` — `given_click_browse_when_png_selected_then_uploaded` | - [ ] |
| 3 | portal-documents | Document Upload Zone | Drop an unsupported file type | Given a user on /documents, when they drop a .exe file, then an inline error is shown and no API call is made | vitest: `DocumentUpload.test.tsx` — `given_unsupported_type_when_dropped_then_inline_error` | - [ ] |
| 4 | portal-documents | Document Upload Zone | Drop a file exceeding 50MB | Given a user on /documents, when they drop a 100MB file, then an inline error is shown and no API call is made | vitest: `DocumentUpload.test.tsx` — `given_oversized_file_when_dropped_then_inline_error` | - [ ] |
| 5 | portal-documents | Document Upload Zone | Drag-over visual state change | Given the upload zone is idle, when a file is dragged over it, then the zone border changes to a highlighted state | vitest: `DocumentUpload.test.tsx` — `given_drag_over_when_state_changed_then_highlighted` | - [ ] |
| 6 | portal-documents | Upload Progress Bar | Upload progress updates in real time | Given a file is uploading via XHR, when the upload progresses, then the progress bar fills proportionally | vitest: `useUpload.test.ts` — `given_uploading_when_onprogress_then_bar_fills` | - [ ] |
| 7 | portal-documents | Upload Progress Bar | Upload completes | Given a file upload reaches 100%, when the server responds with 201, then the progress bar is replaced by a success indicator and the document list invalidates | vitest: `useUpload.test.ts` — `given_upload_complete_when_201_then_success_and_invalidate` | - [ ] |
| 8 | portal-documents | Document Table | Table renders with correct columns | Given the tenant has documents, when the table loads, then columns Filename/Type/Size/Status/Created/Delete are shown | vitest: `DocumentTable.test.tsx` — `given_documents_when_table_loads_then_columns_rendered` | - [ ] |
| 9 | portal-documents | Document Table | Pagination next/previous | Given 30 documents with per_page=25, when the table renders, then page 1 shows 25 docs with a "Next" control | vitest: `DocumentTable.test.tsx` — `given_30_docs_when_page1_then_25_shown_with_next` | - [ ] |
| 10 | portal-documents | Document Table | Empty state | Given the tenant has no documents, when the table renders, then an empty state message and upload zone are shown | vitest: `DocumentTable.test.tsx` — `given_no_docs_when_table_loads_then_empty_state` | - [ ] |
| 11 | portal-documents | Document Table | Loading state shows skeleton rows | Given the query is in-flight, when the table renders, then skeleton placeholder rows are shown | vitest: `DocumentTable.test.tsx` — `given_loading_when_table_renders_then_skeleton` | - [ ] |
| 12 | portal-documents | Status Filter Tabs | Click a status filter tab | Given "All" is active, when the user clicks "Processed", then the table refetches with ?status=processed | vitest: `StatusFilterTabs.test.tsx` — `given_all_active_when_click_processed_then_filter_refetch` | - [ ] |
| 13 | portal-documents | Status Filter Tabs | Filter tab shows document counts | Given 5 processed and 2 pending docs, when filter tabs render, then each tab shows its count | vitest: `StatusFilterTabs.test.tsx` — `given_counts_when_tabs_render_then_counts_displayed` | - [ ] |
| 14 | portal-documents | Status Badge | Processing badge shows pulse animation | Given a document with status "processing", when its row renders, then the badge shows a pulse animation | vitest: `DocumentRow.test.tsx` — `given_processing_status_when_row_renders_then_pulse` | - [ ] |
| 15 | portal-documents | Status Badge | Deleted badge is visually muted | Given a document with status "deleted", when its row renders, then the badge uses grey/muted colour | vitest: `DocumentRow.test.tsx` — `given_deleted_status_when_row_renders_then_muted_badge` | - [ ] |
| 16 | portal-documents | Auto-Polling for In-Flight Documents | Polling starts when pending document exists | Given a pending document in the list, when 3 seconds elapse, then the list is auto-refetched | vitest: `useDocuments.test.ts` — `given_pending_doc_when_3s_then_refetch` | - [ ] |
| 17 | portal-documents | Auto-Polling for In-Flight Documents | Polling stops when all documents reach terminal state | Given polling is active for a processing doc, when it transitions to processed, then polling stops | vitest: `useDocuments.test.ts` — `given_processing_doc_when_completed_then_polling_stops` | - [ ] |
| 18 | portal-documents | Soft Delete | Delete a document from a filtered list | Given a processed doc visible with "Processed" filter, when the user clicks delete, then DELETE /api/v1/documents/{id} is called and the row slides out | vitest: `DocumentRow.test.tsx` — `given_filtered_list_when_delete_then_row_slides_out` | - [ ] |
| 19 | portal-documents | Soft Delete | Delete a document when "All" filter is active | Given a processed doc visible with "All" filter, when the user clicks delete, then the row remains visible with "deleted" badge | vitest: `DocumentRow.test.tsx` — `given_all_filter_when_delete_then_badge_updates` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Upload progress implementation | AI may use `fetch` with a simulated progress bar instead of `XMLHttpRequest.upload.onprogress` | Verify the upload hook uses `XMLHttpRequest` and reads `onprogress` event — not a fake timer |
| 2 | Polling logic | AI may implement constant 3s polling regardless of document status, or may not stop polling when all documents reach terminal state | Verify `refetchInterval` is conditionally enabled only while pending/processing documents exist in the query result |
| 3 | File validation order | AI may validate file type and size server-side only (after upload), bypassing client-side checks | Verify client-side validation runs before any `XMLHttpRequest.send()` call |
| 4 | Delete from filtered list | AI may not handle the filtered-list delete case — row should slide out when filter hides it, not disappear when "All" is active | Verify the row removal behaviour differs between "All" filter (badge changes to deleted) and "Processed" filter (row slides out) |
| 5 | Drag-drop visual state | AI may not implement the visual state change on drag-over (border highlight, removal on leave/drop) | Verify `onDragOver`, `onDragLeave`, `onDrop` handlers with visual state change |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | The UI must not send `tenant_id` in document API requests — tenant context comes from the JWT | Verify no document API call in the frontend includes a `tenant_id` parameter |
| ADR-004 | OpenSpec SDD governance | This is a delta spec under a change package; main spec sync happens at archive | No code-level check — confirm at archive time that main spec is synced |
| ADR-005 | OpenCode agent boundaries | Implementation is limited to `src/portal/` frontend code | Verify no backend files in `src/gateway/`, `src/document-service/`, etc. were modified |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing `given_drop_valid_pdf_when_uploaded_then_row_appears` passes
- [ ] Scenario 2: Test output showing `given_click_browse_when_png_selected_then_uploaded` passes
- [ ] Scenario 3: Test output showing `given_unsupported_type_when_dropped_then_inline_error` passes
- [ ] Scenario 4: Test output showing `given_oversized_file_when_dropped_then_inline_error` passes
- [ ] Scenario 5: Screenshot showing drag-over highlight state on upload zone
- [ ] Scenario 6: Screenshot showing progress bar filling during upload
- [ ] Scenario 7: Screenshot showing success indicator after upload completes, or test proving query invalidated
- [ ] Scenario 8: Screenshot showing document table with correct columns
- [ ] Scenario 9: Screenshot showing pagination controls and correct doc count
- [ ] Scenario 10: Screenshot showing empty state message
- [ ] Scenario 11: Screenshot showing skeleton loading rows
- [ ] Scenario 12: Test or screenshot proving filter refetch with `?status=processed`
- [ ] Scenario 13: Screenshot showing filter tab counts
- [ ] Scenario 14: Screenshot or CSS test showing pulse animation on processing badge
- [ ] Scenario 15: Screenshot showing muted deleted badge
- [ ] Scenario 16: Test or log showing polling fires at 3s interval while pending doc exists
- [ ] Scenario 17: Test or log showing polling stops when no in-flight docs remain
- [ ] Scenario 18: Screenshot showing row sliding out after delete in filtered view
- [ ] Scenario 19: Screenshot showing deleted badge when "All" is active

### Structural Evidence

- [ ] Code review completed — component architecture matches design.md Decision 1 (DocumentUpload, StatusFilterTabs, DocumentTable, DocumentRow)
- [ ] Upload hook verified to use XMLHttpRequest with onprogress (not simulated fetch) per Decision 2
- [ ] Conditional polling logic verified (refetchInterval gated by pending/processing status) per Decision 3
- [ ] No tenant_id parameter in any document API call (ADR-001 compliance)
- [ ] All changes limited to `src/portal/` (ADR-005 compliance)
- [ ] File validation runs client-side before upload per Decision 5

### Edge Case Evidence

- [ ] Risk 1 (Upload progress): Upload hook verified to use `XMLHttpRequest` with real `onprogress` handler
- [ ] Risk 2 (Polling logic): Conditional polling verified — `refetchInterval` is a function returning 3000 or false based on query data
- [ ] Risk 3 (File validation): Client-side file type and size checks confirmed to execute before `send()`
- [ ] Risk 4 (Filtered delete): Delete handler checked for different behaviour between "All" filter and status filters
- [ ] Risk 5 (Drag-drop visual): Drag-over/drop/leave handlers verified with visual state changes

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

**Change slug:** sp-08-documents
**Proposal:** `openspec/changes/sp-08-documents/proposal.md`
**Spec files reviewed:**
- `specs/portal-documents/spec.md`

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
