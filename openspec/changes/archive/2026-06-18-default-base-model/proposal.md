## Why

Currently, extraction fails with HTTP 400 "No active model is available for this tenant" when no tenant-specific model has been trained or promoted. This blocks users from getting any value from the system during onboarding — they must first complete the annotation → training → promotion cycle before they can extract even standard entities (PER, ORG, LOC, MISC). The base `dslim/bert-base-NER` model can produce useful CoNLL entity predictions out of the box, and should serve as a default fallback.

## What Changes

- Model-serving layer falls back to the base `dslim/bert-base-NER` model (conceptually "version 0") when no tenant-promoted model exists
- Model registry returns base model metadata when no promoted version is active, rather than 404
- Extraction service no longer rejects requests when no trained model is promoted — it extracts using the base model with CoNLL labels
- Extraction results are tagged with a `model_version: "0"` or `model_version: "base"` to distinguish them from trained-model results
- A new ADR to codify the base-as-default pattern (amends ADR-002)

## Capabilities

### New Capabilities

(none — this change modifies existing capabilities)

### Modified Capabilities

- `model-serving`: Version resolution logic treats "no promoted model" as version 0 (base model). Inference endpoint returns base model predictions with CoNLL labels when no tenant model is promoted.
- `extraction-service`: The "no active model" error scenarios are replaced with base-model extraction behavior. Responses include `model_version` field to indicate whether results are from base (v0) or trained model.
- `model-registry`: Active model endpoint returns base model metadata (version 0, label list = CoNLL classes) when no promoted version exists, instead of 404.

## Impact

- **Model serving** (`src/model_serving/services/inference_service.py`): Add fallback path in `infer()` and `_resolve_active_version()` to return base model predictions when no tenant model is promoted.
- **Model loader** (`src/model_serving/services/model_loader.py`): May need to add capability to load/run base model via ONNX or Hugging Face pipeline.
- **Model cache** (`src/model_serving/services/model_cache.py`): May need to handle a shared base model entry (not tenant-specific).
- **Extraction API** (`src/extraction_service/api/v1/extraction.py`): Change error-returning paths to success paths with base model results.
- **Extraction worker** (`src/extraction_service/worker.py`): Handle base model version "0" gracefully — skip model version check or treat as valid.
- **Extraction schemas** (`src/extraction_service/api/v1/schemas.py`): Add `model_version` field to response schemas.
- **Model registry** (`training_service/api/v1/models.py` or registry layer): Active endpoint returns base model info when no promoted version exists.
- **Documentation**: ADR-002 amended with base-as-default amendment.

## Open Questions

- Should the base model be pre-loaded into the cache at serving startup (always available), or lazy-loaded on first tenant request?
Answer: base model should be preloaded only if no other model exists or if no other model is promoted.
- Should we export `dslim/bert-base-NER` to ONNX ahead of time, or run it via Hugging Face `pipeline` for the fallback path?
Answer: fallback
- What should the `model_version` field value be for base model results? "0", "base", or "dslim/bert-base-NER"?
Answer: "base"
- Should the base model label list be the standard CoNLL-2003 classes (PER, ORG, LOC, MISC) or a broader set?
Answer: standard classes
