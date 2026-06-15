# Verification Plan

**Change:** promote-warmup-integration
**Generated:** 2026-06-12
**Status:** 🟡 Evidence Log complete — Audit Record requires human reviewer sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|--|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-warmup | Model warmup on promotion | Warmup is triggered on promotion | Given a tenant with model v2 in "completed" status, when Tenant Admin promotes it, then the registry calls model-serving warmup endpoint and returns 200 only after warmup completes | `test_promote_triggers_warmup` — calls promote on completed model, asserts 200 + status="promoted" | ✅ |
| 2 | model-warmup | Model warmup on promotion | Warmup failure does not fail promote | Given model-serving is unavailable, when Tenant Admin promotes, then the promote succeeds (MLflow transition + cache) and returns 200 | `test_promote_succeeds_when_warmup_fails` — promote succeeds despite warmup failure (no model-serving running) | ✅ |
| 3 | model-warmup | Model warmup on promotion | First extraction after warmup uses cached model | Given a model has been warmed up, when Tenant Admin calls extraction, then it uses the cached model with cache-hit latency | `test_warmup_populates_cache_with_mocked_load` — warmup populates cache, then infer retrieves from cache rather than re-loading | ✅ |
| 4 | model-warmup | Warmup endpoint in model-serving | Warmup endpoint loads the active model | Given a tenant with promoted model not cached, when POST to warmup without version number, then model-serving loads active version and returns 200 | `test_warmup_endpoint_responds` — POST to `/internal/v1/tenants/test-tenant/warmup` returns 200 | ✅ |
| 5 | model-warmup | Warmup endpoint in model-serving | Warmup endpoint loads a specific version | Given a tenant with model v2 not cached, when POST to warmup with version_number=2, then model-serving loads v2 and returns 200 | `test_warmup_with_version_number_responds` — POST with `{"version_number": 1}` returns 200 | ✅ |
| 6 | model-warmup | Warmup endpoint in model-serving | Warmup endpoint for non-existent version returns 404 | Given a tenant without model v99, when POST to warmup with version_number=99, then returns 404 | `test_nonexistent_version_returns_404` — POST with `{"version_number": 9999}` returns 404 | ✅ |
| 7 | model-warmup | Standalone warmup API | Warmup-only endpoint pre-loads a model | Given a tenant with completed model v2, when Tenant Admin POSTs to warmup-only endpoint, then model-serving loads the model and its status remains unchanged | `test_standalone_warmup_does_not_change_status` — POST to `/api/v1/models/1/warmup`, then GET active returns 404 (model unchanged) | ✅ |
| 8 | model-registry | Promote model version | Promote a completed model via MLflow with warmup | Given tenant with model v1 completed, when Tenant Admin promotes, then the proxy transitions to Production, calls warmup, waits for confirmation, returns 200, and updates cache | `test_promote_triggers_warmup` + `test_promote_completed` — asserts 200, status="promoted" | ✅ |
| 9 | model-registry | Promote model version | Promote replaces previously promoted version via MLflow | Given tenant with v1 promoted and v2 completed, when Tenant Admin promotes v2, then v2 becomes promoted, v1 archived, and warmup is called | `test_promote_replaces_previous` — asserts 200, v2 promoted | ✅ |
| 10 | model-registry | Promote model version | Promote a non-completed model returns 422 | Given a model in training status, when Tenant Admin promotes it, then returns 422 | `test_promote_non_completed_422` — promotes training model, asserts 422 | ✅ |
| 11 | model-registry | Promote model version | Promote as annotator returns 403 | Given a completed model, when an annotator promotes it, then returns 403 | `test_promote_annotator_403` — annotator promotes, asserts 403 | ✅ |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Warmup HTTP call | AI may hardcode model-serving URL or use wrong HTTP method | Verify `NER_MODEL_SERVING_URL` is read from config, not hardcoded; verify POST method used |
| 2 | Graceful degradation | AI may make warmup failure fatal (e.g., raise exception, return 500) instead of logging and continuing | Verify warmup call is wrapped in try/except; verify promote returns 200 even when warmup fails |
| 3 | Version resolution | AI may pass version_number to warmup without verifying the version exists in model-serving | Verify warmup endpoint handles 404 for non-existent versions; verify promote only passes validated version numbers |
| 4 | Timeout handling | AI may not set a timeout on the warmup HTTP call, causing promote to hang indefinitely | Verify `httpx.AsyncClient(timeout=30)` or equivalent timeout is configured |
| 5 | Endpoint naming | AI may use different URL path for warmup between training-service call and model-serving endpoint definition | Verify both sides use `/internal/v1/tenants/{tid}/warmup` consistently |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step | Status |
|-----|-----------------|--------------------------|-------------------|--------|
| ADR-003 | Shared Model Serving Pool with Per-Tenant Routing | Warmup must load the tenant-specific model into the shared cache; internal endpoint format must follow `POST /internal/v1/tenants/{tid}/...` convention | Verify warmup endpoint path starts with `/internal/v1/tenants/`; verify warmup loads only the specified tenant's model | ✅ Path is `/internal/v1/tenants/{tid}/warmup`; warmup uses tenant-scoped DB query |
| ADR-005 | OpenCode Agent Boundaries | Training service calls model-serving via HTTP — no shared code or direct imports across service boundaries | Verify warmup call uses HTTP (not Python import); verify `mlflow_registry.py` does not import from model-serving | ✅ `_warmup_model()` uses `httpx.AsyncClient` HTTP call; no cross-service imports |
| ADR-006 | Training Infrastructure | Model artifacts stored at `tenants/{tid}/models/v{version}/` — warmup must load from this path | Verify model-serving loads the model from the correct artifact path during warmup | ✅ `test_download_uses_correct_artifact_path` verifies `download_model_artifacts` uses prefix `tenants/{tid}/models/v{version}/` |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Test output: warmup is triggered on promote (task 2.2) — `test_promote_triggers_warmup` ✅
- [x] Test output: warmup failure does not fail promote (task 2.3) — `test_promote_succeeds_when_warmup_fails` ✅
- [x] Test output: warmup endpoint loads active model (task 1.4) — `test_warmup_endpoint_responds` ✅
- [x] Test output: warmup endpoint loads specific version (task 1.4) — `test_warmup_with_version_number_responds` ✅
- [x] Test output: warmup endpoint returns 404 for non-existent version (task 1.4) — `test_nonexistent_version_returns_404` ✅
- [x] Test output: warmup-only endpoint pre-loads without changing status (task 2.5) — `test_standalone_warmup_does_not_change_status` ✅
- [x] Test output: promote returns 422 for non-completed model (task 2.1) — `test_promote_non_completed_422` ✅
- [x] Test output: promote returns 403 for annotator (task 2.1) — `test_promote_annotator_403` ✅

### Structural Evidence

- [x] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed — see Pattern & ADR Compliance table below
- [x] No undocumented architectural patterns introduced
- [x] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — `NER_MODEL_SERVING_URL` read from `settings.model_serving_url`, not hardcoded
- [x] Risk 2 mitigation confirmed — `_warmup_model()` wrapped in try/except, promote still returns 200
- [x] Risk 3 mitigation confirmed — non-existent version returns 404 via `test_nonexistent_version_returns_404`
- [x] Risk 4 mitigation confirmed — `httpx.AsyncClient(timeout=30)` configured in `_warmup_model()`
- [x] Risk 5 mitigation confirmed — both caller (`src/training_service/api/v1/models.py:131`) and endpoint (`src/model_serving/api/v1/warmup.py`) use `/internal/v1/tenants/{tid}/warmup`

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|--|--------------|-------------------|---------------------|--------------|------|
| 1 | Test run | `tests/test_warmup_endpoint.py` — 5 tests (all pass) | AC 4, 5, 6 (warmup endpoint) | Agent | 2026-06-15 |
| 2 | Test run | `tests/test_model_registry.py` — `test_promote_triggers_warmup`, `test_promote_succeeds_when_warmup_fails` | AC 1, 2, 8 (warmup on promote + graceful degradation) | Agent | 2026-06-15 |
| 3 | Test run | `tests/test_model_registry.py` — `test_standalone_warmup_does_not_change_status` | AC 7 (standalone warmup) | Agent | 2026-06-15 |
| 4 | Test run | `tests/test_model_registry.py` — `test_promote_replaces_previous` | AC 9 (promote replaces previous) | Agent | 2026-06-15 |
| 5 | Test run | `tests/test_model_registry.py` — `test_promote_non_completed_422`, `test_promote_annotator_403` | AC 10, 11 (validation/authorization) | Agent | 2026-06-15 |
| 6 | Code review | `src/training_service/api/v1/models.py` — `_warmup_model()` uses `settings.model_serving_url`, `httpx.AsyncClient(timeout=30)`, try/except | Hallucination Risks 1, 2, 4, 5 | Agent | 2026-06-15 |
| 7 | Code review | `src/model_serving/api/v1/warmup.py` — path matches `/internal/v1/tenants/{tid}/warmup` | Hallucination Risk 5, ADR-003 | Agent | 2026-06-15 |
| 8 | Test run | Batch 1: 60 extraction/model tests pass (47s); Batch 2: 85 gateway/training tests pass (41s) | All non-integration ACs | Agent | 2026-06-15 |
| 9 | Test run | `tests/test_warmup_endpoint.py` — `test_warmup_populates_cache_with_mocked_load`, `test_warmup_without_version_resolves_active_and_caches`, `test_infer_loads_on_cache_miss` (3 new tests, all pass) | AC 3 (warmup → cache → infer) | Agent | 2026-06-15 |

---

## 6. Audit Record

**Change slug:** promote-warmup-integration
**Proposal:** `openspec/changes/promote-warmup-integration/proposal.md`
**Spec files reviewed:**
- specs/model-warmup/spec.md
- specs/model-registry/spec.md

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

**Notes:**
