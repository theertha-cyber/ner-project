# ADR-016. Contract-Grounded External SQL Generation

- **Status:** accepted
- **Date:** 2026-09-13

## Context

ADR-013 built the guards for external PostgreSQL chat (contract, index, drift gate, AST validator, read-only executor) but left out how SQL is produced. For platform data, the SQL prompt embeds schema knowledge in code. For external data the schema belongs to the tenant, so it can't live in code. The tenant's published contract must supply it. Contracts carried names only, and names alone don't tell an LLM what values mean. The requirement also calls for a schema vector index, but the first delivery (a live demo) can't wait for retrieval.

## Decision

1. **Schema knowledge comes from the published contract, never from code.**
   - The external generation prompt is fixed, code-owned rules plus schema context rendered from the published version's `external_pg_schema_index` entries.
   - Contracts MAY carry per-relation `description` and `column_descriptions`.
   - Descriptions are context only. They SHALL NOT affect the fingerprint, authorization, or drift.
2. **Generated SQL is validated locally before any tenant-database contact.**
   - The LLM proposes `{sql, params}` with every value as a named placeholder.
   - The external AST validator checks the proposal first.
   - Retries are bounded, and their feedback is limited to finite reason classes and contract identifiers.
   - Only an accepted statement goes to the drift-gated executor, and it runs once.
   - The prompt's rules SHALL mirror the validator's grammar.
3. **The external capability is offered to the planner per turn.**
   - The `external_database` tool is offered only when server-side capability resolution says the authenticated tenant is executable.
   - Tenants without a connection get unchanged planner input.
4. **External evidence has its own channel.**
   - External results travel separately from platform SQL results through accumulation, prompt assembly, and citation assembly (see ADR-015).
5. **Whole-contract context until retrieval exists.**
   - All index entries go into the prompt, under a character budget that fails closed.
   - Embedding retrieval over the same entry text is a later, additive change. It SHALL remain context-only and SHALL NOT authorize (per ADR-013).
6. **No LLM tracing of external generation.**
   - The external generator's LLM client is not wrapped by prompt/output-capturing tracers.

## Consequences

- Tenants control answer quality through contract descriptions, with no platform code change per tenant.
- Rejected proposals cost LLM calls only. Drift checks and database connections happen once per answered question.
- The validator's grammar limits what can be answered: no subqueries, so no "who does NOT…" questions. Widening it requires a new ADR and coordinated prompt changes.
- Large contracts fail with `schema_context_too_large` until retrieval lands, which bounds the tenant schemas this delivery supports.
- Future platform-schema externalization (moving platform schema prose out of code) can reuse the same "rules in code, schema from a versioned artifact" pattern, but is not decided here.
