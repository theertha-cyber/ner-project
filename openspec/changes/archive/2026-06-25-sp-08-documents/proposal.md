## Why

The platform currently has no frontend for document management. While the backend document ingestion service exists, tenant_admin, annotator, and business_user roles have no way to upload, view, filter, or delete documents — blocking the annotation and extraction workflows. This spec delivers the SP-08 Documents screen at `/documents`, matching the mockup's table+upload visual language and the existing document ingestion API contracts.

## What Changes

- New `/documents` route with a paginated document table showing filename, content type, file size, status badge, and created date
- Drag-drop + click-to-browse file upload zone with client-side file type/size validation
- Status filter tabs (All, Pending, Processing, Processed, Failed)
- Soft delete via row-level action
- Auto-polling for documents in `pending` or `processing` status
- Upload progress bar using `XMLHttpRequest.upload.onprogress`

## Capabilities

### New Capabilities

- `portal-documents`: Document management screen at `/documents` with upload, list, filter, and soft-delete for tenant_admin, annotator, and business_user roles. Matches the mockup's table+slide-over visual language.

### Modified Capabilities

*(None — no existing spec requirements are being changed.)*

## Impact

- **New frontend route**: `/documents` in `src/portal/app/(auth)/documents/page.tsx`
- **New components**: `DocumentUpload.jsx`, `DocumentTable.jsx`, `DocumentRow.jsx`, `StatusFilterTabs.jsx` in `src/portal/components/documents/`
- **New hooks**: `useUpload.js` (progress-aware `XMLHttpRequest` wrapper), `useDocuments.js` (TanStack Query + polling)
- **Consumes APIs**: `GET/POST /api/v1/documents`, `GET/DELETE /api/v1/documents/{id}` from the document service
- **Relies on**: SP-03 App Shell (navigation), SP-01 UI primitives (Badge, Spinner, Toast), SP-02 authFetch, SP-02 RequireAuth

## Open Questions

- Should the upload zone show a confirmation step (review before submit) or upload immediately on file drop? **Decision**: Upload immediately on drop — matches the mockup pattern and keeps the workflow fast.
- Document preview on row click is deferred to a future spec. For now, clicking a row navigates to the annotation screen with that document pre-selected.
