# 013. Contract-Governed External PostgreSQL Chat

## Status
Accepted

## Context

FR-010 through FR-013 require direct read-only Azure PostgreSQL chat without copying tenant rows. Existing chat SQL targets only platform tenant schemas; it cannot safely be reused as external query authority. A tenant-uploaded canonical schema contract must authorize tables, columns, and join paths, and a live metadata fingerprint must block drift before every query. This creates an external boundary requiring an ADR and threat model.

## Decision

Introduce a separate tenant-bound external-query capability. It validates a versioned canonical JSON contract and explicit join graph, generates a tenant-isolated schema-index representation for context only, obtains live schema metadata and calculates a canonical deterministic fingerprint before every query, and blocks on any mismatch or check failure. A tenant-scoped, Vault-held, least-privilege read-only database role executes one AST-validated, parameterized SELECT with contract allowlists, a row cap, and a ten-second timeout. Connections permit private endpoints or TLS public endpoints only with customer-approved platform IP allowlisting and TLS certificate validation. The LLM never has database credentials or direct database access; result rows are not persisted.

### Threat model (STRIDE)

| Threat | Control |
|---|---|
| Spoofing | Authenticated tenant context and scoped database credentials. |
| Tampering | Canonical versioned contracts, live fingerprint comparison, AST validation, and read-only role. |
| Repudiation | Correlated, safe outcome/audit events without SQL or data payloads. |
| Information disclosure | Tenant-bound resolver, contract allowlists, TLS, row cap, no result retention, and telemetry redaction. |
| Denial of service | Query timeout, row cap, restricted grammar, and safe drift/failure block. |
| Elevation of privilege | No tenant ID from tool input, no write privileges, no direct LLM database access, and no unapproved joins. |

## Alternatives Considered

| Option | Why not chosen |
|---|---|
| Copy business rows into platform storage | Violates the direct-query/no-copy requirement. |
| Use vector similarity to authorize schema | Retrieval is not deterministic authorization. |
| Reuse platform SQL whitelist unchanged | It does not represent customer schema or external credentials. |
| Permit unrestricted read-only SQL | A SELECT can still expose unauthorized tenant data or cause resource exhaustion. |

## Consequences

This enables bounded external-data answers while retaining the existing RAG path. It adds contract validation/indexing, metadata access, safe drift UX, distinct SQL validation, connector tests, and customer-managed read-only/network prerequisites.

## Related
- Requirement(s): FR-010, FR-011, FR-012, FR-013; BR-002, BR-004; NFR-RELY-002, NFR-SECU-001
- Supersedes / Superseded by: Depends on `007-chatbot-architecture.md` for platform RAG; it does not replace the platform SQL path.

## Revision History

- 2026-09-10 (redo after wind-back): Re-saved unchanged; external PG chat decision and STRIDE controls remain valid. Re-saved so the Design-gate artifact postdates the 2026-09-10 wind-back.
