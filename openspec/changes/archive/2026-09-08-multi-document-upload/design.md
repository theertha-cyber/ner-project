## Context

The portal's document upload zone (`src/portal/src/components/documents/DocumentUpload.tsx`) is single-file by construction:

- the hidden `<input type="file">` has no `multiple` attribute,
- `handleDrop` reads `e.dataTransfer.files[0]`,
- `handleInputChange` reads `e.target.files?.[0]`,
- `handleFile(file: File)` holds one validation result and one success flag,
- `useUpload()` (`src/portal/src/hooks/use-upload.ts`) exposes a single `{ progress, isUploading, error }` triple describing exactly one `XMLHttpRequest`.

The backend endpoint `POST /api/v1/documents` (`src/document_service/api/v1/documents.py:42`) takes `file: UploadFile = File(...)` plus a `purpose` form field — one document per request. Users bulk-ingesting a corpus must repeat the whole click-select-wait cycle per file.

Constraints shaping the design:

- The document service contract must not change — it is consumed by other flows and specced separately under document-ingestion.
- `useUpload` is also unit-tested directly (`src/portal/src/hooks/use-upload.test.tsx`) and its `upload(file, purpose)` signature must keep working so those tests and any other callers stay green.
- Existing `DocumentUpload.test.tsx` single-file drop/validation/drag-state tests must keep passing — they encode the current spec's scenarios, which the delta spec retains verbatim for the single-file path.
- Auth token is fetched per request via `getAccessToken()`; long batches must re-read it per file rather than capture it once.

## Goals / Non-Goals

**Goals:**

- Accept 1–20 files per interaction, via both multi-select picker and multi-file drop.
- Validate each file independently; a bad file never blocks its valid siblings.
- Upload sequentially against the unchanged single-file endpoint.
- Report per-file progress plus batch position, and a per-file failure list at the end.
- Allow cancelling the remainder of a batch without rolling back what already landed.
- Zero change to backend, document table, filter tabs, polling, and soft delete.

**Non-Goals:**

- Concurrent/parallel uploads (explicitly deferred; see Decision 2).
- A batch endpoint accepting `List[UploadFile]` on the document service.
- Per-file `purpose` selection — one `purpose` per batch.
- Retry-failed-files UI, drag-a-folder recursion, resumable/chunked uploads, or rollback of already-uploaded documents on cancel.
- Server-side deduplication of repeat filenames.

## Currently-In-Force ADRs

All eight ADRs in `docs/adr/` are `Status: Proposed`; only ADR-008 declares a `Supersedes` (ADR-002, partially). None of them govern portal upload UI or the document service request shape.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via separate DB schemas | None directly — upload requests already carry the tenant-scoped bearer token; batching changes request count, not tenant resolution. Each file's request must still go through the normal authenticated path so schema routing is unchanged. |
| ADR-004-openspec-governance | Spec-driven development; specs are source of truth | This change ships as a delta spec against `portal-documents`; implementation must not diverge from the delta's scenarios. |
| ADR-002, ADR-003, ADR-006, ADR-007, ADR-008 | Base model strategy, serving topology, training infra, chatbot/RAG architecture, base model as default | Not applicable — no model, inference, or retrieval surface is touched. |

No in-force ADR needs revisiting for this change.

## Decisions

### Decision 1: Batch orchestration lives in the component; `useUpload` keeps its single-file contract

**Choice:** Keep `useUpload().upload(file, purpose)` as the single-file primitive, unchanged in signature and behaviour. Add batch state (queue, per-item status, per-item error, current index, cancel flag) in `DocumentUpload`, driving `upload()` once per queued file in an `await` loop. Extend the hook only additively — an `abort()`/cancel affordance surfaced from the existing `xhrRef`, which `reset()` already calls `abort()` on.

**Rationale:** The hook's existing tests and its `{ progress, isUploading, error }` shape describe one in-flight request; redefining them to mean "batch" would break `use-upload.test.tsx` and any other caller. Sequential upload means the hook's single-request state is exactly right for "the current file" — the component supplies the surrounding batch context.

**Alternatives considered:**
- Rewrite `useUpload` into `useBatchUpload` returning per-file progress arrays — ruled out: breaks the hook's existing tests and contract for no functional gain under sequential upload.
- Add a second hook `useBatchUpload` wrapping the first — ruled out for now as an extra indirection layer; the loop is a dozen lines in the component. Worth extracting only if a second call site appears.

### Decision 2: Sequential upload, concurrency 1

**Choice:** Exactly one `XMLHttpRequest` in flight at a time. Next file starts only after the previous settles (resolve or reject).

**Rationale:** Progress attribution stays trivial (`progress` = current file's bytes), failures are naturally isolated, cancel is a single `abort()` plus loop break, and the document service sees the same request rate as today. Ingest is asynchronous server-side anyway — files land in `pending` and are processed by the worker — so parallel upload would shorten the client-side transfer window but not end-to-end processing time.

**Alternatives considered:**
- Bounded parallelism (3 concurrent) — ruled out: needs per-slot progress state and a more complex cancel path, for a speedup that mostly shifts queueing from the client to the ingest worker. Natural follow-up if batch wall-clock becomes a real complaint.
- Unbounded `Promise.all` over the selection — ruled out: 20 simultaneous multipart uploads risk connection-pool and gateway body-size pressure, and progress UI becomes meaningless.

### Decision 3: Per-file validation up front, then upload only the valid subset

**Choice:** On drop/change, partition the selection: run the existing `validate()` (MIME allowlist + 50MB) over each file, mark invalid ones with their reason, enqueue only valid ones. Then run the sequential loop. The 20-file cap is checked *before* partitioning and rejects the whole selection.

**Rationale:** The user sees every client-side rejection immediately rather than discovering them one at a time as the batch crawls forward. Reusing the existing `validate()` verbatim guarantees the single-file validation scenarios in the spec keep their exact behaviour.

**Alternatives considered:**
- Validate lazily inside the loop — ruled out: delays feedback about a file the client already knows is bad.
- Reject the whole selection if any file is invalid — ruled out: the proposal explicitly requires partial success, and it is the hostile behaviour for a 20-file drop with one stray `.DS_Store`.
- Cap by total bytes instead of file count — ruled out as harder to explain in an error message; per-file 50MB already bounds each request, and 20 files is the user-facing unit.

### Decision 4: Batch cap of 20 rejects the whole selection

**Choice:** A selection of more than 20 files uploads nothing and shows one inline error.

**Rationale:** Silently truncating to the first 20 would be a data-loss-shaped surprise — the user would believe all files were queued. An explicit all-or-nothing rejection makes the user re-split deliberately.

**Alternatives considered:**
- Upload the first 20 and warn about the rest — ruled out: ambiguous which files landed.
- No cap — ruled out: a dropped folder of hundreds of files would start an unbounded sequential run with no guardrail.

### Decision 5: Per-file result list as the terminal state, replacing the single success flag

**Choice:** Replace `uploadSuccess: boolean` with a results array of `{ name, status: "pending" | "uploading" | "success" | "failed" | "cancelled" | "rejected", error?: string }`. Terminal UI renders counts plus the names and reasons of everything not successful. For a one-file batch the rendering collapses to today's single success indicator or single inline error, so the existing single-file tests and spec scenarios still hold.

**Rationale:** A boolean cannot express "3 of 5 succeeded". Keying the array by index over the original selection preserves file order in the UI, and filenames are the only identifier the user has before rows appear in the table.

**Alternatives considered:**
- Toast per file — ruled out: 20 toasts is spam, and the failure reasons scroll away.
- Only show failures — ruled out: users need positive confirmation of the count that landed.

### Decision 6: Invalidate the documents query per successful file

**Choice:** Keep the hook's existing `queryClient.invalidateQueries({ queryKey: ["documents"] })` on each HTTP 201 rather than moving it to end-of-batch.

**Rationale:** The table fills in progressively, which is the visible signal that a long batch is working. Auto-polling already refetches every 3s while anything is `pending`/`processing`, so the extra invalidations are within the existing request budget and no new polling behaviour is introduced.

**Alternatives considered:**
- Invalidate once at end of batch — ruled out: table looks frozen for the whole batch, and it would mean changing hook behaviour (Decision 1 says don't).

### Decision 7: Cancel aborts in-flight and drains the queue, no rollback

**Choice:** A cancel control appears while a multi-file batch runs. It sets a cancel flag checked by the loop before each iteration and calls `abort()` on the in-flight request. Files already uploaded stay uploaded; the user removes them with the existing per-row soft delete if unwanted.

**Rationale:** Rollback would mean issuing `DELETE /api/v1/documents/{id}` for each succeeded file, which needs the returned IDs, is itself failure-prone mid-cancel, and destroys documents the user may want to keep. Soft delete already exists as the deliberate removal path.

**Alternatives considered:**
- Cancel with rollback — ruled out per above: surprising destruction, extra failure modes.
- No cancel control — ruled out: a mistaken 20-file drop would otherwise be uninterruptible.

## Risks / Trade-offs

- [Sequential upload makes a 20 × 40MB batch slow; user may think the UI hung] → "file N of M" indicator plus live per-file percentage plus a cancel control make progress and escape visible at all times.
- [Aborting via `xhr.abort()` may surface as the hook's `onerror` path, mislabeling a cancel as "Network error during upload"] → track the cancel flag in the component and classify that file as `cancelled`, not `failed`; do not rely on the hook's error string to distinguish. Add an explicit test for this.
- [Existing `reset()` calls `xhrRef.current?.abort()`; calling `reset()` between files in a loop could abort the request just started] → call `reset()` once before the batch begins, not per iteration; per-file state lives in the component's results array.
- [Bearer token expiring mid-long-batch causes later files to 401] → token is read inside `upload()` per call (`getAccessToken()` on each invocation), so refreshes are picked up; a 401 is reported as that file's failure and the batch continues rather than dying silently.
- [Per-file query invalidation × 20 plus 3s auto-polling raises request volume on the documents list] → invalidations are debounced by React Query's own dedupe within a tick, and the list endpoint is already polled; measure only if the documents page shows lag.
- [Regression risk to the single-file path, which is the existing specced behaviour] → the delta spec keeps every original single-file scenario, and the existing `DocumentUpload.test.tsx` suite must pass unmodified except for additions.
- [Multi-file drop of a *folder* yields directory entries with empty `type`, which will be rejected as unsupported with a confusing message] → out of scope for this change; the MIME rejection message is accurate enough. Noted as a follow-up.

## Migration Plan

Frontend-only, no schema or API change, no data migration.

1. Extend `useUpload` additively with a cancel affordance (no signature change to `upload`).
2. Convert `DocumentUpload` to batch state; add `multiple` to the input; iterate all dropped/selected files.
3. Run the existing portal test suite — `DocumentUpload.test.tsx` and `use-upload.test.tsx` must pass without edits to their existing cases.
4. Add the new multi-file, mixed-batch, cap, partial-failure, and cancel tests.
5. Ship behind no flag — the single-file path is a strict subset of the new behaviour.

**Rollback:** revert the two component/hook commits. Nothing persisted changes shape, so no data cleanup is needed; documents uploaded via a batch are indistinguishable from single uploads server-side.

## Open Questions

- Should the 20-file cap be a constant in the component or come from portal config? Assumed a local constant alongside `MAX_SIZE` until a second consumer needs it.
- Folder drops (directory entries with empty MIME type) currently surface as "file type not supported". Acceptable for now; a dedicated message is a follow-up, not part of this change.
- No in-force ADR requires supersession for this change.
