## 1. Document Service Middleware Fix

- [x] 1.1 In `src/document_service/middleware/tenant_context.py`, add an OPTIONS guard at the top of `dispatch()` — before the `exempt_paths` check and before the `auth_header` check — that calls `call_next(request)`, sets `X-Request-ID` on the response, and returns it
- [x] 1.2 Confirm the guard is strictly `if request.method == "OPTIONS":` with no additional conditions

## 2. Annotation Service Middleware Fix

- [x] 2.1 In `src/annotation_service/middleware/tenant_context.py`, apply the identical OPTIONS guard at the same position in `dispatch()`
- [x] 2.2 Confirm the guard is strictly `if request.method == "OPTIONS":` with no additional conditions

## 3. Scenario Verification

- [x] 3.1 Verify Scenario 1 (document service preflight): with browser DevTools open and CORS preflight cache cleared, click an annotation task and confirm the OPTIONS request to port 8001 returns 2xx with `Access-Control-Allow-Origin` and `Access-Control-Allow-Headers`, and the `text` response loads — update verification.md Evidence Log row 1
- [x] 3.2 Verify Scenario 2 (annotation service preflight): clear cache and confirm OPTIONS to port 8005 also returns 2xx with CORS headers — update verification.md Evidence Log row 2
- [x] 3.3 Verify Scenario 3 (auth not regressed): send `curl -X GET http://localhost:8001/api/v1/documents/test/text` without an Authorization header and confirm the response is 401 with `AUTH_ERROR` — update verification.md Evidence Log row 3
- [x] 3.4 Verify Scenario 4 (X-Request-ID on OPTIONS): inspect the OPTIONS response headers in DevTools for both ports and confirm `X-Request-ID` is present — update verification.md Evidence Log row 4

## 4. Verification & Evidence

- [ ] 4.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 4.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 4.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 4.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 4.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 4.6 Run `openspec validate fix-cors-preflight-middleware --type change --strict` and confirm it exits clean before archive.
