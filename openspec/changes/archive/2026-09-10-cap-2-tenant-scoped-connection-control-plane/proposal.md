## Why

Tenant administrators cannot currently manage the approved Azure Blob and Azure PostgreSQL connections: integration profiles are developer-managed and only default adapters can activate. This blocks the approved self-service data-source capability while leaving platform uploads unchanged.

## What Changes

- Add a tenant-admin, tenant-scoped lifecycle for the finite Azure Blob Storage and Azure Database for PostgreSQL provider catalog.
- Persist only non-sensitive metadata, secret references, and finite safe lifecycle/test/activation evidence.
- Enforce server-authoritative tenant scope, tenant-admin authorization, activation prerequisites, and one active source of each approved type per tenant.
- Reconcile the authorized obsolete tenant-facing-management and non-default-activation rules in the durable integration-profile specification.

## Capabilities

### New Capabilities

- `tenant-data-source-control-plane`: Tenant-admin lifecycle, safe connection testing and activation for the two approved Azure provider types.

### Modified Capabilities

- `tenant-integration-profile`: Permit tenant-bound administration and non-default activation only for approved Azure Blob and Azure PostgreSQL providers under the new control-plane requirements.

## Impact

Affected areas include the gateway tenant-admin API, shared integration-profile lifecycle and capability resolver, public control-plane migrations, authorization and isolation tests, and safe structured lifecycle telemetry. The change preserves platform upload behavior and does not add plaintext credentials, arbitrary providers, or shared-environment `env://` activation.

## Open Questions

- Exact API routes and payload schemas are defined by this change's specification.
- Per-tenant customer network and governance evidence remains an activation prerequisite; an unmet prerequisite leaves the connection inactive.
