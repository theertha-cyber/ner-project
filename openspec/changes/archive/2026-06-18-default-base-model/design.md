## Context

The platform uses `dslim/bert-base-NER` as its single curated base model (ADR-002). Currently, every tenant must complete annotation → training → promotion before extraction works. There is no fallback path. The `model-serving` inference service (`src/model_serving/services/inference_service.py:68-71`) returns `None` when `_resolve_active_version()` finds no promoted model. The `extraction-service` API (`src/extraction_service/api/v1/extraction.py:54-58`) turns this into HTTP 400. This means tenants cannot extract even standard CoNLL entities (PER, ORG, LOC, MISC) during onboarding, reducing the platform's immediate value.

## Goals / Non-Goals

**Goals:**
- Every tenant can extract entities immediately with no trained model, using `dslim/bert-base-NER` as the default
- Extraction responses indicate whether results come from the base model (v0) or a fine-tuned model
- The base model is lazy-loaded into the serving cache on first request per serving instance (not per tenant — the base model is shared)
- Model registry active endpoint returns base model metadata when no promoted version exists
- ADR-002 is amended to codify the base-as-default pattern

**Non-Goals:**
- Training the base model or fine-tuning it automatically — this is purely about inference fallback
- Changing the training pipeline — training still uses `dslim/bert-base-NER` as before
- Full BYOM support — this is explicitly not changing the base model strategy

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-002 | Single curated base model (`dslim/bert-base-NER`), no BYOM | The fallback model MUST be the same base model used for fine-tuning. No other base model is allowed. |
| ADR-003 | Shared serving pool with per-tenant routing, ONNX Runtime | The base model fallback MUST fit within the shared serving pool architecture. See Decision 3. |
| ADR-006 | Celery + RabbitMQ async GPU workers for training | Not directly constrained by this change (training is unchanged). |

## Decisions

### Decision 1: Base model as conceptual "version 0"

**Choice:** Treat the base model as version `0` for every tenant. The model registry represents it implicitly — the "active model" endpoint returns a synthetic entry for version 0 when no promoted version exists, with:
- `version_number: 0`
- `artifact_path: "base"`
- `label_list: ["O", "B-PER", "I-PER", "B-ORG", "I-ORG", "B-LOC", "I-LOC", "B-MISC", "I-MISC"]` (standard CoNLL-2003)
- `metrics: {}` (empty — no training metrics)

**Rationale:** Version 0 is intuitive (the starting point before any training). Using a synthetic entry means no database changes — the registry endpoint logic handles the fallback. The extraction service and worker can treat version 0 as a valid version without special-casing every guard.

**Alternatives considered:**
- Special sentinel string like `"base"` or `"dslim/bert-base-NER"` — Rejected because it would require string comparisons throughout the codebase instead of a simple `version_number > 0` check.
- Inserting a real database row per tenant — Rejected because it adds migration overhead and cleanup complexity. The base model exists before any tenant is provisioned.

### Decision 2: Hugging Face Transformers pipeline for base model inference (not ONNX)

**Choice:** Load the base model via Hugging Face Transformers `pipeline("ner", model="dslim/bert-base-NER")` for the fallback path, not ONNX Runtime.

**Rationale:**
- `dslim/bert-base-NER` is a production-tested model available on Hugging Face Hub with a ready-made token-classification pipeline
- No export step required — works immediately after `pip install` and first download
- The ONNX path is retained for fine-tuned tenant models (which are exported during training)
- The base model is shared across all tenants, so a single pipeline instance is cached at the service level, not per-tenant

**Alternatives considered:**
- Pre-export `dslim/bert-base-NER` to ONNX — Rejected because it adds a build step and the HF pipeline is fast enough for a fallback path. Can be optimized later if performance demands it.
- ONNX Runtime with the base model's ONNX export from Hugging Face Hub — Possible but the model is published as a Transformers model, not an ONNX model. Would need a conversion step.

### Decision 3: Shared base model pipeline (not per-tenant in cache)

**Choice:** The base model pipeline is held as a module-level singleton in the inference service, not in the per-tenant `ModelCache`. It is lazy-loaded on first fallback inference request.

**Rationale:** The base model is identical for all tenants. Storing it in the per-tenant LRU cache would create N copies (one per tenant) and risk eviction of the base model. A separate singleton ensures the base model is always available once loaded. The `ModelCache` continues to manage only fine-tuned tenant models.

**Alternatives considered:**
- Store base model in cache with fixed key `"__base__"` — Rejected because the cache has eviction and TTL policies that could remove the base model, causing re-loads.
- Pre-load base model at serving startup — Deferred to an Open Question. Lazy loading is simpler and avoids startup delay.

### Decision 4: `model_version` field in extraction response

**Choice:** Add an optional `model_version` field to `ExtractResponse`. It is `"0"` when the base model is used, or the actual version number (e.g., `"3"`) when a fine-tuned model is used.

**Rationale:** Consumers need to distinguish base-model output from trained-model output for trust and debugging. A string field handles both the `"0"` base case and arbitrary version numbers without type coercion issues.

## Risks / Trade-offs

- [Base model CoNLL labels (PER, ORG, LOC, MISC) may not match tenant-defined entity types] → The base model results are clearly tagged as `model_version: "0"`. Users see standard CoNLL labels rather than their custom labels. This is expected behavior for the fallback path.
- [Hugging Face pipeline may have different output format/speed vs ONNX Runtime] → The extraction service post-processing abstracts the difference. For high-throughput tenants, training a custom model is expected.
- [Base model download at first inference adds latency (cold start)] → Mitigated by lazy-loading and the fact that the base model is downloaded once per serving instance, not per tenant.
- [Tenant demotes their last model, falling back to base — users may not notice] → The `model_version` field in responses makes this explicit. Consider adding a UI indicator.

## Migration Plan

1. Add base model pipeline singleton to `inference_service.py` (lazy-loaded `_get_base_pipeline()`)
2. Modify `_resolve_active_version()` to return synthetic version 0 data when no promoted model exists
3. Modify `infer()` to call the base pipeline when version 0 is resolved
4. Update `model-registry` active endpoint to return base model metadata on 404
5. Update `ExtractResponse` schema to include `model_version` field
6. Update extraction API endpoint to populate `model_version`
7. Update batch extraction worker to handle version 0 (no model_version lookup needed)
8. Amend ADR-002
9. Update specs (model-serving, extraction-service, model-registry)

Rollback: Revert the inference service changes and registry endpoint changes. The extraction service will resume returning 400 for tenants with no promoted model.

## Open Questions

- Should the base model be pre-loaded at serving startup? (Current design: lazy on first request)
Answer: base model should be pre-loaded only if no other model exists or if no other model is promoted.
- Should we add a configuration flag to disable base model fallback (for stricter tenants)?
Answer: no need.
- Should ADR-002 be amended with a new superseding ADR, or should we create a separate ADR for the base-as-default pattern?
Answer: amend adr-002