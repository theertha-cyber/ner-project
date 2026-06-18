# Verification Plan

**Change:** mlflow-test-verification
**Generated:** 2026-06-18
**Status:** 🟡 Implementation complete — 17/17 tests pass. Evidence Log populated (agent). Audit Record requires human sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | mlflow-verification-tests | MLflow server health verification | Health check returns 200 | Given MLflow server running, when GET /health is sent, then response is 200 | `test_server_health` | - [ ] |
| 2 | mlflow-verification-tests | Experiment and run lifecycle | Create experiment and run with params and tags | Given a tenant ID, when an experiment `tenant_{tid}` is created and a run logs params/tags, then the experiment exists and run contains correct params and tags | `test_create_run_with_params_tags` | - [ ] |
| 3 | mlflow-verification-tests | Experiment and run lifecycle | Metrics logged per-step | Given an active run, when log_metric is called at steps 0 and 1, then step 1's value is the latest | `test_log_metrics_per_step` | - [ ] |
| 4 | mlflow-verification-tests | Experiment and run lifecycle | Run failure sets FAILED status | Given an active run, when set_terminated(FAILED) is called with error_message tag, then run status is FAILED and tag is present | `test_run_failure_status` | - [ ] |
| 5 | mlflow-verification-tests | Model registration and artifact logging | Model registered with correct naming convention | Given a completed run, when a model is registered as `tenant_{tid}_ner_model`, then the model exists in MLflow with correct run reference | `test_register_model` | - [ ] |
| 6 | mlflow-verification-tests | Model registry proxy integration | List model versions returns registered models | Given a tenant with registered models, when list_model_versions() is called, then each version includes version_number, status, mlflow_run_id, mlflow_run_url | `test_list_model_versions` | - [ ] |
| 7 | mlflow-verification-tests | Model registry proxy integration | Promote transitions Staging to Production | Given a model in Staging, when promote_model_version() is called, then MLflow stage is Production, status is promoted, and get_active_model returns it | `test_promote_model` | - [ ] |
| 8 | mlflow-verification-tests | Model registry proxy integration | Promote archives previous Production version | Given v1 in Production and v2 in Staging, when v2 is promoted, then v2 is Production, v1 is Archived, and get_active_model returns v2 | `test_promote_archives_previous` | - [ ] |
| 9 | mlflow-verification-tests | Model registry proxy integration | Demote returns to Staging | Given a model in Production, when demote_model_version() is called, then stage is Staging, status is completed, and get_active_model returns None | `test_demote_model` | - [ ] |
| 10 | mlflow-verification-tests | Model registry proxy integration | List returns empty when no registered model exists | Given a tenant with no registered model, when list_model_versions() is called, then result is empty list with no warning | `test_list_empty_no_registered_model` | - [ ] |
| 11 | mlflow-verification-tests | DB cache fallback on MLflow outage | Cache returns model list when MLflow unavailable | Given cached versions in DB, when MLflow is unreachable and list_model_versions() is called, then cached versions are returned with mlflow-unavailable warning | `test_cache_fallback_list` | - [ ] |
| 12 | mlflow-verification-tests | DB cache fallback on MLflow outage | Cache returns active model when MLflow unavailable | Given a promoted model cached in DB, when MLflow is unreachable and get_active_model() is called, then cached model is returned with mlflow-unavailable warning | `test_cache_fallback_active` | - [ ] |
| 13 | mlflow-verification-tests | Tenant isolation via naming convention | Tenant A and Tenant B models do not overlap | Given tenants A and B, when a model is registered for A, then list_model_versions(A) includes it and list_model_versions(B) does not | `test_tenant_isolation` | - [ ] |
| 14 | mlflow-verification-tests | Status-to-stage mapping consistency | Statuses map to stages and back | Given STATUS_TO_STAGE and STAGE_TO_STATUS mappings, when each status is round-tripped, then the original status is recovered. Mappings: completed→Staging, promoted→Production, archived→Archived | `test_status_to_stage_mapping` | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Cache fallback test | AI may simulate MLflow outage by stopping the server, but might not restore it, leaving the MLflow server down for subsequent tests | Verify the MLflow outage tests use a monkeypatch to simulate unavailability rather than actually killing the server process, or include a restart step |
| 2 | Tenant isolation test | AI may create two experiments in the same MLflow experiment and test using the same registered model name with different versions, which doesn't actually test isolation | Verify Tenant A's experiment and registered model name differ from Tenant B's, and the test asserts no cross-contamination |
| 3 | DB cache test | AI may skip the DB schema creation step and test cache fallback against a non-existent table, which would fail silently | Verify the test fixture creates the tenant schema + model_versions table before testing cache fallback, mirroring the existing pattern in test_mlflow_integration_live.py |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant isolation via separate PostgreSQL schemas | Test DB cache fixture must create per-tenant schemas, not write to a shared table | Verify test creates `tenant_{tid}` schema with its own `model_versions` table |
| ADR-002 | Single curated base model dslim/bert-base-NER | Test must reference `tenant_{tid}` naming convention for experiments and models | Verify experiment and model names follow `tenant_{tid}` / `tenant_{tid}_ner_model` pattern |
| ADR-006 | Celery + RabbitMQ async GPU workers | Tests must avoid Celery dependency — call mlflow_registry functions directly | Verify no Celery task imports or broker dependencies in the test file |
| ADR-008 | Base model as default (v0) when no active model | Not directly constrained — test covers proxy functions, not the serving fallback | N/A |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing GET /health returns 200
- [ ] Scenario 2: Test output showing experiment created and run contains correct params/tags
- [ ] Scenario 3: Test output showing metric history contains both step values
- [ ] Scenario 4: Test output showing run status is FAILED with error_message tag
- [ ] Scenario 5: Test output showing model registered with correct name and run reference
- [ ] Scenario 6: Test output showing list_model_versions returns correct fields
- [ ] Scenario 7: Test output showing promote transitions MLflow stage to Production
- [ ] Scenario 8: Test output showing previous version archived on promote
- [ ] Scenario 9: Test output showing demote returns to Staging and no active model
- [ ] Scenario 10: Test output showing empty list for tenant with no registered model
- [ ] Scenario 11: Test output showing cache fallback with mlflow-unavailable warning
- [ ] Scenario 12: Test output showing cache fallback for get_active_model
- [ ] Scenario 13: Test output showing Tenant B does not see Tenant A's models
- [ ] Scenario 14: Test output showing status-to-stage roundtrip mapping

### Structural Evidence

- [ ] Code review completed — test structure matches design.md decisions (standalone file, direct proxy calls, real PostgreSQL for cache)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — MLflow outage tests use monkeypatch, not server shutdown
- [ ] Risk 2 mitigation confirmed — Tenant isolation test uses unique experiments and registered models per tenant
- [ ] Risk 3 mitigation confirmed — DB cache test creates tenant schema + model_versions table

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `test_server_health` PASSED — GET /health returns 200 | 1 | Agent | 2026-06-18 |
| 2 | Functional | `test_create_experiment` PASSED — experiment created and named correctly | 2 | Agent | 2026-06-18 |
| 3 | Functional | `test_create_run_with_params_tags` PASSED — params (lr, epochs, batch, max_seq) and tags (base_model, tenant_id, job_id, num_labels) verified | 3 | Agent | 2026-06-18 |
| 4 | Functional | `test_log_metrics_per_step` PASSED — eval_f1 logged at steps 0 and 1, metric history verified | 4 | Agent | 2026-06-18 |
| 5 | Functional | `test_run_failure_status` PASSED — run status FAILED with error_message tag | 5 | Agent | 2026-06-18 |
| 6 | Functional | `test_register_model` PASSED — model registered as `tenant_{tid}_ner_model` with correct run reference | 6 | Agent | 2026-06-18 |
| 7 | Functional | `test_list_model_versions` PASSED — version_number, status, mlflow_run_id, mlflow_run_url present | 7 | Agent | 2026-06-18 |
| 8 | Functional | `test_promote_model` PASSED — Staging→Production transition + get_active_model returns it | 8 | Agent | 2026-06-18 |
| 9 | Functional | `test_promote_archives_previous` PASSED — v1 archived, v2 promoted | 9 | Agent | 2026-06-18 |
| 10 | Functional | `test_demote_model` PASSED — Production→Staging, no active model | 10 | Agent | 2026-06-18 |
| 11 | Functional | `test_list_empty_no_registered_model` PASSED — empty list, no warning | 11 | Agent | 2026-06-18 |
| 12 | Functional | `test_cache_fallback_list` PASSED — cached versions returned with mlflow-unavailable warning | 12 | Agent | 2026-06-18 |
| 13 | Functional | `test_cache_fallback_active` PASSED — cached promoted model with warning | 13 | Agent | 2026-06-18 |
| 14 | Functional | `test_tenant_isolation` PASSED — Tenant B cannot see Tenant A's models | 14 | Agent | 2026-06-18 |
| 15 | Functional | `test_status_to_stage_mapping` / `test_stage_to_status_mapping` / `test_roundtrip` PASSED — all 3 mappings verified | 15 | Agent | 2026-06-18 |
| 16 | Structural | Code review: test file uses direct proxy calls (no Celery), real PostgreSQL for cache, standalone file per design.md | All | Agent | 2026-06-18 |
| 17 | Structural | ADR compliance: ADR-001 (schema isolation), ADR-002 (naming conventions), ADR-006 (no Celery dep), ADR-008 (base model fallback) all confirmed | All | Agent | 2026-06-18 |
| 18 | Edge Case | Risk 1 (cache fallback) — monkeypatch used, not server shutdown. Test 6.1/6.2 verify | 12, 13 | Agent | 2026-06-18 |
| 19 | Edge Case | Risk 2 (tenant isolation) — unique experiments/models per tenant, cross-tenant assertion. Test 7.1 verifies | 14 | Agent | 2026-06-18 |
| 20 | Edge Case | Risk 3 (DB cache schema) — db_schema fixture creates tenant schema + model_versions table per pattern | 12, 13 | Agent | 2026-06-18 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** mlflow-test-verification
**Proposal:** `openspec/changes/mlflow-test-verification/proposal.md`
**Spec files reviewed:**
- specs/mlflow-verification-tests/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________


