## Context

The training service's promote endpoint (`POST /api/v1/models/{version_id}/promote`) transitions a model from completed (MLflow Staging) to promoted (MLflow Production) and updates the local DB cache. The model-serving layer (SM-05) needs the newly promoted model pre-loaded into its in-memory cache so extraction requests after promotion have zero cold-start latency. Currently no warmup call exists — the first extraction request after promotion incurs a multi-second delay while model-serving downloads the ONNX model from blob storage and loads it into memory.

ADR-003 explicitly mandates "Model warmup after promotion (pre-load before marking active)" as a mitigation under Consequences.

## Goals / Non-Goals

**Goals:**
- Add a warmup endpoint to model-serving: `POST /internal/v1/tenants/{tid}/warmup`
- Modify the promote endpoint to call warmup synchronously after MLflow stage transition
- Graceful degradation: warmup failure logs the error but does not fail the promote (extraction falls back to on-demand loading)
- Configurable model-serving URL in training service env (`NER_MODEL_SERVING_URL`)

**Non-Goals:**
- Cache eviction on demote (demoted models remain cached until TTL or LRU eviction)
- Multi-node warmup propagation (single node warmup sufficient for MVP)
- Warmup progress reporting (fire-and-forget with timeout)
- GPU memory pre-allocation during warmup (ONNX Runtime handles this on first inference)

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant Data Isolation via Separate DB Schemas | Warmup must be scoped to a single tenant — no cross-tenant warmup |
| ADR-003 | Shared Model Serving Pool with Per-Tenant Routing | Model warmup on promotion is a required mitigation; internal endpoint format must follow `POST /internal/v1/tenants/{tid}/...` convention |
| ADR-005 | OpenCode Agent Boundaries | Training service and model-serving are separate agents; integration is via HTTP at the endpoint layer |
| ADR-006 | Training Infrastructure with Async GPU Workers | Artifact path convention `tenants/{tid}/models/v{version}/` — model-serving loads from this path |

## Decisions

### Decision 1: Synchronous warmup in promote endpoint

**Choice:** Add an HTTP call to model-serving's warmup endpoint in `models.py:promote_model()` after `mlflow_promote()` returns, before the promote API responds.

```python
# After mlflow_promote() succeeds:
if settings.model_serving_url:
    async with httpx.AsyncClient(timeout=30) as client:
        await client.post(
            f"{settings.model_serving_url}/internal/v1/tenants/{tenant_id}/warmup",
            json={"version_number": version_number},
        )
```

**Rationale:** Placing the call in the endpoint handler (not in `mlflow_registry.py`) preserves separation of concerns — `mlflow_registry` handles MLflow operations, the endpoint orchestrates cross-service calls. Synchronous ensures the promote API does not return until the model is loaded (zero cold-start for first extraction). The call is wrapped in a try/except so a warmup failure does not fail the promotion — the model will be loaded on-demand with cold-start latency.

**Alternatives considered:**
- Event-driven warmup via Redis pub/sub — more complex, requires async consumer, adds eventual consistency window where extraction could arrive before warmup completes
- Warmup in `mlflow_registry.py` `promote_model_version()` — mixes model-serving concerns into MLflow abstraction; `mlflow_registry` should not depend on model-serving

### Decision 2: Warmup endpoint accepts optional version_number

**Choice:** `POST /internal/v1/tenants/{tid}/warmup` accepts `{"version_number": <int>}`. If omitted, model-serving resolves the active (promoted) version from its own version-pinning cache.

**Rationale:** The promote endpoint passes the explicit version number for precision. A standalone warmup-only endpoint (without promotion) can omit the version and warm up whatever is currently active — useful for CI/CD or manual cache seeding.

**Alternatives considered:**
- Always warm up active version — forces model-serving to re-resolve, adds latency; passing version is zero-cost since promote already has it
- No warmup-only endpoint — SM-05 tasks only need promote warmup; but a standalone warmup endpoint is cheap to add (2 lines in router) and useful for operations

### Decision 3: Warmup failure is non-fatal

**Choice:** If the warmup HTTP call fails (timeout, connection refused, 5xx), log the error and return promote success. Extraction falls back to on-demand model loading with cold-start latency.

**Rationale:** The promote operation (MLflow stage transition + DB cache) is the source-of-truth operation. Warmup is an optimization. Failing promotion because model-serving is down would be worse — tenants could not promote models at all. The model-serving warmup endpoint is new and may not be available during phased rollout.

### Decision 4: Configurable model-serving URL via NER_MODEL_SERVING_URL

**Choice:** Add `NER_MODEL_SERVING_URL=http://model-serving:8004` to training service config. Default to `http://localhost:8004` for local dev.

**Rationale:** Follows the existing `NER_` prefix convention. The URL differs between Docker Compose (`http://model-serving:8004`) and local dev (`http://localhost:8004`). Making it configurable avoids hardcoding.

## Risks / Trade-offs

- [Model-serving not yet deployed when promote runs] → Warmup call fails silently (Decision 3); model loads on first extraction request with cold-start latency
- [Warmup timeout blocks promote for 30s] → If model-serving is slow, promote could be delayed. Mitigation: use a shorter warmup timeout (30s should be generous; typical ONNX load is 2–5s from local blob storage)
- [Warmup loads wrong version if model-serving version cache is stale] → Promote passes explicit version_number; model-serving loads exactly that version
- [Multiple concurrent warmups for different tenants] → Model-serving processes concurrently; LRU cache handles memory pressure naturally

## Migration Plan

1. Add `NER_MODEL_SERVING_URL` to `src/shared/config.py` and `.env.example`
2. Implement `POST /internal/v1/tenants/{tid}/warmup` in model-serving (SM-05 codebase)
3. Add warmup HTTP call in `models.py:promote_model()` after `mlflow_promote()` returns
4. Unit test: warmup call is invoked on promote
5. Unit test: warmup failure does not fail promote
6. Integration test: promote → warmup → verify model is cached (via subsequent infer call)

Rollback: Remove the warmup call from promote; warmup endpoint remains in model-serving but becomes a no-op.

## Open Questions

- Should warmup also trigger a health check on the loaded model (run a single inference with dummy input)? 
Answer: no — the model will be validated on first real inference request.
- Should we add a warmup-only public endpoint `POST /api/v1/models/{version_id}/warmup` in the training service? This is useful for operations but adds scope. 
Proposed: include it as a thin proxy that calls model-serving internal warmup — cheap to add, useful for manual cache seeding.
