# Verification Plan

**Change:** fix-model-loading-and-label-mapping
**Generated:** 2026-07-09
**Updated:** 2026-07-13 — added scenarios 13-16 (model-serving ↔ training_service routing bugs found when v7 hit the same "base model only" symptom via a different root cause), scenarios 17-19 (ONNX `token_type_ids` input-signature bug found during live apply-time verification of 13-16 — the deepest of the three root causes, affecting every fine-tuned model regardless of routing correctness), and scenario 20 (warmup client timeout too tight for cold loads under post-training system load, found on user re-test with a freshly-trained v8). Scenarios 13, 15, 16, 17-19, and 20 verified live/standalone this session — see Evidence column.
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | training-worker | Save model artifacts | Artifacts are stored after training | Given a completed training run, when the worker saves the model and tokenizer, then model.safetensors, config.json, tokenizer.json, vocab.txt, training_args.json, metrics.json, and model.onnx exist at the artifact path, and the model_versions table has a new row with version_number, status "completed", and artifact_path | | - [ ] |
| 2 | training-worker | Save model artifacts | label_list is persisted in model version metrics | Given a completed training run with entity types ["company", "contact_details", "programming_language"], when the worker writes the model_versions row, then metrics.label_list contains ["O", "B-company", "I-company", "B-contact_details", "I-contact_details", "B-programming_language", "I-programming_language"], and the label_list includes all BIO tags extracted from the annotated dataset | | - [ ] |
| 3 | training-worker | Save model artifacts | Artifact path uses version number not UUID | Given a training run that produces version_number 5 for tenant "abc-123", when the worker saves artifacts to blob storage, then the artifact path is "tenants/abc-123/models/v5/", and the path does not contain a UUID subdirectory | | - [ ] |
| 4 | model-serving | Internal inference endpoint | Inference returns predictions from fine-tuned model with custom labels | Given a loaded fine-tuned model for the tenant with label_list ["O", "B-company", "I-company", "B-contact_details"], when POST to /internal/v1/infer with tokens ["Acme", "Corp"], then the response has status 200, contains predictions array with per-token label and confidence, labels use the tenant's custom entity types (e.g., "B-company") not CoNLL labels, and model_version is set to the promoted version number | | - [ ] |
| 5 | model-serving | Internal inference endpoint | Inference falls back to base model when no tenant model exists | Given a tenant with no promoted model version, when POST to /internal/v1/infer with tokens ["John", "works", "at", "Acme", "Corp"], then the response has status 200, contains predictions array with CoNLL labels (PER, ORG, LOC, MISC), and model_version is "0" | | - [ ] |
| 6 | model-serving | Internal inference endpoint | Inference falls back to base model when tenant model fails to load | Given a tenant with a promoted model version that fails to load, when POST to /internal/v1/infer, then the response has status 200, uses the base model, and contains a warning header indicating model load failure | | - [ ] |
| 7 | model-serving | Internal inference endpoint | Inference returns 403 when JWT is missing | Given no JWT token, when POST to /internal/v1/infer with tokens ["test"], then the response has status 403 | | - [ ] |
| 8 | model-serving | Model loader uses API-provided artifact path | Loader downloads from API-provided path | Given the active model API returns artifact_path "tenants/abc-123/models/v5/", when the model loader downloads artifacts, then the loader lists and downloads objects under the prefix "tenants/abc-123/models/v5/", and the loader does not use a different path format | | - [ ] |
| 9 | model-serving | Model loader uses API-provided artifact path | Loader handles missing artifacts gracefully | Given the API-provided artifact path exists but contains no ONNX file, when the model loader attempts to load the model, then the loader returns a failure status, and the inference service falls back to the base model | | - [ ] |
| 10 | model-registry | Get active model version | Get active model from MLflow when one is promoted | Given a tenant with model v2 in "promoted" status and metrics.label_list ["O", "B-company", "I-company"], when a Tenant Admin GETs /api/v1/models/active, then the response has status 200, contains the promoted model's version number, artifact path, metrics, and MLflow run URL, and contains label_list with the tenant's custom entity labels | | - [ ] |
| 11 | model-registry | Get active model version | Get active model when MLflow is unavailable | Given a tenant with a promoted model cached locally, when the MLflow Tracking Server is unreachable, then the proxy returns the active model from the local cache, the response has status 200, and the response includes a warning header | | - [ ] |
| 12 | model-registry | Get active model version | Get active model when none is promoted | Given a tenant with no promoted model, when a Tenant Admin GETs /api/v1/models/active, then the response has status 404, and the error indicates no active model exists | | - [ ] |
| 13 | model-serving | Model Registry URL is configurable and targets the correct in-network port | Registry URL is overridden to the Docker-internal port | Given NER_TRAINING_SERVICE_URL is set to http://training_service:8000, when model-serving resolves the active model version inside the Docker Compose network, then the request is sent to http://training_service:8000/api/v1/models/active, and the request successfully connects | Live: docker exec into model_serving-1 calling _resolve_active_version('4126ebb0-...') returned ('tenants/.../v1/599d.../', 5) — correct promoted version, not ('base', 0) | [x] |
| 14 | model-serving | Model Registry URL is configurable and targets the correct in-network port | Registry URL is read from settings, not hardcoded | Given _resolve_active_version() and _resolve_label_list() need to query the active model, when either function builds the request URL, then the URL is built from settings.training_service_url and no hardcoded host:port literal appears in inference_service.py | Code review: both functions now build registry_url from settings.training_service_url; tests/test_inference_endpoint.py::TestResolveActiveVersionUsesConfiguredRegistryUrl (3 cases) verified standalone | [x] |
| 15 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Training service reaches model_serving for warmup via service name | Given the training_service compose block has NER_MODEL_SERVING_URL=http://model_serving:8000, when training_service promotes a model version and calls the warmup endpoint, then the call resolves to the model_serving container without error | Live: promoted v5 via POST /api/v1/models/5/promote; POST /api/v1/models/5/warmup returned {"status":"ok","version_number":5} | [x] |
| 16 | local-dev-stack | Stable Inter-Service Communication via Docker DNS | Model serving reaches training_service via service name at the correct internal port | Given the model_serving compose block has NER_TRAINING_SERVICE_URL=http://training_service:8000, when model_serving resolves a tenant's active model version, then the call resolves to training_service at internal port 8000, not host-mapped port 8003 | Confirmed via docker logs: GET /api/v1/models/active arriving at training_service from model_serving's container IP (172.18.0.2) | [x] |
| 17 | model-serving | ONNX inference inputs match the loaded session's declared inputs | Inference succeeds against a 2-input ONNX export | Given a loaded ONNX session whose declared inputs are input_ids/attention_mask only, when _infer_with_onnx() runs and the tokenizer output includes token_type_ids, then token_type_ids is not sent to session.run(), and the call succeeds without falling back to the base model | tests/test_inference_endpoint.py::TestOnnxInputsMatchSessionSignature::test_inference_succeeds_against_2_input_onnx_export — passing (verified standalone); live end-to-end confirmed against tenant 4126ebb0's promoted v5: model_version="5", no x-model-source:base | [x] |
| 18 | model-serving | ONNX inference inputs match the loaded session's declared inputs | Inference succeeds against a 3-input ONNX export | Given a loaded ONNX session whose declared inputs include token_type_ids, when _infer_with_onnx() runs, then token_type_ids is sent to session.run(), and the call succeeds | tests/test_inference_endpoint.py::TestOnnxInputsMatchSessionSignature::test_inference_includes_token_type_ids_for_3_input_onnx_export — passing (verified standalone) | [x] |
| 19 | model-serving | ONNX inference inputs match the loaded session's declared inputs | A promoted model is actually used for extraction, not silently replaced by the base model | Given a tenant with a promoted, ONNX-loadable model version, when an extraction request is made, then model_version equals the promoted version number and the x-model-source:base header is absent | Live verification: promoted tenant 4126ebb0's v5, POST /internal/v1/infer returned model_version:"5", predictions present, no x-model-source header | [x] |
| 20 | model-warmup | Model warmup on promotion | A slow cold load that exceeds the client timeout still completes in the background | Given a tenant promotes a model version immediately after training finishes and the warmup call exceeds the client timeout, when model-serving continues loading in the background, then a subsequent warmup/extraction request finds the model already cached, and the promote response is still 200 | Live: user-reported "Model warmup failed for tenant=...version=8" during promote, but a follow-up POST /internal/v1/infer for that tenant returned model_version:"8" with real predictions — model had finished loading despite the reported client-side failure. Timeout widened 30s->90s to reduce recurrence. | [x] |

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | S3 path format | AI may use the old `v1/{uuid}/` format instead of `v{version}/` when fixing `_save_artifacts()`, or may not update the INSERT to compute version_number before saving | Verify `worker.py:_save_artifacts()` uses `f"tenants/{tenant_id}/models/v{version_number}/"` and that `version_number` is resolved from `MAX(version_number) + 1` before the artifact upload |
| 2 | label_list construction | AI may not include all BIO tags (missing I- prefixes) or may include "O" in the wrong position, or may sort labels differently than `_extract_label_set()` | Verify the label_list written to metrics matches the output of `_extract_label_set()` which returns `["O"] + sorted(non-O labels)` |
| 3 | Metrics dict mutation | AI may add label_list to metrics after the JSON dump, or may create a separate DB column instead of using the existing metrics JSONB | Verify `label_list` is added to the `metrics` dict before `json.dumps(metrics)` at line 396 of worker.py |
| 4 | Loader path parameter | AI may not change `download_model_artifacts()` to accept `artifact_path` as a parameter, or may add the parameter but not update the caller | Verify `model_loader.py:download_model_artifacts()` signature includes `artifact_path: str` parameter, and `inference_service.py:_load_model_for_tenant()` passes the API-provided path |
| 5 | Migration backfill correctness | AI may not join to entity_definitions correctly, or may use the wrong schema prefix for tenant-specific tables | Verify the migration queries `tenant_{tid}.entity_definitions` for each tenant and reconstructs the label list as `["O"] + sorted(["B-{entity}", "I-{entity}" for each entity])` |
| 6 | CONLL_LABELS fallback | AI may remove the CONLL_LABELS fallback entirely, breaking base model inference for tenants without a promoted model | Verify the fallback to CONLL_LABELS in `_resolve_label_list()` is preserved for the case where no label_list is in metrics |
| 7 | Training service URL setting | AI may hardcode the corrected port (`training_service:8000`) directly in `inference_service.py` instead of adding a proper `Settings` field, or may typo the field name so it silently falls back to a default | Verify `training_service_url` exists in `src/shared/config.py` with `env_prefix = "NER_"` (i.e. `NER_TRAINING_SERVICE_URL`), and that both `_resolve_active_version()` and `_resolve_label_list()` reference `settings.training_service_url` |
| 8 | Docker compose env vars | AI may add `NER_MODEL_SERVING_URL` or `NER_TRAINING_SERVICE_URL` to the wrong service block, or set the port to the host-mapped value (8003/8004) instead of the internal value (8000) | Verify `docker-compose.yml`: `training_service` block has `NER_MODEL_SERVING_URL: "http://model_serving:8000"`; `model_serving` block has `NER_TRAINING_SERVICE_URL: "http://training_service:8000"` — both using port `8000`, not `8003`/`8004` |
| 9 | ONNX input signature fix | AI may fix the symptom by hardcoding "never send token_type_ids" instead of checking the session's actual declared inputs, which would silently break any future model exported WITH token_type_ids | Verify `_infer_with_onnx()` calls `session.get_inputs()` and conditionally includes `token_type_ids` based on the result, not an unconditional removal; verify both the 2-input and 3-input test cases in `TestOnnxInputsMatchSessionSignature` pass |
| 10 | Warmup timeout widening | AI may pick an arbitrary or excessively long timeout, or change the wrong httpx.AsyncClient instantiation (there may be multiple in the file) | Verify the specific `httpx.AsyncClient` inside `_warmup_model()` (not e.g. an unrelated client elsewhere) now reads `timeout=90`, and that the warmup's graceful-degradation behavior (promote still returns 200 on failure) is unchanged |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-002 | All tenants fine-tune from dslim/bert-base-NER, no BYOM | Base model labels (CoNLL) are the fallback when no custom label_list exists | Verify CONLL_LABELS fallback is preserved in inference_service.py for tenants without a promoted model |
| ADR-003 | Shared serving pool with tenant-aware routing, version pinning | Model loader must resolve correct artifact path per tenant/version | Verify model_loader.py uses the API-provided artifact_path and does not construct its own path |
| `local-dev-stack` (main spec) | Stable Inter-Service Communication via Docker DNS — service-name hostnames at the internal port 8000 | `model_serving`'s call to `training_service` must not use the host-mapped port `8003` | Verify `inference_service.py` builds the registry URL from `settings.training_service_url`, and that the Docker override resolves to `training_service:8000` |

---

## 4. Evidence Requirements

### Functional Evidence

- [ ] Scenario 1: Test output showing training worker saves artifacts at correct path with all expected files
- [ ] Scenario 2: Test output showing model_versions row has metrics.label_list populated with correct BIO tags
- [ ] Scenario 3: Test output showing artifact path is "tenants/{tid}/models/v{N}/" without UUID
- [ ] Scenario 4: Test output showing inference returns custom entity labels (e.g., "B-company") not CoNLL labels
- [ ] Scenario 5: Test output showing base model fallback returns CoNLL labels when no promoted model
- [ ] Scenario 6: Test output showing base model fallback with warning header when model fails to load
- [ ] Scenario 7: Test output showing 403 returned when JWT is missing
- [ ] Scenario 8: Test output showing loader downloads from API-provided path
- [ ] Scenario 9: Test output showing loader returns failure when ONNX file missing, inference falls back
- [ ] Scenario 10: Test output showing active model response includes label_list from metrics
- [ ] Scenario 11: Test output showing local cache fallback with warning header when MLflow unavailable
- [ ] Scenario 12: Test output showing 404 when no promoted model exists
- [ ] Scenario 13: Test output showing model-serving successfully connects to training_service via NER_TRAINING_SERVICE_URL at the Docker-internal port
- [ ] Scenario 14: Code review / test output confirming no hardcoded training_service URL literal remains in inference_service.py
- [ ] Scenario 15: Docker log excerpt showing "Model warmup succeeded" for a promote call (not "All connection attempts failed")
- [ ] Scenario 16: Docker log or test output showing model_serving reaches training_service at port 8000, not 8003
- [ ] Scenario 17: Test output showing 2-input ONNX session inference succeeds without sending token_type_ids
- [ ] Scenario 18: Test output showing 3-input ONNX session inference sends token_type_ids
- [ ] Scenario 19: Live extraction response showing model_version equals the promoted version, no x-model-source:base header
- [ ] Scenario 20: Docker log / live test showing a promote's warmup call completing (or its background load finishing) within the widened timeout, and a live extraction confirming the promoted model serves correctly even after a reported warmup failure

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — S3 path format verified as v{version}/ not v1/{uuid}/
- [ ] Risk 2 mitigation confirmed — label_list includes all BIO tags with correct sorting
- [ ] Risk 3 mitigation confirmed — label_list added to metrics dict before JSON serialization
- [ ] Risk 4 mitigation confirmed — download_model_artifacts accepts artifact_path parameter
- [ ] Risk 5 mitigation confirmed — migration correctly joins to tenant entity_definitions
- [ ] Risk 6 mitigation confirmed — CONLL_LABELS fallback preserved for base model case
- [ ] Risk 7 mitigation confirmed — training_service_url is a proper Settings field (NER_TRAINING_SERVICE_URL), referenced by both _resolve_active_version() and _resolve_label_list()
- [ ] Risk 8 mitigation confirmed — docker-compose.yml env vars use port 8000 (internal), not 8003/8004 (host-mapped), on the correct service blocks
- [ ] Risk 9 mitigation confirmed — _infer_with_onnx() checks session.get_inputs() rather than unconditionally omitting token_type_ids
- [ ] Risk 10 mitigation confirmed — the correct httpx.AsyncClient (inside _warmup_model()) now uses timeout=90, and promote's graceful-degradation-on-failure behavior is unchanged

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| | | | | | |

---

## 6. Audit Record

**Change slug:** fix-model-loading-and-label-mapping
**Proposal:** `openspec/changes/fix-model-loading-and-label-mapping/proposal.md`
**Spec files reviewed:**
- specs/training-worker/spec.md
- specs/model-serving/spec.md
- specs/model-registry/spec.md
- specs/local-dev-stack/spec.md
- specs/model-warmup/spec.md

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
