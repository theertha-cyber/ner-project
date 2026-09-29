# Requirements — Multi-Tenant Custom NER Platform (v2)

> Supersedes `requirements.md` (v1, approved 2026-06-03). This revision inlines v1 in full and merges in
> everything shipped since — ~150 OpenSpec change packages and ADR-008 through ADR-019 covering external
> data sources, tabular file ingestion, chat attachments/citations/export/charts, hybrid RAG retrieval,
> entity resolution, LLM-assisted prelabeling, human-gated retraining, audit log UI, and local Docker
> Compose delivery. Sourced from `openspec/specs/` (durable source-of-truth per FR-15) and ADRs 001–019.
> No content is referenced by pointer only — every v1 section is reproduced with v2 additions merged in.

## 0. Document Control

| Field | Value |
|---|---|
| Status | Draft for review — **not yet approved** |
| Date | 2026-09-25 |
| Supersedes | requirements.md v1 (2026-06-03) |
| Author | Claude Code — BRD refresh, sourced from `openspec/specs/` and `docs/adr/` |
| **Approver / sign-off authority** | **NEEDS INPUT.** No approver is recorded anywhere in this repo's artifacts (v1 had none either — its "Status: Approved" names no approving party). Recommend: Product Owner + Architect per the existing Intent Gate (§14.1), but this must be named by the business, not assumed here. |
| **Target date for v2 approval** | **NEEDS INPUT.** No deadline exists in any spec, ADR, or changelog. Recommend the stakeholder set one; this document does not invent one. |
| **Budget / team capacity for closing the gaps in §16** | **NEEDS INPUT.** Not tracked anywhere in the codebase or OpenSpec artifacts — this is a business planning input, not something derivable from source. |
| **Regulated / classified data in scope** | **NEEDS INPUT, with what's known below.** See §6.3 (new) — the codebase enforces tenant isolation, TLS, and PII-leak telemetry scanning, but no spec or ADR states whether GDPR, HIPAA, PCI, or other regulated data categories are in scope, nor which jurisdictions/regions tenant-owned data planes must satisfy. This must be answered by legal/compliance, not inferred from code. |

---

## 1. Executive Summary

This document defines the requirements for a multi-tenant document intelligence platform where each tenant
can define domain-specific named entities, train a tenant-specific NER model, deploy that model in an
isolated runtime, and use extracted structured data for workflows, reporting, and agentic conversations.
Delivery is AI-native: OpenSpec governs requirements, design, tasks, and evidence as the source of truth;
OpenCode is the agentic engineering interface for planning, implementation, review, and validation under
human approval gates.

**v2 addition**: the platform now also lets tenants attach **external, tenant-owned data** — Azure Blob
document sources, external/tenant-owned PostgreSQL business data, and uploaded tabular files (CSV/XLSX) —
as first-class chat-queryable sources alongside NER-extracted entities, under a contract-governed,
read-mostly, SELECT-only query boundary. The chatbot has grown from "RAG over NER + structured data" into a
governed multi-source retrieval and SQL-generation system with hybrid search, reranking, citations, export,
and charting.

**Reference model**: dslim/bert-base-NER (single curated base model for all tenants), reaffirmed by
ADR-008. It recognizes standard CoNLL classes (PER, ORG, LOC, MISC). Tenant-specific extraction requires
custom labels, annotated training data, fine-tuning, evaluation, and model governance before deployment.

---

## 2. Business Objectives

- **Tenant-specific intelligence**: Allow each tenant to extract business-specific entities from its own
  document corpus without mixing data or model artifacts with other tenants.
- **Operational automation**: Convert unstructured documents into validated structured records stored in a
  tenant-scoped database.
- **AI-native delivery**: Build using OpenSpec-managed Spec-Driven Development and OpenCode-assisted
  engineering, with every implementation slice traceable to proposal, design, specification, task, and
  evidence artifacts.
- **Enterprise readiness**: Provide isolation, auditability, model versioning, rollback, observability, and
  secure data handling from the first release.
- **Bring-your-own business data** *(v2)*: Let tenants connect existing Azure Blob document stores and
  PostgreSQL databases (or tenant-owned data-plane stores) without duplicating platform ingestion, subject
  to strict read boundaries and residency rules.
- **Self-service data source administration** *(v2)*: Tenant Admins manage their own connections, sync
  schedules, and retention policy without System Admin involvement.
- **Governed generative SQL** *(v2)*: Any natural-language question answerable against structured/external
  data must go through contract-validated, SELECT-only SQL generation — never free-form execution.

---

## 3. Users and Personas

| Persona | Primary Goals | Key Permissions | Scope |
|---|---|---|---|
| Tenant Admin | Configure entities, upload seed documents, manage annotation workflow, request model training, approve models. **v2**: connect/validate/pause/retire external data sources (Azure Blob, external Postgres, tenant-owned data plane), manage sync schedules and retention mode. | Tenant-scoped configuration, datasets, model lifecycle actions, data source connections. | Tenant |
| Tenant Business User | Upload documents, trigger extraction, review results, search and query reports/chatbot. **v2**: attach files in chat composer, open cited source documents, export chat result rows, request charts. | Tenant-scoped document ingestion and consumption. | Tenant |
| System Admin | Provision tenants, monitor training jobs, approve deployment policies, manage infrastructure and quotas. **v2**: view tenant-filterable audit log. | Cross-tenant operational visibility without access to tenant document content by default. | Global |
| Data Annotator / Reviewer | Label entity examples, validate model outputs, correct extraction errors. **v2**: review LLM-assisted prelabels; Annotator Admin reviews the capped `initial` (≤5 doc) automated batch only — the `large` batch is auto-promoted with no review (ADR-013, see §11 contradiction resolution). | Tenant-scoped annotation and review queues. | Tenant |
| AI/ML Engineer | Tune training pipeline, evaluate model quality, promote/rollback model versions. | Model registry and MLOps permissions. | Global + Tenant |

**Identity model**: Tenant-scoped user directories. Each tenant manages its own users and roles
independently. System Admin exists in a global administrative domain outside any tenant.

**Access control gap (v2, flagged, unresolved in code)**: no spec was found stating which role(s) may
export chat results (FR-24), which role(s) may create a data source connection beyond "Tenant Admin"
generally (e.g. can a Business User request one, or only approve it), or whether embeddable-widget users
(distinct from internal chat users, per the 20 req/min widget rate limit in §6.2) may attach files or
export at all. **Needs a decision owner** — recommend Product Owner + Security.

---

## 4. Scope

### 4.1 In Scope

- Tenant onboarding and tenant-scoped storage, identity, roles, and quotas.
- Tenant admin page for entity type configuration, field definitions, examples, validation rules, and
  extraction targets.
- Document upload pipeline for PDF, DOCX, TXT, CSV (structured import only, no NER), images (JPEG, PNG,
  TIFF), and scanned PDFs where OCR fallback is enabled.
- Annotation workflow for creating BIO/IOB2 token classification datasets from uploaded documents.
- Tenant-specific model training/fine-tuning pipeline using a single curated base model
  (dslim/bert-base-NER).
- Model registry with versions, metrics, datasets, lineage, approval status, and rollback support.
- Separate runtime deployment per tenant, or logically isolated deployment pool where infrastructure
  constraints require pooling.
- Extraction pipeline that stores results in tenant-scoped relational tables and optionally a
  document/search index.
- Agentic chatbot and conversational reporting over extracted data with guardrails and source references.
  Chatbot uses a full RAG architecture: NER model + structured data + document search.
- **External data source connections** *(v2)*: Azure Blob, external/tenant-owned PostgreSQL, with a
  tenant-scoped connection control plane (connect, validate, activate, pause, retire).
- **Durable Azure Blob synchronization** *(v2)*: scheduled polling sync (15-minute cadence), manual
  on-demand sync trigger, one missed-schedule catch-up, source reconciliation.
- **Contract-governed external PostgreSQL query path** *(v2)*: read-only SQL generation against an
  externally-owned schema, executed under row/time caps, results never persisted.
- **Tenant-owned PostgreSQL data plane** *(v2)*: tenants may host their own residency-compliant Postgres
  store; platform provisions and routes to it, with explicit readiness/failure states.
- **Uploaded tabular files (CSV/XLSX) as chat-queryable data sources** *(v2)*, independent of the CSV
  structured-import path above — profiled, versioned, converted to Parquet, queried via locked in-process
  DuckDB.
- **Chat attachments** *(v2)*: users attach documents directly in the chat composer, scoped to that
  conversation.
- **Cited document viewer** *(v2)*: inline rendering of the exact source document/page/span behind a
  citation.
- **Chat export** *(v2)*: export the structured result rows behind an assistant answer to CSV/XLSX, where
  those rows came from the internal relational SQL generator (not external Postgres — see §11).
- **Chat chart generation** *(v2)*: assistant can render a chart from SQL result rows in the same turn.
- **Hybrid retrieval** *(v2)*: dense (pgvector HNSW) + sparse (Postgres full-text) fusion, cross-encoder
  reranking.
- **Entity resolution & normalization layer** *(v2)*: BIO reconstruction, WordPiece merge, alias-based
  disambiguation, typed structured entity values (number/date/money/duration/boolean).
- **LLM-assisted prelabeling** *(v2, verbatim-quote grounded)*, alongside baseline-model prelabeling.
- **Human-gated retraining governance** *(v2)*: dataset accumulation reporting is informational only; no
  automatic training job creation or model version promotion.
- **Confidence-routed review** *(v2)*: extraction-confidence and review-confidence are independent,
  separately configurable thresholds.
- **Audit log UI** *(v2)* for System Admins, tenant-filterable.
- **Observability/workload telemetry** *(v2)*: per-chat-stage spans, tenant-mismatch-safe metrics,
  PII-leak release-gate scan.
- **Local Docker Compose deployment topology** *(v2)* as the standard local/dev delivery mechanism (see
  §6.3 for the production-deployment gap).

### 4.2 Out of Scope for Initial Release

- Fully automated high-quality model creation without human annotation or validation.
- General-purpose document understanding for highly visual forms unless a layout-aware model is explicitly
  included.
- Cross-tenant model training using pooled tenant data unless tenants explicitly opt in.
- Regulated production certifications such as SOC 2 or ISO 27001, although architecture should not block
  later certification.
- Tenant-selectable or bring-your-own base model (single curated base model only).
- **Cross-source joins between uploaded tabular files** *(v2, not yet supported)*.
- **Model-authored ad hoc Python/pandas execution against tabular data** *(v2)* — DuckDB access is SQL-only
  and validated; no code execution path exists.
- **Free-form/unvalidated SQL execution against any external or tenant-owned store** *(v2)*.
- **Presigned-URL-based document delivery for the cited document viewer** *(v2)* — bytes stream through the
  app only, by design.
- **Production/cloud deployment topology** *(v2 gap, see §6.3)* — only local/dev Docker Compose exists
  today.

---

## 5. Functional Requirements

### 5.1 Core Platform (v1)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-01 | System Admin can create and manage tenants, quotas, runtime isolation policy, and admin users. | Must | A tenant can be provisioned with isolated storage, DB schema, and model namespace. See ADR-001 for isolation design. |
| FR-02 | Tenant Admin can define entity types, descriptions, examples, aliases, expected formats, required/optional flags, and target DB mapping. | Must | Entity definitions are versioned and validated before training. Fine-tuning uses the single base model per ADR-002. |
| FR-03 | Tenant users can upload documents in supported formats (PDF, DOCX, TXT, CSV, JPEG, PNG, TIFF) and view parsing status. | Must | Each uploaded document receives immutable metadata, storage path, checksum, and processing status. |
| FR-04 | System extracts text with page number, paragraph, token offsets, and OCR confidence where applicable (OCR fallback only when no native text layer exists). | Must | Training and extraction can trace every entity back to source document location. |
| FR-05 | Annotation UI supports manual labeling, pre-labeling from the baseline NER model, correction, and reviewer approval. | Must | Approved annotations can be exported to token classification format (BIO/IOB2). |
| FR-06 | System Admin or authorized Tenant Admin can trigger tenant-specific training. | Must | Training job captures dataset version, entity config version, base model, hyperparameters, and metrics. Training runs asynchronously on GPU workers per ADR-006. |
| FR-07 | Model evaluation calculates precision, recall, F1, entity-level metrics, confusion matrix, and minimum promotion thresholds. | Must | A model cannot be promoted unless thresholds and manual approval are satisfied. |
| FR-08 | Each tenant has an active model endpoint or isolated model serving route with version pinning. | Must | Extraction requests use the correct active tenant model version. Serving topology per ADR-003. |
| FR-09 | Runtime extraction stores entity values, confidence, normalized value, source span, model version, and review status. | Must | Every extracted record is auditable and correctable. |
| FR-10 | Tenant users can review extraction results and correct low-confidence or incorrect entities. | Should | Corrections are logged and can be fed back into future training datasets via an exportable correction queue. |
| FR-11 | Conversational UI (chatbot) can answer questions from extracted structured data, search source documents, and use NER model inference. It must cite document/entity sources with traceability. | Should | Responses are tenant-scoped, include source references, and are constrainable to tenant data only. Chatbot architecture per ADR-007 (full RAG with guardrails). |
| FR-12 | Reports provide entity coverage, extraction volume, confidence distribution, review backlog, and business metrics. | Should | Reports can be filtered by date, document type, entity type, and model version. |
| FR-13 | System shall maintain an OpenSpec change package for every product, platform, model, and chatbot capability before implementation starts. | Must | Each delivered slice links to openspec/changes/\<change-id\>/proposal.md, design.md, spec.md, tasks.md, and evidence/. Governance per ADR-004. |
| FR-14 | System shall use OpenCode-assisted engineering with bounded agents for planning, coding, review, QA, security, and MLOps tasks. | Should | OpenCode sessions reference AGENTS.md and task-specific agent instructions; generated changes are traceable to approved OpenSpec tasks. Agent boundaries per ADR-005. |
| FR-15 | System shall archive completed OpenSpec changes into source-of-truth specifications after implementation evidence is accepted. | Must | Completed changes are moved to archive and durable specs are updated to reflect current product behavior, APIs, data contracts, and operational rules. Governance per ADR-004. |

### 5.2 External Data Sources & Tabular Files (v2)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-16 | Tenant Admin can create, validate, activate, pause, and retire external data source connections (Azure Blob, external PostgreSQL, tenant-owned data-plane PostgreSQL). | Must | Connection status enum: `draft/validated/active/paused/error/retired`. At most one active Azure Blob document source, one active read-only Azure PostgreSQL connection, and one active Azure PostgreSQL data-plane connection per tenant concurrently. Activation requires typed config validation, resolvable secret reference, TLS-validated secure test, required network evidence, and applicable governance approval. Per ADR-011/ADR-017; `tenant-data-source-control-plane` spec:40. |
| FR-17 | System synchronizes tenant Azure Blob sources on a schedule and on manual trigger. | Must | Sync cadence 15 min; one missed-schedule catch-up run; manual `POST /api/v1/data-sources/{connection_id}/sync` requires `Idempotency-Key`. Per ADR-012; `azure-blob-source-sync` spec. |
| FR-18 | Chatbot can answer questions against tenant external PostgreSQL data via generated, contract-validated, SELECT-only SQL. | Must | Server row cap **100 rows**, 10-second statement timeout; AST validation rejects subqueries/CTEs/UNIONs/window functions and role-change statements; **results are response-only and never persisted in any platform table** — see §11 for the interaction with FR-24 export. Per ADR-013/ADR-016; `external-postgresql-chat` spec:59,82-93. |
| FR-19 | Tenants may provision a tenant-owned PostgreSQL data plane for residency-sensitive data; platform routes chat/content requests to it based on readiness. | Must | Data-plane status enum `awaiting_store/provisioning/provisioning_failed/ready/migration_required/paused/store_retired`; unready/unreachable routes fail with `409 TENANT_DATA_PLANE_NOT_READY` / `503 TENANT_DATA_PLANE_UNAVAILABLE`. Per ADR-017; `tenant-data-plane-routing`, `tenant-data-plane-failure-isolation` specs. |
| FR-20 | Tenant users can upload CSV/XLSX files as standalone, chat-queryable tabular data sources, distinct from the structured-import path (FR-03/§4.1). | Must | Each upload profiled, versioned, converted once to an immutable Parquet "query copy"; original retained separately. File status `profiling/needs_review/publishing/ready/failed/deleted`. Per ADR-018/ADR-019; migration `057_tabular_files.py`. **Size/row/column limits: not specified in any spec found — see §16.3 gap.** |
| FR-21 | Uploaded tabular files are queried only via a locked, in-process, SELECT-only DuckDB session — no persisted DuckDB file, no ad hoc code execution. | Must | DuckDB runs `:memory:`, per-query, external access disabled, memory/thread/time/row caps enforced; only ADR-016-validated SQL executes. |

### 5.3 Chat Platform (v2)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-22 | Users can attach documents directly in the chat composer, scoped to the active conversation. | Must | Supported types: pdf, jpg, jpeg, png, tif, tiff, doc, docx, csv. Conversation created on first send if none exists. Deleting a conversation hard-deletes its attachment documents, blobs, spans/chunks/entities. Per ADR-011 (conversation-scoped attachments); `chat-composer-attachments` spec. **Attachment size limit: not specified in any spec found — see §16.3 gap.** |
| FR-23 | Assistant responses that cite a source document must let the user open that exact document/page/span inline. | Should | Conversion targets doc/docx/csv/tif/tiff to PDF for viewing; no presigned URLs — bytes stream through the app. |
| FR-24 | Users can export the structured result rows behind an assistant answer to CSV or XLSX, when those rows came from the internal relational SQL generator over `document_entities`/`subject` tables. | Should | `GET /api/v1/chat/messages/{message_id}/export?format=csv|xlsx`; export snapshot persisted as `chat_messages.export_rows` in the same transaction as the message, capped at that generator's **1000-row `LIMIT`**, rendered on demand. A zero-row validated query is treated as "no structured retrieval" and produces no export card. Per ADR-014; `chat-export` spec:63. **Does not apply to external-Postgres-sourced answers (FR-18), which cannot be persisted at all — see §11.** |
| FR-25 | Assistant can render a chart from a query result set within the same conversational turn. | Should | `render_chart` tool; two-stage generation (non-streaming decision, then streaming narrative); gated on non-empty SQL results and an ordinary-answer outcome; numeric tolerance 1e-6; `chart` JSONB column on `chat_messages`. |

### 5.4 Retrieval & Entity Quality (v2)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-26 | Retrieval over tenant documents uses hybrid dense+sparse search with reranking. | Must | `HybridRetriever` fuses pgvector HNSW cosine dense search with Postgres `ts_rank` sparse search via Reciprocal Rank Fusion; default `retrieval_top_k=5`; cross-encoder rerank over top 20 candidates via model-serving `/internal/v1/rerank`, enabled by default with graceful fallback. Per `retrieval-core`, `retrieval-eval` specs. |
| FR-27 | All retrieval unconditionally excludes training-purpose document chunks and superseded/confirmed-missing documents. | Must | Non-overridable filter in every retriever; `purpose='training'` chunks and superseded/missing documents never surfaced to chat. |
| FR-28 | Extracted entities carry typed structured values, not just raw strings. | Should | Value kinds: text/number/duration/money/date/boolean; typed columns `value_number`, `value_number_high`, `value_unit`, `value_date`, `value_date_high` on `document_entities`. Per `structured-entity-values` spec. **Rollout to entities extracted before this feature shipped: not addressed in any spec — see §16.4 gap.** |
| FR-29 | System resolves and normalizes entity mentions (BIO reconstruction, subword merge, alias-based disambiguation) before storage. | Must | WordPiece `##` merging; entity confidence = min of constituent token confidences; alias-map lexical normalization. Resolution outcomes recorded as `unresolved/unique/ambiguous/over_cap`. Per `entity-normalization`, `entity-view-layer` specs. |
| FR-30 | Pre-labeling may use either the baseline NER model or an LLM, grounded strictly in verbatim source quotes. | Should | LLM route: exact case-insensitive substring match required; cached by content-hash + entity-config version. Per `llm-prelabeling` spec. |

### 5.5 Training Governance & Operations (v2)

| ID | Requirement | Priority | Acceptance Criteria |
|---|---|---|---|
| FR-31 | Dataset accumulation is reported to Tenant/System Admins but never triggers automatic **training job creation** or **model version promotion**. | Must | Per-entity-type readiness governed separately (ADR-010); accumulation reporting is informational only. Per `human-gated-retraining` spec. **Scope note**: this governs model lifecycle only — it does not contradict ADR-013's automated `large`-batch **annotation span** auto-promotion (suggested spans → confirmed training-data spans); see §11 for the full distinction. |
| FR-32 | Extraction review routes items using two independently configurable thresholds: one for business-facing extraction confidence, one for review escalation. | Should | Review outcome enum `confirmed/corrected/rejected`, recordable via human or LLM route into one outcome record. Per `confidence-routed-review` spec:30,48. **Production default values: not fixed in spec — only illustrative scenario values (extraction 0.50, review 0.80–0.90) — see §16.2, needs a decision owner.** |
| FR-33 | System Admin can view a tenant-filterable audit log of privileged actions. | Should | `GET /api/v1/admin/audit-log`, system_admin only; event kinds `create/approve/promote/complete/run/reject/update`. Per `audit-log` spec. **Retention period: not specified — see §16.3 gap.** |

---

## 6. Non-Functional Requirements

### 6.1 Core Platform (v1)

| Category | Requirement |
|---|---|
| Security | Strict tenant isolation across documents, annotations, extracted data, model artifacts, logs, and vector/search indexes. DB isolation via separate schema per tenant (single database, one schema per tenant). |
| Privacy | No tenant content shall be used for another tenant model unless explicit opt-in and legal agreement exist. |
| Auditability | Every extraction must record source document, span offsets, entity config version, model version, timestamp, and actor/system action. All user actions (login, config change, training trigger, model promotion) recorded in an audit log table. |
| Availability | Runtime extraction and chatbot shall be independently scalable from training workloads. |
| Scalability | Training jobs shall run asynchronously with GPU-capable workers; inference shall support horizontal scaling and model warmup strategy. |
| Performance | Batch extraction should process large document sets asynchronously (target: 100 docs/min per tenant for standard text docs). Interactive chatbot responses should target sub-10-second P95 response for common report queries. |
| Observability | Collect metrics for ingestion, OCR, annotation throughput, training duration, model quality, inference latency, and extraction confidence. Metrics retention: 30 days at full resolution, 12 months aggregated. |
| Governance | Model promotion requires metric thresholds, approval, lineage capture, and rollback mechanism. Maximum 10 model versions retained per tenant. Rollback must complete within 10 minutes (production target). |
| Maintainability | All features must be delivered via AI-native SDD artifacts: proposal, design, spec, tasks, tests, and evidence. |
| OCR | OCR attempted only when a document has no extractable native text layer (scanned PDFs, images). Minimum OCR confidence threshold: 0.70. Documents below threshold are flagged for human review. |

### 6.2 Added Since v1

| Category | Requirement |
|---|---|
| Data residency | `platform_blob` retention mode is explicitly forbidden for `tenant_owned` data-plane tenants (`RETENTION_MODE_NOT_PERMITTED_FOR_DATA_PLANE`); retention modes are `ephemeral/source_only/platform_blob`. Uploaded tabular files are a disclosed, explicit exception: they store in platform MinIO under `tenants/{tenant_id}/tabular/{file_id}/v{version}/` for **all** tenants regardless of residency mode (ADR-019), because DuckDB requires a stable object-store-backed Parquet copy. |
| External connection security | Every external connection uses TLS certificate validation and a Vault-held, tenant-scoped, least-privilege credential; the Azure PostgreSQL credential is specifically read-only. Both private endpoints and TLS-protected public endpoints are permitted; a public endpoint requires customer-approved platform egress IP allowlisting. Telemetry carries secret references only — never connection strings, provider errors, content, SQL text, prompts, or answers. Per ADR-011. **Credential rotation policy: not specified in any spec or ADR found — see §16.3 gap.** |
| External query safety | Every SQL statement against external/tenant-owned Postgres or uploaded tabular files is generated then validated against a fixed rule set (SELECT-only, no subqueries/CTEs/UNIONs/window functions, no `SET ROLE`/`SET SESSION AUTHORIZATION`) before execution; no code path executes unvalidated or free-form SQL. |
| Reliability (external stores) | Content and chat routes must distinguish "not yet provisioned" from "temporarily unreachable" for tenant-owned data planes and respond with distinct, documented error codes (409 vs 503) rather than a generic failure. |
| Reliability (services) | All backing services (Postgres, MinIO, Redis) use exponential backoff on startup (initial ≥0.5s, multiplier ≥2, capped ≤10s); `/health` (readiness) and `/health/live` (liveness) are distinct endpoints. |
| Telemetry safety | Tenant-mismatch metrics carry no tenant label (to avoid cross-tenant leakage in metrics); metric label cardinality is enforced by an automated test; a release-gate scan checks for leaked entity/PII content in telemetry. |
| Migration discipline | Tenant-scoped schema changes must be authored once as `statements(schema)` in `src/shared/tenant_store/revisions/NNNN_<name>.py` and applied to every tenant schema, including tenant-owned data-plane stores; per-tenant migration loops must tolerate tenants missing a given table. |
| Secret handling | No hardcoded secrets; per-tenant secret references follow a `<scheme>://<path>` grammar validated by schema, not heuristics; an unresolvable per-tenant secret degrades that tenant's connection to `error` status rather than crashing the process; process-level secrets (e.g. `NER_JWT_SECRET`) still fail closed at boot. |
| Deployment | Local/dev delivery standardizes on a single root multi-stage Dockerfile plus a Compose topology of 10 backend services + portal (gateway :8000, document_service :8001, extraction_service :8002, training_service :8003, model_serving :8004, annotation_service :8005, portal :3000); a one-shot `db-init` service runs `alembic upgrade head` and seeding; state persists in named volumes (`postgres-data`, `minio-data`). **No production/cloud deployment topology exists in the repo — see §16.2, this is the single largest NFR gap.** |
| Chat rate limiting | 60 requests/min for internal chat clients, 20 requests/min for the embeddable widget. |
| Orchestration determinism | Chat orchestration is a fixed LangGraph `StateGraph`, compiled once, with no loops, tool-calling, or planner nodes — the DAG is static per turn. |

### 6.3 Data Classification & Regulated Data (new — flagged, unanswered)

No spec, ADR, or code artifact states:
- Whether GDPR, HIPAA, PCI-DSS, or other regulated data categories are permitted or expected in tenant
  documents, tenant-owned databases, or uploaded tabular files.
- Which jurisdictions/regions a tenant-owned PostgreSQL data plane must be hosted in to satisfy that
  tenant's residency requirement (the `tenant_owned` retention mode enforces *platform vs. tenant storage*,
  not *geographic* residency).
- Encryption-at-rest requirements for tenant-owned stores, platform Postgres, or MinIO object storage
  (only TLS-in-transit for external connections was found, per §6.2).

**This section cannot be completed from the codebase — it requires legal/compliance and a named decision
owner.** Recommend blocking any tenant onboarding involving regulated data until this is answered.

### 6.4 Performance & Availability Targets — v2 Features (new — flagged, partial)

The only numeric v2 performance figures found in specs are **caps and timeouts**, not throughput or
latency SLOs:

| v2 Feature | What's specified | What's missing |
|---|---|---|
| External Postgres chat query | 100-row cap, 10s statement timeout | End-to-end P95 latency target |
| Azure Blob sync | 15-min cadence, 1 missed-cycle catch-up | Sync throughput (docs/min), max backlog before alerting |
| Tabular file publish (profile → ready) | — | No target found (also listed in §12) |
| Hybrid retrieval + reranking | top_k=5, rerank candidates=20 | Added latency budget vs. v1's existing sub-10s chatbot P95 (§6.1) — reranking is a new hop and could affect it |
| Chat rate limits | 60/min internal, 20/min widget | — (this one is fully specified) |

**Needs a decision owner** (Architect/Performance Engineering) to set the missing targets before production
sign-off.

---

## 7. Target Workflow

| Step | Workflow | Owner | Output |
|---|---|---|---|
| 1 | Provision tenant, create schema, define isolation policy. | System Admin | Tenant record, DB schema, storage namespace, model namespace. |
| 2 | Tenant Admin creates tenant-scoped user directory and assigns roles. | Tenant Admin | User accounts with tenant-scoped permissions. |
| 3 | Tenant Admin defines required entity catalog (entity types, validation rules, target tables). | Tenant Admin | Versioned entity configuration. |
| 4 | Tenant uploads sample documents for training (PDF, DOCX, TXT, images). | Tenant Admin / User | Raw documents and parsed text with offsets. |
| 5 | System creates annotation tasks with optional pre-labels from baseline NER model or LLM (v2). | Platform | Annotation queue. |
| 6 | Annotators label spans; reviewers approve or reject annotations. Disputes escalated to Tenant Admin. **v2**: for automated batches, only the `initial` (≤5 doc) batch is reviewed by an Annotator Admin — the `large` batch auto-promotes with no review (ADR-013). | Tenant Reviewer | Approved training dataset version. |
| 7 | Tenant Admin or System Admin triggers training. Job fine-tunes base model on approved dataset. Never triggered automatically by accumulation volume alone (FR-31). | System Admin / ML Pipeline | Candidate model version with metrics. |
| 8 | Candidate model evaluated (precision, recall, F1, confusion matrix). If thresholds met, manual approval requested. | System Admin / Tenant Admin | Active model version or rejection with diagnostics. |
| 9 | Tenant users upload operational documents. CSV files bypass NER and go through structured import. **v2**: alternatively, upload CSV/XLSX as a tabular data source (FR-20) for chat querying instead of/in addition to structured import. | Tenant User | Documents queued for extraction, or tabular file queued for profiling. |
| 10 | Runtime extraction stores structured records with model version, confidence, source spans. Low-confidence results flagged for review via two independent thresholds (v2, FR-32). | Platform | Tenant DB records with source references. |
| 11 | Tenant users review flagged extractions, correct errors. Corrections queued for future training cycles. | Tenant Business User | Corrected records + correction feedback dataset. |
| 12 | Chatbot/reports answer over extracted data. **v2**: chatbot may also answer over external Postgres data, tenant-owned data-plane data, and uploaded tabular files, via hybrid retrieval + reranking, with citations, export, and charts. | Tenant User | Conversational answers with source citations, dashboards, exports, charts. |
| 13 | Periodic retraining triggered by: confidence drift, correction volume threshold, or manual request. Never fully automatic. | System Admin / Tenant Admin | New model version cycle. |
| A1 *(v2)* | Tenant Admin connects an external data source (Azure Blob, external Postgres, or provisions a tenant-owned data-plane store) via the data source portal. | Tenant Admin | Connection in `draft` status. |
| A2 *(v2)* | System validates connectivity/permissions and activates the connection. | Platform | Connection `active`, or `error` with diagnostics. |
| A3 *(v2)* | Platform syncs Blob sources on schedule or on manual trigger; tabular file uploads are profiled and converted to a versioned Parquet copy. | Platform | Synced documents / published tabular file version. |

---

## 8. Logical Architecture

- **Web/Admin Portal**: Tenant administration, entity catalog, upload management, annotation/review
  screens, model lifecycle, reports, chatbot. **v2**: data source connection management, chat attachment
  composer, cited document viewer, audit log page.
- **API Gateway and Backend**: Tenant-aware APIs, authz (tenant-scoped JWT), orchestration, validation,
  audit logging, and asynchronous job submission.
- **Document Processing Service**: File validation (type, size, malware scan), OCR-only-when-needed
  fallback, text extraction, chunking, tokenization, layout metadata, and source mapping.
- **Annotation Service**: Label task management, pre-labeling from base NER model or LLM (v2), reviewer
  workflow, dispute resolution, dataset export in BIO/IOB2 format.
- **Training Orchestrator**: Creates tenant-specific fine-tuning jobs, records lineage, manages GPU
  workers, persists metrics and artifacts. Uses single curated base model. Never self-triggers from
  accumulation alone (v2, FR-31).
- **Model Registry**: Stores base model reference, tenant model versions (max 10 per tenant), metrics,
  approval status, artifact URI, and deployment status.
- **Model Serving Layer**: Per-tenant endpoint/pod/service or isolated routing layer with version pinning,
  autoscaling, and model warmup. **v2**: also serves the cross-encoder reranker (`/internal/v1/rerank`).
- **Extraction Service**: Runs active model, applies post-processing and validation rules, stores entities
  and normalized records. Flags sub-threshold confidence results. **v2**: entity resolution/normalization
  and typed structured value extraction happen here before storage.
- **Analytics and Conversational Layer**: Full RAG pipeline — SQL/reporting, semantic search over
  documents, NER model inference for real-time extraction queries. Agent tools constrained to tenant data.
  **v2**: hybrid dense+sparse retrieval with reranking; fixed LangGraph orchestration DAG; chat attachments,
  citations, export, and chart generation.
- **Data Source Control Plane** *(v2, new)*: connection lifecycle (draft/validated/active/paused/error/
  retired) for Azure Blob, external PostgreSQL, and tenant-owned PostgreSQL data-plane providers; sync
  scheduling and manual trigger; residency/retention-mode enforcement.
- **Tenant Data Plane Routing & Failure Isolation** *(v2, new)*: routes content/chat requests to the correct
  store per tenant readiness state, isolating failures so one tenant's unready/unreachable store cannot
  affect others.
- **Tabular File Service** *(v2, new)*: profiling, versioning, and Parquet conversion for uploaded CSV/XLSX;
  serves queries through a locked, ephemeral, in-process DuckDB session.
- **AI-Native Delivery Workspace**: AGENTS.md, OpenCode agent definitions, OpenSpec source-of-truth specs,
  change packages, ADRs, prompt/command logs, and delivery evidence.
- **Storage and Databases**: Object storage for documents/artifacts (and, per ADR-019, all tabular files
  regardless of tenant residency mode); single PostgreSQL database with per-tenant schemas, or tenant-owned
  Postgres data plane where provisioned (v2); optional search/vector index for document retrieval.
- **Observability & Workload Telemetry** *(v2, new)*: per-chat-stage span instrumentation, tenant-safe
  metrics, release-gate PII/entity-leak scanning.

**Production deployment gap (new)**: this architecture is described independent of hosting environment,
but the only deployment topology actually specified anywhere in the repo is local Docker Compose (§6.2).
No spec defines a production/staging environment, target cloud, region strategy, or how the per-tenant
isolation model maps onto production infrastructure. **See §16.2 — this is a release blocker, not a nice
to have.**

---

## 9. Data Model — Core Entities

| Entity/Table | Purpose | Key Fields |
|---|---|---|
| tenant | Tenant master record. | tenant_id, name, status, isolation_policy, quotas (max_users, max_docs, max_storage_gb, max_model_versions), created_at |
| tenant_user | Tenant-scoped user account. | user_id, tenant_id, username, email, role (admin / business_user / annotator / reviewer), status, created_at |
| entity_definition | Tenant-configured NER labels and extraction rules. | entity_id, tenant_id, name, description, examples (JSON array), validation_rule (regex/type), target_table, version, required_flag, is_active |
| document | Uploaded document metadata. | document_id, tenant_id, filename, mime_type, file_size_bytes, checksum (SHA-256), storage_uri, status (uploaded / processing / parsed / failed), ocr_applied_flag, error_message |
| document_text_span | Text with offsets and layout references. | span_id, document_id, page_no, block_no, text, start_offset, end_offset, ocr_confidence |
| annotation_task | Annotation and review workflow. | task_id, document_id, assignee (user_id), status (open / in_progress / submitted / approved / rejected), reviewer (user_id), dataset_version, created_at |
| annotation_label | Human-labeled entity spans. | label_id, task_id, entity_id, token_start, token_end, value, confidence (from pre-label), corrected_flag, created_at |
| training_job | Tenant model creation job. | job_id, tenant_id, dataset_version, base_model (name+hash), hyperparameters (JSON), status (queued / running / completed / failed / cancelled), metrics_uri, started_at, completed_at |
| model_version | Model registry entry. | model_id, tenant_id, version, artifact_uri, training_job_id, metrics (JSON), status (candidate / approved / rejected / active / archived), active_flag, promoted_by, promoted_at |
| extraction_run | Runtime extraction batch/job. | run_id, tenant_id, document_id, model_version, status (queued / running / completed / partially_completed / failed), started_at |
| extracted_entity (document_entities) | Extracted entity result. | result_id, run_id, entity_id, value, confidence, normalized_value, source_span_id, review_status (unreviewed / confirmed / corrected / rejected), corrected_value, corrected_by, correction_notes, **+ value_number, value_number_high, value_unit, value_date, value_date_high (v2, FR-28)** |
| audit_log | Immutable action trail. | log_id, tenant_id, actor_id, action, resource_type, resource_id, details (JSON), ip_address, timestamp |
| data_source_connection *(v2)* | Tenant external data source connection. | connection_id, tenant_id, provider_type (azure_blob / azure_postgresql / azure_postgresql_data_plane), status (draft/validated/active/paused/error/retired), retention_mode (ephemeral/source_only/platform_blob), secret_ref |
| tenant_integration_profile *(v2)* | Per-tenant integration/residency profile. | tenant_id, status (draft/validated/active/paused/error/retired), data_plane_status (awaiting_store/provisioning/provisioning_failed/ready/migration_required/paused/store_retired) |
| tabular_files *(v2)* | Uploaded tabular file (platform.tabular_files). | id, tenant_id, display_name, served_version, status (profiling/needs_review/publishing/ready/failed/deleted) |
| tabular_file_versions *(v2)* | Version of an uploaded tabular file. | file_id, version (PK w/ file_id), status (…/superseded), failure_reason, source_kind (csv/xlsx), source_filename, sheet, original_key, parquet_key, profile/review/load_report/contract (JSONB) |
| chat_messages *(extended, v2)* | Existing chat message table, extended. | + export_rows (JSONB, capped 1000 rows, internal SQL generator only), + chart (JSONB) |

**Isolation note**: All tables are deployed per-tenant within a dedicated PostgreSQL schema (or, where
provisioned, a tenant-owned data-plane store — v2). Cross-tenant access at the application layer is
prohibited. Object storage uses separate buckets or prefix-based isolation with IAM-style policies, except
uploaded tabular files, which always store in platform MinIO regardless of tenant residency mode (v2,
ADR-019, disclosed exception).

**Quota/retention gaps found (new, flagged — see §16.3)**: no field or spec sets a maximum tabular file
size/row/column count, a maximum attachment size, a maximum data source connection count beyond "one active
per provider type," a retention period for `chat_messages.export_rows` or attachments after conversation
deletion is *not* invoked, or a retention period for `audit_log` rows.

---

## 10. AI-Native SDD Requirements

- Every feature must start from a proposal.md capturing business intent, measurable outcomes, out-of-scope,
  constraints, and risks.
- design.md must capture architecture decisions, data boundaries, model lifecycle, tenant isolation,
  failure modes, and observability.
- spec.md must use testable SHALL statements and Given/When/Then acceptance criteria.
- tasks.md must split implementation into small, reviewable slices with evidence expectations.
- ADR records are mandatory; see `docs/adr/` for the full set (19 files as of this revision):
  - ADR-001 Tenant data isolation via separate PostgreSQL schemas
  - ADR-002 Single curated base model strategy — dslim/bert-base-NER, no BYOM
  - ADR-003 Per-tenant model serving topology with shared pool and tenant-aware routing
  - ADR-004 OpenSpec Spec-Driven Development governance with mandatory artifact gates
  - ADR-005 OpenCode agent permissions and bounded tool access
  - ADR-006 Training infrastructure with Celery-based async GPU workers
  - ADR-007 Chatbot architecture with full RAG pipeline and guardrails
  - ADR-008 Base model as default
  - ADR-009 System Admin sets training hyperparameters
  - ADR-010 Per-entity-type dataset threshold
  - ADR-011 Tenant-scoped Azure connection control plane **and, separately filed under the same number**,
    conversation-scoped chat attachments
  - ADR-012 Durable Azure Blob source synchronization **and, separately filed under the same number**, the
    CSV branch in the existing ingestion pipeline
  - ADR-013 Contract-governed external PostgreSQL chat, **and also, separately, both** local Docker Compose
    recreate deployment **and** large-batch auto-promotion (no review) — three unrelated decisions sharing
    one number
  - ADR-014 Chat export snapshot storage & on-demand rendering, **and also, separately**, local Compose
    deployment topology **and** mandatory conversation-scoped retrieval
  - ADR-015 External chat reply persistence
  - ADR-016 Contract-grounded external SQL generation
  - ADR-017 Tenant-owned PostgreSQL data plane
  - ADR-018 Uploaded tabular files queried via locked DuckDB over Parquet
  - ADR-019 Uploaded tabular files stored in platform object storage for all tenants
- Evidence folder must include: test results, API contract validation, security checks, model evaluation
  metrics, sample extraction outputs, and review notes.

**Numbering collision (flagged, unresolved)**: ADR numbers 011–014 each cover 2–3 unrelated decisions
across different change packages, distinguished only by filename (e.g.
`docs/adr/011-tenant-scoped-azure-connection-control-plane.md` vs. a second, differently-named ADR-011 file
for chat attachments). This BRD does not renumber them. **Owner and deadline: none assigned — needs
Architect sign-off on whether to renumber before v2 is finalized, and by when.**

---

## 11. Contradiction Resolution (new section)

Two apparent contradictions were raised against the first v2 draft. Both are resolved by scope, not by
error — documented here so the distinction is explicit and doesn't get re-flagged:

**Row caps (FR-18 vs. FR-24)**: FR-18's 100-row cap applies to the **external PostgreSQL** SQL generator
(`external-postgresql-chat` spec:82-86), whose results are explicitly response-only and **never persisted**
in any platform table (spec:89-93 — "no tenant database row SHALL exist in any platform table"). FR-24's
1000-row cap applies to the **internal relational** SQL generator over `document_entities`/`subject`
tables (`chat-export` spec:63), whose results *are* persisted as an export snapshot. These are two
different SQL generators with two different caps and two different persistence rules — not a conflict.
**Consequence**: an answer sourced from external Postgres data currently has no export path. If the
business wants export to also cover external-Postgres-sourced answers, that is a new requirement, not a bug
fix — flag for Product Owner decision.

**Auto-promotion (ADR-013 vs. FR-31)**: ADR-013's "large batches are promoted without any human review"
(`docs/adr/013-large-batch-auto-promotion-no-review.md`) governs **annotation span promotion** — an
automated batch's LLM-suggested spans becoming confirmed training-data spans, with no sampling or
acceptance step, the moment its pre-labeling job reaches a terminal state. FR-31 / `human-gated-retraining`
governs a completely different lifecycle stage: **training job creation and model version promotion to
production**, which remains human-gated regardless of how much labeled data has accumulated (including
data auto-promoted per ADR-013). The word "promotion" is overloaded across two unrelated workflows — span
promotion (annotation → training data) and model promotion (candidate → active). Both statements hold
simultaneously once the scopes are separated.

---

## 12. Risks and Mitigations

| Risk | Impact | Mitigation | ADR |
|---|---|---|---|
| Insufficient annotated data per tenant | Poor model quality and low trust. | Minimum dataset threshold (500 labeled entities per entity type — see ADR-010 for the per-entity-type refinement). Pre-labeling from base model or LLM (v2). Active learning for high-uncertainty samples. Data augmentation review. Manual approval gates for model promotion (not annotation span promotion — see §11). | ADR-006, ADR-010 |
| Highly visual/scanned documents | BERT token classifier may miss layout-dependent fields. | OCR confidence metadata stored with spans. Layout metadata preserved for future LayoutLM/Donut evaluation. Tenant-level flag for form-heavy documents. | ADR-002 |
| Too many tenant-specific models | High operational cost and deployment complexity. | Model pooling only for opted-in tenants per legal agreement. Autoscaling for inference. Model warmup and quantization. Endpoint hibernation for tenants with <10 docs/week. | ADR-003 |
| Cross-tenant data leakage | Critical security/privacy breach. | Schema-per-tenant isolation. Hard tenant_id enforcement at API gateway. Separate storage namespaces. Encryption boundaries. Policy-based penetration tests. Audit logs with alerting on anomalous cross-tenant patterns. **v2**: tenant-mismatch metrics carry no tenant label; automated cardinality test; release-gate PII scan. | ADR-001 |
| Chatbot hallucination | Incorrect business answers. | Agent tools constrained to tenant data APIs and DB. Source references required. SQL validation layer. Block unsupported question types. Human-in-the-loop for high-stakes extraction corrections. **v2**: fixed rule-based SQL validation (no subqueries/CTEs/UNIONs/window functions/role changes) for external/tabular sources too. | ADR-007, ADR-016 |
| Model drift | Quality degrades as document formats change. | Track correction volume and confidence trends per entity type. Periodic re-evaluation (monthly or after N corrections). Alert on >10% F1 degradation. Retraining trigger at 20% correction rate. | ADR-006 |
| OCR quality too low | Entities missed or misidentified. | Minimum OCR confidence threshold (0.70). Documents below threshold flagged for human transcription. OCR confidence stored alongside spans and surfaced in extraction review UI. | — |
| **Residency exception for tabular files** *(v2)* | Tenant believes all its data stays in its own store; tabular uploads silently go to platform storage regardless. | Explicitly disclosed exception (ADR-019); **needs** to be surfaced in tenant-facing data source settings UI, not just in the ADR — not confirmed as implemented. | ADR-019 |
| **Generated SQL against external/tenant data escapes read-only boundary** *(v2)* | Data corruption or unauthorized access in tenant's own external database. | Fixed rule-based validation, 10s timeout, row caps, contract-index-scoped prompting; fails closed on oversized schema context. | ADR-016 |
| **External Postgres or tenant data-plane store temporarily unreachable** *(v2)* | Chat/content requests fail without clear cause. | Explicit 409 (not ready) vs 503 (unreachable) distinction; failure isolation per tenant. | ADR-017 |
| **No production deployment topology** *(v2, new)* | Cannot actually run this in production as specified; only local Compose exists. | None yet — **this is an open risk, not a mitigated one.** | — |
| **Regulated data handling undefined** *(v2, new)* | Legal/compliance exposure if a tenant onboards regulated data without a policy in place. | None yet — **this is an open risk, not a mitigated one.** | — |

---

## 13. Success Metrics

| Metric | Target for Pilot | Target for Production |
|---|---|---|
| Entity-level F1 on tenant validation set | >= 0.80 for high-volume entities | >= 0.90 for mature tenants/entities |
| Extraction traceability | 100% of extracted entities include source span and model version | 100% maintained |
| Manual review reduction | 30% reduction after first model iteration | 60%+ reduction after mature feedback loop |
| Tenant data isolation test pass rate | 100% | 100% |
| Model deployment rollback time | < 30 minutes | < 10 minutes |
| AI-native evidence completeness | All promoted features include spec, tests, and evidence | Mandatory release gate |
| Chatbot response time (P95) | < 15 seconds | < 10 seconds |
| OCR fallback accuracy | >= 90% character accuracy | >= 95% character accuracy |
| External SQL generation validation pass rate (no unsafe statement reaches execution) *(v2)* | 100% | 100% |
| Tenant data-plane routing correctness (no cross-tenant misroute) *(v2)* | 100% | 100% |
| Tabular file publish success rate (profiling → ready) *(v2)* | **No target set — needs stakeholder input; recommend establishing a baseline after 30 days of production use rather than guessing a number now.** | — |
| Chat citation-to-viewer open success rate *(v2)* | **No target set — same recommendation as above.** | — |

---

## 14. Clarified Decisions

| Topic | Decision | Rationale | ADR Reference |
|---|---|---|---|
| Base model strategy | Single curated base model (dslim/bert-base-NER) | Reduces infrastructure complexity; avoids model compatibility matrix | ADR-002, reaffirmed ADR-008 |
| Identity model | Tenant-scoped user directories | Each tenant owns its user lifecycle; no global user management overhead | — |
| OCR strategy | Fallback only when no native text layer | Reduces unnecessary OCR cost and latency; OCR confidence threshold at 0.70 | — |
| CSV handling | Structured import only (no NER); **v2 adds a second, separate path** — CSV/XLSX as an uploaded tabular data source for chat querying | CSV columns are already structured; NER on cell values adds no value. Tabular data source path serves a different need (ad hoc chat querying, not entity extraction). | — / ADR-018 |
| Chatbot architecture | Full RAG (NER + structured data + document search); **v2 adds** hybrid dense+sparse retrieval, reranking, external Postgres, and tabular files as sources | Maximizes answer quality; uses all available data sources | ADR-007 |
| DB isolation | Separate schema per tenant; **v2 adds** optional tenant-owned data-plane store | Good isolation without per-database operational cost; supports schema-level backup/restore. Tenant-owned option serves residency-sensitive tenants. | ADR-001, ADR-017 |
| Tabular file storage location *(v2)* | Always platform-hosted MinIO, all tenants, regardless of residency mode | DuckDB/Parquet query path requires a stable, platform-controlled object store | ADR-019 |
| External SQL generation grounding *(v2)* | Code-enforced rules + contract's schema index, not free-form LLM SQL | Prevents unsafe/hallucinated SQL against tenant-owned business data | ADR-016 |
| Annotation span promotion for automated batches *(v2)* | `large` batch (100-200 docs) auto-promotes with no review; `initial` batch (≤5 docs) is Annotator-Admin-reviewed and gates the large batch | Deliberate throughput-over-safety trade, made explicitly by the project owner, not inferred — see §11 for how this differs from model promotion | ADR-013 |
| Retraining trigger | Never automatic — human-gated regardless of accumulated data volume | Prevents unreviewed model changes; per-entity-type readiness handled separately | ADR-010, human-gated-retraining spec |
| Chat orchestration shape *(v2)* | Fixed LangGraph DAG, no loops/planner/tool-calling nodes | Predictable latency and behavior; easier to audit and test | — |

---

## 15. OpenCode and OpenSpec Delivery Requirements

### 15.1 Delivery Gates

| Gate | Owner | Entry Criteria | Exit Criteria |
|---|---|---|---|
| Intent Gate | Product Owner + Architect | Problem and tenant value are understood. | OpenSpec proposal accepted with success metrics and scope boundaries. |
| Design Gate | Architect + Security + MLOps | Proposal approved. | Design covers data isolation, APIs, runtime, model lifecycle, risks, rollback, and observability. |
| Implementation Gate | Seed Engineer | Spec and tasks approved. | OpenCode implementation maps to tasks and contains tests/migrations/contracts. |
| Evidence Gate | QA + Security + Architect | Implementation complete. | Evidence folder contains test results, validation outputs, screenshots/logs, model metrics, and review notes. |
| Archive Gate | Architect + Product Owner | Evidence accepted. | OpenSpec change archived and source-of-truth specs updated. |
| **Release Acceptance Gate** *(new — proposed, not yet in repo)* | **Needs owner — recommend Product Owner + Architect + Security jointly** | All FRs in this document have passed their Evidence Gate; §16 open items have an assigned owner and status (even if status is "deferred," it must be a decision, not a silence). | A named approver signs off on this document per §0, with a recorded date. **This gate does not exist anywhere in the current OpenSpec governance model** — v1 and v2 both specify per-change evidence gates, but neither specifies who accepts the platform-level release as a whole. This is itself a gap: recommend adding it to `docs/adr.md` governance (ADR-004 scope) rather than inventing an ad hoc process here. |

### 15.2 Mandatory Repository Artifacts

| Artifact | Purpose | Required Content |
|---|---|---|
| AGENTS.md | Repository-level AI engineering policy. | Coding standards, tenant isolation rules, SDD workflow, evidence expectations, security constraints, prohibited actions. |
| .opencode/agents/ | OpenCode role definitions. | Planner, architect reviewer, backend, frontend, MLOps, QA, security, and documentation agents. |
| openspec/project.md | Project principles and context. | Product vision, domain terms, architecture constraints, delivery principles, quality bars. |
| openspec/specs/ | Current source-of-truth specs. | Durable feature specs — now 90+ directories covering tenant, ingestion, annotation, training, serving, extraction, chatbot, retrieval, data sources, and operations. |
| openspec/changes/\<change-id\>/ | Change packages. | proposal.md, design.md, spec.md, tasks.md, evidence/. |
| docs/adr/ | ADR compilation. | 19 ADR files (see §10); some numbers reused across unrelated decisions — flagged as an open item. |

---

## 16. Open Items for Stakeholder Review (consolidated, with owners where determinable)

### 16.1 Mandatory governance fields (no decision possible from code — business input required)

1. **Approver / sign-off authority** for this document. Not recorded in v1 or v2. Recommend: Product Owner
   + Architect (matches Intent Gate, §15.1), but must be confirmed by the business.
2. **Target approval date.** None exists anywhere in the repo's history or artifacts.
3. **Budget / team capacity** to close the gaps listed in §16.2–16.4. Not tracked in code or OpenSpec
   artifacts — a planning input only the business can supply.
4. **Regulated data classification and residency jurisdictions** (§6.3). Requires legal/compliance input;
   recommend blocking regulated-data tenant onboarding until answered.

### 16.2 Decisions with a clear owner, still pending

5. **ADR numbering collisions** (ADR-011 through ADR-014 each cover multiple unrelated decisions, §10).
   Owner: Architect. No deadline set — recommend before this document is finalized, since ADR references
   elsewhere in this BRD depend on filename disambiguation, not just number.
6. **Confidence-routed-review production thresholds** (FR-32) — only illustrative values found (0.50 /
   0.80–0.90). Owner: AI/ML Engineering lead + Tenant Admin representative (this affects review workload
   directly).
7. **Production/cloud deployment topology** (§6.2, §8, §12) — only local Docker Compose exists. Owner:
   Architect + Infrastructure. This is the largest single gap in the document and should be treated as a
   release blocker, not a backlog item.
8. **KPI targets** for tabular publish success rate and citation-viewer open rate (§13). Owner: Product
   Owner — recommend setting after a 30-day production baseline rather than guessing now.
9. **UI-only spec scoping** — `design-tokens`, `dark-theme-consistency`, `nav-config`, and similar
   presentation-only specs were intentionally excluded from this BRD as below FR/NFR granularity. Owner:
   Product Owner — confirm this scoping boundary is correct.
10. **Release Acceptance Gate** does not exist in current OpenSpec governance (per-change evidence gates
    exist; a whole-platform release sign-off gate does not). Owner: Architect — recommend adding to
    ADR-004's governance scope rather than treating this BRD as the gate itself.

### 16.3 Gaps confirmed absent from the codebase (not implementation details BRD omitted — genuinely unspecified)

11. **Size/quota limits**: no maximum tabular file size, row count, or column count found (FR-20); no
    maximum chat attachment size found (FR-22); no connection-count limit beyond "one active per provider
    type" (FR-16).
12. **Credential rotation policy** for external data source secrets — TLS and least-privilege Vault-held
    credentials are specified (§6.2); rotation cadence/process is not.
13. **Retention periods**: no retention period found for chat attachments (beyond "deleted when conversation
    is deleted"), export snapshots, or audit log rows.
14. **Access control specifics**: which role(s) may export chat results, which role(s) beyond "Tenant Admin"
    generally may create/approve a data source connection, and whether embeddable-widget users may attach
    files or export — none of these are stated in any spec found (§3).
15. **Rollout to existing tenants**: no spec addresses backfilling typed structured values (FR-28) onto
    entities extracted before that feature shipped, or how v2 features are enabled for tenants already
    running under v1 behavior.
16. **Operations ownership**: no spec or ADR names who owns monitoring/alerting/on-call for Blob sync
    failures or tenant data-plane outages — only that the platform detects and returns distinct error codes
    (FR-19), not who responds to them.

### 16.4 Cross-references

- Item 15 (rollout/backfill) is also noted inline at FR-28 in §5.4.
- Item 11 (tabular file size) is also noted inline at FR-20 in §5.2; attachment size at FR-22 in §5.3.
- Item 13 (audit log retention) is also noted inline at FR-33 in §5.5.

---

## 17. Changelog

| Date | Change | Author |
|---|---|---|
| 2026-05-28 | PRD v0.2 draft created | Architecture / AI-Native SDD Team |
| 2026-06-03 | Refined to requirements.md v1: fixed duplicate FR IDs, added user/auth entity, resolved 6 ambiguities, clarified workflows, expanded data model | OpenCode analysis + stakeholder clarification |
| 2026-06-04 | ADR-001–007 cross-referenced into v1 | OpenCode — ADR generation pass |
| 2026-09-25 | v2 first draft: folded forward ~150 archived/active OpenSpec changes and ADR-008–019 | Claude Code — BRD refresh |
| 2026-09-25 | v2 revision: inlined all v1 content in full (no pointer-only sections), added Document Control (§0) for approver/deadline/budget/regulated-data fields, resolved the row-cap and auto-promotion contradictions (§11), added data classification (§6.3) and performance-target (§6.4) sections, consolidated all open items with owners where determinable (§16) | Claude Code — BRD gap remediation, per stakeholder review |
