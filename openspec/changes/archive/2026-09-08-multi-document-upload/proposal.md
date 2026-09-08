## Why

The `/documents` upload zone accepts exactly one file per interaction: the hidden `<input type="file">` has no `multiple` attribute, and both `handleDrop` and `handleInputChange` read only `files[0]`. Users onboarding a corpus (query documents for chat, or training documents for annotation) must repeat the click-select-wait cycle once per file, which is slow and error-prone for the common bulk-ingest case.

## What Changes

- Upload zone accepts **multiple files** in a single interaction — via multi-select in the file picker (`multiple` attribute) and via multi-file drag-and-drop (all of `dataTransfer.files`, not just index 0).
- Client-side validation (MIME allowlist, 50MB limit) runs **per file**. Invalid files are rejected individually with a per-file inline error; valid files in the same batch still upload. A batch is never rejected wholesale because one member is bad.
- Uploads are issued **sequentially**, one `XMLHttpRequest` at a time, reusing the existing `POST /api/v1/documents` single-file endpoint. No backend change.
- Progress reporting becomes batch-aware: per-file progress plus an overall "file N of M" indicator, replacing the single global progress bar.
- Batch outcome summary replaces the single "Upload successful" state: counts of succeeded / failed, with failed filenames and reasons listed.
- A failed file does **not** abort the batch; remaining files continue.
- Single-file upload behaviour is preserved as the degenerate one-item batch — same accepted types, same size limit, same endpoint, same `purpose` radio semantics, same query invalidation.
- Not breaking: no API contract change, no change to `DocumentTable`, `DocumentRow`, `StatusFilterTabs`, or polling behaviour.

## Capabilities

### New Capabilities

None. This extends existing upload behaviour rather than introducing a new capability.

### Modified Capabilities

- `portal-documents`: The **Document Upload Zone** requirement changes from single-file to multi-file selection with per-file validation and per-file error reporting. The **Upload Progress Bar** requirement changes from one global progress bar to per-file progress plus batch position, with a batch result summary on completion.

## Impact

**Code**
- `src/portal/src/components/documents/DocumentUpload.tsx` — batch state (queue, per-file status/error), `multiple` on the input, drop/change handlers iterate all files, new progress and summary UI.
- `src/portal/src/hooks/use-upload.ts` — `upload()` must be callable in sequence and report progress attributable to the current file. Existing single-file signature `upload(file, purpose)` is retained so no other caller breaks; batch orchestration lives in the component (or a thin wrapper) rather than changing the hook's contract.
- `src/portal/src/components/documents/DocumentUpload.test.tsx` — existing single-file drop tests must keep passing; new tests for multi-file drop, mixed valid/invalid batch, and partial failure.
- `src/portal/src/hooks/use-upload.test.tsx` — must keep passing unchanged.

**Not touched**
- `src/document_service/api/v1/documents.py` — `POST /api/v1/documents` stays a single-file `UploadFile = File(...)` endpoint.
- Document table, status filter tabs, auto-polling, soft delete.

**Behavioural**
- Sequential upload means wall-clock time for a batch is the sum of per-file times. Acceptable at the expected batch sizes; concurrency is a deliberate non-goal for this change (see Open Questions).
- Existing `queryClient.invalidateQueries({ queryKey: ["documents"] })` fires per successful file, so the table populates progressively during a batch.

## Decisions (confirmed)

- **Concurrency**: sequential, one file at a time. Bounded parallelism is a deliberate non-goal; revisit only if batch wall-clock becomes a complaint.
- **Batch size cap**: 20 files per batch. Exceeding it shows an inline message and uploads nothing from the oversized selection.
- **Cancel**: user may cancel mid-batch. The in-flight file is aborted and queued files are skipped. Already-uploaded documents are **not** rolled back.

## Open Questions

- **`purpose` per batch** — assumed one `purpose` (query vs training) applies to the whole batch, matching the current single radio group. Per-file purpose is out of scope.
