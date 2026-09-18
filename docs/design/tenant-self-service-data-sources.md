# Tenant Self-Service Data Sources — Technical Design

## Overview

This design adds tenant-admin self-service for a finite catalog of Azure Blob document sources and Azure Database for PostgreSQL direct structured-data chat. It extends existing seams without changing the upload path or copying tenant business rows, and records the approved control-plane, synchronization, external-query, security, and local deployment decisions.

## Background / Context

The requirements authority is `docs/requirement/tenant-self-service-data-sources.md` (FR-001 through FR-013). The archived tenant-pluggable-data-foundation change supplied normalized ingestion, integration-profile, retention, and provenance seams but deliberately deferred self-service Azure runtimes and direct external database chat. Existing ADRs 001 and 007 remain dependencies; ADR-001 is amended by this package to permit tenant-bound, non-content control-plane records in `public`. The feature container and trust-boundary view is `docs/architecture/c4/tenant-self-service-data-sources-container.md`.

## Codebase Discovery Findings

- `POST /api/v1/documents` authenticates through tenant request state and constructs a provider-neutral `NormalizedDocument` for `DocumentIngestionService.ingest()` (`src/document_service/api/v1/documents.py:64-112`; `src/document_service/ingestion/contract.py:41-108`; `src/document_service/ingestion/service.py:70-256`). Azure Blob must use this boundary rather than add Azure branches to OCR, NER, chunking, extraction, or retrieval.
- `source_only` retention has no current source-adapter reopen path (`src/document_service/services/ocr_worker.py:296-334`), and OCR dispatch is an in-process `asyncio.create_task` (`src/document_service/ingestion/dispatcher.py:18-26`). Celery submission exists for extraction (`src/extraction_service/api/v1/extraction.py:205-214`), providing the implementation precedent for durable sync work.
- The integration profile is already a `public` tenant-bound control-plane seam with typed configuration and secret references (`src/shared/integration_profile/store.py:21-95`; `config_schema.py:59-103`), but it is developer managed, only default adapters activate, and only `env://` resolves today (`service.py:161-175`; `secrets.py:50-80`). CAP-2 has no gateway route, tenant-facing request/response models, list implementation, or lifecycle error mapping (`src/gateway/main.py:77-84`; `tests/test_tenant_integration_profile.py:494-505`).
- Existing chat entry points are `/api/v1/chat` and `/api/v1/chat/stream` (`src/chat_api/api/v1/chat.py:177-265`). The current SQL generator targets platform tenant schemas with a ten-second read-only transaction (`src/chat_api/services/sql_generator.py:1107-1223`); it is not authority for an external tenant database.
- Retrieval filters only on chunk purpose and currently does not account for a deleted external source (`src/shared/retrieval/retriever.py:65-115`). The touched OCR failure paths print tracebacks/interpolate exception data (`src/document_service/services/ocr_worker.py:350-368,528-542`) and must be remediated under the telemetry invariant.

### Governance Findings

The baseline policy mandates ADRs for the integration boundaries and deployment topology; ADRs 011 through 014 record those decisions. The human has authorized this feature to supersede the conflicting tenant-facing-management/non-default-activation clauses in `openspec/specs/tenant-integration-profile/spec.md` only for the two approved Azure providers. The human also authorized remediation of `openspec/specs/chat-api/spec.md:152-159`: rejected SQL is never logged; only declared finite rejection reason/class and correlation metadata may be emitted. The normative CAP-2 HTTP contract belongs in `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`; this TDD explains but does not override it. The container/boundary view is now `docs/architecture/c4/tenant-self-service-data-sources-container.md`.

## Goals

- Meet FR-001–003 and FR-009 with tenant-admin-only, tenant-scoped connection lifecycle and safe activation.
- Meet FR-004–008 with a durable, idempotent Azure Blob sync path using common ingestion and no durable original Blob copy.
- Meet FR-010–013 with contract-authorized, direct, read-only Azure PostgreSQL chat and drift blocking.
- Preserve existing platform uploads, platform retrieval, and platform SQL chat.

## Non-Goals

- Arbitrary providers, external vector stores, tenant-managed derived-data stores, and a platform-wide rewrite.
- Database writes or DDL, external-row copying, direct LLM database access, unsupported SQL grammar, and field-level visibility controls.
- Staging or production deployment: these are explicitly deferred and must not be inferred from the local dev plan.

## Proposed Design

### Control plane and activation

Amend ADR-001 so `public` holds tenant-bound, non-content control-plane records: finite adapter selection, non-sensitive metadata, secret reference, lifecycle/test/activation evidence, and versioned canonical schema contracts. The authenticated server-side capability resolver supplies the tenant scope; neither portal input, chat/tool input, nor a queued payload can establish a different tenant or connection as authority. Each tenant may have at most one active Azure Blob document source and one active Azure PostgreSQL connection, while platform upload stays available.

Only tenant administrators can create, test, activate, pause, replace, or retire the two connection types. A record activates only after typed finite-catalog validation, a safe successful connection test, customer network approval evidence, relevant legal/retention/residency approval, and a resolvable credential reference. Local dev may resolve an ignored `.env` through `env://`; shared environments require a Vault resolver and remain ineligible until it exists.

Permitted connectivity is either a private endpoint or a TLS public endpoint with customer-approved platform egress IP allowlisting. Both require TLS certificate validation, Vault-held tenant-scoped credentials outside local dev, and least privilege; the PostgreSQL role has read-only database permissions. Safe evidence records outcome classes, not endpoint values, credentials, provider errors, or test payloads.

### CAP-2 tenant-admin REST contract

The gateway SHALL expose the following versioned routes. Every route requires a valid JWT, `resolve_tenant_from_jwt`, and `require_tenant_admin` (`src/gateway/dependencies.py:31-35,65-79`). There is no tenant ID in a path, query, or body. The service uses only the authenticated tenant ID for every lookup, write, idempotency entry, lifecycle constraint, and audit record. A single-record lookup constrains both `id` and authenticated `tenant_id`; absence, including another tenant's ID, returns `404 CONNECTION_NOT_FOUND` with no metadata.

| Method and exact path | Request | Success response |
|---|---|---|
| `POST /api/v1/data-sources` | `CreateConnectionRequest`; `Idempotency-Key` required | `201 Connection` |
| `GET /api/v1/data-sources` | Listed query parameters only | `200 ConnectionPage` |
| `GET /api/v1/data-sources/{connection_id}` | UUID path ID | `200 Connection` |
| `PATCH /api/v1/data-sources/{connection_id}` | `UpdateConnectionRequest`; `Idempotency-Key` required | `200 Connection` |
| `POST /api/v1/data-sources/{connection_id}/test` | `{}`; `Idempotency-Key` required | `200 Connection` |
| `POST /api/v1/data-sources/{connection_id}/activate` | `ActivateConnectionRequest`; `Idempotency-Key` required | `200 Connection` |
| `POST /api/v1/data-sources/{connection_id}/pause` | `{}`; `Idempotency-Key` required | `200 Connection` |
| `POST /api/v1/data-sources/{connection_id}/replace` | `CreateConnectionRequest`; `Idempotency-Key` required | `201 Connection` |
| `POST /api/v1/data-sources/{connection_id}/retire` | `RetireConnectionRequest`; `Idempotency-Key` required | `200 Connection` |

All request bodies are `application/json`; timestamps are RFC 3339 UTC strings and IDs are UUID strings. Unknown body/query fields are rejected. `Idempotency-Key` is 1–128 printable ASCII characters, scoped to authenticated tenant, method, path, and a canonical body digest. The server persists only the digest and replayable safe response for 24 hours, never secret values. Same scope/body returns the original status/body with `Idempotent-Replay: true`; same key with a different body returns `409 IDEMPOTENCY_KEY_REUSED`; missing/malformed key returns `400 IDEMPOTENCY_KEY_REQUIRED`. GET operations need no key.

#### Request JSON schemas (normative source: CAP-2 OpenSpec delta)

`CreateConnectionRequest` and `ReplaceConnectionRequest`:

```json
{
  "provider": "azure_blob | azure_postgresql",
  "configuration": { "provider allowlisted fields": "value" },
  "secret_references": { "provider allowlisted reference fields": "scheme://opaque-path" }
}
```

No other top-level fields are accepted. For `azure_blob`, `configuration` requires non-empty `account` and `container` strings and permits optional `prefix` string; `secret_references` requires non-empty `connection_string_ref`. For `azure_postgresql`, `configuration` requires non-empty `host`, `database`, and `username`; integer `port` in 1–65535; and `sslmode` exactly `verify-full`; `secret_references` requires non-empty `password_ref`. References use only the existing allowlisted `env`, `vault`, `aws-secretsmanager`, `azure-keyvault`, `gcp-secretmanager`, or `file` scheme grammar (`src/shared/integration_profile/config_schema.py:16-24,75-97`). Literal credentials, arbitrary configuration keys, missing required provider fields, and wrong types are invalid. Implementation must extend the typed schema rather than accept arbitrary objects.

`UpdateConnectionRequest` is `{ "configuration": { ... }, "secret_references": { ... } }`, with one or both fields required and each following its provider's closed schema. Omitted provider fields retain their current values; `null` is invalid. Updates are permitted only from `draft`, `paused`, or `error`; an accepted update clears test/activation evidence and makes the status `draft`.

`ActivateConnectionRequest` is `{ "activation_evidence": ["network_approved", "governance_approved"] }`. The set contains both values exactly once and no others. `network_approved` represents validated private connectivity or TLS-public/customer-egress-allowlist approval. `governance_approved` represents approval of an applicable legal/retention/residency obligation, or a recorded determination that none applies. Only these finite attestation classes and correlation metadata are stored.

`TestConnectionRequest` and `PauseConnectionRequest` are `{}`. `RetireConnectionRequest` is `{ "confirm": true }`; `false` or omission is `422 RETIRE_CONFIRMATION_REQUIRED`.

#### Response JSON schemas and list contract

Every successful connection response is this safe `Connection` shape:

```json
{
  "id": "uuid",
  "provider": "azure_blob | azure_postgresql",
  "status": "draft | validated | active | paused | error | retired",
  "configured_fields": ["account", "container"],
  "secret_reference_fields": ["connection_string_ref"],
  "last_test": {"outcome": "passed | failed | not_run", "reason_code": "none | validation_failed | secret_unavailable | connection_failed | tls_validation_failed | authorization_failed | prerequisite_missing", "tested_at": "RFC3339 timestamp | null"},
  "activation": {"outcome": "active | inactive | blocked", "reason_code": "none | test_required | test_failed | prerequisite_missing | active_provider_exists | secret_unavailable", "activated_at": "RFC3339 timestamp | null"},
  "schedule": {"enabled": true, "cadence_minutes": 15},
  "last_sync": {"outcome": "never_run | succeeded | failed | blocked", "completed_at": "RFC3339 timestamp | null"},
  "replaces_connection_id": "uuid | null",
  "replaced_by_connection_id": "uuid | null",
  "created_at": "RFC3339 timestamp",
  "updated_at": "RFC3339 timestamp"
}
```

For `azure_postgresql`, `schedule` is `{ "enabled": false, "cadence_minutes": null }` and `last_sync` is omitted. For Blob, schedule is enabled only while active. Configuration values, secret-reference values, endpoint details, connection strings, provider diagnostics, tenant content, SQL, prompts, and answers are never returned.

`GET /api/v1/data-sources` accepts only: `q` (1–100 characters, case-insensitive safe server-generated identifier search), `provider` (`azure_blob|azure_postgresql`), `status` (returned status enum), `sort` (`last_activity|created_at|provider|status`), `order` (`asc|desc`), `page` (integer >=1, default 1), and `page_size` (integer 1–100, default 20). Defaults are `last_activity`, `desc`, page 1, and 20 per page; ascending `id` is the deterministic tie-breaker. Dynamic sort fields/direction are allowlisted and values parameterized. Filters/search reset the portal to page 1; an out-of-range valid page is an empty list.

```json
{
  "items": ["Connection"],
  "page": 1,
  "page_size": 20,
  "total": 0,
  "total_pages": 0,
  "sort": "last_activity",
  "order": "desc"
}
```

All errors use exactly `{ "error": { "code": "FINITE_SAFE_CODE", "message": "safe actionable text", "request_id": "correlation-id" } }`. Codes are: `UNAUTHENTICATED` (401), `FORBIDDEN` (403), `CONNECTION_NOT_FOUND` (404), `IDEMPOTENCY_KEY_REQUIRED` (400), `IDEMPOTENCY_KEY_REUSED` (409), `INVALID_REQUEST` (422), `INVALID_LIFECYCLE_TRANSITION` (409), `TEST_REQUIRED` (409), `TEST_FAILED` (409), `ACTIVATION_PREREQUISITE_MISSING` (409), `ACTIVE_PROVIDER_EXISTS` (409), `RETIRED_CONNECTION` (409), `RETIRE_CONFIRMATION_REQUIRED` (422), `CONNECTION_TEST_UNAVAILABLE` (503), and `INTERNAL_ERROR` (500). Messages state a next safe action without sensitive values or raw exceptions.

#### Lifecycle and concurrency semantics

Create/replacement produces `draft`. Test is permitted from `draft`, `paused`, or `error`; a passing secure TLS-validated test produces `validated`; a failure/unavailability produces `error` with a safe finite result. Activation is permitted only from `validated`, or `paused` with still-current passed evidence, and requires resolvable secret reference plus both activation attestations. It atomically enforces one active connection per `(tenant_id, provider)` using a database constraint/transaction; `ACTIVE_PROVIDER_EXISTS` leaves the incumbent unchanged.

Pause is permitted only from `active` and disables Blob scheduling. Retirement is permitted only from `draft`, `validated`, `paused`, or `error`, is terminal, and preserves safe history; an active connection must be paused first. Replacement creates a linked successor draft without changing its predecessor. When the successor activates, one transaction retires its same-provider active predecessor then activates the successor. A failed replacement leaves the predecessor unchanged; retired connections cannot be revived.

### Azure Blob synchronization

A contained Azure Blob runtime owns Azure SDK calls, enumeration, opaque object/version identity, byte acquisition, and provider-error mapping. It emits `NormalizedDocument` with Azure provenance to `DocumentIngestionService.ingest()`. It has no access to OCR, NER, chunks, extraction, retrieval, or unrelated tenant credentials.

A Celery/RabbitMQ source-sync worker and scheduler execute the same tenant-bound idempotent use case for manual, scheduled, retry, and one missed-schedule catch-up run. The scheduler enqueues active sources every 15 minutes. A persistent source object/version ledger, run record, and durable lease prevent overlapping work and duplicate derived outputs. Unchanged objects are skipped; changed objects remove/replace their prior derived outputs atomically; objects confirmed missing are marked non-retrievable so retrieval excludes them. Bytes use temporary working storage only and are removed on every terminal success, failure, or cancellation path; platform PostgreSQL/pgvector retains only provenance, sync state, spans, chunks, embeddings, and extraction outputs.

### External PostgreSQL chat and drift enforcement

A separate external-query capability accepts tenant-admin-uploaded, published-version JSON schema contracts. Each canonical contract defines allowed relations, columns, and join graph/join keys; its tenant-isolated schema index helps retrieve context but never authorizes access. Before every query, the connector uses the scoped credential for live schema introspection, produces a canonical fingerprint over contract-relevant metadata, and compares it to the accepted fingerprint. A mismatch, unavailable metadata, or fingerprint failure blocks execution until a replacement contract is accepted.

The external SQL path is distinct from existing platform SQL. It accepts one AST-validated, parameterized SELECT only, with contract-approved tables, columns, joins, aggregates, GROUP BY, HAVING, WHERE, ORDER BY, DISTINCT, aliases, and basic date/time functions. It rejects writes, DDL, multiple statements, subqueries, CTEs, UNION, window functions, and unapproved references. A tenant-scoped read-only database role executes with a server row cap and the existing ten-second timeout. The LLM has no database credential or direct connection; rows exist only for the current response and are never retained as platform data.

### Security, telemetry, compatibility, and migration

All sensitive tenant content is confidential, TLS-protected in transit, and protected at rest under existing platform controls. Logs, traces, metrics, and audits record structured, finite outcome/error classes and correlation identifiers only; never content, SQL, prompts, answers, endpoints, credentials, or raw exceptions. Additive migrations create public control-plane artifacts and tenant-schema source/version records; they backfill default profiles and are backward compatible. Reconciliation is rerunnable. The OpenSpec change must correct the existing rejected-SQL logging requirement and touched OCR unsafe exception telemetry.

## Alternatives Considered

| Alternative | Why not chosen |
|---|---|
| Azure-specific downstream processing | Violates FR-004 and duplicates the common ingestion pipeline. |
| In-process scheduled work | Cannot survive web-process restart or support durable catch-up. |
| Copy tenant database rows into platform storage | Violates FR-010 and the direct-query/no-copy boundary. |
| Metadata-only or vector-based drift authorization | The confirmed decision is live introspection plus a canonical fingerprint before every query. |
| TLS-public endpoints without customer allowlisting | Does not meet the approved customer network control. |

## Data Model / API Changes

| Artifact | Placement | Purpose / invariant |
|---|---|---|
| Connection/profile extension | `public` control plane | Tenant binding, finite type, confidential write-only configuration/secret reference, lifecycle/test/activation evidence; no plaintext secrets or tenant content. |
| Idempotency record | `public` control plane | Tenant/method/path/key/body-digest/replay response with 24-hour expiry; never retains secret body values. |
| Source run and object/version ledger | Tenant schema | Lease, idempotency, source identity/version, document linkage, safe outcome, missing state. |
| Schema contract/version | `public` control plane | Canonical JSON, published version, canonical fingerprint, safe validation status. |
| Schema-index representation | Tenant-isolated platform index | Context retrieval only; never query authorization. |
| Capability/API surfaces | Portal and FastAPI/OpenSpec contracts | Tenant-admin lifecycle, status, sync trigger, contract lifecycle, external chat selection; contract defines exact routes/payloads. |

## Non-Functional Requirements

| Category | Target | Measured how | Source |
|---|---|---|---|
| Reliability (NFR-RELY-001) | Manual, scheduled, retry, unchanged-object, and catch-up paths create zero duplicate derived records. | Integration tests inspect document/provenance and derived stores. | stated |
| Reliability (NFR-RELY-002) | 100% of direct-query attempts perform a drift check before execution; every mismatch prevents execution. | Integration/negative tests assert no execution after mismatch. | stated |
| Security (NFR-SECU-001) | Zero prohibited payload classes in logs, metrics, traces, or audit payloads across success and failure paths. | Automated telemetry scan with seeded flows and negative leak tests. | mandated |
| Performance/capacity/cost (NFR-PERF-001) | Dev operating target: under a controlled single-tenant local workload of 10 sequential direct-query requests against an approved fixture, p95 end-to-end direct-query latency is at most 10 seconds and error rate is 0%; Blob sync has no unbounded request task and runs via the durable worker. This is not a production capacity or cost SLO. | Repeatable local performance test; worker execution inspection. | clarified human direction; limited by dev-only scope |
| Availability (NFR-AVAIL-001) | Dev environment availability target: no uptime SLO. Services expose health/readiness where supported and must report healthy after local deploy before handoff. Production uptime target is deferred. | Compose health/readiness verification. | clarified human direction |
| Recovery (NFR-DR-001) | Dev recovery target: rollback/roll-forward restores a locally runnable compatible stack and health checks within 30 minutes after a failed local deployment; no production RPO/RTO is claimed. | Timed local rollback/roll-forward exercise. | clarified human direction |
| Operations (NFR-OPS-001) | 100% of connection, sync, drift-block, and external-query terminal outcomes emit safe aggregate structured telemetry using declared finite labels. | Metric contract, telemetry scan, and dashboard/alert review. | stated |

## Testing Strategy

- Contract/unit: every CAP-2 route/method/status/schema; closed provider fields; safe error codes; tenant derivation; lifecycle transitions; retirement confirmation; idempotency replay/key-reuse; page/filter/sort bounds and deterministic tie-breaker.
- Integration: non-admin/cross-tenant route negatives; atomic same-provider activation race; safe secure-test failure; replacement predecessor safety; secret-reference and telemetry redaction.
- Unit: finite configuration, lifecycle/authz, tenant resolver, canonical fingerprint, SQL AST rules, redaction, and finite metric labels.
- Integration: secure connection tests; private/TLS-public allowlist activation evidence; manual/scheduled/catch-up idempotency; temporary-byte deletion; deleted-source hiding; changed-object replacement; tenant isolation; contract validation/indexing; drift block; read-only/timeout/row-cap enforcement.
- Compatibility: preserve platform upload API/authorization, platform retrieval, and existing platform chat SQL.
- Evidence: every FR and NFR receives executable OpenSpec acceptance evidence; Azure resources used for activation tests require customer approval.

## Rollout Plan

Use additive, backward-compatible migrations and backfill default profiles. In the single `dev` Docker Compose environment, deploy changed services/workers sequentially using the approved rolling strategy; each replacement waits for compatible migrations and readiness before the next. Keep capabilities inactive until a connection test and activation evidence pass, then enable Blob and PostgreSQL capabilities independently per tenant. If failure occurs, restore the prior compatible local image/configuration or roll forward with a compatible corrective migration; destructive database rollback is not assumed. See `docs/design/deployment-plan.md` and ADR-014.

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Cross-tenant connection/contract/index access | Authenticated server-side resolver, tenant-bound persistence, and negative isolation tests. |
| Schema drift or unavailable metadata | Live introspection and canonical fingerprint hard block before query. |
| Lost or duplicate synchronization | Celery/RabbitMQ jobs, durable lease/ledger, idempotency tests, reconciliation. |
| Sensitive telemetry exposure | Structured safe error mapping, declared metrics, telemetry scan, OCR remediation. |
| Azure prerequisite absent | Do not activate; retain evidence requirement and safe inactive state. |

## Open Questions

- Tenant-specific legal hold, retention, residency, or jurisdiction approval remains an activation prerequisite, determined per affected tenant.
- Detailed staging/production ladder, target, entry point, Vault deployment, production capacity/cost SLO, uptime SLO, and production RPO/RTO are explicitly deferred and require a later approved design/topology ADR; they are not defaults of this build.
- UX must define accessibility, browser/device, and localisation expectations before UI design.

## Document History

- 2026-09-09: Initial design package approved (control plane, Blob sync, external PG chat, dev-only Compose ladder, Clean existing-portal UI direction).
- 2026-09-10 (CAP-2 redo after wind-back): Finalized normative CAP-2 tenant-admin `/api/v1/data-sources` REST contract in this TDD — paths/methods, JSON schemas, tenant-admin auth (`resolve_tenant_from_jwt` + `require_tenant_admin`, no caller-supplied tenant ID), lifecycle actions test/activate/pause/replace/retire, tenant/method/path/body-scoped idempotency (24-hour replay), allowlisted pagination/filter/sort, and finite safe errors. Normative authority is `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`; this TDD is explanatory and does not override it. Retained Blob sync, external PG chat, NFRs, C4 reference `docs/architecture/c4/tenant-self-service-data-sources-container.md`, dev-only docker-compose ladder, Clean existing-portal override, and human authorization to supersede obsolete feature-specific specs. Re-saved so all Design-gate artifacts postdate the 2026-09-10 wind-back.
