## Why

Tenant PostgreSQL rows cannot be copied into platform storage (FR-010, BR-002), and the existing platform chat SQL path targets only platform tenant schemas, so authorized chat users have no read path over a tenant's own Azure Database for PostgreSQL. A canonical schema contract must authorize relations, columns, and join paths, with a live drift check before every query (FR-012, NFR-RELY-002).

## What Changes

- Add a tenant-scoped external-query capability, separate from the platform SQL path: versioned canonical JSON schema contracts with explicit join graph/join keys, tenant-isolated schema-index representations for context only, pre-query live-schema fingerprint validation with hard drift block, and AST-restricted read-only execution (one parameterized SELECT, contract allowlists, server row cap, ten-second timeout) through a tenant-scoped least-privilege read-only role.
- Add tenant-admin contract administration surfaces (upload/validate/publish/history) bound to the authenticated tenant's active PostgreSQL connection, and authenticated chat source/capability selection for the external path.
- Amend the obsolete `chat-api` rejected-SQL logging scenario so rejected statements record only a finite rejection reason class and correlation metadata, never SQL text.
- Verify with fixtures/fakes against the local test database; live Azure PostgreSQL verification stays deferred per `run.provisioning` (capability inactive until approved resources and activation evidence exist).

## Capabilities

### New Capabilities

- `external-postgresql-chat`: Versioned tenant-isolated schema contracts, tenant-isolated schema index (context only), live fingerprint drift gate, AST-validated read-only execution with row cap/timeout, scoped connector, capability resolver, and chat integration. Result rows are response-only and never persisted.

### Modified Capabilities

- `chat-api`: Rejected external statements record a finite safe reason class and correlation metadata rather than raw SQL; platform tenant-schema SQL path remains intact and separate.

## Impact

Affected areas: new `src/shared/external_postgres/` module (contract, fingerprint, index, AST validator, drift-gated connector, capability resolver), public control-plane migration for canonical contracts, tenant-isolated schema-index storage, gateway contract-admin routes, chat API external capability integration, declared finite metric families, and safe structured telemetry. No change to platform upload, Blob sync, platform retrieval, or platform SQL chat semantics; no writes/DDL, no row ingestion, no direct LLM database access, no arbitrary SQL grammar.

## Open Questions

- Live drift-check and direct-query verification needs an approved Azure Database for PostgreSQL test instance; deferred per `run.provisioning` (`skip`), so integration tests use fixtures/fakes and the capability stays inactive until activation evidence exists.
- Customer network/TLS/read-only-role prerequisites are CAP-2 activation evidence; a connection without them stays inactive and never queries.
