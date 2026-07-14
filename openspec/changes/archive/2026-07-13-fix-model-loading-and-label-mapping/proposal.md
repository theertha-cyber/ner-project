## Why

After promoting a fine-tuned model (v5) with custom entities (contact details, company, programming language), batch extraction only returns `B-MISC` — a label from the base model. The fine-tuned model's custom entities are never recognized. Two bugs cause this:

1. **S3 artifact path mismatch**: The training worker saves model artifacts to one path format, but the model loader expects a different format. The ONNX file is never found, so inference silently falls back to the base model.
2. **label_list never persisted**: Even if the model loads correctly, the label mapping is never stored in the DB. The inference service always resolves to the base model's CoNLL-2003 labels, so custom entity IDs map to wrong label names.

**Update (2026-07-13):** the same symptom — extraction only ever using the base v0 model — recurred after promoting a *later* model (v7), even though the path/label_list fixes above were already in place. Docker logs show:

```
Model warmup failed for tenant=4126ebb0-da07-4d09-bc46-df79c7c6933e version=7: All connection attempts failed
INFO:     172.18.0.1:40562 - "POST /api/v1/models/7/warmup HTTP/1.1" 200 OK
```

Investigation found two more, independent bugs in the cross-service routing between `model_serving` and `training_service`:

3. **`model_serving` resolves the active model version from the wrong port**: `inference_service.py`'s `_resolve_active_version()` and `_resolve_label_list()` both hardcode `http://training_service:8003/api/v1/models/active`. Port `8003` is the *host-mapped* port (`ports: "8003:8000"` in `docker-compose.yml`); inside the Docker network, `training_service` only listens on `8000` (per `local-dev-stack`'s "Application Service Port Mapping" and "Stable Inter-Service Communication via Docker DNS" requirements — every other inter-service call uses the container's internal port). Every call to this URL fails to connect; the `requests.RequestException` is caught and the function silently returns `("base", 0)`. This means **every** inference request resolves to the base model regardless of what's promoted — not intermittent, not tenant-specific, structural.
4. **`training_service` cannot reach `model_serving` to warm up a promoted model**: `docker-compose.yml`'s `training_service` block never sets `NER_MODEL_SERVING_URL` (every sibling service that calls `model_serving` — `gateway`, `chat_api`, `extraction_service` — does). `settings.model_serving_url` falls back to its bare-metal default `http://localhost:8004`, which resolves to nothing inside the `training_service` container, producing exactly the "All connection attempts failed" warmup failure seen in the logs.

Both new bugs are masked by the same pattern: the calling code catches the connection failure and degrades gracefully (log a warning, return a default) rather than surfacing it, so `/promote` and `/{version_id}/warmup` report `200 OK` even though the model was never actually loaded or ever will be resolved for inference.

**Update (2026-07-13, during apply-time verification):** after implementing and deploying bugs 3-4's fixes above, rebuilding `model_serving`/`training_service`, and confirming both directions of routing now work (`_resolve_active_version()` correctly resolves the promoted version; `training_service` successfully reaches `model_serving` for warmup), a real end-to-end `/internal/v1/infer` call for a tenant with a promoted model *still* returned `x-model-source: base`. Root cause was a fifth, more fundamental bug, same masking pattern:

5. **ONNX inference always sends an input the exported model doesn't have**: `training_service/worker.py`'s ONNX export (`torch.onnx.export(..., input_names=["input_ids", "attention_mask"], ...)`, line 342) deliberately produces a 2-input graph — no `token_type_ids`. This is the current, ongoing export convention, not a leftover from an old training run. But `model_serving/services/inference_service.py`'s `_infer_with_onnx()` unconditionally attaches `token_type_ids` to the `session.run()` call whenever the BERT tokenizer produces one (which it always does). Every single ONNX inference call against every fine-tuned model — past, present, and future — raised `onnxruntime.capi.onnxruntime_pybind11_state.InvalidArgument: Invalid input name: token_type_ids`, and `infer()`'s outer `except Exception` caught it and silently fell back to the base model. This is very likely the actual, deepest reason promoted models were never used for extraction: even with perfect routing (bugs 3-4 fixed), the ONNX call itself was structurally broken for every tenant, always.

This confirms the "silent graceful degradation masks a permanent misconfiguration" pattern goes three layers deep in this pipeline (routing → routing → ONNX input signature), not two.

**Update (2026-07-13, after user re-test on a freshly-trained v8):** the user trained and promoted another model and still saw `Model warmup failed for tenant=...version=8: ` (empty message) in the logs, despite all fixes above being live. Investigation found this one is not a routing or ONNX bug — it is a sixth issue, this time a timing issue:

6. **Cold model load can exceed the warmup call's client-side timeout, especially right after training**: `_warmup_model()` in `training_service/api/v1/models.py` uses `httpx.AsyncClient(timeout=30)` for the call to `model_serving`'s `/internal/v1/warmup`. A cold load (S3 download of model artifacts + `onnxruntime.InferenceSession` initialization) measured ~6-8 seconds in isolation, but the machine is still under load immediately after a training job finishes, and the observed failures correlate with promoting a model right after training completes. Critically, `model_serving`'s side of the load is **not cancelled** when the client times out — it keeps running in the background and the model does finish loading and gets cached; every follow-up check after a reported "failure" found the model already loaded and serving correctly. This means the "failed" log was a false negative on a self-healing condition, not a permanently broken promotion — but it's still misleading and worth widening the margin for.

**Fix:** increase `_warmup_model()`'s `httpx.AsyncClient` timeout from 30 to 90 seconds, giving cold loads under post-training system load much more room before the client gives up and logs a spurious failure.

(Separately, and not part of any of the six fixes: during reproduction testing this session, an agent action accidentally re-promoted an older model version by confusing the local `model_versions.version_number` numbering with MLflow's own registered-model version numbering — the two are not the same sequence, offset by 2 due to two early MLflow registrations that predate local DB tracking, and every promote/warmup/list endpoint in this codebase operates on MLflow's numbering. The user's intended model was restored to Production immediately after. No code change was made for this, since it isn't a bug in the running system — it only affected a manual reproduction step.)

## What Changes

- **Fix S3 artifact path alignment**: Ensure the training worker and model loader agree on the artifact path convention (`tenants/{tid}/models/v{version}/`). Either training saves to the expected path or the loader uses the path stored in the DB.
- **Persist label_list during training**: The training worker SHALL store the tenant's label list (e.g., `["O", "B-company", "B-contact_details", ...]`) in the `model_versions.metrics` JSONB column under the key `label_list`.
- **Resolve label_list at inference time**: The inference service SHALL read `label_list` from the active model API response and use it to map ONNX output indices to label strings, instead of falling back to CONLL_LABELS.
- **Use artifact_path from API**: The model loader SHALL use the `artifact_path` returned by the active model API rather than constructing its own path.
- **Fix `model_serving` → `training_service` routing**: Replace the hardcoded `http://training_service:8003` in `_resolve_active_version()` and `_resolve_label_list()` with a configurable `training_service_url` setting (mirroring `model_serving_url`, `extraction_service_url`, etc.), defaulting to the correct in-network port.
- **Fix `training_service` → `model_serving` routing for warmup**: Add the missing `NER_MODEL_SERVING_URL` environment variable to the `training_service` block in `docker-compose.yml`, matching every other service that calls `model_serving`.
- **Fix ONNX inference input mismatch**: `_infer_with_onnx()` SHALL only include `token_type_ids` in the ONNX Runtime input dict when the loaded session actually declares that input name (via `session.get_inputs()`), instead of unconditionally including it whenever the tokenizer happens to produce one.
- **Widen the warmup call's client-side timeout**: `_warmup_model()`'s `httpx.AsyncClient` timeout SHALL be increased from 30s to 90s to accommodate cold model loads occurring under post-training system load.

## Capabilities

### Modified Capabilities

- `training-worker`: Add requirement to persist `label_list` in model version metrics after training completes
- `model-serving`: Add requirement to resolve label_list from active model API and use it for ONNX index-to-label mapping; require model loader to use API-provided artifact_path; require the Model Registry URL used for active-version and label-list resolution to be configurable and to target the correct in-network port instead of a hardcoded host-mapped one
- `model-registry`: Ensure active model endpoint returns `label_list` in the response
- `local-dev-stack`: Extend "Stable Inter-Service Communication via Docker DNS" to cover `training_service` → `model_serving` (warmup) alongside the existing `celery_worker_extraction` → `document_service`/`model_serving` scenarios
- `model-serving`: Add requirement that ONNX inference inputs are built from the session's actual declared input names, not assumed unconditionally from tokenizer output

### New Capabilities

_(none — this is a bug fix, not a new feature)_

## Impact

- **Training worker** (`src/training_service/worker.py`): Must write `label_list` to `model_versions.metrics` after training
- **Model serving** (`src/model_serving/services/inference_service.py`, `src/model_serving/services/model_loader.py`): Must read `label_list` from API and use it for label mapping; must use API-provided `artifact_path`; must resolve the Model Registry (`training_service`) URL from settings instead of a hardcoded string
- **Model registry API** (`src/training_service/api/v1/models.py`): Must include `label_list` in the active model response
- **Shared config** (`src/shared/config.py`): Add a `training_service_url` setting (default `http://localhost:8003`, matching the existing `model_serving_url`/`extraction_service_url`/`document_service_url` pattern)
- **Docker compose** (`docker-compose.yml`): Add `NER_MODEL_SERVING_URL: "http://model_serving:8000"` to the `training_service` service block
- **Model serving ONNX inference** (`src/model_serving/services/inference_service.py:_infer_with_onnx()`): Must only pass `token_type_ids` to `session.run()` when the session declares it as an input, for every fine-tuned model version, not just the ones trained going forward
- **Existing trained models**: Models already trained without `label_list` in metrics will need a fallback (use base model labels or retrain)

## Decisions

- **Backfill strategy**: Migration script to backfill `label_list` in `model_versions.metrics` for existing completed/promoted model versions, using the tenant's `entity_definitions` table. No retraining needed.
- **S3 path format**: Fix the training worker to use `tenants/{tid}/models/v{version}/` (matching the spec and loader). The worker currently hardcodes `v1/` with a UUID subdirectory — this diverges from the spec. Existing v5 artifacts are already orphaned (never loadable), so no loss.
- **Registry URL configurability**: Add `training_service_url` to `Settings` rather than hardcoding the fixed correct port, so the value stays consistent with every other inter-service URL in the codebase and remains overridable for non-compose environments (bare-metal dev, tests). Bare-metal default is the host-mapped port (`8003`); `docker-compose.yml` overrides it to the container's internal port (`training_service:8000`) — the exact pattern already used for `model_serving_url`.
- **Keep graceful fallback, but only after fixing the URL**: The existing behavior of falling back to the base model / CONLL_LABELS when the registry call fails is preserved (transient outages should not break extraction). The bug was never in having a fallback — it was in the fallback firing on every single request because the target was structurally unreachable. No new alerting/observability requirement is introduced here; that's a separate concern if silent misconfiguration turns out to be a recurring risk.
