## 1. Canonical contract lifecycle and migration

- [x] 1.1 Add additive alembic migration `042` for `public.external_pg_contracts` (tenant-bound canonical versions, fingerprint, validation/publish state) and `tenant_template.external_pg_schema_index` with per-tenant fan-out.
- [x] 1.2 Implement contract validation, canonical fingerprint, version publish/history, and tenant-isolated index write/replace/clear operations.

## 2. Drift gate, AST validator, and drift-gated connector

- [x] 2.1 Implement live metadata introspection over the `ExternalDatabase` seam and canonical fingerprint comparison with `clean/drift_mismatch/metadata_unavailable/fingerprint_failure` outcomes.
- [x] 2.2 Implement the sqlparse-based AST validator: single SELECT only, no subquery/CTE/UNION/window/write/DDL, contract allowlists for relations/columns/joins, permitted aggregates/clauses/functions, parameter-only literals, finite rejection reasons.
- [x] 2.3 Implement the drift-gated connector: drift check first, read-only transaction, server `statement_timeout`, row cap, tenant-scoped credential, response-only rows, finite outcome telemetry.

## 3. Capability resolver, gateway contract routes, and chat integration

- [x] 3.1 Implement server-side external capability resolution (active connection + accepted contract, authenticated tenant only).
- [x] 3.2 Add gateway contract-admin routes (upload/validate, publish, paginated history) reusing CAP-2 auth and tenant binding.
- [x] 3.3 Wire the external capability into the chat path as a separate selection from platform SQL; record finite rejection classes, never SQL text.

## 4. Verification & Evidence

- [x] 4.1 Add executable contract/index, drift-negative, validator/parameterization/cap/timeout, no-retention, resolver/isolation, and rejection-logging tests for every delta-spec scenario.
- [x] 4.2 Run the configured test command and record evidence in verification.md.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 4.5 Complete Audit Record sign-off in verification.md § Audit Record.
- [x] 4.6 Run `openspec validate cap-4-contract-governed-external-postgresql-query-path --strict` and resolve all findings.
