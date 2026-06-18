## 1. Model Registry — Active Endpoint Base Model Fallback

- [x] 1.1 Modify the active model endpoint (`training_service/api/v1/models.py` or registry layer) to return base model metadata when no promoted version exists — `version_number: 0, artifact_path: "base", label_list: [CoNLL-2003 classes], metrics: {}`
- [x] 1.2 Add `X-Model-Source: base` response header when returning base model metadata
- [x] 1.3 Write tests for active model endpoint: returns promoted model when one exists, returns base metadata (v0) when none exists, returns base metadata when MLflow unavailable with no cached model

## 2. Model Serving — Base Model Fallback Inference

- [x] 2.1 Add `_get_base_pipeline()` singleton in `inference_service.py` that lazy-loads `pipeline("ner", model="dslim/bert-base-NER")` via Hugging Face Transformers (shared across all tenants, not in ModelCache)
- [x] 2.2 Modify `_resolve_active_version()` to return synthetic version 0 data `(artifact_path="base", version_number=0)` when the registry returns no promoted model
- [x] 2.3 Modify `infer()` to call `_get_base_pipeline()` when the resolved version is 0, converting the HF pipeline output to the standard predictions format with CoNLL labels
- [x] 2.4 Add error handling in `infer()` — if a fine-tuned model load fails, fall back to base model and include a warning header
- [x] 2.5 Update the infer endpoint response to include `model_version` field
- [x] 2.6 Write tests for base model fallback inference: returns CoNLL predictions with version 0 for tenants with no promoted model, returns fine-tuned model predictions with version number for tenants with promoted model, falls back gracefully on model load failure

## 3. Extraction Service — Updated Schemas and API

- [x] 3.1 Add `model_version: str` field to `ExtractResponse` schema in `extraction_service/api/v1/schemas.py`
- [x] 3.2 Update real-time extraction endpoint in `extraction.py` to populate `model_version` from the inference response and remove the `400` no-active-model error path
- [x] 3.3 Update batch extraction worker `worker.py` to handle version 0 — `_get_active_model_version` returns "0" when no promoted model exists, and extraction proceeds with the base model
- [x] 3.4 Add `model_version` field to batch run status schemas and persistence
- [x] 3.5 Write tests: extraction returns CoNLL entities with model_version "0" for tenants with no model, extraction returns entities with model_version for tenants with promoted model, batch extraction triggers with version 0, batch run status includes model_version

## 4. ADR — Amend ADR-002 with Base-as-Default Pattern

- [x] 4.1 Create a new ADR (ADR-008) that supersedes ADR-002's "no default" assumption, codifying that the base model is the default inference model (version 0) for any tenant without a promoted fine-tuned model

## 5. Verification & Evidence

- [ ] 5.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass
- [ ] 5.2 Collect functional evidence (test output / API trace / log) for each scenario — one entry per row in verification.md § Evidence Log
- [ ] 5.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register
- [ ] 5.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance
- [ ] 5.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required)
- [ ] 5.6 Run `openspec validate default-base-model --type change --strict` and confirm it exits clean before archive
