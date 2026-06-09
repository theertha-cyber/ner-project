# ADR-001: Tenant Data Isolation via Separate Database Schemas

**Status**: Proposed

**Date**: 2026-06-04

## Context

The platform serves multiple tenants, each managing sensitive business documents and extracted data. Requirements mandate strict isolation across documents, annotations, extracted data, model artifacts, logs, and search/vector indexes. The data model includes 12 core entities that must never leak across tenant boundaries.

We evaluated three isolation strategies:

- **(a) Separate database per tenant**: Strongest isolation but highest operational cost — per-database backup/restore, connection management, and connection pool overhead.
- **(b) Separate schema per tenant within a single database**: Logical isolation within one PostgreSQL instance. Each tenant gets `tenant_<uuid>` schema containing all tables. Migration scripts apply uniformly.
- **(c) Shared tables with row-level security (RLS)**: All tenants share same tables, filtered by `tenant_id` column via RLS policies. Lowest operational overhead but highest risk of misconfiguration leading to data leakage.

## Decision

**Use separate PostgreSQL schemas per tenant** (strategy b).

Enforcement at multiple layers:

| Layer | Mechanism |
|---|---|
| API Gateway | Validates JWT `tenant_id`, injects `X-Tenant-ID` header |
| Database connection | `SET search_path TO tenant_<uuid>` at connection pool init |
| ORM layer | Shared `tenant_context` module injects schema scope into all queries |
| Object storage | Prefix-based isolation: `s3://ner-platform/tenant-<uuid>/documents/` and `s3://ner-platform/tenant-<uuid>/models/` |
| Model artifacts | Stored in tenant-prefixed object storage paths |

Database topology: a single PostgreSQL 16 instance with per-tenant schemas. The `public` schema holds only migration tracking (`alembic_version`). Connection pooling via PgBouncer.

## Consequences

### Positive
- Strong logical isolation without per-database operational overhead.
- Schema-level backup and restore per tenant.
- Single migration script set applies uniformly across all schemas.
- Single connection pool reduces resource usage vs. per-database approach.

### Negative
- Single PostgreSQL instance is a shared-fate point — instance outage affects all tenants.
- Schema count scales linearly with tenants; >500 tenants may require sharding.
- Cross-tenant reporting (System Admin) requires explicit cross-schema queries.

### Mitigations
- Connection pooling with PgBouncer for resource efficiency.
- Monitor schema count; plan sharding at >500 tenants.
- System Admin reporting uses a dedicated reporting schema with controlled cross-schema access.
- WAL streaming for 5-minute RPO; Helm rollback for 30-minute RTO.

## Compliance

- All service code MUST use `search_path` injection via the shared `tenant_context` module.
- No raw SQL or ORM query shall omit the tenant scope filter.
- Object storage paths MUST follow the `tenant-<uuid>/` prefix convention.
- Migration scripts MUST be applied to the `public` schema (tracking) and each tenant schema.
- Penetration tests MUST verify cross-tenant data isolation (zero data leakage).

## References

- Technical Design Document §4.3 (Tenant Isolation Design)
- Technical Design Document §4.4 (Technology Choices — PostgreSQL 16 + pgvector)
- Technical Design Document §3.2 (Data Model — Relationships)
