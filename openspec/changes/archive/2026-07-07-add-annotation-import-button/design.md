## Context

The annotation service exposes `POST /api/v1/annotation-import` which accepts CoNLL (`.txt`) and JSONL (`.json`/`.jsonl`) files, parses them into token/tag rows, validates entity types against `public.entity_definitions`, and stores valid rows in `{tenant_schema}.imported_annotations`. The export endpoint (`GET /api/v1/annotation-export`) already includes `imported_annotations` in its output, and the training job submission slide-over (`submit-job-slideover.tsx`) queries the export to count annotation rows — so the downstream pipeline already works.

The gap is pure UX: the frontend has no way to trigger the import endpoint. The annotation page is a 3-pane workspace (Task Queue | Document Viewer | Entity Palette). There is no import button anywhere in the portal.

The existing upload component (`DocumentUpload.tsx`) is for document ingestion (PDF/images) and is on a different page (`/documents`), so it is not reusable for annotation files.

The project uses a custom `SlideOver` component for overlay panels (used by `SubmitJobSlideover`), and `authFetch` for authenticated API calls. The annotation page is built as a single `AnnotationPage.tsx` component that orchestrates sub-components.

## Goals / Non-Goals

**Goals:**
- Add an "Import" button in the Task Queue header of the annotation page.
- Show a preview slide-over before upload: file format, row count, entity type breakdown, unknown type warnings.
- On confirmation, upload the file to the existing import endpoint.
- Show a result slide-over: imported count, skipped rows with per-row warnings.
- Roles: `annotator` and `tenant_admin` see the button.
- Backend supports partial import: valid rows are imported, rows with unknown entity types are skipped with per-row warnings.

**Non-Goals:**
- No changes to the annotation workspace (span CRUD, pre-labeling, task management).
- No new database tables.
- No new API routes (modify existing endpoint response schema only).
- No changes to the training job submission flow.
- No bulk download/export of annotation files (separate capability).

## Currently-In-Force ADRs

All ADRs in `docs/adr/` are `Proposed` — none are superseded. The following constrain this design:

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate database schemas | Imported annotations are stored in the tenant's isolated schema (`tenant_{id}.imported_annotations`); the existing schema-per-tenant pattern continues unchanged. |
| ADR-004 | OpenSpec spec-driven development governance | This change follows the spec-driven-verified schema: proposal → design → specs → verification → tasks. |

## Decisions

### Decision 1: Pre-parse client-side for preview, backend validates on import

**Choice:** The frontend parses the file in the browser using pure TypeScript functions before upload, showing a preview with entity type counts. The backend re-validates on receipt and returns a result with per-row warnings.

**Rationale:** The preview needs entity type breakdown to be useful (users want to see what's in their file before committing). The frontend already has access to the tenant's entity types via the existing `use-entity-types` hook (`GET /api/v1/tenants/{slug}/entity-types`), so it can flag unknown types at preview time. The backend must still validate to prevent bypass and handle race conditions (entity types changing between preview and upload).

**Alternatives considered:**
- Backend-only: simpler but provides no preview UX.
- Backend returns entity breakdown in response: possible, but the pre-parse approach gives users the preview *before* uploading, which is more valuable (they can cancel if the data looks wrong).

### Decision 2: Slide-over panels for preview and result

**Choice:** Use the existing `SlideOver` component from `src/components/ui/` for both the preview panel (before upload) and the result panel (after upload).

**Rationale:** The project already uses `SlideOver` for the training job submission panel (`SubmitJobSlideover`), establishing a consistent pattern for non-destructive overlay panels. Slide-over panels don't block the underlying page context like modals would. The annotation page's 3-pane layout is already dense — a slide-over avoids disrupting the workspace layout.

**Alternatives considered:**
- Inline preview within the task queue: too little space (Task Queue is only 228px wide).
- Full-page modal: too disruptive to the annotation workflow.
- Toast notification for result: too ephemeral for a detailed summary.

### Decision 3: Modify the backend import endpoint response, not its contract

**Choice:** The `POST /api/v1/annotation-import` endpoint's response changes from `{"imported_count": N}` to include `skipped_count` and `warnings`. The request format (multipart file upload) is unchanged. Entity type validation changes from all-or-nothing reject to per-row filtering: rows with unknown entity types are skipped, valid rows are imported.

**Rationale:** The existing response shape is minimal. Adding `skipped_count` and `warnings` is backward-compatible for any caller reading only `imported_count`. The per-row filtering approach enables the "partial import with warnings" flow the user wants. The backend already has the parsed data and entity type context — it's the natural place for final validation.

**Alternatives considered:**
- New endpoint (`POST /api/v1/annotation-import-v2`): unnecessary versioning for a backward-compatible change.
- Keep backend all-or-nothing, return warnings on separate endpoint: adds unnecessary round-trips.

### Decision 4: Client-side parser in pure TypeScript

**Choice:** Write the CoNLL and JSONL parsers as pure TypeScript functions in `src/lib/annotation-import-parser.ts`, with no external dependencies.

**Rationale:** Both formats are simple text formats. CoNLL is tab-separated token/tag pairs with blank-line sentence separators. JSONL is JSON lines. The parsers are pure functions (string → parsed rows) with no DOM or I/O dependencies, making them easy to test with Vitest. Adding a dependency (e.g., Papa Parse) would be overkill.

### Decision 5: Upload via authFetch with XMLHttpRequest fallback for progress

**Choice:** Use `authFetch` (the project's authenticated fetch wrapper) for the upload, with a progress indicator based on the response time rather than upload progress percentage.

**Rationale:** The existing document upload (`use-upload.ts`) uses `XMLHttpRequest` specifically to get `xhr.upload.onprogress` events. For annotation files (which are text, typically much smaller than 50MB documents), the upload is fast enough that granular progress is unnecessary. `authFetch` integrates cleanly with the project's auth pattern (automatic JWT injection, 401 refresh). If the file is large, a simple spinner with "Importing..." text is sufficient feedback.

## Risks / Trade-offs

- **[Client-side parse does not re-validate after file picker]** → Mitigation: The backend always re-validates. If entity types changed between preview and upload, the backend's response will differ from the preview. The result slide-over shows the backend's authoritative counts.
- **[50MB file upload could timeout]** → Mitigation: The backend already enforces 50MB max. The frontend should also check file size pre-upload and reject files >50MB with a clear message before attempting upload.
- **[CoNLL format ambiguity (.txt could be plain text)]** → Mitigation: The existing backend heuristic (`.txt` = CoNLL, `.json`/`.jsonl` = JSONL) is documented in the UI. The preview shows the detected format before upload, so the user can verify.

## Migration Plan

1. **Backend**: Modify the import endpoint's response schema and validation logic. Deploy independently — the response change is backward-compatible.
2. **Frontend**: Add the parser utility, hooks, and components. The button is additive — the annotation page works without it for roles that don't see it.
3. **No rollback concerns**: The backend change is an in-place modification (wider response, more tolerant validation). Rolling back means reverting the response to the minimal shape; existing callers only read `imported_count` so both shapes work.

## Open Questions

- Should the client-side parser detect encoding issues (non-UTF-8) before upload? The current backend decodes as UTF-8 and will error. A client-side check could catch this earlier.
