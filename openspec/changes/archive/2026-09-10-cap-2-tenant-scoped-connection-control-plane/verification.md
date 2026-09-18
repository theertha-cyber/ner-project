# Verification Plan

**Change:** cap-2-tenant-scoped-connection-control-plane
**Status:** Incomplete until implementation evidence is recorded.

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|---|---|---|---|---|---|
| 1 | control-plane | Tenant-admin-managed finite Azure connections | Tenant administrator tests a supported Azure Blob draft | A tenant admin test returns only finite safe outcome/correlation data bound to its tenant. | API test (`TestSecureTest::test_passing_test_validates`) | - [x] |
| 2 | control-plane | Tenant-admin-managed finite Azure connections | Non-administrator is denied | A non-admin lifecycle request changes no state. | API authorization test (`TestAuthz::test_non_admin_denied_without_state_change`) | - [x] |
| 3 | control-plane | Tenant-admin-managed finite Azure connections | Cross-tenant connection access is denied | A tenant B admin cannot read tenant A metadata. | Tenant-isolation test (`TestAuthz::test_cross_tenant_access_is_not_found`) | - [x] |
| 4 | control-plane | Safe activation and concurrent capability limits | Failed prerequisite blocks activation | Missing test, secret, or evidence leaves connection inactive with safe class only. | Lifecycle test (`TestActivation::{test_activate_without_test_is_required,test_activate_with_failed_test_is_rejected,test_activate_without_evidence_is_blocked}` + `TestSecureTest::{test_unresolvable_reference_errors_safely,test_failing_tester_errors_safely}`) | - [x] |
| 5 | control-plane | Safe activation and concurrent capability limits | Independent approved connections activate concurrently | One active Blob and PostgreSQL connection coexist per tenant. | Limit test (`TestActivation::test_independent_providers_activate_concurrently`) | - [x] |
| 6 | control-plane | Safe activation and concurrent capability limits | Duplicate active provider is rejected | A second active provider of the same class is rejected without changing the first. | Limit test (`TestActivation::test_duplicate_active_provider_rejected`) | - [x] |
| 7 | integration-profile | Only platform default adapters are executable in this change | A non-default selection may be recorded | Unsupported selection remains draft. | Existing compatibility test (`TestCompatibility::test_unsupported_selection_stays_recorded_but_inactive`) | - [x] |
| 8 | integration-profile | Only platform default adapters are executable in this change | An unsupported non-default selection cannot be activated | Unsupported non-Azure selection cannot activate. | Compatibility test (`TestCompatibility::test_unsupported_selection_cannot_activate`) | - [x] |
| 9 | integration-profile | Only platform default adapters are executable in this change | An approved Azure connection can execute after activation | Activated approved Azure capability resolves only for owning tenant. | Resolver test (`TestCompatibility::test_approved_azure_resolves_only_for_owning_tenant`) | - [x] |
| 10 | integration-profile | Only platform default adapters are executable in this change | Ingestion always uses executable adapters | Inactive/unsupported source cannot alter upload path. | Compatibility test (`TestCompatibility::test_platform_defaults_stay_executable`) | - [x] |
| 11 | integration-profile | Profiles are developer-managed | Tenant users cannot modify platform profiles | Tenant admin cannot alter platform-default or unsupported profile. | Authorization test (`TestContract::test_platform_provider_not_administrable`) | - [x] |
| 12 | integration-profile | Profiles are developer-managed | Tenant administrators manage only approved Azure connections | Tenant-admin Azure operation uses bounded lifecycle and tenant scope. | API test (`TestCreate` + `TestAuthz` classes) | - [x] |

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|---|---|---|
| 1 | Tenant authority | Trusting a route or payload tenant identifier. | Confirm server derives tenant from authenticated context in every operation. |
| 2 | Secret handling | Persisting/logging resolved credentials or provider diagnostics. | Inspect models, responses, logs, and telemetry tests for references/outcome classes only. |
| 3 | Activation | Omitting evidence or concurrent-limit checks. | Exercise failed prerequisites and same-type activation race/duplicate paths. |
| 4 | Compatibility | Enabling arbitrary profile selections. | Verify only the two approved Azure provider types are exceptional. |

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step |
|---|---|---|
| ADR-001 | Public records are tenant-bound non-content data; authenticated context is authority. | Review persistence and resolver tests for tenant binding and no sensitive fields. |
| ADR-011 | Finite Azure catalog, safe evidence, TLS/least privilege and prerequisite-gated activation. | Review configuration validation, activation tests, and safe telemetry assertions. |

## 4. Evidence Requirements

- [x] Passing executable tests cover every Section 1 scenario.
- [x] Code review confirms only finite safe evidence and secret references are persisted or surfaced.
- [x] Code review confirms ADR-001 and ADR-011 constraints.
- [x] Telemetry scan confirms lifecycle paths contain no prohibited payload classes.

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|---|---|---|---|---|
| 1 | Executable tests | `tests/test_tenant_data_source_control_plane.py` — 38 passed | Rows 1–12 | ralph CAP-2 apply | 2026-09-10 |
| 2 | Regression tests | `tests/test_tenant_integration_profile.py` + `tests/shared/test_domain_metrics_declarations.py` + `tests/shared/test_config_secret_hygiene.py` — 42 passed | Rows 7–8, 10; metric allowlist | ralph CAP-2 apply | 2026-09-10 |
| 3 | Full suite | `pytest` — 2344 passed; 92 failed + 31 errors + 1 collection error, all in files outside this change's surface (`training_jobs_api`, `model_registry`, `user_auth`, `entity_query`, migrations, `env_config`, …) and reproduced with the CAP-2 router disabled, plus a pre-existing `SyntaxError` in `tests/test_analytics_dashboard.py` | Suite-wide regression | ralph CAP-2 apply | 2026-09-10 |
| 4 | Telemetry assertions + scan self-check | `TestTelemetry` (label sets mirror lifecycle, no tenant label, coercion) + per-response `assert_no_secrets` across the suite; `domain_metrics.allowlist_violations() == []`; `scripts/telemetry_scan.py --dry-run` PASS (self-check: the scan finds planted leaks and rejects empty captures). Full release-gate scan against the live stack is a QA-stage activity. | NFR-SECU-001 (unit level) | ralph CAP-2 apply | 2026-09-10 |
| 5 | Datastore hygiene | `ner_test.public.tenant_data_source_connections`, `tenant_data_source_idempotency`, and `cap2-%` tenant rows all count 0 after the suite | Test isolation | ralph CAP-2 apply | 2026-09-10 |
|---|---|---|---|---|---|

## 6. Audit Record

**Change slug:** cap-2-tenant-scoped-connection-control-plane

- [x] Design, ADR, specification, implementation, and executable evidence reviewed.
  - Reviewed by: `openspec-observer` gate (verdict COMPLETE, 2026-09-10) plus implementer
    code review of models, responses, logs, and telemetry for references/outcome
    classes only. Executable evidence: 38/38 new tests, 42/42 neighbor tests,
    full-suite failures proven pre-existing and out of surface.
