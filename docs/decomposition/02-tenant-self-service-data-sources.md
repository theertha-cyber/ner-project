# Feature Decomposition: Tenant Self-Service Data Sources

**Format version:** 1
**Requirement:** docs/requirement/tenant-self-service-data-sources.md

## Summary

Extend the existing upload-only platform with a finite, tenant-admin-managed Azure Blob document source and Azure Database for PostgreSQL direct structured-data chat source. This increment adds the tenant-scoped control plane, durable Blob synchronization, contract-governed external query path, portal administration surfaces, and local Compose verification while preserving platform uploads, platform-derived retrieval, and existing platform SQL chat.

## Source Documents

- `docs/requirement/tenant-self-service-data-sources.md` (FR-001–FR-013; RS-001–RS-005)
- `docs/design/tenant-self-service-data-sources.md`
- `docs/design/ui-inventory.md`
- `docs/design/ui-contract.md`
- `docs/adr/001-tenant-data-isolation.md`
- `docs/adr/011-tenant-scoped-azure-connection-control-plane.md`
- `docs/adr/012-durable-azure-blob-source-synchronization.md`
- `docs/adr/013-contract-governed-external-postgresql-chat.md`
- `docs/adr/014-local-compose-deployment-topology.md`

## Brainstorm Notes

**What we understand so far:** Existing normalized ingestion already accepts `NormalizedDocument` through `DocumentIngestionService`, but OCR dispatch is in-process and cannot supply durable schedule/recovery. The existing integration profile is a public, tenant-bound seam but currently forbids tenant-facing mutation and non-default activation; ADR-011 and the explicit human authorization supersede those obsolete durable-spec provisions only for Azure Blob and Azure PostgreSQL, so their reconciliation belongs in new OpenSpec change deltas. Existing chat SQL targets platform tenant schemas and must remain separate from the external contract-authorized query path. The three required UI screens are new tenant-admin portal routes and every screen is covered by CAP-5. The rewritten 2026-09-10 TDD §CAP-2 tenant-admin REST contract — normative in `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`, explanatory in the TDD — now fixes routes/payloads, closed provider fields, activation-evidence values, idempotency, list contract, and finite safe errors; this increment implements that contract and does not invent a parallel one.

---

## CAP-2 — Tenant-Scoped Connection Control Plane

**Depends on:** none (foundation capability)
**Owning service:** gateway and shared integration profile
**Satisfies:** FR-001, FR-002, FR-003, FR-009, FR-013; SEC-001, SEC-002, SEC-006, SEC-007
**Governed by:** ADR-001, ADR-011
**Domain:** `tenant-data-source-control-plane`

### Summary

Extend the existing public integration-profile seam into a tenant-admin lifecycle for the two approved Azure provider types. It establishes authoritative server-side tenant capability resolution, bounded lifecycle/testing/activation evidence, source limits, and safe metadata without changing platform-upload behavior.

### Requirements (ADDED)

- **Requirement: Tenant-admin-managed finite connections**
  - The system SHALL allow only an authenticated tenant administrator to create, read, update, test, activate, pause, replace, or retire a connection for Azure Blob Storage or Azure Database for PostgreSQL in that administrator's tenant.
  - Scenario: Tenant administrator tests a supported Azure Blob draft
    - **WHEN** a tenant administrator submits a valid Azure Blob draft and requests a connection test
    - **THEN** the server binds the operation to the authenticated tenant, records only a finite safe outcome class and correlation metadata, and returns no credential, endpoint, provider-error payload, or tenant content.
  - Scenario: Non-administrator is denied
    - **WHEN** a non-administrator requests a connection lifecycle operation
    - **THEN** the operation SHALL be denied and no connection state SHALL change.
- **Requirement: Safe activation and concurrent capability limits**
  - The system SHALL activate a connection only after finite typed configuration validation, resolvable secret reference, successful secure test, required customer network evidence, and applicable governance approval; it SHALL permit at most one active Azure Blob document source and one active Azure PostgreSQL connection for a tenant concurrently.
  - Scenario: Failed prerequisite blocks activation
    - **WHEN** activation is requested for a draft whose test, secret resolution, or required evidence is absent or failed
    - **THEN** the connection SHALL remain inactive and the response SHALL expose only a safe blocking outcome class.

### Requirement Coverage

Requirement §Functional Requirements FR-001–FR-003, FR-009, and FR-013; Technical Design §Control plane and activation and §CAP-2 tenant-admin REST contract; ADR-011. Normative REST authority is `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`; the TDD is explanatory and does not override it.

### Evidence

API authorization, tenant-isolation, lifecycle-transition, secret-reference, finite-catalog, activation-gate, and concurrent-source-limit tests; telemetry scan for lifecycle success and failure paths.

### Demonstrates Reference Scenarios

RS-001. Decision-output-facing backend capability; portal presentation is implemented by CAP-5.

### NFRs
- NFR-OPS-001 safe aggregate lifecycle/test terminal outcomes.

### Constraints
- Public records carry authenticated owning tenant identity and contain non-content metadata and secret references only.
- Shared environments require Vault resolution; `env://` is local Compose only.

### Assumptions
- Customer-specific network and governance evidence is supplied before the affected tenant activates.

### Contracts / Interfaces

Normative `Connection` / `ConnectionPage` shapes, `CreateConnectionRequest` / `ReplaceConnectionRequest`, `UpdateConnectionRequest`, `ActivateConnectionRequest`, `TestConnectionRequest` / `PauseConnectionRequest`, `RetireConnectionRequest`, tenant/method/path/body-scoped idempotency record (24-hour replay), and finite safe error envelope per TDD §CAP-2 tenant-admin REST contract and ADR-011; tenant-bound connection/profile, lifecycle/test/activation evidence, capability resolver, and additive public-schema migration/backfill. Normative authority is `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`; the TDD is explanatory.

### API Surface (normative — `/api/v1/data-sources`)

Gateway exposes the versioned tenant-admin REST contract: `POST /api/v1/data-sources`, `GET /api/v1/data-sources`, `GET /api/v1/data-sources/{connection_id}`, `PATCH /api/v1/data-sources/{connection_id}`, `POST /api/v1/data-sources/{connection_id}/test`, `POST /api/v1/data-sources/{connection_id}/activate`, `POST /api/v1/data-sources/{connection_id}/pause`, `POST /api/v1/data-sources/{connection_id}/replace`, `POST /api/v1/data-sources/{connection_id}/retire`. Every route requires valid JWT, `resolve_tenant_from_jwt`, and `require_tenant_admin` with no caller-supplied tenant ID; single-record lookup constrains `id` plus authenticated `tenant_id` (`404 CONNECTION_NOT_FOUND` otherwise). Mutations require `Idempotency-Key` (1–128 printable ASCII, tenant/method/path/body-digest scope, 24-hour safe replay); list uses only the allowlisted `q/provider/status/sort/order/page/page_size` contract with 20-per-page default and deterministic `id` tie-breaker.

### Data owned

Public tenant-bound connection metadata, secret reference, safe lifecycle/test evidence, and capability state.

### Events published

Safe connection lifecycle outcome events using declared finite values.

### Events consumed

Authenticated tenant context and approved activation-evidence state.

### Implementation Notes

Under the existing human authorization, the change SHALL amend the obsolete tenant-facing prohibition/non-default activation scenarios in `openspec/specs/tenant-integration-profile/spec.md` for these two providers via an OpenSpec delta, rather than treating that durable specification as a blocker. No new human authorization is introduced by this increment.

### Out of scope for this capability
- Arbitrary providers, plaintext credentials, shared-environment `env://` activation, and tenant-managed derived-data stores.

---

## CAP-3 — Durable Azure Blob Synchronization and Source Reconciliation

**Depends on:** CAP-2
**Owning service:** document service
**Satisfies:** FR-004, FR-005, FR-006, FR-007, FR-008, FR-013; NFR-RELY-001
**Governed by:** ADR-001, ADR-012
**Domain:** `azure-blob-source-sync`

### Summary

Add a contained Azure Blob runtime and durable Celery/RabbitMQ synchronization workflow. It sends provider-normalized documents through the existing ingestion boundary, maintains tenant-schema lease/run/object-version state, and reconciles changed or missing source objects without retaining Blob originals.

### Requirements (ADDED)

- **Requirement: Common durable Blob ingestion**
  - The system SHALL execute manual, 15-minute scheduled, retry, and one missed-schedule catch-up Azure Blob synchronization through one tenant-bound durable job that submits each eligible object as a `NormalizedDocument` to `DocumentIngestionService`.
  - Scenario: New object is synchronized
    - **WHEN** an active tenant Blob connection synchronizes a newly discovered supported object
    - **THEN** its bytes SHALL enter the existing common ingestion pipeline and derived document outputs SHALL be stored in the platform tenant schema without Azure-specific OCR, NER, chunking, extraction, or retrieval branches.
- **Requirement: Idempotent source version reconciliation and temporary retention**
  - The system SHALL use a persistent source object/version ledger, run record, and durable lease to skip unchanged objects, atomically replace a changed object's prior derived outputs, and hide derived records for confirmed-missing objects.
  - Scenario: Retry or unchanged object
    - **WHEN** a synchronization retries or observes an unchanged source version
    - **THEN** it SHALL not create duplicate documents, provenance, spans, chunks, embeddings, or extraction outputs.
  - Scenario: Deleted source object
    - **WHEN** a previously synchronized source object is confirmed missing
    - **THEN** its derived records SHALL be excluded from retrieval.
- **Requirement: Source-only original retention**
  - The system SHALL retain Blob bytes only in temporary working storage and SHALL delete them after every terminal success, failure, or cancellation outcome.
  - Scenario: Processing reaches a terminal outcome
    - **WHEN** an acquired Blob object finishes, fails, or is cancelled
    - **THEN** no durable original Blob copy SHALL remain in MinIO while platform-held provenance, state, and derived outputs follow the applicable outcome.

### Requirement Coverage

Requirement §Functional Requirements FR-004–FR-008 and FR-013; RS-002 and RS-005; Technical Design §Azure Blob synchronization.

### Evidence

Worker/scheduler integration tests for manual, scheduled, catch-up, retry, lease overlap, unchanged, changed, missing, temporary-cleanup, tenant-isolation, and retrieval-exclusion paths; executable common-ingestion contract test.

### Demonstrates Reference Scenarios

RS-002, RS-005. Backend decision/output capability; safe sync status is presented by CAP-5.

### NFRs
- NFR-RELY-001 no duplicate derived records.
- NFR-OPS-001 declared safe sync outcome telemetry.

### Constraints
- Azure SDK knowledge is contained in the provider runtime.
- Blob originals never become durable MinIO objects.

### Assumptions
- Approved Azure test resources and prerequisite evidence are available for integration activation tests.

### Contracts / Interfaces

Azure Blob provider runtime; `NormalizedDocument`; `DocumentIngestionService`; Celery/RabbitMQ sync job and scheduler; tenant-schema source run/object-version ledger; retrieval source-state filter.

### API Surface (indicative)

Tenant-admin manual synchronization trigger and safe source/sync status read surface.

### Data owned

Tenant-schema sync runs, leases, source object/version provenance, document linkage, and safe terminal state.

### Events published

Tenant-bound source-sync work and safe terminal outcome events.

### Events consumed

Active Azure Blob capability and durable schedule/catch-up trigger.

### Implementation Notes

Replace only the scheduled external-source dispatch path with durable work; preserve existing platform-upload authorization and normalized ingestion semantics. Touched OCR failure telemetry must use safe structured error classes rather than traceback or interpolated exception payloads.

### Out of scope for this capability
- S3, SharePoint, arbitrary source providers, persistent external originals, and external vector stores.

---

## CAP-4 — Contract-Governed External PostgreSQL Query Path

**Depends on:** CAP-2
**Owning service:** chat API and shared retrieval
**Satisfies:** FR-010, FR-011, FR-012, FR-013; SEC-004; NFR-RELY-002
**Governed by:** ADR-001, ADR-013
**Domain:** `external-postgresql-chat`

### Summary

Implement a tenant-scoped external query capability, distinct from existing platform SQL chat. It owns canonical schema-contract lifecycle/indexing, pre-query live-schema fingerprint validation, AST-restricted read-only execution, and safe chat capability selection without persisting tenant database rows.

### Requirements (ADDED)

- **Requirement: Versioned tenant-isolated schema contracts**
  - The system SHALL accept only valid published-version JSON schema contracts that declare approved relations, columns, and explicit join graph/keys; it SHALL preserve canonical versions and create a tenant-isolated schema index used for context only.
  - Scenario: Valid contract is published
    - **WHEN** a tenant administrator submits a valid contract for the authenticated tenant's active PostgreSQL connection
    - **THEN** the canonical version and safe validation state SHALL be retained, its tenant-isolated index representation SHALL be created, and no contract or index entry SHALL be visible to another tenant.
- **Requirement: Drift-gated external read-only query**
  - The system SHALL introspect live contract-relevant metadata and compare a deterministic canonical fingerprint before every external query; it SHALL block execution on mismatch, unavailable metadata, or fingerprint failure until a replacement contract is accepted.
  - Scenario: Drift blocks execution
    - **WHEN** the live metadata fingerprint differs from the active accepted contract fingerprint
    - **THEN** no external SQL SHALL execute and the caller SHALL receive a safe drift-blocked outcome.
- **Requirement: Contract-authorized SQL execution**
  - The system SHALL execute only one AST-validated, parameterized SELECT through a tenant-scoped read-only credential, enforcing contract-authorized relations, columns, and join paths, server row cap, and ten-second timeout.
  - Scenario: Approved join and aggregation executes
    - **WHEN** an authorized chat request produces a single contract-approved SELECT using an approved join and permitted aggregation
    - **THEN** it SHALL execute within the row cap and timeout and return response-only results without persisting tenant database rows.
  - Scenario: Disallowed statement is rejected safely
    - **WHEN** a proposed external statement contains a write, DDL, multiple statement, subquery, CTE, UNION, window function, or unapproved reference
    - **THEN** it SHALL not reach the tenant database and telemetry SHALL record only a finite rejection reason and correlation metadata.

### Requirement Coverage

Requirement §Functional Requirements FR-010–FR-013; RS-003 and RS-004; Technical Design §External PostgreSQL chat and drift enforcement.

### Evidence

Contract schema/tenant-index tests; fingerprint drift-negative integration test proving no execution; AST grammar/allowlist/parameterization/row-cap/timeout tests; cross-tenant connector and no-row-retention tests; telemetry scan including rejected-SQL paths.

### Demonstrates Reference Scenarios

RS-003, RS-004. Backend decision/output capability; contract administration presentation is implemented by CAP-5.

### NFRs
- NFR-RELY-002 drift check precedes every direct query.
- NFR-PERF-001 dev fixture: ten sequential direct queries meet p95 ≤10 seconds with zero errors.

### Constraints
- The LLM has no database credential or direct connector access.
- The schema index cannot authorize access; the canonical contract and live fingerprint do.

### Assumptions
- The active connection has a TLS-validated, least-privilege read-only role and approved connectivity evidence.

### Contracts / Interfaces

Canonical schema contract/version/fingerprint; tenant-isolated schema index; scoped external connector; AST validator; external-query capability resolver; chat API/tool integration.

### API Surface (indicative)

Tenant-admin contract upload/validate/publish/history operations and authenticated chat source/capability selection; exact routes/payloads remain OpenSpec-defined.

### Data owned

Public tenant-bound canonical contracts, safe validation/fingerprint state, and tenant-isolated platform schema-index representations; external result rows are not retained.

### Events published

Safe contract, drift-check, query-execution, and rejection outcomes using declared finite labels.

### Events consumed

Active PostgreSQL connection capability, authenticated tenant context, and accepted published contract.

### Implementation Notes

The OpenSpec delta SHALL amend `openspec/specs/chat-api/spec.md`'s rejected-SQL logging scenario to record a finite safe reason class rather than raw SQL. The existing platform tenant-schema SQL path remains intact and separate.

### Out of scope for this capability
- Database writes/DDL, row ingestion, direct LLM database access, field-level visibility, arbitrary SQL grammar, and replacing platform chat SQL.

---

## CAP-5 — Tenant Data Source Administration Portal

**Depends on:** CAP-2, CAP-3, CAP-4
**Owning service:** portal
**Satisfies:** FR-001, FR-002, FR-003, FR-005, FR-009, FR-011, FR-012, FR-013
**Governed by:** ADR-011, ADR-012, ADR-013
**Domain:** `tenant-data-source-portal`

### Summary

Add the tenant-admin portal navigation and three inventory-defined data-source administration screens using existing authenticated shell and design tokens. The portal consumes safe backend contracts only and makes lifecycle, sync, contract, and drift states actionable without displaying prohibited payloads.

### Requirements (ADDED)

- **Requirement: Data source collection and navigation**
  - The portal SHALL provide a tenant-admin-only `/settings/data-sources` route with server-backed, URL-backed search, provider/status filters, last-activity sort, and numbered pagination at 20 items per page.
  - Scenario: Administrator filters data sources
    - **WHEN** a tenant administrator changes the provider or status filter
    - **THEN** the collection SHALL reset to page 1, retain query state in the URL, and show loading, empty, filtered-empty, or safe error state as applicable.
- **Requirement: Safe connection lifecycle interface**
  - The portal SHALL provide a connection detail route that presents provider-specific non-sensitive configuration, secret-reference selection, safe test/activation state, schedule/sync aggregate status, and confirmed pause, replacement, and retirement actions.
  - Scenario: Activation is blocked safely
    - **WHEN** the backend reports unmet activation prerequisites
    - **THEN** the lifecycle action SHALL be unavailable with a safe blocking notice and no secret, connection string, provider error, or remote content displayed.
- **Requirement: Schema-contract administration interface**
  - The portal SHALL provide contract upload, validation, publish, safe drift state, and URL-backed paginated contract-history management for PostgreSQL connections.
  - Scenario: Invalid contract is recoverable
    - **WHEN** a tenant administrator uploads invalid JSON or a semantically invalid contract
    - **THEN** the screen SHALL present linked field-level safe validation errors and preserve a recoverable form state without showing database rows or SQL text.

### Requirement Coverage

Requirement §UI/UX and Accessibility Requirements and FR-001–FR-003, FR-005, FR-009, FR-011–FR-013; UI Inventory SCR-1–SCR-3.

### Evidence

Portal route/authz, URL-state, collection control, responsive navigation, keyboard/focus, lifecycle confirmation, safe-display, contract-form, and light/dark regression tests using capability-specific fixtures.

### Demonstrates Reference Scenarios

RS-001, RS-003; SCR-1 (CMP-1, CMP-2, CMP-3, CMP-4, CMP-5), SCR-2 (CMP-1, CMP-3, CMP-6, CMP-7, CMP-8, CMP-9), SCR-3 (CMP-1, CMP-3, CMP-5, CMP-8, CMP-10). No Figma node references are supplied by the inventory.

### NFRs
- Responsive administration controls remain operable without horizontal loss.
- Visible keyboard focus, semantic labels, accessible status text, and reduced-motion support follow the UI contract.

### Constraints
- Use the existing authenticated app shell, portal tokens, typography, light/dark values, and Clean structural foundation.
- Never render secrets, connection strings, provider errors, SQL, prompts, answers, remote document content, or database rows.

### Assumptions
- CAP-2, CAP-3, and CAP-4 expose tenant-scoped safe contracts required by the screens.

### Contracts / Interfaces

Tenant-admin data-source and schema-contract APIs; existing portal auth/navigation; URL search parameters; safe status/outcome vocabulary.

### API Surface (indicative)

Portal routes `/settings/data-sources`, `/settings/data-sources/[connectionId]`, and `/settings/data-sources/[connectionId]/schema-contracts`.

### Data owned

No authoritative backend records; client URL state and transient form state only.

### Events published

User-initiated lifecycle, manual sync, and contract actions through authenticated API calls.

### Events consumed

Safe connection, sync, activation, contract, and drift status from CAP-2 through CAP-4.

### Implementation Notes

Add the navigation entry without replacing current document upload routes. Use the inventory and `ui-contract.md` as visual authorities rather than duplicating their design prose in OpenSpec artifacts.

### Out of scope for this capability
- Redesign of existing upload/chat UI, new accessibility/browser/localisation promises beyond the UI contract, and rendering direct query rows or SQL.

---

## CAP-6 — Local Compose Delivery, Migration, and Operational Evidence

**Depends on:** CAP-2, CAP-3, CAP-4, CAP-5
**Owning service:** platform deployment and shared observability
**Satisfies:** NFR-OPS-001, NFR-AVAIL-001, NFR-DR-001; Delivery and Deployment Requirements
**Governed by:** ADR-014
**Domain:** `local-compose-data-source-delivery`

### Summary

Make the integrated feature locally deployable in the approved single `dev` Docker Compose environment, with additive migration sequencing, service/worker readiness, safe observability, and documented compatible rollback/roll-forward verification.

### Requirements (ADDED)

- **Requirement: Compatible local rolling delivery**
  - The system SHALL deploy changed services and workers sequentially in local Docker Compose only after compatible additive migrations and readiness checks, retaining the prior compatible component until its replacement is healthy.
  - Scenario: Local rolling deployment succeeds
    - **WHEN** the approved dev deployment is performed
    - **THEN** migrations SHALL complete before dependent services/workers are replaced and each replacement SHALL report ready before the next replacement starts.
- **Requirement: Safe operational verification and recovery**
  - The system SHALL provide local health/readiness and declared safe aggregate telemetry for connection, sync, drift-block, and external-query terminal outcomes, and SHALL document a compatible roll-back or roll-forward recovery path.
  - Scenario: Local recovery is exercised
    - **WHEN** a failed local deployment is restored using the documented compatible rollback or corrective roll-forward procedure
    - **THEN** the Compose stack SHALL return to a runnable, health-checked state within 30 minutes without assuming destructive database rollback.

### Requirement Coverage

Requirement §Non-Functional Requirements NFR-AVAIL-001, NFR-DR-001, NFR-OPS-001 and §Delivery, Release and Deployment Requirements; Technical Design §Rollout Plan.

### Evidence

Compose build/up, migration-order, service/worker health/readiness, telemetry scanner, declared-metric-label, and timed local recovery evidence; a local direct-query fixture performance check.

### Demonstrates Reference Scenarios

Not applicable: this deployment capability has no requirement reference scenario or UI screen; it verifies the operating environment for CAP-2 through CAP-5.

### NFRs
- NFR-AVAIL-001 dev-only health/readiness verification.
- NFR-DR-001 compatible local recovery within 30 minutes.
- NFR-OPS-001 safe finite operational telemetry.

### Constraints
- Environment is local `dev` Docker Compose with loopback entry point only.
- No staging, production, cloud secret-manager, HA, remote DNS, or TLS-termination claim is introduced.

### Assumptions
- Required local non-secret environment values are supplied through ignored developer environment files.

### Contracts / Interfaces

Docker Compose topology, additive migration ordering, service/worker health/readiness endpoints, observability metric declarations, and local recovery documentation.

### API Surface (indicative)

Health/readiness surfaces where supported; no new public deployment API.

### Data owned

No product data beyond additive migration state and local operational configuration.

### Events published

Safe deployment/readiness and terminal operational outcomes.

### Events consumed

Migration completion and dependent service/worker health signals.

### Implementation Notes

The capability must scan logs, spans, metric labels, and audit payloads for prohibited sensitive classes and preserve the project telemetry invariant. Production target selection remains a future approved design.

### Out of scope for this capability
- Staging/production deployment, Kubernetes, production SLOs/RPO/RTO, traffic splitting, and destructive rollback.

---

## Cross-Cutting Concerns

- Every OpenSpec change SHALL include proposal, design (including a container/boundary view), delta specification, tasks, and executable acceptance evidence; reconcile the two explicitly authorized obsolete durable-spec rules through deltas.
- Server-authenticated tenant capability resolution is authoritative for all API, worker, connector, contract, and index access. Caller-provided tenant or connection identifiers are never authority.
- All credentials are secret references; secret values, connection strings, provider errors, tenant content, SQL, prompts, answers, external rows, and raw database/model exceptions are prohibited from logs, metrics, traces, audits, and UI.
- Metrics use declared families and finite label values only. Terminal outcomes record structured correlation metadata and finite outcome/reason classes.
- Additive public control-plane and tenant-schema migrations must be backward compatible, backfill applicable defaults, and have rerunnable reconciliation. Platform upload, retrieval, and platform SQL chat remain compatible.
- Customer Azure resources, network allowlisting/private connectivity, least-privilege read-only role, tenant governance approvals, and approved test environments are activation prerequisites, not assumptions the implementation may bypass.

## Dependency Order (Suggested Implementation Sequence)

Wave 1 (no prerequisites): CAP-2
Wave 2 (depends on Wave 1): CAP-3, CAP-4
Wave 3 (depends on Wave 2): CAP-5
Wave 4 (depends on Wave 3): CAP-6

## Summary Table

| ID | Capability | Depends on | Service | FRs |
|---|---|---|---|---|
| CAP-2 | Tenant-Scoped Connection Control Plane | — | gateway and shared integration profile | FR-001, FR-002, FR-003, FR-009, FR-013 |
| CAP-3 | Durable Azure Blob Synchronization and Source Reconciliation | CAP-2 | document service | FR-004, FR-005, FR-006, FR-007, FR-008, FR-013 |
| CAP-4 | Contract-Governed External PostgreSQL Query Path | CAP-2 | chat API and shared retrieval | FR-010, FR-011, FR-012, FR-013 |
| CAP-5 | Tenant Data Source Administration Portal | CAP-2, CAP-3, CAP-4 | portal | FR-001, FR-002, FR-003, FR-005, FR-009, FR-011, FR-012, FR-013 |
| CAP-6 | Local Compose Delivery, Migration, and Operational Evidence | CAP-2, CAP-3, CAP-4, CAP-5 | platform deployment and shared observability | NFR-OPS-001, NFR-AVAIL-001, NFR-DR-001 |
