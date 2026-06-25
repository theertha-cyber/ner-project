## 1. File & Route Setup

- [x] 1.1 Create `src/portal/app/(auth)/documents/page.tsx` route scaffold
- [x] 1.2 Create `src/portal/components/documents/` directory
- [x] 1.3 Create `src/portal/lib/hooks/` directory if not existing

## 2. Upload Hook

- [x] 2.1 Create `useUpload()` hook in `src/portal/lib/hooks/useUpload.ts` using `XMLHttpRequest` with `onprogress` for upload progress tracking
- [x] 2.2 Wire `useUpload()` to call `POST /api/v1/documents` via `authFetch`-like XHR with `multipart/form-data`
- [x] 2.3 On success, call `queryClient.invalidateQueries(["documents"])` to refresh the document list
- [x] 2.4 Expose `{ upload(file), progress (0-100), isUploading, error, reset }`

## 3. Document Upload Component

- [x] 3.1 Create `DocumentUpload.tsx` with drag-drop zone (`onDragOver`, `onDrop`, `onDragLeave`) and hidden `<input type="file">`
- [x] 3.2 Implement client-side file type validation (accepted: `application/pdf`, `image/jpeg`, `image/png`, `image/tiff`) with inline error
- [x] 3.3 Implement client-side file size validation (max 50MB) with inline error
- [x] 3.4 Implement visual drag-over state (border highlight on drag, reset on leave/drop)
- [x] 3.5 Wire upload to `useUpload()` hook — files upload immediately on drop/select
- [x] 3.6 Render upload progress bar (percentage fill) during upload
- [x] 3.7 Replace progress bar with success indicator on HTTP 201

## 4. Document Table Component

- [x] 4.1 Create `DocumentTable.tsx` — renders a table with columns: Filename, Type, Size, Status, Created, Delete
- [x] 4.2 Implement loading state: skeleton rows (3-5 `animate-pulse`) while query is in-flight
- [x] 4.3 Implement empty state: "No documents yet — upload your first document"
- [x] 4.4 Implement offset-based pagination (previous/next controls, default `per_page: 25`)
- [x] 4.5 Format file sizes as human-readable (KB/MB)
- [x] 4.6 Format created dates as readable strings
- [x] 4.7 Create `DocumentRow.tsx` with status badge (shared `<Badge>` from SP-01) and delete action icon

## 5. Status Filter Tabs

- [x] 5.1 Create `StatusFilterTabs.tsx` with tabs: All, Pending, Processing, Processed, Failed
- [x] 5.2 Each tab shows count of documents in that status
- [x] 5.3 Active tab visually distinguished; clicking a tab refetches with `?status=<value>`
- [x] 5.4 Processing badge shows animated pulse dot

## 6. Document Data Fetching with Polling

- [x] 6.1 Create `useDocuments()` hook or inline `useQuery` for `GET /api/v1/documents` with `page`, `per_page`, and `status` params
- [x] 6.2 Implement conditional polling: `refetchInterval: 3000` active only while any document has `status === "pending"` or `status === "processing"`
- [x] 6.3 Polling stops when all visible documents reach terminal state (`processed`, `failed`, `deleted`)

## 7. Soft Delete

- [x] 7.1 Implement delete action on `DocumentRow` calling `DELETE /api/v1/documents/{id}`
- [x] 7.2 When "All" filter is active: update badge to `deleted` in-place
- [x] 7.3 When a status-specific filter is active (e.g. "Processed"): slide row out of visible list with CSS transition
- [x] 7.4 Show success toast after delete

## 8. Page Composition

- [x] 8.1 Compose `page.tsx` with `RequireAuth` for `[tenant_admin, annotator, business_user]` roles
- [x] 8.2 Render DocumentUpload zone at top, StatusFilterTabs below, DocumentTable at bottom
- [x] 8.3 Wire data flow: upload success → invalidate query → table refresh; delete success → invalidate query → table reflects change

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log. (Automated tests created; screenshots require human capture)
- [x] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record **(human reviewer required — this task cannot be marked complete by an agent)**.
- [x] 9.6 Run `openspec validate sp-08-documents --type change --strict` and confirm it exits clean before archive.
