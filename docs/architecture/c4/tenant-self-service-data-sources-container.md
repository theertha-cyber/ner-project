# C4 Container View — Tenant Self-Service Data Sources

## Scope and Authority

This view describes the approved Tenant Self-Service Data Sources feature. It implements the boundaries in ADR-001 and ADR-011 through ADR-014 and the technical design at `docs/design/tenant-self-service-data-sources.md`. It is a design view, not an implementation claim.

## Containers and External Systems

```text
Tenant administrator / authorized chat user
  | authenticated HTTPS
  v
Portal (Next.js) ------------------------> Gateway (FastAPI control plane)
  safe data-source UI                         JWT tenant/admin authorization
  |                                           finite lifecycle API
  |                                           public control-plane records
  |                                           |
  |                                           +--> Vault / local ignored env://
  |                                           |    tenant-scoped credentials only
  |                                           |
  |                                           +--> PostgreSQL public schema
  |                                                connection metadata, references,
  |                                                safe lifecycle evidence/contracts
  |
  +---------------------------------------> Chat API
                                               authenticated capability selection
                                               |                 |
                                               |                 +--> Azure PostgreSQL
                                               |                      TLS; read-only role;
                                               |                      live metadata/query only
                                               v
                                           PostgreSQL tenant schema / pgvector
                                           platform derived data and schema index

Gateway / scheduler --> RabbitMQ --> Source-sync worker --> Azure Blob Storage
                                  tenant-bound job         TLS, scoped credential
                                                    |
                                                    v
                                             Document ingestion service
                                             NormalizedDocument boundary
                                                    |
                                                    v
                                           PostgreSQL tenant schema / pgvector
                                           derived data only; no durable Blob original
```

## Boundary Rules

| Boundary | Permitted flow | Prohibited flow / enforcement |
|---|---|---|
| User to Portal/Gateway/Chat | JWT-authenticated requests; gateway derives tenant and requires tenant admin for lifecycle operations. | Caller-supplied tenant or connection identity is never authority. |
| Portal to Gateway | Safe request fields and safe response/status vocabulary. | Secrets, secret references, endpoints, diagnostics, tenant content, SQL, prompts, answers, and database rows are not rendered. |
| Gateway to control plane | Tenant-bound non-content records in `public`; secret references only. | Plaintext credentials, connection strings, tenant content, derived data, and schema-index embeddings are excluded by ADR-001. |
| Credential resolution | Local ignored `env://` in Compose; Vault required for shared environments. | Credentials are neither persisted nor logged; an unresolved reference blocks activation. |
| Source-sync worker to Azure Blob | Contained provider SDK, TLS, tenant-bound scoped credential; opaque source/version identity. | Provider logic does not enter OCR, NER, chunking, extraction, retrieval, or unrelated tenant credentials. |
| Worker to ingestion | `NormalizedDocument` submitted to existing `DocumentIngestionService`. | No Azure-specific downstream processing branch; original bytes are temporary and deleted at terminal outcome. |
| Chat API to Azure PostgreSQL | Live metadata fingerprint and one validated parameterized read-only SELECT through a tenant-scoped read-only role, TLS-validated. | No LLM credential/direct access; no writes/DDL/unapproved grammar; no external row persistence. |
| Telemetry boundary | Structured finite outcome/reason classes and correlation identifiers. | SQL, identifiers derived from SQL, prompts, answers, rows, credentials, endpoints, provider payloads, and raw exceptions are prohibited. |

## Data Ownership and Trust Zones

- **Platform control plane:** `public` contains tenant-bound non-content connection lifecycle, secret references, canonical schema contracts, and safe evidence.
- **Platform tenant data plane:** each tenant schema and pgvector index contain platform-held derived document data, provenance, sync ledger/state, and tenant-isolated schema-index representations.
- **Tenant Azure trust zone:** Azure Blob originals remain tenant-held; Azure PostgreSQL rows remain tenant-held and response-only.
- **External activation gate:** Azure connections remain inactive until TLS, least-privilege credentials, a passing safe connection test, and the required customer network/governance evidence are present.

## References

- `docs/adr/001-tenant-data-isolation.md`
- `docs/adr/011-tenant-scoped-azure-connection-control-plane.md`
- `docs/adr/012-durable-azure-blob-source-synchronization.md`
- `docs/adr/013-contract-governed-external-postgresql-chat.md`
- `docs/adr/014-local-compose-deployment-topology.md`
