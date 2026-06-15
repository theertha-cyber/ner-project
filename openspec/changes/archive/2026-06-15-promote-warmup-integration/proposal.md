## Why

SM-04 (mlflow-integration) modified the model registry to use MLflow as the source of truth for model version stages. SM-05 (Extraction Engine) needs a model warmup on promotion — the newly promoted model must be pre-loaded into the model-serving cache before the promote API returns, ensuring zero cold-start latency for the first extraction request after promotion. Currently the promote endpoint transitions the MLflow stage and updates the local DB cache, but does not trigger model-serving warmup. This change closes that integration seam.

## What Changes

- Add a `POST /internal/v1/tenants/{tid}/warmup` endpoint in model-serving that loads a model version into the in-memory cache
- Add a warmup call in the training service's `POST /api/v1/models/{version_id}/promote` after the MLflow promotion succeeds, making the promotion synchronous with model loading
- Handle warmup failures gracefully: log the error and return success (extraction falls back to on-demand loading with cold-start latency)
- Implement a companion `POST /api/v1/models/{version_id}/warmup` endpoint in the training service that external callers (e.g., CI/CD) can use to pre-warm the cache without promoting
- No breaking changes — API response shape unchanged, warmup is transparent to existing clients

## Capabilities

### New Capabilities

- `model-warmup`: Cache warming mechanism that pre-loads a promoted model into the model-serving inference cache before the promote API responds

### Modified Capabilities

- `model-serving` (in SM-05 change `sm-05-extraction-engine`): Add internal warmup endpoint `POST /internal/v1/tenants/{tid}/warmup`
- `model-registry` (in `openspec/specs/model-registry/spec.md`): Promote requirement updated to include synchronous cache warmup

## Impact

- **Training service** (`src/training_service/api/v1/models.py`): ~5 line addition after `mlflow_promote()` returns to call model-serving warmup endpoint
- **Model-serving** (new SM-05 service `src/model-serving/`): New endpoint `POST /internal/v1/tenants/{tid}/warmup` that loads the active model into cache
- **Configuration**: Model-serving URL must be configurable in the training service via env var (e.g., `NER_MODEL_SERVING_URL`)
- **No new dependencies**: Uses HTTP call (via httpx) — already in the project

## Open Questions

- Should the warmup endpoint accept an explicit `version_number` parameter, or always warm up the currently promoted model? 
Answer: accept optional version_number, default to active
- Should demote also trigger cache eviction? 
Answer: no — demoted model remains cached until evicted by TTL or LRU pressure
- What timeout should be applied to the warmup HTTP call? 
Answer: 30s — generous for loading a ~400MB model from blob storage
