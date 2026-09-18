## Why

An assistant answer names a candidate and shows a citation chip for the resume it came from. The chip is a dead end: it expands to a metadata card with a text snippet, and there is no way to see the document the answer is actually based on. A recruiter deciding whether to shortlist someone has to leave the conversation, find the file in the Documents library, and open it there — if they can find it at all, since a chat attachment is deliberately absent from that library.

The snippet is the weakest part of the evidence. It is a chunk boundary, not a page: it can begin mid-sentence, omit the table the number came from, and carry none of the layout that tells a reader whether "5 years" was a heading, a bullet, or a caption. The whole point of citing a source is that the reader can check it, and today they cannot.

Nothing about the platform makes this hard any more. `retention_mode` already abstracts where a document's bytes live, and the recently completed `uploader-scoped-chat-retrieval` change settled the question that blocked this work: a citation chip is now only ever shown for a document the asking user is allowed to see, so "can this user open what this chip cites?" has a known answer rather than an open policy question.

## What Changes

- **A new content endpoint on the document service** returns a document's original bytes, `Content-Disposition: inline`, resolving them from whichever store the document's recorded `retention_mode` implies — durable object storage, the working store, or a live re-read from the originating source.
- **A companion availability probe** answers, in one cheap row read, whether the original can be produced and how it should be rendered — so the portal never downloads 50MB to discover the original was released or the format needs converting.
- **Non-natively-renderable formats are converted to PDF server-side** (`.doc`, `.docx`, `.csv`, `.tif`/`.tiff`), so the viewer has exactly one rendering path instead of a per-format matrix. Conversion is on demand and its output is cached only where the document's own retention mode already permits platform storage.
- **The portal gains a document viewer**, opened from a citation chip, rendering PDFs with `pdfjs-dist` and images natively, scrolled to the cited page and highlighting the cited passage where the citation carries the offsets to do so.
- **Chat attachment chips become clickable too**, opening the same viewer. They sit directly above the citation chips in the same thread, and leaving them inert once citations open would read as a bug.
- **BREAKING (infrastructure):** the document service's runtime image gains a document-conversion toolchain. All Python services currently share one Dockerfile, so this introduces a second build target rather than inflating every service image by several hundred megabytes.
- **`pdfjs-dist` is added to the portal** — its first heavy frontend dependency, and the first requiring a web-worker bundling decision under Next.js.
- Content resolution moves out of the OCR worker into a module an HTTP route can import without dragging in chunking and the embedding service. The worker's existing names keep working.

## Capabilities

### New Capabilities

- `document-content-access`: serving a document's original bytes — the availability probe and the bytes route, how each retention mode resolves to bytes (including re-reading from a source adapter), server-side media-type coercion, and the closed set of distinct failure outcomes a caller can act on.
- `document-pdf-rendition`: converting a non-natively-renderable original to a PDF for viewing — which formats, that the rendition is derived and never replaces the original, where a rendition may and may not be persisted, and how conversion failure is reported rather than masked.
- `cited-document-viewer`: the in-chat viewer — opening from a citation or attachment chip, per-format rendering, page deep-linking and passage highlighting, the object-URL lifetime, the distinct unavailable states a reader sees, and keyboard and focus behaviour.

### Modified Capabilities

- `original-document-storage`: one added requirement — a document's bytes reach a client only by streaming through the application, and no storage URL, endpoint, bucket or credential is ever disclosed to one. This makes the "no presigned URL" property enforceable rather than folklore, and names the content-resolution boundary the new route shares with the processing worker.
- `chat-ui`: a citation chip with a document behind it opens the viewer rather than only expanding a metadata card; attachment chips open it too; a citation with no document still behaves as it does today.

## Impact

- `src/document_service/api/v1/documents.py` — the probe and bytes routes, and the authorization helper they share. These are the first routes in the module that must reach conversation-owned rows, so the blanket `conversation_id IS NULL` clause does not apply to them.
- `src/document_service/content_resolution.py` (new) — `resolve_content`, the store selection and the source-reopener registry, extracted from `services/ocr_worker.py`, which re-exports the old names so `blob_sync/reopen.py` and existing tests are unaffected.
- `src/document_service/main.py` — import the Azure reopener at startup. The registry is populated by import, and the API process does not import it today, so without this every source-only document reports as unreadable.
- `src/document_service/rendition/` (new) — the conversion boundary and its adapter.
- `Dockerfile` — a document-service build target carrying the conversion toolchain; `docker-compose.yml` points that service at it.
- `src/portal/package.json` — `pdfjs-dist`; `next.config.js` if the worker needs bundler configuration.
- `src/portal/src/components/documents/` (new) — the viewer; `src/portal/src/hooks/use-original-document.ts` (new) — fetch, object-URL lifetime, cancellation.
- `src/portal/src/components/chat/CitationChips.tsx`, `CitationCard.tsx`, `MessageThread.tsx` — chips open the viewer.
- `src/shared/observability/domain_metrics.py` — a declared family for view outcomes and one for conversion, both with finite label sets.
- Tests: new Python suites for the two routes, resolution per retention mode and the conversion boundary; new portal suites for the viewer and the chip wiring; an end-to-end test driving the real HTTP route, following the precedent set by `tests/test_chat_uploader_isolation_end_to_end.py`.
- **Unaffected by design:** the Documents library listing keeps excluding conversation-linked rows; the uploader-visibility rule is imported, not restated; the external PostgreSQL channel owns no documents and is untouched.

## Open Questions

- **Should `SYNC_ALLOWED_RETENTION` be revisited?** Azure Blob sync refuses `platform_blob`, and an `ephemeral` document loses its bytes at a terminal state. So for a tenant whose corpus arrives that way, "open original" either re-downloads from Azure on every view or never works at all. That may be the correct privacy posture — or it may be a retention default chosen before anyone could ask to see an original. The viewer is built to state the outcome honestly either way; the posture question is raised here rather than silently answered.
- **Where should conversion run?** In the request, or as a job the probe reports progress on? In-request is simpler and matches the honesty of the failure taxonomy; a job is kinder to a large `.docx` and avoids holding a request open. The assumption taken is in-request with a bounded timeout, revisited in design.
- **Is a rendition cache acceptable for `ephemeral` documents?** Caching a converted PDF of a document whose original was deliberately released would recreate durably what retention deleted. The assumption is no — renditions are cached only for `platform_blob` documents — but it is a privacy decision worth confirming rather than inferring.
