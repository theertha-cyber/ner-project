## Context

The existing public integration-profile seam stores tenant-bound non-secret configuration and secret references, but it is developer-managed and permits only platform-default adapters to execute. FR-001–003, FR-009, and FR-013 require a bounded tenant-admin lifecycle for Azure Blob and Azure PostgreSQL while retaining platform uploads and control-plane confidentiality.

## Goals / Non-Goals

**Goals:**

- Provide server-authoritative, tenant-admin-only lifecycle operations for the two approved Azure provider types.
- Store only tenant-bound non-content metadata, secret references, and finite safe evidence.
- Require typed validation, secret resolution, secure test, customer network evidence, and applicable governance approval before activation.
- Permit one active Azure Blob source and one active Azure PostgreSQL connection per tenant.

**Non-Goals:**

- Arbitrary providers, plaintext credentials, tenant-managed derived-data stores, or shared-environment `env://` activation.
- Changes to platform upload authorization or downstream ingestion behavior.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant schemas isolate content; public holds tenant-bound non-content control-plane records. | Authenticated server-side scope constrains every public control-plane operation. |
| ADR-011 | Azure control plane permits only finite Azure Blob/PostgreSQL lifecycle under activation evidence. | References only, TLS/least privilege, safe evidence, and two independent per-tenant limits are mandatory. |

## Decisions

### Decision 1: Extend the existing profile seam with a bounded lifecycle

**Choice:** Add finite Azure Blob and Azure PostgreSQL connection records/lifecycle to the public tenant-bound control plane, with server-side authenticated tenant capability resolution and tenant-admin authorization.

**Rationale:** This preserves the established typed profile and tenant-isolation seam while implementing ADR-011's approved exception to the former tenant-facing prohibition.

**Alternatives considered:**
- A separate unscoped connector store — ruled out because it duplicates the control plane and weakens tenant isolation.
- Arbitrary connection-string submission — ruled out because it cannot provide the finite typed catalog or secret protection.

### Decision 2: Gate activation on finite safe evidence

**Choice:** Lifecycle transitions retain finite outcome/reason classes and correlation metadata only. Activation requires typed configuration validity, a resolvable secret reference, successful secure test, customer network evidence, and applicable governance approval.

**Rationale:** The gate enforces the approved external-boundary threat controls without exposing credentials, endpoints, provider errors, or tenant content.

**Alternatives considered:**
- Activation following configuration validation only — ruled out because it bypasses connectivity and governance prerequisites.
- Persisting diagnostic/provider payloads — ruled out by tenant confidentiality and telemetry controls.

### Decision 3: Enforce independent active-type limits transactionally

**Choice:** The control plane permits at most one active connection per tenant for each approved provider class, enforced during lifecycle transition under the tenant scope.

**Rationale:** It permits the approved simultaneous document and PostgreSQL capabilities without allowing duplicate active sources of either class.

**Alternatives considered:**
- One active connection total — ruled out because FR-009 permits both paths concurrently.
- Limits enforced by portal state — ruled out because callers are not authority.

## Risks / Trade-offs

- [Customer network or governance evidence is unavailable] → retain the connection inactive with a finite safe blocking class.
- [Shared environment lacks Vault resolution] → reject activation; `env://` remains local-Compose-only.
- [Concurrent activation requests race] → enforce the active-type constraint in the tenant-bound persistence transition.

## Migration Plan

1. Add backward-compatible public control-plane lifecycle/evidence fields and indexes, carrying the owning tenant.
2. Backfill existing platform-default profiles without changing their executable behavior.
3. Deploy server-authorized lifecycle APIs with inactive-by-default Azure connections.
4. Roll forward with compatible migrations; preserve existing profile and upload behavior rather than destructively rolling back public data.

## Open Questions

Exact API route and payload names are specified in the delta specification. Per-tenant Azure network and governance evidence is supplied at activation time and is not fabricated by the platform.
