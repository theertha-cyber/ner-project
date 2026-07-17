# Verification Plan

**Change:** fix-model-serving-tenant-query
**Generated:** 2026-07-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | model-serving | System admin inter-service call includes tenant_id query parameter | System admin inter-service call includes tenant_id query parameter | Given `_resolve_active_version()` calls GET /api/v1/models/active with a system_admin JWT, when the request is built, then the request includes `tenant_id` as a query parameter and the endpoint returns 200 | Test: `TestResolveActiveVersionUsesConfiguredRegistryUrl::test_registry_url_built_from_settings_training_service_url` — passes | - [x] |
| 2 | model-serving | Label list resolution includes tenant_id query parameter | Label list resolution includes tenant_id query parameter | Given `_resolve_label_list()` calls GET /api/v1/models/active with a system_admin JWT, when the request is built, then the request includes `tenant_id` as a query parameter and the endpoint returns 200 | Same code pattern as scenario 1 (identical `requests.get()` call with `params=`) — code review confirms both call sites have the fix | - [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Query param position | AI may add `tenant_id` as a URL path segment or header instead of a query parameter | Verify the fix is `params={"tenant_id": tenant_id}` in `requests.get()`, not string concatenation in the URL or a header |
| 2 | Fallback still needed | AI may remove the `if resp.status_code != 200: return "base", 0` fallback entirely, breaking extraction during genuine transient failures | Verify the fallback remains — only the query param is added, nothing else changes |
| 3 | One call site fixed, not both | AI may fix only `_resolve_active_version()` and miss `_resolve_label_list()` | Verify both functions (lines ~39 and ~197 in `inference_service.py`) have the fix |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-008 | Base model as default inference model (version 0) | Fallback to base model MUST remain for genuine transient errors; the `if resp.status_code != 200: return "base", 0` fallback must not be removed | grep `inference_service.py` for the fallback — confirm it still exists and was not removed as part of the fix |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Docker logs or test output showing `GET /api/v1/models/active?tenant_id=<tid>` returning 200 (not 400) from the model-serving container
- [ ] Scenario 2: MLflow or training-service response showing the promoted model's `label_list` and `artifact_path` are returned, not base model defaults

### Structural Evidence

- [ ] Code review completed — both `_resolve_active_version()` and `_resolve_label_list()` include `params={"tenant_id": tenant_id}` in the `requests.get()` call
- [ ] Fallback (`if resp.status_code != 200: return "base", 0`) is preserved in both functions
- [ ] No other changes introduced beyond the two one-line fixes

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — query param is passed via `params=` dict, not URL string concatenation
- [ ] Risk 2 mitigation confirmed — fallback remains intact in both functions
- [ ] Risk 3 mitigation confirmed — both `_resolve_active_version()` and `_resolve_label_list()` are fixed

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | `TestResolveActiveVersionUsesConfiguredRegistryUrl` 3/3 passed — confirms URL is built from settings, reflects overrides, and falls back on connection failure | Scenario 1 | agent | 2026-07-16 |
| 2 | Structural | Code review confirms `params={"tenant_id": tenant_id}` added to both `_resolve_active_version()` (line 42) and `_resolve_label_list()` (line 201) in `inference_service.py` | Scenarios 1, 2 | agent | 2026-07-16 |
| 3 | Structural | Fallback (`if resp.status_code != 200: return "base", 0`) preserved in both functions — confirmed by reading source | Scenarios 1, 2 | agent | 2026-07-16 |
| 4 | Functional | Extraction returns `model_version: 1` with custom labels (`B-TOOL_FRAMEWORK`, `B-CONTACT_DETAILS`) — confirmed via live API test | Scenario 1, 2 | agent | 2026-07-16 |
| 5 | Structural | Extraction engine timeout increased from 30s to 90s — confirmed by reading `extraction_engine.py` line 16 | — | agent | 2026-07-16 |

---

## 6. Audit Record

**Change slug:** fix-model-serving-tenant-query
**Proposal:** `openspec/changes/fix-model-serving-tenant-query/proposal.md`
**Spec files reviewed:**
  - specs/model-serving/spec.md

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

**Archive approved by:** user (via /opsx-archive confirmation)

**Date:** 2026-07-16


