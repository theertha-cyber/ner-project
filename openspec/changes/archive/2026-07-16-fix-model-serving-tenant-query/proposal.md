## Why

After promoting a fine-tuned model with custom labels (company, institution, tools&framework, programming_language, degree, job_title, years_of_experience, contact_details), extraction always returns labels from the base CoNLL-2003 model (PER, ORG, LOC, MISC) — the custom model is never used. Docker logs show `GET /api/v1/models/active → 400 Bad Request` from the model-serving container.

Root cause: `model_serving`'s `_resolve_active_version()` and `_resolve_label_list()` create a `system_admin` JWT but do not pass `?tenant_id=<tid>` as a query parameter. The model-registry API requires `system_admin` callers to supply `tenant_id` explicitly (a deliberate design pattern shared across the training service API — see `training-jobs` spec). The missing parameter triggers HTTP 400, and both functions silently fall back to the base model / CoNLL labels.

This is distinct from the previously-fixed port-routing bug (archive `2026-07-13-fix-model-loading-and-label-mapping`): the URL now resolves correctly to the in-network port, but the auth handshake fails because the system_admin caller doesn't declare which tenant it's querying.

## What Changes

- **`_resolve_active_version()`**: Add `?tenant_id=<tid>` query parameter to the GET request to the training service's `/api/v1/models/active` endpoint.
- **`_resolve_label_list()`**: Same fix — pass `tenant_id` as query parameter.
- Both fallback-to-base paths remain unchanged (they only fire on genuine connection/timeout/HTTP errors, not structural misconfiguration).
- **Extraction engine timeout**: Increase the httpx client timeout from 30s to 90s in `extraction_engine.py` to accommodate cold-start model downloads (411 MiB from MinIO) when warmup hasn't pre-loaded the model.

## Capabilities

### New Capabilities

_(none — this is a bug fix)_

### Modified Capabilities

- `model-serving`: Add requirement that inter-service calls to the model registry as `system_admin` MUST include the `tenant_id` query parameter
- `model-registry`: No requirement changes (the endpoint already requires this)

## Impact

- **Model Serving** (`src/model_serving/services/inference_service.py`): Two one-line changes in `_resolve_active_version()` (line ~39) and `_resolve_label_list()` (line ~197) to add `params={"tenant_id": tenant_id}` to the `requests.get()` call.
- **Extraction Service** (`src/extraction_service/services/extraction_engine.py`): One-line change from `timeout=30` to `timeout=90`.

## Open Questions

- None. The fix is well-understood and the pattern is documented in the training-jobs spec.
