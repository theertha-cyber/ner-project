# Verification Plan

**Change:** cap-4-contract-governed-external-postgresql-query-path
**Status:** Complete — implementation evidence recorded 2026-09-10.

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|---|---|---|---|---|---|
| 1 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Valid contract is published | Canonical version retained; tenant-isolated index created; invisible to other tenants. | Contract publish/index test (`test_valid_contract_publish_creates_tenant_index`) | - [x] |
| 2 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Invalid contract is rejected safely | Version not accepted; finite reason class + field errors; no index entry. | Contract validation test (`test_invalid_contract_rejected_with_finite_reason`) | - [x] |
| 3 | external-postgresql-chat | Versioned tenant-isolated schema contracts | Cross-tenant contract access is denied | Not-found resolution; no cross-tenant index retrieval. | Isolation test (`test_cross_tenant_contract_and_index_denied`) | - [x] |
| 4 | external-postgresql-chat | Drift-gated external read-only query | Drift blocks execution | No SQL executes; safe drift-blocked outcome. | Drift-negative test (`test_drift_mismatch_blocks_without_execution`) | - [x] |
| 5 | external-postgresql-chat | Drift-gated external read-only query | Unavailable metadata blocks execution distinctly | No SQL executes; `metadata_unavailable` reason. | Metadata-unavailable test (`test_unavailable_metadata_blocks_distinctly`) | - [x] |
| 6 | external-postgresql-chat | Drift-gated external read-only query | Replacement contract restores execution | Queries execute again after matching replacement. | Replacement test (`test_replacement_contract_restores_execution`) | - [x] |
| 7 | external-postgresql-chat | Contract-authorized SQL execution | Approved join and aggregation executes | Executes within cap/timeout; response-only rows. | Execution test (`test_approved_join_aggregation_executes`) | - [x] |
| 8 | external-postgresql-chat | Contract-authorized SQL execution | Disallowed statement is rejected safely | Never reaches database; finite rejection reason only. | Validator negative tests (`test_disallowed_statements_rejected_safely`) | - [x] |
| 9 | external-postgresql-chat | Contract-authorized SQL execution | Unparameterized literal never reaches the database | Literals bound or rejected; no interpolation. | Parameterization test (`test_inline_literals_bound_or_rejected`) | - [x] |
| 10 | external-postgresql-chat | Contract-authorized SQL execution | Row cap and timeout are enforced by the server | ≤100 rows; 10s server timeout. | Cap/timeout tests (`test_server_row_cap_and_timeout_enforced`) | - [x] |
| 11 | external-postgresql-chat | Contract-authorized SQL execution | External rows are never retained | No tenant row in platform storage afterwards. | No-retention test (`test_external_rows_never_retained`) | - [x] |
| 12 | external-postgresql-chat | Contract-authorized SQL execution | Capability resolves server-side per authenticated tenant | Only own connection/contract/credential used. | Resolver test (`test_capability_resolves_per_authenticated_tenant`) | - [x] |
| 13 | chat-api | SQL query generation and validation | Malicious SQL is rejected | Rejected with finite reason class, no SQL text. | Rejection-logging test (`test_rejected_sql_records_reason_class_only`) | - [x] |

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required | Disposition |
|---|---|---|---|---|
| 1 | Tenant authority | Reading tenant from contract payload or tool input. | Confirm tenant derives from authenticated context + connection row. | Confirmed: `capability.py` takes `tenant_id` as an argument from the authenticated caller and `active_connection`/`accepted_contract` constrain it server-side; `test_capability_resolves_per_authenticated_tenant` and `test_cross_tenant_contract_and_index_denied` pass. |
| 2 | Index as authority | Authorizing a query from index similarity. | Confirm validator reads canonical contract only. | Confirmed: `validator.validate_statement` takes the canonical contract; `index.py` has no import path into validator/connector. |
| 3 | Drift bypass | Executing when introspection fails open. | Confirm every failure mode blocks; negative tests. | Confirmed: `test_drift_mismatch_blocks_without_execution` and `test_unavailable_metadata_blocks_distinctly` assert zero executions. |
| 4 | SQL interpolation | Formatting literals into SQL text. | Confirm parameter binding; executed-text assertions. | Confirmed: `test_inline_literals_bound_or_rejected` asserts params bound and `%(min_total)s` placeholder form; static scan finds no interpolation in connector/validator. |
| 5 | Telemetry leakage | Logging SQL, literals, rows, endpoints. | Static scan + negative log-capture tests. | Confirmed: `test_disallowed_statements_rejected_safely` and `test_rejected_sql_records_reason_class_only` assert reason-class-only logs with no SQL text; static scan clean. |
| 6 | Live Azure | Attempting real Azure connections in tests. | Confirm fixture seam; deferred live verification. | Confirmed: `FixtureExternalDatabase` throughout; no credential or network in the suite; live verification deferred per `run.provisioning`. |

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step | Disposition |
|---|---|---|---|
| ADR-001 | Public canonical contracts tenant-bound; server-side tenant scope; no tenant rows in platform. | Review migration + tenant binding + no-retention test. | Confirmed: migration 042 creates tenant-bound public contracts + tenant-schema index; `test_cross_tenant_contract_and_index_denied` and `test_external_rows_never_retained` pass. |
| ADR-013 | Separate capability; canonical contract + live fingerprint; AST SELECT-only; row cap; 10s timeout; no LLM credential. | Review validator/connector tests + drift negatives. | Confirmed: 15/15 external-postgres tests pass; drift negatives assert zero executions; cap/timeout asserted on constants and execution. |
| ADR-011 | Active-connection + activation-evidence gating. | Inactive-connection query refusal test. | Confirmed: paused-connection capability resolves `not_active_connection` (`test_capability_resolves_per_authenticated_tenant`). |

## 4. Evidence Requirements

- [x] Passing executable tests cover every Section 1 scenario.
- [x] Code review confirms contract/fingerprint/validator/connector/resolver boundaries.
- [x] Code review confirms ADR-001, ADR-011, ADR-013 constraints.
- [x] Telemetry scan confirms no prohibited payload classes on new paths.
- [x] Datastore hygiene: contract/index test rows removed after the suite.

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|---|---|---|---|---|
| 1 | Executable tests | `tests/test_external_postgresql_chat.py`: 15 passed | Rows 1–13 | ralph CAP-4 apply | 2026-09-10 |
| 2 | Executable tests | `tests/test_tenant_data_source_control_plane.py` + `tests/test_azure_blob_source_sync.py` + `tests/test_ingestion_boundary.py`: 83 passed | CAP-2/CAP-3 dependencies, no regressions | ralph CAP-4 apply | 2026-09-10 |
| 3 | Static review | New `external_postgres/` paths scanned for print/traceback/secret/endpoint/interpolation patterns: none found | Rows 8, 13 | ralph CAP-4 apply | 2026-09-10 |
| 4 | Observer round-trip | First gate returned INCOMPLETE on environmental grounds (observer env lacked `public.tenant_data_source_connections`; 13 setup-time `UndefinedTableError`, zero assertion failures). Test fixture now restates the full CAP-2 DDL (alembic 040) with `IF NOT EXISTS`; table dropped and suite re-run: 15/15 pass on the unmigrated shape, and CAP-2/CAP-3/boundary suites still pass (83/83) against the recreated table. | Rows 1–13 | ralph CAP-4 apply | 2026-09-10 |

## 6. Audit Record

**Change slug:** cap-4-contract-governed-external-postgresql-query-path

- [x] Design, ADR, specification, implementation, and executable evidence reviewed.

Live Azure PostgreSQL verification deferred per `run.provisioning` (no approved test instance); fixture-backed integration tests stand in, and the capability remains inactive until activation evidence exists.
