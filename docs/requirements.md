# Requirements — Multi-Tenant Custom Named Entity Recognition Platform

> Refined from PRD v0.2 (tenant_custom_ner_prd_opencode_openspec.docx.md).
> Ambiguities and gaps resolved via stakeholder clarification on 2026-06-03.
> Duplicate FR-11/FR-12 IDs corrected.

**Status**: Approved
**Date**: 2026-06-03

---

## 1. Executive Summary

This document defines the requirements for a multi-tenant document intelligence platform where each tenant can define domain-specific named entities, train a tenant-specific NER model, deploy that model in an isolated runtime, and use extracted structured data for workflows, reporting, and agentic conversations. Delivery is AI-native: OpenSpec governs requirements, design, tasks, and evidence as the source of truth; OpenCode is the agentic engineering interface for planning, implementation, review, and validation under human approval gates.

**Reference model**: dslim/bert-base-NER (single curated base model for all tenants). It recognizes standard CoNLL classes (PER, ORG, LOC, MISC). Tenant-specific extraction requires custom labels, annotated training data, fine-tuning, evaluation, and model governance before deployment.

---

## 2. Business Objectives

- **Tenant-specific intelligence**: Allow each tenant to extract business-specific entities from its own document corpus without mixing data or model artifacts with other tenants.
- **Operational automation**: Convert unstructured documents into validated structured records stored in a tenant-scoped database.
- **AI-native delivery**: Build using OpenSpec-managed Spec-Driven Development and OpenCode-assisted engineering, with every implementation slice traceable to proposal, design, specification, task, and evidence artifacts.
- **Enterprise readiness**: Provide isolation, auditability, model versioning, rollback, observability, and secure data handling from the first release.

---

## 3. Users and Personas

| Persona | Primary Goals | Key Permissions | Scope |
|---|---|---|---|
| Tenant Admin | Configure entities, upload seed documents, manage annotation workflow, request model training, approve models. | Tenant-scoped configuration, datasets, model lifecycle actions. | Tenant |
| Tenant Business User | Upload documents, trigger extraction, review results, search and query reports/chatbot. | Tenant-scoped document ingestion and consumption. | Tenant |
| System Admin | Provision tenants, monitor training jobs, approve deployment policies, manage infrastructure and quotas. | Cross-tenant operational visibility without access to tenant document content by default. | Global |
| Data Annotator / Reviewer | Label entity examples, validate model outputs, correct extraction errors. | Tenant-scoped annotation and review queues. | Tenant |
| AI/ML Engineer | Tune training pipeline, evaluate model quality, promote/rollback model versions. | Model registry and MLOps permissions. | Global + Tenant |

**Identity model**: Tenant-scoped user directories. Each tenant manages its own users and roles independently. System Admin exists in a global administrative domain outside any tenant.

---

## 4. Scope

### 4.1 In Scope

- Tenant onboarding and tenant-scoped storage, identity, roles, and quotas.
- Tenant admin page for entity type configuration, field definitions, examples, validation rules, and extraction targets.
- Document upload pipeline for PDF, DOCX, TXT, CSV (structured import only, no NER), images (JPEG, PNG, TIFF), and scanned PDFs where OCR fallback is enabled.
- Annotation workflow for creating BIO/IOB2 token classification datasets from uploaded documents.
- Tenant-specific model training/fine-tuning pipeline using a single curated base model (dslim/bert-base-NER).
- Model registry with versions, metrics, datasets, lineage, approval status, and rollback support.
- Separate runtime deployment per tenant, or logically isolated deployment pool where infrastructure constraints require pooling.
- Extraction pipeline that stores results in tenant-scoped relational tables and optionally a document/search index.
- Agentic chatbot and conversational reporting over extracted data with guardrails and source references. Chatbot uses a full RAG architecture: NER model + structured data + document search.

### 4.2 Out of Scope for Initial Release

- Fully automated high-quality model creation without human annotation or validation.
- General-purpose document understanding for highly visual forms unless a layout-aware model is explicitly included.
- Cross-tenant model training using pooled tenant data unless tenants explicitly opt in.
- Regulated production certifications such as SOC 2 or ISO 27001, although architecture should not block later certification.
- Tenant-selectable or bring-your-own base model (single curated base model only).

---

## 5. Functional Requirements

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

---

## 6. Non-Functional Requirements

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

---

## 7. Target Workflow

| Step | Workflow | Owner | Output |
|---|---|---|---|
| 1 | Provision tenant, create schema, define isolation policy. | System Admin | Tenant record, DB schema, storage namespace, model namespace. |
| 2 | Tenant Admin creates tenant-scoped user directory and assigns roles. | Tenant Admin | User accounts with tenant-scoped permissions. |
| 3 | Tenant Admin defines required entity catalog (entity types, validation rules, target tables). | Tenant Admin | Versioned entity configuration. |
| 4 | Tenant uploads sample documents for training (PDF, DOCX, TXT, images). | Tenant Admin / User | Raw documents and parsed text with offsets. |
| 5 | System creates annotation tasks with optional pre-labels from baseline NER model. | Platform | Annotation queue. |
| 6 | Annotators label spans; reviewers approve or reject annotations. Disputes escalated to Tenant Admin. | Tenant Reviewer | Approved training dataset version. |
| 7 | Tenant Admin or System Admin triggers training. Job fine-tunes base model on approved dataset. | System Admin / ML Pipeline | Candidate model version with metrics. |
| 8 | Candidate model evaluated (precision, recall, F1, confusion matrix). If thresholds met, manual approval requested. | System Admin / Tenant Admin | Active model version or rejection with diagnostics. |
| 9 | Tenant users upload operational documents. CSV files bypass NER and go through structured import. | Tenant User | Documents queued for extraction. |
| 10 | Runtime extraction stores structured records with model version, confidence, source spans. Low-confidence results flagged for review. | Platform | Tenant DB records with source references. |
| 11 | Tenant users review flagged extractions, correct errors. Corrections queued for future training cycles. | Tenant Business User | Corrected records + correction feedback dataset. |
| 12 | Chatbot/reports answer over extracted data. Chatbot uses full RAG pipeline (NER + structured data + document search). | Tenant User | Conversational answers with source citations, dashboards, exports. |
| 13 | Periodic retraining triggered by: confidence drift, correction volume threshold, or manual request. | System Admin / Tenant Admin | New model version cycle. |

---

## 8. Logical Architecture

- **Web/Admin Portal**: Tenant administration, entity catalog, upload management, annotation/review screens, model lifecycle, reports, chatbot.
- **API Gateway and Backend**: Tenant-aware APIs, authz (tenant-scoped JWT), orchestration, validation, audit logging, and asynchronous job submission.
- **Document Processing Service**: File validation (type, size, malware scan), OCR-only-when-needed fallback, text extraction, chunking, tokenization, layout metadata, and source mapping.
- **Annotation Service**: Label task management, pre-labeling from base NER model, reviewer workflow, dispute resolution, dataset export in BIO/IOB2 format.
- **Training Orchestrator**: Creates tenant-specific fine-tuning jobs, records lineage, manages GPU workers, persists metrics and artifacts. Uses single curated base model.
- **Model Registry**: Stores base model reference, tenant model versions (max 10 per tenant), metrics, approval status, artifact URI, and deployment status.
- **Model Serving Layer**: Per-tenant endpoint/pod/service or isolated routing layer with version pinning, autoscaling, and model warmup.
- **Extraction Service**: Runs active model, applies post-processing and validation rules, stores entities and normalized records. Flags sub-threshold confidence results.
- **Analytics and Conversational Layer**: Full RAG pipeline — SQL/reporting, semantic search over documents, NER model inference for real-time extraction queries. Agent tools constrained to tenant data.
- **AI-Native Delivery Workspace**: AGENTS.md, OpenCode agent definitions, OpenSpec source-of-truth specs, change packages, ADRs, prompt/command logs, and delivery evidence.
- **Storage and Databases**: Object storage for documents/artifacts; single PostgreSQL database with per-tenant schemas; optional search/vector index for document retrieval.

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
| extracted_entity | Extracted entity result. | result_id, run_id, entity_id, value, confidence, normalized_value, source_span_id, review_status (unreviewed / confirmed / corrected / rejected), corrected_value, corrected_by, correction_notes |
| audit_log | Immutable action trail. | log_id, tenant_id, actor_id, action, resource_type, resource_id, details (JSON), ip_address, timestamp |

**Isolation note**: All tables are deployed per-tenant within a dedicated PostgreSQL schema. Cross-tenant access at the application layer is prohibited. Object storage uses separate buckets or prefix-based isolation with IAM-style policies.

---

## 10. AI-Native SDD Requirements

- Every feature must start from a proposal.md capturing business intent, measurable outcomes, out-of-scope, constraints, and risks.
- design.md must capture architecture decisions, data boundaries, model lifecycle, tenant isolation, failure modes, and observability.
- spec.md must use testable SHALL statements and Given/When/Then acceptance criteria.
- tasks.md must split implementation into small, reviewable slices with evidence expectations.
- ADR records are mandatory for the following topics; see `docs/adr.md` for the full decision records:
  - Tenant data isolation via separate PostgreSQL schemas (ADR-001)
  - Single curated base model strategy — dslim/bert-base-NER, no BYOM (ADR-002)
  - Per-tenant model serving topology with shared pool and tenant-aware routing (ADR-003)
  - OpenSpec Spec-Driven Development governance with mandatory artifact gates (ADR-004)
  - OpenCode agent permissions and bounded tool access (ADR-005)
  - Training infrastructure with Celery-based async GPU workers (ADR-006)
  - Chatbot architecture with full RAG pipeline and guardrails (ADR-007)
- Evidence folder must include: test results, API contract validation, security checks, model evaluation metrics, sample extraction outputs, and review notes.

---

## 11. Risks and Mitigations

| Risk | Impact | Mitigation | ADR |
|---|---|---|---|---|
| Insufficient annotated data per tenant | Poor model quality and low trust. | Minimum dataset threshold (500 labeled entities per entity type). Pre-labeling from base model. Active learning for high-uncertainty samples. Data augmentation review. Manual approval gates. | ADR-006 |
| Highly visual/scanned documents | BERT token classifier may miss layout-dependent fields. | OCR confidence metadata stored with spans. Layout metadata preserved for future LayoutLM/Donut evaluation. Tenant-level flag for form-heavy documents. | ADR-002 |
| Too many tenant-specific models | High operational cost and deployment complexity. | Model pooling only for opted-in tenants per legal agreement. Autoscaling for inference. Model warmup and quantization. Endpoint hibernation for tenants with <10 docs/week. | ADR-003 |
| Cross-tenant data leakage | Critical security/privacy breach. | Schema-per-tenant isolation. Hard tenant_id enforcement at API gateway. Separate storage namespaces. Encryption boundaries. Policy-based penetration tests. Audit logs with alerting on anomalous cross-tenant patterns. | ADR-001 |
| Chatbot hallucination | Incorrect business answers. | Agent tools constrained to tenant data APIs and DB. Source references required. SQL validation layer. Block unsupported question types. Human-in-the-loop for high-stakes extraction corrections. | ADR-007 |
| Model drift | Quality degrades as document formats change. | Track correction volume and confidence trends per entity type. Periodic re-evaluation (monthly or after N corrections). Alert on >10% F1 degradation. Retraining trigger at 20% correction rate. | ADR-006 |
| OCR quality too low | Entities missed or misidentified. | Minimum OCR confidence threshold (0.70). Documents below threshold flagged for human transcription. OCR confidence stored alongside spans and surfaced in extraction review UI. | — |

---

## 12. Success Metrics

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

---

## 13. Clarified Decisions (from PRD v0.2 Review)

| Topic | Decision | Rationale | ADR Reference |
|---|---|---|---|---|
| Base model strategy | Single curated base model (dslim/bert-base-NER) | Reduces infrastructure complexity; avoids model compatibility matrix | ADR-002 |
| Identity model | Tenant-scoped user directories | Each tenant owns its user lifecycle; no global user management overhead | — |
| OCR strategy | Fallback only when no native text layer | Reduces unnecessary OCR cost and latency; OCR confidence threshold at 0.70 | — |
| CSV handling | Structured import only (no NER) | CSV columns are already structured; NER on cell values adds no value | — |
| Chatbot architecture | Full RAG (NER + structured data + document search) | Maximizes answer quality; uses all available data sources | ADR-007 |
| DB isolation | Separate schema per tenant | Good isolation without per-database operational cost; supports schema-level backup/restore | ADR-001 |

---

## 14. OpenCode and OpenSpec Delivery Requirements

### 14.1 Delivery Gates

| Gate | Owner | Entry Criteria | Exit Criteria |
|---|---|---|---|
| Intent Gate | Product Owner + Architect | Problem and tenant value are understood. | OpenSpec proposal accepted with success metrics and scope boundaries. |
| Design Gate | Architect + Security + MLOps | Proposal approved. | Design covers data isolation, APIs, runtime, model lifecycle, risks, rollback, and observability. |
| Implementation Gate | Seed Engineer | Spec and tasks approved. | OpenCode implementation maps to tasks and contains tests/migrations/contracts. |
| Evidence Gate | QA + Security + Architect | Implementation complete. | Evidence folder contains test results, validation outputs, screenshots/logs, model metrics, and review notes. |
| Archive Gate | Architect + Product Owner | Evidence accepted. | OpenSpec change archived and source-of-truth specs updated. |

### 14.2 Mandatory Repository Artifacts

| Artifact | Purpose | Required Content |
|---|---|---|
| AGENTS.md | Repository-level AI engineering policy. | Coding standards, tenant isolation rules, SDD workflow, evidence expectations, security constraints, prohibited actions. |
| .opencode/agents/ | OpenCode role definitions. | Planner, architect reviewer, backend, frontend, MLOps, QA, security, and documentation agents. |
| openspec/project.md | Project principles and context. | Product vision, domain terms, architecture constraints, delivery principles, quality bars. |
| openspec/specs/ | Current source-of-truth specs. | Durable feature specs for tenant, ingestion, annotation, training, serving, extraction, chatbot, and operations. |
| openspec/changes/\<change-id\>/ | Change packages. | proposal.md, design.md, spec.md, tasks.md, evidence/. |
| docs/adr.md | ADR compilation. | 7 ADRs: tenant isolation (ADR-001), base model strategy (ADR-002), serving topology (ADR-003), OpenSpec governance (ADR-004), OpenCode agent boundaries (ADR-005), training infrastructure (ADR-006), chatbot guardrails (ADR-007). |

---

## 15. Changelog

| Date | Change | Author |
|---|---|---|
| 2026-05-28 | PRD v0.2 draft created | Architecture / AI-Native SDD Team |
| 2026-06-03 | Refined to requirements.md: fixed duplicate FR IDs, added user/auth entity, resolved 6 ambiguities (base model, identity, OCR, CSV, chatbot, DB isolation), clarified workflows, expanded data model with audit_log and tenant_user | OpenCode analysis + stakeholder clarification |
| 2026-06-04 | Updated with ADR cross-references (docs/adr.md): ADR-001 through ADR-007 added to FRs, clarified decisions, risks, and section 10/14.2 | OpenCode — ADR generation pass |
