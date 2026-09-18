## Context

A citation chip today expands to a card holding a filename, a relevance score and a chunk of text. The document itself has never been reachable from the chat surface, and nothing in the platform serves original bytes over HTTP at all: the document service exposes create, list, metadata, extracted text and delete, and none of them returns a file.

Three properties of the existing system shape every decision below.

**Bytes live in three different places, and the document row already says which.** `retention_mode` is `platform_blob` (durable object storage), `ephemeral` (a working store, deleted at a terminal processing state with the reference nulled) or `source_only` (nothing stored; re-read from the originating adapter). The processing worker already resolves all three. A viewer that re-derives this would be a second implementation of a rule the `original-document-storage` capability says must be recorded once and never re-derived.

**The storage boundary is deliberately narrow.** That same capability requires the content store expose exactly three operations and forbids it disclosing buckets, endpoints, regions, credentials or the key-construction rule. A presigned URL is not a missing feature here — it is a prohibited one, and adding a URL-minting operation would breach a shipped requirement.

**The portal cannot authenticate a subresource.** The access token lives in a React ref and is attached as a bearer header by `authFetch`; the document service rejects anything without it. A browser cannot put a header on an `<iframe src>` or `<img src>`, so the only shape available is fetch → blob → object URL, which the CSV export path already uses.

The authorization question that blocked this work is now answered. `uploader-scoped-chat-retrieval` made every chat answer channel apply one shared visibility rule, so a chip is only rendered for a document its reader may see. The viewer's job is to apply the same rule at the byte boundary rather than trust that upstream filtering held.

## Goals / Non-Goals

**Goals:**

- Open the original document behind a citation chip, in place, scrolled to the cited page.
- One rendering path in the client, achieved by converting on the server rather than branching per format in the browser.
- Honest, distinguishable outcomes when the original cannot be produced — particularly separating "permanently released by your own retention policy" from "the source is temporarily unreachable".
- Reuse the visibility rule rather than restating it, and enforce it at the byte boundary.
- Attachment chips and citation chips behave alike, because they sit in the same thread.

**Non-Goals:**

- Editing, annotating or re-uploading from the viewer. It is a reader.
- A presigned-URL or direct-to-storage download path. Prohibited by `original-document-storage`.
- Making the Documents library render documents. The library keeps excluding conversation-linked rows; this change adds no UI there, though the viewer component is placed so a later change could reuse it.
- Changing what retention modes tenants use, or which the Azure sync permits. Raised as an open question, not decided here.
- Text-layer search inside the viewer, or any client-side OCR.
- Extraction-quality or highlight-accuracy work beyond what the citation's own offsets already support.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 Tenant Data Isolation (topology partly superseded by ADR-017) | Schema-per-tenant, enforced below the caller | The content routes resolve the schema from authenticated state; a document id from a chip never selects a tenant |
| ADR-007 Chatbot Architecture | The answer pipeline spans vector and relational channels | Citations can originate from either; the viewer must work from a `document_id` alone and degrade when there is none |
| ADR-011 Conversation-Scoped Chat Attachments | Attachments are conversation-owned `documents` rows, hard-deleted with the conversation | The viewer must reach conversation-owned rows, which every existing document route deliberately excludes |
| ADR-012 Durable Azure Blob Source Synchronization | Synced documents are pointers; bytes are re-acquired from the source | `source_only` viewing re-reads through the registered reopener, and inherits its failure modes |
| ADR-014 Mandatory Conversation-Scoped Retrieval | Scoping is a caller-invisible guardrail applied to every channel | The byte boundary is a new channel and inherits both the conversation and uploader rules |
| ADR-017 Tenant-Owned PostgreSQL Data Plane | `documents` may resolve to a tenant-owned database | Authorization must be expressible inside the tenant schema — no join to `public.*`, and none to `conversations`, which may not be co-located |

## Decisions

### Decision 1: Two routes — a probe and the bytes

**Choice:** `GET /api/v1/documents/{id}/content/status` returns JSON describing whether the original can be produced, how it should be rendered, and its size. `GET /api/v1/documents/{id}/content` returns the bytes.

**Rationale:** Without the probe, the only way to learn that an original was released, or that a `.docx` needs converting, is to start downloading it. The probe answers from one row read and never opens the store. It is also where "this needs conversion, which will take a moment" can be said before the client commits to a request — which matters once conversion is in the picture. Keeping the description out of the bytes route also stops that route needing a status code to mean two things at once.

**Alternatives considered:**
- One route, with the client inferring from headers. Ruled out: a 50MB download to discover a permanent failure, and no place to report a render mode before transfer begins.
- `HEAD` on the bytes route. Ruled out: a structured reason and a render mode do not belong in headers, and `HEAD` cannot carry a JSON body explaining why an original is gone.

### Decision 2: Bytes stream through the service; the store's shape is never disclosed

**Choice:** The route reads bytes via the content-resolution boundary and returns them itself. No URL, bucket, endpoint or credential appears in any response, and the `original-document-storage` capability gains a requirement saying so.

**Rationale:** The three-operation boundary is a shipped requirement, so this is the only conforming shape. Writing it into the spec converts a property currently held only by the absence of code into one a test can enforce — the same reason the uploader rule was given a single definition. It also keeps `source_only` working, where there is no platform object to sign a URL for at all.

**Alternatives considered:**
- Add `generate_presigned_url` to the store. Ruled out: breaches the "exactly three operations" requirement, and is unimplementable for `source_only`.
- A short-lived signed URL minted by the application over its own route. Ruled out for now: it reintroduces a credential in a URL — which the chat export requirement already forbids for files — to solve a problem the blob-URL approach does not have.

### Decision 3: The served media type is decided by us, never echoed

**Choice:** The response `Content-Type` is the document's resolved type mapped through a small allow-list; anything unrecognised is served as `application/octet-stream`. `X-Content-Type-Options: nosniff` and a restrictive `Content-Security-Policy` accompany it.

**Rationale:** This is the security-critical line of the feature. `documents.content_type` is whatever the uploader's browser declared, and a blob URL inherits the portal's origin — the origin where the access token lives in JS memory. An original stored as `text/html` and rendered in a frame would execute script beside that token. Coercion server-side is the defence that does not depend on the client remembering anything.

**Alternatives considered:**
- Trust the stored type. Ruled out: it is attacker-influenced input.
- Sniff the bytes and trust the sniff. Ruled out as the sole control: sniffing is a heuristic, and the allow-list is what bounds the outcome. Sniffing is used to *resolve* the type, then the allow-list bounds what is served.

### Decision 4: Extract content resolution out of the OCR worker

**Choice:** A `content_resolution` module holds the store selection, the retention-mode resolution and the source-reopener registry. `ocr_worker` imports and re-exports the existing names.

**Rationale:** An HTTP route importing the worker pulls in chunking and the embedding service — the worker already does a lazy import to dodge a cycle. Extracting keeps the request path light while leaving exactly one implementation of the resolution rule. Re-exporting matters concretely: `blob_sync/reopen.py` registers through `ocr_worker.register_source_reopener`, and existing tests monkeypatch the worker's own attribute, so both must keep resolving.

**Alternatives considered:**
- Import the worker from the route. Ruled out: boots chunking and embeddings to read 20 lines of policy.
- Duplicate the resolution in the route. Ruled out for the reason this codebase has just spent a change fixing: two implementations of one rule drift.

### Decision 5: The reopener registry is populated at API startup

**Choice:** `src/document_service/main.py` imports the Azure reopener during startup, guarded so a missing SDK degrades to "not reopenable" rather than failing the process.

**Rationale:** The registry is a module dict filled as an import side effect. The Celery worker imports it at task time; the API process never does. Without this, every `source_only` document — which is *every Azure-synced document* — reports as unreadable, and the failure looks like a bug in the viewer rather than a missing import. This is the single easiest thing in the change to get wrong, because nothing else fails when it is missing.

### Decision 6: Convert to PDF on the server, in a separate image

**Choice:** `.doc`, `.docx`, `.csv`, `.tif`/`.tiff` are converted to PDF server-side and served as PDF. The toolchain lives in a document-service-specific Docker build target, not the shared runtime stage.

**Rationale:** Converting server-side gives the client exactly one renderer, which is what makes page deep-linking and highlighting uniform instead of per-format. The image split is not incidental: every Python service builds from one Dockerfile today, so adding the toolchain to the shared stage would inflate the model-serving, training and annotation images by several hundred megabytes for a capability none of them use.

**Alternatives considered:**
- Render each format in the browser. Ruled out by the user's decision, and it would mean a second renderer plus a `.doc` story the browser does not have.
- Fall back to extracted text for these formats. Ruled out by the user's decision; it also cannot deep-link, since `document_text_spans` carries no page number.
- Convert during ingestion. Ruled out: it would produce and store a rendition for every document whether or not anyone ever views one, including for tenants whose retention mode forbids storing anything.

### Decision 7: Renditions are cached only where the original is already stored

**Choice:** A converted PDF may be persisted only for a `platform_blob` document. For `ephemeral` and `source_only`, conversion happens per request and the output is never written to a platform store.

**Rationale:** A cached rendition is a durable, readable copy of the document's content. Writing one for an `ephemeral` document would recreate exactly what that tenant's retention policy deleted, and for `source_only` it would store bytes the tenant chose never to place in platform storage. Retention mode is the tenant's statement about durability, and a cache is not exempt from it.

### Decision 8: The blob URL is owned by a plain hook, not the query cache

**Choice:** A dedicated hook owns the fetch, the object URL and its revocation, with an abort on re-open. The probe and any text metadata may use React Query; the bytes may not.

**Rationale:** An object URL is a resource with a lifetime, not a cached value. Caching one means either revoking on unmount and leaving the cache holding a dangling string that renders as a broken frame, or never revoking and leaking the buffer for the session. Revocation must also go through a ref rather than a closed-over state value, so a rapid reopen revokes the generation it created rather than the current one.

### Decision 9: Authorization is the shared rule plus row-local attachment ownership

**Choice:** Both routes resolve the document with the tenant predicate, the shared uploader-visibility predicate from `src/shared/document_visibility.py`, and — for a conversation-owned row — a check against `uploaded_by` on that same row. No join to `conversations`.

**Rationale:** Reusing the predicate is the whole point of having given it one definition. The attachment case is expressible row-locally because ingestion writes `uploaded_by` and `conversation_id` in the same insert, so the document row already knows who attached it; a conversation has exactly one owner, making this equivalent to — and stricter than — checking conversation ownership. Avoiding the join is what keeps the routes correct under ADR-017, where `documents` may resolve to a database `conversations` is not in.

## Risks / Trade-offs

- [**Stored XSS via the blob URL** — a blob URL inherits the portal origin, where the access token lives in memory; an original served as `text/html` or SVG and framed would run script beside it] → Server-side media-type coercion to an allow-list, `nosniff`, a restrictive CSP on the response, and the client re-typing the Blob from the probe's value rather than the response's. Three independent controls because this is the failure with the worst outcome.
- [**Conversion is arbitrary-input parsing of untrusted files**, historically a rich source of RCE] → Run it in the document-service image only, with no network egress needed, a bounded timeout, and a size ceiling. Treat a conversion crash as a reported failure, never a retry loop.
- [**For some tenants the feature may never work.** Azure sync forbids `platform_blob`, and `ephemeral` releases the original at a terminal state, so a chip may always land on "the original was not retained"] → The failure taxonomy says so precisely rather than showing a generic error, and the posture question is raised as an open question rather than answered by the viewer's design.
- [**Memory: up to 50MB per concurrent view**, because `ContentStore.open` returns `bytes` by contract and a streaming operation would need a fourth boundary operation the spec forbids] → Accept for now, add the size to the probe so the client can decline, and instrument it; revisit only with measurements.
- [**Conversion latency inside a request**] → Bounded timeout, the probe reporting that conversion is required so the viewer can show the right waiting state, and a distinct timeout outcome rather than a generic failure.
- [**pdf.js worker bundling under Next.js** is a known sharp edge, and a misconfigured worker fails at runtime in the browser rather than at build time] → Pin the version, configure the worker explicitly rather than relying on a CDN default, and cover it with a test that asserts the worker source is configured — jsdom cannot render a PDF, so the build-time contract is what is testable.
- [**A citation with no `document_id`** — SQL and entity-derived citations have none] → The chip keeps today's behaviour and never offers to open a document that does not exist.

## Migration Plan

1. Extract `content_resolution`, with `ocr_worker` re-exporting. Pure refactor; the existing worker and blob-sync tests passing unchanged is the proof.
2. Register the Azure reopener at API startup, with a test asserting the registry is populated once the app is constructed.
3. Add the probe route, then the bytes route for natively-renderable formats only (`platform_blob` and `source_only`). Useful on its own, and independently revertible.
4. Add the conversion boundary behind the probe's render mode, then the Docker build target, then point compose at it. The image change lands last so a rollback is a compose edit rather than a rebuild.
5. Portal: the hook, then the viewer, then the chip wiring. Each is separately testable, and the chips change last so nothing is clickable before it can open.
6. **Rollback:** the portal change is a revert; the routes are additive and can be left in place unused. No data is written by this change except optional renditions, which are derived and safe to delete.

## Open Questions

- **Should the Azure sync's retention restriction be revisited** now that users can ask to see originals? Carried from the proposal. It is a product and privacy decision, not a design one, and the viewer behaves correctly under either answer.
- ~~**In-request conversion or a job?**~~ **Resolved: in-request**, bounded at 20 seconds and 25MB of input, with timeout reported as its own outcome. A job would add a state machine and a polling contract for a case measured in seconds. The probe remains the natural place to report progress if that changes.
- ~~**May a rendition be cached for an `ephemeral` document?**~~ **Resolved: nothing is cached at all.** The capability permits reuse for a retained document but does not require it, so the conservative reading costs only latency, while a cache that has to be correct about retention costs a privacy incident when it is not. `tests/test_document_rendition.py` asserts the module writes to no store, on the source as well as on behaviour, because a cache added later without a retention gate is exactly the mistake worth guarding.
- **Does the viewer belong in the Documents library too?** Out of scope here, but the component is placed under `components/documents/` rather than `components/chat/` so that a later change does not have to move it.
