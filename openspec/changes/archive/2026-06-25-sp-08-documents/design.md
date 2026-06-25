## Context

The platform has a working document ingestion backend (`src/document-service/`) with endpoints for upload, list, get, and soft-delete, as well as the `openspec/specs/document-ingestion/spec.md` that defines these contracts. The frontend (`src/portal/`) currently lacks any document management UI — tenant_admin, annotator, and business_user roles have no way to upload documents or browse existing ones.

The mockup defines the visual language (table layout, status badges, drag-drop zone) via the existing Tenants screen pattern. No new ADRs are needed — this screen uses exactly one service endpoint set and follows established component patterns.

## Goals / Non-Goals

**Goals:**
- Provide a `/documents` page accessible to tenant_admin, annotator, and business_user roles
- Upload documents via drag-drop and click-to-browse with client-side validation (file type, size ≤ 50MB)
- Display a paginated table of documents with status badges and per-row delete
- Filter documents by status (All, Pending, Processing, Processed, Failed)
- Auto-poll documents in `pending` or `processing` status every 3 seconds
- Show upload progress via `XMLHttpRequest.upload.onprogress`

**Non-Goals:**
- Document preview or inline viewer (deferred to future spec)
- Batch upload (drag multiple files is acceptable but not a requirement)
- CSV import UI (handled by backend API; frontend scope deferred)
- Edit document metadata (not in API contracts)
- Perma-delete (soft delete only, matching the API)
- Real-time updates via WebSocket (polling is sufficient for MVP)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | All document queries are implicitly scoped to the tenant via the JWT — the UI never passes `tenant_id` |
| ADR-004 | OpenSpec SDD governance | This spec exists as a delta spec under a change package; main spec sync happens at archive time |
| ADR-005 | OpenCode agent boundaries | Implementation is limited to frontend code in `src/portal/`; no backend changes required |

## Decisions

### Decision 1: Component Architecture

**Choice:** Split the screen into four components: `DocumentUpload` (drag-drop zone + file input), `StatusFilterTabs` (filter row), `DocumentTable` (table wrapper with pagination), `DocumentRow` (individual row with status badge + delete action).

**Rationale:** Separation matches the mockup's table layout. Each component has a single responsibility. The existing Tenants screen (`SP-06`) uses the same decomposition pattern, and `StatusFilterTabs` can potentially be shared as a generic primitive later.

**Alternatives considered:**
- Single monolithic page component — ruled out because it would violate the established pattern and make unit testing harder.

### Decision 2: Upload via XMLHttpRequest for Progress

**Choice:** Use `XMLHttpRequest` wrapped in a `useUpload()` hook for the upload flow, exposing `{ upload(file), progress (0-100), isUploading, error }`.

**Rationale:** The `fetch` API does not support upload progress events. `XMLHttpRequest.upload.onprogress` is the standard browser API. Wrapping it in a hook keeps the upload logic testable and reusable.

**Alternatives considered:**
- `fetch` with a simulated progress bar — ruled out because it would be inaccurate and misleading.

### Decision 3: TanStack Query with Conditional Polling

**Choice:** Use `useQuery` with `refetchInterval: 3000` that is active only while at least one visible document has `status === "pending"` or `status === "processing"`. When all documents are in terminal states (`processed`, `failed`, `deleted`), polling stops.

**Rationale:** Avoids unnecessary API calls when no documents are in flight. The 3-second interval matches the decomposition document's recommendation.

**Alternatives considered:**
- Constant 3-second polling — ruled out for efficiency.
- WebSocket push — not available from the document service; polling is simpler for MVP.

### Decision 4: Pagination via Offset-Based Controls

**Choice:** Simple previous/next pagination controls matching the document service API (`page` + `per_page`). Default `per_page: 25`.

**Rationale:** The backend uses offset-based pagination. The decomposition document specifies this. Cursor-based would require backend changes.

### Decision 5: File Validation Order

**Choice:** Validate file type and size client-side before calling the API. Show inline errors in the upload zone on violation.

**Rationale:** The decomposition document requires client-side validation for UX (instant feedback, no round-trip). Server-side validation is also enforced (413 for oversized, 422 for unsupported type).

## Risks / Trade-offs

- [Upload zone shows no confirmation step — file uploads immediately on drop] → User may accidentally upload the wrong file. Mitigation: the new row appears at the top of the table immediately, giving visual confirmation. Row delete is one click away.
- [Polling interval creates 3s latency for status updates] → Acceptable for MVP. The annotation workspace requires documents to be `processed`; the wait is bounded by async OCR execution time (typically seconds, not minutes).
- [XHR does not integrate natively with TanStack Query] → The `useUpload()` hook wraps XHR and calls `queryClient.invalidateQueries(["documents"])` on success, keeping the list fresh.

## Migration Plan

No migration needed — this is a greenfield frontend screen. Deploy by adding the `src/portal/app/(auth)/documents/page.tsx` route, which will be immediately accessible via the sidebar nav item configured in SP-03.

## Open Questions

- After a successful upload, should the table automatically switch to the "Pending" filter tab to show the new document? Current decision: stay on the current filter; the new row appears if the current filter matches its status.
- The mockup does not show a specific Documents screen — the design follows the table+slide-over language from the Tenants screen. Is this acceptable? Assumption: yes, consistent with the decomposition document.
