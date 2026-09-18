# Verification Plan

**Change:** cited-document-viewer
**Generated:** 2026-09-18
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | chat-ui | Message thread display | Send message and receive response | Given a selected conversation, when a message is sent, then it appears optimistically, a loader shows, the response appears and the thread auto-scrolls | regression: existing chat-ui suite | - [ ] |
| 2 | chat-ui | Message thread display | Source citations are expandable | Given an assistant message with citations, when one is clicked, then it expands showing document_id or entity_type and snippet text | regression: existing chat-ui suite | - [ ] |
| 3 | chat-ui | Message thread display | A citation naming a document offers to open it | Given a citation carrying a document_id, when viewed, then an affordance to open the cited document is present | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 4 | chat-ui | Message thread display | A citation without a document offers no viewer | Given a citation with no document_id, when viewed, then no open affordance is present and details remain expandable | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 5 | chat-ui | Message thread display | An attachment on a user message offers to open it | Given a user message with an attachment, when viewed, then an affordance to open it is present | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 6 | chat-ui | Message thread display | Opening a document keeps the conversation in place | Given a thread scrolled to a message, when a document is opened and closed, then that message is still shown and no navigation occurred | end-to-end test: `tests/test_cited_document_viewer_end_to_end.py` | - [ ] |
| 7 | cited-document-viewer | A citation chip opens the document it cites | Activating a chip opens the viewer | Given an assistant message citing a viewable document, when the chip is activated, then the viewer opens on it and the conversation remains in view | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 8 | cited-document-viewer | A citation chip opens the document it cites | A citation without a document does not offer to open one | Given a citation with no document id, when its chip is activated, then the detail card is revealed and no viewer opens | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 9 | cited-document-viewer | A citation chip opens the document it cites | The detail card remains reachable | Given a chip that opens a document, when the user seeks the snippet and relevance detail, then it is still reachable | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 10 | cited-document-viewer | A citation chip opens the document it cites | One viewer serves many chips | Given several chips, when one then another is opened, then exactly one viewer exists and shows the most recent document | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 11 | cited-document-viewer | An attachment chip opens the file it represents | Opening an attachment | Given a user message with an attachment chip, when activated, then the viewer opens showing that file | component test: `src/portal/src/components/chat/CitationChips.test.tsx` | - [ ] |
| 12 | cited-document-viewer | The viewer renders the document, at the cited page | A PDF opens at the cited page | Given a citation identifying page 4, when opened, then the viewer displays page 4 first | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 13 | cited-document-viewer | The viewer renders the document, at the cited page | A citation with no page opens at the beginning | Given a citation with no page number, when opened, then the document displays from its first page | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 14 | cited-document-viewer | The viewer renders the document, at the cited page | The cited passage is indicated | Given a citation carrying the passage position, when that page is displayed, then the passage is visually distinguished | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 15 | cited-document-viewer | The viewer renders the document, at the cited page | An image document renders as an image | Given a cited browser-renderable image, when opened, then it is displayed as an image | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 16 | cited-document-viewer | The viewer renders the document, at the cited page | A converted document renders like a PDF | Given a cited document requiring conversion, when opened, then it renders through the same PDF path and page references behave identically | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 17 | cited-document-viewer | Document bytes are fetched as authenticated data, never as a subresource URL | The document is fetched with credentials | Given an authenticated user opening a document, when the bytes request is made, then it carries the caller's credentials | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 18 | cited-document-viewer | Document bytes are fetched as authenticated data, never as a subresource URL | No credential appears in a URL | Given the viewer displaying a document, when the address it renders from is inspected, then it contains no access token | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 19 | cited-document-viewer | Document bytes are fetched as authenticated data, never as a subresource URL | The rendered type is the one the system declared | Given a document whose stored type differs from the determined type, when rendered, then the system-reported type is used | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 20 | cited-document-viewer | The viewer releases what it holds | Closing releases the document | Given an open viewer, when closed, then the in-memory reference is released | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 21 | cited-document-viewer | The viewer releases what it holds | Opening another document releases the previous one | Given an open viewer, when a different document is opened, then the first reference is released and the second is shown | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 22 | cited-document-viewer | The viewer releases what it holds | A superseded request is abandoned | Given a document still loading, when another is opened first, then the first request is abandoned and does not replace the second | unit test: `src/portal/src/hooks/use-original-document.test.ts` | - [ ] |
| 23 | cited-document-viewer | The viewer states why a document cannot be shown | A released original is explained as permanent | Given a document whose original was not retained, when opened, then the viewer explains it was not retained and offers no retry | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 24 | cited-document-viewer | The viewer states why a document cannot be shown | An unreachable source invites a retry | Given a temporarily unreachable source, when opened, then the viewer explains it and offers to try again | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 25 | cited-document-viewer | The viewer states why a document cannot be shown | A failed conversion is distinguished from a missing original | Given a failed conversion, when opened, then the message differs from the not-retained message | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 26 | cited-document-viewer | The viewer states why a document cannot be shown | Extracted text is offered when the original cannot be shown | Given an unavailable original whose extracted text exists, when reported, then the extracted text is offered, labelled as extracted text | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 27 | cited-document-viewer | The viewer is operable from the keyboard | Escape closes the viewer | Given an open viewer, when Escape is pressed, then it closes | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 28 | cited-document-viewer | The viewer is operable from the keyboard | Focus returns to the originating chip | Given a viewer opened from a chip, when it closes, then focus returns to that chip | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 29 | cited-document-viewer | The viewer is operable from the keyboard | Focus stays within the open viewer | Given an open viewer, when focus cycles past its last focusable element, then it returns to the first rather than reaching the conversation | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 30 | cited-document-viewer | The viewer is operable from the keyboard | The viewer is announced as a dialog | Given an open viewer, when its accessible role is inspected, then it is a modal dialog with an accessible name identifying the document | component test: `src/portal/src/components/documents/OriginalDocumentViewer.test.tsx` | - [ ] |
| 31 | document-content-access | A document's original bytes are retrievable over HTTP | A retained original is returned byte for byte | Given a `platform_blob` document with stored bytes, when an authorized caller requests its content, then the identical bytes are returned with inline presentation | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 32 | document-content-access | A document's original bytes are retrievable over HTTP | The response discloses no storage detail | Given any successful content response, when status/headers/body are inspected, then no bucket, container, endpoint, region, credential or storage redirect appears | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 33 | document-content-access | A document's original bytes are retrievable over HTTP | Resolution follows the recorded retention mode | Given a `platform_blob` and an `ephemeral` document alike in all else, when each is requested, then each is read from the store its recorded mode implies | unit test: `tests/test_content_resolution_module.py` | - [ ] |
| 34 | document-content-access | Source-only content is re-read from its originating source | A source-only document is viewable | Given a `source_only` document with a registered adapter, when its content is requested, then bytes are returned and no platform store is read | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 35 | document-content-access | Source-only content is re-read from its originating source | The serving process has its adapters registered | Given the content-serving app as started in production, when the adapter registry is inspected after startup, then the supported pull-source adapter is present | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 36 | document-content-access | Source-only content is re-read from its originating source | A missing adapter degrades rather than failing startup | Given the adapter's dependencies unavailable, when the app starts, then startup succeeds and a source-only request reports the source cannot be re-read | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 37 | document-content-access | Source-only content is re-read from its originating source | No bytes are retained after a source-only view | Given a source-only document just viewed, when platform stores are inspected, then no copy of its bytes was written | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 38 | document-content-access | An availability probe answers before bytes are transferred | The probe describes a viewable document | Given a retained natively-renderable document, when probed, then availability, render mode and size are reported and no bytes are read | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 39 | document-content-access | An availability probe answers before bytes are transferred | The probe reports a released original without transferring anything | Given an `ephemeral` document whose copy was released, when probed, then it reports unavailable with the not-retained reason | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 40 | document-content-access | An availability probe answers before bytes are transferred | The probe reports that conversion is required | Given a retained non-natively-renderable document, when probed, then the render mode indicates conversion for display | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 41 | document-content-access | The served media type is determined by the system, never echoed from stored input | A stored active-content type is not served as active content | Given a document recorded as a script-bearing type such as HTML, when its content is requested, then the served type is an opaque binary type, not that type | security test: `tests/test_document_content_endpoint.py` | - [ ] |
| 42 | document-content-access | The served media type is determined by the system, never echoed from stored input | Content-type sniffing is disabled | Given any content response, when headers are inspected, then the client is instructed not to infer another type | security test: `tests/test_document_content_endpoint.py` | - [ ] |
| 43 | document-content-access | The served media type is determined by the system, never echoed from stored input | A supported format is served as itself | Given a stored PDF, when requested, then the response media type is the PDF type | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 44 | document-content-access | Content access applies the same visibility rules as every other answer channel | A user opens a document they may see | Given a document the requesting non-admin ingested, when they request its content, then the bytes are returned | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 45 | document-content-access | Content access applies the same visibility rules as every other answer channel | A user cannot open another user's document | Given a document ingested by a different human, when a non-admin requests it, then the request is refused and no bytes transferred | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 46 | document-content-access | Content access applies the same visibility rules as every other answer channel | A user opens their own attachment | Given a conversation-owned document the user attached, when they request its content, then the bytes are returned | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 47 | document-content-access | Content access applies the same visibility rules as every other answer channel | Another user cannot open someone's attachment | Given that attachment, when a different user of the same tenant requests it, then the request is refused | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 48 | document-content-access | Content access applies the same visibility rules as every other answer channel | Another tenant's document is not reachable | Given a document of a different tenant, when requested with this tenant's credentials, then it is refused as not found | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 49 | document-content-access | Content access applies the same visibility rules as every other answer channel | Authorization reaches no control-plane table | Given the statements executed while authorizing, when inspected, then none references a control-plane table or the conversations relation | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 50 | document-content-access | Content access applies the same visibility rules as every other answer channel | The rule has one definition | Given the content routes and the document listing, when their visibility predicates are inspected, then both derive from the same shared definition | guard test: `tests/test_document_content_authorization.py` | - [ ] |
| 51 | document-content-access | Every failure outcome is distinct and actionable | A released original is permanent and says so | Given an `ephemeral` document whose copy was released, when content is requested, then the outcome identifies the original as not retained, distinct from unreachable-source | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 52 | document-content-access | Every failure outcome is distinct and actionable | An unreachable source is transient and says so | Given a `source_only` document whose registered adapter fails, when requested, then the outcome identifies a temporarily unreachable source, distinct from no-adapter | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 53 | document-content-access | Every failure outcome is distinct and actionable | A missing document is not confused with a forbidden one | Given a nonexistent document id, when content is requested, then the outcome is not-found and differs from the forbidden outcome | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 54 | document-content-access | Every failure outcome is distinct and actionable | Existing derived data survives a failed view | Given any failed content request, when the document is inspected, then status, spans, chunks and retention mode are unchanged | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 55 | document-content-access | Content access is observable without recording document content | An access is recorded as shape | Given a successful content request, when telemetry is inspected, then it records retention mode and an enumerated outcome and no filename, reference or content | unit test: `tests/test_document_content_telemetry.py` | - [ ] |
| 56 | document-content-access | Content access is observable without recording document content | Metric labels are finite and declared | Given the content-access metric family, when its labels are inspected, then every value set is finite and enumerated and no label carries a stored media type | unit test: `tests/test_document_content_telemetry.py` | - [ ] |
| 57 | document-pdf-rendition | Formats a browser cannot render are converted to PDF for display | A word-processor document is viewable as PDF | Given a retained `.docx`, when requested for display, then a PDF is returned whose text corresponds to the original | integration test: `tests/test_document_rendition.py` | - [ ] |
| 58 | document-pdf-rendition | Formats a browser cannot render are converted to PDF for display | A spreadsheet-style upload is viewable as PDF | Given a retained `.csv`, when requested for display, then a PDF is returned | integration test: `tests/test_document_rendition.py` | - [ ] |
| 59 | document-pdf-rendition | Formats a browser cannot render are converted to PDF for display | A multi-page image is viewable as PDF | Given a retained multi-page TIFF, when requested for display, then a PDF with one page per frame is returned | integration test: `tests/test_document_rendition.py` | - [ ] |
| 60 | document-pdf-rendition | Formats a browser cannot render are converted to PDF for display | Natively renderable formats are not converted | Given a retained PDF and PNG, when each is requested, then neither is converted and each is served in its own format | integration test: `tests/test_document_rendition.py` | - [ ] |
| 61 | document-pdf-rendition | A rendition is derived, and never replaces the original | Conversion does not alter the document record | Given a converted `.docx`, when its record is inspected, then media type, checksum and storage reference are unchanged | integration test: `tests/test_document_rendition.py` | - [ ] |
| 62 | document-pdf-rendition | A rendition is derived, and never replaces the original | The original remains obtainable | Given that document, when the original is requested as a download, then the original bytes in the original format are returned | integration test: `tests/test_document_rendition.py` | - [ ] |
| 63 | document-pdf-rendition | A rendition is persisted only where the original is already persisted | No rendition is stored for a released original | Given an `ephemeral` document, when converted for display, then no rendition is written to any platform store | integration test: `tests/test_document_rendition.py` | - [ ] |
| 64 | document-pdf-rendition | A rendition is persisted only where the original is already persisted | No rendition is stored for source-only content | Given a `source_only` document, when converted for display, then no rendition is written and no bytes reside in platform storage afterwards | integration test: `tests/test_document_rendition.py` | - [ ] |
| 65 | document-pdf-rendition | A rendition is persisted only where the original is already persisted | A rendition may be reused for a retained document | Given a `platform_blob` document converted once, when requested again, then a reused rendition is equivalent to reconverting the original | integration test: `tests/test_document_rendition.py` | - [ ] |
| 66 | document-pdf-rendition | A rendition is persisted only where the original is already persisted | Deleting the document removes its rendition | Given a `platform_blob` document with a stored rendition, when hard-deleted, then the rendition is removed too | integration test: `tests/test_document_rendition.py` | - [ ] |
| 67 | document-pdf-rendition | Conversion is bounded and its failure is reported, never masked | A corrupt original fails explicitly | Given bytes the converter cannot parse, when requested for display, then the outcome identifies conversion as failed and no PDF is returned | integration test: `tests/test_document_rendition.py` | - [ ] |
| 68 | document-pdf-rendition | Conversion is bounded and its failure is reported, never masked | A conversion that exceeds its time bound is reported as such | Given a conversion exceeding its bound, when requested, then it is abandoned and a bounded-conversion failure is reported | integration test: `tests/test_document_rendition.py` | - [ ] |
| 69 | document-pdf-rendition | Conversion is bounded and its failure is reported, never masked | Unconverted bytes are never mislabelled | Given any conversion failure, when the response is inspected, then it does not carry the original's unconverted bytes under a PDF media type | integration test: `tests/test_document_rendition.py` | - [ ] |
| 70 | document-pdf-rendition | Conversion is bounded and its failure is reported, never masked | A failed conversion leaves the document untouched | Given a processed document whose conversion fails, when inspected, then status is still `processed` and spans and chunks are unchanged | integration test: `tests/test_document_rendition.py` | - [ ] |
| 71 | document-pdf-rendition | Conversion runs only where its toolchain belongs | Only the converting service carries the toolchain | Given the runtime image definitions, when inspected, then the conversion toolchain appears only in the converting service's image | image inspection: `tests/test_conversion_toolchain_placement.py` | - [ ] |
| 72 | document-pdf-rendition | Conversion runs only where its toolchain belongs | Conversion is observable as shape | Given a conversion that runs, when telemetry is inspected, then it records an enumerated format category, outcome and duration and no filename or content | unit test: `tests/test_document_content_telemetry.py` | - [ ] |
| 73 | original-document-storage | A document's bytes reach a client only by passing through the application | No pre-authorized URL is minted | Given the content-store boundary and its callers, when inspected, then none produces a URL from which a client could fetch bytes | guard test: `tests/test_content_resolution_module.py` | - [ ] |
| 74 | original-document-storage | A document's bytes reach a client only by passing through the application | A content response carries bytes, not a location | Given any response delivering bytes, when status and headers are inspected, then it is not a redirect and names no storage location | integration test: `tests/test_document_content_endpoint.py` | - [ ] |
| 75 | original-document-storage | A document's bytes reach a client only by passing through the application | Authorization precedes delivery | Given a request from a caller who may not see the document, when handled, then no bytes are read from any store and none transferred | integration test: `tests/test_document_content_authorization.py` | - [ ] |
| 76 | original-document-storage | Content resolution is shared by every reader of a document's bytes | Processing and delivery resolve identically | Given a document under any retention mode, when bytes are resolved for processing and for delivery, then both use the same resolution and the same store | unit test: `tests/test_content_resolution_module.py` | - [ ] |
| 77 | original-document-storage | Content resolution is shared by every reader of a document's bytes | Reading bytes does not require the processing pipeline | Given the content-resolution module, when imported, then chunking and embedding are not required for the import to succeed | unit test: `tests/test_content_resolution_module.py` | - [ ] |
| 78 | original-document-storage | Content resolution is shared by every reader of a document's bytes | Existing callers are unaffected by the extraction | Given prior callers including the pull-source adapter registration, when exercised, then they behave as before | regression: `tests/test_content_resolution_module.py` plus the existing retention and blob-sync suites | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Media-type coercion (design Decision 3) | The agent serves `documents.content_type` straight from the row because it is right for the common case. Every PDF and PNG test passes; the one input that matters — an original stored as `text/html` — is never exercised, and a blob URL then executes script in the origin holding the access token. | Read the route's `Content-Type` assignment. It must map through a closed allow-list, not read the column. Confirm the HTML-typed test exists and fails when the allow-list is bypassed. |
| 2 | Adapter registration at startup (design Decision 5) | The agent implements `source_only` resolution correctly and never imports `blob_sync.reopen` in the API process. Unit tests that register an adapter directly pass; every real Azure-synced document reports "not reopenable", and it looks like a viewer bug. | Start the app and inspect the registry, per the startup scenario. Confirm the import is in the application's startup path, not only in a test fixture. |
| 3 | Rendition caching vs retention (design Decision 7) | The agent adds a cache for all documents because caching is obviously good, silently recreating durable copies for `ephemeral` and `source_only` documents whose tenants opted out of exactly that. | Verify the cache write is gated on retention mode. Run the two "no rendition is stored" scenarios and confirm they fail if the gate is removed. |
| 4 | Conversion failure masking | The agent returns the unconverted bytes, or an empty PDF, when conversion fails — so the viewer shows a blank page instead of an error, and the failure is invisible in telemetry. | Read every conversion error path. Confirm none returns bytes. Run the corrupt-original and timeout scenarios. |
| 5 | Object-URL lifetime (design Decision 8) | The agent stores the blob URL in React Query because every other fetch in the portal uses it, then either revokes on unmount (leaving a cached dangling URL that renders as a broken frame on remount) or never revokes (leaking a buffer per view). | Confirm the bytes are not in the query cache. Exercise rapid open/close/reopen and assert `revokeObjectURL` is called once per created URL, with the URL created by that generation. |
| 6 | Authorization via a conversations join | The agent authorizes an attachment by joining `conversations`, which reads correctly and works in dev — then breaks for any tenant whose `documents` resolve to a tenant-owned database where that table is absent (ADR-017). | Capture the SQL executed while authorizing and assert it names neither a `public.` table nor `conversations`. |
| 7 | Extraction regression (design Decision 4) | Moving content resolution out of `ocr_worker` breaks the pull-source registration, which registers through the worker's own name, or the monkeypatch point existing tests rely on — neither of which the new tests would notice. | Run the existing retention-lifecycle, ingestion-boundary and blob-sync suites unchanged. They are the real proof the refactor was behaviour-preserving. |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation | Schema-per-tenant, enforced below the caller | A document id from a chip must never select a tenant | Run the cross-tenant scenario: another tenant's id returns not-found |
| ADR-007 Chatbot Architecture | Answers span vector and relational channels | Citations from either channel; the viewer works from `document_id` alone and degrades without one | Run the citation-without-a-document scenarios in the chips suite |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments are conversation-owned rows, hard-deleted with the conversation | The viewer reaches conversation-owned rows that every other document route excludes; deletion must also remove any rendition | Run the attachment authorization scenarios and the rendition-deletion scenario |
| ADR-012 Durable Azure Blob Source Synchronization | Synced documents are pointers; bytes re-acquired from source | `source_only` viewing re-reads through the adapter and writes nothing back | Run the source-only scenarios, including that no bytes are retained afterwards |
| ADR-014 Mandatory Conversation-Scoped Retrieval | Scoping is a caller-invisible guardrail on every channel | The byte boundary is a new channel and inherits the rules | Confirm the content routes apply the shared predicate; run the authorization suite |
| ADR-017 Tenant-Owned PostgreSQL Data Plane | `documents` may resolve to a tenant-owned database | Authorization expressible inside the tenant schema only | Capture executed SQL; assert no `public.` table and no `conversations` reference |

---

## 4. Evidence Requirements

### Functional Evidence

*(One item per row in Section 1.)*

- [ ] **End-to-end viewing** (rows covering the chip → open → render path): test output from `tests/test_cited_document_viewer_end_to_end.py`, driving the real content routes over HTTP with a signed JWT. Per the precedent set by the uploader-scoping change, this is what proves the feature — not source inspection.
- [ ] Content route, retained originals: byte-identical round trip, inline disposition, no storage detail in any response
- [ ] Content route, each retention mode: `platform_blob`, `ephemeral` released, `source_only` served and `source_only` unreachable
- [ ] Availability probe: viewable, released, and conversion-required cases, with no bytes read
- [ ] Media-type coercion: an HTML-typed document served as an opaque binary type, with sniffing disabled
- [ ] Authorization: own document, another user's document, own attachment, another user's attachment, another tenant, and the captured-SQL assertion
- [ ] Failure taxonomy: each enumerated outcome distinct, and derived data unchanged after every failure
- [ ] Conversion: `.docx`, `.csv` and multi-page TIFF to PDF; natively-renderable formats untouched; original unchanged and still obtainable
- [ ] Rendition retention: no rendition stored for `ephemeral` or `source_only`; reuse permitted for `platform_blob`; removed on hard delete
- [ ] Conversion failure: corrupt input, timeout, no mislabelled bytes, document untouched
- [ ] Image placement: conversion toolchain present only in the converting service's image
- [ ] Portal viewer: page deep-link, no-page default, passage highlight, image rendering, converted-document rendering
- [ ] Portal hook: credentialed fetch, no token in any URL, declared type honoured, release on close, release on replace, superseded request abandoned
- [ ] Portal unavailable states: released, unreachable, conversion failed, extracted-text fallback — each with its own message
- [ ] Portal accessibility: Escape, focus return, focus containment, dialog role and name
- [ ] Chips: opens viewer, no-document case, detail still reachable, one viewer for many chips, attachment chip
- [ ] Telemetry: enumerated labels only; no filename, storage reference or content in any record; `scripts/telemetry_scan.py` clean
- [ ] Regression: existing retention-lifecycle, ingestion-boundary, blob-sync and chat-ui suites pass unchanged

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — allow-list read in the route; HTML-typed document exercised
- [ ] Risk 2 mitigation confirmed — registry populated by application startup, not by a fixture
- [ ] Risk 3 mitigation confirmed — cache write gated on retention mode; gate removal fails the tests
- [ ] Risk 4 mitigation confirmed — no conversion error path returns bytes
- [ ] Risk 5 mitigation confirmed — bytes absent from the query cache; one revoke per created URL under rapid reopen
- [ ] Risk 6 mitigation confirmed — captured SQL names no control-plane table and no conversations relation
- [ ] Risk 7 mitigation confirmed — pre-existing worker and blob-sync suites pass unchanged

### Mutation Check

- [ ] The end-to-end and authorization suites demonstrably fail when the visibility predicate is forced permissive, and when the media-type allow-list is bypassed. A suite that cannot fail proves nothing; record which tests failed and restore the code afterwards.

### Decisions To Confirm Before Archive

- [ ] Whether a rendition may be cached for an `ephemeral` document (design Decision 7 assumes no)
- [ ] Whether conversion stays in-request or becomes a job (design assumes in-request with a bounded timeout)
- [ ] Whether the Azure sync's retention restriction should be revisited, given that a chip on such a tenant may never open

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** cited-document-viewer
**Proposal:** `openspec/changes/cited-document-viewer/proposal.md`
**Spec files reviewed:**
  - specs/document-content-access/spec.md
  - specs/document-pdf-rendition/spec.md
  - specs/cited-document-viewer/spec.md
  - specs/original-document-storage/spec.md
  - specs/chat-ui/spec.md

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
