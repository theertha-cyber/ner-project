# Verification Plan

**Change:** fix-cors-preflight-middleware
**Generated:** 2026-06-19
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | cors-preflight-passthrough | OPTIONS requests bypass authentication middleware | Browser preflight to document service succeeds | Given a fresh browser session with no cached preflight for port 8001, when an annotator clicks a task, then the OPTIONS request to the document service returns a 2xx response with `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers`, and the subsequent GET returns document text | DevTools Network trace or unit test on middleware | - [ ] |
| 2 | cors-preflight-passthrough | OPTIONS requests bypass authentication middleware | Browser preflight to annotation service succeeds without cache | Given no cached CORS preflight for port 8005, when the browser sends OPTIONS to `/api/v1/documents/{id}/spans`, then the response is 2xx with the required CORS headers and the span request proceeds | DevTools Network trace or unit test on middleware | - [ ] |
| 3 | cors-preflight-passthrough | OPTIONS requests bypass authentication middleware | Non-OPTIONS requests still require authentication | Given a GET/POST/PATCH/DELETE request with no Authorization header to either service, when it reaches TenantContextMiddleware, then the response is 401 with `AUTH_ERROR` and the route handler is not invoked | Existing auth test suite / manual curl | - [ ] |
| 4 | cors-preflight-passthrough | OPTIONS requests bypass authentication middleware | OPTIONS request receives X-Request-ID response header | Given any OPTIONS preflight to either service, when TenantContextMiddleware passes it through, then the response includes an `X-Request-ID` header | Unit test or header inspection in DevTools | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | OPTIONS guard placement | Guard added after auth checks rather than before — OPTIONS still hits token validation | Inspect the generated code: the `if request.method == "OPTIONS"` block must appear BEFORE the `auth_header` check and the `exempt_paths` block |
| 2 | call_next vs early return | AI returns a hardcoded 200 response instead of calling `call_next`, skipping CORSMiddleware entirely | Verify `call_next(request)` is called and the result is returned; no manual CORS header construction should appear |
| 3 | Partial fix (one service only) | AI applies the fix only to the document service middleware, leaving the annotation service middleware unchanged | Diff both files: `src/document_service/middleware/tenant_context.py` and `src/annotation_service/middleware/tenant_context.py` must both have the OPTIONS guard |
| 4 | Auth regression | Guard inadvertently broadens exemptions (e.g., applies to all unauthenticated methods, not just OPTIONS) | Confirm the guard is strictly `if request.method == "OPTIONS"` with no additional conditions or fallthrough |
| 5 | X-Request-ID missing on passthrough | The early-return path for OPTIONS omits the `X-Request-ID` header added in the normal flow | Check the OPTIONS branch: the response from `call_next` must have `response.headers["X-Request-ID"] = request_id` set before returning |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant data is schema-isolated; JWT carries tenant_id | TenantContextMiddleware must still validate auth for all non-OPTIONS methods | Run a GET request without auth to each service and confirm 401 is still returned |
| ADR-005-opencode-agent-boundaries | Services own their own middleware stacks; no shared middleware abstraction | Fix must be applied per-service, not via a shared module | Confirm no new shared module is introduced; both files are edited in-place |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1 (document service preflight): DevTools Network trace or test showing OPTIONS to port 8001 returns 2xx with CORS headers when browser has no cached preflight, and the `text` fetch succeeds
- [ ] Scenario 2 (annotation service preflight): DevTools trace or test showing OPTIONS to port 8005 returns 2xx with CORS headers without cache
- [ ] Scenario 3 (auth regression): curl or test output showing `GET /api/v1/documents/{id}/text` without Authorization header still returns 401
- [ ] Scenario 4 (X-Request-ID): Header inspection confirming `X-Request-ID` is present in the OPTIONS response from both services

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 (guard placement): Confirmed `if request.method == "OPTIONS"` appears before any auth header check in both files
- [ ] Risk 2 (call_next usage): Confirmed no manual CORS header construction; `call_next(request)` is called and its response returned
- [ ] Risk 3 (both services patched): Diff of both middleware files confirms OPTIONS guard present in each
- [ ] Risk 4 (auth not regressed): Non-OPTIONS unauthenticated requests still return 401 in both services
- [ ] Risk 5 (X-Request-ID on OPTIONS): OPTIONS response includes `X-Request-ID` header in both services

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | DevTools: OPTIONS to port 8001 returns 2xx with CORS headers; `text` fetch succeeds after fix | Scenario 1 — doc service preflight | human reviewer | |
| 2 | Functional | DevTools: OPTIONS to port 8005 returns 2xx with CORS headers when cache cleared | Scenario 2 — annotation service preflight | human reviewer | |
| 3 | Functional | `curl -X GET http://localhost:8001/api/v1/documents/test/text` → HTTP 401 `AUTH_ERROR` (confirmed 2026-06-19) | Scenario 3 — auth not regressed | agent | 2026-06-19 |
| 4 | Functional | DevTools: OPTIONS response includes `X-Request-ID` header on both ports | Scenario 4 — X-Request-ID on OPTIONS | human reviewer | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** fix-cors-preflight-middleware
**Proposal:** `openspec/changes/fix-cors-preflight-middleware/proposal.md`
**Spec files reviewed:**
- specs/cors-preflight-passthrough/spec.md

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
