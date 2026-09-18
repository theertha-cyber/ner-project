# Graph Report - ner-project  (2026-09-15)

## Corpus Check
- 1926 files · ~1,935,876 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 22633 nodes · 35369 edges · 1392 communities (1260 shown, 38 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1128 edges (avg confidence: 0.92)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `74fe6d4c`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- FakeSession
- integration_profile/service.py
- authFetch
- AnnotationPage.tsx
- extraction.ts
- entity_eval/runner.py
- test_annotation_import.py
- ocr_worker.py
- DocumentIngestionService
- provision_tenant_data_plane
- SQLGenerator
- _spec
- entity_views.py
- RetrievalResult
- FakeSession
- chat.py
- test_context_assembly_path_equivalence.py
- shared/auth.py
- data-sources.ts
- domain_metrics.py
- _reconcile
- support.js
- vitest
- build_role_statements
- DenseRetriever
- NotFoundError
- @testing-library/user-event
- RetrievalConfig
- context-usage.ts
- test_chat_api_streaming.py
- ContentStore
- TestStructuredValueSQLExecution
- build_chat_graph
- EntityDefinitionSpec
- RAGOrchestrator
- _spec
- shared/config.py
- eval/runner.py
- blob_sync/__init__.py
- _validate_on_surface
- gateway/main.py
- test_chunk_metadata_ingest.py
- chat_proxy.py
- _predict
- schema_for_tenant
- external_postgres/__init__.py
- documents.py
- test_document_ingestion.py
- test_inference_endpoint.py
- GuardrailService
- mlflow_registry.py
- _get
- gateway/api/v1/dashboard.py
- insert_document_entities
- test_azure_blob_source_sync.py
- build_default_registry
- session_factory
- require-auth.tsx
- MODIFIED Requirements
- verify
- react
- app
- ExternalSQLGenerator
- is_valid_entity
- Requirement: Retriever interface
- RetrievalStatus
- data_plane.py
- tracked_tenants
- NormalizedEntity
- canonicalize
- Requirement: Deactivation and orphaning never drop a generated relation
- DocumentTable.tsx
- test_retrieval_tools_integration.py
- _get
- test_entity_definition_reconcile.py
- test_external_postgresql_chat.py
- _entity
- test_llm_usage_metrics.py
- test_annotation_workspace.py
- check_regression
- test_telemetry_scan.py
- test_extraction_worker_postprocess_failopen.py
- stage_span
- ContextAssembler
- test_conversation_history_reaches_retrieval.py
- test_training_jobs_api.py
- test_chat_stage_spans.py
- NER Platform KT Handover Guide
- Entity-Quality Evaluation Fixture README
- test_chat_api_structured_scope.py
- _entity
- _create
- test_model_registry.py
- OpenSpec CLI
- test_external_sql_generator.py
- AnalyticsQueryRequest
- extraction.py
- normalize_value
- nodes.py
- test_telemetry_failure_isolation.py
- training_jobs.py
- test_celery_queue_metrics.py
- _entity
- test_document_content_hash.py
- test_inference_windowing.py
- _get_sync_engine
- _entity
- _insert_entity
- test_inference_confidence_calibration.py
- analytics_service/api/v1/schemas.py
- annotation_service/main.py
- entity_resolver.py
- inference_service.py
- AppError
- auth_header
- test_entity_views_reconciler.py
- configured
- test_mlflow_verification.py
- analytics/page.tsx
- Requirement: Get training job status
- telemetry_scan.py
- test_no_pii_in_logs.py
- Requirement: Batch Runs Tab — Batch Extraction Management
- _entity
- test_migration_037_entity_view_metadata.py
- collapse_duplicates
- ModelCache
- TestSQLPrompt
- test_extraction_metrics.py
- OpenSpec CLI
- ADDED Requirements
- ADDED Requirements
- test_inference_metrics.py
- test_domain_metrics_declarations.py
- test_batch_extraction_eligibility.py
- test_entity_span_trimming.py
- auth_header
- TestSelectionInterpretation
- Candidate
- Requirement: Base Model (Version 0) Entry
- test_orchestrator_integration.py
- _prompt_for
- test_sysadmin_user_onboarding.py
- Requirement: SQL query generation and validation
- Decisions
- reconstruct_entities
- Requirements
- create_access_token
- test_training_metrics.py
- test_observability_wiring.py
- Settings
- model_serving/api/v1/schemas.py
- _app
- Requirement: Document Upload Zone
- Requirements
- Requirement: SQL query generation and validation
- ADDED Requirements
- v1/tasks.py
- backfill_document_entities.py
- DefineEntityTypeSlideOver.tsx
- test_projection_metrics.py
- test_imported_annotations_update.py
- TestMigration036ExtractionRunsProcessingMode
- test_warmup_endpoint.py
- OpenSpec Onboard Skill
- semantic_normalizer.py
- compilerOptions
- v1/models.py
- _get
- test_tenant_document_registry_reconcile.py
- test_entity_postprocessor_tenant_scope.py
- external_pg_contracts.py
- Requirement: Tenant data engines are resolved per tenant with no platform fallback
- auth_header
- OpenSpec CLI
- ADDED Requirements
- TestMigration035DocumentEntitiesProvenance
- architect-reviewer skill
- test_external_pg_contract_descriptions.py
- Decision
- chat_api/test_retrieval_metrics.py
- TestSQLValidation
- test_document_visibility.py
- TestMigration029DocumentEntitiesTypedValues
- data_sources/service.py
- ADDED Requirements
- Requirement: Versioned tenant-isolated schema contracts
- Requirements
- _post_feedback
- test_document_provenance_migration.py
- Requirement: Safe activation and concurrent capability limits
- FakeUpstreamResponse
- Document Ingestion Source Boundary (architecture proposal)
- types/dashboard.ts
- _get_active_model_version
- Requirements
- TestEntityConfigValueKind
- test_migration_032_chat_message_feedback.py
- evaluate_answer
- Requirements
- auth_header
- test_health_endpoints.py
- TestMigration026DocumentEntities
- TestMigration028EntityDefinitionValueKind
- OpenSpec Store (registered standalone repo)
- OpenSpec Onboard Skill
- Requirement: Safe connection lifecycle interface
- MODIFIED Requirements
- ADDED Requirements
- ADDED Requirements
- ADDED Requirements
- TestBackfillDocumentEntities
- _get_summary
- test_entity_config.py
- test_extraction_api.py
- test_migration_027_conversation_entity_state.py
- TestMlflowServerLive
- Requirements
- ADDED Requirements
- apply_to_all_tenant_schemas
- tenant-postgresql-data-plane/tasks.md
- Requirements
- TestTenantAdminQueries
- test_dashboard_tenant_enumeration.py
- test_migration_022_guard.py
- Requirements
- TestSetupTestDbGuard
- ADDED Requirements
- portal/package.json
- ADDED Requirements
- Requirement: Async OCR Processing
- ADDED Requirements
- TestAMalformedSchemaIsCountedAndLogged
- ADDED Requirements
- _run_tenant_schema_ddl
- TestTenantSchemaReconciliation
- test_data_plane_failure_isolation.py
- Decomposition: Tenant Self-Service Data Sources
- Release-gate telemetry scan (scripts/telemetry_scan.py)
- Tenant Self-Service Data Sources — requirements baseline v1.2
- tokenizer-registry.d.ts
- Requirement: Safe connection lifecycle interface
- ADDED Requirements
- test_tenant_provisioning.py
- PROJECT.md — Multi-Tenant Custom NER Platform
- 038_document_provenance_and_retention.py
- devDependencies
- Iris Run: add-doc-docx-upload-support
- Deploy Platform to Kubernetes on Azure (AKS) — requirements baseline
- package.json
- validate_name_labels.py
- validator.py
- ADDED Requirements
- ADDED Requirements
- Requirements
- Requirements
- extraction_proxy.py
- TestBusinessUserQueries
- Requirement: Contract-authorized SQL execution
- c4-diagram skill
- Decisions
- clean_name_labels.py
- test_mlflow_integration_live.py
- Requirements
- Requirements
- Requirement: Per-Entity-Type Dataset Readiness
- ADDED Requirements
- test_dashboard_summary.py
- TestParseOrdinalSelection
- TestWorkerSemanticNormalization
- Requirements
- Requirement: Secondary Metrics Panel
- preprocess_tokenization.py
- Requirement: Define / Edit Entity Type Slide-Over
- TestFeedbackTableIndependence
- test_context_assembly_grep.py
- TestWorkerNormalizesEntitiesOnIngest
- ADDED Requirements
- P3 — Derived relational persistence: connection routing, not a repository abstraction
- UI Inventory — Tenant Self-Service Data Sources (SCR-1/2/3, CMP-1..10)
- build_name_review_report.py
- _active_model_card
- Requirement: Annotation Task Management
- Requirement: Sidebar Layout
- _JwtOnlyTenantMiddleware
- TestTheSharedMiddlewareMakesNoSecurityDecision
- ADDED Requirements
- Requirements
- ADDED Requirements
- ADDED Requirements
- Requirements
- Requirement: Ephemeral retention uses a bounded working copy
- 002_tenant_template_schema.py
- 035_document_entities_provenance.py
- 039_tenant_integration_profiles.py
- Multi-tenant NER Platform investor/exec deck (scroll-snap slide deck)
- extends
- ADDED Requirements
- setup_test_db.py
- Requirement: Contract-authorized SQL execution
- MODIFIED Requirements
- Requirement: Client-Side File Preview
- Requirement: System Admin Cross-Tenant User Creation Endpoint
- TestStatusToStageMapping
- ADDED Requirements
- next.config.js
- opencode.json
- graphify.js
- prettier.config.js
- QA report for add-doc-docx-upload-support: conditional pass, unit/integration tests blocked by missing PostgreSQL
- Requirement: Client-Side File Preview
- ADDED Requirements
- ADDED Requirements
- Widget Key Tester
- context_usage tool
- InApp Logo - Vector (RGB).svg
- Favicon — light theme SVG
- next-env.d.ts
- postcss.config.js
- config
- docker-compose otel-collector service
- Local Development: Clean Database Rebuild procedure
- NER Platform.html (bundled/generated placeholder page)
- Mandatory ADR topics ADR-001..ADR-007: tenant isolation, base model strategy, serving topology, OpenSpec governance, agent permissions, training infra, chatbot RAG guardrails
- OpenCode Ask Agent Command
- ner-project
- ADDED Requirements
- data_sources.py
- Requirement: Contract-authorized SQL execution
- Requirement: Guardrail — blocked question types
- Requirement: System Admin Cross-Tenant User Creation Endpoint
- Requirement: Audit Log Page Tenant Filter UI
- Requirement: Define / Edit Entity Type Slide-Over
- MODIFIED Requirements
- Requirement: Define / Edit Entity Type Slide-Over
- Requirement: Bounded relational surface and value samples in the generation context
- ADDED Requirements
- ADDED Requirements
- Requirement: Dashboard Summary Endpoint
- Requirement: Token-budgeted context assembly
- Requirements
- Requirement: Annotation Task Management
- Requirement: Entity Review Tab — Entity Listing and Review
- ADDED Requirements
- Requirement: Document Upload Zone
- ADDED Requirements
- Requirement: Sidebar Layout
- ADDED Requirements
- Requirement: Sidebar Layout
- ADDED Requirements
- Requirement: Dashboard Summary Endpoint
- Requirements
- Requirements
- Requirements
- ADDED Requirements
- Requirement: Batch extraction
- Requirement: SQL query generation and validation
- Requirements
- Requirement: SQL query generation and validation
- Requirement: Dashboard Summary Endpoint
- Requirement: Promote model version
- SlidingWindowRateLimiter
- ADDED Requirements
- ADDED Requirements
- Requirement: Extraction Service Endpoints Auto-Resolve Tenant ID from JWT
- Requirement: Layout and Navigation
- Decisions
- ADDED Requirements
- ADDED Requirements
- Requirement: Get training job status
- ADDED Requirements
- ADDED Requirements
- Requirements
- Requirement: A generated `subject` column's physical type equals the type its definition declares
- Requirements
- Requirement: useToast hook and ToastProvider
- 2026-07-13-fix-model-loading-and-label-mapping/design.md
- Requirement: Stable Inter-Service Communication via Docker DNS
- Decisions
- Decisions
- Requirement: Dashboard Summary Endpoint
- Requirements
- Requirement: Environment Configuration Loading
- ADDED Requirements
- Requirement: Get training job status
- ADDED Requirements
- Requirement: useToast hook and ToastProvider
- Requirement: Sidebar Layout
- ADDED Requirements
- MODIFIED Requirements
- Requirement: Continue-Work Card Payload
- ADDED Requirements
- Decisions
- ADDED Requirements
- Decisions
- Requirement: SQL query generation and validation
- Requirement: Message feedback submission endpoint
- Requirement: A generated `subject` column's physical type equals the type its definition declares
- Requirement: Common durable Blob ingestion
- Requirements
- Requirement: Common durable Blob ingestion
- Requirement: Tenant Admin Dashboard Queries
- Requirement: Entity Type Definition
- Requirement: Tenant Admin Dashboard Queries
- Requirement: Get training job status
- Requirement: Annotation Action Bar
- Decisions
- ADDED Requirements
- 2026-09-08-entity-relational-projection/tasks.md
- Requirement: Entity Review Tab — Entity Listing and Review
- Requirement: Dashboard Summary Endpoint
- Requirement: Job list card content
- Requirement: Activity Panel
- Decisions
- Requirement: Structured Query API
- Requirements
- Requirement: Batch extraction
- Requirement: Per-Tenant Integration Credentials Are References Only
- Requirement: User Authentication
- MODIFIED Requirements
- Requirement: Sidebar Layout
- ADDED Requirements
- ADDED Requirements
- Requirement: Structured Query API
- Requirement: Document Upload
- MODIFIED Requirements
- Decisions
- What Changes
- Requirement: Batch extraction
- Decisions
- Decisions
- Requirement: Wrong-entity-type defect detection
- Requirement: Approve training job
- Requirement: Widget API key management
- test_chat_api_retrieval_status.py
- data_sources/__init__.py
- _FakeResult
- ADDED Requirements
- ADDED Requirements
- ADDED Requirements
- 2026-06-23-sp-06-rag-chatbot/tasks.md
- Design: Model Registry Promote
- ADDED Requirements
- Decisions
- Decisions
- Decisions
- Decisions
- Requirement: Post-migration schema verification
- Requirements
- Requirement: Approve training job
- test_tenant_store_provisioning.py
- Verification Plan
- ADDED Requirements
- ADDED Requirements
- Decisions
- Decisions
- Decisions
- Requirement: Dashboard Summary Endpoint
- Requirement: Persist Audit Events
- Requirement: RAG chat endpoint
- Requirement: Fixed topology with no agentic behaviour
- What Changes
- Requirement: Multi-subject resolution scopes to every matched document
- Verification Plan
- Requirement: Dataset-to-model lineage diagram
- Decisions
- Verification Plan
- Decisions
- Requirement: Single semantic retrieval capability with internal scope
- Requirement: SQL query generation and validation
- Decisions
- Requirement: Dashboard Summary Endpoint
- Requirement: RAG chat endpoint
- Requirement: Orb-burst overlay on successful sign-in
- Requirement: Model warmup on promotion
- Requirement: Task Assignment Form
- 2026-06-10-sm-03-annotation-workspace/design.md
- 2026-06-11-sm-04-training-pipeline/design.md
- ADDED Requirements
- ADDED Requirements
- 2026-06-16-portal-auth/design.md
- 2026-06-16-portal-foundation/design.md
- ADDED Requirements
- Requirement: Query extracted entities
- 2026-06-22-annotation-ui-fixes/design.md
- ADDED Requirements
- Requirement: Structured Query API
- 2026-06-29-sp-10-model-registry/design.md
- 2026-06-30-fix-dashboard-queries/tasks.md
- Requirement: Post-migration schema verification
- Requirement: Existing tenant schemas are reconciled to the current template shape
- Requirement: Retriever interface
- 2026-09-08-chat-conversation-and-citations/design.md
- Requirement: Citation card display
- 2026-09-08-document-content-hash-and-batch-select-all/design.md
- Requirement: SQL query generation and validation
- Requirement: Base Model (Version 0) Entry
- 2026-09-08-response-feedback-rating/design.md
- Requirement: Dashboard Data Shape
- Requirement: Auth Context Provider
- Requirement: Auth Fetch 401 Silent Refresh
- Verification Plan
- 2026-06-08-sm-01-identity-tenant-entity-config/design.md
- ADDED Requirements
- Verification Plan
- Verification Plan
- 2026-06-09-sm-02-document-ingestion/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-15-sm-05-extraction-engine/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Orb-burst overlay on successful sign-in
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-17-portal-dashboard/tasks.md
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Environment Configuration Loading
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-19-sidebar-action-menu/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-22-sp-05-annotation-workspace/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-23-sp-06-rag-chatbot/design.md
- Verification Plan
- Requirement: RAG chat endpoint
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-06-25-annotation-mockup-alignment/design.md
- 2026-06-25-annotation-mockup-alignment/tasks.md
- Verification Plan
- 2026-06-25-app-shell-exact-mockup/design.md
- 2026-06-25-app-shell-exact-mockup/tasks.md
- Verification Plan
- 2026-06-25-app-shell-v2/design.md
- Verification Plan
- 2026-06-25-fix-entity-types-api-alignment/design.md
- Verification Plan
- 2026-06-25-sp05-annotation-workspace/design.md
- Verification Plan
- Verification Plan
- 2026-06-25-sp-08-documents/design.md
- Verification Plan
- Verification Plan
- Requirement: Task Assignment Form
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-07-01-annotation-file-upload/design.md
- Verification Plan
- 2026-07-01-portal-extraction-page/design.md
- Verification Plan
- Requirement: List extraction runs
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-07-07-add-annotation-import-button/design.md
- Verification Plan
- ADDED Requirements
- Verification Plan
- Requirement: Dashboard Summary Endpoint
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-07-13-redesign-training-jobs-ui/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Dashboard Summary Endpoint
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-09-08-annotator-dashboard-cards-and-per-entity-readiness/tasks.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Batch Runs Tab — Batch Extraction Management
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Rename conversation endpoint
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Requirement: Reranking retriever composition
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-09-08-model-registry-tenant-scoping-run-naming/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- REMOVED Requirements
- Verification Plan
- 2026-09-08-redesign-system-admin-dashboard/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- Verification Plan
- 2026-09-08-subject-column-type-convergence/design.md
- Verification Plan
- 2026-09-08-sysadmin-user-onboarding/design.md
- Verification Plan
- Verification Plan
- 2026-09-08-tenant-dashboard-workspace-refresh/design.md
- Verification Plan
- Verification Plan
- Verification Plan
- Requirements
- Requirement: Async OCR Processing
- Requirement: Login Page Layout and Submission
- Requirement: Query Error Banner
- Requirement: Widget Keys Screen
- 2026-06-08-tenant-admin-user-mgmt/design.md
- 2026-06-11-training-approval-gate/design.md
- 2026-06-12-mlflow-integration/design.md
- 2026-06-15-promote-warmup-integration/design.md
- ADDED Requirements
- Requirement: Auth Fetch 401 Silent Refresh
- 2026-06-16-portal-shell/design.md
- 2026-06-17-add-login-dashboard-transition/design.md
- 2026-06-17-fix-batch-extraction-worker/design.md
- 2026-06-17-portal-dashboard/design.md
- 2026-06-18-default-base-model/design.md
- MODIFIED Requirements
- 2026-06-18-enforce-env-secrets/design.md
- Requirement: Automated Database Initialization on Compose Up
- Requirement: Sidebar Layout
- 2026-06-22-sp-05-annotation-workspace/tasks.md
- 2026-06-23-tenant-from-jwt-in-chat-api/design.md
- 2026-06-24-analytics-and-reporting/design.md
- 2026-06-24-sp-07/design.md
- 2026-06-25-align-dashboard-to-mockup/design.md
- 2026-06-25-sp-04-dashboard/design.md
- Requirement: Dashboard Summary Endpoint
- 2026-06-25-sp-09-entity-types/design.md
- 2026-06-29-assign-annotation-tasks/design.md
- 2026-07-08-fix-tenant-schema-drift-and-training-worker-config/design.md
- 2026-07-08-review-imported-annotations/design.md
- Requirement: Typed retrieval domain model
- 2026-07-29-annotation-completion-workflow/design.md
- 2026-09-08-audit-log-page/design.md
- 2026-09-08-audit-log-tenant-filter/design.md
- Requirement: Audit Log Page Tenant Filter UI
- Requirement: RAG chat endpoint
- 2026-09-08-cloud-readiness-resilience/design.md
- 2026-09-08-dockerize-portal-and-fix-build-hygiene/design.md
- 2026-09-08-entity-quality-postprocessing/tasks.md
- 2026-09-08-entity-resolution-disambiguation/tasks.md
- 2026-09-08-merge-bio-entity-display/design.md
- Requirement: List model versions
- Requirement: Batch extraction
- 2026-09-08-redesign-business-user-dashboard/design.md
- Requirement: The query-surface resolver is the one authoritative description of the readable relations
- 2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/design.md
- Requirements
- Requirement: BIO Tag Persistence on Spans
- Requirement: Manual Blob sync trigger action
- Requirements
- Requirement: Tenant-Admin User CRUD Endpoints
- lifecycle.py
- ADDED Requirements
- 2026-06-08-env-config-setup/design.md
- ADDED Requirements
- 2026-06-08-sm-01-identity-tenant-entity-config/tasks.md
- Requirement: Reject training job
- Requirement: Submit training job
- Requirement: Auth Context Provider
- Requirement: Login Page Layout and Submission
- 2026-06-16-remove-tid-from-url/design.md
- 2026-06-17-add-celery-extraction-worker/design.md
- 2026-06-17-fix-extraction-run-persistence/design.md
- 2026-06-18-dockerize-backend-services/design.md
- 2026-06-18-mlflow-test-verification/design.md
- 2026-06-19-fix-postgres-persistence-and-db-init/design.md
- ADDED Requirements
- 2026-06-24-sp-06/design.md
- Requirement: Widget Keys Screen
- 2026-06-30-fix-dashboard-queries/design.md
- 2026-07-02-batch-extraction-run-history/design.md
- 2026-07-02-fix-prelabel-keyword-search/design.md
- 2026-07-06-fix-analytics-materialized-views/design.md
- ADDED Requirements
- 2026-07-07-fix-analytics-query-feedback/design.md
- 2026-07-08-fix-system-admin-training-queue-bugs/design.md
- 2026-07-09-fix-mlflow-model-logging/design.md
- 2026-07-13-fix-model-loading-and-label-mapping/tasks.md
- 2026-07-13-redesign-training-jobs-ui/tasks.md
- 2026-07-16-fix-model-serving-tenant-query/design.md
- 2026-07-27-clean-rebuild-and-schema-hardening/tasks.md
- Requirement: Annotation Task Management
- Requirement: Batch extraction
- Requirement: Annotation Task Management
- Requirement: Fixed topology with no agentic behaviour
- Requirement: Dashboard Summary Endpoint
- 2026-09-08-batch-extraction-document-selection/design.md
- 2026-09-08-cap-1-add-doc-docx-upload-support/design.md
- 2026-09-08-chat-auto-titles-and-rename/design.md
- 2026-09-08-chat-conversation-and-citations/tasks.md
- Requirement: Document Content Hashing and Duplicate Identification
- Requirement: `document_entities` gains provenance columns on the template and every tenant schema
- Requirement: Document Metadata API
- Requirement: Batch Runs Tab — Batch Extraction Management
- 2026-09-08-normalized-entity-store/tasks.md
- 2026-09-08-observability-workload-instrumentation/tasks.md
- 2026-09-08-relational-only-sql-generation/tasks.md
- 2026-09-08-response-feedback-rating/tasks.md
- Requirement: Semantic value columns are added to the template and every existing tenant schema
- 2026-09-08-structured-entity-value-normalization/tasks.md
- 2026-09-08-system-admin-sets-training-params/design.md
- 2026-09-08-system-admin-sets-training-params/tasks.md
- Requirement: Per-Tenant Integration Credentials Are References Only
- 2026-09-10-cap-2-tenant-scoped-connection-control-plane/design.md
- Requirement: Dark Theme Consistency Across Portal Pages
- Requirement: Document Upload
- Requirement: Multi-Token Drag Span Creation
- Requirements
- Requirement: Fixture setup scripts refuse non-test databases
- SQLAttempt
- Verification Plan
- Requirement: Safe connection lifecycle interface
- ADDED Requirements
- Requirement: Tenant-Admin User CRUD Endpoints
- 2026-06-16-portal-foundation/tasks.md
- Requirement: Role Navigation Matrix
- 2026-06-16-portal-shell/tasks.md
- 2026-06-17-fix-worker-host-routing/design.md
- MODIFIED Requirements
- 2026-06-18-fix-users-tenant-resolution/design.md
- Requirement: Tenant-Admin User CRUD Endpoints
- 2026-06-18-mlflow-test-verification/tasks.md
- 2026-06-19-fix-cors-preflight-middleware/design.md
- Requirement: BIO Tag Persistence on Spans
- 2026-06-22-fix-promote-inprogress-transition/design.md
- 2026-06-23-fix-chat-page-auth/design.md
- 2026-06-25-sp05-annotation-workspace/tasks.md
- 2026-06-25-sp-08-documents/tasks.md
- Requirement: Annotation Task Queue
- 2026-07-08-remove-training-span-gate/design.md
- Changes
- 2026-07-27-document-purpose-scoping/tasks.md
- Approach
- Tasks: Fix Dark Theme Issues Across Portal Pages
- 2026-09-08-agentic-retrieval-loop/tasks.md
- 2026-09-08-annotator-dashboard-ux-refinements/design.md
- 2026-09-08-app-shell-ui-cleanup/design.md
- 2026-09-08-bounded-sql-retry-loop/tasks.md
- Requirement: RAG chat endpoint
- Requirement: Internal inference endpoint
- Requirement: Generated SQL executes under a least-privilege role
- Requirement: Base model confirmation gate on extraction runs
- 2026-09-08-observability-foundation/tasks.md
- Requirement: Orchestrated configuration is measured against the direct baseline
- 2026-09-08-redesign-retrieval-orchestration/tasks.md
- Requirement: Centralized retrieval configuration
- 2026-09-08-retrieval-tools-and-eval/tasks.md
- 2026-09-08-tenant-pluggable-data-foundation/tasks.md
- Requirement: Safe activation and concurrent capability limits
- Requirement: Only platform default adapters are executable in this change
- spec-driven-verified OpenSpec Schema
- Requirement: Role Navigation Matrix
- Requirements
- portal-containerization Specification
- TestChatEndpointTurnShape
- database.py
- test_local_compose_delivery_evidence.py
- test_entity_resolver.py
- ADDED Requirements
- ADDED Requirements
- 2026-06-09-sm-02-document-ingestion/tasks.md
- 2026-06-10-sm-03-annotation-workspace/tasks.md
- 2026-06-15-sm-05-extraction-engine/tasks.md
- Requirement: User Authentication
- 2026-06-16-portal-auth/tasks.md
- Requirement: Authenticated Route Group Layout
- 2026-06-16-remove-tid-from-url/tasks.md
- Requirement: Batch extraction
- 2026-06-17-fix-worker-text-shadowing/design.md
- 2026-06-19-fix-postgres-persistence-and-db-init/tasks.md
- Requirement: Topbar Layout
- Requirement: Multi-Token Drag Span Creation
- 2026-06-22-annotation-ui-fixes/tasks.md
- Requirement: Task Status Lifecycle
- 2026-06-23-fix-chat-api-docker-url/design.md
- 2026-06-24-sp-07/tasks.md
- 2026-06-29-remove-submit-training-job-button/design.md
- Requirement: Batch Runs Tab — Batch Extraction Management
- Requirement: Pre-labeling
- MODIFIED Requirements
- Requirement: Auth Context Provider
- Requirement: Tenant-scoped migrations propagate to existing tenant schemas
- Requirement: Log training run to MLflow Tracking
- Tasks: Model Registry Promote
- Requirement: Model Registry URL is configurable and targets the correct in-network port
- 2026-07-17-fix-seed-promoted-model-conflict/design.md
- Requirement: Fixture setup scripts refuse non-test databases
- Requirement: Document Upload
- Requirement: Dark Theme Consistency Across Portal Pages
- Requirement: Tool results render into bounded LLM observations
- Requirement: Per-Entity-Type Minimum Dataset Gate
- 2026-09-08-audit-log-page/tasks.md
- Requirement: SQL query generation and validation
- 2026-09-08-chat-auto-titles-and-rename/tasks.md
- 2026-09-08-context-assembly-pipeline/tasks.md
- Requirement: Batch Document-Selection Modal — Bulk Selection
- 2026-09-08-fix-batch-runs-scroll-layout/design.md
- 2026-09-08-harden-chat-pipeline-correctness/tasks.md
- 2026-09-08-langgraph-orchestration/tasks.md
- 2026-09-08-multi-document-upload/proposal.md
- 2026-09-08-multi-document-upload/tasks.md
- Requirement: Message thread display
- 2026-09-08-tenant-pluggable-data-foundation/proposal.md
- templates/design.md
- Requirement: Authenticated Route Group Layout
- Requirement: OPTIONS requests bypass authentication middleware
- Requirement: Document Content Hashing and Duplicate Identification
- Requirement: RequireAuth Route Guard
- Verification Plan
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path/design.md
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/design.md
- 2026-09-10-cap-5-tenant-data-source-administration-portal/design.md
- 2026-06-08-env-config-setup/proposal.md
- 2026-06-08-sm-01-identity-tenant-entity-config/proposal.md
- 2026-06-08-tenant-admin-user-mgmt/proposal.md
- 2026-06-09-sm-02-document-ingestion/proposal.md
- 2026-06-10-sm-03-annotation-workspace/proposal.md
- 2026-06-11-sm-04-training-pipeline/proposal.md
- 2026-06-11-training-approval-gate/proposal.md
- 2026-06-12-mlflow-integration/proposal.md
- 2026-06-15-promote-warmup-integration/proposal.md
- Requirement: Promote model version
- 2026-06-15-sm-05-extraction-engine/proposal.md
- 2026-06-16-portal-auth/proposal.md
- 2026-06-16-portal-foundation/proposal.md
- 2026-06-16-portal-shell/proposal.md
- 2026-06-16-remove-tid-from-url/proposal.md
- 2026-06-17-add-celery-extraction-worker/proposal.md
- 2026-06-17-add-login-dashboard-transition/proposal.md
- 2026-06-17-fix-batch-extraction-worker/proposal.md
- 2026-06-17-fix-extraction-run-persistence/proposal.md
- 2026-06-17-fix-worker-host-routing/proposal.md
- 2026-06-17-fix-worker-text-shadowing/proposal.md
- 2026-06-17-portal-dashboard/proposal.md
- 2026-06-18-default-base-model/proposal.md
- 2026-06-18-dockerize-backend-services/proposal.md
- 2026-06-18-enforce-env-secrets/proposal.md
- 2026-06-18-fix-users-tenant-resolution/proposal.md
- 2026-06-18-mlflow-test-verification/proposal.md
- 2026-06-19-fix-cors-preflight-middleware/proposal.md
- 2026-06-19-fix-postgres-persistence-and-db-init/proposal.md
- 2026-06-19-sidebar-action-menu/proposal.md
- 2026-06-22-annotation-ui-fixes/proposal.md
- 2026-06-22-fix-promote-inprogress-transition/proposal.md
- 2026-06-22-sp-05-annotation-workspace/proposal.md
- 2026-06-23-fix-chat-api-docker-url/proposal.md
- 2026-06-23-fix-chat-page-auth/proposal.md
- 2026-06-23-sp-06-rag-chatbot/proposal.md
- 2026-06-23-tenant-from-jwt-in-chat-api/proposal.md
- 2026-06-24-analytics-and-reporting/proposal.md
- 2026-06-24-sp-06/proposal.md
- 2026-06-24-sp-07/proposal.md
- 2026-06-25-align-dashboard-to-mockup/proposal.md
- 2026-06-25-align-dashboard-to-mockup/tasks.md
- 2026-06-25-annotation-mockup-alignment/proposal.md
- 2026-06-25-app-shell-exact-mockup/proposal.md
- 2026-06-25-app-shell-v2/proposal.md
- 2026-06-25-app-shell-v2/tasks.md
- 2026-06-25-fix-entity-types-api-alignment/proposal.md
- 2026-06-25-sp05-annotation-workspace/proposal.md
- 2026-06-25-sp-04-dashboard/proposal.md
- 2026-06-25-sp-08-documents/proposal.md
- 2026-06-25-sp-09-entity-types/proposal.md
- 2026-06-29-assign-annotation-tasks/proposal.md
- 2026-06-29-assign-annotation-tasks/tasks.md
- 2026-06-29-remove-submit-training-job-button/proposal.md
- 2026-06-29-sp-10-model-registry/proposal.md
- 2026-06-29-sp-10-model-registry/tasks.md
- 2026-06-30-fix-dashboard-queries/proposal.md
- 2026-07-01-annotation-file-upload/proposal.md
- 2026-07-01-portal-extraction-page/proposal.md
- 2026-07-01-portal-extraction-page/tasks.md
- 2026-07-02-batch-extraction-run-history/proposal.md
- 2026-07-02-fix-prelabel-keyword-search/proposal.md
- 2026-07-06-fix-analytics-materialized-views/proposal.md
- 2026-07-07-add-annotation-import-button/proposal.md
- 2026-07-07-add-annotation-import-button/tasks.md
- 2026-07-07-fix-analytics-query-feedback/proposal.md
- 2026-07-08-fix-system-admin-training-queue-bugs/proposal.md
- 2026-07-08-fix-system-admin-training-queue-bugs/tasks.md
- 2026-07-08-fix-tenant-schema-drift-and-training-worker-config/proposal.md
- 2026-07-08-remove-training-span-gate/proposal.md
- 2026-07-08-review-imported-annotations/proposal.md
- 2026-07-09-fix-mlflow-model-logging/proposal.md
- ADDED Requirements
- 2026-07-13-fix-model-loading-and-label-mapping/proposal.md
- 2026-07-13-redesign-training-jobs-ui/proposal.md
- 2026-07-16-fix-model-serving-tenant-query/proposal.md
- 2026-07-17-fix-seed-promoted-model-conflict/proposal.md
- 2026-07-24-chunk-metadata-ingest/proposal.md
- 2026-07-24-retrieval-foundation/proposal.md
- 2026-07-27-clean-rebuild-and-schema-hardening/proposal.md
- 2026-07-27-document-purpose-scoping/proposal.md
- 2026-07-27-hybrid-retrieval-hnsw/proposal.md
- Requirement: pgvector semantic search
- 2026-07-29-annotation-completion-workflow/proposal.md
- 2026-09-08-agentic-retrieval-loop/proposal.md
- 2026-09-08-annotator-dashboard-cards-and-per-entity-readiness/proposal.md
- Requirement: Pending Tasks Can Be Started
- Requirement: Deep Link to a Specific Task
- 2026-09-08-annotator-dashboard-ux-refinements/proposal.md
- 2026-09-08-app-shell-ui-cleanup/proposal.md
- 2026-09-08-audit-log-page/proposal.md
- 2026-09-08-audit-log-tenant-filter/proposal.md
- 2026-09-08-batch-extraction-document-selection/proposal.md
- 2026-09-08-bounded-sql-retry-loop/proposal.md
- 2026-09-08-cap-1-add-doc-docx-upload-support/proposal.md
- 2026-09-08-chat-auto-titles-and-rename/proposal.md
- 2026-09-08-chat-conversation-and-citations/proposal.md
- 2026-09-08-chat-response-token-streaming/proposal.md
- 2026-09-08-cloud-readiness-resilience/proposal.md
- 2026-09-08-cloud-readiness-resilience/tasks.md
- 2026-09-08-context-assembly-pipeline/proposal.md
- 2026-09-08-cross-encoder-rerank/proposal.md
- Requirement: Cross-encoder reranking endpoint
- 2026-09-08-cross-encoder-rerank/tasks.md
- 2026-09-08-dockerize-portal-and-fix-build-hygiene/proposal.md
- ADDED Requirements
- 2026-09-08-document-content-hash-and-batch-select-all/proposal.md
- Requirement: Numeric parsing handles a leading numeral followed by trailing words
- 2026-09-08-entity-relational-projection/proposal.md
- 2026-09-08-entity-resolution-disambiguation/proposal.md
- ADDED Requirements
- 2026-09-08-entity-view-layer-foundation/proposal.md
- Requirement: Entity Type Definition
- 2026-09-08-entity-view-layer-foundation/tasks.md
- 2026-09-08-fix-batch-runs-scroll-layout/proposal.md
- 2026-09-08-langgraph-orchestration/proposal.md
- 2026-09-08-model-registry-tenant-scoping-run-naming/proposal.md
- 2026-09-08-model-registry-tenant-scoping-run-naming/tasks.md
- 2026-09-08-normalized-entity-store/proposal.md
- Requirement: Internal inference endpoint
- Requirement: The `document_entities` table exists on the template and every tenant schema
- 2026-09-08-observability-foundation/proposal.md
- 2026-09-08-observability-workload-instrumentation/proposal.md
- 2026-09-08-redesign-business-user-dashboard/proposal.md
- 2026-09-08-redesign-retrieval-orchestration/proposal.md
- 2026-09-08-redesign-system-admin-dashboard/proposal.md
- 2026-09-08-redesign-system-admin-dashboard/tasks.md
- 2026-09-08-relational-only-sql-generation/proposal.md
- 2026-09-08-response-feedback-rating/proposal.md
- 2026-09-08-retrieval-tools-and-eval/proposal.md
- 2026-09-08-structured-entity-value-normalization/proposal.md
- Requirement: Entity Type Definition
- 2026-09-08-subject-column-type-convergence/proposal.md
- 2026-09-08-sysadmin-user-onboarding/proposal.md
- 2026-09-08-sysadmin-user-onboarding/tasks.md
- 2026-09-08-system-admin-sets-training-params/proposal.md
- Requirement: Approve training job
- 2026-09-08-tenant-dashboard-workspace-refresh/proposal.md
- 2026-09-10-cap-2-tenant-scoped-connection-control-plane/proposal.md
- Verification Plan
- 2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/proposal.md
- Verification Plan
- templates/proposal.md
- Requirement: Guardrail — blocked question types
- Requirement: Guardrail — source citation enforcement
- Requirements
- Requirement: Convert trained model to ONNX format
- Requirement: Annotation Task Queue
- Requirement: Prevent re-execution of completed or failed jobs
- 2026-09-11-manual-blob-sync-trigger/design.md
- ADDED Requirements
- C4 Container View — Tenant Self-Service Data Sources
- 2026-06-08-tenant-admin-user-mgmt/tasks.md
- 2026-06-11-sm-04-training-pipeline/tasks.md
- Requirement: Log training run to MLflow Tracking
- 2026-06-12-mlflow-integration/tasks.md
- Requirement: RequireAuth Route Guard
- 2026-06-17-fix-batch-extraction-worker/tasks.md
- 2026-06-17-fix-extraction-run-persistence/tasks.md
- Requirement: Batch extraction
- Requirement: Authenticated Route Group Layout
- Requirement: Environment Variable Documentation
- 2026-06-18-dockerize-backend-services/tasks.md
- ADDED Requirements
- 2026-06-18-enforce-env-secrets/tasks.md
- Requirement: OPTIONS requests bypass authentication middleware
- Requirement: Role Navigation Matrix
- 2026-06-24-analytics-and-reporting/tasks.md
- Requirement: Hero Variant B (system_admin dark mesh)
- 2026-06-25-sp-09-entity-types/tasks.md
- Requirement: Dashboard Summary Endpoint
- Requirement: Load annotated dataset
- 2026-07-08-fix-tenant-schema-drift-and-training-worker-config/tasks.md
- 2026-07-08-review-imported-annotations/tasks.md
- Requirement: Stable Inter-Service Communication via Docker DNS
- Requirement: Model warmup on promotion
- 2026-07-14-model-registry-promote/proposal.md
- Design: Remove Settings Placeholder Copy
- 2026-07-24-chunk-metadata-ingest/design.md
- Requirement: pgvector semantic search
- 2026-07-24-chunk-metadata-ingest/tasks.md
- 2026-07-24-retrieval-foundation/design.md
- 2026-07-24-retrieval-foundation/tasks.md
- 2026-07-27-document-purpose-scoping/design.md
- Requirement: Retriever interface
- Proposal: Fix Dark Theme Issues Across Portal Pages
- 2026-07-27-hybrid-retrieval-hnsw/design.md
- 2026-07-27-hybrid-retrieval-hnsw/tasks.md
- 2026-07-29-annotation-completion-workflow/tasks.md
- 2026-09-08-annotator-dashboard-ux-refinements/tasks.md
- Requirement: List documents eligible for batch extraction
- 2026-09-08-batch-extraction-document-selection/tasks.md
- 2026-09-08-cap-1-add-doc-docx-upload-support/tasks.md
- Requirement: Rename conversation from sidebar
- Requirement: Message thread display
- 2026-09-08-chat-response-token-streaming/tasks.md
- 2026-09-08-context-assembly-pipeline/design.md
- 2026-09-08-cross-encoder-rerank/design.md
- 2026-09-08-dockerize-portal-and-fix-build-hygiene/tasks.md
- 2026-09-08-document-content-hash-and-batch-select-all/tasks.md
- Requirement: The batch extraction request carries a processing mode
- ADDED Requirements
- 2026-09-08-merge-bio-entity-display/proposal.md
- Requirement: Single-Command Local Stack Startup
- Requirement: Structured entity value columns are queryable through the SQL path
- 2026-09-08-subject-column-type-convergence/tasks.md
- Task 9.1 — full suite run
- Requirement: Document provenance and retention metadata
- Requirement: Query extracted entities
- Infrastructure
- _spec
- Requirement: Only platform default adapters are executable in this change
- 2026-09-10-cap-6-local-compose-delivery-migration-and-operational-evidence/design.md
- TestMentionExtraction
- 041_azure_blob_sync_ledger.py
- 2026-06-17-add-login-dashboard-transition/tasks.md
- 2026-06-17-fix-worker-host-routing/tasks.md
- Requirement: Get active model version
- 2026-06-18-default-base-model/tasks.md
- Requirement: System Admin Tenant User Listing
- Requirement: Page enter animation keyframe
- Requirement: Hide submit job action for non-tenant-admin roles
- 2026-07-01-annotation-file-upload/tasks.md
- 2026-07-02-batch-extraction-run-history/tasks.md
- Requirement: Submit form span preflight is informational only
- Requirement: Convert trained model to ONNX format
- Requirement: Prevent re-execution of completed or failed jobs
- 2026-07-09-fix-mlflow-model-logging/tasks.md
- Requirement: Get active model version
- Requirement: Save model artifacts
- Changes
- Tasks: Remove Settings Placeholder Copy
- Requirement: Guardrail — query complexity limits
- 2026-09-08-app-shell-ui-cleanup/tasks.md
- Requirement: Reranked document context
- Requirement: Conversation-scoped binding for follow-up turns
- Requirement: No Hardcoded Secrets in Codebase
- 2026-09-08-redesign-business-user-dashboard/tasks.md
- 2026-09-08-tenant-dashboard-workspace-refresh/tasks.md
- Requirement: pgvector semantic search
- Requirement: Rename conversation endpoint
- Requirement: Document visibility by ingesting actor
- Requirement: List extraction runs
- Requirement: Annotation Action Bar
- Requirement: Span Inspector
- Bugs: Tenant Self-Service Data Sources
- TestBuildCandidates
- Requirement: Tenant-Scoped User Management
- 2026-06-11-training-approval-gate/tasks.md
- 2026-06-15-promote-warmup-integration/tasks.md
- Requirement: Extraction worker deployment
- 2026-06-18-fix-users-tenant-resolution/tasks.md
- 2026-06-19-fix-cors-preflight-middleware/tasks.md
- 2026-06-19-sidebar-action-menu/tasks.md
- Requirement: Configurable chat API service URL
- Requirement: Authenticated API calls from chat page
- 2026-06-23-tenant-from-jwt-in-chat-api/tasks.md
- Requirement: Tenant Detail View
- 2026-06-24-sp-06/tasks.md
- 2026-06-25-fix-entity-types-api-alignment/tasks.md
- 2026-07-07-fix-analytics-query-feedback/tasks.md
- Verification: Model Registry Promote
- Requirement: Seed script idempotent for promoted model
- Proposal: Remove Settings Placeholder Copy
- 2026-09-08-audit-log-tenant-filter/tasks.md
- Requirement: Entities are routed to definitions by entity-type literal, case-insensitively
- Requirement: Candidate presentation with minimal distinguishing metadata
- Requirement: Deterministic mention extraction and matching
- Requirement: Feature flag and flag-off equivalence
- Requirement: Natural-language selection interpretation
- Requirement: Retrieval is constrained to the resolved document
- Requirement: Zero, one, and many resolution outcomes
- Requirement: Per-request authorization context isolation
- 2026-09-08-merge-bio-entity-display/tasks.md
- Requirement: Tenant Detail View
- Tasks 8.2 and 8.3 — architectural scope review
- Tasks 9.3 and 9.4 — hallucination risk register and ADR compliance
- 2026-09-10-cap-2-tenant-scoped-connection-control-plane/tasks.md
- Requirement: Azure Blob sync submits through the common ingestion boundary
- Requirement: Retrieval excludes superseded and confirmed-missing source documents
- 2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/tasks.md
- ADR-NNN. <Decision title>
- Requirement: <!-- requirement name -->
- Requirement: Automatic conversation title generation
- Requirement: Candidate document filtering of semantic retrieval
- Requirement: Conversation CRUD
- Requirement: Structured entity value columns are queryable through the SQL path
- Requirement: Document Metadata API
- Requirement: Document Viewer and Token Rendering
- Requirement: Entity Type Palette and Armed Mode
- Requirement: Layout and Navigation
- Requirement: Pre-labeling and Suggestion Flow
- Requirement: Task Status Lifecycle
- Requirement: Token-Click Span Creation
- Requirement: Settings Page Placeholder
- openspec/specs/worker-network-config/spec.md
- 2026-09-11-redesign-azure-blob-connection-ui/design.md
- _sanitize_error
- TestTelemetry
- 040_tenant_data_source_connections.py
- 2026-06-08-env-config-setup/tasks.md
- ADDED Requirements
- 2026-06-22-fix-promote-inprogress-transition/tasks.md
- 2026-06-25-sp-04-dashboard/tasks.md
- 2026-06-29-remove-submit-training-job-button/tasks.md
- 2026-07-02-fix-prelabel-keyword-search/tasks.md
- 2026-07-06-fix-analytics-materialized-views/tasks.md
- 2026-07-08-remove-training-span-gate/tasks.md
- MODIFIED Requirements
- Requirement: A literal claimed by two active definitions routes to exactly one
- Requirement: Every extracted document gets a subject row
- Requirement: Re-extraction replaces a document's entity rows rather than appending
- Requirement: Relational rows are deleted through a shared pure statement builder
- Requirement: Single-valued selection is deterministic
- Requirement: The projected column value is determined by the definition's value kind
- Requirement: The projection is written inside the existing per-document extraction transaction
- Requirement: Ambiguity pauses the turn and requests clarification
- Requirement: Pending clarification state is persisted per conversation
- 2026-09-08-fix-batch-runs-scroll-layout/tasks.md
- ADDED Requirements
- templates/tasks.md
- Requirement: Reranked document context
- Requirement: Structured retrieval returns candidate document IDs
- Requirement: Callers Construct URLs Without {tid}
- Requirement: Get extraction run status
- Requirement: Real-time extraction
- Requirement: Annotation Toolbar
- Requirement: Focus Mode Entity Palette
- Requirement: Per-request tool availability
- Verification Plan
- 2026-06-17-add-celery-extraction-worker/tasks.md
- 2026-06-17-fix-worker-text-shadowing/tasks.md
- 2026-06-23-fix-chat-api-docker-url/tasks.md
- 2026-06-23-fix-chat-page-auth/tasks.md
- 2026-07-16-fix-model-serving-tenant-query/tasks.md
- 2026-07-17-fix-seed-promoted-model-conflict/tasks.md
- Requirement: A missing generated relation fails the document
- Requirement: Generated identifiers are validated and unassigned definitions are skipped
- Requirement: Generated statements are schema-qualified by the caller
- Requirement: Provenance fields are not projected
- Requirement: The projection consumes the in-memory entity list and never re-reads the EAV store
- Requirement: Original intent is replayed after selection
- Requirement: Resolution outcome is observable
- Requirement: Post-processing confidence filtering
- Requirement: Span Deselection
- 2026-06-25-align-dashboard-to-mockup/README.md
- task-1.3-baseline-diff.md
- Verification Plan
- replace_version_entries
- ADDED Requirements
- local-compose-data-source-delivery Specification
- external_pg_contract_skeleton.py
- Tenant Data Sources — Local Delivery Runbook (dev only)
- _build_windows
- QA Report -- tenant-self-service-data-sources-20260909-2
- test_data_plane_status_endpoint.py
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path/proposal.md
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/proposal.md
- Verification Plan
- Verification Plan
- 2026-09-10-cap-5-tenant-data-source-administration-portal/proposal.md
- 2026-09-10-cap-6-local-compose-delivery-migration-and-operational-evidence/proposal.md
- TestModelQualityIsNotMirrored
- Requirement: Manual Blob sync trigger action
- ToolContext
- to_sql_identifier
- external-postgresql-chat-sql-generation/tasks.md
- 2026-09-10-cap-5-tenant-data-source-administration-portal/tasks.md
- Verification Plan
- export.py
- conversation_entity_state.py
- analytics_proxy.py
- Deployment: tenant-self-service-data-sources-20260909-2 — dev
- 2026-09-11-manual-blob-sync-trigger/proposal.md
- Security -- tenant-self-service-data-sources-20260909-2
- TestBaseModelPathIsCalibrated
- 042_external_pg_contracts.py
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/tasks.md
- 2026-09-10-cap-4-contract-governed-external-postgresql-query-path/tasks.md
- Tasks — cap-6-local-compose-delivery-migration-and-operational-evidence
- Requirement: Common durable Blob ingestion
- Accessibility -- tenant-self-service-data-sources-20260909-2
- summary.md
- Load -- tenant-self-service-data-sources-20260909-2
- 2026-09-11-redesign-azure-blob-connection-ui/proposal.md
- softmax
- external-postgresql-chat-sql-generation/proposal.md
- dependencies
- Integration -- tenant-self-service-data-sources-20260909-2
- Performance -- tenant-self-service-data-sources-20260909-2
- Regression -- tenant-self-service-data-sources-20260909-2
- Smoke -- tenant-self-service-data-sources-20260909-2
- Unit -- tenant-self-service-data-sources-20260909-2
- ADDED Requirements
- k6-smoke-avg.js
- Requirement: Manual sync-now control
- extract_entities
- imported-documents/page.tsx
- 2026-09-11-redesign-azure-blob-connection-ui/tasks.md
- ADR-015. External Chat Replies Persist; External Rows Do Not
- ADR-016. Contract-Grounded External SQL Generation
- 2026-09-11-manual-blob-sync-trigger/tasks.md
- TestModeDoesNotAffectSkipLogic
- conftest.py
- test_tenant_document_registry.py
- entities.py
- DatabasePoolCollector
- test_tenant_data_plane_record.py
- test_tenant_provisioning_data_plane.py
- widget_keys.py
- test_relational_projection_generator.py
- Tenant
- Tenant-Owned PostgreSQL Data Plane — Customer Prerequisites Runbook
- tenant-postgresql-data-plane/proposal.md
- Requirement: Tenant provisioning clones the template atomically
- build_relational_delete_statements
- select_single_value
- training_service/api/v1/schemas.py
- TestBackfillSemanticValues
- test_data_plane_route_gate.py
- test_data_plane_connection_replacement.py
- test_data_plane_health.py
- test_upload_precheck.py
- 043_tenant_data_plane.py
- Requirement: Tenant Creation
- test_tenant_engine_construction_boundary.py
- reconcile_entity_tables_sync
- Requirement: System Admin chooses and observes the tenant data plane
- infer
- Alembic migrations

## God Nodes (most connected - your core abstractions)
1. `app()` - 123 edges
2. `create_access_token()` - 120 edges
3. `FakeSession` - 110 edges
4. `vitest` - 108 edges
5. `FakeLLM` - 98 edges
6. `@testing-library/react` - 96 edges
7. `authFetch()` - 96 edges
8. `session_factory()` - 91 edges
9. `RetrievalResult` - 90 edges
10. `make_generator()` - 85 edges

## Surprising Connections (you probably didn't know these)
- `Logo — dark theme SVG` --semantically_similar_to--> `Design: Fix Dark Theme Issues Across Portal Pages`  [INFERRED] [semantically similar]
  logo/logo-dark-theme.svg → src/openspec/changes/fix-dark-theme-issues/design.md
- `Telemetry Scan CI Workflow` --semantically_similar_to--> `OpenSpec Verify Change Skill`  [INFERRED] [semantically similar]
  .github/workflows/telemetry-scan.yml → .claude/skills/openspec-verify-change/SKILL.md
- `Iris Run: add-doc-docx-upload-support` --semantically_similar_to--> `spec-driven Workflow Schema`  [INFERRED] [semantically similar]
  .iris/runs/add-doc-docx-upload-support-20260903/RUN-STATE.md → .codex/skills/openspec-apply-change/SKILL.md
- `test_row_61_adapters_receive_values_never_a_reference_or_a_resolver()` --uses--> `TenantSecretContext`  [INFERRED]
  tests/test_tenant_integration_profile.py → src/shared/integration_profile/secrets.py
- `OpenCode OpsX Bulk Archive Command` --references--> `OpenSpec Sync Specs Skill (Claude)`  [AMBIGUOUS]
  .opencode/commands/opsx-bulk-archive.md → .claude/skills/openspec-sync-specs/SKILL.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **CAP-2 (control plane) underpins the parallel CAP-3 (Blob sync) and CAP-4 (external PostgreSQL query) waves** — docs_decomposition_02_cap2_connection_control_plane, docs_decomposition_02_cap3_azure_blob_sync, docs_decomposition_02_cap4_external_postgresql_query [EXTRACTED 0.90]
- **The three tenant data-source mockup screens implement one Clean-design-system administration flow** — docs_design_mockup_data_sources, docs_design_mockup_connection_detail, docs_design_mockup_schema_contracts [EXTRACTED 0.90]
- **Local observability stack: OTel collector fans out to Tempo/Prometheus/Loki, surfaced in Grafana** — docker_compose_otel_collector_service, deploy_observability_otel_collector_config_otel_collector, deploy_observability_tempo_tempo_config, deploy_observability_prometheus_prometheus_scrape_config, deploy_observability_grafana_datasources_datasources_grafana_datasources [EXTRACTED 0.95]
- **c4-diagram skill and its reference files form a phased DSL-generation workflow** — opencode_skills_c4_diagram_skill, opencode_skills_c4_diagram_references_cloud_platforms, opencode_skills_c4_diagram_references_pattern_annotations, opencode_skills_c4_diagram_references_dsl_example, opencode_skills_c4_diagram_references_sprite_mappings [EXTRACTED 1.00]
- **DOC/DOCX upload feature QA release-gate package: code quality, summary decision, and unit-test evidence** — qa_add_doc_docx_upload_support_code_quality_review, qa_add_doc_docx_upload_support_summary_report, qa_add_doc_docx_upload_support_unit_tests [EXTRACTED 1.00]
- **Entity-quality fixture, cases, and eval report form one evaluation pipeline** — tests_fixtures_entity_quality_readme, tests_fixtures_entity_quality_report, tests_fixtures_entity_quality_readme_fixture_jsonl [EXTRACTED 1.00]
- **OpenSpec Change Lifecycle** — _agents_skills_openspec_new_change_skill_openspec_new_change, _agents_skills_openspec_continue_change_skill_openspec_continue_change, _agents_skills_openspec_apply_change_skill_openspec_apply_change, _agents_skills_openspec_archive_change_skill_openspec_archive_change, _agents_skills_openspec_onboard_skill_openspec_onboard [EXTRACTED 1.00]
- **Retrieval eval README, golden set, and report form one evaluation pipeline** — tests_fixtures_retrieval_eval_readme, tests_fixtures_retrieval_eval_report, tests_fixtures_retrieval_eval_readme_golden_set_jsonl [EXTRACTED 1.00]
- **BA / Architect / Dev reviewer skills participate in the shared Reviewer Council workflow** — opencode_skills_ba_reviewer_skill, opencode_skills_architect_reviewer_skill, opencode_skills_dev_reviewer_skill, concept_reviewer_council [EXTRACTED 1.00]
- **Spec-Driven Artifact Set** — _agents_skills_openspec_continue_change_skill_proposal_artifact, _agents_skills_openspec_continue_change_skill_specs_artifact, _agents_skills_openspec_continue_change_skill_design_artifact, _agents_skills_openspec_continue_change_skill_tasks_artifact [EXTRACTED 1.00]
- **Document-ingestion-source-boundary, external-data-source-architecture, and tenant-pluggable-data-architecture share one naming/decision reconciliation** — docs_architecture_document_ingestion_source_boundary, docs_architecture_external_data_source_architecture, docs_architecture_tenant_pluggable_data_architecture [EXTRACTED 1.00]
- **Dark-theme tasks and themed logo assets together form the portal's dark-mode support surface** — src_openspec_changes_fix_dark_theme_issues_tasks, src_portal_public_logo_dark_theme, src_portal_public_logo_light_theme [INFERRED 0.55]
- **OpenSpec Archive-and-Sync Pattern Implemented Across Codex and OpenCode** — codex_skills_openspec_archive_change_skill_doc, opencode_commands_opsx_archive_doc, claude_skills_openspec_sync_specs_skill_doc [INFERRED 0.75]
- **Requirements lineage for the platform: PRD draft refined into approved requirements, later extended by the AKS deployment requirement baseline** — docs_tenant_custom_ner_prd_opencode_openspec_docx_document, docs_requirements_document, docs_requirement_deploy_platform_kubernetes_azure_document [INFERRED 0.75]
- **OpenSpec Change Artifact Pipeline (Proposal to Design to Specs to Tasks)** — concept_artifact_proposal, concept_artifact_design, concept_artifact_specs, concept_artifact_tasks [INFERRED 0.80]
- **Core OpenSpec change lifecycle (new -> apply -> archive)** — opencode_skills_openspec_new_change_skill, opencode_skills_openspec_apply_change_skill, opencode_skills_openspec_archive_change_skill [INFERRED 0.80]
- **External tenant data boundary chain: base tenant isolation extended to Azure connections and contract-governed external SQL chat** — docs_adr_001_tenant_data_isolation_tenant_data_isolation, docs_adr_011_tenant_scoped_azure_connection_control_plane_azure_connection_control_plane, docs_adr_013_contract_governed_external_postgresql_chat_contract_governed_external_sql [INFERRED 0.85]
- **Iris Run Pipeline Dispatch Chain (pipeline-guard, ralph, qa-governor)** — iris_runs_add_doc_docx_upload_support_20260903_run_state_doc, concept_pipeline_guard, concept_ralph_agent, concept_qa_governor [INFERRED 0.85]
- **Migrated OPSX Command Family** — _agents_skills_source_command_opsx_apply_skill_opsx_apply, _agents_skills_source_command_opsx_archive_skill_opsx_archive, _agents_skills_source_command_opsx_bulk_archive_skill_opsx_bulk_archive, _agents_skills_source_command_opsx_continue_skill_opsx_continue, _agents_skills_source_command_opsx_explore_skill_opsx_explore, _agents_skills_source_command_opsx_ff_skill_opsx_ff, _agents_skills_source_command_opsx_new_skill_opsx_new, _agents_skills_source_command_opsx_ask_skill_opsx_ask [INFERRED 0.85]
- **opsx-new/opsx-continue/opsx-ff/opsx-propose jointly implement the OpenSpec artifact creation workflow** — opencode_commands_opsx_new, opencode_commands_opsx_continue, opencode_commands_opsx_ff, opencode_commands_opsx_propose [INFERRED 0.85]
- **openspec status --json Shared Data Contract** — claude_commands_opsx_apply, claude_commands_opsx_archive, claude_commands_opsx_continue, claude_commands_opsx_new, claude_commands_opsx_update [INFERRED 0.85]
- **OPSX Core Change Lifecycle (new to continue/ff to apply to archive)** — claude_commands_opsx_new, claude_commands_opsx_continue, claude_commands_opsx_apply, claude_commands_opsx_archive [INFERRED 0.85]
- **Migrated Source Command Skills Group** — agents_skills_source_command_opsx_onboard_skill, agents_skills_source_command_opsx_propose_skill, agents_skills_source_command_opsx_sync_skill, agents_skills_source_command_opsx_verify_skill [INFERRED 0.85]
- **Top-level project governance documentation set (AGENTS.md, PROJECT.md, README.md)** — agents, project, readme [INFERRED 0.85]
- **Reviewer council quality-gate pipeline (qa-reviewer, review-synthesizer, spec-generator)** — opencode_skills_qa_reviewer_skill, opencode_skills_review_synthesizer_skill, opencode_skills_spec_generator_skill [INFERRED 0.85]
- **Local observability release-gate: telemetry scan procedure validated against clean and failing captures plus the workload-instrumentation test suite** — docs_local_dev_telemetry_scan, docs_observability_evidence_scan_clean_run_pass, docs_observability_evidence_workload_instrumentation_tests_run [INFERRED 0.85]
- **Training job governance evolution: ADR-006 base pipeline refined by ADR-009 (who sets hyperparams) and ADR-010 (readiness measurement)** — docs_adr_006_training_infrastructure_celery_gpu_workers, docs_adr_009_system_admin_sets_training_hyperparameters_admin_set_hyperparams, docs_adr_010_per_entity_type_dataset_threshold_per_entity_readiness [INFERRED 0.85]

## Communities (1392 total, 38 thin omitted)

### Community 0 - "FakeSession"
Cohesion: 0.02
Nodes (115): Raised when every attempt failed. Deliberately an exception rather than a…, SQLGenerationFailed, Answers a natural-language question against extracted structured entity data.…, StructuredRetrievalTool, A statement that outruns the 10s bound is cancelled, the transaction is rolled…, verification.md rows 6, 7, 13 — the execution path either runs a validated…, definition_row(), FakeLLM (+107 more)

### Community 1 - "integration_profile/service.py"
Cohesion: 0.04
Nodes (83): The declared set of adapter selections, and which of them are executable. A…, Names of the slots whose recorded selection is not executable in this change., unsupported_selections(), declared_secret_fields(), InvalidSecretReference, ProfileValidationError, Exception, Typed, allowlisted profile configuration. A value is rejected because it fails… (+75 more)

### Community 2 - "authFetch"
Cohesion: 0.03
Nodes (90): @tanstack/react-query, JobsPage(), TrainingJob, DataPlaneMode, NewTenantPage(), mockAuthFetch, mockPush, Tenant (+82 more)

### Community 3 - "AnnotationPage.tsx"
Cohesion: 0.03
Nodes (84): AnnotationActionBar(), AnnotationActionBarProps, SAVE_LABELS, SaveState, task, AnnotationPage(), mockAuthFetch, MY_TASK (+76 more)

### Community 4 - "extraction.ts"
Cohesion: 0.03
Nodes (65): BaseModelConfirmDialog(), BaseModelConfirmDialogProps, BatchDocumentSelectModal(), BatchDocumentSelectModalProps, EXTRACTED_DOC, FRESH_DOC, MIXED_DOCS, mockUseEligibleDocuments (+57 more)

### Community 5 - "entity_eval/runner.py"
Cohesion: 0.04
Nodes (50): ExpectedEntity, FixtureCase, FixtureError, load_fixture(), _parse_case(), Exception, Path, The labelled entity-quality fixture and its loader. Every case is drawn from a… (+42 more)

### Community 6 - "test_annotation_import.py"
Cohesion: 0.05
Nodes (71): compute_entity_type_counts(), generate_uuid(), get_known_entity_types_lower(), get_session(), get_tenant_id(), import_annotations(), parse_conll(), parse_jsonl() (+63 more)

### Community 7 - "ocr_worker.py"
Cohesion: 0.05
Nodes (78): needs_tesseract, classify_processing_error(), ContentUnresolvable, _embed_chunks(), extract_text_doc(), extract_text_image(), extract_text_pdf(), extract_text_pdf_as_image() (+70 more)

### Community 8 - "DocumentIngestionService"
Cohesion: 0.07
Nodes (73): AST, requires_real_stores, Where this document came from, in the source's own terms. Timestamps are never…, SourceReference, InProcessDispatcher, ProcessingDispatcher, Protocol, Post-ingestion processing dispatch. The payload is document identity and tenant… (+65 more)

### Community 9 - "provision_tenant_data_plane"
Cohesion: 0.05
Nodes (63): ModuleType, provision_tenant_data_plane(), Provisions `tenant_id`'s own store: `vector` extension, schema, baseline +…, _set_outcome(), apply(), Connection, Apply the tenant-store baseline and pending revisions to one store (Design D5,…, True when `schema` exists, holds at least one table, and has no… (+55 more)

### Community 10 - "SQLGenerator"
Cohesion: 0.04
Nodes (77): accepted_columns(), accepted_relations(), _error_class(), _fix_document_name_reference(), _force_nulls_last_on_desc(), _is_identifier_token(), iter_table_references(), _langsmith_extra() (+69 more)

### Community 11 - "_spec"
Cohesion: 0.15
Nodes (11): _child_rows(), verification.md rows 10-12, verification.md row 13, verification.md rows 14, 15, 24, 33, 34, verification.md rows 35, 36, 37, 38, _spec(), _statements(), TestCollisionResolution (+3 more)

### Community 12 - "entity_views.py"
Cohesion: 0.03
Nodes (102): _checked_identifier(), build_projection_statements(), _checked_table(), _child_insert(), _child_params(), project_document_entities(), Projects a document's final entity list into the tenant's generated relational…, The value a `subject` column receives, decided by the definition's… (+94 more)

### Community 13 - "RetrievalResult"
Cohesion: 0.05
Nodes (51): Any, resolve_rerank_candidate_count(), resolve_reranker_enabled(), resolve_top_k(), RetrievalResult, CrossEncoderReranker, _metrics(), Protocol (+43 more)

### Community 14 - "FakeSession"
Cohesion: 0.05
Nodes (44): Closed set of per-attempt outcomes. `EMPTY_WITH_DEFECT` is the *only* way a…, SQLAttemptOutcome, FakeLLM, _FakeResult, FakeSession, _generator(), `sql_attempt` records the shape of the query, never the query. Verification row…, A rejected statement has to be visible even when INFO is turned off. (+36 more)

### Community 15 - "chat.py"
Cohesion: 0.04
Nodes (58): field_validator, chat(), chat_stream(), _check_tenant_and_rate_limit(), create_conversation(), delete_conversation(), get_conversation(), list_conversations() (+50 more)

### Community 16 - "test_context_assembly_path_equivalence.py"
Cohesion: 0.23
Nodes (8): _make_chunk(), Stands in for RAGOrchestrator's two DB-touching helpers. `prompt_assembly`…, Covers scenario 13: task 6.5. Both execution paths delegate to ContextAssembler…, verification.md rows 71, 72, 73. `source_assembly` used to slice chunks at a…, _state(), _StubOrchestrator, test_graph_path_matches_direct_assembler_call(), TestCitationsDeriveFromAdmittedEvidence

### Community 17 - "shared/auth.py"
Cohesion: 0.04
Nodes (76): add_bearer_security(), app_error_handler(), health(), lifespan(), exception_handler, FastAPI, get, Request (+68 more)

### Community 18 - "data-sources.ts"
Cohesion: 0.03
Nodes (113): react-dom, DataSourceDetailPage(), DetailContent(), mockAuthFetch, UPDATABLE, ContractsContent(), handlePublish(), handleUpload() (+105 more)

### Community 19 - "domain_metrics.py"
Cohesion: 0.03
Nodes (107): main(), Regenerate `docs/observability/metric-contract.md` from the live declarations.…, render_family(), _defect_class(), The defect's category, without its payload. `SQLAttempt.defect` carries the…, delete_relational_entities(), Clear the document's relational rows on the caller's connection. Resolves which…, _accumulate_entity_counts() (+99 more)

### Community 20 - "_reconcile"
Cohesion: 0.10
Nodes (19): _column_types(), verification.md rows 1-8, 11, 12. A `value_kind` edit changes the catalog; `ADD…, Row 2 — the direction that fixes the observed `PHONE_NUMBER` misconfiguration., Rows 1, 2 over the date type., Row 3 — PostgreSQL provides no cast in either direction between these two,…, Row 4 — `'unknown'` would abort any casting conversion, and with it the admin's…, Row 8 — the values go, the rows stay. `'5 years'` is not `5.0`, and no cast…, Row 7 — `document_entities` is the system of record and keeps every value,… (+11 more)

### Community 21 - "support.js"
Cohesion: 0.07
Nodes (61): boot(), collectProps(), compileAttr(), compileTemplate(), createComponentFactory(), getDC(), Dispatcher(), createExternalModules() (+53 more)

### Community 22 - "vitest"
Cohesion: 0.03
Nodes (90): @testing-library/react, vitest, SettingsPage(), AnnotationImportResult(), AnnotationImportResultProps, baseDoc, BASE_MODEL_ID, BASE_MODEL_NAME (+82 more)

### Community 23 - "build_role_statements"
Cohesion: 0.05
Nodes (45): _async_dsn(), main(), Provision the least-privilege role that generated chat SQL executes under, then…, build_role_statements(), InvalidIdentifierError, _list_active_tenants(), list_tenant_schemas(), provision_role() (+37 more)

### Community 24 - "DenseRetriever"
Cohesion: 0.07
Nodes (45): _fake_vector(), FakeEmbeddingService, main(), Manual playground for HybridRetriever/SparseRetriever/DenseRetriever — no…, Returns a fixed query vector — swap for the real EmbeddingService if you have…, run_query(), setup(), DenseRetriever (+37 more)

### Community 25 - "NotFoundError"
Cohesion: 0.03
Nodes (63): DeclarativeBase, create_tenant(), create_tenant_user(), CreateTenantRequest, deactivate_tenant(), get_tenant(), list_audit_log(), list_tenant_users() (+55 more)

### Community 26 - "@testing-library/user-event"
Cohesion: 0.05
Nodes (34): @testing-library/user-event, AuditEventRow(), AuditPage(), formatTimestamp(), KIND_COLORS, mockEvents, mockRefetch, mockTenants (+26 more)

### Community 27 - "RetrievalConfig"
Cohesion: 0.05
Nodes (72): ContextFactory, KeyError, _create_schema(), main(), CLI entry point for the retrieval eval harness. Seeds the committed synthetic…, Per-instance/per-call override for retrieval behaviour settings. Any field left…, RetrievalConfig, EmbeddingModelMismatchError (+64 more)

### Community 28 - "context-usage.ts"
Cohesion: 0.05
Nodes (60): applyTokenTelemetry(), buildCategory(), buildContextSummary(), capitalize(), CategoryEntry, CategoryEntrySource, CategorySummary, collectMessageTexts() (+52 more)

### Community 29 - "test_chat_api_streaming.py"
Cohesion: 0.07
Nodes (38): _app(), auth_header(), CannedStreamOrchestrator, _fake_citation(), _iter_sse_events_live(), _make_orchestrator(), NoopGuardrails, _patch_orchestrator() (+30 more)

### Community 30 - "ContentStore"
Cohesion: 0.05
Nodes (45): requires_minio, retry, ContentStore, Protocol, StorageReference, The application-owned boundary for a document's bytes. Three operations and…, Store bytes and return the reference by which they can be reopened. `filename`…, Return the bytes at a previously returned reference, or None if they are gone. (+37 more)

### Community 31 - "TestStructuredValueSQLExecution"
Cohesion: 0.39
Nodes (3): asyncio, Covers verification.md rows 19, 22-25 — deterministic filtering over real rows., TestStructuredValueSQLExecution

### Community 32 - "build_chat_graph"
Cohesion: 0.06
Nodes (28): _DummyOrchestrator, main(), Generates a Mermaid diagram for the chat graph's single, fixed topology using…, build_nodes() only closes over this; node bodies never run here., build_chat_graph(), Compiles the chat graph topology. With `entity_resolution_enabled` off (the…, _route_after_guardrail(), CountingLLMClient (+20 more)

### Community 33 - "EntityDefinitionSpec"
Cohesion: 0.09
Nodes (18): EntityDefinitionSpec, The subset of `public.entity_definitions` the generated layer needs, as plain…, Rows 11, 14, 15 — ADR-008. On a base-model tenant `entity_type` holds CoNLL…, TestBaseModelGrounding, _count(), _define(), Deleting a document clears its rows from every generated relational table. The…, verification.md rows 89, 90, 91, 92 (+10 more)

### Community 34 - "RAGOrchestrator"
Cohesion: 0.04
Nodes (46): Queue, skip, Citation, Source, EmbeddingService, ExternalAnswer, The generator's outcome for one question. `reason` is `None` on success; every…, Only `generation_node` calls this. An entity-resolution clarification reply… (+38 more)

### Community 35 - "_spec"
Cohesion: 0.06
Nodes (26): build_entity_table_statements(), build_subject_table_statements(), entity_type_literals(), generated_table_names(), Every stored `entity_type` value that means this definition, uppercased and…, The `subject` table, then one `ADD COLUMN IF NOT EXISTS` per active `single`…, The full, idempotent table script for one tenant schema. Returned rather than…, The tenant's query surface: `subject` plus every active `multi` definition's… (+18 more)

### Community 36 - "shared/config.py"
Cohesion: 0.02
Nodes (143): Formatter, Handler, LogRecord, Sync tenant_{id} schemas with tenant_template. Clones missing tables and adds…, _Token, Ensure the ner_mlflow database exists before the MLflow tracking server starts.…, current_context(), get_tenant_id() (+135 more)

### Community 37 - "eval/runner.py"
Cohesion: 0.09
Nodes (40): Judgment, aggregate(), AggregateMetrics, compute_query_metrics(), _grade_map(), Judgment, mrr_at_k(), ndcg_at_k() (+32 more)

### Community 38 - "blob_sync/__init__.py"
Cohesion: 0.08
Nodes (28): AzureBlobLiveProvider, SDK-backed Azure Blob provider (CAP-3, ADR-012). Replaces…, One tenant connection's live Azure Blob container, via the SDK., Durable Azure Blob synchronization runtime (CAP-3, ADR-012). One tenant-bound…, BlobListingFailed, BlobObject, BlobObjectMissing, BlobProvider (+20 more)

### Community 39 - "_validate_on_surface"
Cohesion: 0.05
Nodes (23): _names(), The whitelist check used to resolve only the first identifier after each…, `public.documents` is not `documents` — the qualifier is grounds for rejection,…, A legitimate comma join must keep working — the fix is a security fix, not a…, verification.md rows 22-25 — the accepted relation set is the resolved surface., Row 24 — the shape the prompt teaches: a child table joined to `subject`., Row 22 — a relation the resolver does not report is not readable., Row 25 — the surface is per-tenant; `e_skill` elsewhere means nothing here. (+15 more)

### Community 40 - "gateway/main.py"
Cohesion: 0.05
Nodes (71): AsyncEngine, add_bearer_security(), health(), health_live(), lifespan(), FastAPI, get, add_bearer_security() (+63 more)

### Community 41 - "test_chunk_metadata_ingest.py"
Cohesion: 0.09
Nodes (21): _store_chunks(), chunk_text(), Chunk, BaseModel, _fake_vector(), FakeEmbeddingService, asyncio, fixture (+13 more)

### Community 42 - "chat_proxy.py"
Cohesion: 0.24
Nodes (21): _proxy(), proxy_chat(), proxy_chat_stream(), proxy_create_conversation(), proxy_create_widget_key(), proxy_delete_conversation(), proxy_get_conversation(), proxy_list_conversations() (+13 more)

### Community 43 - "_predict"
Cohesion: 0.07
Nodes (20): _FakeResponse, _predict(), The extraction worker writes EAV and relational rows in one transaction, or…, verification.md rows 1, 14, 15, 22, 81, verification.md rows 13, 24, verification.md rows 25, 26, 27, 83, verification.md rows 2, 31, verification.md rows 79, 80, 84 (+12 more)

### Community 44 - "schema_for_tenant"
Cohesion: 0.27
Nodes (14): create_extraction_run(), find_existing_run(), get_already_extracted(), get_extraction_run(), insert_entity(), list_extraction_runs(), list_processed_document_ids(), AsyncSession (+6 more)

### Community 45 - "external_postgres/__init__.py"
Cohesion: 0.06
Nodes (47): external_chat_answer(), ExternalNotExecutable, Exception, External PostgreSQL chat capability (CAP-4, ADR-013). A separate selection from…, Answer one external chat turn: resolve, then drift-gated execution. Returns…, No executable external capability for this tenant; finite reason only., _build_system_prompt(), Contract-grounded external SQL generation (ADR-016). Turns a natural-language… (+39 more)

### Community 46 - "documents.py"
Cohesion: 0.04
Nodes (77): delete_document(), get_document(), get_document_text(), get_tenant_id(), list_documents(), _platform_session(), AsyncSession, delete (+69 more)

### Community 47 - "test_document_ingestion.py"
Cohesion: 0.10
Nodes (44): extract_text_docx(), Extract paragraph text from a DOCX document., auth_header(), cleanup_public(), client(), _create_tables_sql(), _ensure_profile_table(), _ensure_public_tenants() (+36 more)

### Community 48 - "test_inference_endpoint.py"
Cohesion: 0.12
Nodes (12): auth_header(), asyncio, Regression guard: _infer_with_onnx() used to unconditionally send…, Covers verification.md row 51: base-model predictions must be an ordered, non-…, Regression guard: inference_service._resolve_active_version() used to hardcode…, TestInferenceAuth, TestInferenceBaseModelFallback, TestInferenceCustomLabelList (+4 more)

### Community 49 - "GuardrailService"
Cohesion: 0.05
Nodes (32): GuardrailService, _Classifier, _decisions(), _fail_open(), Exception, Guardrail decisions are counted by rule, and a fail-open is not an admission.…, Row 8 — the assertion this file exists for., `str(e)` on a provider error can quote the request back. Only the class name is… (+24 more)

### Community 50 - "mlflow_registry.py"
Cohesion: 0.10
Nodes (29): _cache_model_version(), demote_model_version(), get_active_model(), _get_client(), _get_sync_engine(), list_model_versions(), _lookup_run_number(), _metrics_with_label_list() (+21 more)

### Community 51 - "_get"
Cohesion: 0.08
Nodes (15): auth_header(), _clear_entity_definitions(), _get(), asyncio, fixture, parametrize, public.entity_definitions survives the per-test tenant-schema teardown, so…, demo-tenant's shape: real spans, no configured entity definitions. A… (+7 more)

### Community 52 - "gateway/api/v1/dashboard.py"
Cohesion: 0.09
Nodes (54): _activity_tag_colour(), ActivityRow, _all_active_tenant_ids(), _annotator_continue_work(), _annotator_data(), _annotator_side_panel(), _annotator_task_activity(), _annotator_type_counts() (+46 more)

### Community 53 - "insert_document_entities"
Cohesion: 0.12
Nodes (20): insert_document_entities(), Writes reconstructed entities, with the provenance that says where each value…, _entity(), asyncio, fixture, Covers verification.md rows 56-63. `document_entities` could not previously…, Row 57 — a NULL means unchanged, not unknown., Rows 59-62 at the storage boundary. (+12 more)

### Community 54 - "test_azure_blob_source_sync.py"
Cohesion: 0.09
Nodes (70): acquire_lease(), confirm_missing(), ensure_sync_tables(), get_source(), hidden_document_ids(), hide_document(), last_successful_run_at(), ledger_identities() (+62 more)

### Community 55 - "build_default_registry"
Cohesion: 0.06
Nodes (68): orchestrate_retrieval(), Top-level entry point: plans, executes, and degrades to a fallback plan (both…, build_default_registry(), _budget(), _context_factory(), _make_chunk(), Exception, Covers verification.md row 6. (+60 more)

### Community 56 - "session_factory"
Cohesion: 0.11
Nodes (46): Record a profile. Validation is by declared schema, never by value inspection.…, write_profile(), session_factory(), platform_tenant(), fixture, Verification for the tenant-integration-profile ADDED requirement (ADR-017,…, Scenario: Platform blob retention is rejected for a residency tenant., A `platform` tenant is unaffected by the new restriction. (+38 more)

### Community 57 - "require-auth.tsx"
Cohesion: 0.09
Nodes (23): lucide-react, AppShell(), AppShellProps, Sidebar(), SidebarProps, mockLogout, mockPush, userInitials() (+15 more)

### Community 58 - "MODIFIED Requirements"
Cohesion: 0.04
Nodes (48): ADDED Requirements, MODIFIED Requirements, REMOVED Requirements, Requirement: Annotation Task Queue, Requirement: Annotation Toolbar, Requirement: Document Viewer and Token Rendering, Requirement: Entity Type Palette and Armed Mode, Requirement: Focus Mode Entity Palette (+40 more)

### Community 59 - "verify"
Cohesion: 0.18
Nodes (10): _declared_public_tables(), _declared_tenant_template_tables(), main(), Verify the live database's schema matches what the Alembic migration chain…, Table name -> declared column names, for every ORM model mapped to…, Union of every table any migration creates in tenant_template. Every migration…, Returns a list of human-readable drift descriptions. Empty means clean., verify() (+2 more)

### Community 60 - "react"
Cohesion: 0.03
Nodes (62): react, react-markdown, remark-gfm, ChatPage(), Conversation, Message, Source, mockFetch (+54 more)

### Community 61 - "app"
Cohesion: 0.06
Nodes (31): app(), fixture, auth_header(), asyncio, TestAnalyticsExportEndpoint, auth_header(), TestAnalyticsQueryEndpoint, auth_header() (+23 more)

### Community 62 - "ExternalSQLGenerator"
Cohesion: 0.12
Nodes (16): AsyncAzureOpenAI, build_client(), find_name_span(), main(), process_record(), One-off script: identifies the resume owner's own name span in each…, ExternalSQLGenerator, _metrics() (+8 more)

### Community 63 - "is_valid_entity"
Cohesion: 0.11
Nodes (17): filter_valid_entities(), is_valid_entity(), Whether an entity is a fact worth storing. `NOT NULL` does not catch an empty…, Partitions entities into those worth persisting and a count of those dropped.…, _short_value_types(), _entity(), parametrize, Covers verification.md rows 20-23. `document_entities.normalized_value` is `NOT… (+9 more)

### Community 64 - "Requirement: Retriever interface"
Cohesion: 0.04
Nodes (48): Purpose, Requirement: Centralized retrieval configuration, Requirement: Citation enrichment executes without error, Requirement: Reranker interface, Requirement: Reranking configuration, Requirement: Reranking retriever composition, Requirement: Retrieval excludes superseded and confirmed-missing source documents, Requirement: Retriever interface (+40 more)

### Community 65 - "RetrievalStatus"
Cohesion: 0.08
Nodes (19): Renders the turn's retrieval outcome for the answer model, or None when every…, render_retrieval_status(), CapabilityStatus, What one plan entry actually did. `error` holds the specific failure text,…, The turn's retrieval outcome, as one value with named consumers. Replaces…, The strongest signal any invocation of this capability produced, ordered failed…, RetrievalStatus, A turn that never reached retrieval passes no status; behaviour is unchanged. (+11 more)

### Community 66 - "data_plane.py"
Cohesion: 0.08
Nodes (28): _Cache, _cas_status(), DataPlaneRecord, _default_platform_record(), get_data_plane_record(), get_data_plane_record_sync(), invalidate(), mark_paused() (+20 more)

### Community 67 - "tracked_tenants"
Cohesion: 0.08
Nodes (44): active_connection(), enqueued(), fixture, parametrize, Verification for the manual Azure Blob sync trigger. Maps to…, Record broker enqueues instead of sending them., test_broker_unavailable_returns_safe_code(), test_connection_reports_latest_completed_sync_run() (+36 more)

### Community 68 - "NormalizedEntity"
Cohesion: 0.09
Nodes (45): NormalizedEntity, apply_decisions(), build_candidates(), _build_client(), build_window(), call_postprocessor(), Candidate, _comparable() (+37 more)

### Community 69 - "canonicalize"
Cohesion: 0.06
Nodes (23): canonicalize(), fold_text(), _is_adjacent(), Removes Unicode format characters (general category `Cf`) and folds typographic…, Deterministic fallback (format-character removal, typographic folding, NFKC,…, Whether `current` continues the entity `prev` belongs to. Model serving filters…, The entity's surface text. When the caller supplies the full ordered token…, Splits a `B-TYPE`/`I-TYPE` label into (prefix, type). Labels with no recognized… (+15 more)

### Community 70 - "Requirement: Deactivation and orphaning never drop a generated relation"
Cohesion: 0.04
Nodes (45): ADDED Requirements, MODIFIED Requirements, REMOVED Requirements, RENAMED Requirements, Requirement: Deactivation and orphaning never drop a generated relation, Requirement: Each active multi-valued entity gets a child table, Requirement: Each tenant gets a subject table with one column per single-valued entity, Requirement: Entity type matching is case-insensitive and covers base-model labels (+37 more)

### Community 71 - "DocumentTable.tsx"
Cohesion: 0.10
Nodes (21): DocumentsPage(), DocumentRow(), DocumentRowProps, formatDate(), purposeLabel(), statusToVariant, DocumentTable(), DocumentTableProps (+13 more)

### Community 72 - "test_retrieval_tools_integration.py"
Cohesion: 0.13
Nodes (20): _create_chunks_table(), _create_second_schema(), _fake_vector(), FakeEmbeddingService, _insert_chunk(), _insert_document(), fixture, Covers verification.md row 28: multi-document scope, results restricted to the… (+12 more)

### Community 73 - "_get"
Cohesion: 0.09
Nodes (12): DashboardSummaryResponse, _get(), asyncio, TestDashboardSummaryShape, TestRouteDispatch, TestSystemAdminActivityFeed, TestSystemAdminPlatformHealthEndpoint, TestSystemAdminResponseShape (+4 more)

### Community 74 - "test_entity_definition_reconcile.py"
Cohesion: 0.08
Nodes (24): _column_type(), _columns(), _persisted_value_kind(), fixture, All four entity-definition write paths reconcile the tenant's generated schema,…, verification.md rows 64, 114, verification.md row 115, verification.md rows 65, 67, 68, 116 (+16 more)

### Community 75 - "test_external_postgresql_chat.py"
Cohesion: 0.14
Nodes (29): is_external_request_executable(), Whether one named connection may serve this tenant's external request., clamp_limit(), execute_external_query(), Enforce the server row cap: keep a smaller LIMIT, else append one., Run one drift-gated, validated, parameterized external SELECT. Returns…, _record(), FixtureExternalDatabase (+21 more)

### Community 76 - "_entity"
Cohesion: 0.13
Nodes (18): EntityTypeConfig, _entity(), fixture, Covers verification.md rows 42-47 — the permitted-transformation contract.…, Row 43 — merging is bounded exactly as BIO continuation is., Rows 44 and 45 — the largest thing only this stage can fix, bounded to the…, Row 46 — an unverifiable number in an indexed numeric column is exactly what…, Punctuation, whitespace and casing are handled deterministically, so the prompt… (+10 more)

### Community 77 - "test_llm_usage_metrics.py"
Cohesion: 0.09
Nodes (15): _calls(), _latency_observations(), LLM calls report tokens, latency and an outcome — and never the provider's…, Row 5's second clause., Cost is derived from configured rates, not from a table in source., Found on the running stack, not in a test. Three of the four LLM operations —…, Attribution degrades to `unknown` rather than dropping the observation — a lost…, Row 5's first clause. (+7 more)

### Community 78 - "test_annotation_workspace.py"
Cohesion: 0.16
Nodes (39): auth_header(), cleanup_public(), client(), _create_tables_sql(), make_token(), asyncio, fixture, pending' is written by the tenant seed path but was missing from the transition… (+31 more)

### Community 79 - "check_regression"
Cohesion: 0.08
Nodes (25): eval_gate, BaselineNotFoundError, check_regression(), _comparability_failure(), GateResult, load_baseline(), MetricDelta, Exception (+17 more)

### Community 80 - "test_telemetry_scan.py"
Cohesion: 0.05
Nodes (19): _load_scan(), parametrize, The release-gate scan's four behaviours, re-runnable outside the pipeline.…, Not 'greater than zero': one log line and one span would pass that, and a flow…, Ordering is the whole point: a content check that runs first and finds nothing…, Row 40 — this change adds most of its new surface there, and the foundation's…, An attribute key nobody expected is exactly the one a leak arrives on, so the…, `--dry-run` is what CI can run without a stack, so it must exercise the real… (+11 more)

### Community 81 - "test_extraction_worker_postprocess_failopen.py"
Cohesion: 0.08
Nodes (18): dict, _entity(), _FakeHeaders, _FakeHttpResponse, _FakeResponse, asyncio, fixture, Covers verification.md rows 48-52. Post-processing is an optional enhancement… (+10 more)

### Community 82 - "stage_span"
Cohesion: 0.06
Nodes (26): current_trace_id(), BaseException, Span helpers for the workload instrumentation. Auto-instrumentation gives one…, The ambient trace id as a 32-character hex string, or None outside a trace., A span for one stage, yielding a setter for attributes decided inside the…, Attribute setter that is a no-op when there is no live span., The exception's *class*, not its message. A driver message quotes the offending…, _Setter (+18 more)

### Community 83 - "ContextAssembler"
Cohesion: 0.04
Nodes (59): AdmittedEvidence, _bounded(), build_system_prompt(), collapse_duplicate_rows(), ContextAssembler, _count_tokens(), _dedupe_chunks(), _fit_external_rows() (+51 more)

### Community 84 - "test_conversation_history_reaches_retrieval.py"
Cohesion: 0.11
Nodes (16): _metrics(), One classifier call. Returns True (in-domain) on any error, so a provider…, Returns True if the query is in-domain. Fails open (treats the query as in-…, The domain-metric recorders, resolved on first use. `domain_metrics` imports…, Deterministic short-circuits that decline without an LLM call: a reference to…, Single definition of how much prior conversation each LLM call sees, and how it…, The trailing window of history, oldest first. Empty list when there is none., The same window rendered as `role: content` lines, for the prompts that… (+8 more)

### Community 85 - "test_training_jobs_api.py"
Cohesion: 0.17
Nodes (36): auth_header(), client(), _create_tables_sql(), engine(), fake_celery_send_task(), make_token(), asyncio, fixture (+28 more)

### Community 86 - "test_chat_stage_spans.py"
Cohesion: 0.11
Nodes (17): _node_outcome(), What this node decided, as a category — never what it decided *about*. Every…, nodes(), _orchestrator(), fixture, One chat question produces one span per stage it executed. Verification row 1.…, A declined question never reaches generation, and the absence of the span is…, A node added later without widening the enumeration lands on `other`, which is… (+9 more)

### Community 87 - "NER Platform KT Handover Guide"
Cohesion: 0.07
Nodes (35): MLflow Tracking Server K8s Service, Grafana Datasources Provisioning (Prometheus/Loki/Tempo), OpenTelemetry Collector Config, Prometheus Scrape Config, Tempo Local Tracing Backend Config, docker-compose celery_worker service (training), docker-compose chat_api service, docker-compose mlflow service (+27 more)

### Community 88 - "Entity-Quality Evaluation Fixture README"
Cohesion: 0.08
Nodes (33): _embed(), main(), One-off generator for…, Entity-Quality Evaluation Fixture README, correct_extraction failure class, date_value failure class, Development tenant d2eb33ab-68f1-4e67-a841-f040f7eaf233, duplicate_mentions failure class (+25 more)

### Community 89 - "test_chat_api_structured_scope.py"
Cohesion: 0.09
Nodes (18): apply_document_scope(), document_scope_columns(), `relation -> the column a document scope constrains`, static tables plus the…, Constrains every scoped table reference in an already-validated statement to a…, Structural document-scope enforcement for structured retrieval —…, A derived table needs a name; using the table's own keeps every qualified…, An aggregate projects no document_id, so a post-execution row filter could…, verification.md row 40 — the predicate is inside the source, so the row limit… (+10 more)

### Community 90 - "_entity"
Cohesion: 0.15
Nodes (10): `sql_identifier -> entities routed to it`, skipping every unroutable entity. An…, route_entities(), _entity(), parametrize, verification.md rows 19-21, verification.md row 4 — the builders touch no database., verification.md rows 6-9, TestPurity (+2 more)

### Community 91 - "_create"
Cohesion: 0.08
Nodes (16): _create(), AsyncClient, fixture, parametrize, `cardinality` and `sql_identifier` reachable end to end through the entity-type…, verification.md rows 106, 107, 108, 109, verification.md rows 110, 111, 112, verification.md row 113 (+8 more)

### Community 92 - "test_model_registry.py"
Cohesion: 0.21
Nodes (34): auth_header(), client(), _create_tables_sql(), engine(), make_token(), mock_mlflow(), asyncio, fixture (+26 more)

### Community 93 - "OpenSpec CLI"
Cohesion: 0.16
Nodes (34): Caveman (README Overview), Auto-Clarity Rule, Caveman (SKILL Instructions), Caveman Intensity Levels (lite/full/ultra/wenyan), Brainstorm-Then-Decompose Principle, Feature Decomposer Skill, OpenSpec Apply Change Skill, OpenSpec CLI (+26 more)

### Community 94 - "test_external_sql_generator.py"
Cohesion: 0.18
Nodes (23): CountingFixtureExternalDatabase, executable_tenant(), FakeLLM, _make_connection(), make_generator(), _patch_live_database(), _patch_live_database_unreachable(), _publish() (+15 more)

### Community 95 - "AnalyticsQueryRequest"
Cohesion: 0.17
Nodes (14): analytics_export(), analytics_query(), analytics_refresh(), AsyncSession, post, Request, AnalyticsExportRequest, AnalyticsQueryRequest (+6 more)

### Community 96 - "extraction.py"
Cohesion: 0.20
Nodes (19): BatchExtractRequest, BatchExtractResponse, BatchRunListItem, BatchRunListResponse, BatchRunStatus, EligibleDocument, EligibleDocumentListResponse, EntityQueryParams (+11 more)

### Community 97 - "normalize_value"
Cohesion: 0.05
Nodes (26): normalize_value(), Pure, deterministic dispatch by declared value kind. No network, database, or…, parametrize, Covers verification.md rows 24-28. `_read_number` tried `_digits_to_number`…, Row 28 — the fallback must not start inventing numbers., The fallback anchors at the start of the phrase, so a trailing identifier…, Row 24 — the exact stored value from `Resume RENJIEAPEN.pdf`., Row 26 — what the reconstruction fix now hands the parser. (+18 more)

### Community 98 - "nodes.py"
Cohesion: 0.04
Nodes (90): setter, _route_after_entity_resolution(), build_nodes(), Log, span and time one graph node. The span lives here rather than in a second…, Returns a new RetrievalPlan with every `semantic_retrieval` entry's `scope`…, Returns a dict of node-name -> async callable, each closing over the given…, _rewrite_plan_for_resolution(), _traced() (+82 more)

### Community 99 - "test_telemetry_failure_isolation.py"
Cohesion: 0.15
Nodes (9): _get(), A telemetry outage must not become a platform outage. Verification rows 21 and…, The config-only rollback. If telemetry ever causes a production problem,…, The counterpart: a passing test above means nothing if export never happens., One request could pass before the exporter's first failed connection. A run of…, Risk-register item 5 — the property that makes the above true, asserted…, TestExportIsDisabledByAnEmptyEndpoint, TestRequestsSurviveAnUnreachableCollector (+1 more)

### Community 100 - "training_jobs.py"
Cohesion: 0.14
Nodes (31): _all_active_tenant_ids(), approve_training_job(), cancel_training_job(), _compute_run_name(), create_training_job(), get_platform_session(), get_session(), get_tenant_id() (+23 more)

### Community 101 - "test_celery_queue_metrics.py"
Cohesion: 0.09
Nodes (17): _depth(), _duration_count(), _failures(), Queue depth, wait time and execution duration are three different measurements.…, Design Decision 7 — a negative wait is clamped and counted, so skew becomes…, Design Decision 7's mechanism — a field on a hook that already exists., The header is additive: a task enqueued by a producer that predates it must…, Occupancy is only true at the instant it is read — the same rule the foundation… (+9 more)

### Community 102 - "_entity"
Cohesion: 0.10
Nodes (13): _entity(), fixture, Covers verification.md rows 29-33. Post-processing every entity was measured…, Row 31 — the type declares a number and the parser produced none., Row 32 — the `two` / `half years` shape, if reconstruction ever leaves one., A raw logit of 5.63 is not on the `[0, 1]` scale the threshold is expressed in;…, stable_settings(), TestCandidatesAreBatchedPerDocument (+5 more)

### Community 103 - "test_document_content_hash.py"
Cohesion: 0.11
Nodes (19): auth_header(), client(), engine(), _fake_store(), _FakeContentStore, make_token(), _provision_tenant(), asyncio (+11 more)

### Community 104 - "test_inference_windowing.py"
Cohesion: 0.09
Nodes (19): Resolves (window_budget, overlap) in WordPiece units, clamped so that…, _window_geometry(), _fake_session(), _FakeInput, label_list(), patched_serving(), _positions_of_word(), fixture (+11 more)

### Community 105 - "_get_sync_engine"
Cohesion: 0.05
Nodes (35): _extract_label_set(), fine_tune_model(), _get_sync_engine(), _load_annotated_dataset(), _make_service_token(), MLflowCallback, Exception, task (+27 more)

### Community 106 - "_entity"
Cohesion: 0.16
Nodes (13): _entity(), fixture, Covers verification.md rows 34-38. "Invalid LLM output must never be written…, Row 35 — and never the extraction., _respond(), stable_settings(), TestAcceptedValuesGoThroughDeterministicNormalization, TestInvalidItemDoesNotInvalidateSiblings (+5 more)

### Community 107 - "_insert_entity"
Cohesion: 0.15
Nodes (8): _insert_entity(), Covers verification.md rows 22, 23, 26-31., Covers verification.md row 23: two tenant schemas share a normalized value;…, verification.md row 41. Resolution used to stop at the first mention that…, verification.md row 43 — the single-subject path behaves exactly as before., verification.md row 45 — the cap applies to the union, and an over-cap turn is…, Ambiguity is still a property of ONE mention matching several people — two…, TestResolveEntityOutcomes

### Community 108 - "test_inference_confidence_calibration.py"
Cohesion: 0.17
Nodes (12): _fake_session(), _FakeInput, _install_session(), label_list(), patched_serving(), fixture, Guards the calibration fix: `_infer_window()` used to report `np.max(logits)`…, The exact regression: a max logit of 5.0 used to be reported verbatim. (+4 more)

### Community 109 - "analytics_service/api/v1/schemas.py"
Cohesion: 0.18
Nodes (19): analytics_dashboard(), fetch_widget_data(), AsyncSession, get, Request, AnalyticsFilter, AnalyticsQueryResponse, ConfidenceBucket (+11 more)

### Community 110 - "annotation_service/main.py"
Cohesion: 0.10
Nodes (37): _compute_bio_tags(), create_span(), delete_span(), generate_uuid(), get_session(), get_tenant_id(), list_spans(), prelabel_document() (+29 more)

### Community 111 - "entity_resolver.py"
Cohesion: 0.04
Nodes (51): _accept_matching_mentions(), _build_candidates(), _depossessive(), _extract_mentions(), interpret_selection(), _lookup_candidate_rows(), _mention_matches(), _MentionMatch (+43 more)

### Community 112 - "inference_service.py"
Cohesion: 0.13
Nodes (26): WarmupRequest, post, Request, warmup_endpoint(), _get_base_pipeline(), _get_tokenizer(), infer(), _infer_window() (+18 more)

### Community 113 - "AppError"
Cohesion: 0.04
Nodes (74): Response, app_error_handler(), exception_handler, Request, app_error_handler(), exception_handler, Request, app_error_handler() (+66 more)

### Community 114 - "auth_header"
Cohesion: 0.16
Nodes (10): auth_header(), asyncio, TestCorrectEntity, TestCorrectEntityAnnotator, TestQueryEntitiesAnnotator200, TestQueryEntitiesByConfidence, TestQueryEntitiesByDocument, TestQueryEntitiesByType (+2 more)

### Community 115 - "test_entity_views_reconciler.py"
Cohesion: 0.20
Nodes (12): _drop_schema(), _insert_child_row(), _make_schema(), fixture, Integration tests for the entity table reconciler against a real tenant schema.…, The extraction worker's connection idiom, so the sync executor is exercised as…, verification.md rows 65, 68 — the never-drop rule against a live server., _row_count() (+4 more)

### Community 116 - "configured"
Cohesion: 0.11
Nodes (18): configured(), fixture, parametrize, Every process logs, at the configured level, with the context keys always…, Deriving it from the message would make the client IP the event name — a…, The reason this matters: an access line is the one record that quotes a caller-…, Row 3 — `NER_LOG_LEVEL` governs what is emitted., Row 5 — present, and null, when no request is active. (+10 more)

### Community 117 - "test_mlflow_verification.py"
Cohesion: 0.10
Nodes (16): cleanup(), _complete_run(), _create_run(), db_schema(), experiment_name(), mlflow_client(), fixture, Comprehensive end-to-end verification of the MLflow integration. Preconditions:… (+8 more)

### Community 118 - "analytics/page.tsx"
Cohesion: 0.10
Nodes (18): mockDashboardData, mockQueryErrorObj, mockQueryResponse, mockRefetchQuery, AnalyticsPage(), ResultsTableProps, useAnalyticsQuery(), useDashboardWidgets() (+10 more)

### Community 119 - "Requirement: Get training job status"
Cohesion: 0.04
Nodes (45): Purpose, Requirement: Approve training job, Requirement: Cancel training job, Requirement: Get training job status, Requirement: Hide submit job action for non-tenant-admin roles, Requirement: List training jobs, Requirement: Reject training job, Requirement: Submit form span preflight is informational only (+37 more)

### Community 120 - "telemetry_scan.py"
Cohesion: 0.13
Nodes (22): _attribute_value(), Backends, capture_logs(), capture_metric_labels(), capture_spans(), check_capture_floor(), drive_seeded_flow(), Finding (+14 more)

### Community 121 - "test_no_pii_in_logs.py"
Cohesion: 0.17
Nodes (10): captured_records(), _emit_extraction_path_records(), fixture, Extracted personal data never reaches a log record. Verification row 14, and…, A cheap catch-all for the leak class that matters most, independent of which…, The counterpart. A scan that passes because nothing was logged at all would be…, Capture everything the extraction path logs, through the real handler., Drive the log calls the extraction path makes for one document. Called with the… (+2 more)

### Community 122 - "Requirement: Batch Runs Tab — Batch Extraction Management"
Cohesion: 0.04
Nodes (44): Purpose, Requirement: Batch Document-Selection Modal — Bulk Selection, Requirement: Batch Runs Tab — Batch Extraction Management, Requirement: Entity Review Tab — Entity Listing and Review, Requirement: Extraction Page Layout and Tab Navigation, Requirement: Playground Tab — Real-time Extraction, Requirements, Scenario: Already-extracted documents are disabled in the modal (+36 more)

### Community 123 - "_entity"
Cohesion: 0.15
Nodes (12): _entity(), fixture, Covers verification.md rows 39-41 — the invention boundary. The distinction…, Row 41 — a correction differing only by a curly quote is still supported., The window is deliberately bounded; text outside it is not evidence., _respond(), stable_settings(), TestEvidenceWindowConstruction (+4 more)

### Community 124 - "test_migration_037_entity_view_metadata.py"
Cohesion: 0.13
Nodes (16): _columns(), _insert_definition(), migrated(), fixture, parametrize, Migration 037: view-layer metadata on public.entity_definitions. Follows the…, verification.md row 34, verification.md rows 35-36 (+8 more)

### Community 125 - "collapse_duplicates"
Cohesion: 0.15
Nodes (12): collapse_duplicates(), Collapses repeated mentions of the same fact within one document into a single…, _entity(), asyncio, Covers verification.md rows 64-67. 364 rows on the development tenant held only…, Row 67 — the key is per document, so two documents naming the same skill keep…, They canonicalize to the same value, which is what the key uses., Row 65 — citations point at this row, so its offsets must be real text. (+4 more)

### Community 126 - "ModelCache"
Cohesion: 0.10
Nodes (7): CachedModel, ModelCache, cache(), fixture, TestCacheHitOnSubsequentRequest, TestLoadModelOnFirstRequest, TestLRUEvictionOnMemoryPressure

### Community 127 - "TestSQLPrompt"
Cohesion: 0.20
Nodes (6): verification.md row 1 and Risk 7 — the prompt teaches the relational surface,…, Row 1 — no instruction to select from `document_entities`, and no `entity_type`…, Row 5.5 — the graph's scope filter and citation assembly both need it., Task 5.3 — the guidance that was never EAV-specific stays., Task 5.4 — document metadata questions still work; the EAV store is not offered., TestSQLPrompt

### Community 128 - "test_extraction_metrics.py"
Cohesion: 0.10
Nodes (13): _entities_total(), _failures(), _jobs(), _pages_sum(), An extraction run reports its shape; a failed one reports where it stopped.…, Read off the source rather than executed, because driving a real run needs…, The failure counter is labelled by exception class and the stage is not on it,…, Design Decision 12 and verification row 41, asserted here as well as in the… (+5 more)

### Community 129 - "OpenSpec CLI"
Cohesion: 0.24
Nodes (25): source-command-opsx-onboard Skill, source-command-opsx-propose Skill, source-command-opsx-sync Skill, source-command-opsx-verify Skill, AskUserQuestion Tool, OPSX: Apply Command, OPSX: Archive Command, OPSX: Ask Command (VSCode Ask Agent) (+17 more)

### Community 130 - "ADDED Requirements"
Cohesion: 0.05
Nodes (43): ADDED Requirements, Requirement: A tenant whose relational surface is unpopulated reports the source as unavailable, Requirement: Base-model tenants resolve to the same relational surface, Requirement: Document-scoped questions stay document-scoped on the relational surface, Requirement: Invalid relational SQL is rejected before execution, Requirement: One resolver supplies the tenant's relational surface to the generator, Requirement: Relational failures are detected and corrected without entity-type patterns, Requirement: The generated relational surface is the canonical query model (+35 more)

### Community 131 - "ADDED Requirements"
Cohesion: 0.05
Nodes (42): ADDED Requirements, Portal Annotation Workspace, Purpose, Requirement: Annotation Task Queue, Requirement: Char-Offset to Token-Index Conversion, Requirement: Document Viewer and Token Rendering, Requirement: Entity Type Palette and Armed Mode, Requirement: Layout and Navigation (+34 more)

### Community 132 - "test_inference_metrics.py"
Cohesion: 0.10
Nodes (12): _duration_count(), _inferences(), _load_duration_count(), _loads(), Which model answered, how long it took, and whether the load was cold.…, Which is what lets the base model be a success. Folding them into one label…, Task 6.4. The serving-side and caller-side numbers differ by the network hop,…, A version number climbs without bound as a tenant retrains, so as a label it is… (+4 more)

### Community 133 - "test_domain_metrics_declarations.py"
Cohesion: 0.08
Nodes (13): The declarations in `domain_metrics.py` are the cardinality and disclosure…, `tenant_id` is bounded by the tenant table rather than by a written-out set,…, The number this produces is the whole point of the enumeration rule. If it…, Row 41 — design Decision 12. Entity types are tenant-configured…, Row 34 — the allowlist is permissive about what it names, not merely a denylist., Row 35 — the check must fail *and* say which family., Row 35, the standing case — this is the assertion that goes red on a new label., Row 36 — enumerated, not a pattern. (+5 more)

### Community 134 - "test_batch_extraction_eligibility.py"
Cohesion: 0.18
Nodes (16): auth_header(), eligibility_tenant_schema(), _insert_document(), _mark_extracted(), _promote_model(), asyncio, fixture, Mirrors production shape: the legacy `version` column is left NULL and the real… (+8 more)

### Community 135 - "test_entity_span_trimming.py"
Cohesion: 0.12
Nodes (14): Strips leading and trailing punctuation, returning `(trimmed, left, right)`…, trim_span(), _predict(), parametrize, Covers verification.md rows 16-19. `worker._tokenize_span` splits on `\\S+`, so…, The development tenant stored `O Konni, Pathanamthitta (Dist),` — the closing…, Row 19 — the property that makes citations resolvable., Whitespace tokenization with real offsets, matching `worker._tokenize_span`. (+6 more)

### Community 136 - "auth_header"
Cohesion: 0.15
Nodes (14): auth_header(), baseline_documents(), isolated_tenant_schemas(), asyncio, fixture, Covers scenarios 25-26: default batch extraction excludes training-purpose…, POST /extract-batch now reads `documents` to reject training-purpose ids, so…, Provisions fresh tenant_<id>.extraction_runs tables for arbitrary tenant ids… (+6 more)

### Community 137 - "TestSelectionInterpretation"
Cohesion: 0.22
Nodes (4): Exception, Covers verification.md rows 42-45., ScriptedSelectionClient, TestSelectionInterpretation

### Community 138 - "Candidate"
Cohesion: 0.05
Nodes (34): Candidate, Deterministic clarification text — no LLM call., render_clarification(), fixture, Covers verification.md row 40., Covers verification.md rows 39, 41, 46, 47, 48, 49., Covers verification.md rows 54-58 at the persistence layer., state_schema() (+26 more)

### Community 139 - "Requirement: Base Model (Version 0) Entry"
Cohesion: 0.05
Nodes (42): Purpose, Requirement: Base Model (Version 0) Entry, Requirement: Demote Model Version, Requirement: Model Detail Panel, Requirement: Model Version Card, Requirement: Model Versions API Hooks, Requirement: Model Versions List Page, Requirement: Promote Model Version (+34 more)

### Community 140 - "test_orchestrator_integration.py"
Cohesion: 0.17
Nodes (15): _create_chunks_table(), _fake_vector(), FakeEmbeddingService, _insert_chunk(), _insert_document(), fixture, Covers verification.md row 18., Covers verification.md row 19. (+7 more)

### Community 141 - "_prompt_for"
Cohesion: 0.11
Nodes (13): _prompt_for(), PromptCapturingLLM, Forcing extra columns into a GROUP BY would split the groups and break every…, The regression the first version of this directive caused. Asked for candidates…, Ordering is the fix: the evidence requirement has to be read first, since the…, Naming the concrete failure, not just the rule — the model has to know what…, Captures the generation prompt and returns a fixed statement., The identity that survives filename collisions, and the only column the graph's… (+5 more)

### Community 142 - "test_sysadmin_user_onboarding.py"
Cohesion: 0.36
Nodes (23): auth_header(), create_tenant(), AsyncClient, asyncio, tenant_admin_token(), test_admin_create_user_duplicate_email_in_tenant_returns_409(), test_admin_create_user_inactive_tenant_returns_403(), test_admin_create_user_nonexistent_tenant_returns_404() (+15 more)

### Community 143 - "Requirement: SQL query generation and validation"
Cohesion: 0.08
Nodes (25): chat-api (delta), MODIFIED Requirements, Purpose, Requirement: SQL query generation and validation, Scenario: A child table retained from a `multi` era is excluded from the query surface, Scenario: A generated entity table is both granted and whitelisted, Scenario: A grant for a table that does not yet exist is skipped safely, Scenario: A table that leaves the query surface loses its grant (+17 more)

### Community 144 - "Decisions"
Cohesion: 0.10
Nodes (19): Context, Currently-In-Force ADRs, Decision 10: Cross-plane reads are explicit, Decision 11: Local Compose tenant store, Decision 12: Feature flag for shared environments, Decision 1: Relocate the whole tenant schema by connection routing, Decision 2: Control-plane data-plane record with an explicit status machine, Decision 3: New provider `azure_postgresql_data_plane` (+11 more)

### Community 145 - "reconstruct_entities"
Cohesion: 0.05
Nodes (39): aggregate_confidence(), merge_wordpieces(), Reconstructs complete logical entities from an ordered, WordPiece-merged…, Merges `##`-prefixed WordPiece continuation tokens into the preceding token's…, Entity-level confidence is the minimum of its constituent tokens' confidences —…, reconstruct_entities(), _pred(), `reconstruct_entities` used to continue an entity across an `I-` tag no matter… (+31 more)

### Community 146 - "Requirements"
Cohesion: 0.05
Nodes (42): Model Serving, Purpose, Requirement: Cross-encoder reranking endpoint, Requirement: Internal inference endpoint, Requirement: Model cache, Requirement: Model loader uses API-provided artifact path, Requirement: Model Registry URL is configurable and targets the correct in-network port, Requirement: Model warmup on promotion (+34 more)

### Community 147 - "create_access_token"
Cohesion: 0.21
Nodes (27): create_access_token(), fixture, system_admin_header(), tenant_admin_header(), client(), fixture, The document service's own app: `/api/v1/documents` is served there, not by…, tenant() (+19 more)

### Community 148 - "test_training_metrics.py"
Cohesion: 0.11
Nodes (12): BaseException, Map a raised exception onto the enumerated failure causes. Deliberately coarse.…, _training_failure_cause(), _duration_count(), _failures(), parametrize, Training reports its lifecycle. Model quality stays in MLflow. Verification…, ADR-009 makes the `training_jobs` row the authority on a job's state, and… (+4 more)

### Community 149 - "test_observability_wiring.py"
Cohesion: 0.11
Nodes (13): parametrize, _python_sources(), Structural guards: one logging configuration, one request-identifier generator.…, `print` is the one output path no logging control can reach. Not a style rule.…, Every one of the eight entry points makes the single wiring call., Row 2 — `logging.basicConfig` appears only under `src/shared/observability/`., The counterpart assertion — a passing test above means nothing if the shared…, Row 10 — the eight `tenant_context.py` files no longer mint identifiers. (+5 more)

### Community 150 - "Settings"
Cohesion: 0.07
Nodes (33): BaseSettings, model_validator, Inject database_ssl_mode into the default connection URLs when the URLs…, Settings, clean_ner_environment(), parametrize, Run with no `NER_` variables set, restoring them afterwards. The suite's own…, Row 30 — no plaintext secret defaults in `src/shared/config.py`. (+25 more)

### Community 151 - "model_serving/api/v1/schemas.py"
Cohesion: 0.19
Nodes (18): get_tenant_id(), inference_endpoint(), post, Request, get_tenant_id(), post, Request, rerank_endpoint() (+10 more)

### Community 152 - "_app"
Cohesion: 0.21
Nodes (13): _app(), _foundation_sample_lines(), _get(), parametrize, `/metrics` is reachable without auth, counts requests, and carries no tenant…, Row 23 — two readings either side of a served request., Row 24 — every label set, on every family this change declares, on every…, The scope above is only meaningful if the names in it match real families. A… (+5 more)

### Community 153 - "Requirement: Document Upload Zone"
Cohesion: 0.05
Nodes (41): Portal Documents, Purpose, Requirement: Auto-Polling for In-Flight Documents, Requirement: Cancel an In-Progress Batch, Requirement: Document Table, Requirement: Document Upload Zone, Requirement: Soft Delete, Requirement: Status Badge (+33 more)

### Community 154 - "Requirements"
Cohesion: 0.05
Nodes (41): Purpose, Requirement: Backfill of semantic values without re-inference, Requirement: Date normalization, Requirement: Deterministic structured queries, Requirement: Numeric and duration normalization, Requirement: Open bounds and closed ranges, Requirement: Parser registry is extensible without pipeline changes, Requirement: Semantic normalization is distinct from lexical normalization (+33 more)

### Community 155 - "Requirement: SQL query generation and validation"
Cohesion: 0.08
Nodes (25): chat-api (delta), MODIFIED Requirements, Purpose, Requirement: SQL query generation and validation, Scenario: A child table retained from a `multi` era is excluded from the query surface, Scenario: A generated entity table is both granted and whitelisted, Scenario: A grant for a table that does not yet exist is skipped safely, Scenario: A table that leaves the query surface loses its grant (+17 more)

### Community 156 - "ADDED Requirements"
Cohesion: 0.05
Nodes (40): ADDED Requirements, Requirement: Bounded agentic retrieval loop, Requirement: Evidence accumulation into existing state keys, Requirement: Feature flag and flag-off equivalence, Requirement: Iteration, tool-call, and wall-clock budgets, Requirement: Loop failure falls back to one-shot retrieval, Requirement: Loop is measured against the one-shot configuration, Requirement: Malformed tool calls get one corrective retry, then the loop degrades (+32 more)

### Community 157 - "v1/tasks.py"
Cohesion: 0.33
Nodes (11): create_task(), generate_uuid(), get_session(), get_tenant_id(), list_tasks(), AsyncSession, get, post (+3 more)

### Community 158 - "backfill_document_entities.py"
Cohesion: 0.09
Nodes (24): backfill_document(), backfill_semantic_values_for_document(), _documents_for_semantic_backfill(), _documents_needing_backfill(), _fetch_token_records(), main(), Backfill `document_entities` for documents extracted before normalized entity…, Populates typed value columns for an already-normalized document by re-parsing… (+16 more)

### Community 159 - "DefineEntityTypeSlideOver.tsx"
Cohesion: 0.05
Nodes (47): AnnotationImportPreview(), AnnotationImportPreviewProps, PreviewState, makeQC(), mockAuthFetch, mockUseEntityTypes, renderPreview(), BASE_LABELS (+39 more)

### Community 160 - "test_projection_metrics.py"
Cohesion: 0.13
Nodes (11): _duration_count(), _duration_sum(), _projections(), Projection reports how long it took and whether it wrote what it meant to.…, Task 5.3's second clause. The audit conclusion is that post-processing is not a…, Row 13's first clause., Row 13's second clause., So the rate is `drift / total` on one query rather than a join between two… (+3 more)

### Community 161 - "test_imported_annotations_update.py"
Cohesion: 0.23
Nodes (19): auth_header(), cleanup_public(), client(), _create_tables_sql(), make_token(), asyncio, fixture, Tests for imported annotations update endpoints (PATCH and mark-reviewed). (+11 more)

### Community 162 - "TestMigration036ExtractionRunsProcessingMode"
Cohesion: 0.19
Nodes (11): _columns(), asyncio, fixture, Covers verification.md rows 90-92 for migration 036., Covers verification.md rows 90-92., Row 91 — every run that already happened really was BERT-only., Row 92 — provisioning clones the template, so the template must carry them., `tenant_template.extraction_runs` is created by the shared database setup and… (+3 more)

### Community 163 - "test_warmup_endpoint.py"
Cohesion: 0.13
Nodes (13): auth_header(), asyncio, Tests for model-serving warmup endpoint., ADR-006: Model artifacts path must follow tenants/{tid}/models/v{version}/., Task 3.6: Model loads on-demand when cache is empty., Task 3.5: Warmup → cache populated, verified via subsequent lookup., TestArtifactPathConvention, TestInferOnDemandLoad (+5 more)

### Community 164 - "OpenSpec Onboard Skill"
Cohesion: 0.27
Nodes (19): OpenSpec Fast-Forward Change Skill, OpenSpec Onboard Skill, OpenSpec Propose Skill (Claude), OpenSpec Update Change Skill (Claude), OpenSpec Verify Change Skill, OpenSpec Propose Skill (Codex), OpenSpec Update Change Skill (Codex), Design Artifact (design.md) (+11 more)

### Community 165 - "semantic_normalizer.py"
Cohesion: 0.08
Nodes (36): _as_mapping(), _convert_duration(), _digits_to_number(), _extract_open_bound_phrase(), _extract_range(), _extract_source_unit(), _leading_numeral_to_number(), load_entity_definition_specs() (+28 more)

### Community 166 - "compilerOptions"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 167 - "v1/models.py"
Cohesion: 0.29
Nodes (18): _base_model_metadata(), _compute_run_name(), demote_model(), get_active_model(), get_session(), get_tenant_id(), _get_version_or_404(), list_model_versions() (+10 more)

### Community 168 - "_get"
Cohesion: 0.24
Nodes (7): _get(), A leaked contextvar would silently merge two users' work under one identifier., Rows 15 and 17 — a hash for the user, a UUID for the tenant, nothing else., Row 4 — the four fields match the values resolved for that request., _records(), TestContextMatchesTheRequest, TestIdentityIsOpaque

### Community 169 - "test_tenant_document_registry_reconcile.py"
Cohesion: 0.15
Nodes (19): Upserts one document's registry row. Called after ingestion, an OCR status…, record(), fixture, Verification for `registry.record`/`update_status` and…, Scenario #33: Status transitions reach the registry., Scenario #34: Drift is reconciled., Scenario #35: Unreachable store does not erase registry rows., Scenario #36: System admin sees counts during a tenant outage. (+11 more)

### Community 170 - "test_entity_postprocessor_tenant_scope.py"
Cohesion: 0.18
Nodes (10): _entity(), fixture, Covers verification.md rows 53-55. ADR-001 requires zero cross-tenant leakage,…, `insert_document_entities` takes its schema and document id from the caller., Tenant scope is the worker's, resolved from server-controlled context; the…, stable_settings(), TestEvidenceWindowIsBounded, TestOneDocumentPerRequest (+2 more)

### Community 171 - "external_pg_contracts.py"
Cohesion: 0.22
Nodes (17): contract_history(), _error(), _owned_pg_connection(), publish_contract(), AsyncSession, get, post, Request (+9 more)

### Community 172 - "Requirement: Tenant data engines are resolved per tenant with no platform fallback"
Cohesion: 0.11
Nodes (17): ADDED Requirements, Requirement: Every tenant has exactly one data plane recorded in the control plane, Requirement: Fleet operations enumerate tenants from the control plane, Requirement: Tenant content routes are gated on data-plane readiness, Requirement: Tenant data engines are resolved per tenant with no platform fallback, Scenario: Awaiting-store tenant administrator can configure the store, Scenario: Awaiting-store tenant cannot upload, Scenario: Data-plane record carries no sensitive values (+9 more)

### Community 173 - "auth_header"
Cohesion: 0.14
Nodes (12): auth_header(), asyncio, Covers scenario 4, Hallucination Risk 1: task 2.8., Covers scenario 5 (adjusted to 401 to match TenantContextMiddleware convention…, Covers scenario 1: task 2.5., Covers scenario 2: task 2.6., Covers scenario 3: task 2.7., TestRerankAuth (+4 more)

### Community 174 - "OpenSpec CLI"
Cohesion: 0.28
Nodes (18): OpenSpec New Change Skill, design.md artifact, proposal.md artifact, specs/<capability>/spec.md artifact, tasks.md artifact, OpenSpec CLI, Bulk archive command, OpenCode OpsX Bulk Archive Command (+10 more)

### Community 175 - "ADDED Requirements"
Cohesion: 0.05
Nodes (40): ADDED Requirements, Requirement: Each active multi-valued entity gets a child view, Requirement: Each tenant gets a subject view pivoting its single-valued entities, Requirement: Entity type matching is case-insensitive and covers base-model labels, Requirement: Tenant-supplied names are slugged into safe SQL identifiers, Requirement: The reconciler applies generated DDL idempotently per tenant schema, Requirement: The subject view is dropped and recreated, never replaced in place, Requirement: View DDL is produced by a pure function (+32 more)

### Community 176 - "TestMigration035DocumentEntitiesProvenance"
Cohesion: 0.24
Nodes (9): _columns(), asyncio, fixture, Covers verification.md rows 86-89 for migration 035. The provenance columns…, Row 87. The stored 5.63 is an uncalibrated logit — the migration must leave it…, Covers verification.md rows 86-89., _run(), sync_engine() (+1 more)

### Community 177 - "architect-reviewer skill"
Cohesion: 0.22
Nodes (17): AC Verification Policy (AGENTS.md Invariant 2), AC Verification Policy (docs/workflow/acceptance-criteria.md), Project coding standards (docs/standards/coding-standards.md), Microservice pattern-selection rules (docs/architecture/microservice-patterns.md), openspec/project.md (PROJECT.md), Reviewer Council conventions (docs/agents/reviewer-council.md), Architect Review Checklist, architect-reviewer skill (+9 more)

### Community 178 - "test_external_pg_contract_descriptions.py"
Cohesion: 0.13
Nodes (34): accepted_contract(), canonical_fingerprint(), CanonicalContract, ContractValidation, _is_safe_name(), _normalize_relations(), publish_version(), Canonical schema-contract lifecycle (CAP-4, ADR-013). A contract declares… (+26 more)

### Community 179 - "Decision"
Cohesion: 0.12
Nodes (16): 017. Tenant-Owned PostgreSQL Data Plane (Data Residency), 1. The unit of residency is the whole tenant schema, 2. A content-free document registry in the control plane, for all tenants, 3. A distinct connection provider with write privileges, 4. New tenants only; plane is fixed, 5. Provisioning and migrations run per data plane, 6. Engine routing and failure isolation, 7. Originals do not rest on the platform (+8 more)

### Community 180 - "chat_api/test_retrieval_metrics.py"
Cohesion: 0.15
Nodes (9): _bucket(), _observations(), A retrieval that finds nothing is recorded as such, not as an absence of…, Task 3.5's fourth measurement — what survived merge and the cap., The recording sits in `_invoke_entry`, which is the one point every dispatched…, TestHitRate, TestTheOrchestratorRecordsEveryDispatchedCapability, TestZeroResults (+1 more)

### Community 181 - "TestSQLValidation"
Cohesion: 0.12
Nodes (3): verification.md row 33: entity lookups match on the canonical value., verification.md row 34: extracted_entities (raw BIO tokens) must not be…, TestSQLValidation

### Community 182 - "test_document_visibility.py"
Cohesion: 0.22
Nodes (16): client(), listed_ids(), asyncio, fixture, Verification for document visibility by ingesting actor — verification.md rows…, Retrieval filters on `purpose` alone, so anything it can cite must be listable., The two queries build their WHERE clause from one list of conditions; a…, seed_document() (+8 more)

### Community 183 - "TestMigration029DocumentEntitiesTypedValues"
Cohesion: 0.26
Nodes (8): _columns(), _index_names(), asyncio, fixture, Covers verification.md rows 38-42., _run(), sync_engine(), TestMigration029DocumentEntitiesTypedValues

### Community 184 - "data_sources/service.py"
Cohesion: 0.09
Nodes (47): mark_retired(), Retirement -> `store_retired`, terminal. No DDL/DML against the tenant store —…, LifecycleRejected, Exception, A lifecycle action the connection's state, evidence, or limits forbid. Carries…, activate_connection(), _canonical_body_digest(), _emit() (+39 more)

### Community 185 - "ADDED Requirements"
Cohesion: 0.05
Nodes (39): ADDED Requirements, Requirement: Backfill of semantic values without re-inference, Requirement: Date normalization, Requirement: Deterministic structured queries, Requirement: Numeric and duration normalization, Requirement: Open bounds and closed ranges, Requirement: Parser registry is extensible without pipeline changes, Requirement: Semantic normalization is distinct from lexical normalization (+31 more)

### Community 186 - "Requirement: Versioned tenant-isolated schema contracts"
Cohesion: 0.09
Nodes (22): ADDED Requirements, MODIFIED Requirements, Requirement: Contract-authorized SQL execution, Requirement: Safe external chat outcomes, Requirement: Versioned tenant-isolated schema contracts, Scenario: Approved join and aggregation executes, Scenario: Capability resolves server-side per authenticated tenant, Scenario: Contract without descriptions remains valid (+14 more)

### Community 187 - "Requirements"
Cohesion: 0.05
Nodes (39): Purpose, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Requirement: Data Freshness, Requirement: Hero Section, Requirement: Hero Variant B (system_admin dark mesh), Requirement: Secondary Metrics Panel (+31 more)

### Community 188 - "_post_feedback"
Cohesion: 0.38
Nodes (5): auth_header(), _insert_conversation(), _insert_message(), _post_feedback(), TestFeedbackEndpoint

### Community 189 - "test_document_provenance_migration.py"
Cohesion: 0.20
Nodes (15): _columns(), migrated_database(), _migration(), asyncio, fixture, Verification for migration 038 — verification.md rows 82-87. The migration is…, Provisioning clones `tenant_template`, so inheriting is a property of the…, No unique constraint: `documents` is soft-deleted, and content-addressed reuse… (+7 more)

### Community 190 - "Requirement: Safe activation and concurrent capability limits"
Cohesion: 0.12
Nodes (16): ADDED Requirements, MODIFIED Requirements, Requirement: Data-plane connection pause and retirement drive data-plane status, Requirement: Safe activation and concurrent capability limits, Requirement: Tenant-admin-managed finite Azure connections, Scenario: Cross-tenant connection access is denied, Scenario: Data-plane test reports a missing vector extension, Scenario: Duplicate active provider is rejected (+8 more)

### Community 191 - "FakeUpstreamResponse"
Cohesion: 0.17
Nodes (9): _FakeRequest, FakeUpstreamResponse, _patch_upstream_client(), Covers verification.md rows 21, 22 (tasks 3.3, 3.4). Calls `proxy_chat_stream`…, Stands in for the `httpx.Response` returned by `client.send(req, stream=True)`…, Duck-typed stand-in for `starlette.Request` carrying only what…, TestChatStreamGatewayProxy, _executable_string_literals() (+1 more)

### Community 192 - "Document Ingestion Source Boundary (architecture proposal)"
Cohesion: 0.20
Nodes (14): Document Ingestion Source Boundary (architecture proposal), DocumentContent (re-openable byte access port), DocumentIngestionService (inbound port), DocumentSource (deferred pull-side port), OriginalDocumentStore (outbound blob-storage port), External Data Source Architecture (Keka-first sync engine), Change-detection ladder (version / timestamp / content-hash rungs), CredentialProvider indirection (credential_ref resolution) (+6 more)

### Community 193 - "types/dashboard.ts"
Cohesion: 0.05
Nodes (50): DashboardPage(), ActiveModelCard(), ActiveModelCardProps, ActivityPanel(), ActivityPanelProps, ActivityRowList(), ActivityRowListProps, ROW_ICONS (+42 more)

### Community 194 - "_get_active_model_version"
Cohesion: 0.14
Nodes (17): _get_active_model_version(), _get_cached_model_version(), Promoted version from the local `model_versions` cache. Reads `version_number`…, Active model version, resolved from the training-service registry — the same…, model_registry_tenant(), _promote(), asyncio, fixture (+9 more)

### Community 195 - "Requirements"
Cohesion: 0.05
Nodes (39): Purpose, Requirement: Dataset-to-model lineage diagram, Requirement: Design token compliance, Requirement: Detail panel defaults to the most recent job when none is selected, Requirement: Detail panel header shows the full job id and creation timestamp, Requirement: Filter tab active state is not obscured by hover styling, Requirement: Filter tabs do not overflow into adjacent content, Requirement: Horizontal status timeline (+31 more)

### Community 196 - "TestEntityConfigValueKind"
Cohesion: 0.30
Nodes (8): auth_header(), AsyncClient, asyncio, fixture, Covers verification.md rows 29-33., tenant_admin_token(), TestEntityConfigValueKind, _unique_name()

### Community 197 - "test_migration_032_chat_message_feedback.py"
Cohesion: 0.18
Nodes (7): dev_engine(), fixture, Verifies migration 032 (chat_message_feedback + chat_messages.answer_kind/…, Sanity check: existing chat_messages rows (inserted before this migration) were…, _table_columns(), TestMigration032AppliedToTenantTemplate, TestMigration032BackfilledToLiveTenantSchemas

### Community 198 - "evaluate_answer"
Cohesion: 0.18
Nodes (8): AnswerCase, AnswerCaseResult, evaluate_answer(), Answer-level evaluation — verification.md rows 85, 86, 87. Chunk-ranking…, The single most damaging failure the investigation found: a broken turn…, One answer-level case. `required_facts` are the substrings the reply must…, TestAnswerLevelHarness, The case must fail when the reply carries evidence for only one subject — the…

### Community 199 - "Requirements"
Cohesion: 0.05
Nodes (39): Purpose, Requirement: authFetch stub, Requirement: Badge component, Requirement: MiniBar component, Requirement: PlaceholderScreen component, Requirement: Primitive barrel export, Requirement: SegmentControl component, Requirement: SlideOver component (+31 more)

### Community 200 - "auth_header"
Cohesion: 0.33
Nodes (6): auth_header(), asyncio, The regression this guards: if serving ever reverts to raw logits, the values…, _stub_infer(), TestLowConfidenceEntitiesAreFiltered, TestThresholdIsMeaningfulAgainstTheReturnedScale

### Community 201 - "test_health_endpoints.py"
Cohesion: 0.37
Nodes (12): _get(), asyncio, chat_api readiness checks base model_serving reachability only — it must not…, test_chat_api_health_200_when_all_dependencies_healthy(), test_chat_api_health_503_when_database_unhealthy(), test_chat_api_health_live_returns_200_regardless_of_dependencies(), test_chat_api_health_stays_healthy_when_only_base_model_reachable(), test_document_service_health_checks_database_and_minio() (+4 more)

### Community 202 - "TestMigration026DocumentEntities"
Cohesion: 0.27
Nodes (7): _columns(), asyncio, fixture, _run_downgrade_026(), _run_upgrade_026(), sync_engine(), TestMigration026DocumentEntities

### Community 203 - "TestMigration028EntityDefinitionValueKind"
Cohesion: 0.28
Nodes (7): _columns(), asyncio, fixture, Covers verification.md rows 43-44., _run(), sync_engine(), TestMigration028EntityDefinitionValueKind

### Community 204 - "OpenSpec Store (registered standalone repo)"
Cohesion: 0.30
Nodes (12): OpenSpec Explore Skill (Claude), OpenSpec Sync Specs Skill (Claude), OpenSpec Apply Change Skill (Codex), OpenSpec Archive Change Skill (Codex), OpenSpec Explore Skill (Codex), OpenSpec Sync Specs Skill (Codex), OpenSpec Store (registered standalone repo), /opsx:explore command (+4 more)

### Community 205 - "OpenSpec Onboard Skill"
Cohesion: 0.24
Nodes (12): OpenSpec Apply Change Skill, OpenSpec Archive Change Skill, OpenSpec Bulk Archive Change Skill, OpenSpec Continue Change Skill, OpenSpec Explore Skill, OpenSpec Fast-Forward Change Skill, OpenSpec New Change Skill, OpenSpec Onboard Skill (+4 more)

### Community 206 - "Requirement: Safe connection lifecycle interface"
Cohesion: 0.12
Nodes (15): ADDED Requirements, MODIFIED Requirements, Requirement: Safe connection lifecycle interface, Requirement: Tenant users see a safe data-plane readiness state, Scenario: A failed test hides the attestation checkboxes and returns the control to a retry state, Scenario: A passed test surfaces the attestation checkboxes inline, Activate stays disabled until both are checked, Scenario: Activation is blocked safely, Scenario: Awaiting-store tenant administrator is guided to setup (+7 more)

### Community 207 - "MODIFIED Requirements"
Cohesion: 0.05
Nodes (38): ADDED Requirements, MODIFIED Requirements, REMOVED Requirements, Requirement: Annotation Task Queue, Requirement: Annotation Toolbar, Requirement: Entity Type Palette and Armed Mode, Requirement: Focus Mode Entity Palette, Requirement: Layout and Navigation (+30 more)

### Community 208 - "ADDED Requirements"
Cohesion: 0.12
Nodes (15): ADDED Requirements, Requirement: Activating a data-plane connection provisions the tenant schema in the tenant store, Requirement: Pending tenant-store revisions are applied per store on deploy, Requirement: Replacement connections must point at the same store, Requirement: Tenant-store schema is defined by a versioned baseline and ordered revisions, Scenario: Credential rotation keeps the tenant ready, Scenario: Deploy upgrades a residency store, Scenario: Missing tenant-store revision fails the build (+7 more)

### Community 209 - "ADDED Requirements"
Cohesion: 0.05
Nodes (38): ADDED Requirements, Requirement: Dataset-to-model lineage diagram, Requirement: Design token compliance, Requirement: Detail panel defaults to the most recent job when none is selected, Requirement: Detail panel header shows the full job id and creation timestamp, Requirement: Filter tab active state is not obscured by hover styling, Requirement: Filter tabs do not overflow into adjacent content, Requirement: Horizontal status timeline (+30 more)

### Community 210 - "ADDED Requirements"
Cohesion: 0.05
Nodes (38): ADDED Requirements, Requirement: Client streaming kill switch, Requirement: Gateway streams the chat stream without buffering, Requirement: Non-streaming chat endpoint is preserved, Requirement: Persistence is unchanged by streaming, Requirement: SSE event protocol, Requirement: Streaming chat endpoint, Requirement: Streaming error handling (+30 more)

### Community 211 - "TestBackfillDocumentEntities"
Cohesion: 0.23
Nodes (4): _FakeResponse, asyncio, Covers verification.md rows 20-22., TestBackfillDocumentEntities

### Community 212 - "_get_summary"
Cohesion: 0.36
Nodes (5): auth_header(), _get_summary(), Creates `total` eligible assistant answer messages; the first len(ratings) of…, _seed_feedback(), TestResponseQualityCard

### Community 213 - "test_entity_config.py"
Cohesion: 0.44
Nodes (11): auth_header(), AsyncClient, asyncio, fixture, tenant_with_token(), test_scenario_14_create_entity_type_v1(), test_scenario_15_update_increments_version(), test_scenario_16_valid_label_mapping() (+3 more)

### Community 214 - "test_extraction_api.py"
Cohesion: 0.29
Nodes (6): auth_header(), asyncio, TestExtractNoModelReturns400, TestExtractNonAdminReturns403, TestExtractTextReturnsEntities, TestLowConfidenceFiltered

### Community 215 - "test_migration_027_conversation_entity_state.py"
Cohesion: 0.26
Nodes (8): _columns(), asyncio, fixture, Covers verification.md task 1.3: migration created and reversible., _run_downgrade_027(), _run_upgrade_027(), sync_engine(), TestMigration027ConversationEntityState

### Community 216 - "TestMlflowServerLive"
Cohesion: 0.17
Nodes (7): Verify MLflow server is reachable and responds correctly., MLflow server responds to health check., Can create an MLflow experiment., Run created with params and tags., Metrics can be logged per-step., Run can be set to FAILED with error message., TestMlflowServerLive

### Community 217 - "Requirements"
Cohesion: 0.05
Nodes (38): Purpose, Requirement: Celery Queue Instrumentation, Requirement: Chat And Retrieval Path Instrumentation, Requirement: Entity Resolution Outcomes Are Recorded, Requirement: Extraction And Projection Instrumentation, Requirement: Guardrail Decisions Are Counted, Including Fail-Open, Requirement: LangSmith And OpenTelemetry Traces Are Correlated, Requirement: Model Serving Instrumentation (+30 more)

### Community 218 - "ADDED Requirements"
Cohesion: 0.05
Nodes (37): ADDED Requirements, Requirement: authFetch stub, Requirement: Badge component, Requirement: MiniBar component, Requirement: PlaceholderScreen component, Requirement: Primitive barrel export, Requirement: SegmentControl component, Requirement: SlideOver component (+29 more)

### Community 219 - "apply_to_all_tenant_schemas"
Cohesion: 0.33
Nodes (6): upgrade(), downgrade(), upgrade(), downgrade(), upgrade(), apply_to_all_tenant_schemas()

### Community 220 - "tenant-postgresql-data-plane/tasks.md"
Cohesion: 0.12
Nodes (15): 10. Provisioning task and per-store migration, 11. Failure isolation, 12. Document registry, 13. Portal, 14. Documentation, 15. Verification & Evidence, 1. Prerequisites, 2. Control-plane schema (migration 043) (+7 more)

### Community 221 - "Requirements"
Cohesion: 0.05
Nodes (37): Local Development Stack, Purpose, Requirement: Application Service Port Mapping, Requirement: Automated Database Initialization on Compose Up, Requirement: Docker Build Context Hygiene, Requirement: Postgres Data Persistence Across Compose Cycles, Requirement: Service Startup Dependencies, Requirement: Shared Root Dockerfile (+29 more)

### Community 222 - "TestTenantAdminQueries"
Cohesion: 0.31
Nodes (4): _seed_docs(), _seed_promoted_model(), _seed_training_jobs(), TestTenantAdminQueries

### Community 223 - "test_dashboard_tenant_enumeration.py"
Cohesion: 0.42
Nodes (6): auth_header(), _delete_tenant(), _get_system_admin(), _insert_tenant(), asyncio, TestDashboardTenantEnumeration

### Community 224 - "test_migration_022_guard.py"
Cohesion: 0.31
Nodes (7): _create_annotation_tasks(), _create_bare_documents(), asyncio, fixture, _run_upgrade_022(), sync_engine(), TestMigration022Guard

### Community 225 - "Requirements"
Cohesion: 0.05
Nodes (37): Purpose, Requirement: Entity definition value kind columns are added to the public schema, Requirement: Existing tenant schemas are reconciled to the current template shape, Requirement: Per-tenant-schema DDL tolerates tenant schemas missing a table, Requirement: Semantic value columns are added to the template and every existing tenant schema, Requirement: Tenant provisioning clones the template atomically, Requirement: Tenant-scoped migrations propagate to existing tenant schemas, Requirement: The `document_entities` table exists on the template and every tenant schema (+29 more)

### Community 226 - "TestSetupTestDbGuard"
Cohesion: 0.29
Nodes (4): CompletedProcess, asyncio, _run_script(), TestSetupTestDbGuard

### Community 227 - "ADDED Requirements"
Cohesion: 0.05
Nodes (36): ADDED Requirements, Requirement: Celery Queue Instrumentation, Requirement: Chat And Retrieval Path Instrumentation, Requirement: Entity Resolution Outcomes Are Recorded, Requirement: Extraction And Projection Instrumentation, Requirement: Guardrail Decisions Are Counted, Including Fail-Open, Requirement: LangSmith And OpenTelemetry Traces Are Correlated, Requirement: Model Serving Instrumentation (+28 more)

### Community 228 - "portal/package.json"
Cohesion: 0.06
Nodes (30): results, @axe-core/playwright, eslint, eslint-config-next, eslint-config-prettier, jsdom, next, @playwright/test (+22 more)

### Community 229 - "ADDED Requirements"
Cohesion: 0.06
Nodes (35): ADDED Requirements, Requirement: Attempt outcome classification, Requirement: Bounded SQL attempt loop, Requirement: Bounded tenant entity profile in the generation context, Requirement: Exhausted retries report failure rather than an empty result, Requirement: Per-attempt observability, Requirement: Previous-attempt feedback is supplied to the generator, Requirement: Tenant isolation and validation hold across every attempt (+27 more)

### Community 230 - "Requirement: Async OCR Processing"
Cohesion: 0.06
Nodes (35): ADDED Requirements, MODIFIED Requirements, Requirement: Async OCR Processing, Requirement: Document provenance and retention metadata, Requirement: Document Upload, Requirement: Document visibility by ingesting actor, Scenario: A newly provisioned tenant inherits the columns, Scenario: A system-ingested document is visible tenant-wide (+27 more)

### Community 231 - "ADDED Requirements"
Cohesion: 0.06
Nodes (34): ADDED Requirements, Requirement: Conversation CRUD, Requirement: Disclaimer in every response, Requirement: Guardrail — blocked question types, Requirement: Guardrail — query complexity limits, Requirement: Guardrail — source citation enforcement, Requirement: NER inference for chat context, Requirement: pgvector semantic search (+26 more)

### Community 232 - "TestAMalformedSchemaIsCountedAndLogged"
Cohesion: 0.13
Nodes (9): parametrize, `assert_tenant_schema` counts and logs; it never raises. Verification rows 30…, The `code_path` label is itself an enumerated value set — a free-form string…, The behavioural commitment. A raise here would be a behavioural change smuggled…, A violating value is by definition one we did not expect, so it must not be…, TestAMalformedSchemaIsCountedAndLogged, TestAWellFormedSchemaPasses, TestTheCallSitesAreDeclared (+1 more)

### Community 233 - "ADDED Requirements"
Cohesion: 0.06
Nodes (34): ADDED Requirements, Requirement: Base Model (Version 0) Entry, Requirement: Demote Model Version, Requirement: Model Detail Panel, Requirement: Model Version Card, Requirement: Model Versions API Hooks, Requirement: Model Versions List Page, Requirement: Promote Model Version (+26 more)

### Community 234 - "_run_tenant_schema_ddl"
Cohesion: 0.33
Nodes (4): asyncio, _run_tenant_schema_ddl(), TestApplyToAllTenantSchemas, TestRemediationMigration

### Community 235 - "TestTenantSchemaReconciliation"
Cohesion: 0.29
Nodes (5): asyncio, fixture, _run_upgrade_023(), sync_engine(), TestTenantSchemaReconciliation

### Community 236 - "test_data_plane_failure_isolation.py"
Cohesion: 0.17
Nodes (15): _bearer(), _make_unreachable_ready_tenant(), platform_tenant(), fixture, Verification for "An unreachable tenant store fails closed for that tenant…, Scenario #24: Other tenants are unaffected., Scenario #25: Driver error text is not exposed., Scenario #26: Upload during outage writes nothing (see also… (+7 more)

### Community 237 - "Decomposition: Tenant Self-Service Data Sources"
Cohesion: 0.47
Nodes (9): ADR-014: Local Docker Compose Deployment Topology, CAP-2 — Tenant-Scoped Connection Control Plane, CAP-3 — Durable Azure Blob Synchronization and Source Reconciliation, CAP-4 — Contract-Governed External PostgreSQL Query Path, CAP-5 — Tenant Data Source Administration Portal, CAP-6 — Local Compose Delivery, Migration, and Operational Evidence, Decomposition: Tenant Self-Service Data Sources, Deployment Plan — Tenant Self-Service Data Sources (dev-only Compose) (+1 more)

### Community 238 - "Release-gate telemetry scan (scripts/telemetry_scan.py)"
Cohesion: 0.22
Nodes (9): Release-gate telemetry scan (scripts/telemetry_scan.py), Telemetry scan clean run: PASS, no seeded value or personal-data pattern (63 logs, 124 spans, 13 metrics), Telemetry scan FAIL: capture too thin to conclude anything (0 logs, 0 spans), Telemetry scan FAIL: 3 findings, seeded entity value leaked in log records, Telemetry scan FAIL: 1 finding, seeded entity value leaked only in a span attribute, Core data model: tenant, entity_definition, document, annotation_task, training_job, model_version, extraction_run, extracted_entity, audit_log, FR-01..FR-15: tenant provisioning, entity catalog, training, model registry, extraction, chatbot, OpenSpec/OpenCode governance, PRD v0.2 FR-01..FR-13 (contains duplicate FR-11/FR-12 IDs later fixed in requirements.md) (+1 more)

### Community 239 - "Tenant Self-Service Data Sources — requirements baseline v1.2"
Cohesion: 0.20
Nodes (9): Ralph run report: CAP-2 tenant-scoped connection control plane blocked, architecture-resolver returned ESCALATE, CAP-2..CAP-6 dependency chain: CAP-3/4 blocked by CAP-2, CAP-5/6 blocked by CAP-3, Azure Blob Storage as synchronized document source, Azure Database for PostgreSQL direct read-only structured-data chat, Current-state brownfield seams: upload flow, ingestion/retention, control plane, chat, durability gap, Decision Register DEC-001..DEC-006: drift detection mechanism, connection network/identity model, legal-hold approval, Tenant Self-Service Data Sources — requirements baseline v1.2, FR-001..FR-013: tenant-admin connection lifecycle, Azure Blob sync, Azure PostgreSQL direct chat, schema-contract drift blocking (+1 more)

### Community 240 - "tokenizer-registry.d.ts"
Cohesion: 0.22
Nodes (7): SessionMessageInfoShape, SessionMessageShape, TokenizerEntry, TokenizerRegistry, TokenizerResolutionError, TokenizerSpec, TokenModel

### Community 241 - "Requirement: Safe connection lifecycle interface"
Cohesion: 0.12
Nodes (15): MODIFIED Requirements, Requirement: Data source collection and navigation, Requirement: Safe connection lifecycle interface, Scenario: A failed test hides the attestation checkboxes and returns the control to a retry state, Scenario: A passed test surfaces the attestation checkboxes inline, Activate stays disabled until both are checked, Scenario: Activation is blocked safely, Scenario: Administrator creates a connection from the modal, Scenario: Administrator dismisses the new-connection modal without creating a draft (+7 more)

### Community 242 - "ADDED Requirements"
Cohesion: 0.06
Nodes (34): ADDED Requirements, Requirement: Permitted transformations are enumerated and enforced, Requirement: Post-processing failure never destroys a successful extraction, Requirement: Post-processing is tenant-scoped and server-controlled, Requirement: Post-processing runs only on selected candidate entities, Requirement: The post-processor returns a strictly validated structured decision, Requirement: The post-processor SHALL NOT invent entities, Scenario: A failed run is never the consequence of post-processing alone (+26 more)

### Community 243 - "test_tenant_provisioning.py"
Cohesion: 0.58
Nodes (8): auth_header(), AsyncClient, asyncio, test_scenario_1_create_tenant_201(), test_scenario_2_duplicate_slug_409(), test_scenario_3_quota_exceeded_429(), test_scenario_4_paginated_list(), test_scenario_5_deactivate_tenant()

### Community 244 - "PROJECT.md — Multi-Tenant Custom NER Platform"
Cohesion: 0.29
Nodes (8): AGENTS.md Baseline Agent Instructions, MLflow Tracking Server K8s Deployment Manifest, mlflow-tracking-server Deployment (v2.20.0), Technical Design Document Skill, PROJECT.md — Multi-Tenant Custom NER Platform, PROJECT.md MLflow Tech Stack Entry (2.20+), README.md — NER Platform Service & API Reference, README MLflow Integration Section

### Community 245 - "038_document_provenance_and_retention.py"
Cohesion: 0.39
Nodes (7): _add_clauses(), downgrade(), _drop_clauses(), _for_each_tenant_schema(), add provenance, retention and ingesting-actor columns to documents Every column…, Apply one statement to every provisioned tenant schema, per the 030/034…, upgrade()

### Community 246 - "devDependencies"
Cohesion: 0.10
Nodes (20): devDependencies, autoprefixer, @axe-core/playwright, eslint, eslint-config-next, eslint-config-prettier, jsdom, @playwright/test (+12 more)

### Community 247 - "Iris Run: add-doc-docx-upload-support"
Cohesion: 0.25
Nodes (8): Kubernetes/Azure deploy target (deploy/k8s/), docker-compose stack (telemetry backends), pipeline-guard (Iris dispatcher), qa-governor (Iris QA agent), ralph (Iris build agent), Telemetry Scan CI Workflow, Iris Run: add-doc-docx-upload-support, Iris Run: deploy-platform-kubernetes-azure

### Community 248 - "Deploy Platform to Kubernetes on Azure (AKS) — requirements baseline"
Cohesion: 0.15
Nodes (15): Local Observability Stack (grafana, otel-collector, tempo, loki, prometheus), tenant_id metric-label allowlist: exactly five metric families, Observability workload instrumentation pytest run: 275 passed, 3 warnings, Metric contract: every metric family, its labels and closed value sets, Entity-type label deliberately absent from every metric family, Model quality (F1/precision/recall/loss) deliberately absent from every metric family, Tenant-label allowlist: 5 metric families may carry tenant_id, Current-state platform inventory: 22 compose containers, config surface, portal URL wiring (+7 more)

### Community 249 - "package.json"
Cohesion: 0.25
Nodes (7): devDependencies, autoprefixer, tailwindcss, autoprefixer, tailwindcss, private, workspaces

### Community 250 - "validate_name_labels.py"
Cohesion: 0.39
Nodes (7): _clean(), _contains_blocklisted_substring(), main(), name_span(), Deterministic post-validation safety net over annotations.jsonl.labeled's NAME…, Returns the char offset where a blocklisted word starts inside the concatenated…, validate()

### Community 251 - "validator.py"
Cohesion: 0.19
Nodes (17): Identifier, _check_columns(), _first_keyword(), _function_names(), _identifiers_in_from(), _is_select_alias(), Exception, AST validator for external PostgreSQL SELECT statements (CAP-4, ADR-013).… (+9 more)

### Community 252 - "ADDED Requirements"
Cohesion: 0.06
Nodes (34): ADDED Requirements, Requirement: Correlation Identifier Propagated Across Every Hop, Requirement: Distributed Traces Spanning Services And Workers, Requirement: Metrics Endpoint On Every Service, Requirement: Opaque Identity In Telemetry, Requirement: Sensitive Content Excluded From Telemetry, Requirement: Shared Observability Initialization Across All Processes, Requirement: Single Shared Observability Middleware (+26 more)

### Community 253 - "ADDED Requirements"
Cohesion: 0.06
Nodes (34): ADDED Requirements, Requirement: Evidence accumulation into existing state keys, Requirement: Intent Orchestrator is the single retrieval routing layer, Requirement: Invalid plan entries are rejected without executing, Requirement: Plan execution budgets, Requirement: Plan-then-execute with no re-planning cycle, Requirement: Plan trace, Requirement: Planning failure degrades to both capabilities on the raw query (+26 more)

### Community 254 - "Requirements"
Cohesion: 0.06
Nodes (34): Document Ingestion Boundary, Purpose, Requirement: Azure Blob sync submits through the common ingestion boundary, Requirement: Declared content-acquisition capability, Requirement: Injectable processing dispatch, Requirement: Normalized document contract, Requirement: Platform upload is an adapter over the ingestion contract, Requirement: Single application-owned ingestion entry point (+26 more)

### Community 255 - "Requirements"
Cohesion: 0.06
Nodes (34): Purpose, Requirement: Baseline regression gate, Requirement: Configuration matrix comparison, Requirement: Deterministic offline evaluation, Requirement: Evaluation executes through the tool layer, Requirement: Report output, Requirement: Retrieval metrics, Requirement: Versioned golden set (+26 more)

### Community 256 - "extraction_proxy.py"
Cohesion: 0.44
Nodes (11): _proxy(), proxy_batch(), proxy_batch_list(), proxy_batch_status(), proxy_eligible_documents(), proxy_extract(), proxy_list_entities(), proxy_patch_entity() (+3 more)

### Community 258 - "Requirement: Contract-authorized SQL execution"
Cohesion: 0.11
Nodes (18): external-postgresql-chat, MODIFIED Requirements, Purpose, Requirement: Contract-authorized SQL execution, Requirement: Drift-gated external read-only query, Requirement: Versioned tenant-isolated schema contracts, Scenario: Approved join and aggregation executes, Scenario: Capability resolves server-side per authenticated tenant (+10 more)

### Community 259 - "c4-diagram skill"
Cohesion: 0.38
Nodes (7): Structurizr MCP server, C4 Diagram README (Corporate Travel Portal), Cloud Platform Service Mapping reference, Reference DSL Full Example, Architectural Pattern Annotation Rules, C4-PlantUML Sprite Mappings, c4-diagram skill

### Community 260 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, Currently-In-Force ADRs, Decision 1: Descriptions live beside columns, not inside them, Decision 2: Index entry text carries descriptions; no schema change, Decision 3: Generator in chat-api, injected into the shared tool through `ToolContext`, Decision 4: Hardcoded prompt rules match the validator's grammar exactly, Decision 5: Tool set composed per turn, Decision 6: Separate evidence channel for external rows (+7 more)

### Community 261 - "clean_name_labels.py"
Cohesion: 0.43
Nodes (6): clean_span(), _clean_word(), main(), name_span(), Deterministic cleanup pass over annotations.jsonl.labeled's NAME spans. Trims…, Returns (new_start, new_end) or None if nothing salvageable. Strategy: walk…

### Community 262 - "test_mlflow_integration_live.py"
Cohesion: 0.19
Nodes (12): MlflowClient, _experiment_name(), cleanup(), db_schema(), experiment_name(), mlflow_client(), fixture, Live integration tests for MLflow integration. Requires: - MLflow Tracking… (+4 more)

### Community 263 - "Requirements"
Cohesion: 0.06
Nodes (33): entity-normalization Specification, Purpose, Requirement: Backfill of previously extracted documents, Requirement: BIO sequence reconstruction, Requirement: Canonical value normalization, Requirement: Entity-level confidence aggregation, Requirement: Location metadata on normalized entities, Requirement: Normalized entity persistence (+25 more)

### Community 264 - "Requirements"
Cohesion: 0.06
Nodes (33): Purpose, Requirement: Adapter selection is observable, Requirement: Only platform default adapters are executable in this change, Requirement: Per-tenant integration profile in control-plane storage, Requirement: Profile status model, Requirement: Profiles are developer-managed, Requirement: Profiles hold secret references, never secret values, Requirement: Typed profile configuration with an allowlisted shape (+25 more)

### Community 265 - "Requirement: Per-Entity-Type Dataset Readiness"
Cohesion: 0.06
Nodes (32): ADDED Requirements, MODIFIED Requirements, REMOVED Requirements, Requirement: Annotator Assigned-Task Fraction, Requirement: Annotator Tenant-Wide Entities Annotated Stat, Requirement: Dashboard Summary Endpoint, Requirement: Per-Entity-Type Dataset Readiness, Requirement: Stat Sub-Labels Carry Information (+24 more)

### Community 266 - "ADDED Requirements"
Cohesion: 0.06
Nodes (32): ADDED Requirements, Requirement: Baseline regression gate, Requirement: Configuration matrix comparison, Requirement: Deterministic offline evaluation, Requirement: Evaluation executes through the tool layer, Requirement: Report output, Requirement: Retrieval metrics, Requirement: Versioned golden set (+24 more)

### Community 267 - "test_dashboard_summary.py"
Cohesion: 0.15
Nodes (10): _platform_health_status(), auth_header(), _FakeHealthClient, _FakeHealthResponse, _seed_annotator_tasks(), _seed_spans(), test_platform_health_status_critical_when_gateway_or_model_serving_offline(), test_platform_health_status_degraded_when_noncritical_offline() (+2 more)

### Community 269 - "TestWorkerSemanticNormalization"
Cohesion: 0.21
Nodes (4): _FakeResponse, asyncio, Covers verification.md rows 1, 2, 5, 18, 20, 21., TestWorkerSemanticNormalization

### Community 270 - "Requirements"
Cohesion: 0.06
Nodes (32): Purpose, Requirement: Chat runtime behaviour is unchanged by the tool layer, Requirement: Document retrieval tools, Requirement: Entity retrieval tool, Requirement: Retrieval tool contract, Requirement: Tenant scope is caller-supplied, never argument-supplied, Requirement: Tool registry and schema export, Requirement: Tool result envelope (+24 more)

### Community 271 - "Requirement: Secondary Metrics Panel"
Cohesion: 0.06
Nodes (31): MODIFIED Requirements, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Requirement: Secondary Metrics Panel, Requirement: Stat Card Strip, Scenario: annotator data shape, Scenario: annotator strip renders three cards including the continue card, Scenario: annotator summary returns real task data (+23 more)

### Community 272 - "preprocess_tokenization.py"
Cohesion: 0.53
Nodes (5): is_shattered(), main(), Repairs recoverable tokenization damage in annotations.jsonl before NAME…, repair_record(), split_token()

### Community 273 - "Requirement: Define / Edit Entity Type Slide-Over"
Cohesion: 0.06
Nodes (31): ADDED Requirements, MODIFIED Requirements, Requirement: Changing an entity type's cardinality requires confirmation, Requirement: Define / Edit Entity Type Slide-Over, Requirement: Editing an entity type preserves its full base label mapping, Requirement: Entity Types API Hooks, Scenario: A multi-key mapping survives an unrelated edit, Scenario: An unchanged cardinality does not prompt (+23 more)

### Community 275 - "test_context_assembly_grep.py"
Cohesion: 0.47
Nodes (5): _python_files(), Covers scenario 14: task 6.3., Covers Hallucination Risk 1: task 6.4., test_exactly_one_system_prompt_definition(), test_no_character_slice_of_chunk_text()

### Community 276 - "TestWorkerNormalizesEntitiesOnIngest"
Cohesion: 0.18
Nodes (5): _FakeResponse, asyncio, Covers verification.md row 19: a failure while inserting normalized entities…, Covers verification.md rows 16-19, 25 — normalized entities are persisted…, TestWorkerNormalizesEntitiesOnIngest

### Community 277 - "ADDED Requirements"
Cohesion: 0.06
Nodes (31): ADDED Requirements, Requirement: Backfill of previously extracted documents, Requirement: BIO sequence reconstruction, Requirement: Canonical value normalization, Requirement: Entity-level confidence aggregation, Requirement: Location metadata on normalized entities, Requirement: Normalized entity persistence, Requirement: Raw BIO storage is preserved (+23 more)

### Community 278 - "P3 — Derived relational persistence: connection routing, not a repository abstraction"
Cohesion: 0.40
Nodes (5): P3 — Derived relational persistence: connection routing, not a repository abstraction, Decomposition: Frontend UI (Next.js portal), Decomposition: Multi-Tenant Custom NER Platform (SM-01..SM-07), Technical Design Document v0.1 (9-service architecture), Entity Relational Projection — Implementation Specification

### Community 279 - "UI Inventory — Tenant Self-Service Data Sources (SCR-1/2/3, CMP-1..10)"
Cohesion: 0.40
Nodes (5): Mockup: Data Source Connection detail screen (HTML), Mockup: Data Sources list screen (HTML), Mockup: Schema Contracts screen (HTML), UI Design Contract — Tenant Self-Service Data Sources, UI Inventory — Tenant Self-Service Data Sources (SCR-1/2/3, CMP-1..10)

### Community 280 - "build_name_review_report.py"
Cohesion: 0.60
Nodes (4): load(), main(), name_span(), Builds a human-readable review report comparing annotations.jsonl (source)…

### Community 281 - "_active_model_card"
Cohesion: 0.40
Nodes (5): _active_model_card(), ActiveModelInfo, _format_deployed_date(), Deployment metadata only — which model is currently serving, not how well it…, Deployment metadata only (which model is serving) — no eval metrics.…

### Community 282 - "Requirement: Annotation Task Management"
Cohesion: 0.06
Nodes (31): Annotation Workspace, Purpose, Requirement: Annotation Export, Requirement: Annotation Task Management, Requirement: Pre-labeling, Requirement: Span CRUD, Requirements, Scenario: Complete a task that has spans (+23 more)

### Community 283 - "Requirement: Sidebar Layout"
Cohesion: 0.06
Nodes (31): Purpose, Requirement: Authenticated Route Group Layout, Requirement: Placeholder Screens, Requirement: Sidebar Layout, Requirement: Topbar Layout, Requirements, Scenario: active nav item is highlighted, Scenario: authenticated access renders shell (+23 more)

### Community 284 - "_JwtOnlyTenantMiddleware"
Cohesion: 0.40
Nodes (4): _JwtOnlyTenantMiddleware, BaseHTTPMiddleware, Request, Resolves tenancy from the token claim, exactly as each service's own middleware…

### Community 285 - "TestTheSharedMiddlewareMakesNoSecurityDecision"
Cohesion: 0.40
Nodes (3): parametrize, Risk-register item 1: the consolidation must not have absorbed access control., TestTheSharedMiddlewareMakesNoSecurityDecision

### Community 286 - "ADDED Requirements"
Cohesion: 0.06
Nodes (30): ADDED Requirements, Requirement: Chat runtime behaviour is unchanged by the tool layer, Requirement: Document retrieval tools, Requirement: Entity retrieval tool, Requirement: Retrieval tool contract, Requirement: Tenant scope is caller-supplied, never argument-supplied, Requirement: Tool registry and schema export, Requirement: Tool result envelope (+22 more)

### Community 287 - "Requirements"
Cohesion: 0.06
Nodes (30): Purpose, Requirement: Celery worker initialisation, Requirement: Fine-tune the model, Requirement: Handle training failure, Requirement: Load annotated dataset, Requirement: Log training run to MLflow Tracking, Requirement: Save model artifacts, Requirement: Tokenize dataset (+22 more)

### Community 288 - "ADDED Requirements"
Cohesion: 0.07
Nodes (29): ADDED Requirements, Requirement: Declared content-acquisition capability, Requirement: Injectable processing dispatch, Requirement: Normalized document contract, Requirement: Platform upload is an adapter over the ingestion contract, Requirement: Single application-owned ingestion entry point, Requirement: The processing pipeline contains no source-specific behaviour, Scenario: A single-use source is never assigned source-only retention (+21 more)

### Community 289 - "ADDED Requirements"
Cohesion: 0.07
Nodes (29): ADDED Requirements, Requirement: Adapter selection is observable, Requirement: Only platform default adapters are executable in this change, Requirement: Per-tenant integration profile in control-plane storage, Requirement: Profile status model, Requirement: Profiles are developer-managed, Requirement: Profiles hold secret references, never secret values, Requirement: Typed profile configuration with an allowlisted shape (+21 more)

### Community 290 - "Requirements"
Cohesion: 0.07
Nodes (29): Purpose, Requirement: DB cache fallback on MLflow outage, Requirement: Experiment and run lifecycle, Requirement: MLflow client-server version compatibility, Requirement: MLflow server health verification, Requirement: Model registration and artifact logging, Requirement: Model registry proxy integration, Requirement: ONNX artifact completeness (+21 more)

### Community 291 - "Requirement: Ephemeral retention uses a bounded working copy"
Cohesion: 0.07
Nodes (29): Original Document Storage, Purpose, Requirement: Document content store boundary, Requirement: Ephemeral retention uses a bounded working copy, Requirement: No consumer parses the storage reference, Requirement: Reprocessability is bounded by retention mode and stated, never silently assumed, Requirement: Retention mode is explicit and determines content resolution, Requirement: The storage reference is an outcome, never an input (+21 more)

### Community 295 - "Multi-tenant NER Platform investor/exec deck (scroll-snap slide deck)"
Cohesion: 0.50
Nodes (4): InApp logo asset, Multi-tenant NER Platform investor/exec deck (scroll-snap slide deck), Platform logo asset (red square mark), Presenter Script for Multi-Tenant NER Platform deck

### Community 296 - "extends"
Cohesion: 0.50
Nodes (3): next/core-web-vitals, extends, prettier

### Community 297 - "ADDED Requirements"
Cohesion: 0.07
Nodes (28): ADDED Requirements, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Requirement: Data Freshness, Requirement: Hero Section, Requirement: Secondary Metrics Panel, Requirement: Stat Card Strip (+20 more)

### Community 298 - "setup_test_db.py"
Cohesion: 0.67
Nodes (3): _assert_test_database(), main(), Create extraction service tables in ner_test database.

### Community 299 - "Requirement: Contract-authorized SQL execution"
Cohesion: 0.11
Nodes (18): ADDED Requirements, external-postgresql-chat, Purpose, Requirement: Contract-authorized SQL execution, Requirement: Drift-gated external read-only query, Requirement: Versioned tenant-isolated schema contracts, Scenario: Approved join and aggregation executes, Scenario: Capability resolves server-side per authenticated tenant (+10 more)

### Community 300 - "MODIFIED Requirements"
Cohesion: 0.07
Nodes (28): MODIFIED Requirements, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Requirement: Data Freshness, Requirement: Hero Section, Requirement: Secondary Metrics Panel, Requirement: Stat Card Strip (+20 more)

### Community 301 - "Requirement: Client-Side File Preview"
Cohesion: 0.07
Nodes (28): Purpose, Requirement: Annotation File Import — Frontend Button, Requirement: Annotation File Upload and Backend Import, Requirement: Backend Partial Import Support, Requirement: Client-Side File Preview, Requirement: Import Result Feedback, Requirements, Scenario: Backend response schema change is backward-compatible (+20 more)

### Community 302 - "Requirement: System Admin Cross-Tenant User Creation Endpoint"
Cohesion: 0.07
Nodes (28): Purpose, Requirement: Admin Console Cross-Tenant User Creation UI, Requirement: Shared User Creation Business Logic, Requirement: System Admin Cross-Tenant User Creation Endpoint, Requirement: Tenant Admin Onboarding Flow Remains Unchanged, Requirement: User Creation Is Audited, Requirements, Scenario: Audit event recorded when System Admin creates a user (+20 more)

### Community 304 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Requirement: Auto-Polling for In-Flight Documents, Requirement: Document Table, Requirement: Document Upload Zone, Requirement: Soft Delete, Requirement: Status Badge, Requirement: Status Filter Tabs, Requirement: Upload Progress Bar (+19 more)

### Community 340 - "QA report for add-doc-docx-upload-support: conditional pass, unit/integration tests blocked by missing PostgreSQL"
Cohesion: 0.67
Nodes (3): Code-quality review of DOC/DOCX upload support: no blocking issues, QA report for add-doc-docx-upload-support: conditional pass, unit/integration tests blocked by missing PostgreSQL, Unit test coverage for DOC/DOCX upload: could not run — PostgreSQL unavailable

### Community 341 - "Requirement: Client-Side File Preview"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Requirement: Annotation File Import — Frontend Button, Requirement: Annotation File Upload and Backend Import, Requirement: Backend Partial Import Support, Requirement: Client-Side File Preview, Requirement: Import Result Feedback, Scenario: Backend response schema change is backward-compatible, Scenario: Backend returns entity type breakdown (+19 more)

### Community 342 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, context-assembly, Requirement: Chunk caps are independently configurable, Requirement: Citations are derived from admitted evidence, Requirement: Duplicate structured values are collapsed before rendering, Requirement: Exhaustiveness claims match what was admitted, Requirement: Retrieval status is rendered into the prompt, Requirement: Structured evidence degrades by truncation, never by silent omission (+19 more)

### Community 343 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Requirement: Bounded structured-to-semantic recovery, Requirement: Conjunctive and multi-source planning contract, Requirement: Consistent cross-invocation score semantics, Requirement: Per-invocation retrieval status, Requirement: Retrieval status reaches the answer model, Requirement: Structural document-scope enforcement for structured retrieval, retrieval-orchestration (+19 more)

### Community 344 - "Widget Key Tester"
Cohesion: 0.67
Nodes (3): Widget Key Tester, POST /api/v1/public/chat (chat_api), ner_widget_... bearer key format

### Community 418 - "ADDED Requirements"
Cohesion: 0.07
Nodes (27): ADDED Requirements, Requirement: Document content store boundary, Requirement: Ephemeral retention uses a bounded working copy, Requirement: No consumer parses the storage reference, Requirement: Reprocessability is bounded by retention mode and stated, never silently assumed, Requirement: Retention mode is explicit and determines content resolution, Requirement: The storage reference is an outcome, never an input, Scenario: A NULL reference is not reported as a failure (+19 more)

### Community 419 - "data_sources.py"
Cohesion: 0.12
Nodes (41): enqueue_sync(), activate_data_source(), _body_digest(), create_data_source(), _created(), _data_plane_body(), _enqueue_blob_sync(), _error() (+33 more)

### Community 420 - "Requirement: Contract-authorized SQL execution"
Cohesion: 0.11
Nodes (18): external-postgresql-chat Specification, Purpose, Requirement: Contract-authorized SQL execution, Requirement: Drift-gated external read-only query, Requirement: Versioned tenant-isolated schema contracts, Requirements, Scenario: Approved join and aggregation executes, Scenario: Capability resolves server-side per authenticated tenant (+10 more)

### Community 421 - "Requirement: Guardrail — blocked question types"
Cohesion: 0.07
Nodes (26): MODIFIED Requirements, REMOVED Requirements, Requirement: Guardrail — blocked question types, Requirement: Guardrail — query complexity limits, Requirement: Guardrail — source citation enforcement, Requirement: NER inference for chat context, Requirement: pgvector semantic search, Requirement: RAG chat endpoint (+18 more)

### Community 422 - "Requirement: System Admin Cross-Tenant User Creation Endpoint"
Cohesion: 0.07
Nodes (26): ADDED Requirements, Requirement: Admin Console Cross-Tenant User Creation UI, Requirement: Shared User Creation Business Logic, Requirement: System Admin Cross-Tenant User Creation Endpoint, Requirement: Tenant Admin Onboarding Flow Remains Unchanged, Requirement: User Creation Is Audited, Scenario: Audit event recorded when System Admin creates a user, Scenario: Audit event recorded when Tenant Admin creates a user (+18 more)

### Community 423 - "Requirement: Audit Log Page Tenant Filter UI"
Cohesion: 0.07
Nodes (26): audit-log Specification, Purpose, Requirement: Audit Log Endpoint Tenant Filtering, Requirement: Audit Log Page Tenant Filter UI, Requirement: List Audit Events via API, Requirement: Persist Audit Events, Requirement: Render Audit Log Page, Requirements (+18 more)

### Community 424 - "Requirement: Define / Edit Entity Type Slide-Over"
Cohesion: 0.07
Nodes (26): Purpose, Requirement: Activate / Deactivate Entity Type, Requirement: Define / Edit Entity Type Slide-Over, Requirement: Entity Type Card, Requirement: Entity Types API Hooks, Requirement: Entity Types List Page, Requirements, Scenario: API error shows error toast (+18 more)

### Community 425 - "MODIFIED Requirements"
Cohesion: 0.08
Nodes (25): MODIFIED Requirements, MODIFIED Requirements, MODIFIED Requirements, MODIFIED Requirements, MODIFIED Requirements, REMOVED Requirements, Requirement: Activity Panel, Requirement: Hero Section (+17 more)

### Community 426 - "Requirement: Define / Edit Entity Type Slide-Over"
Cohesion: 0.08
Nodes (25): ADDED Requirements, Requirement: Activate / Deactivate Entity Type, Requirement: Define / Edit Entity Type Slide-Over, Requirement: Entity Type Card, Requirement: Entity Types API Hooks, Requirement: Entity Types List Page, Scenario: API error shows error toast, Scenario: BASE MODEL LABEL chip selection is single-select (+17 more)

### Community 427 - "Requirement: Bounded relational surface and value samples in the generation context"
Cohesion: 0.08
Nodes (25): MODIFIED Requirements, RENAMED Requirements, Requirement: Attempt outcome classification, Requirement: Bounded relational surface and value samples in the generation context, Requirement: Previous-attempt feedback is supplied to the generator, Requirement: Zero rows is a legitimate result unless a deterministic defect explains it, Scenario: A column no relation declares is classified as a validation failure, Scenario: A value that occurs nowhere in the tenant's data is not a defect (+17 more)

### Community 428 - "ADDED Requirements"
Cohesion: 0.08
Nodes (24): ADDED Requirements, Requirement: Batch extraction, Requirement: Get extraction run status, Requirement: Post-processing confidence filtering, Requirement: Query extracted entities, Requirement: Real-time extraction, Requirement: Review and correct entities, Scenario: Batch extraction for tenant with no promoted model (+16 more)

### Community 429 - "ADDED Requirements"
Cohesion: 0.08
Nodes (24): ADDED Requirements, Requirement: Approve/reject training job (system_admin), Requirement: Cancel training job from UI, Requirement: Submit training job, Requirement: Training job detail panel, Requirement: Training job list view, Scenario: Approve a pending job as system_admin, Scenario: Approve/reject buttons hidden for non-pending jobs (+16 more)

### Community 430 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.08
Nodes (24): MODIFIED Requirements, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Requirement: Secondary Metrics Panel, Scenario: activity row navigates on click, Scenario: annotator data shape, Scenario: annotator summary returns real task data (+16 more)

### Community 431 - "Requirement: Token-budgeted context assembly"
Cohesion: 0.08
Nodes (24): context-assembly Specification, Purpose, Requirement: Context assembly configuration, Requirement: Overlapping chunk deduplication, Requirement: Provenance-labeled context, Requirement: Single shared assembly implementation, Requirement: Token-budgeted context assembly, Requirements (+16 more)

### Community 432 - "Requirements"
Cohesion: 0.08
Nodes (24): Purpose, Requirement: Authorization Failures And Rate-Limit Rejections Are Counted, Requirement: Automated Release-Gate Telemetry Scan, Requirement: Cross-Tenant Access Attempts Are Counted, Requirement: Metric Label Cardinality Allowlist, Requirement: Tenant Schema Is Asserted Before Query Execution, Requirement: Touched OCR failure paths emit safe structured error classes, Requirements (+16 more)

### Community 433 - "Requirement: Annotation Task Management"
Cohesion: 0.08
Nodes (23): ADDED Requirements, Requirement: Annotation Export, Requirement: Annotation Task Management, Requirement: Pre-labeling, Requirement: Span CRUD, Scenario: Complete a task that has spans, Scenario: Complete a task with no spans returns 422, Scenario: Create a span on a processed document (+15 more)

### Community 434 - "Requirement: Entity Review Tab — Entity Listing and Review"
Cohesion: 0.08
Nodes (23): ADDED Requirements, Requirement: Batch Runs Tab — Batch Extraction Management, Requirement: Entity Review Tab — Entity Listing and Review, Requirement: Extraction Page Layout and Tab Navigation, Requirement: Playground Tab — Real-time Extraction, Scenario: Batch Runs tab lists existing runs, Scenario: Changing filter re-fetches entities, Scenario: Clicking a tab switches the active content (+15 more)

### Community 435 - "ADDED Requirements"
Cohesion: 0.08
Nodes (23): ADDED Requirements, Requirement: Create and update accept cardinality, Requirement: Creating an entity type assigns its sql_identifier, Requirement: Definition write paths reconcile the tenant's generated schema, Requirement: Entity type payloads are validated by a typed schema, Requirement: Entity type responses expose view-layer metadata, Scenario: A client-supplied sql_identifier is ignored, Scenario: A malformed create payload returns 422 (+15 more)

### Community 436 - "Requirement: Document Upload Zone"
Cohesion: 0.08
Nodes (23): ADDED Requirements, MODIFIED Requirements, Requirement: Cancel an In-Progress Batch, Requirement: Document Upload Zone, Requirement: Upload Progress Bar, Scenario: Batch position is shown during a multi-file upload, Scenario: Batch summary after all files succeed, Scenario: Cancel a batch after the first file succeeds (+15 more)

### Community 437 - "ADDED Requirements"
Cohesion: 0.09
Nodes (22): ADDED Requirements, Requirement: DB cache fallback on MLflow outage, Requirement: Experiment and run lifecycle, Requirement: MLflow server health verification, Requirement: Model registration and artifact logging, Requirement: Model registry proxy integration, Requirement: Status-to-stage mapping consistency, Requirement: Tenant isolation via naming convention (+14 more)

### Community 438 - "Requirement: Sidebar Layout"
Cohesion: 0.09
Nodes (22): MODIFIED Requirements, Requirement: Sidebar Layout, Requirement: Topbar Layout, Scenario: active nav item is highlighted, Scenario: avatar has 10px border radius, Scenario: badge renders when present, Scenario: dark mode toggle has 10px border radius, Scenario: dark mode toggle switches theme (+14 more)

### Community 439 - "ADDED Requirements"
Cohesion: 0.09
Nodes (22): ADDED Requirements, Requirement: Editing Imported Row Annotations, Requirement: Imported Documents List View, Requirement: Imported Rows Remain Decoupled from the Annotation Task Pipeline, Requirement: Review Progress Tracking, Requirement: Token-Level Rendering with Entity Colors, Scenario: B/I run renders as one colored span, Scenario: Create a new span from unselected tokens (+14 more)

### Community 440 - "Requirement: Sidebar Layout"
Cohesion: 0.09
Nodes (22): MODIFIED Requirements, Requirement: Sidebar Layout, Requirement: Topbar Layout, Scenario: active nav item is highlighted, Scenario: avatar has 10px border radius, Scenario: badge renders when present, Scenario: dark mode toggle has 10px border radius, Scenario: dark mode toggle switches theme (+14 more)

### Community 441 - "ADDED Requirements"
Cohesion: 0.09
Nodes (22): ADDED Requirements, Requirement: Context assembly configuration, Requirement: Overlapping chunk deduplication, Requirement: Provenance-labeled context, Requirement: Single shared assembly implementation, Requirement: Token-budgeted context assembly, Scenario: A chunk that does not fit is skipped, not cut, Scenario: A full chunk reaches the prompt intact (+14 more)

### Community 442 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.09
Nodes (22): MODIFIED Requirements, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Scenario: activity row navigates on click, Scenario: annotator data shape, Scenario: annotator summary returns real task data, Scenario: business_user conversation row navigates to chat (+14 more)

### Community 443 - "Requirements"
Cohesion: 0.09
Nodes (22): chat-orchestration-graph Specification, Purpose, Requirement: Explicit stage outcomes in state, Requirement: Fixed topology with no agentic behaviour, Requirement: Graph-based chat execution flow, Requirement: Node-level observability, Requirement: Per-request state isolation, Requirement: Retrieval and model components are orchestrated, not replaced (+14 more)

### Community 444 - "Requirements"
Cohesion: 0.09
Nodes (22): Purpose, Requirement: Authenticated API calls from chat page, Requirement: Chat screen route and access, Requirement: Conversation sidebar, Requirement: Message thread display, Requirement: Rename conversation from sidebar, Requirement: Role-gated chat access, Requirements (+14 more)

### Community 445 - "Requirements"
Cohesion: 0.09
Nodes (22): Purpose, Requirement: Environment variable interface, Requirement: ESLint and Prettier configuration, Requirement: Next.js workspace structure, Requirement: Root layout with provider wiring, Requirement: Tailwind CSS integration, Requirement: TypeScript strict configuration, Requirement: Vitest and Testing Library setup (+14 more)

### Community 446 - "ADDED Requirements"
Cohesion: 0.09
Nodes (21): ADDED Requirements, Requirement: BIO reconstruction tolerates a bounded same-page gap in a continuation, Requirement: Canonicalization removes Unicode format characters and folds typographic punctuation, Requirement: Entity spans are punctuation-trimmed with offsets adjusted, Requirement: Invalid entities are rejected before persistence, Scenario: A gap wider than the bound still splits, Scenario: A legitimate short value of a configured short-code type is persisted, Scenario: A punctuation-only entity is not persisted (+13 more)

### Community 447 - "Requirement: Batch extraction"
Cohesion: 0.09
Nodes (21): MODIFIED Requirements, Requirement: Batch extraction, Requirement: Post-processing confidence filtering, Scenario: A run degraded by post-processing failure is reported as such, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction skips already-extracted documents, Scenario: Batch extraction uses version 0 when no model promoted (+13 more)

### Community 448 - "Requirement: SQL query generation and validation"
Cohesion: 0.09
Nodes (21): chat-api, MODIFIED Requirements, Requirement: Guardrail — source citation enforcement, Requirement: RAG chat endpoint, Requirement: SQL query generation and validation, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with simple entity count query (+13 more)

### Community 449 - "Requirements"
Cohesion: 0.09
Nodes (21): Purpose, Requirement: Citation enrichment with entity type resolution, Requirement: Citation model with document names and entity type names, Requirement: Configurable chat API service URL, Requirement: Conversation creation endpoint, Requirement: Disclaimer in every response, Requirement: Per-request authorization context isolation, Requirement: Rate limiting (+13 more)

### Community 450 - "Requirement: SQL query generation and validation"
Cohesion: 0.09
Nodes (22): Requirement: SQL query generation and validation, Scenario: A child table retained from a `multi` era is excluded from the query surface, Scenario: A generated entity table is both granted and whitelisted, Scenario: A grant for a table that does not yet exist is skipped safely, Scenario: A table that leaves the query surface loses its grant, Scenario: An inactive definition's table is excluded from the query surface, Scenario: Comma-joined non-whitelisted table is rejected, Scenario: Entity lookup matches on the canonical value (+14 more)

### Community 451 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.09
Nodes (21): Purpose, Requirement: Dashboard Summary Endpoint, Requirement: DashboardData TypeScript Type, Requirements, Scenario: A partial aggregate is not reported as a complete total, Scenario: Active Users count reflects tenant_users status, Scenario: An unreachable critical service reports Critical status, Scenario: An unreachable non-critical service degrades status without failing the request (+13 more)

### Community 452 - "Requirement: Promote model version"
Cohesion: 0.09
Nodes (21): Model Registry, Purpose, Requirement: Demote model version, Requirement: Get active model version, Requirement: List model versions, Requirement: Promote model version, Requirements, Scenario: Demote a non-promoted model returns 422 (+13 more)

### Community 453 - "SlidingWindowRateLimiter"
Cohesion: 0.13
Nodes (6): _count_rejection(), Count one rejection, splitting the bucket key into its scope and tenant. Keys…, SlidingWindowRateLimiter, The tenant label here is deliberate: a rejected request produces the least…, TestRateLimitRejectionsAreCounted, TestRateLimiter

### Community 454 - "ADDED Requirements"
Cohesion: 0.13
Nodes (14): ADDED Requirements, Requirement: Bounded schema context without retrieval, Requirement: Contract-grounded SQL generation, Requirement: Generation telemetry is content-free, Requirement: Local validation with bounded reason-guided retry, Scenario: Accepted statement executes once through the drift gate, Scenario: Attempts are bounded, Scenario: Generated statement uses placeholders for values (+6 more)

### Community 455 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Environment variable interface, Requirement: ESLint and Prettier configuration, Requirement: Next.js workspace structure, Requirement: Root layout with provider wiring, Requirement: Tailwind CSS integration, Requirement: TypeScript strict configuration, Requirement: Vitest and Testing Library setup (+12 more)

### Community 456 - "Requirement: Extraction Service Endpoints Auto-Resolve Tenant ID from JWT"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Callers Construct URLs Without {tid}, Requirement: Extraction Service Endpoints Auto-Resolve Tenant ID from JWT, Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure, Requirement: Model Serving Endpoints Auto-Resolve Tenant ID from JWT, Scenario: Batch extraction accepts request without tid in URL, Scenario: Batch status returns run details without tid in URL, Scenario: Entity list returns entities without tid in URL (+12 more)

### Community 457 - "Requirement: Layout and Navigation"
Cohesion: 0.10
Nodes (20): ADDED Requirements, MODIFIED Requirements, Requirement: Layout and Navigation, Requirement: Span Deselection, Requirement: Task Display Name, Requirement: Task Status Lifecycle, Scenario: Browser-native fullscreen exit (Escape) syncs layout state, Scenario: Clicking an unannotated token closes the span inspector (+12 more)

### Community 458 - "Decisions"
Cohesion: 0.10
Nodes (20): Context, Currently-In-Force ADRs, Decision 10: Structured document scope is applied as a bound parameter, not appended prose, Decision 11: Guardrail differentiates empty from failed, Decision 12: Planning contract changes are prompt-and-verify, not a new planner, Decision 1: Resolve every table reference with a hardened clause parser, no dependency, Decision 2: Least-privilege role for generated-SQL execution, Decision 3: `RetrievalStatus` replaces the two collapsed error booleans (+12 more)

### Community 459 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Answer-level correctness evaluation, Requirement: Degraded and failed queries score zero, Requirement: Evaluation runs against tenant-representative data, Requirement: Query-class evaluation coverage, retrieval-eval, Scenario: Aggregate reports failure counts alongside scores, Scenario: Answer asserting absence of retrievable data fails (+12 more)

### Community 460 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Explicit stage outcomes in state, Requirement: Fixed topology with no agentic behaviour, Requirement: Graph-based chat execution flow, Requirement: Node-level observability, Requirement: Per-request state isolation, Requirement: Retrieval and model components are orchestrated, not replaced, Scenario: Blocked question short-circuits to END (+12 more)

### Community 461 - "Requirement: Get training job status"
Cohesion: 0.10
Nodes (20): ADDED Requirements, MODIFIED Requirements, Requirement: Get training job status, Requirement: Model version reuses its training job's run number, Requirement: Submit training job, Scenario: Completed job's model version shares the job's run name, Scenario: Get status of completed job, Scenario: Get status of failed job (+12 more)

### Community 462 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Authorization Failures And Rate-Limit Rejections Are Counted, Requirement: Automated Release-Gate Telemetry Scan, Requirement: Cross-Tenant Access Attempts Are Counted, Requirement: Metric Label Cardinality Allowlist, Requirement: Tenant Schema Is Asserted Before Query Execution, Scenario: A clean run passes the scan, Scenario: A deliberately reintroduced leak fails the scan (+12 more)

### Community 463 - "ADDED Requirements"
Cohesion: 0.10
Nodes (20): ADDED Requirements, Requirement: Assistant messages carry model-identity metadata for future evaluation, Requirement: Feedback data model supports future extension, Requirement: Feedback restricted to the Business User role, Requirement: One immutable rating per eligible assistant message, Requirement: Only eligible assistant answer messages are rateable, Scenario: A new feedback attribute can be added without breaking existing rows, Scenario: Assistant message from an NER-grounded answer records model_version (+12 more)

### Community 464 - "Requirements"
Cohesion: 0.10
Nodes (20): Purpose, Requirement: Create and Update Endpoints Return Flat Entity Object, Requirement: Entity Type Read Responses Deserialize JSON Columns, Requirement: Entity Type Routes Use Name Identifier, Requirement: Entity Types API Tenant-Scoped Routes, Requirement: PATCH Endpoint for Toggling Active Status, Requirements, Scenario: Deactivate sets is_active to false (+12 more)

### Community 465 - "Requirement: A generated `subject` column's physical type equals the type its definition declares"
Cohesion: 0.10
Nodes (20): entity-view-layer Specification, Purpose, Requirement: A column no active `single` definition owns is left at its existing type, Requirement: A failed convergence leaves the catalog and the physical schema consistent, Requirement: A generated `subject` column's physical type equals the type its definition declares, Requirement: Converging a column preserves the system of record and destroys no relation, Requirements, Scenario: A column created under one kind converges when the kind changes (+12 more)

### Community 466 - "Requirements"
Cohesion: 0.10
Nodes (20): Purpose, Requirement: Dependency Connection Retry with Bounded Exponential Backoff, Requirement: Externally Configurable Deployment Assumptions, Requirement: Liveness Endpoint Independent of Dependency State, Requirement: Readiness Endpoint Reflects Actual Dependency State, Requirement: Retry Parameters Are Externally Configurable, Requirements, Scenario: A critical dependency is unreachable (+12 more)

### Community 467 - "Requirement: useToast hook and ToastProvider"
Cohesion: 0.10
Nodes (20): Purpose, Requirement: Hook barrel export, Requirement: Unit test coverage for hooks, Requirement: useDarkMode hook, Requirement: useToast hook and ToastProvider, Requirements, Scenario: bad kind uses error colour, Scenario: Banner auto-dismisses after 4 seconds (+12 more)

### Community 468 - "2026-07-13-fix-model-loading-and-label-mapping/design.md"
Cohesion: 0.10
Nodes (19): Addendum 2 (found during exploration, 2026-07-13), Addendum 3 (found during apply-time verification, 2026-07-13), Addendum 4 (found during user re-test, 2026-07-13), Addendum (found during implementation), Context, Currently-In-Force ADRs, Decision 1: Fix training worker to use spec-compliant S3 path, Decision 2: Store label_list in model_versions.metrics during training (+11 more)

### Community 469 - "Requirement: Stable Inter-Service Communication via Docker DNS"
Cohesion: 0.10
Nodes (19): ADDED Requirements, MODIFIED Requirements, Requirement: Docker Build Context Hygiene, Requirement: Shared Root Dockerfile, Requirement: Single-Command Local Stack Startup, Requirement: Stable Inter-Service Communication via Docker DNS, Scenario: All services built from shared Dockerfile, Scenario: All services start with docker compose up (+11 more)

### Community 470 - "Decisions"
Cohesion: 0.10
Nodes (19): Context, Currently-In-Force ADRs, Decision 10: Missing table or column fails the document, Decision 11: Close the configuration path before the projection goes live, Decision 12: Cardinality stays editable, behind a confirmation, Decision 1: Physical tables, not views, Decision 2: One write point, inside the existing transaction, Decision 3: Routing by entity-type literal set, never by name equality (+11 more)

### Community 471 - "Decisions"
Cohesion: 0.10
Nodes (19): Context, Currently-In-Force ADRs, Decision 10: The allowlist is five families, enforced against the live registry, Decision 11: The release-gate scan drives the real stack and treats an empty capture as failure, Decision 12: Entity type is a span attribute, never a metric label, Decision 1: One declared registry of domain metrics, not `create_counter` at call sites, Decision 2: Label values are derived categories, never the underlying field, Decision 3: Instrument the service layer, not the graph nodes (+11 more)

### Community 472 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.10
Nodes (19): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Requirement: DashboardData TypeScript Type, Scenario: A partial aggregate is not reported as a complete total, Scenario: annotator summary returns task data, Scenario: business_user summary returns extraction data, Scenario: null values are assignable, Scenario: one tenant schema failure does not blank out other tenants' stats (+11 more)

### Community 473 - "Requirements"
Cohesion: 0.10
Nodes (19): Purpose, Requirement: Colour palette tokens, Requirement: CSS custom-property token declarations, Requirement: Page enter animation keyframe, Requirement: Radius and shadow tokens, Requirement: Tailwind config token references, Requirement: Typography tokens, Requirements (+11 more)

### Community 474 - "Requirement: Environment Configuration Loading"
Cohesion: 0.10
Nodes (19): Environment Configuration, Purpose, Requirement: docker-compose Uses Environment Interpolation for Secrets, Requirement: .env Excluded from Version Control, Requirement: Environment Configuration Loading, Requirement: Environment Variable Documentation, Requirements, Scenario: docker-compose resolves NER_JWT_SECRET from .env (+11 more)

### Community 475 - "ADDED Requirements"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Async OCR Processing, Requirement: Document Metadata API, Requirement: Document Upload, Requirement: Tenant Context Enforcement, Scenario: Authenticated request with valid tenant, Scenario: Delete a document, Scenario: Get deleted document returns 200 with deleted status (+10 more)

### Community 476 - "Requirement: Get training job status"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Cancel training job, Requirement: Get training job status, Requirement: List training jobs, Requirement: Submit training job, Scenario: Cancel a completed job returns 422, Scenario: Cancel a queued job, Scenario: Get status of completed job (+10 more)

### Community 477 - "ADDED Requirements"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Celery worker initialisation, Requirement: Fine-tune the model, Requirement: Handle training failure, Requirement: Load annotated dataset, Requirement: Save model artifacts, Requirement: Tokenize dataset, Requirement: Update job progress during training (+10 more)

### Community 478 - "Requirement: useToast hook and ToastProvider"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Hook barrel export, Requirement: Unit test coverage for hooks, Requirement: useDarkMode hook, Requirement: useToast hook and ToastProvider, Scenario: bad kind uses error colour, Scenario: Banner auto-dismisses after 4 seconds, Scenario: Calling useToast outside ToastProvider throws (+10 more)

### Community 479 - "Requirement: Sidebar Layout"
Cohesion: 0.11
Nodes (18): MODIFIED Requirements, Requirement: Sidebar Layout, Requirement: Topbar Layout, Scenario: active nav item is highlighted, Scenario: badge renders when present, Scenario: dark mode toggle switches theme, Scenario: logout clears session and redirects, Scenario: menu closes on backdrop click (+10 more)

### Community 480 - "ADDED Requirements"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Create and Update Endpoints Return Flat Entity Object, Requirement: Entity Type Read Responses Deserialize JSON Columns, Requirement: Entity Type Routes Use Name Identifier, Requirement: Entity Types API Tenant-Scoped Routes, Requirement: PATCH Endpoint for Toggling Active Status, Scenario: Deactivate sets is_active to false, Scenario: GET by name returns 404 when not found (+10 more)

### Community 481 - "MODIFIED Requirements"
Cohesion: 0.11
Nodes (18): MODIFIED Requirements, Requirement: Internal inference endpoint, Requirement: Model loader uses API-provided artifact path, Requirement: Model Registry URL is configurable and targets the correct in-network port, Requirement: ONNX inference inputs match the loaded session's declared inputs, Scenario: A misconfigured or unreachable registry URL still falls back to the base model, Scenario: A promoted model is actually used for extraction, not silently replaced by the base model, Scenario: Inference falls back to base model when no tenant model exists (+10 more)

### Community 482 - "Requirement: Continue-Work Card Payload"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Continue-Work Card Payload, Requirement: Continue-Work Card Rendering, Scenario: card is not rendered for other roles, Scenario: caught-up state renders without a link, Scenario: caught-up state when no tasks are assigned at all, Scenario: completed task is offered for review when nothing else remains, Scenario: every not-started vocabulary is recognised (+10 more)

### Community 483 - "ADDED Requirements"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: Dependency Connection Retry with Bounded Exponential Backoff, Requirement: Externally Configurable Deployment Assumptions, Requirement: Liveness Endpoint Independent of Dependency State, Requirement: Readiness Endpoint Reflects Actual Dependency State, Requirement: Retry Parameters Are Externally Configurable, Scenario: A critical dependency is unreachable, Scenario: All dependencies reachable (+10 more)

### Community 484 - "Decisions"
Cohesion: 0.11
Nodes (18): Context, Currently-In-Force ADRs, Decision 10: Processing mode is a server-validated request field, recorded on the run, Decision 11: The post-processor is a tenant-scoped, server-controlled client in the extraction worker, Decision 1: Calibrate confidence in `model_serving`, before anything else in this change, Decision 2: Deterministic repairs land as a distinct, LLM-free group, and land first, Decision 3: A validity gate and an explicit duplicate policy, at the persistence boundary, Decision 4: Post-process **selected candidates only**, never every entity — Option B (+10 more)

### Community 485 - "ADDED Requirements"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: A labelled entity fixture covers every observed failure class, Requirement: A post-processing configuration must pass a quality gate before being offered, Requirement: Downstream structured-query success is measured, Requirement: Entity-level metrics are computed per configuration, Requirement: Three configurations are compared so the LLM's contribution is isolated, Scenario: A configuration that regresses retrieval is blocked, Scenario: A deterministic-only gain is attributed correctly (+10 more)

### Community 486 - "Decisions"
Cohesion: 0.11
Nodes (18): Context, Currently-In-Force ADRs, Decision 1: Where the orchestration boundary sits, Decision 2: Node granularity, Decision 3: Parallel fan-out via two edges, not `asyncio.gather` inside one node, Decision 4: State schema — a `TypedDict` with `total=False`, Decision 5: Graph compiled once at import; state carries the request, Decision 6: `jwt_token` threading replaces attribute mutation (+10 more)

### Community 487 - "Requirement: SQL query generation and validation"
Cohesion: 0.11
Nodes (18): ADDED Requirements, MODIFIED Requirements, Requirement: Candidate document filtering of semantic retrieval, Requirement: SQL query generation and validation, Requirement: Structured retrieval returns candidate document IDs, Scenario: Candidate IDs are the distinct document IDs of the result rows, Scenario: Empty candidate set leaves semantic retrieval unfiltered, Scenario: Entity lookup matches on the canonical value (+10 more)

### Community 488 - "Requirement: Message feedback submission endpoint"
Cohesion: 0.11
Nodes (18): ADDED Requirements, MODIFIED Requirements, Requirement: Conversation CRUD, Requirement: Message feedback submission endpoint, Scenario: Business user submits first rating on an eligible answer, Scenario: Delete another user's conversation returns 404, Scenario: Delete conversation, Scenario: Get conversation messages (+10 more)

### Community 489 - "Requirement: A generated `subject` column's physical type equals the type its definition declares"
Cohesion: 0.11
Nodes (18): ADDED Requirements, Requirement: A column no active `single` definition owns is left at its existing type, Requirement: A failed convergence leaves the catalog and the physical schema consistent, Requirement: A generated `subject` column's physical type equals the type its definition declares, Requirement: Converging a column preserves the system of record and destroys no relation, Scenario: A column created under one kind converges when the kind changes, Scenario: A column reclaimed by a reactivated definition converges, Scenario: A deactivated definition's column keeps its type and rows (+10 more)

### Community 490 - "Requirement: Common durable Blob ingestion"
Cohesion: 0.11
Nodes (18): ADDED Requirements, azure-blob-source-sync, Purpose, Requirement: Common durable Blob ingestion, Requirement: Idempotent source version reconciliation and temporary retention, Requirement: Tenant-scoped safe sync status, Scenario: Changed object is atomically replaced, Scenario: Deleted source object (+10 more)

### Community 491 - "Requirements"
Cohesion: 0.11
Nodes (18): analytics-dashboard, Purpose, Requirement: Confidence Distribution Widget, Requirement: Dashboard Aggregation API, Requirement: Entity Coverage Widget, Requirement: Extraction Volume Over Time Widget, Requirement: Materialized View Refresh on Extraction Event, Requirement: On-Demand Materialized View Refresh (+10 more)

### Community 492 - "Requirement: Common durable Blob ingestion"
Cohesion: 0.11
Nodes (18): azure-blob-source-sync Specification, Purpose, Requirement: Common durable Blob ingestion, Requirement: Idempotent source version reconciliation and temporary retention, Requirement: Tenant-scoped safe sync status, Requirements, Scenario: Changed object is atomically replaced, Scenario: Deleted source object (+10 more)

### Community 493 - "Requirement: Tenant Admin Dashboard Queries"
Cohesion: 0.11
Nodes (18): Purpose, Requirement: Annotator Dashboard Queries, Requirement: Business User Dashboard Queries, Requirement: Tenant Admin Dashboard Queries, Requirements, Scenario: annotator completion percentage, Scenario: annotator shows task activity rows, Scenario: annotator side panel shows dataset readiness (+10 more)

### Community 494 - "Requirement: Entity Type Definition"
Cohesion: 0.11
Nodes (18): Entity Configuration, Purpose, Requirement: Base Label Mapping, Requirement: Entity Type Definition, Requirement: Entity Type Listing and Query, Requirements, Scenario: An entity type predating the view layer defaults to multi, Scenario: Cardinality is constrained to the two known values (+10 more)

### Community 495 - "Requirement: Tenant Admin Dashboard Queries"
Cohesion: 0.11
Nodes (17): ADDED Requirements, Requirement: Annotator Dashboard Queries, Requirement: Business User Dashboard Queries, Requirement: Tenant Admin Dashboard Queries, Scenario: annotator completion percentage, Scenario: annotator shows task activity rows, Scenario: annotator side panel shows dataset readiness, Scenario: annotator stats return assigned task and span counts (+9 more)

### Community 496 - "Requirement: Get training job status"
Cohesion: 0.11
Nodes (17): MODIFIED Requirements, Requirement: Get training job status, Requirement: List training jobs, Scenario: Get status of completed job, Scenario: Get status of failed job, Scenario: Get status of queued job, Scenario: Get status of running job, Scenario: Get training job as non-owner tenant (+9 more)

### Community 497 - "Requirement: Annotation Action Bar"
Cohesion: 0.11
Nodes (17): ADDED Requirements, MODIFIED Requirements, Requirement: Annotation Action Bar, Requirement: Annotation Toolbar, Requirement: Task Status Lifecycle, Scenario: Action bar disabled with no task selected, Scenario: Action bar renders at the bottom of the workspace, Scenario: Badge reflects completed status without offering a transition (+9 more)

### Community 498 - "Decisions"
Cohesion: 0.11
Nodes (17): Constraints shaping this design, Context, Currently-In-Force ADRs, Decision 1: The loop lives inside `SQLGenerator.generate_and_execute`, not in the graph, Decision 2: Explicit outcome classification replaces the catch-all `except`, Decision 3: Zero rows is a legitimate answer unless a deterministic defect explains it, Decision 4: Failures propagate as `ToolResult.error`; the sink carries the trace, Decision 5: One bounded tenant entity profile, fetched once per invocation (+9 more)

### Community 499 - "ADDED Requirements"
Cohesion: 0.11
Nodes (17): ADDED Requirements, Requirement: Original BERT output survives post-processing, Requirement: Post-processing changes are attributable to a model and prompt version, Requirement: Repeated mentions collapse to one row with an occurrence count, Requirement: Rows record which extraction pipeline produced them, Scenario: A modified value retains its original, Scenario: A row that was never post-processed is distinguishable, Scenario: All rows changed by a given prompt version are queryable (+9 more)

### Community 500 - "2026-09-08-entity-relational-projection/tasks.md"
Cohesion: 0.11
Nodes (17): 10. Portal — types and hooks, 11. Portal — entity type form, 12. Portal — cardinality change confirmation, 13. Document delete propagation, 14. Grants and query whitelist, 15. Documentation and out-of-scope guards, 16. End-to-end verification, 17. Verification & Evidence (+9 more)

### Community 501 - "Requirement: Entity Review Tab — Entity Listing and Review"
Cohesion: 0.11
Nodes (17): MODIFIED Requirements, Requirement: Entity Review Tab — Entity Listing and Review, Requirement: Playground Tab — Real-time Extraction, Scenario: BIO prefix is stripped from entity type in display, Scenario: Changing filter re-fetches entities, Scenario: Confidence color coding reflects thresholds, Scenario: Confirming an entity updates its review status optimistically, Scenario: Empty entity list shows empty state (+9 more)

### Community 502 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.11
Nodes (17): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Scenario: A partial aggregate is not reported as a complete total, Scenario: Active Users count reflects tenant_users status, Scenario: An unreachable critical service reports Critical status, Scenario: An unreachable non-critical service degrades status without failing the request, Scenario: annotator summary returns task data, Scenario: business_user summary returns extraction data (+9 more)

### Community 503 - "Requirement: Job list card content"
Cohesion: 0.11
Nodes (17): ADDED Requirements, MODIFIED Requirements, Requirement: Hyperparameters render as a single 4-column row, Requirement: Job list card content, Requirement: Submit slide-over visual parity without behavior change, Requirement: System Admin approval form collects hyperparameters, Scenario: Approve action opens a hyperparameter form, Scenario: Approve form submits entered hyperparameters (+9 more)

### Community 504 - "Requirement: Activity Panel"
Cohesion: 0.11
Nodes (17): MODIFIED Requirements, Requirement: Activity Panel, Requirement: Dashboard Data Shape, Scenario: activity row navigates on click, Scenario: annotator added event appears in tenant_admin activity feed, Scenario: annotator data shape, Scenario: business user added event appears in tenant_admin activity feed, Scenario: business_user data shape (+9 more)

### Community 505 - "Decisions"
Cohesion: 0.11
Nodes (17): Context, Currently-In-Force ADRs, Decision 10: Naming is reconciled once, across all four documents, Decision 1: One inbound ingestion contract; the pull-side source contract is separate and deferred, Decision 2: Content acquisition is a declared capability, and retention mode is the recorded resolution, Decision 3: The content store has three operations, and the storage reference is an outcome, Decision 4: The OCR branch keys off media type, and dispatch carries only identity, Decision 5: Reprocessability is bounded by retention mode, and the purge follows the resolve (+9 more)

### Community 506 - "Requirement: Structured Query API"
Cohesion: 0.11
Nodes (17): analytics-query-api, Purpose, Requirement: Query Parameter Validation, Requirement: Structured Query API, Requirement: Tenant-scoped Query Execution, Requirements, Scenario: Database error returns HTTP 502, Scenario: Invalid date format returns 422 (+9 more)

### Community 507 - "Requirements"
Cohesion: 0.11
Nodes (17): analytics-ui, Purpose, Requirement: Ad-Hoc Query Controls, Requirement: Analytics Dashboard Page, Requirement: Dashboard Page Loading State, Requirement: Error State Handling, Requirement: Export Button, Requirements (+9 more)

### Community 508 - "Requirement: Batch extraction"
Cohesion: 0.11
Nodes (18): Requirement: Batch extraction, Scenario: A run degraded by post-processing failure is reported as such, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction persists normalized entities, Scenario: Batch extraction skips already-extracted documents, Scenario: Batch extraction uses version 0 when no model promoted, Scenario: Changing the mode does not reprocess existing results (+10 more)

### Community 509 - "Requirement: Per-Tenant Integration Credentials Are References Only"
Cohesion: 0.11
Nodes (17): Purpose, Requirement: No Hardcoded Secrets in Codebase, Requirement: Per-Tenant Integration Credentials Are References Only, Requirement: Runtime Credential Resolution Failure Is Explicit, Requirement: Test Fixtures Use Isolated Env Injection, Requirements, Scenario: A value in a secret field is rejected by schema, not by heuristic, Scenario: AGENTS.md documents the no-hardcoded-secrets invariant (+9 more)

### Community 510 - "Requirement: User Authentication"
Cohesion: 0.11
Nodes (17): Purpose, Requirement: Tenant Context Middleware, Requirement: Tenant-Scoped User Management, Requirement: User Authentication, Requirements, Scenario: Logout clears the refresh token cookie, Scenario: Request with non-existent tenant slug, Scenario: Request with tenant mismatch between URL and token (+9 more)

### Community 511 - "MODIFIED Requirements"
Cohesion: 0.12
Nodes (16): MODIFIED Requirements, Requirement: Demote model version, Requirement: Get active model version, Requirement: List model versions, Requirement: Promote model version, Scenario: Demote a non-promoted model returns 422, Scenario: Demote the active model via MLflow, Scenario: Get active model from MLflow when one is promoted (+8 more)

### Community 512 - "Requirement: Sidebar Layout"
Cohesion: 0.12
Nodes (16): ADDED Requirements, Requirement: Placeholder Screens, Requirement: Sidebar Layout, Requirement: Topbar Layout, Scenario: active nav item is highlighted, Scenario: badge renders when present, Scenario: dark mode toggle switches theme, Scenario: logout clears session and redirects (+8 more)

### Community 513 - "ADDED Requirements"
Cohesion: 0.12
Nodes (16): ADDED Requirements, Requirement: Confidence Distribution Widget, Requirement: Dashboard Aggregation API, Requirement: Entity Coverage Widget, Requirement: Extraction Volume Over Time Widget, Requirement: Materialized View Refresh on Extraction Event, Requirement: On-Demand Materialized View Refresh, Requirement: Per-Document Entity Counts Widget (+8 more)

### Community 514 - "ADDED Requirements"
Cohesion: 0.12
Nodes (16): ADDED Requirements, Requirement: Accept CoNLL TXT annotation file uploads, Requirement: Accept JSONL annotation file uploads, Requirement: Export endpoint includes imported annotations, Requirement: Store imported annotations in tenant-isolated table, Requirement: Validate file size and content type, Scenario: Export includes both sources, Scenario: Export with entity type filter applies to both sources (+8 more)

### Community 515 - "Requirement: Structured Query API"
Cohesion: 0.12
Nodes (16): analytics-query-api, MODIFIED Requirements, Requirement: Query Parameter Validation, Requirement: Structured Query API, Requirement: Tenant-scoped Query Execution, Scenario: Database error returns HTTP 502, Scenario: Invalid date format returns 422, Scenario: Invalid entity type returns 422 (+8 more)

### Community 516 - "Requirement: Document Upload"
Cohesion: 0.12
Nodes (16): MODIFIED Requirements, Requirement: Async OCR Processing, Requirement: Document Upload, Scenario: DOC text extraction succeeds, Scenario: DOCX text extraction succeeds, Scenario: Image OCR succeeds, Scenario: OCR processing fails, Scenario: PDF text extraction succeeds (+8 more)

### Community 517 - "MODIFIED Requirements"
Cohesion: 0.12
Nodes (16): ADDED Requirements, MODIFIED Requirements, Requirement: Citation enrichment with entity type resolution, Requirement: Citation model with document names and entity type names, Requirement: Conversation creation endpoint, Requirement: RAG chat endpoint, Requirement: SQL query generation and validation, Scenario: Chat response includes citations with document names (+8 more)

### Community 518 - "Decisions"
Cohesion: 0.12
Nodes (16): Context, Currently-In-Force ADRs, Decision 1: Server-Sent Events over a POST request, as a new sibling endpoint, Decision 2: Token sink in `ChatState`, drained by the endpoint, Decision 3: Guardrail source enforcement decided before the first token, Decision 4: Terminal short-circuit paths emit no tokens and go straight to `done`, Decision 5: `done` carries the complete response payload; persistence stays where it is, Decision 6: Gateway proxies the stream without buffering (+8 more)

### Community 519 - "What Changes"
Cohesion: 0.12
Nodes (16): A. Confidence calibration (blocking — everything else depends on it), B. Deterministic repairs (no LLM, no token cost), C. LLM post-processing (new, optional, off by default), Capabilities, D. Provenance, E. Business-user processing mode, Explicitly not changing, F. Evaluation (+8 more)

### Community 520 - "Requirement: Batch extraction"
Cohesion: 0.12
Nodes (16): MODIFIED Requirements, Requirement: Batch extraction, Scenario: A document failure leaves both stores clean and the run continues, Scenario: A freshly provisioned tenant extracts successfully on its first run, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction skips already-extracted documents, Scenario: Batch extraction uses version 0 when no model promoted (+8 more)

### Community 521 - "Decisions"
Cohesion: 0.12
Nodes (16): Context, Currently-In-Force ADRs, Decision 1: Resolve after planning, as a node between `orchestrator` and `retrieval_execution`, Decision 2: Deterministic n-gram mention extraction, not an LLM extraction call, Decision 3: Ambiguity is counted over distinct `document_id`s, Decision 4: Candidate cards assembled from `document_entities`, with a fixed field priority and empty-field omission, Decision 5: Ordinal parsing first, one constrained LLM call as fallback for natural-language selection, Decision 6: Persist conversation state in a tenant-schema table, one row per conversation (+8 more)

### Community 522 - "Decisions"
Cohesion: 0.12
Nodes (16): Context, Currently-In-Force ADRs, Decision 1: Entity type matching is case-insensitive and includes base-model labels, Decision 2: `subject` is always DROP + CREATE; child views use CREATE OR REPLACE, Decision 3: `to_sql_identifier` is total — degenerate input yields `e_unnamed`, collisions get a numeric suffix, Decision 4: Module lives at `src/shared/entity_views.py`, Decision 5: A typed `single` entity projects two columns — typed and text, Decision 6: `MAX()` as the single-value tie-break, `LEFT JOIN` from `documents` (+8 more)

### Community 523 - "Requirement: Wrong-entity-type defect detection"
Cohesion: 0.12
Nodes (16): ADDED Requirements, Requirement: Failed recovery is reported, never laundered into an empty result, Requirement: Structured retrieval reports result completeness, Requirement: Wrong-entity-type defect detection, Scenario: Complete result is reported as complete, Scenario: Completeness reporting does not change returned rows, Scenario: Deadline-abandoned recovery is distinguishable from exhausted attempts, Scenario: Defect feedback names the correct entity type (+8 more)

### Community 524 - "Requirement: Approve training job"
Cohesion: 0.12
Nodes (16): MODIFIED Requirements, Requirement: Approve training job, Requirement: Submit form span preflight is informational only, Requirement: Submit training job, Scenario: Approve a job that is not pending_approval, Scenario: Approve a pending training job with valid hyperparameters, Scenario: Approve as non-system-admin, Scenario: Approve with invalid hyperparameters (+8 more)

### Community 525 - "Requirement: Widget API key management"
Cohesion: 0.12
Nodes (16): Purpose, Requirement: CORS configuration for widget endpoints, Requirement: Hosted widget JS file, Requirement: Widget API key management, Requirement: Widget-specific chat endpoint, Requirements, Scenario: Chat with invalid widget API key, Scenario: Generate widget API key (+8 more)

### Community 526 - "test_chat_api_retrieval_status.py"
Cohesion: 0.16
Nodes (11): Per-capability retrieval outcome for the turn. Additive: a client that ignores…, RetrievalStatusOut, _app(), auth_header(), CannedOrchestrator, _fake_citation(), _patch(), `retrieval_status` on the chat response — verification.md rows 18, 19, 28. The… (+3 more)

### Community 527 - "data_sources/__init__.py"
Cohesion: 0.14
Nodes (23): _require_keys(), Tenant-scoped Azure connection control plane (CAP-2, ADR-011)., ConnectionValidationError, Exception, The finite approved provider catalog for the tenant control plane (CAP-2). Only…, Reject anything outside the two approved providers., Check one provider's non-secret configuration against its closed key set., Check that required reference fields hold references and nothing else. Unknown… (+15 more)

### Community 529 - "ADDED Requirements"
Cohesion: 0.12
Nodes (15): ADDED Requirements, Requirement: Demote model version, Requirement: Get active model version, Requirement: List model versions, Requirement: Promote model version, Scenario: Demote a non-promoted model returns 422, Scenario: Demote the active model, Scenario: Get active model when none is promoted (+7 more)

### Community 530 - "ADDED Requirements"
Cohesion: 0.12
Nodes (15): ADDED Requirements, Requirement: Application Service Port Mapping, Requirement: Service Startup Dependencies, Requirement: Shared Root Dockerfile, Requirement: Single-Command Local Stack Startup, Requirement: Stable Inter-Service Communication via Docker DNS, Scenario: All services built from shared Dockerfile, Scenario: All services start with docker compose up (+7 more)

### Community 531 - "ADDED Requirements"
Cohesion: 0.12
Nodes (15): ADDED Requirements, Requirement: CORS configuration for widget endpoints, Requirement: Hosted widget JS file, Requirement: Widget API key management, Requirement: Widget-specific chat endpoint, Scenario: Chat with invalid widget API key, Scenario: Generate widget API key, Scenario: List widget API keys (+7 more)

### Community 532 - "2026-06-23-sp-06-rag-chatbot/tasks.md"
Cohesion: 0.12
Nodes (15): 10. Widget API Key Management, 11. Widget JS File, 12. Widget Chat Endpoint, 13. Chat UI (Frontend), 14. Gateway Routes & CORS, 15. Verification & Evidence, 1. Infrastructure & Database Setup, 2. Chat API Service Scaffolding (+7 more)

### Community 533 - "Design: Model Registry Promote"
Cohesion: 0.12
Nodes (15): 1. Model Listing Returns Only 1 Version, 2. `_update_job_progress` Crashes on Dict, 3. `model_versions` Status Hardcoded to `completed`, Current behaviour, Current behaviour, Current behaviour, Design: Model Registry Promote, Files Changed (+7 more)

### Community 534 - "ADDED Requirements"
Cohesion: 0.12
Nodes (15): ADDED Requirements, Requirement: Centralized retrieval configuration, Requirement: Citation enrichment executes without error, Requirement: Retriever interface, Requirement: Single chunking implementation, Requirement: Typed retrieval domain model, Scenario: Chunking output is unchanged for existing documents, Scenario: Configuration is overridable via environment variable (+7 more)

### Community 535 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, Currently-In-Force ADRs, Decision 1: Normalize in the worker from the in-memory prediction sequence, Decision 2: Pure-function normalizer, thin persistence layer, Decision 3: Minimum as the confidence aggregation strategy, Decision 4: `normalized_value` = static alias map over a deterministic fallback, Decision 5: Offsets by re-alignment, NULL on failure, Decision 6: Whitelist swap, not dual exposure, in the SQL generator (+7 more)

### Community 536 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, Currently-In-Force ADRs, Decision 1: OpenTelemetry as the sole instrumentation boundary, Decision 2: One shared module, not per-service instrumentation, Decision 3: Context carried in `contextvars`, not function arguments, Decision 4: Redaction as a mandatory logging filter, backed by a test, Decision 5: Users identified by a keyed hash, tenants by UUID, Decision 6: No `tenant_id` metric label in this change (+7 more)

### Community 537 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, Currently-In-Force ADRs, Decision 1: Promote `resolve_generated_tables` into a richer `resolve_query_surface`, keeping the old function as a wrapper, Decision 2: Resolve the surface by schema, not by threading `tenant_id` through the tool boundary, Decision 3: Rebuild the grounding block around relations; keep `document_entities` as the value oracle, Decision 4: Resolve the document-scope column map from the surface, and make an unscopeable statement a defect, Decision 5: Replace the defect ladder in place; keep the outcome set and the zero-rows policy, Decision 6: Add column validation, permissive on unattributable references (+7 more)

### Community 538 - "Decisions"
Cohesion: 0.12
Nodes (15): Context, Currently-In-Force ADRs, Decision 1: Tools wrap existing retrievers; they contain no retrieval logic, Decision 2: Tenant scope travels in `ToolContext`, never in `args`, Decision 3: Retrieval configuration becomes an explicit override object resolved ahead of `settings`, Decision 4: Extract the SQL entity path out of `RAGOrchestrator` into a shared service, Decision 5: Golden set is a synthetic, committed corpus with precomputed embeddings, Decision 6: Metrics implemented in-repo, no eval framework dependency (+7 more)

### Community 539 - "Requirement: Post-migration schema verification"
Cohesion: 0.12
Nodes (15): Dev Database Reset, Purpose, Requirement: Documented clean-rebuild procedure for the local stack, Requirement: Drift blocks stack startup, Requirement: Post-migration schema verification, Requirements, Scenario: A clean database starts the stack normally, Scenario: A clean rebuild passes verification (+7 more)

### Community 540 - "Requirements"
Cohesion: 0.12
Nodes (15): MLflow Infrastructure, Purpose, Requirement: Docker Compose MLflow service, Requirement: K8s deployment manifests, Requirement: MLflow environment configuration, Requirement: MLflow Tracking Server deployment, Requirement: Tenant isolation via naming convention, Requirements (+7 more)

### Community 541 - "Requirement: Approve training job"
Cohesion: 0.12
Nodes (15): Purpose, Requirement: Approve training job, Requirement: Reject training job, Requirements, Scenario: Approve a job that is not pending_approval, Scenario: Approve a pending training job, Scenario: Approve a pending training job with valid hyperparameters, Scenario: Approve as non-system-admin (+7 more)

### Community 542 - "test_tenant_store_provisioning.py"
Cohesion: 0.18
Nodes (14): _cleanup(), _make_provisioning_tenant(), provisioning_tenant(), fixture, Verification for `provision_tenant_data_plane` against `tenant-residency-store-…, Scenario #14: Provisioning failure is safe and retryable. Schema creation is…, Scenario #15: Provisioning refuses a non-empty foreign schema., Scenario #16: No platform schema is created for a residency tenant. (+6 more)

### Community 543 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 544 - "ADDED Requirements"
Cohesion: 0.13
Nodes (14): ADDED Requirements, Requirement: Ad-Hoc Query Controls, Requirement: Analytics Dashboard Page, Requirement: Dashboard Page Loading State, Requirement: Error State Handling, Requirement: Export Button, Scenario: API error shows error banner, Scenario: CSV export downloads file (+6 more)

### Community 545 - "ADDED Requirements"
Cohesion: 0.13
Nodes (14): ADDED Requirements, Requirement: Tenant Admin User Creation, Requirement: Tenant Admin User Deactivation, Requirement: Tenant Admin User List, Requirement: Tenant Admin User Role Update, Scenario: Deactivation is cancelled, Scenario: Duplicate email rejected on creation, Scenario: Non-tenant-admin cannot access users page (+6 more)

### Community 546 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: Rebuild from empty rather than repair in place, Decision 2: Verify schema by comparing the live database against a freshly migrated reference, Decision 3: Drift hard-fails `db-init`, Decision 4: Fix enumeration by intersecting tenants with `pg_namespace`, Decision 5: Distinguish partial aggregates from complete ones, Decision 6: Reconcile tenant schemas from `tenant_template` in one migration (+6 more)

### Community 547 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: One loop node, not a multi-node LangGraph cycle, Decision 2: The loop terminates on the first of four conditions, and budget exhaustion is a normal outcome, Decision 3: The loop writes the existing state keys; nothing downstream learns it exists, Decision 4: Tenant scope stays in `ToolContext`; tool arguments are always validated and never trusted, Decision 5: Malformed tool calls get one corrective retry, then the loop degrades, Decision 6: The complexity guardrail routes into the loop instead of declining, only when the flag is on (+6 more)

### Community 548 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: Readiness is measured per active entity type, at 200 each, Decision 2: Overall readiness is the mean of per-type progress, each capped at 100%, Decision 3: `continueWork` is a new optional top-level payload field, not a `StatItem`, Decision 4: Task selection precedence, with an ordering fallback, Decision 5: Three status vocabularies are normalised at the query boundary, Decision 6: `pending` is added to the task state machine (+6 more)

### Community 549 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.13
Nodes (14): MODIFIED Requirements, Requirement: Dashboard Data Shape, Requirement: Dashboard Summary Endpoint, Scenario: annotator data shape, Scenario: annotator summary returns real task data and a live progress bar, Scenario: business_user data shape, Scenario: business_user summary returns real extraction data, Scenario: partial service failure degrades gracefully (+6 more)

### Community 550 - "Requirement: Persist Audit Events"
Cohesion: 0.13
Nodes (14): ADDED Requirements, Requirement: List Audit Events via API, Requirement: Persist Audit Events, Requirement: Render Audit Log Page, Scenario: Audit event recorded on entity type update, Scenario: Audit event recorded on model promotion, Scenario: Audit event recorded on tenant deactivation, Scenario: Audit event recorded on training job approval (+6 more)

### Community 551 - "Requirement: RAG chat endpoint"
Cohesion: 0.13
Nodes (14): MODIFIED Requirements, Requirement: Guardrail — source citation enforcement, Requirement: RAG chat endpoint, Scenario: Ambiguous reference returns a clarification response, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with NER query, Scenario: Chat with simple entity count query (+6 more)

### Community 552 - "Requirement: Fixed topology with no agentic behaviour"
Cohesion: 0.13
Nodes (14): ADDED Requirements, MODIFIED Requirements, Requirement: Fixed topology with no agentic behaviour, Requirement: Resolution outcome carried in graph state, Scenario: Blocked question short-circuits to END, Scenario: Clarification short-circuits to END, Scenario: Compiled graph remains acyclic with the flag on, Scenario: Downstream nodes are unchanged (+6 more)

### Community 553 - "What Changes"
Cohesion: 0.13
Nodes (14): A. Security (blocking, lands first), B. Error and status contracts, C. Correctness and recovery, Capabilities, D. Retrieval and context assembly, E. Orchestration and evaluation, Explicitly not changing, Harden chat pipeline correctness (+6 more)

### Community 554 - "Requirement: Multi-subject resolution scopes to every matched document"
Cohesion: 0.13
Nodes (14): ADDED Requirements, entity-resolution, Requirement: Multi-subject resolution scopes to every matched document, Requirement: Plan rewriting preserves every resolved document, Scenario: Ambiguity within one mention still requests clarification, Scenario: Anaphoric follow-up inherits the full bound set, Scenario: One named subject resolves and another does not, Scenario: Post-execution row filter respects the full set (+6 more)

### Community 555 - "Verification Plan"
Cohesion: 0.13
Nodes (14): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+6 more)

### Community 556 - "Requirement: Dataset-to-model lineage diagram"
Cohesion: 0.13
Nodes (14): MODIFIED Requirements, Requirement: Dataset-to-model lineage diagram, Requirement: Detail panel header shows the full job id and creation timestamp, Requirement: Job list card content, Scenario: Completed job card shows F1 score, Scenario: Detail header falls back to the full job id for legacy jobs, Scenario: Detail header shows the run name and a creation date, Scenario: Legacy job card falls back to job id when run_name is absent (+6 more)

### Community 557 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: Batch orchestration lives in the component; `useUpload` keeps its single-file contract, Decision 2: Sequential upload, concurrency 1, Decision 3: Per-file validation up front, then upload only the valid subset, Decision 4: Batch cap of 20 rejects the whole selection, Decision 5: Per-file result list as the terminal state, replacing the single success flag, Decision 6: Invalidate the documents query per successful file (+6 more)

### Community 558 - "Verification Plan"
Cohesion: 0.13
Nodes (14): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, A note on `tenant_id` in the evidence above, AI Output Review (+6 more)

### Community 559 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: Guardrail is an LLM domain classifier behind deterministic short-circuits, Decision 2: `semantic_retrieval` takes a structured `scope` object rather than separate tools, Decision 3: Single-shot plan, then concurrent execution, Decision 4: Orchestrator planning lives in `src/shared/retrieval/orchestrator.py`, node wiring stays in `src/chat_api`, Decision 5: Graph topology and state, Decision 6: Delete the legacy path and both flags outright (+6 more)

### Community 560 - "Requirement: Single semantic retrieval capability with internal scope"
Cohesion: 0.13
Nodes (14): ADDED Requirements, REMOVED Requirements, Requirement: Document retrieval tools, Requirement: Entity retrieval tool, Requirement: Exactly two retrieval capabilities are exposed, Requirement: Single semantic retrieval capability with internal scope, Scenario: Capability descriptions state retrieval intent, Scenario: Document scope accepts multiple documents (+6 more)

### Community 561 - "Requirement: SQL query generation and validation"
Cohesion: 0.13
Nodes (14): MODIFIED Requirements, Requirement: SQL query generation and validation, Scenario: A child table retained from a `multi` era is excluded from the query surface, Scenario: A generated entity table is both granted and whitelisted, Scenario: A grant for a table that does not yet exist is skipped safely, Scenario: A table that leaves the query surface loses its grant, Scenario: An inactive definition's table is excluded from the query surface, Scenario: Grants, whitelist, and generation context resolve from one source (+6 more)

### Community 562 - "Decisions"
Cohesion: 0.13
Nodes (14): Context, Currently-In-Force ADRs, Decision 1: Semantic normalization is a separate pass, not an extension of `canonicalize()`, Decision 2: Value kinds are declared on `entity_definitions`, not in a code registry, Decision 3: Typed values go in sparse typed columns on `document_entities`, not JSONB and not a side table, Decision 4: One parser per kind behind a registry, dispatched by declared kind, Decision 5: Unparseable is NULL, never an error, Decision 6: Backfill derives typed values from stored text, without re-running inference (+6 more)

### Community 563 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.13
Nodes (14): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Requirement: DashboardData TypeScript Type, Scenario: A partial aggregate is not reported as a complete total, Scenario: ActivityRow icon and time fields are required strings, Scenario: null values are assignable, Scenario: one tenant schema failure does not blank out other tenants' stats, Scenario: system_admin summary returns role-specific data (+6 more)

### Community 564 - "Requirement: RAG chat endpoint"
Cohesion: 0.13
Nodes (15): Requirement: RAG chat endpoint, Scenario: Ambiguous reference returns a clarification response, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with NER query, Scenario: Chat with simple entity count query, Scenario: Chat without authentication, Scenario: Clarification turn is persisted to the conversation (+7 more)

### Community 565 - "Requirement: Orb-burst overlay on successful sign-in"
Cohesion: 0.13
Nodes (14): Purpose, Requirement: Dashboard fade-in on entry, Requirement: No regression to login page behaviour, Requirement: Orb-burst overlay on successful sign-in, Requirements, Scenario: Dashboard fades in after burst, Scenario: Error state remains functional, Scenario: Fade-in keyframe defined in global CSS (+6 more)

### Community 566 - "Requirement: Model warmup on promotion"
Cohesion: 0.13
Nodes (14): Model Warmup, Purpose, Requirement: Model warmup on promotion, Requirement: Standalone warmup API (optional convenience), Requirement: Warmup endpoint in model-serving, Requirements, Scenario: A slow cold load that exceeds the client timeout still completes in the background, Scenario: First extraction after warmup uses cached model (+6 more)

### Community 567 - "Requirement: Task Assignment Form"
Cohesion: 0.13
Nodes (14): Purpose, Requirement: Task Assignment Form, Requirements, Scenario: Annotator dropdown lists only annotator-role users, Scenario: Assign button disabled until both fields are selected, Scenario: Assign Task button hidden for annotator, Scenario: Assign Task button visible for tenant admin, Scenario: Cancel collapses form without submitting (+6 more)

### Community 568 - "2026-06-10-sm-03-annotation-workspace/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: Standalone Microservice (not gateway extension), Decision 2: Mock Pre-labeling (no ML deps for MVP), Decision 3: HuggingFace Dataset Format for Export, Decision 4: Manual Annotation Task Creation (no auto-assignment), Decision 5: Document Locking Per Annotator, Decision 6: Pre-labeling Stores Candidate Spans Separately (+5 more)

### Community 569 - "2026-06-11-sm-04-training-pipeline/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: Standalone Microservice, Decision 2: Redis Broker for MVP (Celery), Decision 3: CPU Training for Local Dev (GPU Optional), Decision 4: Polling-Based Job Status (no WebSocket), Decision 5: HuggingFace Dataset Loaded from Annotation Service Export, Decision 6: Database Tables in tenant_template Schema (+5 more)

### Community 570 - "ADDED Requirements"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Docker Compose MLflow service, Requirement: K8s deployment manifests, Requirement: MLflow environment configuration, Requirement: MLflow Tracking Server deployment, Requirement: Tenant isolation via naming convention, Scenario: MLflow server deploys to K8s, Scenario: MLflow server health check (+5 more)

### Community 571 - "ADDED Requirements"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Internal inference endpoint, Requirement: Model cache, Requirement: Model warmup on promotion, Requirement: Version pinning, Scenario: Cache hit on subsequent request, Scenario: Inference for tenant with no loaded model, Scenario: Inference returns predictions (+5 more)

### Community 572 - "2026-06-16-portal-auth/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: Access token in `useRef`, user object in `useState`, Decision 2: Concurrent-safe refresh via module-level singleton, Decision 3: Backend `refresh` reads from cookie, not body, Decision 4: `Secure` cookie flag is environment-conditional, Decision 5: On-mount silent refresh, immediate child rendering, Decision 6: `authFetch` routes URLs by service prefix (+5 more)

### Community 573 - "2026-06-16-portal-foundation/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: SPA-style client components — no Next.js API routes for data, Decision 2: Tailwind CSS with CSS custom-property tokens, not plain Tailwind theme values, Decision 3: Dark-mode strategy — `class` on `<html>`, persisted to localStorage, Decision 4: Font loading via `next/font/google`, not CDN link tags, Decision 5: Primitive components co-located in `src/portal/src/components/ui/`, not a separate package, Decision 6: `authFetch` stub — interface only in this change (+5 more)

### Community 574 - "ADDED Requirements"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Colour palette tokens, Requirement: CSS custom-property token declarations, Requirement: Radius and shadow tokens, Requirement: Tailwind config token references, Requirement: Typography tokens, Scenario: All status tokens have dark overrides, Scenario: Card shadow token used on dashboard stat cards (+5 more)

### Community 575 - "Requirement: Query extracted entities"
Cohesion: 0.14
Nodes (13): MODIFIED Requirements, Requirement: Batch extraction, Requirement: Query extracted entities, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction skips already-extracted documents, Scenario: Query entities as annotator, Scenario: Query entities by confidence threshold (+5 more)

### Community 576 - "2026-06-22-annotation-ui-fixes/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: Drag-to-annotate interaction model, Decision 2: BIO tag storage — column on spans table, Decision 3: Fullscreen via browser Fullscreen API, Decision 4: Sticky navbar — height chain fix, Decision 5: Task display name — frontend queue index, Decision 6: Focus mode as single toggle (+5 more)

### Community 577 - "ADDED Requirements"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Chat screen route and access, Requirement: Conversation sidebar, Requirement: Message thread display, Requirement: Role-gated chat access, Scenario: Annotator accesses chat screen, Scenario: Business user accesses chat, Scenario: Clicking conversation loads messages (+5 more)

### Community 578 - "Requirement: Structured Query API"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Query Parameter Validation, Requirement: Structured Query API, Requirement: Tenant-scoped Query Execution, Scenario: Invalid date format returns 422, Scenario: Invalid entity type returns 422, Scenario: Query filters by tenant schema, Scenario: Query returns empty results for non-matching filters (+5 more)

### Community 579 - "2026-06-29-sp-10-model-registry/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: One spec (`model-registry-screen`) covering page + hooks + components, Decision 2: Two-column list+detail layout matching training-jobs pattern, Decision 3: Active model fetched as separate query, Decision 4: Promote/demote/warmup buttons gated by role client-side, Decision 5: Per-entity metrics in collapsible section, Decision 6: Always show base model (version 0) as a permanent list entry (+5 more)

### Community 580 - "2026-06-30-fix-dashboard-queries/tasks.md"
Cohesion: 0.14
Nodes (13): 1. Schema Reconciliation Migration, 2. Route and Handler Wiring, 3. Tenant Admin Queries (`_tenant_admin_data`), 4. Annotator Queries (`_annotator_data`), 5. Business User Queries (`_business_user_data`), 6. Tests, 7. Demo Seed Data, 8. Verification & Evidence (+5 more)

### Community 581 - "Requirement: Post-migration schema verification"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Documented clean-rebuild procedure for the local stack, Requirement: Drift blocks stack startup, Requirement: Post-migration schema verification, Scenario: A clean database starts the stack normally, Scenario: A clean rebuild passes verification, Scenario: A missing public column is detected, Scenario: A missing tenant_template table is detected (+5 more)

### Community 582 - "Requirement: Existing tenant schemas are reconciled to the current template shape"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: Existing tenant schemas are reconciled to the current template shape, Requirement: Per-tenant-schema DDL tolerates tenant schemas missing a table, Requirement: Tenant provisioning clones the template atomically, Scenario: A failed table clone rolls back the whole tenant, Scenario: A provisioned tenant has the full template table set, Scenario: A tenant schema missing a whole table gains it from the template, Scenario: A tenant schema missing annotation_tasks does not abort migration 022 (+5 more)

### Community 583 - "Requirement: Retriever interface"
Cohesion: 0.14
Nodes (13): MODIFIED Requirements, Requirement: Centralized retrieval configuration, Requirement: Retriever interface, Scenario: Configuration is overridable via environment variable, Scenario: Default configuration matches prior hardcoded behavior, Scenario: DenseRetriever uses the hnsw index, Scenario: HybridRetriever fuses dense and sparse results via RRF, Scenario: HybridRetriever includes dense-only matches when sparse search returns nothing (+5 more)

### Community 584 - "2026-09-08-chat-conversation-and-citations/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: New dedicated `POST /api/v1/chat/conversations` endpoint, Decision 2: Unified `Citation` model, with `Source` retained for widget backwards compatibility, Decision 3: Citation enrichment via batch queries in the orchestrator, Decision 4: Always render `ChatInput` when `activeConvId` is set, Decision 5: SQL prompt must use correct table alias (`documents AS d`), Decision 6: Visible error toast on new conversation API failure (+5 more)

### Community 585 - "Requirement: Citation card display"
Cohesion: 0.14
Nodes (13): ADDED Requirements, MODIFIED Requirements, Requirement: Citation card display, Requirement: Conversation sidebar, Requirement: Message thread display, Scenario: Assistant message shows citation cards, Scenario: Citation card expands to show context, Scenario: Citation card without context snippet (+5 more)

### Community 586 - "2026-09-08-document-content-hash-and-batch-select-all/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: SHA-256 hex digest over raw uploaded bytes, Decision 2: Identify and link, never reject or merge, Decision 3: Duplicate lookup is tenant-schema scoped and excludes soft-deleted rows, Decision 4: Index the existing column rather than adding a new one, Decision 5: "Select all" is derived state, not a third selection mode, Decision 6: No server-side change to `POST /api/v1/extract-batch` (+5 more)

### Community 587 - "Requirement: SQL query generation and validation"
Cohesion: 0.14
Nodes (13): MODIFIED Requirements, Requirement: SQL query generation and validation, Scenario: A child table retained from a `multi` era is excluded from the query surface, Scenario: A generated entity table is both granted and whitelisted, Scenario: A grant for a table that does not yet exist is skipped safely, Scenario: A table that leaves the query surface loses its grant, Scenario: An inactive definition's table is excluded from the query surface, Scenario: Grants and whitelist resolve from one source (+5 more)

### Community 588 - "Requirement: Base Model (Version 0) Entry"
Cohesion: 0.14
Nodes (13): MODIFIED Requirements, Requirement: Base Model (Version 0) Entry, Requirement: Model Version Card, Scenario: Base model card hidden even when it is the tenant's only active model, Scenario: Base model card hidden for business_user and annotator, Scenario: Base model card hidden for tenant_admin, Scenario: Base model card visible to system_admin alongside fine-tuned models, Scenario: Base model card visible to system_admin with no fine-tuned models trained yet (+5 more)

### Community 589 - "2026-09-08-response-feedback-rating/design.md"
Cohesion: 0.14
Nodes (13): Context, Currently-In-Force ADRs, Decision 1: Separate `chat_message_feedback` table, not a column on `chat_messages`, Decision 2: Immutability enforced by a DB unique constraint + explicit conflict response, Decision 3: Feedback owned by chat_api, aggregation exposed by gateway, Decision 4: Response Quality is a dedicated interpreted card, not a generic row list, and never touches the Active model panel, Decision 5: Explicit `answer_kind` discriminator gates feedback eligibility, Decision 6: Reuse the existing `model_version` identifier instead of inventing a new one (+5 more)

### Community 590 - "Requirement: Dashboard Data Shape"
Cohesion: 0.14
Nodes (13): ADDED Requirements, MODIFIED Requirements, Requirement: Dashboard Data Shape, Requirement: Response Quality Card, Scenario: annotator data shape, Scenario: business_user data shape, Scenario: Healthy status renders a positive recommendation, Scenario: Monitor status renders a watch-and-gather-more-feedback recommendation (+5 more)

### Community 591 - "Requirement: Auth Context Provider"
Cohesion: 0.14
Nodes (13): Auth Context, Purpose, Requirement: Auth Context Access Token Exposure, Requirement: Auth Context Provider, Requirements, Scenario: authFetch reads token synchronously without re-render, Scenario: authFetch updates token after silent refresh, Scenario: Logout clears cached query data (+5 more)

### Community 592 - "Requirement: Auth Fetch 401 Silent Refresh"
Cohesion: 0.14
Nodes (13): Auth Fetch, Purpose, Requirement: Auth Fetch 401 Silent Refresh, Requirement: Auth Fetch Interceptor, Requirements, Scenario: 401 triggers one silent refresh and retries, Scenario: authFetch injects Bearer token on authenticated requests, Scenario: authFetch passes absolute URLs through unchanged (+5 more)

### Community 593 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 594 - "2026-06-08-sm-01-identity-tenant-entity-config/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Tenant Identity Resolution via URL Path Prefix, Decision 2: Synchronous Tenant Provisioning, Decision 3: JWT with Namespaced Custom Claims, Decision 4: Entity Type Configuration with Label Mapping, Decision 5: Admin Console as a Separate SPA Route, Decisions (+4 more)

### Community 595 - "ADDED Requirements"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Tenant Context Middleware, Requirement: Tenant-Scoped User Management, Requirement: User Authentication, Scenario: Request with non-existent tenant slug, Scenario: Request with tenant mismatch between URL and token, Scenario: Request with valid tenant and matching token, Scenario: Tenant Admin attempts cross-tenant user creation (+4 more)

### Community 596 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 597 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 598 - "2026-06-09-sm-02-document-ingestion/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Standalone Microservice vs Gateway Extension, Decision 2: Async OCR via Message Broker vs Inline, Decision 3: Blob Storage Provider, Decision 4: PDF Text Extraction Library, Decision 5: Message Queue Pattern, Decisions (+4 more)

### Community 599 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 600 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 601 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 602 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 603 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 604 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 605 - "2026-06-15-sm-05-extraction-engine/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Two Microservices (model-serving + extraction-service), Decision 2: ONNX Runtime for Inference (CPU), Decision 3: In-Memory Model Cache with LRU Eviction, Decision 4: Redis Broker for Batch Extraction (Celery), Decision 5: Idempotent Batch Extraction, Decisions (+4 more)

### Community 606 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 607 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 608 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 609 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 610 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 611 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 612 - "Requirement: Orb-burst overlay on successful sign-in"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Dashboard fade-in on entry, Requirement: No regression to login page behaviour, Requirement: Orb-burst overlay on successful sign-in, Scenario: Dashboard fades in after burst, Scenario: Error state remains functional, Scenario: Fade-in keyframe defined in global CSS, Scenario: Failed login shows no burst (+4 more)

### Community 613 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 614 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 615 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 616 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 617 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 618 - "2026-06-17-portal-dashboard/tasks.md"
Cohesion: 0.15
Nodes (12): 10. App-Shell Delta: Remove system_admin Redirect, 11. TypeScript & Build Verification, 12. Verification & Evidence, 1. Setup: Install TanStack Query, 2. Types: DashboardData Shape, 3. Gateway: Dashboard Summary Endpoint, 4. Hook: useDashboardData, 5. Components: Stat Card (+4 more)

### Community 619 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 620 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 621 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 622 - "Requirement: Environment Configuration Loading"
Cohesion: 0.15
Nodes (12): MODIFIED Requirements, Requirement: docker-compose Uses Environment Interpolation for Secrets, Requirement: Environment Configuration Loading, Requirement: Environment Variable Documentation, Scenario: docker-compose resolves NER_JWT_SECRET from .env, Scenario: docker-compose.yml contains no hardcoded secret literals, Scenario: .env.example includes docker-compose variables, Scenario: .env.example marks secret fields as required (+4 more)

### Community 623 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 624 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 625 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 626 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 627 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 628 - "2026-06-19-sidebar-action-menu/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Menu positioning — upward, absolutely positioned, Decision 2: Fade transition via CSS opacity, Decision 3: Trigger icon — vertical ellipsis `⋮`, Decision 4: Click-outside detection via `mousedown` listener, Decision 5: Settings label unified to "Settings" for all roles, Decisions (+4 more)

### Community 629 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 630 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 631 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 632 - "2026-06-22-sp-05-annotation-workspace/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Span state managed by `useReducer`, not TanStack Query cache, Decision 2: Char-offset ↔ token-index conversion via cumulative-offset map, Decision 3: Escape key disarms via a global `keydown` listener on the annotation page, Decision 4: Component directory structure under `src/portal/src/components/annotation/`, Decision 5: Optimistic highlight via a transient `optimistic` flag in the reducer, Decisions (+4 more)

### Community 633 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 634 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 635 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 636 - "2026-06-23-sp-06-rag-chatbot/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Standalone Chat API Microservice, Decision 2: Direct RAG Pipeline (No LangChain/LlamaIndex), Decision 3: SQL Validation Layer with Read-Only Transactions, Decision 4: Pre-Computed Document Chunks at Upload Time, Decision 5: Widget API Keys in Public Schema, Decisions (+4 more)

### Community 637 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 638 - "Requirement: RAG chat endpoint"
Cohesion: 0.15
Nodes (12): MODIFIED Requirements, Requirement: Conversation CRUD, Requirement: RAG chat endpoint, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with NER query, Scenario: Chat with simple entity count query, Scenario: Chat without authentication (+4 more)

### Community 639 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 640 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 641 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 642 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 643 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 644 - "2026-06-25-annotation-mockup-alignment/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Filename comes from the annotation-task API response (no separate document fetch), Decision 2: Span count in task queue meta comes from the annotation-task API response, Decision 3: SpanInspector and SuggestionPanel move to the right entity panel (3-pane), Decision 4: Focus-mode inspector uses condensed single-line header, Decision 5: No AnnotationTask type change for `filename` — update gateway response and frontend type, Decisions (+4 more)

### Community 645 - "2026-06-25-annotation-mockup-alignment/tasks.md"
Cohesion: 0.15
Nodes (12): 10. Focus Mode Span Inspector (Condensed Header), 11. Tests: Update Affected Test Files, 12. Verification & Evidence, 1. Backend: Annotation Task List API, 2. Frontend: TypeScript Types, 3. Task Queue Component, 4. Annotation Toolbar, 5. Layout and Navigation (Fullscreen Removal) (+4 more)

### Community 646 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 647 - "2026-06-25-app-shell-exact-mockup/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Remove glass effect; use solid surface tokens, Decision 2: Chevron boxed container as a styled `<span>`, not an icon component, Decision 3: Role-switcher container as a single `<div>` pill wrapping all chips, Decision 4: `fadeUp` keyframe in `globals.css`; applied at page root level, Decision 5: Widget Keys screen — read-only stub, no backend dependency, Decisions (+4 more)

### Community 648 - "2026-06-25-app-shell-exact-mockup/tasks.md"
Cohesion: 0.15
Nodes (12): 10. Page Enter Animations, 11. Widget Keys Screen, 12. Verification & Evidence, 1. Animation Foundation, 2. Sidebar — Background and Logo, 3. Sidebar — Tenant Pill, 4. Sidebar — User Strip Trigger, 5. Sidebar — Chevron Framed Box (+4 more)

### Community 649 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 650 - "2026-06-25-app-shell-v2/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Chevron rotation via CSS `transform` on a single element, Decision 2: Fixed-overlay backdrop for outside-close, Decision 3: `menuPop` keyframe in global CSS, Decision 4: Role-driven hero variant via a `heroVariant` helper, Decision 5: `AS` label is a hardcoded string in demo mode, Decisions (+4 more)

### Community 651 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 652 - "2026-06-25-fix-entity-types-api-alignment/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Adopt tenant-scoped URL prefix, remove old flat prefix entirely, Decision 2: Look up entity types by `name`, not UUID, Decision 3: PATCH for is_active toggle, not PUT, Decision 4: Parse JSON columns in _row_to_dict, Decision 5: Flatten create/update response shape, Decisions (+4 more)

### Community 653 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 654 - "2026-06-25-sp05-annotation-workspace/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: View-mode toggle is a radio button group, not a single toggle, Decision 2: Task status managed via inline toolbar status group, not a dedicated "Mark Complete" button, Decision 3: Focus mode floating palette is a bottom-center fixed strip, not a right-side panel, Decision 4: Component decomposition, Decision 5: Task display name uses document filename, not "Task N" ordinal, Decisions (+4 more)

### Community 655 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 656 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 657 - "2026-06-25-sp-08-documents/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Component Architecture, Decision 2: Upload via XMLHttpRequest for Progress, Decision 3: TanStack Query with Conditional Polling, Decision 4: Pagination via Offset-Based Controls, Decision 5: File Validation Order, Decisions (+4 more)

### Community 658 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 659 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 660 - "Requirement: Task Assignment Form"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Task Assignment Form, Scenario: Annotator dropdown lists only annotator-role users, Scenario: Assign button disabled until both fields are selected, Scenario: Assign Task button hidden for annotator, Scenario: Assign Task button visible for tenant admin, Scenario: Cancel collapses form without submitting, Scenario: Clicking Assign Task button expands the inline form (+4 more)

### Community 661 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 662 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 663 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 664 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 665 - "2026-07-01-annotation-file-upload/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Store imported annotations in a new tenant-scoped table, not the `spans` table, Decision 2: Merge imported annotations into the export endpoint, Decision 3: Token-based storage over char-based storage, Decision 4: Accept both JSONL and CoNLL TXT formats, Decision 5: Validate entity types at import time, Decisions (+4 more)

### Community 666 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 667 - "2026-07-01-portal-extraction-page/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Tab state in component state, not URL, Decision 2: One page component, sub-components per tab, Decision 3: Custom hooks for each data concern, Decision 4: Batch Runs layout mirrors training-jobs split panel, Decision 5: Entity review uses filter pills, not tabs, Decisions (+4 more)

### Community 668 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 669 - "Requirement: List extraction runs"
Cohesion: 0.15
Nodes (12): ADDED Requirements, MODIFIED Requirements, Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure, Requirement: List extraction runs, Scenario: List batch extraction runs for a tenant, Scenario: List entities as non-admin business user, Scenario: List is scoped to the requesting tenant, Scenario: List returns empty array when no runs exist (+4 more)

### Community 670 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 671 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 672 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 673 - "2026-07-07-add-annotation-import-button/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Pre-parse client-side for preview, backend validates on import, Decision 2: Slide-over panels for preview and result, Decision 3: Modify the backend import endpoint response, not its contract, Decision 4: Client-side parser in pure TypeScript, Decision 5: Upload via authFetch with XMLHttpRequest fallback for progress, Decisions (+4 more)

### Community 674 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 675 - "ADDED Requirements"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Purpose, query-error-feedback, Requirement: Query Error Banner, Requirement: Query Loading State, Requirement: Query retry on error, Scenario: Loading state clears on success or failure, Scenario: Loading state shown during query (+4 more)

### Community 676 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 677 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.15
Nodes (12): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Requirement: DashboardData TypeScript Type, Scenario: annotator summary returns task data, Scenario: business_user summary returns extraction data, Scenario: null values are assignable, Scenario: one tenant schema failure does not blank out other tenants' stats, Scenario: system_admin summary returns role-specific data (+4 more)

### Community 678 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 679 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 680 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 681 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 682 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 683 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 684 - "2026-07-13-redesign-training-jobs-ui/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Lineage diagram is a new reusable primitive, not a training-jobs-local component, Decision 2: Job-status color/pill logic stays centralized in the existing `Badge` component, Decision 3: `JobTimeline` reorientation is a rewrite, not a CSS-only flip, Decision 4: Lineage's DATASET box is a static/decorative label, not a per-job field, Decision 5: Metrics keys are `eval_*`-prefixed, matching what the training worker actually persists, Decisions (+4 more)

### Community 685 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 686 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 687 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 688 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 689 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 690 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.15
Nodes (12): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Scenario: A partial aggregate is not reported as a complete total, Scenario: annotator summary returns task data, Scenario: business_user summary returns extraction data, Scenario: one tenant schema failure does not blank out other tenants' stats, Scenario: system_admin summary returns role-specific data, Scenario: tenant_admin summary returns pipeline data (+4 more)

### Community 691 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 692 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 693 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 694 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 695 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 696 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 697 - "2026-09-08-annotator-dashboard-cards-and-per-entity-readiness/tasks.md"
Cohesion: 0.15
Nodes (12): 0. Task state machine (blocks the Start action), 10. Test migration, 11. Verification & Evidence, 1. Pre-flight data checks, 2. Threshold semantics (backend), 3. Annotator stat set (backend), 4. Placeholder sub-label removal (backend, all roles), 5. Portal types and cards (+4 more)

### Community 698 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 699 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 700 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 701 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 702 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 703 - "Requirement: Batch Runs Tab — Batch Extraction Management"
Cohesion: 0.15
Nodes (12): MODIFIED Requirements, Requirement: Batch Runs Tab — Batch Extraction Management, Scenario: Already-extracted documents are disabled in the modal, Scenario: Batch Runs tab lists existing runs, Scenario: Canceling the modal sends no request, Scenario: Clicking "New batch run" opens the document-selection modal, Scenario: Confirm is disabled with no selection, Scenario: In-progress runs poll for status updates (+4 more)

### Community 704 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 705 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 706 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 707 - "Requirement: Rename conversation endpoint"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Automatic conversation title generation, Requirement: Rename conversation endpoint, Scenario: Empty-content first message falls back to placeholder title, Scenario: Owner renames their conversation, Scenario: Renaming another user's conversation returns 404, Scenario: Renaming requires authentication, Scenario: Renaming with an empty title is rejected (+4 more)

### Community 708 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 709 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 710 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 711 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 712 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 713 - "Requirement: Reranking retriever composition"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Reranker interface, Requirement: Reranking configuration, Requirement: Reranking retriever composition, Scenario: CrossEncoderReranker reorders results by cross-encoder score, Scenario: CrossEncoderReranker returns None when the service is unavailable, Scenario: Reranking can be disabled via environment variable, Scenario: Reranking defaults are applied when no environment overrides are set (+4 more)

### Community 714 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 715 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 716 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 717 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 718 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 719 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 720 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 721 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 722 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 723 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 724 - "2026-09-08-model-registry-tenant-scoping-run-naming/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Assign `run_number` at training-job submission time, reuse it at model-version creation, Decision 2: Run number is a per-tenant monotonic counter that is never reused, even on cancel/reject/fail, Decision 3: Display name is computed as `run-{run_number:03d}-{created_at:%Y%m%d}`, not stored as a string column, Decision 4: Base model keeps a static label with no run number; frontend gates rendering by `version_number === 0` and role, Decision 5: Extraction confirmation dialog checks `GET /api/v1/models/active` client-side before submitting the run, Decisions (+4 more)

### Community 725 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 726 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 727 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 728 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 729 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 730 - "REMOVED Requirements"
Cohesion: 0.15
Nodes (12): REMOVED Requirements, Requirement: Bounded agentic retrieval loop, Requirement: Evidence accumulation into existing state keys, Requirement: Feature flag and flag-off equivalence, Requirement: Iteration, tool-call, and wall-clock budgets, Requirement: Loop failure falls back to one-shot retrieval, Requirement: Loop is measured against the one-shot configuration, Requirement: Malformed tool calls get one corrective retry, then the loop degrades (+4 more)

### Community 731 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 732 - "2026-09-08-redesign-system-admin-dashboard/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Platform Activity feed reads `public.audit_events` directly, not through `AuditService`, Decision 2: Platform Activity is a generic "most recent audit_events" feed — the friendly-title map is an implementation convenience, not part of the contract, Decision 3: The fourth stat card is "Training Jobs Running," not a model-deployment count, Decision 4: Health checks run concurrently with a short per-service timeout; overall status is a deterministic function of reachability, not a free-text summary, Decision 5: `sideMetrics` (3 fixed slots) carries Gateway/Chat API/Extraction Service; `sideRows` carries Training Service/Model Serving, Decisions (+4 more)

### Community 733 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 734 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 735 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 736 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 737 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 738 - "2026-09-08-subject-column-type-convergence/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Compare declared type against actual type, and converge in the reconciler, Decision 2: Always `USING NULL::<type>`, never a value-preserving cast, Decision 3: Blanking is the documented outcome, and it is logged, Decision 4: `value_kind` stays editable, Decision 5: Off-surface columns are left alone, Decisions (+4 more)

### Community 739 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 740 - "2026-09-08-sysadmin-user-onboarding/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: New endpoint, not a widened `POST /api/v1/users`, Decision 2: Reuse `UserService.create_user` as-is, no new authorization abstraction, Decision 3: Tenant-active validation moves into `UserService.create_user`, Decision 4: Audit logging added to `UserService.create_user`, Decision 5: Frontend — extract shared `CreateUserForm`, mount on tenant detail page, reuse existing terminology, Decisions (+4 more)

### Community 741 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 742 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 743 - "2026-09-08-tenant-dashboard-workspace-refresh/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Derive events from existing columns via a UNION query, not a new audit table, Decision 2: One curated event kind per underlying status transition, computed per-row (no delta/diff tracking), Decision 3: `system_admin`'s approval queue stays on the old raw builder, Decision 4: Icon field is a string key resolved client-side, not a URL or raw SVG, Decision 5: Relative timestamp formatted server-side as a plain string, Decisions (+4 more)

### Community 744 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 745 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 746 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 747 - "Requirements"
Cohesion: 0.15
Nodes (12): analytics-export, Purpose, Requirement: CSV Export Endpoint, Requirement: Export Filter Validation, Requirement: Export Result Size Limit, Requirement: JSON Export Endpoint, Requirements, Scenario: Empty export returns header-only CSV (+4 more)

### Community 748 - "Requirement: Async OCR Processing"
Cohesion: 0.15
Nodes (13): Requirement: Async OCR Processing, Scenario: Declared media type selects the extractor, Scenario: Derived data is not deleted when bytes cannot be resolved, Scenario: DOC text extraction succeeds, Scenario: DOCX text extraction succeeds, Scenario: Filename extension is the fallback when the declared type is generic, Scenario: Image OCR succeeds, Scenario: OCR processing fails (+5 more)

### Community 749 - "Requirement: Login Page Layout and Submission"
Cohesion: 0.15
Nodes (12): Login Page, Purpose, Requirement: Demo Role Chips, Requirement: Login Page Layout and Submission, Requirements, Scenario: Already-authenticated user is redirected away from login, Scenario: Clicking a demo chip fills and submits credentials, Scenario: Demo chips are absent in production mode (+4 more)

### Community 750 - "Requirement: Query Error Banner"
Cohesion: 0.15
Nodes (12): Purpose, query-error-feedback, Requirement: Query Error Banner, Requirement: Query Loading State, Requirement: Query retry on error, Requirements, Scenario: Loading state clears on success or failure, Scenario: Loading state shown during query (+4 more)

### Community 751 - "Requirement: Widget Keys Screen"
Cohesion: 0.15
Nodes (12): Purpose, Requirement: Widget Keys Screen, Requirements, Scenario: copy button copies key prefix to clipboard, Scenario: empty state shown on API error, Scenario: empty state shown when API returns empty list, Scenario: keys table renders when API returns data, Scenario: screen renders API path breadcrumb (+4 more)

### Community 752 - "2026-06-08-tenant-admin-user-mgmt/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: New `users.py` router module, Decision 2: `require_tenant_admin` admits only `tenant_admin`, Decision 3: Remove admin user CRUD endpoints, Decision 4: `tenant_admin` can create other `tenant_admin` users, Decisions, Goals / Non-Goals (+3 more)

### Community 753 - "2026-06-11-training-approval-gate/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: System admin guard reuses existing role pattern, Decision 2: Approve/reject endpoints are tenant-scoped but system-admin-guarded, Decision 3: `pending_approval` is cancellable by tenant admin, Decision 4: List endpoint shows `pending_approval` and `rejected` jobs alongside others, Decisions, Goals / Non-Goals (+3 more)

### Community 754 - "2026-06-12-mlflow-integration/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: MLflow Tracking Server — Standalone Deployment, Decision 2: Tenant Isolation via Naming Conventions, Decision 3: Model Registry Proxy — Keep External API, Replace Internal Implementation, Decision 4: Manual MLflow Logging (Not Autolog), Decisions, Goals / Non-Goals (+3 more)

### Community 755 - "2026-06-15-promote-warmup-integration/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Synchronous warmup in promote endpoint, Decision 2: Warmup endpoint accepts optional version_number, Decision 3: Warmup failure is non-fatal, Decision 4: Configurable model-serving URL via NER_MODEL_SERVING_URL, Decisions, Goals / Non-Goals (+3 more)

### Community 756 - "ADDED Requirements"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Model warmup on promotion, Requirement: Standalone warmup API (optional convenience), Requirement: Warmup endpoint in model-serving, Scenario: First extraction after warmup uses cached model, Scenario: Warmup endpoint for non-existent version returns 404, Scenario: Warmup endpoint loads a specific version, Scenario: Warmup endpoint loads the active model (+3 more)

### Community 757 - "Requirement: Auth Fetch 401 Silent Refresh"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Auth Fetch 401 Silent Refresh, Requirement: Auth Fetch Interceptor, Scenario: 401 triggers one silent refresh and retries, Scenario: authFetch injects Bearer token on authenticated requests, Scenario: authFetch passes absolute URLs through unchanged, Scenario: authFetch prepends document service URL for document routes, Scenario: authFetch prepends gateway URL for admin routes (+3 more)

### Community 758 - "2026-06-16-portal-shell/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Next.js `(auth)` route group for the authenticated layout, Decision 2: `AppShell` as a single client component, children passed as `{children}`, Decision 3: `navFor(role)` as a pure function in `src/lib/nav-config.ts`, Decision 4: Role-switcher gated behind `NEXT_PUBLIC_DEMO_MODE`, Decisions, Goals / Non-Goals (+3 more)

### Community 759 - "2026-06-17-add-login-dashboard-transition/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: CSS keyframe expand over GSAP / Framer Motion, Decision 2: `clip-path: circle(...)` expansion from card-side, Decision 3: Delay navigation until `animationend`, not a fixed `setTimeout`, Decision 4: Fade-in applied to the `(auth)` layout, not just the dashboard page, Decisions, Goals / Non-Goals (+3 more)

### Community 760 - "2026-06-17-fix-batch-extraction-worker/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Read document text from `document_text_spans` directly in the worker, Decision 2: Add `document_id` to `extracted_entities` via Alembic migration, Decision 3: Fix idempotency check against `extracted_entities.document_id`, Decision 4: Update `query_entities` to filter on `extracted_entities.document_id` directly, Decisions, Goals / Non-Goals (+3 more)

### Community 761 - "2026-06-17-portal-dashboard/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Single `/api/v1/dashboard/summary` endpoint instead of multiple parallel client fetches, Decision 2: TanStack Query (`@tanstack/react-query`) for data fetching, Decision 3: Layout toggle stored in `localStorage`, not URL or server state, Decision 4: Static `dashData(role)` shape for mockup-faithful content, with real values substituted where APIs exist, Decisions, Goals / Non-Goals (+3 more)

### Community 762 - "2026-06-18-default-base-model/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Base model as conceptual "version 0", Decision 2: Hugging Face Transformers pipeline for base model inference (not ONNX), Decision 3: Shared base model pipeline (not per-tenant in cache), Decision 4: `model_version` field in extraction response, Decisions, Goals / Non-Goals (+3 more)

### Community 763 - "MODIFIED Requirements"
Cohesion: 0.17
Nodes (11): MODIFIED Requirements, Requirement: Internal inference endpoint, Requirement: Model warmup on promotion, Requirement: Version resolution with base fallback, Scenario: Base model is shared across tenants, Scenario: Inference falls back to base model when no tenant model exists, Scenario: Inference falls back to base model when tenant model fails to load, Scenario: Inference returns predictions from fine-tuned model (+3 more)

### Community 764 - "2026-06-18-enforce-env-secrets/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Remove defaults for secret fields in `Settings`, Decision 2: Use `${VAR}` interpolation in `docker-compose.yml`, Decision 3: Extend `.env.example` with docker-compose variables and required markers, Decision 4: Update `test_settings_fallback_defaults` in `test_env_config.py`, Decisions, Goals / Non-Goals (+3 more)

### Community 765 - "Requirement: Automated Database Initialization on Compose Up"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Automated Database Initialization on Compose Up, Requirement: Postgres Data Persistence Across Compose Cycles, Scenario: Application services wait for db-init to complete, Scenario: Database contents survive docker compose down and up, Scenario: Explicit volume removal resets the database, Scenario: Init is idempotent on subsequent compose up cycles, Scenario: Migrations are applied automatically on compose up (+3 more)

### Community 766 - "Requirement: Sidebar Layout"
Cohesion: 0.17
Nodes (11): MODIFIED Requirements, Requirement: Sidebar Layout, Scenario: active nav item is highlighted, Scenario: badge renders when present, Scenario: floating menu opens and closes on trigger, Scenario: logout clears session and redirects, Scenario: menu closes on Escape, Scenario: menu closes on outside click (+3 more)

### Community 767 - "2026-06-22-sp-05-annotation-workspace/tasks.md"
Cohesion: 0.17
Nodes (11): 10. Task Status Lifecycle, 11. Verification & Evidence, 1. Setup and Route Scaffolding, 2. State Management — Span Reducer, 3. Char-Offset Utility, 4. Layout and Task Queue, 5. Document Viewer and Token Rendering, 6. Entity Type Palette (+3 more)

### Community 768 - "2026-06-23-tenant-from-jwt-in-chat-api/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Remove `{tid}` entirely from chat API paths, Decision 2: Remove `tid` mismatch checks from handlers, Decision 3: Update gateway proxy routes, Decision 4: Update existing spec scenarios, Decisions, Goals / Non-Goals (+3 more)

### Community 769 - "2026-06-24-analytics-and-reporting/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Dedicated analytics service vs. in-gateway endpoint, Decision 2: Materialized views vs. live aggregation queries, Decision 3: Query filter format, Decision 4: Frontend charting library, Decisions, Goals / Non-Goals (+3 more)

### Community 770 - "2026-06-24-sp-07/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Single page with split-panel layout (list + detail), Decision 2: Client-side polling with TanStack Query for running jobs, Decision 3: Status timeline derived client-side from job status, Decision 4: Span-count preflight via annotation-export endpoint, Decisions, Goals / Non-Goals (+3 more)

### Community 771 - "2026-06-25-align-dashboard-to-mockup/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Keep inline styles vs adopt CSS modules, Decision 2: Remove SegmentControl entirely (not just hide), Decision 3: Activity row indicator — dot + right-aligned tag, Decision 4: Stat card grid — replace flex-wrap with explicit 4-column grid, Decisions, Goals / Non-Goals (+3 more)

### Community 772 - "2026-06-25-sp-04-dashboard/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Gateway composite endpoint vs. client-side aggregation, Decision 2: Per-service failure isolation with `sources` metadata, Decision 3: Role-to-service routing via JWT claims, Decision 4: Editorial/Command layout as pure CSS concern, Decisions, Goals / Non-Goals (+3 more)

### Community 773 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Dashboard Summary Endpoint, Requirement: DashboardData TypeScript Type, Scenario: annotator summary returns task data, Scenario: business_user summary returns extraction data, Scenario: null values are assignable, Scenario: system_admin summary returns role-specific data, Scenario: tenant_admin summary returns pipeline data (+3 more)

### Community 774 - "2026-06-25-sp-09-entity-types/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: One spec (`entity-types-screen`) covering page + hooks + components, Decision 2: Hue assigned client-side by index mod 7, Decision 3: Reuse existing `SlideOver` primitive, Decision 4: Separate components, not a monolith page file, Decisions, Goals / Non-Goals (+3 more)

### Community 775 - "2026-06-29-assign-annotation-tasks/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Inline expandable form in the Task Queue panel (not a modal), Decision 2: Fetch annotator list and document list on-demand (when form opens), Decision 3: Client-side document filter — only show `processed` documents, Decision 4: Optimistic task list update on successful creation, Decisions, Goals / Non-Goals (+3 more)

### Community 776 - "2026-07-08-fix-tenant-schema-drift-and-training-worker-config/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Apply tenant-scoped DDL to `tenant_template` and every active tenant schema in the same migration, via a shared helper, Decision 2: Ship a new remediation migration that adds the missing `error_message` column (and defensively re-verifies the rest of 005's shape) via the new helper, Decision 3: Fix `ANNOTATION_SERVICE_URL` default and set it explicitly in `docker-compose.yml`, Decision 4: Reconcile `seed.py`'s inline tenant table DDL with `tenant_template`, Decisions, Goals / Non-Goals (+3 more)

### Community 777 - "2026-07-08-review-imported-annotations/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: New capability, not a modification of `annotation-import-ui`, Decision 2: Token-index edit model, not char-offset spans, Decision 3: `reviewed` as a simple boolean + audit fields, not a status enum, Decision 4: Entity colors computed client-side, same scheme as the main workspace, Decisions, Goals / Non-Goals (+3 more)

### Community 778 - "Requirement: Typed retrieval domain model"
Cohesion: 0.17
Nodes (11): MODIFIED Requirements, Requirement: Single chunking implementation, Requirement: Typed retrieval domain model, Scenario: A chunk never spans more than one page, Scenario: Chunk carries page metadata when produced from a span, Scenario: Empty spans produce no chunks, Scenario: Ingestion and chat share one chunking function, Scenario: Ingestion produces typed chunks (+3 more)

### Community 779 - "2026-07-29-annotation-completion-workflow/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Promote to `in-progress` on task selection, not on first span, Decision 2: `completed` → `completed` is an idempotent 200, Decision 3: New `AnnotationActionBar` component in the existing grid row 4, Decision 4: Save indicator is derived, not a new persistence layer, Decisions, Goals / Non-Goals (+3 more)

### Community 780 - "2026-09-08-audit-log-page/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Append-only audit table in `public` schema, Decision 2: Manual event recording at action sites (not DB triggers or CDC), Decision 3: Offset-based pagination on the API, Decision 4: New `AuditLog` React component inline in the page, no new route-level component, Decisions, Goals / Non-Goals (+3 more)

### Community 781 - "2026-09-08-audit-log-tenant-filter/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Filter via a single optional query parameter, applied in both SQL statements, Decision 2: Tenant options fetched via existing `/admin/tenants?per_page=100`, Decision 3: New lightweight `SearchableCombobox` UI component, styled to match `FilterSelect`, Decision 4: Selecting a tenant resets pagination to page 1, Decisions, Goals / Non-Goals (+3 more)

### Community 782 - "Requirement: Audit Log Page Tenant Filter UI"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Audit Log Endpoint Tenant Filtering, Requirement: Audit Log Page Tenant Filter UI, Scenario: Default view shows all tenants, Scenario: Empty state for a tenant with no audit events, Scenario: Filtering to a specific tenant, Scenario: No tenant filter supplied, Scenario: Returning to All Tenants (+3 more)

### Community 783 - "Requirement: RAG chat endpoint"
Cohesion: 0.17
Nodes (11): MODIFIED Requirements, Requirement: Guardrail — source citation enforcement, Requirement: RAG chat endpoint, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with NER query, Scenario: Chat with simple entity count query, Scenario: Chat without authentication (+3 more)

### Community 784 - "2026-09-08-cloud-readiness-resilience/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Use `tenacity` for retry/backoff, applied at the client-construction boundary, Decision 2: Split `/health` into readiness (`/health`) and liveness (`/health/live`), Decision 3: Externalize DB SSL mode as a dedicated setting instead of only via the URL string, Decision 4: Retry defaults are conservative and bounded, tuned for "seconds to low tens of seconds" dependency startup delay, Decisions, Goals / Non-Goals (+3 more)

### Community 785 - "2026-09-08-dockerize-portal-and-fix-build-hygiene/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Portal Dockerfile — 3-stage build, Decision 2: Root Dockerfile — multi-stage (builder + runtime), Decision 3: Gateway → chat_api via Docker DNS, Decision 4: Delete stale `src/training_service/Dockerfile` and dead `requirements.txt` files, Decisions, Goals / Non-Goals (+3 more)

### Community 786 - "2026-09-08-entity-quality-postprocessing/tasks.md"
Cohesion: 0.17
Nodes (11): 10. Portal contract (no UI implementation), 11. Verification & Evidence, 1. Confidence calibration (blocking — lands first), 2. Migration A — `document_entities` provenance, 3. Deterministic repairs — normalization and reconstruction, 4. Validity gate and duplicate policy, 5. Migration B — `extraction_runs` processing mode, 6. Batch extraction contract — processing mode (+3 more)

### Community 787 - "2026-09-08-entity-resolution-disambiguation/tasks.md"
Cohesion: 0.17
Nodes (11): 10. Flag-off equivalence tests — `tests/test_entity_resolution_flag_off.py`, 11. Verification & Evidence, 1. Configuration and migration, 2. Resolver core (no graph wiring yet), 3. Conversation state, 4. Graph wiring, 5. API surface, 6. Resolver unit tests — `tests/test_entity_resolver.py` (+3 more)

### Community 788 - "2026-09-08-merge-bio-entity-display/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Merge in the frontend hook, not the component, Decision 2: Grouped layout replaces flat list, not layered on top, Decision 3: Average confidence for merged tokens, Decision 4: Sort within groups by start_offset ascending (text order), Decisions, Goals / Non-Goals (+3 more)

### Community 789 - "Requirement: List model versions"
Cohesion: 0.17
Nodes (11): ADDED Requirements, MODIFIED Requirements, Requirement: Base model omits run name, Requirement: List model versions, Scenario: Active model endpoint returns null run name for the base model, Scenario: Legacy model version with no run_number exposes a null run name, Scenario: List all versions when multiple exist in same MLflow stage, Scenario: List model versions with MLflow links (+3 more)

### Community 790 - "Requirement: Batch extraction"
Cohesion: 0.17
Nodes (11): MODIFIED Requirements, Requirement: Batch extraction, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction persists normalized entities, Scenario: Batch extraction skips already-extracted documents, Scenario: Batch extraction uses version 0 when no model promoted, Scenario: Default batch extraction excludes training-purpose documents (+3 more)

### Community 791 - "2026-09-08-redesign-business-user-dashboard/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Query chat-api's tenant-schema tables directly from the gateway, matching the existing per-role handler pattern, Decision 2: Assistant status via a single call to chat-api's existing `/health` endpoint, Decision 3: "Average Response Time" is best-effort and omitted when no data exists, Decision 4: "Frequently Asked Topics" via keyword frequency over conversation titles, Decisions, Goals / Non-Goals (+3 more)

### Community 792 - "Requirement: The query-surface resolver is the one authoritative description of the readable relations"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Provisioning smoke-checks the generated relations, Requirement: The query-surface resolver is the one authoritative description of the readable relations, Scenario: A base-model definition resolves through its label mapping, Scenario: A generated relation is smoke-checked, Scenario: A missing grant on a generated relation is caught at provisioning time, Scenario: Off-surface relations are excluded, Scenario: One tenant's surface never includes another's relations (+3 more)

### Community 793 - "2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: One sync use case, four triggers, identity-only queued payloads, Decision 2: Ledger, lease, and run record in the tenant schema, Decision 3: Replace-by-reprocessing with retrieval hiding for missing objects, Decision 4: Temporary working storage with guaranteed deletion, Decisions, Goals / Non-Goals (+3 more)

### Community 794 - "Requirements"
Cohesion: 0.17
Nodes (11): Admin Console, Purpose, Requirement: GPU Job Monitoring, Requirement: Tenant Detail View, Requirement: Tenant Management Dashboard, Requirements, Scenario: System Admin creates a user in the tenant from this view, Scenario: System Admin creates tenant via UI (+3 more)

### Community 795 - "Requirement: BIO Tag Persistence on Spans"
Cohesion: 0.17
Nodes (11): BIO Tag Storage, Purpose, Requirement: BIO Tag Persistence on Spans, Requirement: BIO Tag Schema Migration, Requirements, Scenario: BIO tags are recomputed on entity type retype, Scenario: BIO tags are stored when a span is created, Scenario: Export falls back to computed BIO for legacy spans with NULL bio_tags (+3 more)

### Community 796 - "Requirement: Manual Blob sync trigger action"
Cohesion: 0.11
Nodes (18): Purpose, Requirement: Manual Blob sync trigger action, Requirement: Safe activation and concurrent capability limits, Requirement: Tenant-admin-managed finite Azure connections, Requirements, Scenario: Administrator triggers a manual sync on an active Blob connection, Scenario: Cross-tenant connection access is denied, Scenario: Cross-tenant manual sync is denied (+10 more)

### Community 797 - "Requirements"
Cohesion: 0.17
Nodes (11): Purpose, Requirement: Tenant Creation, Requirement: Tenant Listing and Detail, Requirement: Tenant Quotas, Requirements, Scenario: System Admin creates a tenant with duplicate slug, Scenario: System Admin creates a tenant with valid data, Scenario: System Admin deactivates a tenant (+3 more)

### Community 798 - "Requirement: Tenant-Admin User CRUD Endpoints"
Cohesion: 0.17
Nodes (11): Purpose, Requirement: Tenant-Admin User CRUD Endpoints, Requirements, Scenario: Non-tenant-admin role cannot access user endpoints (role enforcement), Scenario: Tenant Admin creates a user in their own tenant, Scenario: Tenant Admin deactivates a user in their tenant, Scenario: Tenant Admin gets a specific user in their tenant, Scenario: Tenant Admin lists users in their own tenant (+3 more)

### Community 799 - "lifecycle.py"
Cohesion: 0.08
Nodes (36): _connection_string(), DataPlaneSecureTester, _query_role_available(), The `azure_postgresql_data_plane` secure tester (ADR-017, Design D3, D11 — task…, Registered for `azure_postgresql_data_plane` in `testing.py`'s tester registry.…, Returns a failure reason, or `None` if the target schema is absent, empty, or…, run_data_plane_test_sync(), _schema_create_privilege() (+28 more)

### Community 800 - "ADDED Requirements"
Cohesion: 0.14
Nodes (13): ADDED Requirements, Requirement: An unreachable tenant store fails closed for that tenant only, Requirement: Background tasks retry with bounded backoff and then park, Requirement: Per-tenant store health is a content-free control-plane signal, Requirement: Uploads are rejected before bytes are accepted when the store is unavailable, Scenario: Chat fails closed during a store outage, Scenario: Driver error text is not exposed, Scenario: Extraction parks after bounded retries (+5 more)

### Community 801 - "2026-06-08-env-config-setup/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Single `.env` at project root, Decision 2: `.env.example` tracked, `.env` gitignored, Decision 3: Test overrides remain in `conftest.py`, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 802 - "ADDED Requirements"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Base Label Mapping, Requirement: Entity Type Definition, Requirement: Entity Type Listing and Query, Scenario: Entity type with invalid base model label, Scenario: Entity type with valid label mapping, Scenario: Tenant Admin creates an entity type, Scenario: Tenant Admin filters active entity types only (+2 more)

### Community 803 - "2026-06-08-sm-01-identity-tenant-entity-config/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Project Setup & Scaffolding, 2. Data Model & Database Migrations, 3. Tenant Context Middleware, 4. Tenant Provisioning API, 5. User Authentication API, 6. User Management API, 7. Entity Configuration API (+2 more)

### Community 804 - "Requirement: Reject training job"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Approve training job, Requirement: Reject training job, Scenario: Approve a job that is not pending_approval, Scenario: Approve a pending training job, Scenario: Approve as non-system-admin, Scenario: Reject a job that is not pending_approval, Scenario: Reject a pending training job (+2 more)

### Community 805 - "Requirement: Submit training job"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Cancel training job, Requirement: Submit training job, Scenario: Cancel a completed job returns 422, Scenario: Cancel a pending_approval job, Scenario: Cancel a queued job, Scenario: Submit a valid training job, Scenario: Submit training job as non-admin (+2 more)

### Community 806 - "Requirement: Auth Context Provider"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Auth Context Access Token Exposure, Requirement: Auth Context Provider, Scenario: authFetch reads token synchronously without re-render, Scenario: authFetch updates token after silent refresh, Scenario: Logout clears user and calls logout endpoint, Scenario: On-mount refresh failure leaves user as null, Scenario: On-mount refresh restores session from cookie (+2 more)

### Community 807 - "Requirement: Login Page Layout and Submission"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Demo Role Chips, Requirement: Login Page Layout and Submission, Scenario: Already-authenticated user is redirected away from login, Scenario: Clicking a demo chip fills and submits credentials, Scenario: Demo chips are absent in production mode, Scenario: Demo chips are visible when DEMO_MODE is enabled, Scenario: Failed login shows form-level error (+2 more)

### Community 808 - "2026-06-16-remove-tid-from-url/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Remove `{tid}` from URL path, rely entirely on JWT for tenant context, Decision 2: Extraction engine `infer()` function must pass JWT to model serving, Decision 3: Gateway extraction proxy forwards Authorization header transparently, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 809 - "2026-06-17-add-celery-extraction-worker/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Separate worker service (not merging into existing celery_worker), Decision 2: Reuse training_service Dockerfile (not a lighter image), Decision 3: Use `--pool=solo` for Windows compatibility, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 810 - "2026-06-17-fix-extraction-run-persistence/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Pre-create the run row in the POST handler (synchronous insert), Decision 2: Single row per batch run (not one per document), Decision 3: New Alembic migration adding six columns, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 811 - "2026-06-18-dockerize-backend-services/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Single shared root Dockerfile for all services, Decision 2: Internal port 8000 for every service; distinct host ports, Decision 3: Update inter-service env vars to Docker service names, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 812 - "2026-06-18-mlflow-test-verification/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Standalone Test File (Not Merged Into Existing Tests), Decision 2: Direct MLflow Client + Proxy Calls (Not Celery Task), Decision 3: Database Cache Fixture With Real PostgreSQL, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 813 - "2026-06-19-fix-postgres-persistence-and-db-init/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Named Docker volume for postgres data directory, Decision 2: Dedicated `db-init` one-shot service for migrations and seeding, Decision 3: `db-init` commands run as a combined shell invocation, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 814 - "ADDED Requirements"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: CSV Export Endpoint, Requirement: Export Filter Validation, Requirement: Export Result Size Limit, Requirement: JSON Export Endpoint, Scenario: Empty export returns header-only CSV, Scenario: Export exceeds size limit, Scenario: Export returns valid CSV (+2 more)

### Community 815 - "2026-06-24-sp-06/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Add `GET /api/v1/admin/tenants/{tenant_id}/users` backend endpoint, Decision 2: Implement `/users` page as a single-page CRUD view (no separate create page), Decision 3: Allow role changes but not re-activation via the users page, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 816 - "Requirement: Widget Keys Screen"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Widget Keys Screen, Scenario: copy button copies key prefix to clipboard, Scenario: empty state shown on API error, Scenario: empty state shown when API returns empty list, Scenario: keys table renders when API returns data, Scenario: screen renders API path breadcrumb, Scenario: topbar shows correct title for /widget-keys (+2 more)

### Community 817 - "2026-06-30-fix-dashboard-queries/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Schema-qualified table names over search_path switching, Decision 2: Gateway queries tenant schemas directly (no service calls), Decision 3: Reconcile migration drift with a new migration, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 818 - "2026-07-02-batch-extraction-run-history/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Follow the existing raw-SQL-with-schema-prefix pattern, not a new query abstraction, Decision 2: Cap the list with `LIMIT 50`, no pagination params, Decision 3: Response shape mirrors `BatchRunStatus` plus `run_id`, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 819 - "2026-07-02-fix-prelabel-keyword-search/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Keyword source — use `examples` column instead of `base_label_mapping` values, Decision 2: Case-insensitive matching, Decision 3: Longest-match-wins overlap resolution, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 820 - "2026-07-06-fix-analytics-materialized-views/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Backfill via new Alembic migration, Decision 2: Update seed script to create MVs, Decision 3: Refresh MVs immediately after creation, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 821 - "ADDED Requirements"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Backfill Missing Materialized Views for Existing Tenants, Requirement: Create Materialized Views for New Tenants, Requirement: Refresh Materialized Views After Creation, Scenario: Analytics dashboard shows populated widgets after backfill, Scenario: Migration backfills a tenant missing MVs, Scenario: Migration skips tenants that already have MVs, Scenario: MVs reflect existing data after creation (+2 more)

### Community 822 - "2026-07-07-fix-analytics-query-feedback/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Frontend error handling — use existing `errorMessage` pattern, Decision 2: Gateway proxy — structured error forwarding, Decision 3: Backend — typed exception handling, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 823 - "2026-07-08-fix-system-admin-training-queue-bugs/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Surface `tenant_id` on the training job response and thread it end-to-end, Decision 2: System Admin Training Queue list aggregates pending-approval jobs across tenants by default, Decision 3: Roll back the shared session after each per-tenant-schema query failure in `_system_admin_data`, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 824 - "2026-07-09-fix-mlflow-model-logging/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Pin MLflow client to 2.x instead of upgrading server, Decision 2: Use `torch.onnx.export()` directly for ONNX conversion, Decision 3: Simple database pre-check as retry guard, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 825 - "2026-07-13-fix-model-loading-and-label-mapping/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Training Worker — S3 Path Fix, 2. Training Worker — label_list Persistence, 3. Model Serving — Loader Path Parameter, 4. Model Serving — label_list Resolution, 5. Migration — Backfill label_list, 6. Model Serving — Training Service URL Configuration, 7. Docker Compose — Training Service Warmup Routing (+2 more)

### Community 826 - "2026-07-13-redesign-training-jobs-ui/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Full Mockup Fidelity Pass (found via direct visual comparison against `docs/NER Platform.html`'s actual computed template/JS, not just the earlier eyeballed re-skin), 11. Verification & Evidence, 1. Shared Primitive: LineageFlow, 2. Job List & Filter Tabs Re-skin, 3. Horizontal Status Timeline, 4. Detail Panel: Running Callout, Metrics, MLflow Card, Lineage, 5. Submit Slide-over & Actions Re-skin, 6. Page Shell (+2 more)

### Community 827 - "2026-07-16-fix-model-serving-tenant-query/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Pass `tenant_id` as query parameter (fix in model-serving only), Decision 2: Preserve existing error handling, Decision 3: Increase extraction engine timeout to 90s, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 828 - "2026-07-27-clean-rebuild-and-schema-hardening/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Tree Hygiene (must precede any image rebuild), 2. Dashboard Tenant Enumeration, 3. Migration Robustness, 4. Tenant Schema Reconciliation, 5. Tenant Provisioning Atomicity, 6. Fixture Script Guard, 7. Schema Verification Step (+2 more)

### Community 829 - "Requirement: Annotation Task Management"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Annotation Task Management, Scenario: Complete a task that has spans, Scenario: Complete a task with no spans returns 422, Scenario: Create an annotation task, Scenario: Create task for a query-purpose document is rejected, Scenario: Create task for already-assigned document returns 409, Scenario: Document picker only lists training-purpose documents (+2 more)

### Community 830 - "Requirement: Batch extraction"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Batch extraction, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities with document linkage, Scenario: Batch extraction skips already-extracted documents, Scenario: Batch extraction uses version 0 when no model promoted, Scenario: Default batch extraction excludes training-purpose documents, Scenario: Explicit documentIds bypasses purpose filtering (+2 more)

### Community 831 - "Requirement: Annotation Task Management"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Annotation Task Management, Scenario: Complete a task that has spans, Scenario: Complete a task with no spans returns 422, Scenario: Create an annotation task, Scenario: Create task for already-assigned document returns 409, Scenario: List annotation tasks with status filter, Scenario: Re-completing a completed task is idempotent (+2 more)

### Community 832 - "Requirement: Fixed topology with no agentic behaviour"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Fixed topology with no agentic behaviour, Requirement: Retrieval and model components are orchestrated, not replaced, Scenario: Blocked question short-circuits to END, Scenario: Excess complexity short-circuits to END when the loop is disabled, Scenario: Flag-off topology is unchanged, Scenario: Graph remains acyclic with the loop enabled, Scenario: No LangChain model, retriever, or agent wrappers are imported (+2 more)

### Community 833 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Scenario: annotator dataset readiness at or above threshold, Scenario: annotator dataset readiness reflects real progress and threshold purpose, Scenario: annotator summary returns task data with entity terminology, Scenario: business_user summary returns extraction data, Scenario: system_admin summary returns role-specific data, Scenario: tenant_admin summary returns pipeline data (+2 more)

### Community 834 - "2026-09-08-batch-extraction-document-selection/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: New read-only endpoint vs. reusing `/api/v1/documents`, Decision 2: Extract shared "already extracted" lookup out of `worker.py`, Decision 3: Enforcement is server-side, not just modal-disabled checkboxes, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 835 - "2026-09-08-cap-1-add-doc-docx-upload-support/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Use `python-docx` for `.docx` extraction, Decision 2: Use `antiword` subprocess for `.doc` extraction, Decision 3: Minimal error handling for `.doc` extraction failure, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 836 - "2026-09-08-chat-auto-titles-and-rename/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Generate the title synchronously, in-process, from the first user message text, Decision 2: Title derivation algorithm, Decision 3: Rename endpoint shape, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 837 - "2026-09-08-chat-conversation-and-citations/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Remediation tasks (gaps from initial implementation), 1. Backend: Citation model and schemas, 2. Backend: Conversation creation endpoint, 3. Backend: Citation enrichment layer, 4. Backend: SQL generator prompt enhancement, 5. Frontend: Unified CitationCard component, 6. Frontend: New conversation button API integration, 7. Frontend: Chat page input visibility fix (+2 more)

### Community 838 - "Requirement: Document Content Hashing and Duplicate Identification"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Document Content Hashing and Duplicate Identification, Scenario: A soft-deleted document is not reported as a duplicate, Scenario: Different content is not reported as a duplicate, Scenario: Different filenames with identical content are recognised as identical content, Scenario: Document metadata exposes the stored checksum, Scenario: Duplicate detection does not cross tenant boundaries, Scenario: Duplicate upload does not modify the original document (+2 more)

### Community 839 - "Requirement: `document_entities` gains provenance columns on the template and every tenant schema"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: `document_entities` gains provenance columns on the template and every tenant schema, Requirement: `extraction_runs` gains processing-mode columns on the template and every tenant schema, Scenario: A tenant schema missing the table does not abort the migration, Scenario: Columns exist on every tenant schema, Scenario: Columns exist on every tenant schema, Scenario: Downgrade removes only the added columns, Scenario: Existing rows survive unchanged (+2 more)

### Community 840 - "Requirement: Document Metadata API"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Document Metadata API, Scenario: A deleted document stops answering generated SQL, Scenario: Delete a document, Scenario: Deletion clears the document's relational rows, Scenario: Deletion tolerates a document with no relational rows, Scenario: Get deleted document returns 200 with deleted status, Scenario: Get document metadata (+2 more)

### Community 841 - "Requirement: Batch Runs Tab — Batch Extraction Management"
Cohesion: 0.18
Nodes (10): MODIFIED Requirements, Requirement: Batch Runs Tab — Batch Extraction Management, Scenario: Batch Runs tab lists existing runs, Scenario: Document selection dialog remains centered and independently scrollable, Scenario: In-progress runs poll for status updates, Scenario: Long run list scrolls independently of the page, Scenario: Run history persists across page reload, Scenario: Selecting a batch run shows detail (+2 more)

### Community 842 - "2026-09-08-normalized-entity-store/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Schema, 2. Inference ordering fix, 3. Entity normalizer (pure functions), 4. Offset alignment, 5. Normalized entity persistence, 6. Backfill utility, 7. Structured retrieval migration (+2 more)

### Community 843 - "2026-09-08-observability-workload-instrumentation/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Declarations and enforcement — land first, gate everything after, 2. Tenant-safety counters — smallest diff, highest gate value, 3. Chat path — guardrails, resolution, retrieval, 4. Chat path — SQL generation, execution and LLM usage, 5. Extraction, projection and the Celery queues, 6. Model serving and training, 7. LangSmith correlation (+2 more)

### Community 844 - "2026-09-08-relational-only-sql-generation/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Query-surface resolver (behaviour-preserving), 2. Validation: relations and columns from the surface, 3. Document scoping over the relational surface, 4. Grounding: relational surface plus semantics plus samples, 5. Prompt: relational-only query model, 6. Defect ladder and retry feedback, 7. Projection-coverage safety (+2 more)

### Community 845 - "2026-09-08-response-feedback-rating/tasks.md"
Cohesion: 0.18
Nodes (10): 1. Database migration, 2. chat_api: answer classification and model-version capture, 3. chat_api: feedback persistence and endpoint, 4. gateway: feedback analytics for the dashboard, 5. Portal: chat message feedback UI, 6. Portal: dashboard response-quality panel, 7. Verification tests, 8. Deploy: rebuild and restart affected containers (+2 more)

### Community 846 - "Requirement: Semantic value columns are added to the template and every existing tenant schema"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Entity definition value kind columns are added to the public schema, Requirement: Semantic value columns are added to the template and every existing tenant schema, Scenario: Columns are added without touching existing definitions, Scenario: Downgrade removes the columns, Scenario: Existing rows are preserved, Scenario: Newly provisioned tenants inherit the columns, Scenario: Re-running the migration is a no-op (+2 more)

### Community 847 - "2026-09-08-structured-entity-value-normalization/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Schema — value kind configuration (mandatory), 2. Schema — typed value columns on `document_entities` (mandatory), 3. Semantic normalizer module (mandatory), 4. Wire normalization into the extraction pipeline (mandatory), 5. Entity type configuration API (mandatory), 6. SQL query layer (mandatory), 7. Backfill (mandatory) (+2 more)

### Community 848 - "2026-09-08-system-admin-sets-training-params/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Where hyperparameter validation lives, Decision 2: `hyperparams` nullability, Decision 3: Approval is a single validated request, not a two-step "propose then confirm", Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 849 - "2026-09-08-system-admin-sets-training-params/tasks.md"
Cohesion: 0.18
Nodes (10): 10. Verification & Evidence, 1. Database Migration, 2. Backend: Submit Endpoint, 3. Backend: Approve Endpoint, 4. Backend Tests, 5. Frontend: Submit Slideover, 6. Frontend: System Admin Approval Form, 7. Frontend: Null-Hyperparameter Rendering (+2 more)

### Community 850 - "Requirement: Per-Tenant Integration Credentials Are References Only"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: Per-Tenant Integration Credentials Are References Only, Requirement: Runtime Credential Resolution Failure Is Explicit, Scenario: A value in a secret field is rejected by schema, not by heuristic, Scenario: An unresolvable reference errors the profile, not the process, Scenario: Credential resolution is not reachable from adapter code, Scenario: No credential value is persisted, Scenario: Process-level secret-class settings still fail fast (+2 more)

### Community 851 - "2026-09-10-cap-2-tenant-scoped-connection-control-plane/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Extend the existing profile seam with a bounded lifecycle, Decision 2: Gate activation on finite safe evidence, Decision 3: Enforce independent active-type limits transactionally, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 852 - "Requirement: Dark Theme Consistency Across Portal Pages"
Cohesion: 0.18
Nodes (10): dark-theme-consistency, Purpose, Requirement: Dark Theme Consistency Across Portal Pages, Requirements, Scenario: Chat Page Dark Mode, Scenario: Documents Page Dark Mode, Scenario: Imported Documents Page Dark Mode, Scenario: Model Registry Page Dark Mode (+2 more)

### Community 853 - "Requirement: Document Upload"
Cohesion: 0.18
Nodes (11): Requirement: Document Upload, Scenario: Ephemeral retention stores no durable original, Scenario: Platform retention stores the original durably, Scenario: Upload a DOC document, Scenario: Upload a DOCX document, Scenario: Upload a PDF document, Scenario: Upload an unsupported file type, Scenario: Upload exceeds file size limit (+3 more)

### Community 854 - "Requirement: Multi-Token Drag Span Creation"
Cohesion: 0.18
Nodes (10): Drag Annotation, Purpose, Requirement: Multi-Token Drag Span Creation, Requirements, Scenario: Drag across tokens creates a multi-token span, Scenario: Drag direction is agnostic (right-to-left = left-to-right), Scenario: Drag ending on an already-confirmed token is blocked, Scenario: Drag preview highlights range during drag (+2 more)

### Community 855 - "Requirements"
Cohesion: 0.18
Nodes (10): Extraction Service, Purpose, Requirement: Gateway Extraction Proxy Uses JWT-Only URL Structure, Requirement: Review and correct entities, Requirements, Scenario: Correct an extracted entity, Scenario: Correct entity as annotator, Scenario: Proxy forwards batch run list request without tid in URL (+2 more)

### Community 856 - "Requirement: Fixture setup scripts refuse non-test databases"
Cohesion: 0.18
Nodes (10): Purpose, Requirement: Explicit opt-in override for the fixture guard, Requirement: Fixture setup scripts refuse non-test databases, Requirements, Scenario: Override permits a non-standard test database name, Scenario: Script refuses to run against the development database, Scenario: Script runs against a test database, Scenario: The guard reads the URL actually used, not the default (+2 more)

### Community 857 - "SQLAttempt"
Cohesion: 0.08
Nodes (18): _filename_filter_literals(), The literals a query requires `documents.filename` to match, with any SQL…, Renders prior attempts into the corrective block appended to a retry prompt. At…, One pass of generate -> validate -> execute -> classify., _render_attempt_feedback(), SQLAttempt, Rows 52, 58 — the feedback has to name the relation that would work, and must…, TestFilenameDefect (+10 more)

### Community 858 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 859 - "Requirement: Safe connection lifecycle interface"
Cohesion: 0.08
Nodes (25): Purpose, Requirement: Data source collection and navigation, Requirement: Manual sync-now control, Requirement: Safe connection lifecycle interface, Requirement: Schema-contract administration interface, Requirements, Scenario: A failed test hides the attestation checkboxes and returns the control to a retry state, Scenario: A passed test surfaces the attestation checkboxes inline, Activate stays disabled until both are checked (+17 more)

### Community 860 - "ADDED Requirements"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Tenant Creation, Requirement: Tenant Listing and Detail, Requirement: Tenant Quotas, Scenario: System Admin creates a tenant with duplicate slug, Scenario: System Admin creates a tenant with valid data, Scenario: System Admin deactivates a tenant, Scenario: System Admin lists tenants with pagination (+1 more)

### Community 861 - "Requirement: Tenant-Admin User CRUD Endpoints"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Tenant-Admin User CRUD Endpoints, Scenario: Non-tenant-admin role cannot create users (role enforcement), Scenario: Tenant Admin cannot create users in another tenant (cross-tenant blocked), Scenario: Tenant Admin creates a user in their own tenant, Scenario: Tenant Admin deactivates a user in their tenant, Scenario: Tenant Admin gets a specific user in their tenant, Scenario: Tenant Admin lists users in their own tenant (+1 more)

### Community 862 - "2026-06-16-portal-foundation/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Workspace Setup, 2. Design Tokens, 3. API Foundations, 4. Root Layout and Font Wiring, 5. Utility Hooks, 6. UI Primitives, 7. Tests for UI Primitives, 8. Build and Type Verification (+1 more)

### Community 863 - "Requirement: Role Navigation Matrix"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Role Navigation Matrix, Requirement: Screen Title Map, Scenario: annotator nav, Scenario: business_user nav, Scenario: known screen lookup, Scenario: system_admin nav, Scenario: tenant_admin nav (+1 more)

### Community 864 - "2026-06-16-portal-shell/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Nav Config Module, 2. AppShell Component — Sidebar, 3. AppShell Component — Topbar, 4. AppShell Root Component, 5. Authenticated Route Group Layout, 6. File Migration (admin pages), 7. Placeholder Screens, 8. Smoke Tests (Browser) (+1 more)

### Community 865 - "2026-06-17-fix-worker-host-routing/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: `host.docker.internal` for host service discovery, Decision 2: Configurable service URLs via `Settings`, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 866 - "MODIFIED Requirements"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Batch extraction, Requirement: Get extraction run status, Requirement: Real-time extraction, Scenario: Batch extraction uses version 0 when no model promoted, Scenario: Extract entities from a text paragraph with fine-tuned model, Scenario: Extract entities using base model when none is promoted, Scenario: Get extraction run status with model version (+1 more)

### Community 867 - "2026-06-18-fix-users-tenant-resolution/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Use `resolve_tenant_from_jwt` and drop the URL slug segment, Decision 2: Cut the old URL immediately, no deprecated alias, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 868 - "Requirement: Tenant-Admin User CRUD Endpoints"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Tenant-Admin User CRUD Endpoints, Scenario: Non-tenant-admin role cannot access user endpoints (role enforcement), Scenario: Tenant Admin creates a user in their own tenant, Scenario: Tenant Admin deactivates a user in their tenant, Scenario: Tenant Admin gets a specific user in their tenant, Scenario: Tenant Admin lists users in their own tenant, Scenario: Tenant Admin updates a user in their tenant (+1 more)

### Community 869 - "2026-06-18-mlflow-test-verification/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Setup & Dependencies, 2. Infrastructure Health Tests, 3. Experiment & Run Lifecycle Tests, 4. Model Registration Tests, 5. Model Registry Proxy Tests, 6. Cache Fallback Tests (Monkeypatched MLflow), 7. Tenant Isolation Tests, 8. Status Mapping Tests (+1 more)

### Community 870 - "2026-06-19-fix-cors-preflight-middleware/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Exempt OPTIONS in `TenantContextMiddleware`, not in a new middleware layer, Decision 2: Apply the fix to both services simultaneously, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 871 - "Requirement: BIO Tag Persistence on Spans"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: BIO Tag Persistence on Spans, Requirement: BIO Tag Schema Migration, Scenario: BIO tags are recomputed on entity type retype, Scenario: BIO tags are stored when a span is created, Scenario: Export falls back to computed BIO for legacy spans with NULL bio_tags, Scenario: Export reads stored bio_tags from spans, Scenario: Migration adds nullable column without data loss (+1 more)

### Community 872 - "2026-06-22-fix-promote-inprogress-transition/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Fix in `handlePromote`, not in `handleMarkComplete`, Decision 2: Reuse the existing `sentInProgressRef` + `taskStatuses` guard pattern unchanged, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 873 - "2026-06-23-fix-chat-page-auth/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Replace raw fetch with authFetch, Decision 2: Do not add chat API paths to authFetch's resolveUrl prefix list, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 874 - "2026-06-25-sp05-annotation-workspace/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Layout and View-Mode Toggle, 2. Annotation Toolbar Redesign, 3. Armed Banner Update, 4. Entity Type Palette Redesign, 5. Span Inspector Redesign, 6. Focus Mode Bottom Palette, 7. Task Queue and Filename Display, 8. Pre-labeling and Suggestion Panel (+1 more)

### Community 875 - "2026-06-25-sp-08-documents/tasks.md"
Cohesion: 0.20
Nodes (9): 1. File & Route Setup, 2. Upload Hook, 3. Document Upload Component, 4. Document Table Component, 5. Status Filter Tabs, 6. Document Data Fetching with Polling, 7. Soft Delete, 8. Page Composition (+1 more)

### Community 876 - "Requirement: Annotation Task Queue"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Annotation Task Queue, Scenario: Active task row is highlighted, Scenario: Annotator does not see Assign Task button, Scenario: Annotator sees only assigned tasks, Scenario: Empty queue shows contextual message, Scenario: Selecting a task loads the document, Scenario: Task row shows filename and document metadata (+1 more)

### Community 877 - "2026-07-08-remove-training-span-gate/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Delete the client-side threshold instead of syncing it to the backend's configured value, Decision 2: Preflight banner shows span count only, no pass/fail styling, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 878 - "Changes"
Cohesion: 0.20
Nodes (9): 1. `model_versions` row must reflect actual job outcome, 2. New scenario: Failed job sets model_versions to failed, 3. `_update_job_progress` must accept dict-type metrics, Changes, Current spec (Requirement: Save model artifacts, Scenario: Artifacts are stored after training), Current spec (Requirement: Update job progress during training), Training Worker — Delta, Updated requirement (+1 more)

### Community 879 - "2026-07-27-document-purpose-scoping/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Database Migration, 2. Upload Endpoint, 3. Ingestion Denormalization, 4. Retriever Purpose Filtering, 5. Annotation Task Purpose Enforcement, 6. Document Picker Scoping, 7. Batch Extraction Purpose Scoping, 8. Frontend Upload Purpose Selection (+1 more)

### Community 880 - "Approach"
Cohesion: 0.20
Nodes (9): Approach, Architecture, Color Mapping, Conversion Strategy, Design: Fix Dark Theme Issues Across Portal Pages, Files to Modify, Risks, Status Badges (active/inactive) (+1 more)

### Community 881 - "Tasks: Fix Dark Theme Issues Across Portal Pages"
Cohesion: 0.20
Nodes (9): Overview, Task 1: Fix Users Page ✓, Task 2: Fix Tenants Page ✓, Task 3: Fix Model Registry Page ✓, Task 4: Fix Chat Page ✓, Task 5: Fix Documents Page ✓, Task 6: Fix Imported Documents Page ✓, Tasks: Fix Dark Theme Issues Across Portal Pages (+1 more)

### Community 882 - "2026-09-08-agentic-retrieval-loop/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Configuration and tool-layer support, 2. Loop core, 3. Graph wiring, 4. Loop tests, 5. Security and isolation tests, 6. Flag and topology tests, 7. Eval integration, 8. Rollout measurement (+1 more)

### Community 883 - "2026-09-08-annotator-dashboard-ux-refinements/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Reuse existing `DashboardData` fields for the richer copy, no new fields, Decision 2: Fix `bar` by threading `bar_pct` out of `_annotator_side_panel`, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 884 - "2026-09-08-app-shell-ui-cleanup/design.md"
Cohesion: 0.20
Nodes (9): Context, Currently-In-Force ADRs, Decision 1: Remove `demoRole` state rather than relocating it, Decision 2: Wordmark text fix only, no logo/asset changes, Decisions, Goals / Non-Goals, Migration Plan, Open Questions (+1 more)

### Community 885 - "2026-09-08-bounded-sql-retry-loop/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Configuration, 2. Attempt model and outcome classification, 3. Bounded tenant entity profile, 4. Feedback construction, 5. The bounded loop, 6. Wiring: sink, failure propagation, trace, 7. Tests — `tests/test_chat_api_sql_retry.py`, 8. Tests — integration and regression (+1 more)

### Community 886 - "Requirement: RAG chat endpoint"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: RAG chat endpoint, Scenario: Chat with document context query, Scenario: Chat with existing conversation, Scenario: Chat with NER query, Scenario: Chat with simple entity count query, Scenario: Chat without authentication, Scenario: Document context sent to the LLM identifies its source document by name (+1 more)

### Community 887 - "Requirement: Internal inference endpoint"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Internal inference endpoint, Scenario: Confidence is a calibrated probability on the base-model path, Scenario: Confidence is a calibrated probability on the fine-tuned path, Scenario: Inference falls back to base model when no tenant model exists, Scenario: Inference falls back to base model when tenant model fails to load, Scenario: Inference returns 403 when JWT is missing, Scenario: Inference returns predictions from fine-tuned model with custom labels (+1 more)

### Community 888 - "Requirement: Generated SQL executes under a least-privilege role"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Execution role is server-controlled, Requirement: Generated SQL executes under a least-privilege role, Scenario: Generated SQL cannot read cross-tenant relations even if validation is bypassed, Scenario: Legitimate tenant-scoped query succeeds under the restricted role, Scenario: Restricted role cannot write, Scenario: Role cannot be selected by generated SQL, Scenario: Role is applied without a tool argument (+1 more)

### Community 889 - "Requirement: Base model confirmation gate on extraction runs"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Base model confirmation gate on extraction runs, Scenario: Batch Runs shows confirmation dialog when only the base model is available, Scenario: Confirming the dialog proceeds with the base-model extraction, Scenario: Confirming the dialog proceeds with the batch run, Scenario: Declining the dialog cancels the batch run, Scenario: Declining the dialog cancels the Playground run, Scenario: Playground run proceeds without a dialog when a fine-tuned model is promoted (+1 more)

### Community 890 - "2026-09-08-observability-foundation/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Dependencies and configuration, 2. Shared observability module, 3. Local observability stack, 4. Service conversion — one service at a time, 5. Correlation propagation, 6. Close the sensitive-content leak, 7. Traces and metrics, 8. Documentation (+1 more)

### Community 891 - "Requirement: Orchestrated configuration is measured against the direct baseline"
Cohesion: 0.20
Nodes (9): ADDED Requirements, MODIFIED Requirements, Requirement: Evaluation executes through the tool layer, Requirement: Orchestrated configuration is measured against the direct baseline, Scenario: Capability errors are recorded, not fatal, Scenario: Configuration fields match the orchestrator's budgets, Scenario: Eval run invokes the capability layer, Scenario: Orchestrated configuration appears in the report (+1 more)

### Community 892 - "2026-09-08-redesign-retrieval-orchestration/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Retrieval layer: one semantic capability with internal scope, 2. Orchestrator core in `src/shared/retrieval/orchestrator.py`, 3. Guardrail as a domain filter, 4. Graph rewiring, 5. Remove retrieval-time NER, 6. Remove the legacy path and feature flags, 7. Eval harness retarget, 8. Downstream and cross-cutting (+1 more)

### Community 893 - "Requirement: Centralized retrieval configuration"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Centralized retrieval configuration, Scenario: Absent override falls back to global settings, Scenario: Configuration is overridable via environment variable, Scenario: Default configuration matches prior hardcoded behavior, Scenario: Existing call sites are unaffected, Scenario: HybridRetriever's per-source candidate count is bounded, Scenario: Overrides do not mutate global settings (+1 more)

### Community 894 - "2026-09-08-retrieval-tools-and-eval/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Retrieval configuration override (retrieval-core), 2. Tool layer foundation (retrieval-tools), 3. Document retrieval tools (retrieval-tools), 4. Entity retrieval tool (retrieval-tools), 5. Golden set and corpus fixtures (retrieval-eval), 6. Metrics (retrieval-eval), 7. Eval runner, matrix, and report (retrieval-eval), 8. Baseline and regression gate (retrieval-eval) (+1 more)

### Community 895 - "2026-09-08-tenant-pluggable-data-foundation/tasks.md"
Cohesion: 0.20
Nodes (9): 1. Hygiene — no behaviour change, 2. Content-store boundary, 3. Ingestion boundary and upload adapter, 4. Processing pipeline corrections, 5. Retention lifecycle, 6. Schema — provenance, retention, visibility, 7. Control plane — integration profiles, 8. Architectural invariants (+1 more)

### Community 896 - "Requirement: Safe activation and concurrent capability limits"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Safe activation and concurrent capability limits, Requirement: Tenant-admin-managed finite Azure connections, Scenario: Cross-tenant connection access is denied, Scenario: Duplicate active provider is rejected, Scenario: Failed prerequisite blocks activation, Scenario: Independent approved connections activate concurrently, Scenario: Non-administrator is denied (+1 more)

### Community 897 - "Requirement: Only platform default adapters are executable in this change"
Cohesion: 0.20
Nodes (9): MODIFIED Requirements, Requirement: Only platform default adapters are executable in this change, Requirement: Profiles are developer-managed, Scenario: A non-default selection cannot be activated, Scenario: A non-default selection may be recorded, Scenario: An approved Azure connection can execute after activation, Scenario: Ingestion always uses executable adapters, Scenario: Tenant administrators manage only approved Azure connections (+1 more)

### Community 898 - "spec-driven-verified OpenSpec Schema"
Cohesion: 0.20
Nodes (9): Activate, ADR conventions, Change folder structure, Related documentation, spec-driven-verified OpenSpec Schema, Spec format, Stage Gates, verification.md sections (+1 more)

### Community 899 - "Requirement: Role Navigation Matrix"
Cohesion: 0.20
Nodes (9): ADDED Requirements, Requirement: Role Navigation Matrix, Requirement: Screen Title Map, Scenario: annotator nav, Scenario: business_user nav, Scenario: known screen lookup, Scenario: system_admin nav, Scenario: tenant_admin nav (+1 more)

### Community 900 - "Requirements"
Cohesion: 0.20
Nodes (9): Portal Annotation Workspace, Purpose, Requirement: Char-Offset to Token-Index Conversion, Requirement: Task Display Name, Requirements, Scenario: Multi-token span covers correct token range, Scenario: Task queue shows document filename, Scenario: Token index maps to correct char offsets (+1 more)

### Community 901 - "portal-containerization Specification"
Cohesion: 0.20
Nodes (9): portal-containerization Specification, Purpose, Requirement: Portal Compose Service, Requirement: Portal Multi-Stage Docker Build, Requirements, Scenario: Portal can reach the gateway API, Scenario: Portal image builds successfully, Scenario: Portal starts as part of the compose stack (+1 more)

### Community 902 - "TestChatEndpointTurnShape"
Cohesion: 0.42
Nodes (3): asyncio, verification.md rows 16, 17, 20, 21 — the RAG chat endpoint's existing…, TestChatEndpointTurnShape

### Community 903 - "database.py"
Cohesion: 0.03
Nodes (110): get_db(), AsyncSession, Request, Routed through EngineResolver (ADR-017)., handle_extraction_completed(), task, refresh_analytics_materialized_views(), get_session() (+102 more)

### Community 904 - "test_local_compose_delivery_evidence.py"
Cohesion: 0.23
Nodes (12): _chain_heads(), _compose(), Path, Local Compose delivery evidence (CAP-6, ADR-014). Hermetic by design: every…, _revisions(), test_app_service_host_ports_are_unique(), test_chain_check_rejects_branch_and_broken_link(), test_db_init_applies_migrations_before_app_services() (+4 more)

### Community 905 - "test_entity_resolver.py"
Cohesion: 0.20
Nodes (6): entity_schema(), fixture, Covers verification.md rows 63, 64. No full user message is logged (the…, TestPersonTypes, TestResolutionLogging, usefixtures

### Community 906 - "ADDED Requirements"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: .env Excluded from Version Control, Requirement: Environment Configuration Loading, Requirement: Environment Variable Documentation, Scenario: .env.example documents all settings, Scenario: .env is gitignored, Scenario: Settings fall back to defaults when .env missing, Scenario: Settings load from .env file

### Community 907 - "ADDED Requirements"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: GPU Job Monitoring, Requirement: Tenant Detail View, Requirement: Tenant Management Dashboard, Scenario: System Admin creates tenant via UI, Scenario: System Admin views all training jobs, Scenario: System Admin views tenant dashboard, Scenario: System Admin views tenant details

### Community 908 - "2026-06-09-sm-02-document-ingestion/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Service Scaffolding & Shared Code, 2. Database Migrations, 3. MinIO Blob Storage, 4. Document Upload Endpoint, 5. Async OCR Worker, 6. Document CRUD Endpoints, 7. Tests, 8. Verification & Evidence

### Community 909 - "2026-06-10-sm-03-annotation-workspace/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Service Scaffolding & Shared Code, 2. Database Migrations, 3. Span CRUD Endpoints, 4. Pre-labeling, 5. Annotation Task Management, 6. Annotation Export, 7. Tests, 8. Verification & Evidence

### Community 910 - "2026-06-15-sm-05-extraction-engine/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Setup & Scaffolding, 2. Model Serving — Inference Endpoint, 3. Extraction Service — Real-time Extraction API, 4. Extraction Service — Batch Extraction, 5. Extraction Service — Entity Query & Review, 6. Model Warmup on Promotion, 7. Gateway Routing, 8. Verification & Evidence

### Community 911 - "Requirement: User Authentication"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: User Authentication, Scenario: Logout clears the refresh token cookie, Scenario: Token refresh via cookie succeeds and sets new cookie, Scenario: Token refresh with no cookie returns 401, Scenario: User accesses API with expired token, Scenario: User logs in with incorrect password, Scenario: User logs in with valid credentials and receives cookie

### Community 912 - "2026-06-16-portal-auth/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Gateway Backend — Set-Cookie on Auth Endpoints, 2. Auth Context Rewrite, 3. Auth Fetch Interceptor Rewrite, 4. Login Page, 5. RequireAuth Guard, 6. Unit Tests, 7. Build and Type Verification, 8. Verification & Evidence

### Community 913 - "Requirement: Authenticated Route Group Layout"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Admin Sub-Layout Role Guard, Requirement: Authenticated Route Group Layout, Scenario: authenticated access renders shell, Scenario: existing admin URLs unchanged, Scenario: non-admin role blocked from /admin/*, Scenario: system_admin accesses admin route, Scenario: unauthenticated access redirects to login

### Community 914 - "2026-06-16-remove-tid-from-url/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Extraction Service — Remove `{tid}` from Endpoint URLs, 2. Model Serving — Remove `{tid}` from Internal Endpoint URLs, 3. Callers — Update URL Construction, 4. Gateway — Update Extraction Proxy, 5. Tests — Update Test URL Paths, 6. Documentation, 7. ADR — Record Endpoint URL Change, 8. Verification & Evidence

### Community 915 - "Requirement: Batch extraction"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Batch extraction, Requirement: Get extraction run status, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction skips already-extracted documents, Scenario: Get extraction run status, Scenario: Get extraction run status of completed run, Scenario: Trigger batch extraction

### Community 916 - "2026-06-17-fix-worker-text-shadowing/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: Rename `text` → `doc_text` at both assignment sites, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 917 - "2026-06-19-fix-postgres-persistence-and-db-init/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Postgres Named Volume, 2. db-init One-Shot Service, 3. Service Dependency Wiring, 4. Smoke Test — Fresh Stack, 5. Smoke Test — Persistence Cycle, 6. Smoke Test — Reset Behaviour, 7. Smoke Test — Fail-Fast Behaviour, 8. Verification & Evidence

### Community 918 - "Requirement: Topbar Layout"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Topbar Layout, Scenario: dark mode toggle switches theme, Scenario: role-switcher hidden in production mode, Scenario: role-switcher visible in demo mode, Scenario: screen title matches pathname, Scenario: search placeholder is non-interactive, Scenario: Topbar remains visible after scrolling

### Community 919 - "Requirement: Multi-Token Drag Span Creation"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Multi-Token Drag Span Creation, Scenario: Drag across tokens creates a multi-token span, Scenario: Drag direction is agnostic (right-to-left = left-to-right), Scenario: Drag ending on an already-confirmed token is blocked, Scenario: Drag preview highlights range during drag, Scenario: Drag while unarmed does not create a span, Scenario: Single-click (same token mousedown and mouseup) still creates a single-token span

### Community 920 - "2026-06-22-annotation-ui-fixes/tasks.md"
Cohesion: 0.22
Nodes (8): 1. DB Migration — BIO Tag Column, 2. Annotation Service — BIO Tag Storage, 3. Annotation Service — Export Reads Stored Tags, 4. AppShell — Sticky Navbar, 5. Annotation Workspace — Quick UX Fixes (Deselect, Mark Complete, Task Name, Focus Toggle), 6. Annotation Workspace — Fullscreen Focus Mode, 7. Drag-to-Annotate, 8. Verification & Evidence

### Community 921 - "Requirement: Task Status Lifecycle"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Task Status Lifecycle, Scenario: First span creation via token click triggers in-progress transition, Scenario: In-progress transition fires only once per session, Scenario: Mark Complete becomes enabled when spans exist, Scenario: Mark Complete button is visible but disabled with no spans, Scenario: Mark Complete transitions task to completed, Scenario: Promoting a suggestion triggers in-progress transition

### Community 922 - "2026-06-23-fix-chat-api-docker-url/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: Full URL setting matching existing pattern, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 923 - "2026-06-24-sp-07/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Types and Utilities, 2. Data Hooks, 3. Job List Component, 4. Detail Panel Component, 5. Submit Job Slide-Over, 6. Action Buttons (Role-Gated), 7. Training Jobs Page Integration, 8. Verification & Evidence

### Community 924 - "2026-06-29-remove-submit-training-job-button/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: Role check at the page level, not inside the component, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 925 - "Requirement: Batch Runs Tab — Batch Extraction Management"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Batch Runs Tab — Batch Extraction Management, Scenario: Batch Runs tab lists existing runs, Scenario: In-progress runs poll for status updates, Scenario: Run history persists across page reload, Scenario: Selecting a batch run shows detail, Scenario: Status pills use correct visual styles, Scenario: Triggering a new batch run

### Community 926 - "Requirement: Pre-labeling"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Pre-labeling, Scenario: List suggested spans, Scenario: Pre-label a processed document, Scenario: Pre-label longest match wins for overlapping examples, Scenario: Pre-label matching is case-insensitive, Scenario: Pre-label replaces existing suggestions, Scenario: Promote a suggested span to confirmed

### Community 927 - "MODIFIED Requirements"
Cohesion: 0.22
Nodes (8): analytics-ui, MODIFIED Requirements, Requirement: Ad-Hoc Query Controls, Requirement: Error State Handling, Scenario: Dashboard API error shows error banner, Scenario: Filter controls execute query and show results, Scenario: Query API error shows error banner, Scenario: Query with no results shows empty state

### Community 928 - "Requirement: Auth Context Provider"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Auth Context Provider, Scenario: Logout clears cached query data, Scenario: Logout clears user and calls logout endpoint, Scenario: On-mount refresh failure leaves user as null, Scenario: On-mount refresh restores session from cookie, Scenario: Successful login sets user and stores token in memory, Scenario: useAuth throws when called outside AuthProvider

### Community 929 - "Requirement: Tenant-scoped migrations propagate to existing tenant schemas"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Tenant-scoped migrations propagate to existing tenant schemas, Requirement: The `training_jobs.error_message` column is backfilled onto the template and every existing tenant schema, Scenario: A new column is added to a tenant-scoped table, Scenario: A schema that already has the column is unaffected, Scenario: An inactive tenant's schema is still updated, Scenario: Re-running the migration DDL is a no-op, Scenario: `tenant_template` and existing tenants gain the missing column

### Community 930 - "Requirement: Log training run to MLflow Tracking"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Log training run to MLflow Tracking, Requirement: Save model artifacts, Scenario: Artifacts are stored after training, Scenario: MLflow run starts when training begins, Scenario: Model artifacts are logged on completion, Scenario: Per-epoch metrics are logged to MLflow, Scenario: Training failure logs error to MLflow

### Community 931 - "Tasks: Model Registry Promote"
Cohesion: 0.22
Nodes (8): Files to Modify, Implementation Order, Pre-Flight, Task 1: Fix `list_model_versions` to return all versions, Task 2: Fix `_update_job_progress` to JSON-serialize dict values, Task 3: Fix `model_versions` status lifecycle in training worker, Task 4: Add verification tests, Tasks: Model Registry Promote

### Community 932 - "Requirement: Model Registry URL is configurable and targets the correct in-network port"
Cohesion: 0.22
Nodes (8): MODIFIED: Label list resolution includes tenant_id query parameter, MODIFIED Requirements, MODIFIED: System admin inter-service call includes tenant_id query parameter, Requirement: Model Registry URL is configurable and targets the correct in-network port, Scenario: A misconfigured or unreachable registry URL still falls back to the base model, Scenario: Registry URL defaults to the correct port for bare-metal dev, Scenario: Registry URL is overridden to the Docker-internal port, Scenario: Registry URL is read from settings, not hardcoded

### Community 933 - "2026-07-17-fix-seed-promoted-model-conflict/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: Add existence check before insert, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 934 - "Requirement: Fixture setup scripts refuse non-test databases"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Explicit opt-in override for the fixture guard, Requirement: Fixture setup scripts refuse non-test databases, Scenario: Override permits a non-standard test database name, Scenario: Script refuses to run against the development database, Scenario: Script runs against a test database, Scenario: The guard reads the URL actually used, not the default, Scenario: Unset override leaves the guard in force

### Community 935 - "Requirement: Document Upload"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Document Upload, Scenario: Upload a PDF document, Scenario: Upload an unsupported file type, Scenario: Upload exceeds file size limit, Scenario: Upload with an explicit training purpose, Scenario: Upload with an invalid purpose value is rejected, Scenario: Upload without a purpose field defaults to query

### Community 936 - "Requirement: Dark Theme Consistency Across Portal Pages"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Dark Theme Consistency Across Portal Pages, Scenario: Chat Page Dark Mode, Scenario: Documents Page Dark Mode, Scenario: Imported Documents Page Dark Mode, Scenario: Model Registry Page Dark Mode, Scenario: Tenants Page Dark Mode, Scenario: Users Page Dark Mode

### Community 937 - "Requirement: Tool results render into bounded LLM observations"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Tool context carries remaining execution budget, Requirement: Tool results render into bounded LLM observations, Scenario: Absent deadline preserves existing behaviour, Scenario: Chunk results render with follow-up identity, Scenario: Error result renders as an error observation, Scenario: Expired deadline denies the call before any I/O, Scenario: Rendering respects the character limit and preserves results

### Community 938 - "Requirement: Per-Entity-Type Minimum Dataset Gate"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Per-Entity-Type Minimum Dataset Gate, Scenario: both gates apply independently, Scenario: entity type with zero spans blocks submission, Scenario: gate is inert at its default, Scenario: inactive entity types are excluded from the gate, Scenario: submission accepted when every active type meets the minimum, Scenario: submission rejected when one entity type falls short

### Community 939 - "2026-09-08-audit-log-page/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Data Model & Migration, 2. Backend: Audit Service & API, 3. Backend: Wire Audit Recording at Action Sites, 4. Frontend: Hook & Data Fetching, 5. Frontend: Audit Log Page, 6. Backend: Tests, 7. Frontend: Tests, 8. Verification & Evidence

### Community 940 - "Requirement: SQL query generation and validation"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: SQL query generation and validation, Scenario: Failed query is recovered within the attempt budget, Scenario: Generation context carries bounded tenant entity values, Scenario: Malicious SQL is rejected, Scenario: Query exceeds timeout, Scenario: Query with non-whitelisted table is rejected, Scenario: Valid SQL query is executed

### Community 941 - "2026-09-08-chat-auto-titles-and-rename/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Backend: title derivation helper, 2. Backend: wire title generation into conversation creation, 3. Backend: rename endpoint, 4. Backend tests, 5. Frontend: sidebar rename UI, 6. Frontend: wire rename to API, 7. Frontend tests, 8. Verification & Evidence

### Community 942 - "2026-09-08-context-assembly-pipeline/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Configuration, 2. ContextAssembler — Budget, 3. ContextAssembler — Deduplication, 4. ContextAssembler — Provenance, 5. Wire the Graph Path, 6. Wire the Legacy Path, 7. End-to-End & Regression, 8. Verification & Evidence

### Community 943 - "Requirement: Batch Document-Selection Modal — Bulk Selection"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Batch Document-Selection Modal — Bulk Selection, Scenario: Clearing Select all deselects eligible documents without affecting disabled ones, Scenario: Run extraction submits only eligible selected documents, Scenario: Select all is disabled when there are no eligible documents, Scenario: Select all reflects the current selection state, Scenario: Select all selects every eligible document and excludes already-extracted ones, Scenario: Unextracted documents are selectable

### Community 944 - "2026-09-08-fix-batch-runs-scroll-layout/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: Bound the run list column height with `max-height` + `overflow-y: auto`, not a page-level flex/`h-screen` restructure, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 945 - "2026-09-08-harden-chat-pipeline-correctness/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Security — table-reference resolution, 2. Security — least-privilege execution role, 3. Error contract — RetrievalStatus end to end, 4. Correctness — multi-subject entity resolution, 5. Correctness — SQL defect detection, completeness, and recovery, 6. Retrieval and context assembly, 7. Orchestration contract and evaluation, 8. Verification & Evidence

### Community 946 - "2026-09-08-langgraph-orchestration/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Gate — dependency resolution, 2. Baseline — golden transcripts before any port, 3. Retrieval seam — remove per-request state from the singleton, 4. Graph — state and nodes, 5. Graph — topology and adapter, 6. Parity and isolation verification, 7. Fill verification artifacts, 8. Verification & Evidence

### Community 947 - "2026-09-08-multi-document-upload/proposal.md"
Cohesion: 0.22
Nodes (8): Capabilities, Decisions (confirmed), Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 948 - "2026-09-08-multi-document-upload/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Baseline, 2. Hook: additive cancel support, 3. Component: multi-file selection, 4. Component: batch state and sequential upload, 5. Component: progress, summary, cancel UI, 6. Tests, 7. Regression guard, 8. Verification & Evidence

### Community 949 - "Requirement: Message thread display"
Cohesion: 0.22
Nodes (8): MODIFIED Requirements, Requirement: Message thread display, Scenario: Business user sees feedback controls on eligible answer messages only, Scenario: Non-business_user does not see feedback controls, Scenario: Rated message stays fixed after page refresh, Scenario: Rating a message fixes the selection, Scenario: Send message and receive response, Scenario: Source citations are expandable

### Community 950 - "2026-09-08-tenant-pluggable-data-foundation/proposal.md"
Cohesion: 0.22
Nodes (8): Capabilities, Impact, Modified Capabilities, Named follow-on changes, New Capabilities, Open Questions, What Changes, Why

### Community 951 - "templates/design.md"
Cohesion: 0.22
Nodes (8): Context, Currently-In-Force ADRs, Decision 1: <!-- title -->, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 952 - "Requirement: Authenticated Route Group Layout"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Admin Sub-Layout Role Guard, Requirement: Authenticated Route Group Layout, Scenario: authenticated access renders shell, Scenario: existing admin URLs unchanged, Scenario: non-admin role blocked from /admin/*, Scenario: system_admin accesses admin route, Scenario: unauthenticated access redirects to login

### Community 953 - "Requirement: OPTIONS requests bypass authentication middleware"
Cohesion: 0.22
Nodes (8): CORS Preflight Passthrough, Purpose, Requirement: OPTIONS requests bypass authentication middleware, Requirements, Scenario: Browser preflight to annotation service succeeds without cache, Scenario: Browser preflight to document service succeeds, Scenario: Non-OPTIONS requests still require authentication, Scenario: OPTIONS request receives X-Request-ID response header

### Community 954 - "Requirement: Document Content Hashing and Duplicate Identification"
Cohesion: 0.22
Nodes (9): Requirement: Document Content Hashing and Duplicate Identification, Scenario: A soft-deleted document is not reported as a duplicate, Scenario: Different content is not reported as a duplicate, Scenario: Different filenames with identical content are recognised as identical content, Scenario: Document metadata exposes the stored checksum, Scenario: Duplicate detection does not cross tenant boundaries, Scenario: Duplicate upload does not modify the original document, Scenario: Identical content produces the same deterministic hash (+1 more)

### Community 955 - "Requirement: RequireAuth Route Guard"
Cohesion: 0.22
Nodes (8): Purpose, Require Auth, Requirement: RequireAuth Route Guard, Requirements, Scenario: Authenticated access renders children, Scenario: Role-restricted access with matching role renders children, Scenario: Role-restricted access with non-matching role redirects to dashboard, Scenario: Unauthenticated access redirects to login

### Community 956 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 957 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Canonical contract JSON with explicit join graph; fingerprint over canonical form, Decision 2: sqlparse-based AST validator, separate from the platform whitelist, Decision 3: Drift-gated connector with read-only transaction, row cap, timeout, Decision 4: Tenant-isolated schema index for context only, Decision 5: Gateway contract-admin routes reuse CAP-2 auth and tenant binding, Decisions (+4 more)

### Community 958 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Canonical contract JSON with explicit join graph; fingerprint over canonical form, Decision 2: sqlparse-based AST validator, separate from the platform whitelist, Decision 3: Drift-gated connector with read-only transaction, row cap, timeout, Decision 4: Tenant-isolated schema index for context only, Decision 5: Gateway contract-admin routes reuse CAP-2 auth and tenant binding, Decisions (+4 more)

### Community 959 - "2026-09-10-cap-5-tenant-data-source-administration-portal/design.md"
Cohesion: 0.15
Nodes (12): Context, Currently-In-Force ADRs, Decision 1: Routes under `(auth)/settings/data-sources`, Decision 2: Relative-URL data layer through `authFetch`, no `resolveUrl` change, Decision 3: Reuse `ui` primitives, add `data-sources` components, Decision 4: Safe-type boundary at the TypeScript layer, Decision 5: Fixture-backed verification, live Azure out of scope, Decisions (+4 more)

### Community 960 - "2026-06-08-env-config-setup/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 961 - "2026-06-08-sm-01-identity-tenant-entity-config/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 962 - "2026-06-08-tenant-admin-user-mgmt/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 963 - "2026-06-09-sm-02-document-ingestion/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 964 - "2026-06-10-sm-03-annotation-workspace/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 965 - "2026-06-11-sm-04-training-pipeline/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 966 - "2026-06-11-training-approval-gate/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 967 - "2026-06-12-mlflow-integration/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 968 - "2026-06-15-promote-warmup-integration/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 969 - "Requirement: Promote model version"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Promote model version, Scenario: Promote a completed model via MLflow with warmup, Scenario: Promote a non-completed model returns 422, Scenario: Promote as annotator returns 403, Scenario: Promote replaces previously promoted version via MLflow, Scenario: Warmup failure does not fail promote

### Community 970 - "2026-06-15-sm-05-extraction-engine/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 971 - "2026-06-16-portal-auth/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 972 - "2026-06-16-portal-foundation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 973 - "2026-06-16-portal-shell/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 974 - "2026-06-16-remove-tid-from-url/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 975 - "2026-06-17-add-celery-extraction-worker/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 976 - "2026-06-17-add-login-dashboard-transition/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 977 - "2026-06-17-fix-batch-extraction-worker/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 978 - "2026-06-17-fix-extraction-run-persistence/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 979 - "2026-06-17-fix-worker-host-routing/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 980 - "2026-06-17-fix-worker-text-shadowing/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 981 - "2026-06-17-portal-dashboard/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 982 - "2026-06-18-default-base-model/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 983 - "2026-06-18-dockerize-backend-services/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 984 - "2026-06-18-enforce-env-secrets/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 985 - "2026-06-18-fix-users-tenant-resolution/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 986 - "2026-06-18-mlflow-test-verification/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 987 - "2026-06-19-fix-cors-preflight-middleware/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 988 - "2026-06-19-fix-postgres-persistence-and-db-init/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 989 - "2026-06-19-sidebar-action-menu/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 990 - "2026-06-22-annotation-ui-fixes/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 991 - "2026-06-22-fix-promote-inprogress-transition/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 992 - "2026-06-22-sp-05-annotation-workspace/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 993 - "2026-06-23-fix-chat-api-docker-url/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 994 - "2026-06-23-fix-chat-page-auth/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 995 - "2026-06-23-sp-06-rag-chatbot/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 996 - "2026-06-23-tenant-from-jwt-in-chat-api/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 997 - "2026-06-24-analytics-and-reporting/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 998 - "2026-06-24-sp-06/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 999 - "2026-06-24-sp-07/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1000 - "2026-06-25-align-dashboard-to-mockup/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1001 - "2026-06-25-align-dashboard-to-mockup/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Dashboard Page Structural Changes, 2. DashboardHero Visual Alignment, 3. StatCard Layout Changes, 4. ActivityPanel Row Style Changes, 5. MetricsPanel Layout Changes, 6. Update Component Tests, 7. Verification & Evidence

### Community 1002 - "2026-06-25-annotation-mockup-alignment/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1003 - "2026-06-25-app-shell-exact-mockup/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1004 - "2026-06-25-app-shell-v2/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1005 - "2026-06-25-app-shell-v2/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Global Styles — `menuPop` keyframe, 2. Sidebar — User Strip Trigger (Sidebar.tsx), 3. Sidebar — Tenant Pill Caret, 4. Topbar — Demo Role Switcher `AS` Label (Topbar.tsx), 5. Dashboard Hero — Variant B (`heroVariant` helper + DashboardHero), 6. Tests, 7. Verification & Evidence

### Community 1006 - "2026-06-25-fix-entity-types-api-alignment/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1007 - "2026-06-25-sp05-annotation-workspace/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1008 - "2026-06-25-sp-04-dashboard/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1009 - "2026-06-25-sp-08-documents/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1010 - "2026-06-25-sp-09-entity-types/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1011 - "2026-06-29-assign-annotation-tasks/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1012 - "2026-06-29-assign-annotation-tasks/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Data Fetching Hooks, 2. AssignTaskForm Component, 3. Task Queue Panel Integration, 4. AnnotationTask Type Update, 5. Component Tests — task-assignment-ui Scenarios, 6. Component Tests — portal-annotation Delta Scenarios, 7. Verification & Evidence

### Community 1013 - "2026-06-29-remove-submit-training-job-button/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1014 - "2026-06-29-sp-10-model-registry/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1015 - "2026-06-29-sp-10-model-registry/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Types, 2. API Hooks, 3. ModelVersionCard Component, 4. ModelDetailPanel Component, 5. ModelRegistryPage, 5b. Base Model (Version 0) Entry, 6. Verification & Evidence

### Community 1016 - "2026-06-30-fix-dashboard-queries/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1017 - "2026-07-01-annotation-file-upload/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1018 - "2026-07-01-portal-extraction-page/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1019 - "2026-07-01-portal-extraction-page/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Scaffold, 2. API Hooks, 3. ExtractionPage — Shell and Tab Navigation, 4. PlaygroundTab Component, 5. BatchRunsTab Component, 6. EntityReviewTab Component, 7. Verification & Evidence

### Community 1020 - "2026-07-02-batch-extraction-run-history/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1021 - "2026-07-02-fix-prelabel-keyword-search/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1022 - "2026-07-06-fix-analytics-materialized-views/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1023 - "2026-07-07-add-annotation-import-button/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1024 - "2026-07-07-add-annotation-import-button/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Backend — Partial Import Support, 2. Frontend — Client-Side File Parser, 3. Frontend — Upload Hook, 4. Frontend — Preview Slide-Over, 5. Frontend — Result Slide-Over, 6. Frontend — Import Button and Integration, 7. Verification & Evidence

### Community 1025 - "2026-07-07-fix-analytics-query-feedback/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1026 - "2026-07-08-fix-system-admin-training-queue-bugs/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1027 - "2026-07-08-fix-system-admin-training-queue-bugs/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Backend: surface tenant_id on training job responses, 2. Backend: System Admin cross-tenant detail and list access, 3. Frontend: thread tenant_id through selection, detail, and actions, 4. Frontend: clear query cache on logout, 5. Gateway: fix dashboard summary transaction cascade, 6. Type-level verification, 7. Verification & Evidence

### Community 1028 - "2026-07-08-fix-tenant-schema-drift-and-training-worker-config/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1029 - "2026-07-08-remove-training-span-gate/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1030 - "2026-07-08-review-imported-annotations/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1031 - "2026-07-09-fix-mlflow-model-logging/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1032 - "ADDED Requirements"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: MLflow client-server version compatibility, Requirement: ONNX artifact completeness, Requirement: Retry guard prevents duplicate execution, Scenario: MLflow client version matches server version range, Scenario: ONNX file exists in exported artifacts, Scenario: Worker skips completed job

### Community 1033 - "2026-07-13-fix-model-loading-and-label-mapping/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Decisions, Impact, Modified Capabilities, New Capabilities, What Changes, Why

### Community 1034 - "2026-07-13-redesign-training-jobs-ui/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1035 - "2026-07-16-fix-model-serving-tenant-query/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1036 - "2026-07-17-fix-seed-promoted-model-conflict/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1037 - "2026-07-24-chunk-metadata-ingest/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1038 - "2026-07-24-retrieval-foundation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1039 - "2026-07-27-clean-rebuild-and-schema-hardening/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1040 - "2026-07-27-document-purpose-scoping/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1041 - "2026-07-27-hybrid-retrieval-hnsw/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1042 - "Requirement: pgvector semantic search"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: pgvector semantic search, Scenario: Chat retrieves relevant document context for a lexical (exact-term) query, Scenario: Citation includes page number when the chunk has one, Scenario: Citation page number is null for chunks without metadata, Scenario: Semantic search returns relevant chunks, Scenario: Semantic search with empty corpus

### Community 1043 - "2026-07-29-annotation-completion-workflow/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1044 - "2026-09-08-agentic-retrieval-loop/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1045 - "2026-09-08-annotator-dashboard-cards-and-per-entity-readiness/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1046 - "Requirement: Pending Tasks Can Be Started"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Pending Tasks Can Be Started, Scenario: completed remains terminal, Scenario: existing transitions are unchanged, Scenario: pending task can be started, Scenario: pending task cannot skip straight to completed, Scenario: span precondition still guards completion

### Community 1047 - "Requirement: Deep Link to a Specific Task"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Deep Link to a Specific Task, Scenario: no parameter preserves existing behaviour, Scenario: parameter does not override later selection, Scenario: task belonging to another annotator is not selected, Scenario: task parameter pre-selects the task, Scenario: unknown task id falls back to default selection

### Community 1048 - "2026-09-08-annotator-dashboard-ux-refinements/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1049 - "2026-09-08-app-shell-ui-cleanup/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1050 - "2026-09-08-audit-log-page/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1051 - "2026-09-08-audit-log-tenant-filter/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1052 - "2026-09-08-batch-extraction-document-selection/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1053 - "2026-09-08-bounded-sql-retry-loop/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1054 - "2026-09-08-cap-1-add-doc-docx-upload-support/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1055 - "2026-09-08-chat-auto-titles-and-rename/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1056 - "2026-09-08-chat-conversation-and-citations/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1057 - "2026-09-08-chat-response-token-streaming/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1058 - "2026-09-08-cloud-readiness-resilience/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1059 - "2026-09-08-cloud-readiness-resilience/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Foundations, 2. Retry on Dependency Initialization, 3. Readiness and Liveness Endpoints, 4. Configuration Audit, 5. Docker Compose Hygiene, 6. Scenario Verification Tests, 7. Verification & Evidence

### Community 1060 - "2026-09-08-context-assembly-pipeline/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1061 - "2026-09-08-cross-encoder-rerank/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1062 - "Requirement: Cross-encoder reranking endpoint"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Cross-encoder reranking endpoint, Scenario: Rerank reorders candidates by relevance, Scenario: Rerank respects the requested top_k, Scenario: Rerank returns 401 when JWT is missing, Scenario: Rerank with an empty candidate list, Scenario: Reranker model is not held in the per-tenant model cache

### Community 1063 - "2026-09-08-cross-encoder-rerank/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Configuration, 2. Model Serving Rerank Endpoint, 3. Reranker Client, 4. RerankingRetriever, 5. Wire RAGOrchestrator, 6. Regression, 7. Verification & Evidence

### Community 1064 - "2026-09-08-dockerize-portal-and-fix-build-hygiene/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1065 - "ADDED Requirements"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Portal Compose Service, Requirement: Portal Multi-Stage Docker Build, Scenario: Portal can reach the gateway API, Scenario: Portal image builds successfully, Scenario: Portal starts as part of the compose stack, Scenario: Runtime image excludes dev dependencies

### Community 1066 - "2026-09-08-document-content-hash-and-batch-select-all/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1067 - "Requirement: Numeric parsing handles a leading numeral followed by trailing words"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Numeric parsing handles a leading numeral followed by trailing words, Scenario: A merged multi-token duration parses to its full value, Scenario: A numeral followed by prose parses, Scenario: Equivalent surface forms produce equal typed values, Scenario: Existing parses are unchanged, Scenario: Genuinely unparseable values still yield no typed value

### Community 1068 - "2026-09-08-entity-relational-projection/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1069 - "2026-09-08-entity-resolution-disambiguation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1070 - "ADDED Requirements"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: Bounded clarification retry, Requirement: Entity resolution precedes retrieval execution, Scenario: First unresolvable answer re-asks, Scenario: Resolution queries are tenant-scoped, Scenario: Resolution runs before any tool invocation, Scenario: Second unresolvable answer abandons clarification

### Community 1071 - "2026-09-08-entity-view-layer-foundation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1072 - "Requirement: Entity Type Definition"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Entity Type Definition, Scenario: An entity type predating the view layer defaults to multi, Scenario: Cardinality is constrained to the two known values, Scenario: Tenant Admin creates an entity type, Scenario: Tenant Admin updates an entity type, Scenario: Two tenants may share an sql_identifier

### Community 1073 - "2026-09-08-entity-view-layer-foundation/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Baseline, 2. Identifier slugging (everything depends on this), 3. Migration 037, 4. DDL generators (pure functions, no DB), 5. Reconciler, 6. Scope guard, 7. Verification & Evidence

### Community 1074 - "2026-09-08-fix-batch-runs-scroll-layout/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1075 - "2026-09-08-langgraph-orchestration/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1076 - "2026-09-08-model-registry-tenant-scoping-run-naming/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1077 - "2026-09-08-model-registry-tenant-scoping-run-naming/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Database Migration, 2. Backend — Training Job Run Numbers, 3. Backend — Model Version Run Names, 4. Frontend — Model Registry Screen Role Gating, 5. Frontend — Training Jobs Screen Run Names, 6. Frontend — Extraction Base-Model Confirmation Dialog, 7. Verification & Evidence

### Community 1078 - "2026-09-08-normalized-entity-store/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1079 - "Requirement: Internal inference endpoint"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Internal inference endpoint, Scenario: Base-model predictions preserve token order and repeats, Scenario: Inference falls back to base model when no tenant model exists, Scenario: Inference falls back to base model when tenant model fails to load, Scenario: Inference returns 403 when JWT is missing, Scenario: Inference returns predictions from fine-tuned model with custom labels

### Community 1080 - "Requirement: The `document_entities` table exists on the template and every tenant schema"
Cohesion: 0.25
Nodes (7): ADDED Requirements, Requirement: The `document_entities` table exists on the template and every tenant schema, Scenario: Downgrade removes only the new table, Scenario: Inactive tenant schemas are not skipped, Scenario: Raw entity table is untouched, Scenario: Re-running the migration DDL is a no-op, Scenario: Template and existing tenant schemas both receive the table

### Community 1081 - "2026-09-08-observability-foundation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1082 - "2026-09-08-observability-workload-instrumentation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1083 - "2026-09-08-redesign-business-user-dashboard/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1084 - "2026-09-08-redesign-retrieval-orchestration/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1085 - "2026-09-08-redesign-system-admin-dashboard/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1086 - "2026-09-08-redesign-system-admin-dashboard/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Backend: generic audit-event activity feed helper, 2. Backend: Active Users, Training Jobs Running, deterministic Platform Health, 3. Backend: assemble system_admin response and hero copy, 4. Backend: preserve existing failure-isolation and schema-exclusion behavior, 5. Frontend: activity navigation and Platform Health colour, 6. Structural and dead-code review, 7. Verification & Evidence

### Community 1087 - "2026-09-08-relational-only-sql-generation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1088 - "2026-09-08-response-feedback-rating/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1089 - "2026-09-08-retrieval-tools-and-eval/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1090 - "2026-09-08-structured-entity-value-normalization/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1091 - "Requirement: Entity Type Definition"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Entity Type Definition, Scenario: Existing entity types keep working, Scenario: Tenant Admin creates an entity type, Scenario: Tenant Admin declares a structured value kind, Scenario: Tenant Admin updates an entity type, Scenario: Unsupported value kind is rejected

### Community 1092 - "2026-09-08-subject-column-type-convergence/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1093 - "2026-09-08-sysadmin-user-onboarding/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1094 - "2026-09-08-sysadmin-user-onboarding/tasks.md"
Cohesion: 0.25
Nodes (7): 1. Backend: Shared Service Extensions, 2. Backend: Admin User Creation Endpoint, 3. Backend Tests, 4. Frontend: Shared Create User Form, 5. Frontend: Admin Console Create User UI, 6. Frontend Tests, 7. Verification & Evidence

### Community 1095 - "2026-09-08-system-admin-sets-training-params/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1096 - "Requirement: Approve training job"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Approve training job, Scenario: Approve a job that is not pending_approval, Scenario: Approve a pending training job with valid hyperparameters, Scenario: Approve as non-system-admin, Scenario: Approve with invalid hyperparameters, Scenario: Approve without supplying hyperparameters

### Community 1097 - "2026-09-08-tenant-dashboard-workspace-refresh/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1098 - "2026-09-10-cap-2-tenant-scoped-connection-control-plane/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1099 - "Verification Plan"
Cohesion: 0.25
Nodes (7): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, Verification Plan

### Community 1100 - "2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1101 - "Verification Plan"
Cohesion: 0.25
Nodes (7): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, Verification Plan

### Community 1102 - "templates/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1103 - "Requirement: Guardrail — blocked question types"
Cohesion: 0.25
Nodes (8): Requirement: Guardrail — blocked question types, Scenario: Blocked question returns graceful decline, Scenario: Chit-chat and general-knowledge prompts are declined, Scenario: Classifier failure fails open, Scenario: Cross-tenant reference is short-circuited without an LLM call, Scenario: In-domain question proceeds to orchestration, Scenario: Multi-lookup questions are no longer refused, Scenario: Out-of-domain question returns graceful decline

### Community 1104 - "Requirement: Guardrail — source citation enforcement"
Cohesion: 0.25
Nodes (8): Requirement: Guardrail — source citation enforcement, Scenario: Clarification request is not replaced by the guardrail, Scenario: Domain decline keeps its message, Scenario: Empty-sources turn emits no tokens before the fallback, Scenario: Generated answer after selection still requires citations, Scenario: Response with no sources after a retrieval failure, Scenario: Response with no sources after successful empty retrieval, Scenario: Response without sources is rejected

### Community 1105 - "Requirements"
Cohesion: 0.25
Nodes (7): Document Ingestion, Purpose, Requirement: Tenant Context Enforcement, Requirements, Scenario: Authenticated request with valid tenant, Scenario: Request for unknown tenant, Scenario: Request with inactive tenant

### Community 1106 - "Requirement: Convert trained model to ONNX format"
Cohesion: 0.25
Nodes (7): ONNX Conversion, Purpose, Requirement: Convert trained model to ONNX format, Requirements, Scenario: ONNX file is loadable by model-serving layer, Scenario: ONNX file is produced after training, Scenario: ONNX file is uploaded to blob storage

### Community 1107 - "Requirement: Annotation Task Queue"
Cohesion: 0.25
Nodes (8): Requirement: Annotation Task Queue, Scenario: Active task row is highlighted, Scenario: Annotator does not see Assign Task button, Scenario: Annotator sees only assigned tasks, Scenario: Empty queue shows contextual message, Scenario: Selecting a task loads the document, Scenario: Task row shows filename and document metadata, Scenario: Tenant admin sees Assign Task button

### Community 1108 - "Requirement: Prevent re-execution of completed or failed jobs"
Cohesion: 0.25
Nodes (7): Purpose, Requirement: Prevent re-execution of completed or failed jobs, Requirements, Scenario: Job already completed is not re-executed, Scenario: Job already failed is not re-executed, Scenario: Job in non-terminal status proceeds normally, Training Retry Guard

### Community 1109 - "2026-09-11-manual-blob-sync-trigger/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Gateway route enqueues via broker, never runs inline, Decision 2: Manual bypasses cadence, keeps every other guard, Decision 3: Reuse the `_mutate` idempotency wrapper and safe-code shape, Decision 4: Portal control is a thin caller with refreshed status, no polling, Decisions, Goals / Non-Goals (+3 more)

### Community 1110 - "ADDED Requirements"
Cohesion: 0.15
Nodes (12): ADDED Requirements, Requirement: Data source collection and navigation, Requirement: Safe connection lifecycle interface, Requirement: Schema-contract administration interface, Scenario: Activation is blocked safely, Scenario: Administrator filters data sources, Scenario: Collection uses server-backed paging defaults, Scenario: Destructive lifecycle actions require confirmation (+4 more)

### Community 1111 - "C4 Container View — Tenant Self-Service Data Sources"
Cohesion: 0.29
Nodes (6): Boundary Rules, C4 Container View — Tenant Self-Service Data Sources, Containers and External Systems, Data Ownership and Trust Zones, References, Scope and Authority

### Community 1112 - "2026-06-08-tenant-admin-user-mgmt/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Dependencies Layer, 2. New Router Module, 3. Spec & Documentation, 4. Tests, 5. Admin Route Cleanup (scope expansion), 6. Verification & Evidence

### Community 1113 - "2026-06-11-sm-04-training-pipeline/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Training Service Scaffolding, 2. Training Jobs API, 3. Model Registry API, 4. Training Worker, 5. Integration & Migration, 6. Verification & Evidence

### Community 1114 - "Requirement: Log training run to MLflow Tracking"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Log training run to MLflow Tracking, Scenario: MLflow run starts when training begins, Scenario: Model artifacts are logged on completion, Scenario: Per-epoch metrics are logged to MLflow, Scenario: Training failure logs error to MLflow

### Community 1115 - "2026-06-12-mlflow-integration/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Setup & Dependencies, 2. MLflow Infrastructure — Training Worker Integration, 3. Model Registry — MLflow Proxy Implementation, 4. MLflow Infrastructure — Deployment, 5. Testing, 6. Verification & Evidence

### Community 1116 - "Requirement: RequireAuth Route Guard"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: RequireAuth Route Guard, Scenario: Authenticated access renders children, Scenario: Role-restricted access with matching role renders children, Scenario: Role-restricted access with non-matching role redirects to dashboard, Scenario: Unauthenticated access redirects to login

### Community 1117 - "2026-06-17-fix-batch-extraction-worker/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Schema Migration, 2. Worker — Replace HTTP Text Fetch with DB Query, 3. Worker — Fix Idempotency Check, 4. Worker — Populate `document_id` on Entity INSERT, 5. Entity Store — Fix `query_entities` Document Filter, 6. Verification & Evidence

### Community 1118 - "2026-06-17-fix-extraction-run-persistence/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Database Migration, 2. POST Handler — Pre-create Run Row, 3. Celery Worker — Fix Status Updates, 4. Update Tests, 5. Manual Integration Test (requires running Celery + PostgreSQL), 6. Verification & Evidence

### Community 1119 - "Requirement: Batch extraction"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Batch extraction, Scenario: Batch extraction for tenant with no promoted model, Scenario: Batch extraction persists extracted entities, Scenario: Batch extraction skips already-extracted documents, Scenario: Trigger batch extraction

### Community 1120 - "Requirement: Authenticated Route Group Layout"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Authenticated Route Group Layout, Scenario: authenticated access renders shell, Scenario: existing admin URLs unchanged, Scenario: system_admin lands on dashboard (not redirected to /admin), Scenario: unauthenticated access redirects to login

### Community 1121 - "Requirement: Environment Variable Documentation"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Environment Variable Documentation, Scenario: .env.example documents all settings, Scenario: .env.example documents inter-service URL variables, Scenario: .env.example includes docker-compose variables, Scenario: .env.example marks secret fields as required

### Community 1122 - "2026-06-18-dockerize-backend-services/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Root Dockerfile, 2. docker-compose.yml — New Application Services, 3. docker-compose.yml — Update Existing Services, 4. Environment Documentation, 5. Smoke Testing, 6. Verification & Evidence

### Community 1123 - "ADDED Requirements"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: No Hardcoded Secrets in Codebase, Requirement: Test Fixtures Use Isolated Env Injection, Scenario: AGENTS.md documents the no-hardcoded-secrets invariant, Scenario: Source code contains no plaintext secret defaults, Scenario: Test secrets use setdefault and cannot override real env

### Community 1124 - "2026-06-18-enforce-env-secrets/tasks.md"
Cohesion: 0.29
Nodes (6): 1. src/shared/config.py — Remove secret defaults, 2. docker-compose.yml — Replace hardcoded literals with interpolation, 3. .env.example — Add required markers and docker-compose vars, 4. AGENTS.md — Add secret-hygiene invariant, 5. tests/test_env_config.py — Update for removed defaults, 6. Verification & Evidence

### Community 1125 - "Requirement: OPTIONS requests bypass authentication middleware"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: OPTIONS requests bypass authentication middleware, Scenario: Browser preflight to annotation service succeeds without cache, Scenario: Browser preflight to document service succeeds, Scenario: Non-OPTIONS requests still require authentication, Scenario: OPTIONS request receives X-Request-ID response header

### Community 1126 - "Requirement: Role Navigation Matrix"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Role Navigation Matrix, Scenario: annotator nav, Scenario: business_user nav, Scenario: system_admin nav, Scenario: tenant_admin nav

### Community 1127 - "2026-06-24-analytics-and-reporting/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Setup & Shared Infrastructure, 2. Analytics Query API, 3. Analytics Dashboard & Materialized Views, 4. Analytics Export, 5. Analytics UI (Portal), 6. Verification & Evidence

### Community 1128 - "Requirement: Hero Variant B (system_admin dark mesh)"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Hero Variant B (system_admin dark mesh), Scenario: heroVariant helper is pure and testable, Scenario: non-admin roles render Variant A light hero, Scenario: system_admin hero renders Variant B dark mesh, Scenario: Variant B still respects Editorial/Command layout

### Community 1129 - "2026-06-25-sp-09-entity-types/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Types, 2. API Hooks, 3. EntityTypeCard Component, 4. DefineEntityTypeSlideOver Component, 5. EntityTypesPage, 6. Verification & Evidence

### Community 1130 - "Requirement: Dashboard Summary Endpoint"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Dashboard Summary Endpoint, Scenario: annotator summary returns real task data, Scenario: business_user summary returns real extraction data, Scenario: sources map includes all data domains, Scenario: tenant_admin summary returns real data from wired sources

### Community 1131 - "Requirement: Load annotated dataset"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Load annotated dataset, Scenario: Annotation service URL defaults to the correct internal port, Scenario: Annotation service URL is overridable via environment variable, Scenario: Dataset loads successfully, Scenario: Export returns no data

### Community 1132 - "2026-07-08-fix-tenant-schema-drift-and-training-worker-config/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Shared tenant-schema migration helper, 2. Remediation migration for `training_jobs.error_message`, 3. Fix training worker's annotation service URL, 4. Reconcile `seed.py` with `tenant_template`, 5. Live remediation for the already-affected environment, 6. Verification & Evidence

### Community 1133 - "2026-07-08-review-imported-annotations/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Database Migration, 2. Backend: List Endpoint, 3. Backend: Detail & Update Endpoints, 4. Frontend: Imported Documents List View, 5. Frontend: Token-Level Review & Edit, 6. Verification & Evidence

### Community 1134 - "Requirement: Stable Inter-Service Communication via Docker DNS"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Stable Inter-Service Communication via Docker DNS, Scenario: Extraction worker reaches document_service via service name, Scenario: Extraction worker reaches model_serving via service name, Scenario: Model serving reaches training_service via service name at the correct internal port, Scenario: Training service reaches model_serving for warmup via service name

### Community 1135 - "Requirement: Model warmup on promotion"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Model warmup on promotion, Scenario: A slow cold load that exceeds the client timeout still completes in the background, Scenario: First extraction after warmup uses cached model, Scenario: Warmup failure does not fail promote, Scenario: Warmup is triggered on promotion

### Community 1136 - "2026-07-14-model-registry-promote/proposal.md"
Cohesion: 0.29
Nodes (6): Capabilities, Impact, Modified Capabilities, Open Questions, What Changes, Why

### Community 1137 - "Design: Remove Settings Placeholder Copy"
Cohesion: 0.29
Nodes (6): Context, Decision, Design: Remove Settings Placeholder Copy, Implementation Notes, Rationale, Verification

### Community 1138 - "2026-07-24-chunk-metadata-ingest/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1139 - "Requirement: pgvector semantic search"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: pgvector semantic search, Scenario: Citation includes page number when the chunk has one, Scenario: Citation page number is null for chunks without metadata, Scenario: Semantic search returns relevant chunks, Scenario: Semantic search with empty corpus

### Community 1140 - "2026-07-24-chunk-metadata-ingest/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Database Migration, 2. Domain Model & Chunking Changes, 3. Per-Span Ingestion in ocr_worker, 4. DenseRetriever & Citation Wiring, 5. Regression Coverage, 6. Verification & Evidence

### Community 1141 - "2026-07-24-retrieval-foundation/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1142 - "2026-07-24-retrieval-foundation/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Domain Models & Configuration, 2. Shared Chunking Implementation, 3. Retriever Interface & DenseRetriever, 4. Wire Orchestrator to Typed Retrieval, 5. Citation Enrichment Bug Fix, 6. Verification & Evidence

### Community 1143 - "2026-07-27-document-purpose-scoping/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1144 - "Requirement: Retriever interface"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Retriever interface, Scenario: A chat query cannot bypass the purpose restriction, Scenario: DenseRetriever matches existing similarity search behavior, Scenario: rag_orchestrator retrieves via the Retriever interface, Scenario: Retrieval excludes training-purpose chunks

### Community 1145 - "Proposal: Fix Dark Theme Issues Across Portal Pages"
Cohesion: 0.29
Nodes (6): Affected Pages, Impact, Key Tokens to Use, Problem Statement, Proposal: Fix Dark Theme Issues Across Portal Pages, Proposed Solution

### Community 1146 - "2026-07-27-hybrid-retrieval-hnsw/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1147 - "2026-07-27-hybrid-retrieval-hnsw/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Database Migration, 2. SparseRetriever, 3. Retriever Interface Extension & metadata_filter, 4. HybridRetriever & RRF Fusion, 5. Wire RAGOrchestrator, 6. Verification & Evidence

### Community 1148 - "2026-07-29-annotation-completion-workflow/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Backend — terminal completed state, 2. Portal — strip the status switcher from the toolbar, 3. Portal — promote to in-progress on task open, 4. Portal — bottom action bar with Mark as Completed, 5. Cleanup and cross-checks, 6. Verification & Evidence

### Community 1149 - "2026-09-08-annotator-dashboard-ux-refinements/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Backend: stat label rename, 2. Backend: dataset readiness progress and copy, 3. Frontend sanity check (no code change expected), 4. Verification: dashboard-summary-endpoint scenarios, 5. Verification: portal-dashboard scenarios, 6. Verification & Evidence

### Community 1150 - "Requirement: List documents eligible for batch extraction"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: List documents eligible for batch extraction, Scenario: A document re-extracted under a new model version becomes eligible again, Scenario: Eligible documents list as non-admin, Scenario: Eligible documents list excludes non-processed documents, Scenario: Eligible documents list marks already-extracted documents

### Community 1151 - "2026-09-08-batch-extraction-document-selection/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Backend — shared eligibility lookup, 2. Backend — eligible-documents endpoint, 3. Frontend — types and hook changes, 4. Frontend — document-selection modal, 5. Frontend — wire modal into BatchRunsTab, 6. Verification & Evidence

### Community 1152 - "2026-09-08-cap-1-add-doc-docx-upload-support/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Setup, 2. Backend Implementation, 3. Frontend Implementation, 4. Spec Updates, 5. Tests, 6. Verification & Evidence

### Community 1153 - "Requirement: Rename conversation from sidebar"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Rename conversation from sidebar, Scenario: Newly created conversation shows placeholder until first message, Scenario: Rename API failure keeps the previous title, Scenario: User cancels a rename in progress, Scenario: User renames a conversation via the sidebar

### Community 1154 - "Requirement: Message thread display"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Message thread display, Scenario: Citations and rating appear only on completion, Scenario: Failed turn clears the Thinking indicator, Scenario: Send message and receive streamed response, Scenario: Source citations are expandable

### Community 1155 - "2026-09-08-chat-response-token-streaming/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Graph streaming mode, 2. Streaming endpoint on chat_api, 3. Gateway pass-through, 4. Portal streaming client, 5. Regression sweep, 6. Verification & Evidence

### Community 1156 - "2026-09-08-context-assembly-pipeline/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1157 - "2026-09-08-cross-encoder-rerank/design.md"
Cohesion: 0.29
Nodes (6): Context, Decisions, Goals / Non-Goals, Migration Plan, Open Questions, Risks / Trade-offs

### Community 1158 - "2026-09-08-dockerize-portal-and-fix-build-hygiene/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Build Context Hygiene, 2. Portal Containerization, 3. Gateway to chat_api Docker DNS Fix, 4. Root Dockerfile Multi-Stage Conversion, 5. Dead File Cleanup, 6. Verification & Evidence

### Community 1159 - "2026-09-08-document-content-hash-and-batch-select-all/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Backend — content hash helper, 2. Backend — upload persists checksum and identifies duplicates, 3. Backend — schema index, 4. Frontend — Select all and selected count, 5. Regression checks, 6. Verification & Evidence

### Community 1160 - "Requirement: The batch extraction request carries a processing mode"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: The batch extraction request carries a processing mode, Scenario: An unavailable mode surfaces the server's rejection, Scenario: Default mode is transmitted when the user changes nothing, Scenario: The run list reports the mode each run used, Scenario: The selected mode reaches the server

### Community 1161 - "ADDED Requirements"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Each active multi-valued definition receives one row per routed entity, Requirement: Entities matching no definition are written to the EAV store only, Scenario: An undefined type still reaches the system of record, Scenario: Three routed entities produce three rows, Scenario: Two source labels collapsing onto one definition do not raise

### Community 1162 - "2026-09-08-merge-bio-entity-display/proposal.md"
Cohesion: 0.29
Nodes (6): Capabilities, Impact, Modified Capabilities, Open Questions, What Changes, Why

### Community 1163 - "Requirement: Single-Command Local Stack Startup"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Single-Command Local Stack Startup, Scenario: All services start with docker compose up, Scenario: Individual service health endpoints respond, Scenario: Observability stack is reachable, Scenario: Stack starts when the observability services are unavailable

### Community 1164 - "Requirement: Structured entity value columns are queryable through the SQL path"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Structured entity value columns are queryable through the SQL path, Scenario: Date comparison query passes validation, Scenario: Non-whitelisted column is still rejected, Scenario: Numeric comparison query passes validation, Scenario: Text-only queries continue to work

### Community 1165 - "2026-09-08-subject-column-type-convergence/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Type comparison in the pure layer, 2. Introspection and the reconcile plan, 3. Reconciler behaviour against a real schema, 4. The entity-definition write paths, 5. Projection, 6. Verification & Evidence

### Community 1166 - "Task 9.1 — full suite run"
Cohesion: 0.29
Nodes (6): Environment, Every test this change owns passes, Failing-set diff — the result that matters, Result, Task 9.1 — full suite run, Timing

### Community 1167 - "Requirement: Document provenance and retention metadata"
Cohesion: 0.29
Nodes (7): Requirement: Document provenance and retention metadata, Scenario: A newly provisioned tenant inherits the columns, Scenario: Duplicate external identities are permitted, Scenario: Existing documents remain valid after migration, Scenario: No second storage-reference column is introduced, Scenario: Retention mode is constrained to the declared values, Scenario: The migration reaches every existing tenant schema

### Community 1168 - "Requirement: Query extracted entities"
Cohesion: 0.29
Nodes (7): Requirement: Query extracted entities, Scenario: Query entities as annotator, Scenario: Query entities by confidence threshold, Scenario: Query entities by document after batch extraction, Scenario: Query entities by type, Scenario: Query entities cross-tenant 404, Scenario: Query entities unreviewed

### Community 1169 - "Infrastructure"
Cohesion: 0.29
Nodes (6): Infrastructure, Purpose, Requirement: Seed script idempotent for promoted model, Requirements, Scenario: First run inserts promoted model, Scenario: Re-run seed script skips existing promoted model

### Community 1170 - "_spec"
Cohesion: 0.24
Nodes (7): _columns(), asyncio, verification.md rows 59-63, verification.md row 53 — the failure mode most likely to reach production., _spec(), TestReconcilerRepairs, TestSubjectColumnListChanges

### Community 1171 - "Requirement: Only platform default adapters are executable in this change"
Cohesion: 0.15
Nodes (12): ADDED Requirements, MODIFIED Requirements, Requirement: Only platform default adapters are executable in this change, Requirement: Tenant-owned data plane forbids platform-retained originals, Scenario: A non-default selection cannot be activated, Scenario: A non-default selection may be recorded, Scenario: A read-only PostgreSQL source does not relocate the tenant, Scenario: An approved Azure connection can execute after activation (+4 more)

### Community 1172 - "2026-09-10-cap-6-local-compose-delivery-migration-and-operational-evidence/design.md"
Cohesion: 0.17
Nodes (11): Context, Currently-In-Force ADRs, Decision 1: Evidence-first delivery change, no runtime behavior change, Decision 2: Migration compatibility asserted by chain inspection, not rewrite, Decision 3: Telemetry evidence via declarations + scan, not new dashboards, Decision 4: Recovery evidenced by procedure + timed compose-level exercise record, Decisions, Goals / Non-Goals (+3 more)

### Community 1174 - "041_azure_blob_sync_ledger.py"
Cohesion: 0.47
Nodes (5): downgrade(), _for_each_tenant_schema(), durable azure blob sync ledger in every tenant schema (CAP-3) ADR-012 keeps…, Apply one statement to every provisioned tenant schema, per the 038 pattern.…, upgrade()

### Community 1175 - "2026-06-17-add-login-dashboard-transition/tasks.md"
Cohesion: 0.33
Nodes (5): 1. CSS Keyframes, 2. Login Page — Burst Overlay, 3. Auth Layout — Dashboard Fade-in, 4. Smoke Testing, 5. Verification & Evidence

### Community 1176 - "2026-06-17-fix-worker-host-routing/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Settings & Configuration, 2. Worker URL Replacement, 3. Docker Compose Updates, 4. Build & Test, 5. Verification & Evidence

### Community 1177 - "Requirement: Get active model version"
Cohesion: 0.33
Nodes (5): MODIFIED Requirements, Requirement: Get active model version, Scenario: Get active model from MLflow when one is promoted, Scenario: Get active model when MLflow is unavailable with no cached promoted model, Scenario: Get active model when none is promoted — returns base model

### Community 1178 - "2026-06-18-default-base-model/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Model Registry — Active Endpoint Base Model Fallback, 2. Model Serving — Base Model Fallback Inference, 3. Extraction Service — Updated Schemas and API, 4. ADR — Amend ADR-002 with Base-as-Default Pattern, 5. Verification & Evidence

### Community 1179 - "Requirement: System Admin Tenant User Listing"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: System Admin Tenant User Listing, Scenario: Non-system-admin cannot access the endpoint, Scenario: System Admin lists users of a tenant, Scenario: System Admin requests users for non-existent tenant

### Community 1180 - "Requirement: Page enter animation keyframe"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Page enter animation keyframe, Scenario: animate-fade-up class is registered in Tailwind config, Scenario: animation fires on each route change, Scenario: screen root div receives the animation class

### Community 1181 - "Requirement: Hide submit job action for non-tenant-admin roles"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Hide submit job action for non-tenant-admin roles, Scenario: Submit button hidden for system_admin, Scenario: Submit button visible for tenant_admin, Scenario: Submit slideover not accessible for system_admin

### Community 1182 - "2026-07-01-annotation-file-upload/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Database Migration, 2. Import Endpoint, 3. Export Endpoint Modification, 4. Tests, 5. Verification & Evidence

### Community 1183 - "2026-07-02-batch-extraction-run-history/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Backend — Extraction Service, 2. Backend — Gateway Proxy, 3. Backend Tests, 4. Frontend Verification, 5. Verification & Evidence

### Community 1184 - "Requirement: Submit form span preflight is informational only"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Submit form span preflight is informational only, Scenario: Backend rejection for insufficient entities is surfaced after submit, Scenario: Preflight display shows span count while loading and on fetch failure, Scenario: Submit enabled with span count below the legacy 500 threshold

### Community 1185 - "Requirement: Convert trained model to ONNX format"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Convert trained model to ONNX format, Scenario: ONNX file is loadable by model-serving layer, Scenario: ONNX file is produced after training, Scenario: ONNX file is uploaded to blob storage

### Community 1186 - "Requirement: Prevent re-execution of completed or failed jobs"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Prevent re-execution of completed or failed jobs, Scenario: Job already completed is not re-executed, Scenario: Job already failed is not re-executed, Scenario: Job in non-terminal status proceeds normally

### Community 1187 - "2026-07-09-fix-mlflow-model-logging/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Dependencies & Configuration, 2. Retry Guard (Job Status Pre-Check), 3. ONNX Conversion, 4. MLflow Model Logging Fix, 5. Verification & Evidence

### Community 1188 - "Requirement: Get active model version"
Cohesion: 0.33
Nodes (5): MODIFIED Requirements, Requirement: Get active model version, Scenario: Get active model from MLflow when one is promoted, Scenario: Get active model when MLflow is unavailable, Scenario: Get active model when none is promoted

### Community 1189 - "Requirement: Save model artifacts"
Cohesion: 0.33
Nodes (5): MODIFIED Requirements, Requirement: Save model artifacts, Scenario: Artifact path uses version number not UUID, Scenario: Artifacts are stored after training, Scenario: label_list is persisted in model version metrics

### Community 1190 - "Changes"
Cohesion: 0.33
Nodes (5): 1. List model versions — fix implementation to match spec, 2. New scenario: List models with mixed stages, Changes, Model Registry — Delta, Scenario: List all versions when multiple exist in same MLflow stage

### Community 1191 - "Tasks: Remove Settings Placeholder Copy"
Cohesion: 0.33
Nodes (5): Overview, Task 1: Update Settings page ✓, Task 2: Add focused verification ✓, Tasks: Remove Settings Placeholder Copy, Verification

### Community 1192 - "Requirement: Guardrail — query complexity limits"
Cohesion: 0.33
Nodes (5): MODIFIED Requirements, Requirement: Guardrail — query complexity limits, Scenario: Blocked question type is still declined with the loop enabled, Scenario: Overly complex question is answered when the loop is enabled, Scenario: Overly complex question is simplified when the loop is disabled

### Community 1193 - "2026-09-08-app-shell-ui-cleanup/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Sidebar changes, 2. Topbar changes, 3. AppShell wiring, 4. Test updates, 5. Verification & Evidence

### Community 1194 - "Requirement: Reranked document context"
Cohesion: 0.33
Nodes (5): ADDED Requirements, Requirement: Reranked document context, Scenario: A relevant chunk ranked below the truncation cutoff is promoted into context, Scenario: Chat succeeds with unreranked ordering when the reranker is unavailable, Scenario: Reranking does not alter the structured entity source

### Community 1195 - "Requirement: Conversation-scoped binding for follow-up turns"
Cohesion: 0.33
Nodes (6): Requirement: Conversation-scoped binding for follow-up turns, Scenario: A different person replaces the binding, Scenario: Bound mention is not re-clarified, Scenario: Corpus-wide question clears the binding, Scenario: Follow-up without a name inherits the binding, Scenario: Several follow-ups keep the same binding

### Community 1196 - "Requirement: No Hardcoded Secrets in Codebase"
Cohesion: 0.33
Nodes (5): MODIFIED Requirements, Requirement: No Hardcoded Secrets in Codebase, Scenario: AGENTS.md documents the no-hardcoded-secrets invariant, Scenario: Source code contains no plaintext secret defaults, Scenario: Startup fails when the telemetry pepper is absent

### Community 1197 - "2026-09-08-redesign-business-user-dashboard/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Backend: business_user data sourcing, 2. Frontend: navigation wiring, 3. Spec verification tasks, 4. Follow-up: real response-time tracking + topics removal, 5. Verification & Evidence

### Community 1198 - "2026-09-08-tenant-dashboard-workspace-refresh/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Backend: shape and hero copy, 2. Backend: curated tenant_admin event catalogue, 3. Frontend: types and rendering, 4. Verification tasks (spec scenario coverage), 5. Verification & Evidence

### Community 1199 - "Requirement: pgvector semantic search"
Cohesion: 0.33
Nodes (6): Requirement: pgvector semantic search, Scenario: Chat retrieves relevant document context for a lexical (exact-term) query, Scenario: Citation includes page number when the chunk has one, Scenario: Citation page number is null for chunks without metadata, Scenario: Semantic search returns relevant chunks, Scenario: Semantic search with empty corpus

### Community 1200 - "Requirement: Rename conversation endpoint"
Cohesion: 0.33
Nodes (6): Requirement: Rename conversation endpoint, Scenario: Owner renames their conversation, Scenario: Renaming another user's conversation returns 404, Scenario: Renaming requires authentication, Scenario: Renaming with an empty title is rejected, Scenario: Renaming with an over-length title is rejected

### Community 1201 - "Requirement: Document visibility by ingesting actor"
Cohesion: 0.33
Nodes (6): Requirement: Document visibility by ingesting actor, Scenario: A system-ingested document is visible tenant-wide, Scenario: A user does not see another user's upload, Scenario: A user sees their own uploads, Scenario: Administrators are unaffected, Scenario: Listing and retrieval agree

### Community 1202 - "Requirement: List extraction runs"
Cohesion: 0.33
Nodes (6): Requirement: List extraction runs, Scenario: List batch extraction runs for a tenant, Scenario: List entities as non-admin business user, Scenario: List is scoped to the requesting tenant, Scenario: List returns empty array when no runs exist, Scenario: Runs are ordered most-recent-first

### Community 1203 - "Requirement: Annotation Action Bar"
Cohesion: 0.33
Nodes (6): Requirement: Annotation Action Bar, Scenario: Action bar disabled with no task selected, Scenario: Action bar renders at the bottom of the workspace, Scenario: Completing with no spans surfaces the error and keeps the task in-progress, Scenario: Mark as Completed completes the task, Scenario: Re-completing an already completed task saves further edits

### Community 1204 - "Requirement: Span Inspector"
Cohesion: 0.33
Nodes (6): Requirement: Span Inspector, Scenario: Clicking a confirmed span opens the inspector with metadata grid, Scenario: Clicking a retype chip updates the span, Scenario: Delete removes the span, Scenario: Focus mode inspector renders as fixed glass card, Scenario: Retype chips are shown for all entity types

### Community 1205 - "Bugs: Tenant Self-Service Data Sources"
Cohesion: 0.25
Nodes (8): Bugs: Tenant Self-Service Data Sources, DS-001: Last-run status never updates, DS-002: Portal shows `INTERNAL_ERROR` for every data-source error, DS-003: Blob sync scheduler appears stuck, DS-004: Gateway blocks its event loop while enqueuing a manual sync, DS-005: Gateway had no Celery broker configured, DS-006: Blob sync containers download the tokenizer at startup and die if it fails, DS-007: Blob sync OCR tests fail on a stale test-fixture schema

### Community 1207 - "Requirement: Tenant-Scoped User Management"
Cohesion: 0.40
Nodes (4): MODIFIED Requirements, Requirement: Tenant-Scoped User Management, Scenario: Tenant Admin attempts cross-tenant user creation, Scenario: Tenant Admin creates a user in their own tenant

### Community 1208 - "2026-06-11-training-approval-gate/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Backend Implementation — Training Jobs Router, 2. Tests — Modified Existing Scenarios, 3. Tests — New Approve/Reject Scenarios, 4. Verification & Evidence

### Community 1209 - "2026-06-15-promote-warmup-integration/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Configuration & Endpoints, 2. Integration in Promote Endpoint, 3. Testing, 4. Verification & Evidence

### Community 1210 - "Requirement: Extraction worker deployment"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Extraction worker deployment, Scenario: Batch extraction task is consumed, Scenario: Worker connects and processes an extraction task

### Community 1211 - "2026-06-18-fix-users-tenant-resolution/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Router Update, 2. Smoke Test, 3. Spec Update, 4. Verification & Evidence

### Community 1212 - "2026-06-19-fix-cors-preflight-middleware/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Document Service Middleware Fix, 2. Annotation Service Middleware Fix, 3. Scenario Verification, 4. Verification & Evidence

### Community 1213 - "2026-06-19-sidebar-action-menu/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Nav Config — Remove Settings Entries, 2. Sidebar — Floating Action Menu Implementation, 3. Verification — Write Acceptance Tests, 4. Verification & Evidence

### Community 1214 - "Requirement: Configurable chat API service URL"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Configurable chat API service URL, Scenario: Default URL works for local development, Scenario: Gateway proxies to configured URL

### Community 1215 - "Requirement: Authenticated API calls from chat page"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Authenticated API calls from chat page, Scenario: Chat page sends authenticated requests, Scenario: Unauthenticated chat request returns 401

### Community 1216 - "2026-06-23-tenant-from-jwt-in-chat-api/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Chat API Routes — Remove `{tid}`, 2. Gateway Proxy — Update Routes, 3. Spec Sync, 4. Verification & Evidence

### Community 1217 - "Requirement: Tenant Detail View"
Cohesion: 0.40
Nodes (4): MODIFIED Requirements, Requirement: Tenant Detail View, Scenario: System Admin views tenant details, Scenario: Tenant with no users shows empty state

### Community 1218 - "2026-06-24-sp-06/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Backend: System Admin Tenant Users Endpoint, 2. Frontend: Tenant Admin Users Page (`/users`), 3. Frontend: Admin Console Tenant Detail Users Section, 4. Verification & Evidence

### Community 1219 - "2026-06-25-fix-entity-types-api-alignment/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Router: Fix Prefix and Route Parameters, 2. Service: Add toggle_entity_type and _get_by_name, 3. Service: Fix JSON Deserialization in _row_to_dict, 4. Verification

### Community 1220 - "2026-07-07-fix-analytics-query-feedback/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Backend — Typed exception handling in query service, 2. Gateway — Error handling in analytics proxy, 3. Frontend — Query error feedback, 4. Verification & Evidence

### Community 1221 - "Verification: Model Registry Promote"
Cohesion: 0.40
Nodes (4): AC Verification Matrix, Risks, Test Harness Notes, Verification: Model Registry Promote

### Community 1222 - "Requirement: Seed script idempotent for promoted model"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Seed script idempotent for promoted model, Scenario: First run inserts promoted model, Scenario: Re-run seed script skips existing promoted model

### Community 1223 - "Proposal: Remove Settings Placeholder Copy"
Cohesion: 0.40
Nodes (4): Impact, Problem Statement, Proposal: Remove Settings Placeholder Copy, Proposed Solution

### Community 1224 - "2026-09-08-audit-log-tenant-filter/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Backend: Tenant Filter on Audit Log Endpoint, 2. Frontend: Searchable Tenant Combobox Component, 3. Frontend: Wire Tenant Filter into Audit Page, 4. Verification & Evidence

### Community 1225 - "Requirement: Entities are routed to definitions by entity-type literal, case-insensitively"
Cohesion: 0.40
Nodes (5): Requirement: Entities are routed to definitions by entity-type literal, case-insensitively, Scenario: A base-model CoNLL label routes through base_label_mapping, Scenario: A fine-tuned label routes by name, Scenario: Routing and DDL agree on the literal set, Scenario: Stored case differing from definition case still routes

### Community 1226 - "Requirement: Candidate presentation with minimal distinguishing metadata"
Cohesion: 0.40
Nodes (5): Requirement: Candidate presentation with minimal distinguishing metadata, Scenario: Card shows only the fields that exist, Scenario: Card values come from the entity store, Scenario: Identical cards fall back to filenames, Scenario: Skills are capped

### Community 1227 - "Requirement: Deterministic mention extraction and matching"
Cohesion: 0.40
Nodes (5): Requirement: Deterministic mention extraction and matching, Scenario: Extraction makes no LLM call, Scenario: Longest matching mention wins, Scenario: Name is matched through shared canonicalization, Scenario: Non-person entity types are not matched

### Community 1228 - "Requirement: Feature flag and flag-off equivalence"
Cohesion: 0.40
Nodes (5): Requirement: Feature flag and flag-off equivalence, Scenario: Existing chat tests pass unmodified with the flag off, Scenario: Flag off issues no resolver query, Scenario: Flag off leaves the graph topology unchanged, Scenario: Stale state is inert when the flag is off

### Community 1229 - "Requirement: Natural-language selection interpretation"
Cohesion: 0.40
Nodes (5): Requirement: Natural-language selection interpretation, Scenario: Attribute answer resolves through the constrained call, Scenario: Descriptive answer resolves through the constrained call, Scenario: Ordinal answer resolves without an LLM call, Scenario: Out-of-range index is rejected

### Community 1230 - "Requirement: Retrieval is constrained to the resolved document"
Cohesion: 0.40
Nodes (5): Requirement: Retrieval is constrained to the resolved document, Scenario: Aggregate rows without a document id are retained, Scenario: Answer cites only the resolved document, Scenario: Semantic scope is overridden with the resolved document, Scenario: Structured rows outside the resolved scope are dropped

### Community 1231 - "Requirement: Zero, one, and many resolution outcomes"
Cohesion: 0.40
Nodes (5): Requirement: Zero, one, and many resolution outcomes, Scenario: Multiple documents produce an ambiguous outcome, Scenario: No match leaves the existing strategy untouched, Scenario: Repeated name within one document is one candidate, Scenario: Single match proceeds directly into scoped retrieval

### Community 1232 - "Requirement: Per-request authorization context isolation"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Per-request authorization context isolation, Scenario: Interleaved tenant requests do not leak tokens, Scenario: Orchestrator singleton holds no request-scoped state

### Community 1233 - "2026-09-08-merge-bio-entity-display/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Playground — BIO Merge Utility, 2. Playground — Grouped Display Layout, 3. Entity Review Tab — Grouped Display, 4. Verification & Evidence

### Community 1234 - "Requirement: Tenant Detail View"
Cohesion: 0.40
Nodes (4): MODIFIED Requirements, Requirement: Tenant Detail View, Scenario: System Admin creates a user in the tenant from this view, Scenario: System Admin views tenant details

### Community 1235 - "Tasks 8.2 and 8.3 — architectural scope review"
Cohesion: 0.40
Nodes (4): 8.2 — No abstraction was introduced over the platform's chosen technologies, 8.3 — No deferred capability was started, Files this change touches, by group, Tasks 8.2 and 8.3 — architectural scope review

### Community 1236 - "Tasks 9.3 and 9.4 — hallucination risk register and ADR compliance"
Cohesion: 0.40
Nodes (4): Explicitly not confirmed by this agent, Task 9.3 — Hallucination Risk Register mitigations, Task 9.4 — ADR compliance, Tasks 9.3 and 9.4 — hallucination risk register and ADR compliance

### Community 1237 - "2026-09-10-cap-2-tenant-scoped-connection-control-plane/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Control-plane domain and migration, 2. Tenant-admin lifecycle API, 3. Compatibility and observability, 4. Verification

### Community 1238 - "Requirement: Azure Blob sync submits through the common ingestion boundary"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Azure Blob sync submits through the common ingestion boundary, Scenario: Sync document enters through the common boundary, Scenario: Sync documents cannot assert tenant identity

### Community 1239 - "Requirement: Retrieval excludes superseded and confirmed-missing source documents"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: Retrieval excludes superseded and confirmed-missing source documents, Scenario: Confirmed-missing document chunks are excluded, Scenario: Superseded document chunks are excluded

### Community 1240 - "2026-09-10-cap-3-durable-azure-blob-synchronization-and-source-reconciliation/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Tenant-schema sync ledger and migration, 2. Contained provider runtime and durable sync job, 3. Reconciliation, retention, and compatibility, 4. Verification & Evidence

### Community 1241 - "ADR-NNN. <Decision title>"
Cohesion: 0.40
Nodes (4): ADR-NNN. <Decision title>, Consequences, Context, Decision

### Community 1242 - "Requirement: <!-- requirement name -->"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: <!-- requirement name -->, Scenario: <!-- another scenario -->, Scenario: <!-- scenario name -->

### Community 1243 - "Requirement: Automatic conversation title generation"
Cohesion: 0.40
Nodes (5): Requirement: Automatic conversation title generation, Scenario: Empty-content first message falls back to placeholder title, Scenario: Title generated from a short first message, Scenario: Title is generated once and not overwritten by later messages, Scenario: Title truncated for a long first message

### Community 1244 - "Requirement: Candidate document filtering of semantic retrieval"
Cohesion: 0.40
Nodes (5): Requirement: Candidate document filtering of semantic retrieval, Scenario: Empty candidate set leaves semantic retrieval unfiltered, Scenario: Explicit document scope from the planner wins, Scenario: Feature disabled preserves concurrent execution, Scenario: Semantic search is scoped to structured candidates

### Community 1245 - "Requirement: Conversation CRUD"
Cohesion: 0.40
Nodes (5): Requirement: Conversation CRUD, Scenario: Delete another user's conversation returns 404, Scenario: Delete conversation, Scenario: Get conversation messages, Scenario: List conversations for a user

### Community 1246 - "Requirement: Structured entity value columns are queryable through the SQL path"
Cohesion: 0.40
Nodes (5): Requirement: Structured entity value columns are queryable through the SQL path, Scenario: Date comparison query passes validation, Scenario: Non-whitelisted column is still rejected, Scenario: Numeric comparison query passes validation, Scenario: Text-only queries continue to work

### Community 1247 - "Requirement: Document Metadata API"
Cohesion: 0.40
Nodes (5): Requirement: Document Metadata API, Scenario: Delete a document, Scenario: Get deleted document returns 200 with deleted status, Scenario: Get document metadata, Scenario: List documents with status filter

### Community 1248 - "Requirement: Document Viewer and Token Rendering"
Cohesion: 0.40
Nodes (5): Requirement: Document Viewer and Token Rendering, Scenario: Confirmed span tokens are highlighted, Scenario: Document renders inside a card container, Scenario: Suggested span tokens show dashed overlay, Scenario: Unannotated tokens render without highlight

### Community 1249 - "Requirement: Entity Type Palette and Armed Mode"
Cohesion: 0.40
Nodes (5): Requirement: Entity Type Palette and Armed Mode, Scenario: Clicking a chip arms the entity type and shows animated banner, Scenario: Clicking the armed chip again disarms it, Scenario: Escape key disarms via banner, Scenario: Palette shows entity types with base label and span count

### Community 1250 - "Requirement: Layout and Navigation"
Cohesion: 0.40
Nodes (5): Requirement: Layout and Navigation, Scenario: Clicking "3-pane" button exits focus mode, Scenario: Clicking "Focus" button enters CSS focus mode, Scenario: Default layout renders three columns, Scenario: Layout preference is restored on reload

### Community 1251 - "Requirement: Pre-labeling and Suggestion Flow"
Cohesion: 0.40
Nodes (5): Requirement: Pre-labeling and Suggestion Flow, Scenario: Dismiss removes suggestion locally, Scenario: Pre-label button is disabled during in-flight request, Scenario: Pre-label populates suggestion cards, Scenario: Promote converts a suggestion to a confirmed span

### Community 1252 - "Requirement: Task Status Lifecycle"
Cohesion: 0.40
Nodes (5): Requirement: Task Status Lifecycle, Scenario: Creating a span does not send a status request, Scenario: In-progress transition fires only once per session, Scenario: Opening a completed task sends no status request, Scenario: Opening an unannotated task promotes it to in-progress

### Community 1253 - "Requirement: Token-Click Span Creation"
Cohesion: 0.40
Nodes (5): Requirement: Token-Click Span Creation, Scenario: API error reverts optimistic span, Scenario: Clicking a token while armed creates a span, Scenario: Clicking a token while no type is armed opens the span inspector, Scenario: Clicking an already-spanned token while armed does nothing

### Community 1254 - "Requirement: Settings Page Placeholder"
Cohesion: 0.40
Nodes (4): Requirement: Settings Page Placeholder, Requirements, Scenario: Settings page does not show coming-soon copy, Settings Page

### Community 1255 - "openspec/specs/worker-network-config/spec.md"
Cohesion: 0.40
Nodes (4): Purpose, Requirement: Worker host service connectivity, Requirements, Scenario: Worker processes a batch document from Docker

### Community 1256 - "2026-09-11-redesign-azure-blob-connection-ui/design.md"
Cohesion: 0.18
Nodes (10): Context, Currently-In-Force ADRs, Decision 1: Merge test, attestation, and activation into one sequential control — attestation checkboxes stay, no auto-submission, Decision 2: Reorder via straight JSX reordering in `DetailContent`, not a new layout abstraction, Decision 3: New-connection modal reuses `SlideOver`'s internals as a centered dialog, not a right-edge panel, Decisions, Goals / Non-Goals, Migration Plan (+2 more)

### Community 1257 - "_sanitize_error"
Cohesion: 0.25
Nodes (5): BaseException, Renders an exception into a single bounded line safe to put in a prompt., _sanitize_error(), Row 57 — SQLAlchemy appends the statement and bound values to str(exc)., Row 57 — bounded length.

### Community 1260 - "2026-06-08-env-config-setup/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Environment Configuration Setup, 2. Test & Verification, 3. Verification & Evidence

### Community 1261 - "ADDED Requirements"
Cohesion: 0.50
Nodes (3): ADDED Requirements, Requirement: Worker host service connectivity, Scenario: Worker processes a batch document from Docker

### Community 1262 - "2026-06-22-fix-promote-inprogress-transition/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Frontend Fix — `handlePromote` In-Progress Transition, 2. Verification — Spec Scenarios, 3. Verification & Evidence

### Community 1263 - "2026-06-25-sp-04-dashboard/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Backend — Dashboard Summary Endpoint, 2. Frontend — DashboardPage Component, 3. Verification & Evidence

### Community 1264 - "2026-06-29-remove-submit-training-job-button/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Implementation, 2. Verification — Scenario Tests, 3. Verification & Evidence

### Community 1265 - "2026-07-02-fix-prelabel-keyword-search/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Backend — Update prelabel_document() in spans.py, 2. Tests — Update test_annotation_workspace.py, 3. Verification & Evidence

### Community 1266 - "2026-07-06-fix-analytics-materialized-views/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Alembic Migration, 2. Seed Script Update, 3. Verification & Evidence

### Community 1267 - "2026-07-08-remove-training-span-gate/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Remove the client-side threshold, 2. Update component tests, 3. Verification & Evidence

### Community 1268 - "MODIFIED Requirements"
Cohesion: 0.50
Nodes (3): MODIFIED Requirements, Requirement: Settings Page Placeholder, Scenario: Settings page does not show coming-soon copy

### Community 1269 - "Requirement: A literal claimed by two active definitions routes to exactly one"
Cohesion: 0.50
Nodes (4): Requirement: A literal claimed by two active definitions routes to exactly one, Scenario: A collision never double-writes, Scenario: A name match wins the collision, Scenario: With no name match, sort order decides deterministically

### Community 1270 - "Requirement: Every extracted document gets a subject row"
Cohesion: 0.50
Nodes (4): Requirement: Every extracted document gets a subject row, Scenario: A definition with no matching entities yields no child rows, Scenario: A never-extracted document has no row, Scenario: A zero-entity document still gets a row

### Community 1271 - "Requirement: Re-extraction replaces a document's entity rows rather than appending"
Cohesion: 0.50
Nodes (4): Requirement: Re-extraction replaces a document's entity rows rather than appending, Scenario: A deactivated definition's stale rows are still cleared, Scenario: Re-extraction under a new model version does not duplicate, Scenario: The idempotency ledger is preserved

### Community 1272 - "Requirement: Relational rows are deleted through a shared pure statement builder"
Cohesion: 0.50
Nodes (4): Requirement: Relational rows are deleted through a shared pure statement builder, Scenario: Both callers use the same statements, Scenario: The builder executes nothing, Scenario: The subject row is included

### Community 1273 - "Requirement: Single-valued selection is deterministic"
Cohesion: 0.50
Nodes (4): Requirement: Single-valued selection is deterministic, Scenario: A confidence tie is broken deterministically, Scenario: The highest-confidence value is selected, Scenario: Unselected values remain in the system of record

### Community 1274 - "Requirement: The projected column value is determined by the definition's value kind"
Cohesion: 0.50
Nodes (4): Requirement: The projected column value is determined by the definition's value kind, Scenario: A numeric kind writes the parsed number, Scenario: A text kind writes the surface value, Scenario: An unparseable typed value writes NULL

### Community 1275 - "Requirement: The projection is written inside the existing per-document extraction transaction"
Cohesion: 0.50
Nodes (4): Requirement: The projection is written inside the existing per-document extraction transaction, Scenario: A failure rolls both back, Scenario: EAV and relational commit together, Scenario: No second synchronization path exists

### Community 1276 - "Requirement: Ambiguity pauses the turn and requests clarification"
Cohesion: 0.50
Nodes (4): Requirement: Ambiguity pauses the turn and requests clarification, Scenario: Candidate count above the cap declines to list, Scenario: Clarification names the reference and lists candidates, Scenario: Clarification turn skips retrieval and generation

### Community 1277 - "Requirement: Pending clarification state is persisted per conversation"
Cohesion: 0.50
Nodes (4): Requirement: Pending clarification state is persisted per conversation, Scenario: A new clarification replaces the previous one, Scenario: Pending state is tenant-scoped, Scenario: Pending state survives across requests

### Community 1278 - "2026-09-08-fix-batch-runs-scroll-layout/tasks.md"
Cohesion: 0.50
Nodes (3): 1. Layout Change, 2. Existing Behavior Regression Checks, 3. Verification & Evidence

### Community 1279 - "ADDED Requirements"
Cohesion: 0.50
Nodes (3): ADDED Requirements, Requirement: Touched OCR failure paths emit safe structured error classes, Scenario: OCR failure records a class, not a payload

### Community 1280 - "templates/tasks.md"
Cohesion: 0.50
Nodes (3): 1. <!-- Task Group Name (e.g., Setup) -->, 2. <!-- Task Group Name (e.g., Core Implementation) -->, N. Verification & Evidence

### Community 1281 - "Requirement: Reranked document context"
Cohesion: 0.50
Nodes (4): Requirement: Reranked document context, Scenario: A relevant chunk ranked below the truncation cutoff is promoted into context, Scenario: Chat succeeds with unreranked ordering when the reranker is unavailable, Scenario: Reranking does not alter the structured entity source

### Community 1282 - "Requirement: Structured retrieval returns candidate document IDs"
Cohesion: 0.50
Nodes (4): Requirement: Structured retrieval returns candidate document IDs, Scenario: Candidate IDs are the distinct document IDs of the result rows, Scenario: Failed structured retrieval yields no candidates, Scenario: No document_id column yields no candidates

### Community 1283 - "Requirement: Callers Construct URLs Without {tid}"
Cohesion: 0.50
Nodes (4): Requirement: Callers Construct URLs Without {tid}, Scenario: Extraction engine forwards request without tid in URL, Scenario: Training service constructs warmup URL without tid in path, Scenario: Worker constructs inference URL without tid in path

### Community 1284 - "Requirement: Get extraction run status"
Cohesion: 0.50
Nodes (4): Requirement: Get extraction run status, Scenario: Get extraction run status, Scenario: Get extraction run status of completed run, Scenario: Get extraction run status with model version

### Community 1285 - "Requirement: Real-time extraction"
Cohesion: 0.50
Nodes (4): Requirement: Real-time extraction, Scenario: Extract entities as non-admin, Scenario: Extract entities from a text paragraph with fine-tuned model, Scenario: Extract entities using base model when none is promoted

### Community 1286 - "Requirement: Annotation Toolbar"
Cohesion: 0.50
Nodes (4): Requirement: Annotation Toolbar, Scenario: Badge reflects completed status without offering a transition, Scenario: Toolbar exposes no status selection control, Scenario: Toolbar renders all elements for an active task

### Community 1287 - "Requirement: Focus Mode Entity Palette"
Cohesion: 0.50
Nodes (4): Requirement: Focus Mode Entity Palette, Scenario: Arming from the bottom palette works identically to the right-panel palette, Scenario: Bottom palette is hidden in 3-pane mode, Scenario: Bottom palette renders in focus mode

### Community 1288 - "Requirement: Per-request tool availability"
Cohesion: 0.18
Nodes (10): ADDED Requirements, Requirement: External database retrieval tool, Requirement: Per-request tool availability, Scenario: Drift block is returned as a finite error, Scenario: Fallback plan excludes the external tool, Scenario: Successful query returns rows, Scenario: Tenant with a published contract is offered the tool, Scenario: Tenant without a connection is never offered the tool (+2 more)

### Community 1289 - "Verification Plan"
Cohesion: 0.15
Nodes (12): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, AI Output Review, Edge Case Evidence (+4 more)

### Community 1296 - "Requirement: A missing generated relation fails the document"
Cohesion: 0.67
Nodes (3): Requirement: A missing generated relation fails the document, Scenario: A missing table fails the document visibly, Scenario: Projection emits no DDL

### Community 1297 - "Requirement: Generated identifiers are validated and unassigned definitions are skipped"
Cohesion: 0.67
Nodes (3): Requirement: Generated identifiers are validated and unassigned definitions are skipped, Scenario: A definition with no identifier is skipped, Scenario: A hostile entity name cannot reach a statement

### Community 1298 - "Requirement: Generated statements are schema-qualified by the caller"
Cohesion: 0.67
Nodes (3): Requirement: Generated statements are schema-qualified by the caller, Scenario: Statements target only the caller's schema, Scenario: The module resolves no schema

### Community 1299 - "Requirement: Provenance fields are not projected"
Cohesion: 0.67
Nodes (3): Requirement: Provenance fields are not projected, Scenario: Child tables carry values, not provenance, Scenario: Provenance remains joinable

### Community 1300 - "Requirement: The projection consumes the in-memory entity list and never re-reads the EAV store"
Cohesion: 0.67
Nodes (3): Requirement: The projection consumes the in-memory entity list and never re-reads the EAV store, Scenario: Post-processing results reach the relational tables, Scenario: The projection issues no read of document_entities

### Community 1301 - "Requirement: Original intent is replayed after selection"
Cohesion: 0.67
Nodes (3): Requirement: Original intent is replayed after selection, Scenario: Original request resumes automatically, Scenario: Pending state is cleared once resumed

### Community 1302 - "Requirement: Resolution outcome is observable"
Cohesion: 0.67
Nodes (3): Requirement: Resolution outcome is observable, Scenario: Ambiguous turn is logged with its candidate count, Scenario: Zero-match mention is logged

### Community 1303 - "Requirement: Post-processing confidence filtering"
Cohesion: 0.67
Nodes (3): Requirement: Post-processing confidence filtering, Scenario: Low-confidence entities are filtered out, Scenario: The threshold is meaningful against the returned scale

### Community 1304 - "Requirement: Span Deselection"
Cohesion: 0.67
Nodes (3): Requirement: Span Deselection, Scenario: Clicking an unannotated token closes the span inspector, Scenario: Clicking unannotated token while armed does not deselect

### Community 1307 - "Verification Plan"
Cohesion: 0.18
Nodes (10): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, Edge Case Evidence, Functional Evidence (+2 more)

### Community 1308 - "replace_version_entries"
Cohesion: 0.31
Nodes (8): clear_connection_entries(), entry_text_for_relation(), _index_table(), Tenant-isolated schema-index representations (CAP-4, ADR-013). The index helps…, Bounded context text for one relation: its description, columns (each with an…, Replace one version's index entries; returns the entry count., Remove every index entry for one connection (retirement path)., replace_version_entries()

### Community 1309 - "ADDED Requirements"
Cohesion: 0.20
Nodes (9): ADDED Requirements, local-compose-data-source-delivery Specification, Purpose, Requirement: Compatible local rolling delivery, Requirement: Safe operational verification and recovery, Scenario: Additive migration compatibility holds, Scenario: Local recovery is exercised, Scenario: Local rolling deployment succeeds (+1 more)

### Community 1310 - "local-compose-data-source-delivery Specification"
Cohesion: 0.20
Nodes (9): local-compose-data-source-delivery Specification, Purpose, Requirement: Compatible local rolling delivery, Requirement: Safe operational verification and recovery, Requirements, Scenario: Additive migration compatibility holds, Scenario: Local recovery is exercised, Scenario: Local rolling deployment succeeds (+1 more)

### Community 1311 - "external_pg_contract_skeleton.py"
Cohesion: 0.33
Nodes (9): Namespace, _build_contract(), _introspect_columns(), _introspect_foreign_keys(), _introspect_primary_keys(), main(), _parse_args(), Connection (+1 more)

### Community 1312 - "Tenant Data Sources — Local Delivery Runbook (dev only)"
Cohesion: 0.22
Nodes (8): 1. Rolling deployment sequence, 2. Health/readiness checklist, 3. Safe operational telemetry, 4. Compatible rollback / roll-forward (dev target: healthy within 30 min), 5. Activation gate (unchanged), 6. Explicitly out of scope, Recovery exercise record (2026-09-10), Tenant Data Sources — Local Delivery Runbook (dev only)

### Community 1313 - "_build_windows"
Cohesion: 0.31
Nodes (4): _build_windows(), Partitions word indices into overlapping `[start, end)` windows, each fitting…, A single monster token must not wedge the walk into an infinite loop., TestBuildWindows

### Community 1314 - "QA Report -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.22
Nodes (9): Authentication, Deployment Under Test, Evidence, Follow-Up Work, QA Report -- tenant-self-service-data-sources-20260909-2, Release Gate, Results By Test Type, Scope (+1 more)

### Community 1315 - "test_data_plane_status_endpoint.py"
Cohesion: 0.21
Nodes (12): _bearer(), failed_tenant(), fixture, Verification for `GET /api/v1/data-plane` and `POST /api/v1/data-…, Scenario: retry from `provisioning_failed` CAS's to `provisioning` and enqueues…, A `tenant_owned` tenant whose provisioning attempt failed, with a real…, Scenario: a tenant with no `tenant_data_planes` row reads back the platform…, Scenario: retry on a `platform`/`ready` tenant is a no-op, rejected. (+4 more)

### Community 1316 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1317 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1318 - "Verification Plan"
Cohesion: 0.25
Nodes (7): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, Verification Plan

### Community 1319 - "Verification Plan"
Cohesion: 0.25
Nodes (7): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log, 6. Audit Record, Verification Plan

### Community 1320 - "2026-09-10-cap-5-tenant-data-source-administration-portal/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1321 - "2026-09-10-cap-6-local-compose-delivery-migration-and-operational-evidence/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1322 - "TestModelQualityIsNotMirrored"
Cohesion: 0.27
Nodes (5): Row 23 — the registry walk., The walk, not the grep. A dynamically registered family — the natural way to…, The other way in: `ner_training_metric{name="f1"}` satisfies the letter of the…, The corollary — the boundary is about where they live, not about dropping them., TestModelQualityIsNotMirrored

### Community 1323 - "Requirement: Manual Blob sync trigger action"
Cohesion: 0.22
Nodes (8): ADDED Requirements, Requirement: Manual Blob sync trigger action, Scenario: Administrator triggers a manual sync on an active Blob connection, Scenario: Cross-tenant manual sync is denied, Scenario: Idempotent manual sync replay renders the safe result, Scenario: Manual sync on a PostgreSQL connection is rejected, Scenario: Manual sync on an inactive connection is rejected safely, Scenario: Non-administrator is denied

### Community 1324 - "ToolContext"
Cohesion: 0.03
Nodes (71): RuntimeError, ArgValidationError, assert_no_tenancy_params(), Any, Exception, Protocol, Validates `args` against a minimal JSON-Schema-shaped `args_schema` (type,…, Shared execution wrapper: validates args, times the call, and converts any… (+63 more)

### Community 1325 - "to_sql_identifier"
Cohesion: 0.12
Nodes (12): _backfill_sql_identifiers(), view-layer metadata on entity_definitions The read model for extracted entities…, Assigns every existing row an identifier, resolving collisions within each…, upgrade(), The identifier body, before the prefix, the length bound, and collision…, Deterministic, collision-free, <=63 chars, matches `^e_[a-z0-9][a-z0-9_]*$`.…, _slug_base(), to_sql_identifier() (+4 more)

### Community 1326 - "external-postgresql-chat-sql-generation/tasks.md"
Cohesion: 0.22
Nodes (8): 1. Demo Prerequisites (do first — these block everything live), 2. Contract Descriptions (Design D1, D2), 3. Contract Skeleton Script (Design D8), 4. External SQL Generator (Design D3, D4, D7), 5. External Database Tool (retrieval-tools spec), 6. Chat Graph Wiring (Design D5, D6), 7. Live Demo Rehearsal, 8. Verification & Evidence

### Community 1327 - "2026-09-10-cap-5-tenant-data-source-administration-portal/tasks.md"
Cohesion: 0.29
Nodes (6): 1. Navigation and data layer, 2. SCR-1 collection screen, 3. SCR-2 lifecycle screen, 4. SCR-3 contract screen, 5. Access control and contract compliance, 6. Verification & Evidence

### Community 1328 - "Verification Plan"
Cohesion: 0.29
Nodes (6): 1. Spec Alignment, 2. Hallucination Risk Register, 3. Pattern & ADR Compliance, 4. Evidence Requirements, 5. Evidence Log and Audit Record, Verification Plan

### Community 1329 - "export.py"
Cohesion: 0.31
Nodes (8): export_annotations(), get_session(), get_tenant_id(), AsyncSession, get, Request, Routed through EngineResolver (ADR-017)., _tokenize()

### Community 1330 - "conversation_entity_state.py"
Cohesion: 0.10
Nodes (24): CandidateEntity, PendingClarification, _candidates_to_schema(), Candidate, _candidates_from_json(), _candidates_to_json(), clear_binding(), clear_pending() (+16 more)

### Community 1331 - "analytics_proxy.py"
Cohesion: 0.50
Nodes (8): _proxy(), proxy_analytics_dashboard(), proxy_analytics_export(), proxy_analytics_query(), proxy_analytics_refresh(), get, post, Request

### Community 1332 - "Deployment: tenant-self-service-data-sources-20260909-2 — dev"
Cohesion: 0.33
Nodes (5): Access, Deployment: tenant-self-service-data-sources-20260909-2 — dev, Prior blocking finding — resolved, Security review (baseline-policy `security.nonOverridable`), What landed

### Community 1333 - "2026-09-11-manual-blob-sync-trigger/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1334 - "Security -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.33
Nodes (5): Decision, Findings, Gaps (honest, non-blocking), Security -- tenant-self-service-data-sources-20260909-2, What passed

### Community 1335 - "TestBaseModelPathIsCalibrated"
Cohesion: 0.33
Nodes (4): slow, Row 3: the base-model fallback reports the same scale, so a tenant with no…, Downloads the base model, so it is excluded from the default run. It is the…, TestBaseModelPathIsCalibrated

### Community 1336 - "042_external_pg_contracts.py"
Cohesion: 0.60
Nodes (4): downgrade(), _for_each_tenant_schema(), canonical external-postgresql schema contracts and tenant schema index (CAP-4)…, upgrade()

### Community 1337 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path-superseded-unrecorded/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Canonical contract lifecycle and migration, 2. Drift gate, AST validator, and drift-gated connector, 3. Capability resolver, gateway contract routes, and chat integration, 4. Verification & Evidence

### Community 1338 - "2026-09-10-cap-4-contract-governed-external-postgresql-query-path/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Canonical contract lifecycle and migration, 2. Drift gate, AST validator, and drift-gated connector, 3. Capability resolver, gateway contract routes, and chat integration, 4. Verification & Evidence

### Community 1339 - "Tasks — cap-6-local-compose-delivery-migration-and-operational-evidence"
Cohesion: 0.40
Nodes (4): Task 1: Delivery-evidence pytest module, Task 2: Local delivery runbook, Task 3: Live evidence and verification record, Tasks — cap-6-local-compose-delivery-migration-and-operational-evidence

### Community 1340 - "Requirement: Common durable Blob ingestion"
Cohesion: 0.25
Nodes (7): MODIFIED Requirements, Requirement: Common durable Blob ingestion, Scenario: Inactive connection never syncs, Scenario: Manual trigger runs the same job as the schedule, Scenario: New object is synchronized, Scenario: Overlapping runs are prevented by the durable lease, Scenario: Scheduled cadence with missed-schedule catch-up

### Community 1341 - "Accessibility -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.40
Nodes (4): Accessibility -- tenant-self-service-data-sources-20260909-2, Decision, Notes, Results

### Community 1342 - "summary.md"
Cohesion: 0.40
Nodes (3): Decision, Demo & Fixture Hygiene -- tenant-self-service-data-sources-20260909-2, Results

### Community 1343 - "Load -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.40
Nodes (4): Decision, Load -- tenant-self-service-data-sources-20260909-2, Results, Stages

### Community 1344 - "2026-09-11-redesign-azure-blob-connection-ui/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1345 - "softmax"
Cohesion: 0.21
Nodes (7): ndarray, Numerically stable softmax over `axis`. Subtracting the per-row maximum before…, softmax(), Row 4: overlap conflicts are resolved by edge distance first, confidence…, The observed production logit band was roughly 2.8-7.4, which is exactly the…, TestOverlapTieBreakStillWorks, TestSoftmaxHelper

### Community 1346 - "external-postgresql-chat-sql-generation/proposal.md"
Cohesion: 0.25
Nodes (7): Capabilities, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1347 - "dependencies"
Cohesion: 0.25
Nodes (8): dependencies, lucide-react, next, react, react-dom, react-markdown, remark-gfm, @tanstack/react-query

### Community 1348 - "Integration -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.50
Nodes (3): Decision, Integration -- tenant-self-service-data-sources-20260909-2, Results

### Community 1349 - "Performance -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.50
Nodes (3): Decision, Performance -- tenant-self-service-data-sources-20260909-2, Results

### Community 1350 - "Regression -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.50
Nodes (3): Decision, Regression -- tenant-self-service-data-sources-20260909-2, Results

### Community 1351 - "Smoke -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.50
Nodes (3): Decision, Results, Smoke -- tenant-self-service-data-sources-20260909-2

### Community 1352 - "Unit -- tenant-self-service-data-sources-20260909-2"
Cohesion: 0.50
Nodes (3): Decision, Results, Unit -- tenant-self-service-data-sources-20260909-2

### Community 1353 - "ADDED Requirements"
Cohesion: 0.17
Nodes (11): ADDED Requirements, Requirement: Content-free document registry in the control plane, Requirement: Quotas and fleet counts use the registry, Requirement: The registry follows the tenant store, which stays authoritative, Scenario: Drift is reconciled, Scenario: Existing documents are backfilled, Scenario: Quota uses the registry, Scenario: Registry schema holds no content columns (+3 more)

### Community 1355 - "Requirement: Manual sync-now control"
Cohesion: 0.29
Nodes (6): ADDED Requirements, Requirement: Manual sync-now control, Scenario: Administrator triggers a manual sync from the detail view, Scenario: Lease-held manual sync surfaces a safe retry notice, Scenario: Sync-now is absent for PostgreSQL connections, Scenario: Sync-now is unavailable for inactive connections

### Community 1356 - "extract_entities"
Cohesion: 0.41
Nodes (12): extract_entities(), get_batch_status(), _get_role(), _get_tenant_id(), list_batch_runs(), list_eligible_documents(), AsyncSession, get (+4 more)

### Community 1357 - "imported-documents/page.tsx"
Cohesion: 0.05
Nodes (47): Favicon — dark theme SVG, Logo — dark theme SVG, Hardcoded-color-to-CSS-variable mapping (text-gray-900 -> var(--ink), bg-white -> var(--surface-2), etc.), Design: Fix Dark Theme Issues Across Portal Pages, Proposal: Fix Dark Theme Issues Across Portal Pages, Fix Dark Theme Issues - Tasks, In-app Logo SVG, Logo (Dark Theme) SVG (+39 more)

### Community 1358 - "2026-09-11-redesign-azure-blob-connection-ui/tasks.md"
Cohesion: 0.33
Nodes (5): 1. Shared focus-trap extraction, 2. Lifecycle panel: merge test + attestation + activation into one sequential control, 3. Detail page: reorder panels, drop redundant Activation fact, 4. New-connection modal, 5. Verification & Evidence

### Community 1359 - "ADR-015. External Chat Replies Persist; External Rows Do Not"
Cohesion: 0.40
Nodes (4): ADR-015. External Chat Replies Persist; External Rows Do Not, Consequences, Context, Decision

### Community 1360 - "ADR-016. Contract-Grounded External SQL Generation"
Cohesion: 0.40
Nodes (4): ADR-016. Contract-Grounded External SQL Generation, Consequences, Context, Decision

### Community 1361 - "2026-09-11-manual-blob-sync-trigger/tasks.md"
Cohesion: 0.40
Nodes (4): 1. Gateway Manual Sync Route, 2. Portal Sync-Now Control, 3. Acceptance-Criteria Tests, 4. Verification & Evidence

### Community 1362 - "TestModeDoesNotAffectSkipLogic"
Cohesion: 0.40
Nodes (3): Row 73 — flipping the toggle must not reprocess and overwrite existing entities., The whole worker module is inspected, not one function. `run_batch_extraction`…, TestModeDoesNotAffectSkipLogic

### Community 1363 - "conftest.py"
Cohesion: 0.27
Nodes (11): _assert_test_database(), captured_spans(), client(), db_session(), engine(), fixture, pytest_sessionstart(), Collect the stage spans a block of code emits.… (+3 more)

### Community 1364 - "test_tenant_document_registry.py"
Cohesion: 0.20
Nodes (11): _backfill_registry_from_schema(), fixture, Verification for `public.tenant_document_registry` (ADR-017). Maps to…, The same projection alembic migration 043 runs per platform tenant schema,…, Scenario: Existing documents are backfilled. Given a platform tenant with 5…, A throwaway tenant schema shaped like `documents` at head 042 (migration 038's…, Scenario: Registry schema holds no content columns., registry_source_schema() (+3 more)

### Community 1365 - "entities.py"
Cohesion: 0.38
Nodes (10): _get_tenant_id(), _get_user_id(), list_entities(), patch_entity(), AsyncSession, get, Request, EntityItem (+2 more)

### Community 1366 - "DatabasePoolCollector"
Cohesion: 0.20
Nodes (7): DatabasePoolCollector, init_db_pool_metrics(), instrument_app(), Register the pool collector once per process. Re-registering raises in…, Expose `/metrics` on a FastAPI service. The endpoint is mounted on the app…, Reports database connection usage at scrape time. The obvious implementation —…, Bind to the engine's pool events, once, on the first scrape that finds one.…

### Community 1367 - "test_tenant_data_plane_record.py"
Cohesion: 0.18
Nodes (9): Verification for `public.tenant_data_planes` — the ADR-017 control-plane…, Scenario: Data-plane record carries no sensitive values. A finite column check…, A freshly inserted tenant with no data-plane row is a bug this test would catch…, Scenario: Existing tenants are backfilled to the platform plane., Scenario: Mode cannot be changed. The immutability trigger raises a Postgres…, test_backfilled_tenant_owned_tenant_is_not_auto_created(), test_existing_tenants_are_backfilled_to_platform_ready(), test_mode_cannot_be_changed() (+1 more)

### Community 1368 - "test_tenant_provisioning_data_plane.py"
Cohesion: 0.31
Nodes (10): auth_header(), AsyncClient, asyncio, Verification for tenant creation with `data_plane_mode` (ADR-017, task 9.3) —…, Scenario: System Admin creates a tenant-owned data plane tenant., Scenario: Invalid data plane mode is rejected., Feature-flag gating: creating a tenant_owned tenant is rejected when disabled., test_invalid_data_plane_mode_is_rejected() (+2 more)

### Community 1369 - "widget_keys.py"
Cohesion: 0.31
Nodes (9): create_widget_key(), get_session(), list_widget_keys(), AsyncSession, delete, get, post, Request (+1 more)

### Community 1370 - "test_relational_projection_generator.py"
Cohesion: 0.31
Nodes (4): Pure-function tests for the relational projection. Database-free, deliberately.…, verification.md rows 4, 22, 32, _subject(), TestSubjectRow

### Community 1371 - "Tenant"
Cohesion: 0.24
Nodes (3): fixture, A tenant schema plus the handful of helpers every test below needs., Tenant

### Community 1372 - "Tenant-Owned PostgreSQL Data Plane — Customer Prerequisites Runbook"
Cohesion: 0.22
Nodes (8): 1. Server, 2. The `vector` extension, 3. A dedicated database, 4. A login role for the platform's connection, 5. The query role — two supported paths, 6. Network reachability, 7. What happens if a prerequisite is missing later, not at setup, Tenant-Owned PostgreSQL Data Plane — Customer Prerequisites Runbook

### Community 1373 - "tenant-postgresql-data-plane/proposal.md"
Cohesion: 0.22
Nodes (8): Capabilities, Change Notes, Impact, Modified Capabilities, New Capabilities, Open Questions, What Changes, Why

### Community 1374 - "Requirement: Tenant provisioning clones the template atomically"
Cohesion: 0.22
Nodes (8): ADDED Requirements, MODIFIED Requirements, Requirement: Tenant provisioning clones the template atomically, Requirement: Tenant-scoped migrations also reach residency stores, Scenario: A column added by migration reaches both planes, Scenario: A failed table clone rolls back the whole tenant, Scenario: A provisioned tenant has the full template table set, Scenario: A tenant-owned tenant is not cloned on the platform

### Community 1375 - "build_relational_delete_statements"
Cohesion: 0.31
Nodes (4): build_relational_delete_statements(), Clear this document from every **existing** generated table, plus its `subject`…, verification.md rows 27, 28, 30, TestDeleteStatements

### Community 1376 - "select_single_value"
Cohesion: 0.31
Nodes (4): The one value a `single` definition contributes to the document's `subject`…, select_single_value(), verification.md rows 16-18, TestSingleValueSelection

### Community 1377 - "training_service/api/v1/schemas.py"
Cohesion: 0.39
Nodes (8): ApproveJobRequest, ModelVersionListResponse, ModelVersionPromoteRequest, BaseModel, RejectJobRequest, TrainingJobCreate, TrainingJobListResponse, TrainingJobResponse

### Community 1378 - "TestBackfillSemanticValues"
Cohesion: 0.39
Nodes (3): asyncio, Covers verification.md rows 26-28., TestBackfillSemanticValues

### Community 1379 - "test_data_plane_route_gate.py"
Cohesion: 0.28
Nodes (8): awaiting_store_tenant(), _bearer(), fixture, Verification for the content-route readiness gate (ADR-017, Design D9) —…, Scenario: Awaiting-store tenant cannot upload., Scenario: Awaiting-store tenant administrator can configure the store. Data-…, test_awaiting_store_tenant_administrator_can_configure_the_store(), test_awaiting_store_tenant_cannot_upload()

### Community 1380 - "test_data_plane_connection_replacement.py"
Cohesion: 0.32
Nodes (7): fixture, Verification for "Replacement connections must point at the same store"…, The stored configuration validates as `sslmode=verify-full` (production shape);…, A `tenant_owned` tenant already `ready`, with a real `tenant_<id>` schema and…, ready_tenant_with_real_store(), _relax_data_plane_tls(), _store_engine()

### Community 1381 - "test_data_plane_health.py"
Cohesion: 0.39
Nodes (7): _cleanup(), _make_ready_tenant(), Verification for "Per-tenant store health is a content-free control-plane…, Scenario #29: Service stays ready during a tenant outage., Scenario #30: Recovery is detected., test_scenario_29_service_stays_ready_during_a_tenant_outage(), test_scenario_30_recovery_is_detected()

### Community 1382 - "test_upload_precheck.py"
Cohesion: 0.29
Nodes (7): _bearer(), fixture, Verification for "Uploads are rejected before bytes are accepted when the store…, A `ready` `tenant_owned` tenant whose store is actually unreachable —…, Scenario: Upload during outage writes nothing., test_upload_during_outage_writes_nothing(), unreachable_ready_tenant()

### Community 1383 - "043_tenant_data_plane.py"
Cohesion: 0.38
Nodes (5): _for_each_platform_tenant_schema(), _quoted(), tenant data plane control plane: tenant_data_planes, tenant_document_registry,…, Apply one statement to every provisioned platform tenant schema. `statement` is…, upgrade()

### Community 1384 - "Requirement: Tenant Creation"
Cohesion: 0.29
Nodes (6): MODIFIED Requirements, Requirement: Tenant Creation, Scenario: Invalid data plane mode is rejected, Scenario: System Admin creates a tenant-owned data plane tenant, Scenario: System Admin creates a tenant with duplicate slug, Scenario: System Admin creates a tenant with valid data

### Community 1385 - "test_tenant_engine_construction_boundary.py"
Cohesion: 0.38
Nodes (6): _iter_py_files(), Source checks for the tenant-data-plane-routing spec's scenario #7: "Workers…, Guards the allowlist itself against typos/renames going stale., test_allowlist_files_actually_exist(), test_no_cross_schema_public_join_in_tenant_session_sql(), test_no_direct_platform_engine_construction_outside_allowlist()

### Community 1386 - "reconcile_entity_tables_sync"
Cohesion: 0.33
Nodes (4): Connection, `reconcile_entity_tables` for a synchronous `Connection`. The extraction worker…, reconcile_entity_tables_sync(), Both executors share one plan; only `execute` differs. The worker reconciles at…

### Community 1387 - "Requirement: System Admin chooses and observes the tenant data plane"
Cohesion: 0.40
Nodes (4): ADDED Requirements, Requirement: System Admin chooses and observes the tenant data plane, Scenario: Document counts remain visible during a tenant outage, Scenario: System Admin creates a tenant-owned tenant

### Community 1388 - "infer"
Cohesion: 0.67
Nodes (3): infer(), _infer_url(), Request

## Ambiguous Edges - Review These
- `OpenSpec Sync Specs Skill (Claude)` → `OpenCode OpsX Archive Command`  [AMBIGUOUS]
  .opencode/commands/opsx-archive.md · relation: calls
- `OpenSpec Sync Specs Skill (Claude)` → `OpenCode OpsX Bulk Archive Command`  [AMBIGUOUS]
  .opencode/commands/opsx-bulk-archive.md · relation: references
- `OpenSpec CLI` → `OPSX: Ask Command (VSCode Ask Agent)`  [AMBIGUOUS]
  .claude/commands/opsx/ask.md · relation: conceptually_related_to
- `Tenant Self-Service Data Sources — requirements baseline v1.2` → `Deploy Platform to Kubernetes on Azure (AKS) — requirements baseline`  [AMBIGUOUS]
  docs/requirement/deploy-platform-kubernetes-azure.md · relation: conceptually_related_to
- `Fix Dark Theme Issues - Tasks` → `Logo (Dark Theme) SVG`  [AMBIGUOUS]
  src/openspec/changes/fix-dark-theme-issues/tasks.md · relation: conceptually_related_to
- `Fix Dark Theme Issues - Tasks` → `Logo (Light Theme) SVG`  [AMBIGUOUS]
  src/openspec/changes/fix-dark-theme-issues/tasks.md · relation: conceptually_related_to
- `ADR-002: Single Curated Base Model Strategy (No BYOM)` → `ADR-003: Per-Tenant Model Serving Topology (Shared Pool + Routing)`  [AMBIGUOUS]
  docs/adr/003-model-serving-topology.md · relation: conceptually_related_to

## Knowledge Gaps
- **9382 isolated node(s):** `$schema`, `plugin`, `vendorRoot`, `SessionMessage`, `SessionMessageInfo` (+9377 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 12699 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **38 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `OpenSpec Sync Specs Skill (Claude)` and `OpenCode OpsX Archive Command`?**
  _Edge tagged AMBIGUOUS (relation: calls) - confidence is low._
- **What is the exact relationship between `OpenSpec Sync Specs Skill (Claude)` and `OpenCode OpsX Bulk Archive Command`?**
  _Edge tagged AMBIGUOUS (relation: references) - confidence is low._
- **What is the exact relationship between `OpenSpec CLI` and `OPSX: Ask Command (VSCode Ask Agent)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Tenant Self-Service Data Sources — requirements baseline v1.2` and `Deploy Platform to Kubernetes on Azure (AKS) — requirements baseline`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Fix Dark Theme Issues - Tasks` and `Logo (Dark Theme) SVG`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `Fix Dark Theme Issues - Tasks` and `Logo (Light Theme) SVG`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `ADR-002: Single Curated Base Model Strategy (No BYOM)` and `ADR-003: Per-Tenant Model Serving Topology (Shared Pool + Routing)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._