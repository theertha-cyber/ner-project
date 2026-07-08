## 1. Backend — Partial Import Support

- [x] 1.1 Modify `POST /api/v1/annotation-import` response to include `entity_type_counts` dict, `skipped_count` int, and `warnings` array alongside existing `imported_count`
- [x] 1.2 Change entity type validation from all-or-nothing reject to per-row filtering: iterate rows individually, skip rows with unknown entity types, collect warnings with row index and message, import valid rows
- [x] 1.3 Add backend tests for: partial import (some rows skipped), backward-compatible response (existing fields unchanged), entity type breakdown in response, all rows unknown (imported_count: 0), file too large (413), unsupported MIME type (415)

## 2. Frontend — Client-Side File Parser

- [x] 2.1 Create `src/lib/annotation-import-parser.ts` with pure TypeScript functions: `parseConll(content: string): ParsedRow[]` and `parseJsonl(content: string): ParsedRow[]`, where `ParsedRow = { tokens: string[], tags: string[] }`
- [x] 2.2 Create `parseFile(file: File): Promise<ParseResult>` that detects format by extension, reads the file as text, delegates to the appropriate parser, and computes entity type breakdown with counts and unknown type warnings against known entity types
- [x] 2.3 Write Vitest tests for the parser: valid CoNLL, valid JSONL, malformed CoNLL (missing tab), empty file, entity type breakdown counts, utf-8 decode handling

## 3. Frontend — Upload Hook

- [x] 3.1 Create `src/hooks/use-annotation-import.ts` with `importAnnotations(file: File): Promise<ImportResult>` that POSTs multipart/form-data to `{ANNOTATION_URL}/api/v1/annotation-import` via authFetch, returns parsed response with `imported_count`, `skipped_count`, `warnings`, `entity_type_counts`
- [x] 3.2 Write Vitest tests for the hook: successful upload, partial import response, error responses (413, 415), network failure

## 4. Frontend — Preview Slide-Over

- [x] 4.1 Create `AnnotationImportPreview` component (slide-over) that accepts a `ParseResult` and displays: detected format, row count, entity type breakdown bar chart, unknown type warnings with skip indication, Cancel button, "Import N rows" button
- [x] 4.2 Handle preview states: parsing (loading spinner), parse error (message + disabled Import), file too large (message + disabled Import), valid parse (full preview with enabled Import)

## 5. Frontend — Result Slide-Over

- [x] 5.1 Create `AnnotationImportResult` component (slide-over) that accepts an `ImportResult` and displays: imported count, skipped count (if > 0), warnings list (if any), entity type summary, Done button that closes the panel
- [x] 5.2 Handle result states: uploading (loading spinner), success with no skips, success with skips, error (full reject — backend unreachable or unrecoverable)

## 6. Frontend — Import Button and Integration

- [x] 6.1 Add an "Import" button to the Task Queue header in `AnnotationPage.tsx`, conditionally rendered for `annotator` and `tenant_admin` roles (same pattern as existing "Assign Task" button)
- [x] 6.2 Wire the full flow: button click → file picker → preview slide-over → confirm → upload with loading state → result slide-over → Done closes all
- [x] 6.3 Write component tests for: button visibility per role, file picker accept attribute, full flow integration (mock file, mock API, verify slide-overs render)

## 7. Verification & Evidence

- [x] 7.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 7.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. *(human reviewer)*
- [ ] 7.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register. *(human reviewer)*
- [ ] 7.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance. *(human reviewer)*
- [ ] 7.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent). *(human reviewer)*
- [x] 7.6 Run `openspec validate add-annotation-import-button --type change --strict` and confirm it exits clean before archive.
