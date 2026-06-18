## 1. Extraction Service — Remove `{tid}` from Endpoint URLs

- [ ] 1.1 Change `src/extraction_service/api/v1/extraction.py` — update router prefix from `/api/v1/tenants/{tid}` to `/api/v1`, remove `tid` parameter from `extract_entities()`, `trigger_batch_extraction()`, and `get_batch_status()` handler signatures, remove `tid != tenant_id` validation checks
- [ ] 1.2 Change `src/extraction_service/api/v1/entities.py` — update router prefix from `/api/v1/tenants/{tid}` to `/api/v1`, remove `tid` parameter from `list_entities()` and `patch_entity()` handler signatures, remove `tid != tenant_id` validation checks
- [ ] 1.3 Update `src/extraction_service/services/extraction_engine.py` — remove `tenant_id` from `_infer_url()` URL construction (URL becomes `/internal/v1/infer`), add JWT forwarding by reading `Authorization` header from the incoming request and passing it in the httpx call

## 2. Model Serving — Remove `{tid}` from Internal Endpoint URLs

- [ ] 2.1 Change `src/model_serving/api/v1/inference.py` — update router prefix from `/internal/v1/tenants/{tid}` to `/internal/v1`, remove `tid` parameter from `inference_endpoint()` signature, remove `tid != tenant_id` validation
- [ ] 2.2 Change `src/model_serving/api/v1/warmup.py` — update router prefix from `/internal/v1/tenants/{tid}` to `/internal/v1`, remove `tid` parameter from `warmup_endpoint()` signature, remove `tid != tenant_id` validation, remove the `tenant_id = getattr(request.state, ...)` inline (rely solely on middleware)

## 3. Callers — Update URL Construction

- [ ] 3.1 Update `src/extraction_service/worker.py` — change inference URL from `/internal/v1/tenants/{tenant_id}/infer` to `/internal/v1/infer` (JWT already forwarded, no change needed to auth)
- [ ] 3.2 Update `src/training_service/api/v1/models.py` (`_warmup_model`) — change warmup URL from `/internal/v1/tenants/{tenant_id}/warmup` to `/internal/v1/warmup` (JWT already forwarded, no change needed to auth)

## 4. Gateway — Update Extraction Proxy

- [ ] 4.1 Change `src/gateway/api/v1/extraction_proxy.py` — update router prefix from `/api/v1/tenants/{tid}` to `/api/v1`, remove `tid` parameter from all 5 proxy handler signatures (`proxy_extract`, `proxy_batch`, `proxy_batch_status`, `proxy_list_entities`, `proxy_patch_entity`), update downstream URL construction to omit `/api/v1/tenants/{tid}` prefix

## 5. Tests — Update Test URL Paths

- [ ] 5.1 Update all test files that reference old extraction endpoint URLs (`/api/v1/tenants/{tid}/extract`, `/api/v1/tenants/{tid}/extract-batch`, `/api/v1/tenants/{tid}/entities`) to use new paths without `{tid}`
- [ ] 5.2 Update all test files that reference old model serving internal URLs (`/internal/v1/tenants/{tid}/infer`, `/internal/v1/tenants/{tid}/warmup`) to use new paths without `{tid}`
- [ ] 5.3 Update test for extraction_engine.infer() — verify Authorization header is forwarded (add mock assertion)
- [ ] 5.4 Update gateway proxy tests — verify requests go to correct downstream paths without `{tid}`
- [ ] 5.5 Write or update test to confirm 403 is returned when no JWT provided on new endpoint URLs

## 6. Documentation

- [ ] 6.1 Update `README.md` — change all extraction endpoint paths from `/api/v1/tenants/{tid}/...` to `/api/v1/...`, change all model serving paths from `/internal/v1/tenants/{tid}/...` to `/internal/v1/...`

## 7. ADR — Record Endpoint URL Change

- [ ] 7.1 Create new ADR at `docs/adr/009-endpoint-tenant-id-resolution.md` that supersedes ADR-003's endpoint URL specification, documenting the decision to resolve tenant_id exclusively from JWT rather than URL path

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 8.6 Run `openspec validate remove-tid-from-url --type change --strict` and confirm it exits clean before archive.
