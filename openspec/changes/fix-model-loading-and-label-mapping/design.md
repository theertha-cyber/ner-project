## Context

The NER pipeline has two bugs that prevent fine-tuned models from being used at inference time. After promoting a custom model (v5), batch extraction only returns `B-MISC` from the base model because:

1. The training worker saves artifacts to `tenants/{tid}/models/v1/{uuid}/` but the model loader downloads from `tenants/{tid}/models/v{N}/` — paths never match, ONNX never loads, inference falls back to base model.
2. The `label_list` (e.g., `["O", "B-company", "B-contact_details", ...]`) is never written to `model_versions.metrics`, so inference always resolves to `CONLL_LABELS` (base model labels). Even if the ONNX loaded, label indices would map to wrong names.

The `ModelVersionResponse` schema already declares `label_list: list[str] | None` and `_base_model_metadata()` already populates it for version 0. The contract is ready — the training worker just never fills it.

## Goals / Non-Goals

**Goals:**
- Align S3 artifact paths between training worker and model loader
- Persist `label_list` in `model_versions.metrics` during training
- Resolve `label_list` from the active model API at inference time (no CONLL fallback for fine-tuned models)
- Backfill `label_list` for existing completed/promoted model versions via migration

**Non-Goals:**
- Changing the model serving architecture (LRU cache, warmup, version resolution)
- Modifying the ONNX export format or model format
- Retraining existing models (migration handles backfill)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-002 | All tenants fine-tune from dslim/bert-base-NER, no BYOM | Base model labels (CoNLL) are the fallback when no custom label_list exists |
| ADR-003 | Shared serving pool with tenant-aware routing, version pinning | Model loader must resolve correct artifact path per tenant/version |
| `local-dev-stack` (main spec) | "Stable Inter-Service Communication via Docker DNS" — inter-service calls use Docker service names at the container's internal port (`8000`), never the host-mapped port | `model_serving`'s call to `training_service` must use `training_service:8000` in Docker, not the host-mapped `training_service:8003` |

## Decisions

### Decision 1: Fix training worker to use spec-compliant S3 path

**Choice:** Change `_save_artifacts()` to use `tenants/{tid}/models/v{version_number}/` format. The version_number will be determined after the INSERT (using the MAX(version_number) + 1 already computed) and the artifact_path stored in the DB will reflect this.

**Rationale:** The spec (`training-worker` line 91) and the model loader (`model_loader.py:19`) both expect `v{version}/`. The worker was the outlier with hardcoded `v1/{uuid}/`. Fixing the worker aligns two components (spec + loader) vs fixing the loader which would only align one.

**Alternatives considered:**
- Fix the loader to use `v1/{uuid}/` — rejected because the path convention is non-standard and the spec was written intentionally with `v{version}/`
- Pass artifact_path from DB to loader — partially addressed in Decision 3

### Decision 2: Store label_list in model_versions.metrics during training

**Choice:** After extracting `label_list` from the annotated dataset (line 216 of worker.py), add `"label_list": label_list` to the `metrics` dict that gets written to `model_versions.metrics` JSONB (line 355-360).

**Rationale:** The metrics JSONB column already stores per-run metrics. `label_list` is a per-run property (different training runs for the same tenant could have different entity sets). Storing it here requires no schema change. The inference service already reads `metrics.label_list` — it just always gets None today.

**Alternatives considered:**
- Add a `label_list` column to `model_versions` — rejected because JSONB is sufficient and avoids a migration for the column itself
- Store in MLflow only — rejected because MLflow may be unavailable and inference needs a fast local lookup

### Decision 3: Use artifact_path from API in model loader

**Choice:** Change `_load_model_for_tenant()` to accept and use the `artifact_path` returned by `_resolve_active_version()` instead of constructing its own path internally. The loader's `download_model_artifacts()` will take `artifact_path` directly.

**Rationale:** The `_infer_with_onnx()` function already retrieves `artifact_path` from `_resolve_active_version()` (line 82-83) but never passes it to the loader. This makes the loader path-redundant and fragile if training ever changes its path convention again.

**Alternatives considered:**
- Keep loader constructing its own path — rejected because it creates two sources of truth for the path

### Decision 4: Migration script to backfill label_list

**Choice:** Write a one-time Alembic migration that:
1. Queries all `model_versions` rows with `status IN ('completed', 'promoted')`
2. For each, joins to the tenant's `entity_definitions` table to reconstruct the label list
3. Updates the `metrics` JSONB to include `"label_list": [...]`

**Rationale:** Existing models (like v5) were trained before this fix. They have no `label_list` in metrics. Rather than retraining, we can reconstruct the label list from entity definitions which are the source of truth for what entities the tenant configured.

**Alternatives considered:**
- Retrain all models — rejected because it wastes GPU time and the entity definitions already capture the label set
- Inference-time fallback to entity definitions — rejected because it's fragile and adds a dependency on the annotation service at inference time

### Decision 5: Add `training_service_url` setting; fix hardcoded port in `model_serving`

**Choice:** Add `training_service_url: str = "http://localhost:8003"` to `Settings` (`src/shared/config.py`), and change `inference_service.py`'s `_resolve_active_version()` and `_resolve_label_list()` to build `registry_url` from `settings.training_service_url` instead of the hardcoded literal `"http://training_service:8003"`. `docker-compose.yml`'s `model_serving` block gets `NER_TRAINING_SERVICE_URL: "http://training_service:8000"` added.

**Rationale:** Every other cross-service call in the codebase (`model_serving_url`, `extraction_service_url`, `document_service_url`, `chat_api_url`, `analytics_service_url`) is a `Settings` field with a bare-metal `localhost:<host-port>` default, overridden in `docker-compose.yml` to the service name at the container's internal port `8000`. `training_service` was the one callee never given this treatment — it was hardcoded directly in `inference_service.py`, and hardcoded to the *wrong* port (`8003`, the host mapping, instead of `8000`, the internal listening port declared by `local-dev-stack`'s "Application Service Port Mapping" requirement and the service's own `command: uvicorn ... --port 8000`). Since nothing in the Docker network listens on `8003`, every `_resolve_active_version()`/`_resolve_label_list()` call fails to connect, and the existing `except requests.RequestException` silently returns `("base", 0)` / `CONLL_LABELS` — meaning inference has been resolving to the base model on every single request, not just for orphaned/mismatched artifacts.

**Alternatives considered:**
- Leave the URL hardcoded but fix only the port number — rejected because it perpetuates the inconsistency with every other inter-service call and leaves the value unoverridable for tests/bare-metal dev (tests already set `NER_MODEL_SERVING_URL`, `NER_TRAINING_SERVICE_URL` would need the same treatment for symmetry).
- Route through the gateway instead of calling `training_service` directly — rejected as out of scope; ADR-003 already establishes direct service-to-service calls for this kind of internal resolution, and changing the topology is a larger change than this bug fix warrants.

### Decision 6: Add missing `NER_MODEL_SERVING_URL` to `training_service` in `docker-compose.yml`

**Choice:** Add `NER_MODEL_SERVING_URL: "http://model_serving:8000"` to the `training_service` service block in `docker-compose.yml`, matching `gateway`, `chat_api`, and `extraction_service`.

**Rationale:** `training_service/api/v1/models.py`'s `_warmup_model()` already correctly reads `settings.model_serving_url` and already has a working try/except around the `httpx` call — the code path itself needs no change. The bug is purely a missing environment variable: without it, `settings.model_serving_url` falls back to its bare-metal default `http://localhost:8004`, which is unreachable from inside the `training_service` container, producing the `httpx.RequestError: All connection attempts failed` seen in the logs. This is the same class of gap `fix-worker-host-routing` (archived 2026-06-17) and `dockerize-backend-services` (archived 2026-06-18) fixed for `celery_worker_extraction` — `training_service` was simply missed when those changes went through the other services.

**Alternatives considered:**
- Change the code to hardcode `http://model_serving:8000` — rejected because it breaks bare-metal/non-compose dev, and every sibling service already solves this via the env-var-driven `Settings` pattern.

### Decision 7: Only send `token_type_ids` to ONNX Runtime when the session declares it

**Choice:** In `inference_service.py:_infer_with_onnx()`, read `session.get_inputs()` once per call and only add `token_type_ids` to the `inputs` dict passed to `session.run()` if `"token_type_ids"` is among the declared input names. Do not change the training worker's ONNX export.

**Rationale:** Discovered during apply-time end-to-end verification of Decisions 5-6: `training_service/worker.py`'s `torch.onnx.export()` call explicitly declares `input_names=["input_ids", "attention_mask"]` — a deliberate 2-input export, current for all training runs, not a leftover from an old convention. `_infer_with_onnx()` assumed a 3-input signature (`input_ids`, `attention_mask`, `token_type_ids`) whenever the tokenizer produced `token_type_ids` (which BERT tokenizers do by default), causing `onnxruntime.InvalidArgument: Invalid input name: token_type_ids` on every ONNX inference call for every fine-tuned model. `infer()`'s existing `except Exception` fallback caught this and silently served the base model — meaning the "still uses the base model" symptom this whole change targets had a structural cause in the inference path itself, independent of whether routing (Decisions 5-6) or artifact loading (Decisions 1, 3) were correct. Reading the session's actual declared inputs makes the code correct for both today's 2-input exports and any future export that does include `token_type_ids`, with no retraining required.

**Alternatives considered:**
- Change the training worker to also export `token_type_ids` as a third input — rejected as higher-risk (requires retraining every existing model to regenerate compatible ONNX artifacts) for no accuracy benefit; BERT's `forward()` already defaults `token_type_ids` to all-zeros when omitted, so the 2-input export is not itself a correctness bug.
- Wrap `session.run()` in a try/except that retries without `token_type_ids` on failure — rejected as slower (pays the exception cost on every request) and less explicit than just checking the declared input names once.

### Decision 8: Widen the warmup call's client-side timeout from 30s to 90s

**Choice:** In `training_service/api/v1/models.py`'s `_warmup_model()`, change `httpx.AsyncClient(timeout=30)` to `httpx.AsyncClient(timeout=90)`.

**Rationale:** Found when the user re-tested with a freshly-trained v8: `Model warmup failed for tenant=...version=8: ` (empty message, matching `httpx.RequestError`) appeared even with Decisions 5-7 all live and confirmed correct. A cold model load (S3 download + `onnxruntime.InferenceSession()` init) measured ~6-8 seconds on an idle system, but promoting a model happens immediately after training finishes, when the machine is still under load from that job — plausibly pushing the same cold load past 30 seconds. Critically, `model_serving`'s side of the load is not cancelled by the client giving up: every time this was checked after a reported "failure," the model had already finished loading and was serving correctly moments later. 90 seconds gives meaningfully more headroom for the post-training-load case while still being a bounded timeout (not infinite).

**Alternatives considered:**
- Make the model load itself faster/non-blocking (e.g., offload to a thread pool, pre-warm during training) — rejected for this change's scope; a concurrency test during investigation (4 simultaneous cold-load calls) showed model_serving already handles overlapping load requests without serializing to 4x the single-request time, so blocking-event-loop was ruled out as the mechanism. The actual slowdown is real system load right after training, which a longer timeout addresses directly without a riskier architectural change.
- Make the promote-triggered warmup fire-and-forget (don't await it at all) — rejected because `model-warmup`'s existing "Warmup is triggered on promotion" requirement specifies the promote endpoint SHALL wait for model-serving to confirm the model is loaded; removing the wait would be a larger behavior change than this fix warrants.

## Risks / Trade-offs

- [Existing models saved at `v1/{uuid}/` path are orphaned] → They were never loadable anyway (bug existed since training). After the fix, new training runs will save to the correct path. If a user needs the old model, they must retrain.
- [Migration backfill may not perfectly match original label_list] → Entity definitions are the source of truth for what was trained. If annotations used labels not in entity_definitions, the backfill could miss them. Mitigation: the migration can also scan existing training job annotations if available.
- [label_list in metrics JSONB has no schema enforcement] → Mitigated by the inference service gracefully falling back to CONLL_LABELS if label_list is missing or malformed.
- [Every prior inference request has been silently served by the base model] → Since `_resolve_active_version()` has been unreachable on every call (Decision 5), any tenant that believed they were getting fine-tuned predictions has actually been getting base CoNLL predictions since this code path was introduced. There is no data-integrity fix for past extractions; this is a forward-looking correctness fix. Worth flagging to affected tenants once deployed.
- [Fixing the URL surfaces a previously-silent connectivity dependency] → Once `_resolve_active_version()` can actually reach `training_service`, the model-serving layer becomes newly sensitive to `training_service` latency/availability on every inference request (it always intended to be, per ADR-003, but never actually was). Mitigated by the existing TTL-cacheable design already specified in `model-serving`'s "Version resolution with base fallback" requirement — no change needed here, just confirming it now matters.

## Migration Plan

1. Deploy the code changes (worker path fix, label_list storage, inference resolution)
2. Run the Alembic migration to backfill existing model_versions
3. Verify: query `model_versions` for any promoted version and confirm `metrics.label_list` is populated
4. Trigger a batch extraction for a tenant with a promoted model — should now use custom entities
5. Deploy the `training_service_url` setting + `inference_service.py` fix, and the `docker-compose.yml` env var additions (`NER_TRAINING_SERVICE_URL` on `model_serving`, `NER_MODEL_SERVING_URL` on `training_service`)
6. Verify: promote a model version, confirm the warmup log line reads "Model warmup succeeded" (not "failed: All connection attempts failed"), and confirm a subsequent extraction request returns the promoted version's custom labels, not CoNLL/`B-MISC`

**Rollback:** If the migration causes issues, the label_list can be removed from metrics JSONB via a down migration. Inference will fall back to CONLL_LABELS (current behavior). The routing fixes (Decisions 5-6) are additive env-var/config changes with no migration; reverting the code change or the compose env vars simply restores the prior (broken) behavior.

## Open Questions

None — all decisions resolved.

## Addendum 2 (found during exploration, 2026-07-13)

After the S3-path and label_list fixes above shipped, the same "always base v0" symptom recurred for a later promoted model (v7). The docker logs pointed at a connection failure during warmup, not a missing-ONNX or missing-label_list case. Investigating led to two further, independent bugs — see Decisions 5 and 6 above:

1. `inference_service.py` has hardcoded `http://training_service:8003` (host-mapped port) instead of the container-internal port `8000`, in both `_resolve_active_version()` and `_resolve_label_list()`. This is structural, not intermittent — it fails on every request, meaning no promoted model has ever actually been resolved for inference via this path.
2. `docker-compose.yml`'s `training_service` block never set `NER_MODEL_SERVING_URL`, so the warmup call after `/promote` (and the standalone `/{version_id}/warmup` endpoint) has always been reaching for `localhost:8004` from inside a container where nothing listens there.

Both failures were invisible from the API because the calling code in each direction catches the connection error and degrades gracefully (falls back to base model / logs a warning) rather than raising — exactly the kind of masking `model-warmup`'s "Warmup failure does not fail promote" requirement calls for by design, but it also means a permanent misconfiguration looks identical to a transient one from the outside. This addendum does not change that graceful-degradation behavior; it fixes the underlying misconfiguration so the fallback stops being the only path taken.

## Addendum 3 (found during apply-time verification, 2026-07-13)

After deploying Decisions 5-6 and confirming both routing directions worked (`_resolve_active_version()` correctly resolved a promoted tenant's version and artifact path; `training_service` successfully reached `model_serving` for warmup, evidenced by `GET /api/v1/models/active` requests arriving at `training_service` from `model_serving`'s container IP for the first time), a real `/internal/v1/infer` call for that tenant still returned `x-model-source: base` / `model_version: "0"`.

Root cause (Decision 7): the ONNX export in `training_service/worker.py` produces a 2-input graph (`input_ids`, `attention_mask` only), but `_infer_with_onnx()` unconditionally added `token_type_ids` whenever the tokenizer produced one. `onnxruntime` rejected every call with `InvalidArgument: Invalid input name: token_type_ids`, and the existing outer `except Exception` in `infer()` silently fell back to the base model. This affects every fine-tuned model, not just the one used for verification — it is very likely the deepest and most consequential of the three bugs found in this change, since it means no fine-tuned ONNX model could ever have served a real prediction through this path, independent of routing correctness.

After the fix (reading `session.get_inputs()` and conditionally including `token_type_ids`), a live end-to-end test — promote a completed model version, confirm warmup succeeds, call `/internal/v1/infer` for that tenant — returned `model_version: "5"` (the promoted version) with real ONNX-backed predictions, not the base model. Separately noticed but out of scope for this addendum: this particular test model's predictions came back as `CONLL`-style labels (e.g. `I-PER`) with confidence values above 1.0, which points to (a) `label_list` not having been backfilled for this specific model version, and (b) `_infer_with_onnx()` using raw logits as "confidence" rather than a softmax-normalized probability. Both are pre-existing, separate from the three routing/ONNX bugs this change addresses, and are not fixed here.

## Addendum 4 (found during user re-test, 2026-07-13)

With Decisions 5-7 deployed, the user trained and promoted a new model (v8) and still saw `Model warmup failed for tenant=...version=8: ` in the logs. This time it was not a routing or ONNX-signature issue (see Decision 8): a cold model load taking longer than the 30-second client timeout, most likely due to system load right after the training job that produced v8 had just finished. The model finished loading server-side regardless and was confirmed serving correctly (`model_version: "8"`) shortly after.

While reproducing this, an agent-side mistake temporarily promoted the wrong model version: the promote/warmup endpoints operate on MLflow's own registered-model version numbers, which are offset by 2 from the local `model_versions.version_number` column (two early MLflow registrations predate local DB tracking and have no local row). A reproduction call intended to target "the tenant's newest local version" was issued using the local numbering and landed on a different, older MLflow version, transitioning it to Production and demoting the user's actual v8 back to Archived. This was caught and corrected within the same session (v8 restored to Production, confirmed via direct inference). No code changes resulted from this — the version-numbering split itself is consistent and not a bug in the running system, it only tripped up a manual reproduction step. Worth noting for future troubleshooting: **always use the version number as displayed by the portal/API (MLflow's numbering) when manually calling promote/warmup/demote — it does not necessarily match `model_versions.version_number` in the local database.**

## Addendum (found during implementation)

Task 4.1/4.2 assumed the model-registry API already returned `label_list` correctly. Implementation revealed it did not, for two reasons:

1. `models.py:_row_to_response()` read `row.get("label_list")` — a top-level key that is never set on real (non-base) rows; `label_list` only ever exists nested under `metrics`.
2. `mlflow_registry.py`'s `get_active_model`/`list_model_versions`/`promote_model_version`/`demote_model_version` build their `metrics` dict from MLflow's `run.data.metrics`, which only holds values logged via `mlflow.log_metrics()` — numeric only. `label_list` is a list, so it can never round-trip through that path.

**Fix applied:** `worker.py` now also logs `label_list` as an MLflow *param* (`mlflow.log_param("label_list", json.dumps(label_list))`), following the same pattern already used for `artifact_path`. `mlflow_registry.py` gained a `_metrics_with_label_list()` helper that parses this param back out of `run.data.params` and merges it into the returned `metrics` dict for all four functions. `_row_to_response()` was fixed to read `label_list` from `metrics.get("label_list")`. This keeps MLflow as the source of truth on the reachable path and the local DB JSONB cache as the fallback path, consistent with Decision 2's rationale.
