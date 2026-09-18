## Context

Platform chat SQL targets platform tenant schemas only (`src/chat_api/services/sql_generator.py`); no external connector, schema-contract artifact, or schema index exists. CAP-2 supplies the tenant-scoped active PostgreSQL connection and activation evidence; this change adds the contract-governed query path on top of it. ADR-013 (contract-governed external PostgreSQL chat) and ADR-001 (tenant isolation, public control-plane records) are in force. Live Azure verification is deferred per `run.provisioning`; tests use fixtures/fakes against the local test database.

## Goals / Non-Goals

**Goals:**

- Versioned canonical JSON contracts declaring approved relations, columns, and explicit join graph/keys, with tenant-isolated index representations for context only.
- Live schema fingerprint comparison before every external query; mismatch, unavailable metadata, or fingerprint failure blocks execution until a replacement contract is accepted.
- One AST-validated, parameterized SELECT per execution through a tenant-scoped read-only credential: contract-authorized relations/columns/join paths, server row cap, ten-second timeout, response-only rows, LLM never holds credentials.
- Tenant-admin contract upload/validate/publish/history bound to the authenticated tenant's active connection; chat source/capability selection resolved server-side.

**Non-Goals:**

- Writes/DDL, row ingestion or copying, direct LLM database access, field-level visibility, arbitrary SQL grammar (subqueries, CTEs, UNION, window functions stay rejected), replacing platform chat SQL, staging/production deployment.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation | Separate schema per tenant; public holds tenant-bound non-content control-plane records; server-side tenant resolution only | Canonical contracts live in `public` with owning tenant; index entries tenant-isolated; no caller-supplied tenant authority; no tenant rows in platform storage |
| ADR-013-contract-governed-external-postgresql-chat | Separate external-query capability; canonical contract + live fingerprint; AST-validated read-only SELECT; row cap; 10s timeout; TLS/private connectivity; LLM has no credentials | Exact enforcement surface of this change; STRIDE controls apply |
| ADR-011-tenant-scoped-azure-connection-control-plane | Tenant-admin lifecycle, activation evidence, one active connection per (tenant, provider) | External queries run only against the CAP-2 active PostgreSQL connection with current activation evidence |
| ADR-007-chatbot-architecture | Platform RAG/SQL architecture | Platform SQL path preserved intact and separate; not reused as external authority |

## Decisions

### Decision 1: Canonical contract JSON with explicit join graph; fingerprint over canonical form

**Choice:** Contracts are JSON documents `{version, relations: {name: {columns: [...], primary_key}}, joins: [{left, right, left_key, right_key}]}`. The accepted fingerprint is SHA-256 over a canonical serialization (sorted relations, sorted columns, sorted normalized joins). Live introspection fetches only contract-relevant metadata (relation/column names for declared relations plus join-key columns) and recomputes the same canonical fingerprint for comparison.

**Rationale:** Deterministic comparison without full-schema snapshots; join keys are part of the fingerprint so a dropped key blocks. Column-type changes that do not alter names/keys intentionally do not block (authorization is about relations/columns/paths, not types).

**Alternatives considered:**
- Full `information_schema` snapshot hash — ruled out because unrelated database changes (new tables, type tweaks) would block queries the contract still authorizes.
- Vector similarity over schema — ruled out by ADR-013/BR-004: retrieval is not deterministic authorization.

### Decision 2: sqlparse-based AST validator, separate from the platform whitelist

**Choice:** New `src/shared/external_postgres/validator.py` built on `sqlparse` (already a dependency): single statement only; first keyword must be SELECT (WITH rejected, so no CTEs); reject UNION/INTERSECT/EXCEPT, subqueries (parenthesized SELECT), window functions, non-SELECT keywords (INSERT/UPDATE/DELETE/DDL/SET/COPY/GRANT etc.); identifiers resolved against the canonical contract (relations, columns, join paths, aliases); allowlist of aggregates (COUNT/SUM/AVG/MIN/MAX), GROUP BY/HAVING/WHERE/ORDER BY/DISTINCT/aliases/basic date functions; every literal must be a parameter placeholder (parameterization enforced by construction — the executor binds values, never interpolates).

**Rationale:** Platform validator authorizes platform tables; external authorization must come from the tenant's canonical contract. sqlparse is already vendored and sufficient for a restricted grammar.

**Alternatives considered:**
- Reuse platform SQL validator unchanged — ruled out: it does not represent customer schema or external credentials (ADR-013).
- Full grammar engine (sqlglot) — ruled out: new dependency for a deliberately restricted grammar; validator must reject by default.

### Decision 3: Drift-gated connector with read-only transaction, row cap, timeout

**Choice:** `connector.py` executes only after `drift.check()` returns clean: `SET TRANSACTION READ ONLY`, `statement_timeout = 10000`, server-side `LIMIT min(requested, ROW_CAP=100)`, asyncpg/psycopg execution through the tenant-scoped credential resolved via CAP-2 secret references. Rows are returned to the caller only, never written to platform tables. Any drift state other than clean raises `DriftBlocked` before SQL parsing/execution; telemetry records finite outcome/reason classes only.

**Rationale:** Defense in depth: even a validator bug cannot write (read-only role + transaction), cannot exhaust (cap + timeout), cannot run stale (drift gate precedes every execution, NFR-RELY-002).

**Alternatives considered:**
- Application-side timeout only — ruled out: server `statement_timeout` survives client hangs.
- Client-side LIMIT append — ruled out: string rewriting is itself injection-prone; cap enforced by wrapping/clamping at execution.

### Decision 4: Tenant-isolated schema index for context only

**Choice:** Index entries (relation/column/JOIN key text + embeddings hook) stored per tenant (`tenant_<id>.external_pg_schema_index`), populated on contract publish, cleared/replaced on replacement. Retrieval uses it for schema context; authorization decisions read only the canonical contract + live fingerprint.

**Rationale:** ADR-013: index helps retrieve context but never authorizes access; tenant isolation keeps one tenant's schema vocabulary out of another's prompts.

**Alternatives considered:**
- Shared index table with tenant_id filter — ruled out: weaker isolation, leaks vocabulary through shared embeddings.
- No index (contract text in prompt) — ruled out: contracts can exceed prompt budget; indexed top-K keeps context bounded.

### Decision 5: Gateway contract-admin routes reuse CAP-2 auth and tenant binding

**Choice:** `POST /api/v1/data-sources/{id}/contracts` (upload+validate, returns version + validation state), `POST .../contracts/{version}/publish` (accept), `GET .../contracts` (paginated history). All require JWT + `resolve_tenant_from_jwt` + `require_tenant_admin`; connection lookup constrains `(id, tenant_id)`; contract rows carry owning tenant; only validated contracts of the active connection publish.

**Rationale:** Same trust model as CAP-2; no new auth primitive, no caller-supplied tenant.

## Risks / Trade-offs

- [Live metadata unavailable looks like drift] — Distinct `metadata_unavailable` reason class; blocked either way, but operators can tell downtime from schema change.
- [sqlparse gap admits a construct the validator misparses] — Validator rejects on unresolvable references; unknown constructs default to rejection, and the read-only role bounds residual risk.
- [Fixture-backed verification diverges from Azure] — Fixture implements the same `ExternalDatabase` seam (introspect/execute) the Azure connector will implement; live verification deferred explicitly, capability stays inactive without activation evidence.
- [Contract JSON too large for prompt] — Index top-K context; canonical contract never fully inlined.

## Migration Plan

Additive migration `042_external_pg_contracts.py`: `public.external_pg_contracts` (tenant-bound canonical versions + fingerprint + validation/publish state) and `tenant_template.external_pg_schema_index` (+ per-tenant fan-out, same pattern as 041). No backfill (empty by definition), no existing row changes. Rollback: drop new tables; platform SQL/chat paths untouched so prior behavior restores by removing routes/module.

## Open Questions

- Live Azure Database for PostgreSQL test instance approval (deferred per `run.provisioning`); no new ADR needed.
- No in-force ADR needs revisiting; ADR-013 STRIDE controls are implemented as written.
