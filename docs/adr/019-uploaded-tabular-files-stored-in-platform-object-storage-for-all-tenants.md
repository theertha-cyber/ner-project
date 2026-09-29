# ADR-019. Uploaded Tabular Files Are Stored in Platform Object Storage for All Tenants (v1)

- **Status:** accepted
- **Date:** 2026-09-23

## Context

ADR-017 (proposed) introduces a tenant-owned PostgreSQL data plane so that `tenant_owned` tenants keep their data in their own infrastructure. A companion plan for tenant-owned blob storage was designed and then dropped on 2026-09-20, because of complexity and a conflict with retention rules. No tenant-owned object store exists.

Uploaded tabular files (ADR-018) need an object store for the original file and its Parquet query copy. Their metadata and contracts are read during chat capability resolution, which must use a platform session because a `tenant_owned` tenant's session has no control-plane tables.

## Decision

1. For v1, every tenant's uploaded tabular files, originals and Parquet copies alike, are stored in platform MinIO, whatever the tenant's residency mode. Keys are prefixed `tenants/{tenant_id}/tabular/{file_id}/v{version}/`.
2. Their metadata, review state and published contracts live in platform control-plane tables (`public.*`) and are accessed only through platform sessions. No tenant-store DDL is introduced for this feature.
3. This is an explicit, recorded exception to the residency intent of ADR-017 for this data class. It SHALL be disclosed to `tenant_owned` tenants in the portal and in tenant documentation.

## Consequences

- The feature works for every tenant immediately, with no residency-specific code paths.
- `tenant_owned` tenants' uploaded spreadsheet data resides on the platform. Tenants for whom that is unacceptable must not upload files until a tenant-owned object store exists.
- A future tenant-owned object storage design will need a new ADR superseding this one, plus a migration of existing objects and a change to where capability resolution reads contracts.
- Tenant isolation for this data rests on key prefixes, tenant-bound resolution and server-side key construction. No key is ever built from request or model input.
