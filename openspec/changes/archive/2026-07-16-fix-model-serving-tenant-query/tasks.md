## 1. Core Fix

- [x] 1.1 In `_resolve_active_version()` (`src/model_serving/services/inference_service.py:39`), add `params={"tenant_id": tenant_id}` to the `requests.get(registry_url, ...)` call
- [x] 1.2 In `_resolve_label_list()` (`src/model_serving/services/inference_service.py:197`), add `params={"tenant_id": tenant_id}` to the `requests.get(registry_url, ...)` call
- [x] 1.3 Rebuild and restart the `model_serving` Docker container: `docker-compose up -d --build model_serving`
- [x] 1.4 Update `fake_get` test helpers in `test_inference_endpoint.py` to accept `**kwargs` so the new `params` kwarg doesn't break tests
- [x] 1.5 Increase extraction engine timeout from 30s to 90s in `src/extraction_service/services/extraction_engine.py` to handle cold-start model downloads

## 2. Verification & Evidence

- [x] 2.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [x] 2.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [x] 2.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [x] 2.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [x] 2.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [x] 2.6 Run `openspec validate fix-model-serving-tenant-query --type change --strict` and confirm it exits clean before archive.
