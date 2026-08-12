# Keka Integration — Research Document

> **Status:** Research / Decision-support (no code written)
> **Scope:** Feasibility of integrating Keka HRMS as the first external data source for the NER platform's provider-agnostic external document ingestion architecture.
> **Evidence convention:** `Confirmed` = demonstrated via Keka MCP OpenAPI server, official Keka docs (developers.keka.com), or first-party code in this repo. `Inferred` = reasonable conclusion from confirmed facts, not directly demonstrated. `Unknown` = not yet demonstrated; needs verification during build.
> **Source of truth:** `external-data-source-ingestion-source-of-truth.md` (architecture), `AGENTS.md` (process invariants).

---

## 1. Executive Summary

- **Keka can be integrated today** as a document source using its **REST API** (`GET /hris/employees/documents`, attachment download URL, document types). Document objects expose only `id`, `name`, `attributes` (custom fields), and `attachments` — **no timestamp, no checksum, no size, no MIME type** in the list payload. `Confirmed`
- The **Keka MCP server** (`https://developers.keka.com/mcp`) is a read-only **OpenAPI discovery wrapper** (tools: `list-endpoints`, `get-endpoint`, `search-endpoints`, `list-specs`, plus endpoint invocation). It is a research/agent surface, not a production integration surface — live calls via `execute-request` require OAuth credentials configured in the MCP client. `Confirmed`
- **Recommended strategy:** production sync over Keka REST with OAuth2 (`scope=kekaapi` + `api_key`); MCP stays a dev/research tool. Polling-based sync with per-employee `lastModified` + full document-list diff; **document-level change detection is weak** because no document timestamp or document-change webhook was found. `Confirmed` (gap) / `Inferred` (strategy)
- **Webhooks:** exist in Keka but are **manually configured in the Keka UI** (Settings → Communications → Event Triggers); payload is form-encoded `employeeIndentifier`, `eventType`, `subDomain`. **No document-upload/document-change event is documented**, so webhooks can accelerate employee-level events but cannot replace document polling. `Confirmed`
- **Architecture gap in our platform:** the `tenant_{tid}.documents` table has no `source_id` / `external_id` / `source_modified_at` columns, and there is no connector/state layer. These must be added **provider-agnostically** before any external ingestion. `Confirmed`
- The existing ingestion pipeline (MinIO upload → `documents` row → OCR → `document_text_spans`/`document_chunks` → extraction → RAG) is fully reusable; the connector only needs to produce normalized `ExternalDocument`s and reuse the existing document-service ingestion path. `Confirmed`

## 2. Context & Goals

- The NER platform is a multi-tenant, FastAPI microservice stack (document service, extraction service, chat/RAG API, gateway, training) backed by PostgreSQL + pgvector, MinIO, Redis/RabbitMQ + Celery.
- Goal: ingest HR documents (offer letters, ID proof, payslips, etc.) from Keka into the existing document → OCR → extraction → RAG pipeline, per tenant, with idempotent re-syncs.
- Constraint: the ingestion architecture must stay **provider-agnostic** (Keka is the first source; the normalized interface is the contract).

## 3. Scope

**In scope:** Keka API surface relevant to documents; auth; pagination; rate limits; webhooks; MCP feasibility; mapping to the normalized `ExternalDocument` model; gaps in the platform schema; recommended strategy; open questions.

**Out of scope (by design):** Keka payroll, leave, attendance, performance, recruitment API details; Marketplace/partner commercial process (noted where relevant); any code or migration.

## 4. Keka MCP — What It Is

- **Endpoint:** `https://developers.keka.com/mcp` (configured in `~/.config/opencode/opencode.jsonc`, `enabled: true`). `Confirmed`
- **Server:** name `Keka API`, version `1.0`, protocol `2025-03-26`; exposes **no resources / no resource templates**. `Confirmed`
- **Tools (from `tools/list`):** `list-endpoints`, `get-endpoint`, `search-endpoints`, `list-specs`, plus a couple of endpoint-call tools (e.g. `execute-request`). It is an **OpenAPI-readme wrapper** over the same `developers.keka.com` docs. `Confirmed`
- **Live data access:** `execute-request` returns `This endpoint requires OAuth authentication. Please authenticate via your MCP client settings.` — so **no tenant data is reachable without Keka credentials**, even through the MCP. `Confirmed`
- **Specs exposed (from `list-specs`):** Core HR, Document, KEKA API, identity, identity-app-portal, keka-api-format, Payroll, Leave, Attendance, Expense, PMS, PSA, Requisition, Skills, Helpdesk, Assets, BGV APIs, Keka Hire API, Test API, and a few duplicates/aliases. `Confirmed`

**Judgment:** Use the MCP for **discovery, spec exploration, and agent-assisted integration work**. Do **not** build the production connector on MCP — it is a protocol indirection over the same REST API, requires OAuth anyway, and is undocumented as a production surface. `Confirmed` (facts) / `Inferred` (judgment)

## 5. Keka REST — Document APIs (the production surface)

All under base `https://{subdomain}.keka.com/api/v1`. `Confirmed`

| Endpoint | Purpose | Key params | Notes |
|---|---|---|---|
| `GET /hris/employees/documents` | List an employee's documents | `employeeId` (uuid, required), `documentTypeId` (uuid, optional), `pageNumber`, `pageSize` (default 100, max 200) | Returns `EmployeeDocumentDtoPagedResponse`. `EmployeeDocumentDto`: `id`, `name`, `attributes` (CustomField[]: `id`, `title`, `type`, `value`), `attachments` (DocumentAttachmentDto[]: `id`, `name`). **No timestamp, checksum, size, or MIME type.** |
| `GET /hris/employees/documents/attachment` | Get a **temporary download URL** for one attachment | `employeeId`, `documentId`, `attachmentId` | Returns `DocumentFileUrlDtoResponse { succeeded, message, errors, data: { fileURL } }`. Second authenticated request; the fileURL is time-limited. |
| `GET /hris/documents/types` | Document-type taxonomy | — | Use to filter/organize (e.g., only "ID Proof", "Offer Letter"). |
| `POST /hris/employees/documents` | Upload a document | `employeeId`, `documentTypeId` | Returns `GuidResponse`. Useful if we ever need write-back (out of scope now). |
| `GET /hris/employees` | List employees (paging/filtering) | `employeeIds`, `employeeNumbers`, `employmentStatus` (Working, Relieved), `inProbation`, `inNoticePeriod`, `lastModified` (ISO 8601), `searchKey` (min 3 chars), `pageNumber`, `pageSize` | `lastModified` filter exists **at employee level only**. |
| `GET /hris/webhooks/retrylogs` | Inspect webhook delivery logs | `continuationToken`, `webhookId`, `eventId`, `eventName`, `createdFromUtc/ToUtc`, `lastRetryFromUtc/ToUtc`, `status` | Uses **continuation-token** pagination (different from page-based). |

**Security scheme (documented in OpenAPI):** OAuth2, `authorizationUrl: https://login.kekad.com/connect/authorize`, scope `kekaapi`. `Confirmed`

### 5.1 Identity / token flow (official docs)
- Credentials: `client_id`, `client_secret`, `api_key`, scope `kekaapi`. `Confirmed`
- Token endpoint: **Production** `https://login.keka.com/connect/token`; **Sandbox** `https://login.kekademo.com/connect/token`. `Confirmed`
- Request: `POST` form-urlencoded `grant_type`, `scope`, `client_id`, `client_secret`, `api_key`. Default `grant_type` is `kekaapi`. `Confirmed`
- Python note from Keka docs: send header `"user-agent": "Mozilla"` when calling Keka APIs. `Confirmed`
- The MCP `identity-app-portal` spec shows a **refresh-token** `POST /connect/token`; the API-key client flow above is the customer-facing one per official docs. `Confirmed`

### 5.2 Pagination
- All Keka list APIs are paginated. **Defaults:** page number 1, page size 100 (max 200). `Confirmed`
- Response envelope carries `pageNumber`, `pageSize`, `firstPage`, `lastPage`, `totalPages`, `totalRecords`, `nextPageReference`, `previousPageReference`; **`nextPageReference == null` means last page**. `Confirmed`

### 5.3 Rate limits
- **50 requests/minute per endpoint**, refilled every 60 seconds; HTTP `429` with reason `rateLimitExceeded`. `Confirmed`
- A compliant connector needs client-side throttling (per-endpoint bucket) + backoff on 429. `Inferred` (implementation)

### 5.4 Scopes & privileges
- Documented scopes: Employee And Org Information, Leave, Attendance, Payroll, Timesheet, Performance. `Confirmed`
- **No `Document` scope is listed**; the document endpoints belong to HRIS/employee data → **likely "Employee And Org Information"**. `Inferred`
- Keka API is a **paid add-on**; only a **Global admin** can generate/manage API keys; keys can select scopes/privileges and an optional expiry. `Confirmed`

### 5.5 Webhooks
- Configured **manually in the Keka UI** (Settings → Communications → Event Triggers) → Add Webhook Action (URL, optional headers). `Confirmed`
- Delivery: `POST` with form-encoded params `employeeIndentifier`, `eventType`, `subDomain`. `Confirmed`
- Documented event names are **employee-level** (e.g. `EmployeeSalaryUpdated`, `leaverequestcreated`). **No document-upload/update/delete event found.** `Confirmed` (examples) / `Unknown` (full event catalog)
- `GET /hris/webhooks/retrylogs` gives delivery visibility with continuation-token paging. `Confirmed`
- **No API to create/update webhook subscriptions was found** (search for `subscription` → no matches). Webhooks are an ops-managed accelerator, not the primary sync mechanism. `Confirmed` (no API) / `Inferred` (strategy)

### 5.6 Sandbox / partner access
- Sandbox available via the **App Portal** (`appbuilder.keka.com`) for App Portal users, plus a separate **demo environment** (`login.kekademo.com`); CSMs can issue sandboxes for partner engagements. `Confirmed`
- Partner process: App Portal app listing is required to ship on the Marketplace; client credentials are issued per app; **commercial approval is separate from technical access**. `Confirmed`
- For our platform: per-customer Keka tenants are provisioned by the customer's Global admin; we need client creds + `api_key` per tenant. `Inferred`

## 6. Existing Platform — Document Pipeline (what we reuse)

All `Confirmed` from repo code.

1. **Upload:** `POST /api/v1/documents` (multipart) in `src/document_service/api/v1/documents.py`.
   - Max 50 MB; content-type allowlist (pdf/jpg/jpeg/png/tif/tiff); purposes `query` / `training`.
   - Role gating: `tenant_admin` → training+query; `business_user` → query only.
   - **Checksum:** SHA-256 of raw bytes via `src/document_service/services/content_hash.py` → `documents.checksum VARCHAR(64)`. Dedup is checksum-based (index `ix_documents_checksum`, migration `034`).
   - Inserts `tenant_{tid}.documents` (id, tenant_id, filename, content_type, file_size, checksum, blob_path, status=`pending`, purpose, uploaded_by) and **triggers OCR** asynchronously.
2. **Storage:** `src/document_service/services/storage.py` `MinioStorageClient` — key `tenants/{tenant_id}/documents/{document_id}.{ext}`.
3. **OCR:** `src/document_service/services/ocr_worker.py` → `document_text_spans`; if purpose=query, chunks (`src/shared/retrieval/chunking.py`, tiktoken cl100k, size 512 / overlap 128) → `document_chunks` with embeddings → **RAG-ready**.
4. **Extraction:** `src/extraction_service` (batch worker via Celery; eligibility = status `processed` + purpose `query`; already-extracted skip keyed on `model_version`).
5. **RAG:** `src/chat_api/services/rag_orchestrator.py` (HybridRetriever dense+sparse, CrossEncoder reranker).
6. **Config:** `src/shared/config.py` — env prefix `NER_`, retry defaults (initial 0.5s, ×2, max 10s, total 30s), `chunk_size`/`chunk_overlap`/`embedding_model`, service URLs. **No secret has a default value; absent env fails at startup** (AGENTS.md invariant).

**Documents table columns (migrations 002/003/030 + code):** `id, tenant_id, filename, content_type, file_size, blob_path, checksum, status, purpose, uploaded_by, error_message, updated_at, created_at` (+ legacy `mime_type, file_size_bytes, storage_uri, ocr_applied_flag`). **No external-source fields.**

## 7. Normalized ExternalDocument Mapping

Per the source-of-truth doc:

| ExternalDocument field | Keka mapping | Evidence |
|---|---|---|
| `source_id` | `"keka"` (provider-agnostic: Keka is the first provider value) | design |
| `external_id` | `"{employeeId}:{documentId}:{attachmentId}"` — the **attachment** is the real file; a document can have multiple attachments | `Confirmed` (schemas) / design (composite) |
| `filename` | `attachment.name` | `Confirmed` |
| `content` | bytes downloaded from `GET /hris/employees/documents/attachment` → `data.fileURL` (temporary URL) | `Confirmed` |
| `content_type` | **Not exposed by Keka**; derive from extension (pdf → `application/pdf`, png/jpg, etc.) | `Confirmed` (absent) / design |
| `modified_at` | **Not exposed** on the document DTO; employee-level `lastModified` exists. Set `modified_at = sync_time` for now; revisit if Keka adds document timestamps. | `Confirmed` (absent) / `Inferred` |
| `checksum` | Compute SHA-256 of downloaded bytes (reuse `compute_content_hash`) | design |

**Idempotency:** dedup key = `(source_id, external_id)`; second key = `checksum` (matches existing upload dedup). A re-sync of unchanged documents must be a no-op.

## 8. Sync Strategies

### 8.1 Full sync (initial backfill)
- Page `GET /hris/employees` → for each employee page `GET /hris/employees/documents` → for each attachment `GET .../attachment` → download → hash → normalize → ingest.
- Respect pagination (nextPageReference-null) and 50/min rate limit.

### 8.2 Incremental sync (steady state)
- Per-employee cursor on `lastModified` (employee-level, ISO 8601). For each changed/new employee, re-fetch the **full document list** and diff by `external_id` + checksum.
- **No document-level timestamp or event exists** → document-level incrementality is not possible yet; document diff cost is bounded by per-employee list calls. `Confirmed` (no timestamp) / `Inferred` (strategy)

### 8.3 Webhooks (optional accelerator)
- If Keka adds/document document events, webhooks can trigger targeted pulls; `webhooks/retrylogs` aids delivery debugging. Today: rely on polling. `Confirmed` (retrylogs, no doc event) / `Inferred`

### 8.4 Deletions
- **No deletion signal** (no tombstone event, no `deletedAt` on document DTO). Strategy: periodic reconciliation where documents in DB (by external_id) absent from the source are marked (soft-deleted / `status='deleted'`) or flagged for review — needs a product decision. `Confirmed` (no signal) / `Inferred` (strategy)

## 9. Recommended Strategy

1. **Production connector = Keka REST + OAuth2** (`client_id`, `client_secret`, `api_key`, scope `kekaapi`; token endpoint by environment; `user-agent: Mozilla` header).
2. **MCP** stays a research/agent tool only.
3. **Polling-based sync**, per tenant, scheduled (Celery beat or similar):
   - full backfill first, then incremental by employee `lastModified` + document-list diff.
4. **Reuse existing ingestion path:** normalized `ExternalDocument` → MinIO upload → `documents` row → OCR → spans/chunks → extraction → RAG. No second RAG pipeline.
5. **Add provider-agnostic schema:** `source_id`, `external_id`, `source_modified_at` (nullable), unique constraint on `(source_id, external_id)`, and a connector-state table (`source_id`, per-tenant cursor, `last_sync_at`, status/error).
6. **Secrets per tenant** from env (NER-prefixed), never hardcoded; per-tenant Keka credentials belong to each customer's Keka tenant.

## 10. Architectural Gaps (platform changes required)

| Gap | Detail | Evidence |
|---|---|---|
| No `source_id` / `external_id` columns | `tenant_{tid}.documents` has none; unique `(source_id, external_id)` prevents duplicate ingestion | `Confirmed` |
| No connector/state layer | No cursor, last_sync, error tracking | `Confirmed` (grep: no external/connector symbols in `src/`) |
| No sync scheduling/trigger | Upload is user-triggered; external sync needs a scheduler | `Confirmed` |
| No source-side content-type | Keka gives none → derive from extension | `Confirmed` |
| No source-side modified_at | `modified_at` = sync time fallback | `Confirmed` |
| No document-deletion signal | Soft-delete/reconcile policy needed | `Confirmed` |
| uploaded_by semantics | External docs have no user; needs `uploaded_by='system'` or nullable + source attribution | design |

## 11. Insertion Points (code)

- **New:** `src/external_ingestion/` (or per source `src/external_ingestion/sources/keka/`) with connector + state store. `design`
- **Reuse unchanged:** `document_service.services.storage` (MinIO), `content_hash`, `ocr_worker` (`process_document`), extraction batch worker, RAG retrievers, `shared.retrieval.chunking`.
- **Touch minimally:** document-service ingestion path to accept `(bytes, metadata)` where metadata carries `source_id/external_id/source_modified_at` instead of only the multipart form; role gate stays for user uploads, system ingest bypasses role checks but records `uploaded_by = 'system'`. `design`
- **Envelope contract** per source-of-truth doc: `ExternalDocument(source_id, external_id, filename, content, content_type, modified_at, checksum)`.

## 12. Secrets & Configuration

- Env (NER_ prefix), no defaults, fail-fast at startup per AGENTS.md:
  - `NER_KEKA_ENVIRONMENT` (`production` | `sandbox`)
  - `NER_KEKA_API_BASE_URL` (per-tenant subdomain)
  - `NER_KEKA_CLIENT_ID`, `NER_KEKA_CLIENT_SECRET`, `NER_KEKA_API_KEY`
- Per-tenant credential lookup at sync time; store tenant→credential mapping in a secrets vault / env per tenant, not in code. `design`

## 13. Failure Modes & Resilience

- **429 / rateLimitExceeded:** per-endpoint throttling (≤50/min), exponential backoff honoring `Retry-After`; queue-based sync tolerates slow refills. `Confirmed` (limits) / design
- **Expired/revoked API key or token:** token refresh + clear error surfaced to tenant admin; keys revoked in Keka UI by Global admin. `Confirmed` (key model)
- **Temporary attachment URL expiry:** re-request `.../attachment` before download; treat download failure as retryable. `Inferred`
- **Partial page failures / continuation:** resume-safe sync using per-employee cursor + page cursors; store last successful cursor. `design`
- **Idempotency:** `(source_id, external_id)` + checksum dedup ensures re-sync is a no-op; no double OCR (existing model-version skip also applies). `Confirmed` (existing dedup) / design
- **Keka outages:** retry with backoff (platform defaults 0.5s→10s, 30s cap are tight for 50/min bucket; connector should use a longer, bucket-aware window). `Inferred`

## 14. Rate Limit Budget Example

- 50 req/min/endpoint. Initial sync for T tenants × N employees: documents lists cost ~(employees/200) calls each; attachment URL calls = #attachments. A 5-employee pilot with ~20 attachments ≈ 25 calls — trivially within limits. A large tenant (500 employees, ~2000 attachments) needs sequential/scheduled batches. `Inferred` (arithmetic on confirmed limits)

## 15. Open Questions

1. Does the document DTO ever expose `createdAt`/`modifiedAt`? (Would enable true incremental sync.) `Unknown`
2. Does Keka expose MIME/size anywhere (attachment download HEAD)? `Unknown`
3. Is there a document-level webhook event in the full (undocumented) catalog? `Unknown`
4. Does downloading the `fileURL` require the OAuth bearer, or is the URL public while valid? `Unknown` (assume bearer required)
5. Can a `documentTypeId`-scoped sync be done? Yes — `documentTypeId` filter confirmed. `Confirmed`
6. Multi-attachment handling: one document row per attachment, or one row per document? Recommend per-attachment (external_id includes attachmentId). `design`
7. Deletion UX: auto-soft-delete vs flag-for-review. Product decision. `design`
8. Keka sandbox tenant availability for our dev environment (partner process or paid add-on). `Inferred` (docs) / needs account access
9. Does the API-key grant-type (`kekaapi`) match the `identity` spec in the MCP, or only official docs? Official docs are authoritative here. `Confirmed` (docs) / minor risk
10. Per-tenant credential lifecycle: who provisions and rotates? Ops process needed. `design`

## 16. Risks

| Risk | Level | Mitigation |
|---|---|---|
| No document-level change timestamp → possible missed/duplicated sync work | Medium | Employee-level lastModified + full list diff + checksum; acceptable at current scale |
| Rate limits on big initial backfills | Medium | Bucket-aware scheduler, sequential batches, resume cursors |
| Temporary download URL expiry mid-sync | Low | Re-request on failure |
| Webhook unreliability/absence for documents | Low-Medium | Polling is primary; webhooks optional |
| Keka API is paid add-on / per-tenant provisioning | Medium (go-to-market) | Customer Global admin enables; document in onboarding |
| Content-type misclassification | Low | Extension-based mapping + platform allowlist check at ingest |
| `modified_at` fallback = sync time may cause unnecessary re-embeds | Low-Medium | Skip re-embed when checksum unchanged (already the dedup path) |

## 17. Out of Scope (Noted)

- Keka payroll/leave/attendance/timesheet/performance/reporting APIs (leave & attendance exist in MCP specs; intentionally out of document-ingestion scope).
- Keka Hire (recruitment) API — separate domain.
- Marketplace listing / commercial process (technical feasibility unaffected).

## 18. Verification Plan (future, when building)

- **Sandbox POC:** provision Keka sandbox → create employee → upload docs (via UI or `POST /hris/employees/documents`) → connector syncs → assert documents appear in tenant DB, OCR, extraction, RAG retrievability.
- **Idempotency test:** re-run sync → zero new rows, no re-embed.
- **Change test:** upload a new attachment → next sync picks it up (external_id diff).
- **Rate-limit test:** verify ≤50 req/min/endpoint, 429 handling.
- **Failure test:** revoke key → clean error + retry; kill mid-sync → resume from cursor.

## 19. Sources

- Keka MCP server (`https://developers.keka.com/mcp`) — `list-specs`, `list-endpoints`, `get-endpoint`, `search-endpoints`, `execute-request` (auth-required error). `Confirmed`
- Keka official docs: `https://developers.keka.com/` (getting started, authentication, pagination, rate limits, scopes, webhooks, sandbox, partner process). `Confirmed`
- Keka API reference: `https://developers.keka.com/reference/employeedocuments`, `.../getting-started-with-your-api`, `.../clients`. `Confirmed`
- This repo: `src/document_service/**`, `src/shared/retrieval/chunking.py`, `src/shared/config.py`, `src/extraction_service/**`, `src/chat_api/services/rag_orchestrator.py`, `alembic/versions/002_003_030_034`, `src/gateway/**`. `Confirmed`
- `~/.config/opencode/opencode.jsonc` (Keka MCP config). `Confirmed`

## 20. Final Judgment (decision support)

1. **MCP vs REST:** Use **REST** for the production connector; MCP for research/dev only.
2. **Webhooks:** Optional; **polling is the primary mechanism** until a document event exists.
3. **Sync:** Full backfill then incremental (employee `lastModified` + document-list diff + checksum).
4. **Mapping:** `source_id=keka`, `external_id={employeeId}:{documentId}:{attachmentId}`, filename=attachment.name, content_type=derived, modified_at=sync-time fallback, checksum=SHA-256.
5. **Schema:** add `source_id`, `external_id`, `source_modified_at` (unique on source_id+external_id) + connector-state table — provider-agnostic.
6. **Reuse:** MinIO, content_hash, ocr_worker, extraction batch, RAG, chunking unchanged.
7. **Secrets:** NER_KEKA_* env vars, fail-fast, per-tenant credential mapping.
8. **Verdict:** **Proceed** — feasible with modest, provider-agnostic schema + connector-layer additions; biggest external unknowns are document timestamps and the full webhook event catalog, both non-blocking.
