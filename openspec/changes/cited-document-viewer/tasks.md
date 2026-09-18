## 1. Content resolution extraction

- [ ] 1.1 Create `src/document_service/content_resolution.py` holding `store_for`, `resolve_content`, `resolve_content_for_processing`, the source-reopener registry and `register_source_reopener`, moved from `services/ocr_worker.py`. The module must import without pulling in chunking or the embedding service. (scenarios: "Processing and delivery resolve identically", "Reading bytes does not require the processing pipeline")
- [ ] 1.2 Re-export the moved names from `ocr_worker` at module level, so `blob_sync/reopen.py`'s `ocr_worker.register_source_reopener(...)` and the existing monkeypatch of `ocr_worker._resolve_content_for_processing` both still resolve. (scenario: "Existing callers are unaffected by the extraction")
- [ ] 1.3 Add `has_source_reopener(source_type)` so a caller can distinguish "no adapter for this source" from "the adapter failed", which `reopen_azure_blob_content` cannot express because it swallows every exception. (scenario: "An unreachable source is transient and says so")
- [ ] 1.4 Add `tests/test_content_resolution_module.py` — identity between the worker's names and the shared ones, registration through either path, resolution per retention mode, and an import-isolation assertion. (scenarios: rows for "Processing and delivery resolve identically", "Reading bytes does not require the processing pipeline", "Resolution follows the recorded retention mode")
- [ ] 1.5 Run `tests/test_retention_lifecycle.py`, `tests/test_ingestion_boundary.py`, `tests/test_data_plane_task_retry.py` and the blob-sync suites unchanged. Their passing is the proof the refactor preserved behaviour. (scenario: "Existing callers are unaffected by the extraction"; Risk 7)

## 2. Adapter registration in the serving process

- [ ] 2.1 Import the Azure reopener during document-service startup, guarded so a missing SDK degrades to "not reopenable" rather than failing the process. (scenarios: "The serving process has its adapters registered", "A missing adapter degrades rather than failing startup")
- [ ] 2.2 Assert in `tests/test_document_content_endpoint.py` that constructing the application leaves the pull-source adapter registered — checked against the real startup path, not a fixture that registers one. (scenario: "The serving process has its adapters registered"; Risk 2)

## 3. Telemetry

- [ ] 3.1 Declare content-access and conversion metric families in `src/shared/observability/domain_metrics.py` with enumerated retention-mode, outcome and format-category labels, and named recorders that coerce out-of-set values. No label may carry a stored media type. (scenarios: "Metric labels are finite and declared", "Conversion is observable as shape")
- [ ] 3.2 Add `tests/test_document_content_telemetry.py` — declared label sets, out-of-set coercion, and that no emitted record contains a filename, storage reference or document content. (scenarios: "An access is recorded as shape", "Metric labels are finite and declared", "Conversion is observable as shape")
- [ ] 3.3 Confirm `scripts/telemetry_scan.py` passes with the new families and call sites.

## 4. Authorization for content access

- [ ] 4.1 Add a shared document-loading helper for the content routes: tenant predicate, the uploader-visibility predicate imported from `src/shared/document_visibility.py`, and for a conversation-owned row a check against `uploaded_by` on that same row. No join to `conversations`, no control-plane table. Do not apply the blanket `conversation_id IS NULL` clause the other routes use. (scenarios: all six authorization scenarios, "The rule has one definition")
- [ ] 4.2 Add `tests/test_document_content_authorization.py` — own document, another user's, own attachment, another user's attachment, another tenant, missing-vs-forbidden distinction, and a captured-SQL assertion that no statement names a `public.` table or `conversations`. (scenarios: rows 14–20 of the content-access capability; Risk 6)

## 5. The availability probe

- [ ] 5.1 Add `GET /api/v1/documents/{id}/content/status` returning availability, render mode, size and — when unavailable — the enumerated reason. It must not open the content store. (scenarios: "The probe describes a viewable document", "The probe reports a released original without transferring anything", "The probe reports that conversion is required")
- [ ] 5.2 Derive `render_mode` from the coerced media type, not the stored one, so the client is told how to render by the same authority that decides what is served. (scenario: "The rendered type is the one the system declared")

## 6. The bytes route

- [ ] 6.1 Add `GET /api/v1/documents/{id}/content` returning the bytes with `Content-Disposition: inline`, a coerced `Content-Type` from a closed allow-list, `X-Content-Type-Options: nosniff` and a restrictive `Content-Security-Policy`. Never echo `documents.content_type`. (scenarios: "A retained original is returned byte for byte", "A stored active-content type is not served as active content", "Content-type sniffing is disabled", "A supported format is served as itself"; Risk 1)
- [ ] 6.2 Resolve bytes through `content_resolution` for all three retention modes, including the source reopen path, and assert nothing is written to a platform store on the source-only path. (scenarios: "A source-only document is viewable", "No bytes are retained after a source-only view", "Resolution follows the recorded retention mode")
- [ ] 6.3 Implement the closed failure taxonomy — not found, not permitted, original released, original missing, source not reopenable, source unreachable, conversion failed, too large — each with its own machine-readable code, and none altering the document's derived data. (scenarios: the four failure scenarios plus "Existing derived data survives a failed view")
- [ ] 6.4 Assert no response is a redirect and none carries a storage location header. (scenarios: "The response discloses no storage detail", "A content response carries bytes, not a location")
- [ ] 6.5 Add `tests/test_document_content_endpoint.py` covering the above against real Postgres and a stub content store, including the HTML-typed document and the byte-identical round trip. (scenarios: the content-access rows not covered by 4.2)
- [ ] 6.6 Add a guard test asserting no caller of the content store produces a URL for a client. (scenario: "No pre-authorized URL is minted")

## 7. PDF rendition

- [ ] 7.1 Add `src/document_service/rendition/` with a conversion boundary and one adapter, converting `.doc`, `.docx`, `.csv`, `.tif`/`.tiff` to PDF and preserving page structure. Bounded by time and input size. (scenarios: the four "viewable as PDF" / "not converted" scenarios)
- [ ] 7.2 Treat the rendition as derived: never write back over the original's bytes, media type, checksum or storage reference, and keep the original obtainable as a download. (scenarios: "Conversion does not alter the document record", "The original remains obtainable")
- [ ] 7.3 Gate rendition persistence on retention mode — permitted for `platform_blob` only, never for `ephemeral` or `source_only`. (scenarios: "No rendition is stored for a released original", "No rendition is stored for source-only content", "A rendition may be reused for a retained document"; Risk 3)
- [ ] 7.4 Remove a stored rendition when the document is hard-deleted, alongside the existing content deletion. (scenario: "Deleting the document removes its rendition")
- [ ] 7.5 Report conversion failure and timeout as distinct outcomes; never return unconverted bytes under a PDF media type, and never change the document's processing status. (scenarios: the four conversion-failure scenarios; Risk 4)
- [ ] 7.6 Add `tests/test_document_rendition.py` covering conversion per format, derivation, retention gating, deletion and every failure path. (scenarios: the rendition capability's rows)
- [ ] 7.7 Resolve the open question on whether conversion stays in-request or becomes a job; record the decision in `design.md` before implementing 7.1. (design Open Questions)

## 8. Image and deployment

- [ ] 8.1 Add a document-service build target to `Dockerfile` carrying the conversion toolchain, leaving the shared runtime stage unchanged. (scenario: "Only the converting service carries the toolchain")
- [ ] 8.2 Point `document_service` (and any worker that converts) at the new target in `docker-compose.yml`; leave every other service on the shared target.
- [ ] 8.3 Add `tests/test_conversion_toolchain_placement.py` asserting the toolchain appears only in the converting service's image definition. (scenario: "Only the converting service carries the toolchain")

## 9. Portal: fetching and holding the document

- [ ] 9.1 Add `pdfjs-dist` to `src/portal/package.json`, pinned, and configure its worker explicitly rather than relying on a CDN default. (Risk: pdf.js worker bundling)
- [ ] 9.2 Add `src/portal/src/hooks/use-original-document.ts`: probe, then fetch bytes with `authFetch`, build the Blob using the probe's media type, create an object URL, abort in-flight work on change, and revoke through a ref rather than a closed-over value. The bytes must not enter the React Query cache. (scenarios: the six "fetched as authenticated data" and "releases what it holds" scenarios; Risk 5)
- [ ] 9.3 Add `src/portal/src/hooks/use-original-document.test.ts` following the `ExportCard.test.tsx` recipe — mock `@/lib/auth-fetch`, stub `URL.createObjectURL`/`revokeObjectURL`, assert one revoke per created URL under rapid reopen. (same scenarios)

## 10. Portal: the viewer

- [ ] 10.1 Add `src/portal/src/components/documents/OriginalDocumentViewer.tsx` on `SlideOver` and `useFocusTrap`: PDF via pdf.js, images natively, opening at the cited page and highlighting the cited passage where offsets exist. Place it under `documents/` so the library can reuse it later. (scenarios: the five rendering scenarios)
- [ ] 10.2 Render each unavailability outcome as its own message, distinguishing permanent from retryable, and offer the extracted text where it exists. (scenarios: the four "states why a document cannot be shown" scenarios)
- [ ] 10.3 Add `OriginalDocumentViewer.test.tsx` covering rendering, page deep-link, highlight, every unavailable state, Escape, focus return, focus containment and the dialog role. (scenarios: the rendering, unavailability and accessibility rows)

## 11. Portal: chip wiring

- [ ] 11.1 Lift the viewer state above the chip row in `CitationChips.tsx` so one viewer serves every chip in a message; a chip with a `document_id` opens it, one without keeps today's card behaviour. (scenarios: the four "citation chip opens" scenarios)
- [ ] 11.2 Keep the existing snippet and relevance detail reachable from a chip that also opens a document. (scenario: "The detail card remains reachable")
- [ ] 11.3 Make attachment chips in `MessageThread.tsx` open the same viewer. (scenarios: "Opening an attachment", "An attachment on a user message offers to open it")
- [ ] 11.4 Add `CitationChips.test.tsx` covering chip-opens-viewer, the no-document case, detail reachability, one-viewer-per-message and the attachment chip. (scenarios: the chips rows)
- [ ] 11.5 Confirm the existing chat-ui suites pass unchanged. (scenarios: "Send message and receive response", "Source citations are expandable")

## 12. End-to-end proof

- [ ] 12.1 Add `tests/test_cited_document_viewer_end_to_end.py` driving the real content routes over HTTP with a signed JWT: seed a document per retention mode plus an attachment, then assert each opens or fails with its own outcome, and that another user's document does not open. Follow the precedent of `tests/test_chat_uploader_isolation_end_to_end.py` — source inspection is not proof. (scenarios: the end-to-end rows)
- [ ] 12.2 Mutation-check the suite: force the visibility predicate permissive, and separately bypass the media-type allow-list; record which tests fail, then restore. A suite that cannot fail proves nothing. (verification.md § Mutation Check)

## 13. Verification & Evidence

- [ ] 13.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 13.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 13.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 13.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 13.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 13.6 Run `openspec validate cited-document-viewer --type change --strict` and confirm it exits clean before archive.
