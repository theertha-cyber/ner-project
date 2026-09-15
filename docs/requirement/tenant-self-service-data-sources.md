# Tenant Self-Service Data Sources — End-to-End Discovery and Requirements Baseline

## Document Control

| Field | Value |
|---|---|
| Title | Tenant Self-Service Data Sources |
| Version | 1.2 |
| Status | Ready for Architecture |
| Date | 2026-09-09 |
| Prepared from | Prior approved baseline v1.1 at this path; run history and user clarification for `tenant-self-service-data-sources-20260909`; brownfield codebase discovery validated for `tenant-self-service-data-sources-20260909-2` on 2026-09-09; `PROJECT.md`; `AGENTS.md` |
| Owners and approvers | Requester is product owner and release approver. Tenant administrators operate connections. |

## Executive Summary

The feature changes the platform from upload-only document intake to a tenant-admin self-service, finite provider catalog. It adds Azure Blob Storage as a synchronized document source and Azure Database for PostgreSQL as a tenant-managed, read-only structured-data chat source. Derived document data—text spans, chunks, embeddings, NER outputs, provenance, and sync state—remains in platform PostgreSQL/pgvector; tenant Azure PostgreSQL rows remain in the tenant database and are never ingested or copied. Brownfield seams exist for normalized upload ingestion, control-plane profiles, secret references, and platform chat, but external pull synchronization, self-service lifecycle, durable dispatch, external database chat, and schema-contract indexing are not implemented; this was revalidated against the implementation for run `tenant-self-service-data-sources-20260909-2`. Tenant resources, network access, provider quotas, and test environments are onboarding/deployment prerequisites rather than assumed platform facts; activation requires a secure credential connection test. Readiness: Ready for Architecture; scale and operating targets are intentionally delegated to Architecture and Operations for proposal and approval.

## Business Context and Success Measures

- **Business outcome** — Tenant administrators configure, test, activate, deactivate, update, and use supported sources without developer intervention. Status: Confirmed.
- **Product boundary** — The release is a finite, platform-supported provider catalog, not arbitrary connector support. Status: Confirmed.
- **Success measure** — The ten acceptance outcomes in FR-001 through FR-010 are the stated delivery outcomes; each requires executable verification in the eventual OpenSpec change. Status: Confirmed.
- **Commercial schedule and budget** — The requester supplied no delivery constraints; scope is not constrained by deadline, budget shape, or resourcing. Status: Confirmed.

## Stakeholders, Users, Roles and Personas

- **Tenant administrator** — Sole role allowed to manage, test, activate, deactivate, replace, delete connections, and upload schema contracts. Status: Confirmed.
- **Authorized chatbot user** — May use active tenant-scoped document retrieval and/or direct structured-data chat; approved contract fields are equally available in this release. Status: Confirmed.
- **Product owner and release approver** — The requester is both product owner and release approver; FR-001 through FR-013 are the acceptance basis. Status: Confirmed.
- **Platform engineering, Security, Data, QA, DevOps, Operations** — Downstream delivery and assurance stakeholders. Status: Confirmed.

## Scope
### In Scope
- Platform Upload and Azure Blob Storage document intake; common downstream processing; manual and scheduled Azure Blob synchronization. Status: Confirmed.
- Per-tenant connection control plane, provider-specific portal forms, safe connection tests, activation lifecycle, secret references, and safe status reporting. Status: Confirmed.
- Azure Database for PostgreSQL direct, read-only structured-data chat, supporting joins across contract-approved relationships and aggregation, using a tenant-uploaded, versioned schema-contract JSON and tenant-isolated schema vector index. Status: Confirmed.
- Server-side, auditable, tenant-scoped source/capability selection. Status: Confirmed.

### Out of Scope
- Arbitrary connectors; Keka, S3, SharePoint, non-Azure databases, external vector stores, tenant-managed pgvector, and a platform-wide hexagonal rewrite. Status: Confirmed.
- Persisting document-derived data in a tenant-managed database; derived data remains in platform PostgreSQL/pgvector. Status: Confirmed.
- Database writes, DDL, migrations, views, materialized views, stored procedures, direct LLM database access, and copying tenant database rows to the platform. Status: Confirmed.
- Role- or column-specific field visibility and usage limits. Status: Confirmed.
- Subqueries/CTEs, UNION, and window functions in direct database chat SQL. Status: Confirmed.

### Future Scope
- Additional providers behind contained runtime-provider boundaries. Status: Deferred.

## Current State

- **Upload flow** — `POST /api/v1/documents` obtains tenant identity from request state, normalizes platform-upload content, and calls `DocumentIngestionService.ingest()`. Status: Confirmed. Evidence: `src/document_service/api/v1/documents.py:64-112`.
- **Common ingestion and retention** — Ingestion writes tenant-schema document/provenance records and supports durable, ephemeral, and source-only retention modes; source-only cannot currently finish processing because no reopenable external source exists. Status: Confirmed. Evidence: `src/document_service/ingestion/service.py:142-256`; `src/document_service/services/ocr_worker.py:300-334`.
- **Derived data plane** — OCR writes spans and query chunks/embeddings; extraction writes entities and normalized projections in platform PostgreSQL/pgvector. Status: Confirmed. Evidence: `src/document_service/services/ocr_worker.py:385-531`; `src/extraction_service/worker.py:350-494`.
- **Control plane** — A tenant integration profile and typed, secret-reference configuration schema exist, but profiles are explicitly not tenant-facing and only platform-default adapters can activate. Status: Confirmed. Evidence: `src/shared/integration_profile/service.py:1-5,161-175`; `src/shared/integration_profile/config_schema.py:59-144`.
- **Chat** — Existing tools and SQL validation operate only over platform document/entity relations; no external connector, schema-contract artifact, or schema vector index exists. Status: Confirmed. Evidence: `src/shared/retrieval/orchestrator.py:15-68`; `src/chat_api/services/sql_generator.py:1107-1223`.
- **Durability gap** — OCR dispatch is an in-process asyncio task, while extraction uses Celery; a scheduled external sync cannot rely on request-process dispatch. Status: Confirmed. Evidence: `src/document_service/ingestion/dispatcher.py:18-26`; `src/extraction_service/api/v1/extraction.py:187-216`.
- **Documented versus implemented** — The feature brief calls for Azure Blob sync and Azure PostgreSQL chat; implementation currently supports platform defaults and uploads only. Status: Confirmed. Evidence: this document’s source §6–§8; `src/shared/integration_profile/adapters.py:11-28`.

## User Journeys and Business Workflows

- **Connection administration** — Tenant administrator creates a provider-specific draft, supplies settings/credentials, tests it, sees a safe outcome, and activates only a passing supported configuration. Status: Confirmed.
- **Blob synchronization** — An active connection runs the same idempotent use case for manual and scheduled sync: enumerate, identify new/changed objects, obtain bytes, invoke common ingestion, and persist safe source/version/outcome state. Status: Confirmed.
- **Direct database chat** — An authorized user asks a question; the server resolves the tenant’s active capability, retrieves relevant approved schema context, validates proposed SQL against the canonical contract/current state, executes only validated read-only SQL, and returns an answer without persisting rows. Status: Confirmed.
- **Drift response** — Before every direct query, the platform checks drift; a mismatch blocks chat until the administrator provides a replacement contract. Status: Confirmed.

## Functional Requirements
| ID | Requirement | Source | Stakeholder | Journey | Acceptance Criterion | Status |
|---|---|---|---|---|---|---|
| FR-001 | Tenant admins alone can manage supported connection drafts, tests, activation, deactivation, replacement and deletion. | Brief §5 | Tenant admin | Connection administration | Non-admin denied; admin configures/tests Azure Blob. | Confirmed |
| FR-002 | Store credentials only in approved secret management; records retain only a secret reference and non-sensitive metadata. | Brief §5 | Tenant admin, Security | Connection administration | Missing secret/test failure prevents activation and leaks no sensitive value. | Confirmed |
| FR-003 | Refuse unsupported, incomplete, or failed-test configurations. | Brief §5 | Tenant admin | Connection administration | Safe failure is shown and activation is prevented. | Confirmed |
| FR-004 | Route Platform Upload and Azure Blob bytes through one common ingestion pipeline without Azure branching in OCR, NER, chunking, extraction, or chat. | Brief §6.1 | Product, Development | Blob synchronization | New Blob document reaches common pipeline. | Confirmed |
| FR-005 | Support manual and scheduled idempotent Azure Blob sync; default cadence is 15 minutes and one idempotent catch-up runs after a missed schedule. | Brief §6.2; Run history | Tenant admin | Blob synchronization | Manual and scheduled sync ingest new document without duplicates. | Confirmed |
| FR-006 | Persist source identity/version, safe provenance, derived outputs and sync state in platform PostgreSQL/pgvector; retain no durable Blob original in MinIO and delete temporary bytes at terminal outcome. | Brief §6.2, §9; Run history | Product, Data | Blob synchronization | Derived data exists and durable original does not. | Confirmed |
| FR-007 | Hide derived records from retrieval when their Azure Blob source is deleted. | Run history | Tenant admin | Blob synchronization | Deleted-source records are not retrieved. | Confirmed |
| FR-008 | Reprocess a changed Blob document by replacing its prior derived version, without duplicate derived outputs. | Brief §6.2; Run history | Product, Data | Blob synchronization | Retry/unchanged creates no duplicate; changed version replaces prior derived version. | Confirmed |
| FR-009 | Permit one active document source and one active PostgreSQL connection per tenant, including Azure Blob and Azure PostgreSQL concurrently. | Run history | Tenant admin | Connection administration | Tenant can operate the permitted concurrent capabilities. | Confirmed |
| FR-010 | Support direct, read-only Azure PostgreSQL chat; validate one SELECT statement against approved tables/columns/join paths, permitting joins across contract-approved relationships, aggregation (COUNT/SUM/AVG/MIN/MAX), GROUP BY, HAVING, WHERE, ORDER BY, DISTINCT, column aliasing and basic date/time functions, with row limit and timeout before execution. | Brief §7 | Authorized chatbot user | Direct database chat | Writes/multiple statements/unapproved relation, column or join path never execute; approved joins and aggregations return correct results. | Confirmed |
| FR-011 | Accept only valid, published-version JSON schema contracts; preserve canonical versions and create tenant-isolated schema-index representations. | Brief §7.2 | Tenant admin, Data | Direct database chat | Invalid contract rejected; valid version indexed only for tenant. | Confirmed |
| FR-012 | Check schema drift before every direct query and block direct chat until an updated contract is accepted. | Brief §7.3; Run history | Tenant admin | Drift response | Query after detected drift is blocked before execution. | Confirmed |
| FR-013 | Resolve capabilities server-side per authenticated tenant; a tenant cannot inspect or use another tenant’s connection, contract, metadata, derived records, or index entries. | Brief §8, §11 | All users, Security | All | Cross-tenant access is denied. | Confirmed |

## Reference Scenarios
| ID | Actors | Trigger / Input | Expected Observable Outcome | Source |
|---|---|---|---|---|
| RS-001 | Tenant administrator | Configures and tests Azure Blob connection | Successful configuration test; non-admin cannot perform it. | Brief §11.1 |
| RS-002 | Tenant administrator | Manual or scheduled Blob sync for a new supported document | Common pipeline processes it; derived data is platform-held and no durable MinIO original exists. | Brief §11.3–4 |
| RS-003 | Tenant administrator | Uploads a valid or invalid schema-contract JSON | Valid contract is versioned/indexed tenant-only; invalid JSON/schema is rejected. | Brief §11.6–7 |
| RS-004 | Authorized chatbot user | Questions an active Azure PostgreSQL connection | Only validated, read-only, single-statement, allowlisted SQL executes. | Brief §11.8–9 |
| RS-005 | Tenant administrator | A source object is deleted or changed | Deleted record is hidden; changed object replaces its prior derived version. | Run history |

## Business Rules
| ID | Rule | Source | Status |
|---|---|---|---|
| BR-001 | Provider catalog is explicit and finite. | Brief §1, §4 | Confirmed |
| BR-002 | Azure PostgreSQL is a direct chat source, never a document source or derived-data store. | Brief §2, §4; Run history | Confirmed |
| BR-003 | Blob originals remain tenant-held; temporary processing bytes are deleted after terminal processing. | Brief §6.2 | Confirmed |
| BR-004 | The canonical JSON contract, rather than vector similarity, authorizes queryable relations, columns and join paths between relations. | Brief §7.2 | Confirmed |
| BR-005 | A tenant has at most one document source and one PostgreSQL connection; both paths may be active together. | Run history | Confirmed |

## Data Requirements

- **Derived document data** — Store spans, chunks, embeddings, NER output, provenance, and sync state in platform PostgreSQL/pgvector; do not migrate these to tenant infrastructure. Status: Confirmed.
- **Tenant business data** — Azure PostgreSQL rows remain tenant-owned and are queried read-only at question time without platform dataset retention. Status: Confirmed.
- **Schema contract** — Retain the accepted JSON as a versioned canonical control-plane artifact and its tenant-isolated vector representation; the contract declares an explicit join-graph (approved relationships and join keys between tables), not only a flat per-table column allowlist. Status: Confirmed.
- **Deletion/history** — Hide deleted-source derived records; replace, rather than retain, changed-document derived versions. Status: Confirmed.
- **Classification and handling** — All tenant content is confidential and tenant-scoped. Encrypt it in transit and at rest; enforce tenant isolation and least privilege; never log tenant content, credentials, SQL, prompts, or answers. Status: Confirmed.
- **Retention and legal hold** — Originals are temporary only; derived document data and chat use existing platform retention. A tenant-specific legal hold, retention, or residency requirement requires approval before that tenant is activated. This release makes no new jurisdictional promise. Status: Confirmed.
- **Recovery objectives** — Architecture and Operations shall propose scale, availability, recovery, and operating targets for requester approval. Status: Deferred.

## Integration Requirements

- **Azure Blob Storage** — Customers own the Azure resources. Architecture must define the self-service configuration, secret-reference, least-privilege, and secure credential connection-test requirements. Tenant network paths, IP rotation, quotas, sandboxes, provider engine/version details, and equivalent provider-specific facts are onboarding/deployment prerequisites; they must be verified before activation and are not assumed by this baseline. Status: Confirmed.
- **Azure Database for PostgreSQL** — Customers own the Azure resources and provide the tenant-managed read-only connection. The platform must validate it through a secure credential connection test before activation; network and provider prerequisites are verified during onboarding/deployment. Status: Confirmed.
- **Secret management** — Use the platform-approved secret-management path, retaining references only; production-capable secret-reference resolution is an architecture, Security, and DevOps design obligation. The current resolver supports only `env://`, while `PROJECT.md` names Vault. Status: Confirmed.

## UI/UX and Accessibility Requirements

- **Portal** — Provider-specific configuration, test results, activation lifecycle, status, safe aggregate outcomes, schedule state, and active schema-contract version are required. Status: Confirmed.
- **Safe feedback** — Never display secrets, connection strings, remote document content, SQL, prompts/answers, or provider error values that contain sensitive data. Status: Confirmed.
- **Accessibility, browser/device support, localisation, UX analytics** — Not specified; UX must establish before detailed UI design. Status: Open – Non-blocking.

## Security, Privacy and Compliance Requirements
| ID | Requirement | Driver (regulation / policy / risk) | Evidence Needed | Status |
|---|---|---|---|---|
| SEC-001 | Enforce authenticated tenant scope and tenant-admin-only connection administration. | Cross-tenant and privilege-escalation risk | Authorization and isolation tests | Confirmed |
| SEC-002 | Keep credentials in approved secret management and never plaintext control-plane storage. | Project secret invariant | Secret-storage and access-path review | Mandated |
| SEC-003 | Prohibit sensitive values in logs, metrics, traces, and audit payloads. | Project telemetry invariant; tenant data risk | Telemetry scan and negative tests | Mandated |
| SEC-004 | Validate external SQL before execution: single read-only SELECT, contract-allowlisted tables/columns/join paths, limit, timeout, no direct LLM database access. | SQL injection/data integrity risk | Validator and connector negative tests | Confirmed |
| SEC-005 | Define Azure network controls, least-privilege database role, credential rotation, audit access, and the activation evidence for any tenant-specific governance obligation. | External tenant data exposure | Security/threat-model, least-privilege review, and tenant-activation approval record where applicable | Open – Non-blocking |
| SEC-006 | Treat all tenant content as confidential and tenant-scoped; encrypt in transit and at rest, isolate tenants, enforce least privilege, and prohibit tenant content, credentials, SQL, prompts, and answers from logs, metrics, traces, and audit payloads. | Requester clarification; project telemetry invariant | Threat model, encryption/configuration review, isolation tests, telemetry scan | Confirmed |
| SEC-007 | Before tenant activation, obtain approval for any tenant-specific legal hold, retention, residency, or other jurisdictional obligation; do not represent a new jurisdictional promise in this release. | Requester clarification | Recorded governance approval and activation-gate evidence | Confirmed |

## Non-Functional Requirements
| ID | Metric | Target | Measurement Point | Workload / Condition | Validation Method | Environment | Owner | Status |
|---|---|---|---|---|---|---|---|---|
| NFR-RELY-001 | Sync idempotency | No duplicate derived records for retry or unchanged object | Document/provenance and derived-data stores | Manual, scheduled, retry and catch-up sync | Integration tests | Production-like | QA/Data | Confirmed |
| NFR-RELY-002 | Drift enforcement | Drift check before every direct query; mismatch prevents execution | Direct-query request path | Active database connection | Integration/negative tests | Production-like | QA/Security | Confirmed |
| NFR-SECU-001 | Sensitive telemetry exposure | Zero prohibited payload classes | Logs, metrics, traces, audit payloads | Success and failure paths | Automated telemetry scan and review | CI and staging | Security | Mandated |
| NFR-PERF-001 | Sync and chat latency/capacity | Architecture shall propose measurable service, sync, capacity, and cost operating targets for requester approval; no target is approved in this baseline. | End-to-end source sync and direct-query response | Agreed production-like tenant workload | Performance test against approved targets | Production-like | Architect/Operations; requester approves | Deferred |
| NFR-AVAIL-001 | Availability/uptime | Architecture and Operations shall propose an availability target and service-operating objectives for requester approval; no target is approved in this baseline. | Tenant source and chat capability | Production operation | SLO monitoring and availability test against approved target | Production | Architect/Operations; requester approves | Deferred |
| NFR-DR-001 | Recovery objectives | Architecture and Operations shall propose RPO/RTO, restore, and DR-test targets for requester approval. | Platform-held derived data and connection control plane | Production incident and recovery exercise | Restore/DR exercise against approved targets | Production-like | Architect/Operations; requester approves | Deferred |
| NFR-OPS-001 | Observability | Safe aggregate connection/sync outcome and existing structured telemetry | Control-plane and worker operations | All source lifecycle outcomes | Dashboard/alert and telemetry review | Staging | Operations | Confirmed |

## Architecture-Driving Requirements and Constraints

- **Runtime provider isolation** — Provider SDK knowledge must not leak into common OCR, NER, chunking, extraction, or chat behavior. Status: Confirmed.
- **Separate paths** — Document-source ingestion and direct structured-data chat may share administration/secrets but are not interchangeable abstractions. Status: Confirmed.
- **Tenant runtime configuration** — Capability resolution must be tenant-scoped and not process-global. Status: Confirmed.
- **Durable background work** — Scheduled synchronization must be durable, observable, retry-safe, idempotent, and not an unbounded web-request task. Status: Confirmed.
- **Compatibility** — Preserve platform upload route/authorization behavior and current document-derived chat while extending it. Status: Confirmed.
- **Tenant activation gate** — Activation cannot assume a customer network, IP rotation, quota, sandbox, or provider version; it requires successful secure credential connection testing and evidence that applicable onboarding/deployment prerequisites are met. Status: Confirmed.

## Technology Constraints, Preferences and Open Selections
| Area | Item | Tech Status | Driver / Rationale | Decision Owner |
|---|---|---|---|---|
| Frontend | Existing React/Next.js portal | Existing constraint | `PROJECT.md` | Architect |
| Backend | Existing FastAPI/Python services | Existing constraint | `PROJECT.md` | Architect |
| Data stores | Platform PostgreSQL 16 with pgvector for derived document data | Mandated | Feature boundary and `PROJECT.md` | Architect |
| Integration | Azure Blob Storage document source | Mandated | Initial provider catalog | Architect |
| Integration | Azure Database for PostgreSQL direct chat source | Mandated | Initial provider catalog | Architect |
| Infrastructure | Vault-approved secret-management path | Existing constraint | `PROJECT.md` | Security/DevOps |
| Background work | Existing RabbitMQ/Celery capability | Existing constraint | `PROJECT.md`; durable-sync need | Architect |

## Environment and Infrastructure Requirements

- **Environments** — Azure resource access, subscriptions/regions, private connectivity/allowlists, provider limits, and any sandbox are customer/onboarding/deployment prerequisites. Architecture, Security, and DevOps must define the evidence required to activate a connection without assuming their availability. Status: Confirmed.
- **Temporary storage** — Blob processing uses working storage only and deletes temporary bytes at terminal outcome. Status: Confirmed.
- **Infrastructure provisioning and access ownership** — IaC, privileged access, certificate/DNS, cost/tagging, environment ladder, targets, deployment strategy, and approval policy must be proposed by Architecture/DevOps for requester approval. Status: Deferred.

## Engineering and Quality Requirements

- **SDD** — Follow OpenSpec governance; no implementation authorization is granted by this baseline. Status: Mandated.
- **Executable acceptance evidence** — Every eventual acceptance criterion requires an executable artifact that fails when its THEN condition is violated. Status: Mandated.
- **Existing platform safeguards** — Preserve tenant-schema isolation, structured observability, and unchanged upload compatibility. Status: Confirmed.
- **Known remediation** — OCR worker currently prints traceback/interpolates exception data, conflicting with telemetry invariants; touched work must remediate or explicitly isolate this risk. Status: Open – Non-blocking.

## Testing and Acceptance Strategy

- **Functional acceptance** — Verify FR-001 through FR-013, including lifecycle authorization, safe failures, both sync triggers, temporary-content cleanup, idempotency, replacement, contract validation/indexing, SQL validation, drift blocking, concurrency limits and tenant isolation. Status: Confirmed.
- **Integration testing** — Use controlled customer-approved Azure Blob/Azure PostgreSQL resources or approved equivalents; activation tests verify secure credentials and prerequisites without recording tenant content or credentials. Status: Confirmed.
- **Security testing** — Test cross-tenant access, secrets/telemetry leakage, malformed contracts, SQL writes/multi-statements/allowlist bypass and drift bypass. Status: Confirmed.
- **NFR acceptance** — Architecture/Operations propose performance, availability, recovery, and support targets; requester approves the resulting release acceptance targets before release. Status: Deferred.

## Delivery, Release and Deployment Requirements

- **Release safety** — Preserve existing upload and platform-derived retrieval behavior; use controlled tenant rollout capability where available. Status: Confirmed.
- **Strategy and approvals** — Requester is release approver. Architecture/DevOps must propose deployment ladder, strategy, rollback/roll-forward rules, maintenance window, data rollback limits, and supporting approval policy before release. Status: Deferred.
- **Data migration** — Additive control-plane/provenance/schema-contract changes need backward-compatible migration and reconciliation; exact migration plan is architecture/design work. Status: Open – Non-blocking.

## Migration and Rollout Requirements

- **Existing behavior** — Platform Upload remains a supported document source and must preserve current behavior for existing users. Status: Confirmed.
- **Transition** — Existing tenant integration profiles are defaulted/backfilled; new per-tenant source limits and activation behavior need compatibility evaluation against existing profiles. Status: Open – Non-blocking.
- **Decommissioning** — Not Applicable — no system replacement or legacy source retirement is specified.

## Operations and Support Requirements

- **Connection/sync visibility** — Show safe status, last test/sync outcome, last successful sync time, and aggregate counts/outcomes. Status: Confirmed.
- **Support model and SLOs** — Architecture and Operations must propose service/operational ownership, support hours, alert thresholds, incident escalation, backup/restore, DR objectives, and operating targets for requester approval. Status: Deferred.
- **Runbooks** — Require source-test failure, credential rotation, sync failure/catch-up, drift-blocked chat, and tenant-isolation incident procedures. Status: Recommended.

## Traceability Matrix
| Requirement ID | Source | Stakeholder / Owner | Acceptance Criterion | Validation Method | Status |
|---|---|---|---|---|---|
| FR-001–003 | Brief §5, §11.1–2 | Tenant admin/Security | Admin-only safe lifecycle | API/UI authorization and negative tests | Confirmed |
| FR-004–008 | Brief §6, §9, §11.3–5; Run history | Product/Data | Common, safe, idempotent Blob processing | Integration and lifecycle tests | Confirmed |
| FR-009 | Run history | Product | Permitted concurrent sources | Control-plane integration tests | Confirmed |
| FR-010–012 | Brief §7, §11.6–9; Run history | Tenant admin/Security/Data | Contract-controlled direct chat and drift block | Contract, validator and connector tests | Confirmed |
| FR-013 | Brief §8, §11.10 | Security | No cross-tenant visibility/use | Isolation tests | Confirmed |

## Decision Register
| ID | Decision Required | Context and Constraints | Options | Recommendation | Owner | Decision Deadline | Status | Downstream Impact |
|---|---|---|---|---|---|---|---|---|
| DEC-001 | Azure drift-detection implementation | Must check before every query and block on mismatch | Metadata comparison; live schema introspection; equivalent verifiable mechanism | Architect/Security select a mechanism meeting FR-012 | Architect/Security | Before detailed design | Open – Non-blocking | External connector, test plan |
| DEC-002 | External connection network/identity model | Customer-owned Azure resources; self-service configuration, secret refs, connection test, and least privilege must be defined. Network, IP rotation, quota, sandbox, and provider facts are verified onboarding/deployment prerequisites rather than assumed. | Approved connectivity/identity patterns compatible with customer prerequisites | Security/DevOps define acceptable patterns and activation evidence | Security/DevOps | Before implementation | Open – Non-blocking | Security, infrastructure |
| DEC-003 | Tenant-specific legal-hold, retention, residency, and jurisdiction approval | All tenant content is confidential; existing platform retention applies to derived data/chat; no new jurisdiction promise. | Tenant has no special obligation; obligation documented and approved before activation | Security/Product establish activation approval record | Security/Product | Before affected tenant activation | Open – Non-blocking | Data, security, operations |
| DEC-004 | Measurable capacity/availability/recovery targets | Requester directs Architecture to propose scale and operating targets. | Architecture/Operations proposals for requester approval | Propose measurable targets and approval criteria | Architect/Operations; requester approves | Before release approval | Deferred | NFR, infrastructure, QA |
| DEC-005 | Delivery constraints | Requester confirmed no deadline, budget, or resourcing constraint. | Not Applicable | No action required unless constraints are introduced | Requester | Not Applicable | Not Applicable | Scope and roadmap |
| DEC-006 | Formal acceptance and release authority | Requester confirmed that they are product and release approver; FR-001–FR-013 are the acceptance basis. | Not Applicable | No action required | Requester | Not Applicable | Confirmed | All workstreams |

## Assumption Register
| ID | Assumption | Reason | Validation Owner | Validation Deadline | Impact if Incorrect |
|---|---|---|---|---|---|
| ASM-001 | No customer Azure connectivity, IP rotation, quota, sandbox, or provider-version condition is assumed before activation. | Requester explicitly requires these to be onboarding/deployment prerequisites. | Security/DevOps | Before affected tenant activation | Connection cannot be safely activated. |
| ASM-002 | Existing tenant-admin authorization model can be extended without changing non-admin access behavior. | Current route behavior exists, self-service lifecycle does not. | Architect/Security | Before detailed design | Privilege or compatibility regression. |

## Dependency Register
| ID | Dependency | Type | Owner | Needed By | Status | Impact if Unavailable |
|---|---|---|---|---|---|---|
| DEP-001 | Completed `tenant-pluggable-data-foundation` seams | Internal change | Platform team | Architecture | Confirmed | Cannot safely extend documented seam. |
| DEP-002 | Azure Blob tenant resource, access, and prerequisite evidence | External integration | Customer/Azure owner | Affected tenant activation and integration testing | Open – Non-blocking | Blob capability remains inactive for that tenant. |
| DEP-003 | Azure PostgreSQL tenant resource, read-only credential, test schema, and prerequisite evidence | External integration | Customer/Azure owner | Affected tenant activation and integration testing | Open – Non-blocking | Direct chat remains inactive for that tenant. |
| DEP-004 | Approved production secret-manager integration | Platform security | Security/DevOps | Implementation | Open – Non-blocking | Credentials cannot meet requirement. |

## Risk Register
| ID | Risk | Likelihood | Impact | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|
| RSK-001 | Cross-tenant connector or schema-index selection | Medium | High | Server-side tenant binding and isolation tests | Security | Confirmed |
| RSK-002 | Sensitive tenant data leaks through errors or telemetry | Medium | High | Safe error mapping; structured telemetry scan; prohibit payload logging | Security/Development | Confirmed |
| RSK-003 | Blob retry/change processing duplicates or loses derived state | Medium | High | Durable idempotent source/version ledger and reconciliation tests | Architect/Data | Confirmed |
| RSK-004 | External schema drift causes incorrect or unsafe query | Medium | High | Pre-query drift check and hard block pending updated contract | Architect/Security | Confirmed |
| RSK-005 | In-process OCR dispatch loses scheduled work | High | High | Durable background dispatch before scheduled sync rollout | Architect/DevOps | Confirmed |
| RSK-006 | Customer prerequisite or tenant-specific governance obligation is unmet at activation | Medium | High | Explicit activation evidence for secure connection test, least privilege, and approved legal-hold/retention/residency obligations | Security/Product/DevOps | Confirmed |

## Open Questions
### Blocking
- None. The mandatory elicitation items are settled. Per-tenant Azure and governance conditions are activation prerequisites, not architecture-stage assumptions.

### Non-blocking
- **DEC-001:** Architect and Security select and document a verifiable drift-detection mechanism before detailed design.
- **DEC-002:** Security/DevOps define permitted secure connectivity, identity, secret-reference, least-privilege, test, and activation-evidence patterns before implementation.
- **DEC-003:** Security/Product establish an approval record for any tenant-specific legal hold, retention, residency, or jurisdictional obligation before that tenant activates.
- **DEC-004:** Architecture/Operations propose measurable scale and operating targets for requester approval before release.
- UX establishes accessibility, supported browsers/devices and localisation expectations before UI design.
- DevOps establishes detailed deployment strategy, environment ladder, rollback constraints and operations runbook ownership before release.

## Readiness Assessment

**Overall rating: Ready for Architecture.** The requester has confirmed customer Azure ownership/prerequisite boundaries, confidential tenant-data handling, acceptance and sign-off authority, and absence of delivery constraints. Core scope, storage resolution, workflows, bounded providers, acceptance outcomes, and brownfield impacts are clear; remaining design, per-tenant activation, and release-operating decisions have named owners and deadlines.

| Workstream | Ready / Conditional / Blocked | Evidence | Remaining gap | Owner |
|---|---|---|---|---|
| Product and business | Ready | Goals, scope, outcomes, acceptance, approver, and no delivery constraints confirmed | Tenant-specific governance approval when applicable | Requester/Product |
| UX | Conditional | Admin lifecycle and safe feedback | Accessibility/platform/localisation | UX |
| Architecture | Conditional | Clear path separation and current seams | Drift/network decisions | Architect |
| Data | Conditional | Storage boundary, confidentiality, temporary originals, and existing derived/chat retention clear | Tenant-specific legal-hold/retention/residency approval; recovery targets | Product/Security/Data |
| Security | Conditional | SQL/tenant/telemetry controls and confidential handling clear | Connectivity/identity pattern and activation evidence | Security |
| Development | Conditional | Brownfield entry points and compatibility known | Detailed design and secret integration | Architect |
| QA | Conditional | Acceptance outcomes and risks known | Customer-approved integration resources; proposed NFR targets | QA/Architecture |
| Infrastructure and DevOps | Conditional | Existing K8s/Vault/RabbitMQ context; customer-prerequisite boundary clear | Connectivity pattern, environments, SLO/RPO/RTO, release policy | DevOps |
| Migration | Conditional | Additive profile/provenance migration evidence | Compatibility plan | Architect/Data |
| Operations | Conditional | Required safe status identified | Owner, support model, alerts, DR, operating-target proposal | Operations |

## Delivery Workstreams and Todo List

- **Business analysis** — Maintain FR-001–FR-013 as the acceptance basis and record any tenant-specific governance approval.
- **UX** — Inventory admin portal states and confirm accessibility/platform expectations.
- **Architecture** — Define contained runtime-provider, durable-sync, direct-query, contract-index and drift-check designs within stated boundaries.
- **Security** — Threat-model Azure connectivity, tenant isolation, secrets, SQL validation and sensitive telemetry; approve controls.
- **Data** — Define schema-contract governance, source/version reconciliation, and recovery proposal; apply existing retention unless a tenant-specific approved obligation supersedes it.
- **Development** — Preserve upload compatibility and implement only approved OpenSpec work.
- **Testing** — Build executable coverage for FR/RS/NFR acceptance and Azure integration negatives.
- **DevOps** — Establish permitted connectivity and activation evidence, secret integration, durable jobs, deployment/rollback, monitoring, and operating-target proposals.
- **Migration** — Plan additive/backward-compatible schema/profile transition and reconciliation.
- **Operations** — Define ownership, SLOs, alerts, incident/runbook and handover evidence.

## Handoff Contract

- **Product / BA** — Scope, workflows, FR/BR/RS traceability, acceptance outcomes, and blocking governance decisions.
- **UX** — Tenant-admin and chatbot journeys, required safe states, and unresolved accessibility/platform constraints.
- **Architect** — Current-state evidence, path-separation constraints, data boundaries, compatibility risks, and DEC-001/002.
- **Security** — Tenant, secret, telemetry, SQL-safety requirements and DEC-002/003.
- **Developer** — Confirmed behavior, existing seams, compatibility constraints, and no implementation authorization before OpenSpec approval.
- **QA** — FR/RS traceability, negative security cases, idempotency/drift criteria, and open NFR targets.
- **DevOps** — Durable-sync, environment, secret, network, deployment, recovery and monitoring needs.
- **Operations** — Required safe status and unresolved SLO/support/runbook/DR ownership.
