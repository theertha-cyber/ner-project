# Verification Plan

**Change:** `remove-tid-from-url`
**Generated:** 2026-06-16
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Single extraction returns entities without tid in URL | Given a valid JWT with tenant_id for a tenant that has a promoted model, when POST /api/v1/extract with `{"text": "Acme Corp"}`, then 200 with entities and model_version | Integration test: `test_extract_no_tid.py` | - [ ] |
| 2 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Batch extraction accepts request without tid in URL | Given a valid JWT with tenant_id and role: tenant_admin, when POST /api/v1/extract-batch?documentIds=uuid1,uuid2, then 200 with run_id and status "queued" | Integration test: `test_batch_extract_no_tid.py` | - [ ] |
| 3 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Batch status returns run details without tid in URL | Given a valid JWT with tenant_id, when GET /api/v1/extract-batch/{run_id}, then 200 with batch run status and model_version | Integration test: `test_batch_status_no_tid.py` | - [ ] |
| 4 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Entity list returns entities without tid in URL | Given a valid JWT with tenant_id, when GET /api/v1/entities?reviewStatus=unreviewed, then 200 with paginated entity list | Integration test: `test_list_entities_no_tid.py` | - [ ] |
| 5 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Entity patch updates review without tid in URL | Given a valid JWT with tenant_id, when PATCH /api/v1/entities/{entity_id} with `{"review_status": "confirmed"}`, then 200 with updated entity | Integration test: `test_patch_entity_no_tid.py` | - [ ] |
| 6 | auto-resolve-tenant-id | Extraction Service Endpoints Auto-Resolve Tenant ID from JWT | Extraction returns 403 when JWT is missing | Given no JWT token, when POST /api/v1/extract with `{"text": "test"}`, then 403 | Integration test: `test_extract_no_jwt.py` | - [ ] |
| 7 | auto-resolve-tenant-id | Model Serving Endpoints Auto-Resolve Tenant ID from JWT | Inference returns predictions without tid in URL | Given a valid JWT with tenant_id, when POST /internal/v1/infer with `{"tokens": ["Acme", "Corp"]}`, then 200 with predictions and model_version | Integration test: `test_infer_no_tid.py` | - [ ] |
| 8 | auto-resolve-tenant-id | Model Serving Endpoints Auto-Resolve Tenant ID from JWT | Warmup loads model without tid in URL | Given a valid JWT with tenant_id, when POST /internal/v1/warmup with `{"version_number": 3}`, then 200 with `{"status": "ok", "version_number": 3}` | Integration test: `test_warmup_no_tid.py` | - [ ] |
| 9 | auto-resolve-tenant-id | Model Serving Endpoints Auto-Resolve Tenant ID from JWT | Warmup version 0 succeeds without tid in URL | Given a valid JWT with tenant_id, when POST /internal/v1/warmup with `{"version_number": 0}`, then 200 with `{"status": "ok", "version_number": 0}` | Integration test: `test_warmup_v0_no_tid.py` | - [ ] |
| 10 | auto-resolve-tenant-id | Model Serving Endpoints Auto-Resolve Tenant ID from JWT | Inference returns 403 when JWT is missing | Given no JWT token, when POST /internal/v1/infer with `{"tokens": ["test"]}`, then 403 | Integration test: `test_infer_no_jwt.py` | - [ ] |
| 11 | auto-resolve-tenant-id | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy forwards single extraction request without tid in URL | Given a valid JWT with tenant_id and role: business_user, when POST to external gateway /api/v1/extract with `{"text": "Acme Corp"}`, then 200 and proxy forwards to extraction service at /api/v1/extract | Integration test: `test_proxy_extract_no_tid.py` | - [ ] |
| 12 | auto-resolve-tenant-id | Gateway Extraction Proxy Uses JWT-Only URL Structure | Proxy returns 403 when JWT is missing | Given no JWT token, when POST to external gateway /api/v1/extract with `{"text": "test"}`, then 403 | Integration test: `test_proxy_extract_no_jwt.py` | - [ ] |
| 13 | auto-resolve-tenant-id | Callers Construct URLs Without {tid} | Extraction engine forwards request without tid in URL | Given synchronous extract endpoint receives a request with valid JWT, when extraction_engine.infer() is called, then HTTP POST to model serving uses URL /internal/v1/infer with Authorization header | Unit test: verify `_infer_url()` returns `/internal/v1/infer`; mock assertion on `Authorization` header presence | - [ ] |
| 14 | auto-resolve-tenant-id | Callers Construct URLs Without {tid} | Worker constructs inference URL without tid in path | Given a batch extraction run is processing, when worker sends inference request, then URL is /internal/v1/infer with valid JWT | Code review: grep for old URL pattern in worker.py | - [ ] |
| 15 | auto-resolve-tenant-id | Callers Construct URLs Without {tid} | Training service constructs warmup URL without tid in path | Given a model is being promoted, when _warmup_model() sends warmup request, then URL is /internal/v1/warmup with valid JWT | Code review: grep for old URL pattern in models.py | - [ ] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Caller URL updates | AI may update endpoint files (extraction.py, etc.) but forget to update the callers (extraction_engine.py, worker.py, models.py) that construct URLs to those endpoints | Verify all 3 caller files are updated — grep for old patterns like `tenants/{tenant_id}/infer` and `tenants/{tenant_id}/warmup` — should return zero matches |
| 2 | JWT forwarding in extraction_engine | AI may remove tenant_id from the URL but forget to add JWT forwarding in the `infer()` function (currently no Authorization header is sent) — the model serving service would have no way to determine tenant_id | Verify extraction_engine.infer() reads Authorization header from the incoming request and forwards it in the httpx call |
| 3 | Gateway proxy prefix | AI may update the extraction service endpoints but forget the gateway extraction proxy — external callers would still hit the old URLs | Verify gateway extraction_proxy.py router prefix no longer contains `{tid}` |
| 4 | README endpoint docs | AI may update code but leave stale endpoint URLs in README.md | Verify README no longer documents any `/api/v1/tenants/{tid}/` extraction or `/internal/v1/tenants/{tid}/` model serving URLs |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 | Tenant data isolation via separate PostgreSQL schemas per tenant | Tenant_id must still be resolved from JWT and used for schema-scoped queries — removing URL `{tid}` must not break schema resolution | Confirm middleware still sets `request.state.tenant_id` — no code changes to middleware or schema resolution |
| ADR-003 | Shared Model Serving Layer, endpoint `POST /internal/v1/tenants/{tenant_id}/infer` | The endpoint URL is documented in ADR-003 — this change modifies it. ADR-003 must be updated or superseded | Verify new ADR is created that supersedes ADR-003's endpoint URL spec, or ADR-003 is updated to reflect `POST /internal/v1/infer` |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Test output showing ALL extraction endpoint scenarios pass with new URL paths (no `{tid}`)
- [ ] Test output showing model serving inference and warmup endpoints work with new URL paths
- [ ] Test output showing gateway proxy forwards requests to new extraction URLs
- [ ] Test output showing extraction_engine.infer() sends Authorization header with JWT
- [ ] Test output showing 403 responses when JWT is missing on new endpoint URLs

### Structural Evidence

- [ ] Code review completed — all handler signatures no longer accept `tid` parameter
- [ ] Code review completed — no `tid != tenant_id` validation remains in any updated handler
- [ ] All 3 caller files (extraction_engine.py, worker.py, models.py) updated to use URLs without `{tid}`
- [ ] Gateway extraction proxy updated — prefix no longer includes `{tid}`
- [ ] README.md updated — no stale `/api/v1/tenants/{tid}` or `/internal/v1/tenants/{tid}` URLs remain
- [ ] ADR-003 endpoint URL change addressed (new ADR or update)

### Edge Case Evidence

- [ ] Grep confirms zero occurrences of `/internal/v1/tenants/{` or `/api/v1/tenants/{tid}` in code paths (only expected in git history)
- [ ] Extraction engine infer() verified to pass JWT Authorization header — confirmed via code review
- [ ] All test files using old URL paths found and updated — grep for old URL patterns in test files

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** `remove-tid-from-url`
**Proposal:** `openspec/changes/remove-tid-from-url/proposal.md`
**Spec files reviewed:**
- specs/auto-resolve-tenant-id/spec.md

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
<!-- Any observations, caveats, or follow-up items for future changes. -->
