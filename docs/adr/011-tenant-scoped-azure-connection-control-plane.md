# 011. Tenant-Scoped Azure Connection Control Plane

## Status
Accepted

## Context

FR-001 through FR-003, FR-009, and FR-013 require tenant-admin self-service for a finite Azure Blob/Azure PostgreSQL catalog. Existing profiles are developer-managed, only default adapters activate, and `env://` is the only implemented resolver. ADR-001 requires tenant isolation. These Azure integrations are external boundaries, so baseline policy requires an ADR and threat model. Ralph blocked CAP-2 because the earlier approved package did not define an implementable tenant-admin REST contract.

## Decision

Extend the existing integration-profile control plane with tenant-bound lifecycle records in `public` for only Azure Blob and Azure PostgreSQL, consistent with the ADR-001 amendment. Store a secret reference and non-sensitive metadata only; local-only Compose may resolve ignored `.env` values through `env://`, while any shared environment requires Vault resolution before activation. Server-side authenticated tenant capability resolution, a passing safe connection test, customer network approval/allowlisting evidence, and applicable governance approval are required to activate one document source and one PostgreSQL connection per tenant.

Both private endpoints and TLS-protected public endpoints are permitted. A public endpoint is eligible only when the customer has approved platform egress IP allowlisting. Every connection uses TLS certificate validation and a Vault-held, tenant-scoped least-privilege credential; the Azure PostgreSQL credential is read-only.

The gateway exposes the versioned, tenant-scoped `/api/v1/data-sources` API defined normatively in `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md`; the TDD is explanatory. It provides explicit create/list/read/update and `test`, `activate`, `pause`, `replace`, and confirmed `retire` actions; no tenant ID supplied by a caller is authority. Each protected operation requires JWT-derived tenant resolution and tenant-admin authorization before a tenant-qualified lookup/write. State-changing requests use a tenant/method/path/body-scoped idempotency key with a 24-hour replay window. The API returns field names and finite safe outcome classes only, and uses bounded allowlisted list filtering, sorting, and pagination; configuration values, secret references, endpoints, connection strings, and provider diagnostics are confidential/write-only.

### Threat model (STRIDE)

| Threat | Control |
|---|---|
| Spoofing | Authenticated JWT tenant context; connection test authenticates only with scoped credential. |
| Tampering | Server-side lifecycle transitions, validated finite configuration, and audit-safe state transitions. |
| Repudiation | Structured, redacted lifecycle/test outcome records with correlation identifiers. |
| Information disclosure | Secret references only; TLS; no connection strings, provider errors, content, SQL, prompts, or answers in telemetry. |
| Denial of service | Bounded catalog, validation, retries, queueing, and safe failure states. |
| Elevation of privilege | Tenant-admin-only administration; server-side tenant binding; least-privilege scoped credentials and network allowlisting. |

## Alternatives Considered

| Option | Why not chosen |
|---|---|
| Developer-managed profiles | Cannot meet tenant self-service requirements. |
| Store credentials/configuration plaintext | Violates secret-management and confidential-data controls. |
| Arbitrary provider/connection-string input | Cannot be safely validated or supported as a finite catalog. |
| Generic status patch or client-managed transitions | Cannot enforce action-specific confirmation, activation evidence, idempotency, or atomic provider limits. |

## Consequences

This preserves existing profile seams and makes activation auditable, but requires migration/backfill, portal/API contract tests, Vault work before shared deployment, customer prerequisite evidence, and an atomic database-backed active-provider limit. Unmet prerequisites leave a connection inactive rather than weakening controls.

## Related
- Requirement(s): FR-001, FR-002, FR-003, FR-009, FR-013; SEC-001, SEC-002, SEC-005, SEC-006, SEC-007
- Supersedes / Superseded by: Depends on amended `001-tenant-data-isolation.md`; supersedes the tenant-facing prohibition and non-default activation restriction in `openspec/specs/tenant-integration-profile/spec.md` for these two approved providers.

## Revision History

- 2026-09-09: Accepted — tenant-scoped Azure connection control plane with safe boundary, atomic one-active-per-provider limit, and STRIDE controls.
- 2026-09-10 (CAP-2 redo after wind-back): Retained decision, STRIDE, idempotency (tenant/method/path/body-scoped key, 24-hour replay), safe boundary (field names and finite outcome classes only), and atomic `(tenant_id, provider)` limit. Confirmed CAP-2 REST contract reference: normative authority is `openspec/changes/cap-2-tenant-scoped-connection-control-plane/specs/tenant-data-source-control-plane/spec.md` (versioned `/api/v1/data-sources` routes, create/list/read/update plus test/activate/pause/replace/confirmed-retire, tenant-admin auth, allowlisted pagination/filter/sort, finite safe errors); this ADR and the TDD are explanatory. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
