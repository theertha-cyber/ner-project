**Project Requirements Document**

Multi-Tenant Custom Named Entity Recognition Platform

v0.2 Draft \- updated for OpenCode \+ OpenSpec

| Prepared for | Multi-tenant custom NER platform initiative |
| :---- | :---- |
| **Prepared by** | Architecture / AI-Native SDD Team |
| **Date** | 28 May 2026 |
| **Status** | Updated architecture and delivery draft using OpenCode and OpenSpec |

# **1\. Executive Summary**

This document defines the requirements for a multi-tenant document intelligence platform where each tenant can define domain-specific named entities, train a tenant-specific NER model, deploy that model in an isolated runtime, and use extracted structured data for workflows, reporting, and agentic conversations. The delivery model is explicitly AI-Native: OpenSpec governs requirements, design, tasks, and evidence as the source of truth; OpenCode is used as the agentic engineering interface for planning, implementation, review, and validation under human approval gates.

**Note:** dslim/bert-base-NER is a useful baseline/reference model, but it recognizes only the standard CoNLL-style classes such as person, organization, location, and miscellaneous. Tenant-specific extraction requires custom labels, annotated training data, fine-tuning, evaluation, and model governance before deployment.

# **2\. Business Objectives**

* **Tenant-specific intelligence:** Allow each tenant to extract business-specific entities from its own document corpus without mixing data or model artifacts with other tenants.  
* **Operational automation:** Convert unstructured documents into validated structured records stored in a tenant-scoped database.  
* AI-native delivery: Build using OpenSpec-managed Spec-Driven Development and OpenCode-assisted engineering, with every implementation slice traceable to proposal, design, specification, task, and evidence artifacts.  
* **Enterprise readiness:** Provide isolation, auditability, model versioning, rollback, observability, and secure data handling from the first release.

# **3\. Users and Personas**

| Persona | Primary Goals | Key Permissions |
| :---- | :---- | :---- |
| Tenant Admin | Configure entities, upload seed documents, manage annotation workflow, request model training, approve models. | Tenant-scoped configuration, datasets, model lifecycle actions. |
| Tenant Business User | Upload documents, trigger extraction, review results, search and query reports/chatbot. | Tenant-scoped document ingestion and consumption. |
| System Admin | Provision tenants, monitor training jobs, approve deployment policies, manage infrastructure and quotas. | Cross-tenant operational visibility without access to tenant document content by default. |
| Data Annotator / Reviewer | Label entity examples, validate model outputs, correct extraction errors. | Tenant-scoped annotation and review queues. |
| AI/ML Engineer | Tune training pipeline, evaluate model quality, promote/rollback model versions. | Model registry and MLOps permissions. |

# **4\. Scope**

## **4.1 In Scope**

* Tenant onboarding and tenant-scoped storage, identity, roles, and quotas.  
* Tenant admin page for entity type configuration, field definitions, examples, validation rules, and extraction targets.  
* Document upload pipeline for PDF, DOCX, TXT, CSV, images, and scanned PDFs where OCR is enabled.  
* Annotation workflow for creating BIO/IOB2 token classification datasets from uploaded documents.  
* Tenant-specific model training/fine-tuning pipeline using a configurable base model.  
* Model registry with versions, metrics, datasets, lineage, approval status, and rollback support.  
* Separate runtime deployment per tenant, or logically isolated deployment pool where infrastructure constraints require pooling.  
* Extraction pipeline that stores results in tenant-scoped relational tables and optionally a document/search index.  
* Agentic chatbot and conversational reporting over extracted data with guardrails and source references.

## **4.2 Out of Scope for Initial Release**

* Fully automated high-quality model creation without human annotation or validation.  
* General-purpose document understanding for highly visual forms unless a layout-aware model is explicitly included.  
* Cross-tenant model training using pooled tenant data unless tenants explicitly opt in.  
* Regulated production certifications such as SOC 2 or ISO 27001, although architecture should not block later certification.

# **5\. Functional Requirements**

| ID | Requirement | Priority | Acceptance Criteria |
| :---- | :---- | :---- | :---- |
| FR-01 | System admin can create and manage tenants, quotas, runtime isolation policy, and admin users. | Must | A tenant can be provisioned with isolated storage, DB schema/database, and model namespace. |
| FR-02 | Tenant admin can define entity types, descriptions, examples, aliases, expected formats, required/optional flags, and target DB mapping. | Must | Entity definitions are versioned and validated before training. |
| FR-03 | Tenant users can upload documents in supported formats and view parsing status. | Must | Each uploaded document receives immutable metadata, storage path, checksum, and processing status. |
| FR-04 | System extracts text with page number, paragraph, token offsets, and OCR confidence where applicable. | Must | Training and extraction can trace every entity back to source document location. |
| FR-05 | Annotation UI supports manual labeling, pre-labeling from a baseline NER model, correction, and reviewer approval. | Must | Approved annotations can be exported to token classification format. |
| FR-06 | System admin or authorized tenant admin can trigger tenant-specific training. | Must | Training job captures dataset version, entity config version, base model, hyperparameters, and metrics. |
| FR-07 | Model evaluation calculates precision, recall, F1, entity-level metrics, confusion matrix, and minimum promotion thresholds. | Must | A model cannot be promoted unless thresholds and manual approval are satisfied. |
| FR-08 | Each tenant has an active model endpoint or isolated model serving route with version pinning. | Must | Extraction requests use the correct active tenant model version. |
| FR-09 | Runtime extraction stores entity values, confidence, normalized value, source span, model version, and review status. | Must | Every extracted record is auditable and correctable. |
| FR-10 | Tenant users can review extraction results and correct low-confidence or incorrect entities. | Should | Corrections can be fed back into future training datasets. |
| FR-11 | Conversational UI can answer questions from extracted structured data and cite document/entity sources. | Should | Responses are tenant-scoped and include source references where possible. |
| FR-12 | Reports provide entity coverage, extraction volume, confidence distribution, review backlog, and business metrics. | Should | Reports can be filtered by date, document type, entity type, and model version. |
| FR-11 | System shall maintain an OpenSpec change package for every product, platform, model, and chatbot capability before implementation starts. | Must | Each delivered slice links to openspec/changes/\<change-id\>/proposal.md, design.md, spec.md, tasks.md, and evidence/. |
| FR-12 | System shall use OpenCode-assisted engineering with bounded agents for planning, coding, review, QA, security, and MLOps tasks. | Should | OpenCode sessions reference AGENTS.md and task-specific agent instructions; generated changes are traceable to approved OpenSpec tasks. |
| FR-13 | System shall archive completed OpenSpec changes into source-of-truth specifications after implementation evidence is accepted. | Must | Completed changes are moved to archive and durable specs are updated to reflect current product behavior, APIs, data contracts, and operational rules. |

# **6\. Non-Functional Requirements**

| Category | Requirement |
| :---- | :---- |
| Security | Strict tenant isolation across documents, annotations, extracted data, model artifacts, logs, and vector/search indexes. |
| Privacy | No tenant content should be used for another tenant model unless explicit opt-in and legal agreement exist. |
| Auditability | Every extraction must record source document, span offsets, entity config version, model version, timestamp, and actor/system action. |
| Availability | Runtime extraction and chatbot should be independently scalable from training workloads. |
| Scalability | Training jobs should run asynchronously with GPU-capable workers; inference should support horizontal scaling and model warmup strategy. |
| Performance | Batch extraction should process large document sets asynchronously; interactive chatbot responses should target sub-10-second response for common report queries. |
| Observability | Collect metrics for ingestion, OCR, annotation throughput, training duration, model quality, inference latency, and extraction confidence. |
| Governance | Model promotion requires metric thresholds, approval, lineage capture, and rollback mechanism. |
| Maintainability | All features must be delivered via AI-native SDD artifacts: proposal, design, spec, tasks, tests, and evidence. |

# **7\. Target Workflow**

| Step | Workflow | Owner | Output |
| :---- | :---- | :---- | :---- |
| 1 | Provision tenant and define isolation policy. | System Admin | Tenant record, storage namespace, DB schema/database, model namespace. |
| 2 | Tenant admin defines required entity catalog. | Tenant Admin | Versioned entity configuration. |
| 3 | Tenant uploads sample documents for training. | Tenant Admin/User | Raw documents and parsed text with offsets. |
| 4 | System creates annotation tasks and optional pre-labels. | Platform | Annotation queue. |
| 5 | Annotators label and reviewers approve. | Tenant Reviewer | Approved training dataset version. |
| 6 | Training job fine-tunes a tenant model. | System Admin / ML Pipeline | Candidate model version with metrics. |
| 7 | Candidate model is evaluated and promoted. | System Admin / Tenant Admin | Active model version. |
| 8 | Tenant users upload operational documents. | Tenant User | Documents queued for extraction. |
| 9 | Runtime extraction stores structured records. | Platform | Tenant DB records with source references. |
| 10 | Chatbot/reports answer over extracted data. | Tenant User | Conversational answers, dashboards, exports. |

# **8\. Logical Architecture**

* **Web/Admin Portal:** Tenant administration, entity catalog, upload management, annotation/review screens, model lifecycle, reports, chatbot.  
* **API Gateway and Backend:** Tenant-aware APIs, authz, orchestration, validation, audit logging, and asynchronous job submission.  
* **Document Processing Service:** File validation, malware scan hook, OCR, text extraction, chunking, tokenization, layout metadata, and source mapping.  
* **Annotation Service:** Label task management, pre-labeling, reviewer workflow, dataset export in BIO/IOB2 format.  
* **Training Orchestrator:** Creates tenant-specific training jobs, records lineage, manages GPU workers, persists metrics and artifacts.  
* **Model Registry:** Stores base model reference, tenant model versions, metrics, approval status, artifact URI, and deployment status.  
* **Model Serving Layer:** Per-tenant endpoint/pod/service or isolated routing layer with version pinning and autoscaling.  
* **Extraction Service:** Runs active model, applies post-processing and validation rules, stores entities and normalized records.  
* **Analytics and Conversational Layer:** SQL/reporting, semantic search where needed, RAG/agent tools constrained to tenant extracted data.  
* AI-Native Delivery Workspace: AGENTS.md, OpenCode agent definitions, OpenSpec source-of-truth specs, change packages, ADRs, prompt/command logs, and delivery evidence.  
* **Storage and Databases:** Object storage for documents/artifacts; relational DB for metadata/entities; optional search/vector index for document retrieval.

# **9\. Data Model \- Core Entities**

| Entity/Table | Purpose | Key Fields |
| :---- | :---- | :---- |
| tenant | Tenant master record. | tenant\_id, name, status, isolation\_policy, quotas. |
| entity\_definition | Tenant configured NER labels and extraction rules. | entity\_id, tenant\_id, name, description, examples, validation\_rule, target\_table, version. |
| document | Uploaded document metadata. | document\_id, tenant\_id, filename, mime\_type, checksum, storage\_uri, status. |
| document\_text\_span | Text with offsets and layout references. | span\_id, document\_id, page\_no, block\_no, text, start\_offset, end\_offset. |
| annotation\_task | Annotation and review workflow. | task\_id, document\_id, assignee, status, reviewer, dataset\_version. |
| annotation\_label | Human-labeled entity spans. | label\_id, task\_id, entity\_id, token\_start, token\_end, value. |
| training\_job | Tenant model creation job. | job\_id, tenant\_id, dataset\_version, base\_model, status, metrics\_uri. |
| model\_version | Model registry entry. | model\_id, tenant\_id, version, artifact\_uri, metrics, status, active\_flag. |
| extraction\_run | Runtime extraction batch/job. | run\_id, tenant\_id, document\_id, model\_version, status. |
| extracted\_entity | Extracted entity result. | result\_id, run\_id, entity\_id, value, confidence, normalized\_value, source\_span, review\_status. |

# **10\. AI-Native SDD Requirements**

* Every feature must start from a proposal.md capturing business intent, measurable outcomes, out-of-scope, constraints, and risks.  
* design.md must capture architecture decisions, data boundaries, model lifecycle, tenant isolation, failure modes, and observability.  
* spec.md must use testable SHALL statements and acceptance criteria.  
* tasks.md must split implementation into small, reviewable slices with evidence expectations.  
* ADR records are mandatory for model-per-tenant strategy, tenant data isolation, OpenSpec workflow governance, OpenCode agent permissions, training infrastructure, model serving topology, and chatbot guardrails.  
* Evidence folder must include test results, API contract validation, security checks, model evaluation metrics, sample extraction outputs, and review notes.

# **11\. Risks and Mitigations**

| Risk | Impact | Mitigation |
| :---- | :---- | :---- |
| Insufficient annotated data per tenant | Poor model quality and low trust. | Introduce minimum dataset thresholds, active learning, pre-labeling, data augmentation review, and manual approval gates. |
| Highly visual/scanned documents | BERT token classifier may miss layout-dependent fields. | Add OCR confidence, layout metadata, and evaluate LayoutLM/Donut-style models for form-heavy tenants. |
| Too many tenant-specific models | High operational cost and deployment complexity. | Support model pooling only for opted-in tenants; use autoscaling, model warmup, quantization, and endpoint hibernation for low-volume tenants. |
| Cross-tenant data leakage | Critical security/privacy breach. | Hard tenant\_id enforcement, separate namespaces, encryption boundaries, policy tests, and audit logs. |
| Chatbot hallucination | Incorrect business answers. | Constrain agent tools to tenant data APIs, require source references, use SQL validation, and block unsupported answers. |
| Model drift | Quality degrades as document formats change. | Track corrections, confidence trends, periodic re-evaluation, and retraining triggers. |

# **12\. Success Metrics**

| Metric | Target for Pilot | Target for Production |
| :---- | :---- | :---- |
| Entity-level F1 on tenant validation set | \>= 0.80 for high-volume entities | \>= 0.90 for mature tenants/entities |
| Extraction traceability | 100% of extracted entities include source span and model version | 100% maintained |
| Manual review reduction | 30% reduction after first model iteration | 60%+ reduction after mature feedback loop |
| Tenant data isolation test pass rate | 100% | 100% |
| Model deployment rollback time | \< 30 minutes | \< 10 minutes |
| AI-native evidence completeness | All promoted features include spec, tests, and evidence | Mandatory release gate |

# **13\. Source Notes**

The referenced dslim/bert-base-NER model is a MIT-licensed Hugging Face token-classification model based on bert-base-cased and fine-tuned on the English CoNLL-2003 NER dataset. It recognizes LOC, ORG, PER, and MISC and reports strong CoNLL evaluation metrics, but the model card notes domain and post-processing limitations. Source: https://huggingface.co/dslim/bert-base-NER

# **14\. OpenCode and OpenSpec Delivery Requirements**

The project shall use OpenSpec as the governing SDD framework and OpenCode as the AI coding agent interface. The purpose is to prevent vague prompt-driven implementation, keep product intent durable, and make every code/model/infrastructure change auditable.

## **14.1 OpenSpec Source-of-Truth Rules**

* The repository shall be initialized with openspec/ and shall maintain durable source-of-truth specs for tenant management, entity catalog, document ingestion, annotation, model lifecycle, extraction runtime, chatbot/reporting, security, and operations.  
* Every change shall start as a named change package under openspec/changes/\<change-id\>/ with proposal.md, design.md, spec.md, tasks.md, and evidence/.  
* proposal.md shall capture business intent, measurable outcomes, out-of-scope items, assumptions, constraints, impacted tenants, data sensitivity, and risks.  
* design.md shall capture architecture, API/data contract impact, model lifecycle impact, failure modes, observability, security controls, and rollback strategy.  
* spec.md shall contain testable SHALL requirements and Given/When/Then acceptance scenarios.  
* tasks.md shall decompose work into bounded implementation slices that can be reviewed independently.  
* After acceptance, each completed change shall be archived and the durable source-of-truth specs shall be updated to reflect the current product behavior.

## **14.2 OpenCode Working Rules**

* OpenCode shall be used for agentic planning, code generation, refactoring, tests, documentation, and review, but not as an uncontrolled autonomous committer.  
* AGENTS.md shall define repository-wide rules: tenant isolation is non-negotiable, no cross-tenant data access, no code without approved OpenSpec tasks, no schema change without migration and rollback notes, and no model promotion without evaluation evidence.  
* Dedicated OpenCode agents shall be configured for plan/architecture, backend, frontend, MLOps, QA, security review, and documentation tasks.  
* The plan agent shall be used for analysis and review-only work where code changes are not allowed.  
* Developer agents shall operate only against approved tasks and must update evidence with tests, screenshots, logs, metrics, or review notes as applicable.  
* Security and QA agents shall run independently from the implementation agent before merge.

## **14.3 Mandatory Repository Artifacts**

| Artifact | Purpose | Required Content |
| :---- | :---- | :---- |
| AGENTS.md | Repository-level AI engineering policy. | Coding standards, tenant isolation rules, SDD workflow, evidence expectations, security constraints, prohibited actions. |
| .opencode/agents/ | OpenCode role definitions. | Planner, architect reviewer, backend, frontend, MLOps, QA, security, and documentation agents. |
| openspec/project.md | Project principles and context. | Product vision, domain terms, architecture constraints, delivery principles, quality bars. |
| openspec/specs/ | Current source-of-truth behavior. | Durable feature specs for tenant, ingestion, annotation, training, serving, extraction, chatbot, and operations. |
| openspec/changes/\<change-id\>/ | Proposed and active implementation changes. | proposal.md, design.md, spec.md, tasks.md, evidence/. |
| docs/adr/ | Architectural decision records. | Tenant isolation, model topology, OpenCode permissions, OpenSpec governance, serving design, chatbot guardrails. |

## **14.4 Delivery Gates**

| Gate | Owner | Entry Criteria | Exit Criteria |
| :---- | :---- | :---- | :---- |
| Intent Gate | Product Owner \+ Architect | Problem and tenant value are understood. | OpenSpec proposal accepted with success metrics and scope boundaries. |
| Design Gate | Architect \+ Security \+ MLOps | Proposal approved. | Design covers data isolation, APIs, runtime, model lifecycle, risks, rollback, and observability. |
| Implementation Gate | Seed Engineer | Spec and tasks approved. | OpenCode implementation maps to tasks and contains tests/migrations/contracts. |
| Evidence Gate | QA \+ Security \+ Architect | Implementation complete. | Evidence folder contains test results, validation outputs, screenshots/logs, model metrics, and review notes. |
| Archive Gate | Architect \+ Product Owner | Evidence accepted. | OpenSpec change archived and source-of-truth specs updated. |

## **14.5 Source Notes for Tooling**

OpenCode reference: https://opencode.ai/docs/ \- open-source AI coding agent available through terminal, desktop, and IDE workflows, with configurable specialized agents.

OpenSpec reference: https://openspec.pro/ \- lightweight open-source SDD framework for AI coding assistants using proposals, specs, design, tasks, implementation, and archive flow.