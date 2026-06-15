## Context

The platform currently plans a fully custom experiment tracking and model registry system: the training worker persists metrics directly to the `training_jobs` DB table, and a custom Model Registry service manages version lifecycle. This works but lacks experiment comparison capabilities, standardized model packaging, and a UI for browsing runs. MLflow is the de-facto standard in the ML ecosystem and provides all of these as off-the-shelf capabilities.

## Goals / Non-Goals

**Goals:**
- Replace the custom Model Registry's internal implementation with the MLflow Model Registry while keeping the same external API surface
- Add MLflow Tracking to the Training Worker so hyperparameters, metrics, and artifacts are logged to MLflow
- Deploy an MLflow Tracking Server as part of the platform infrastructure
- Establish a tenant isolation strategy that works with MLflow's single-tenant architecture
- Maintain backward compatibility for all existing Model Registry API consumers

**Non-Goals:**
- Changing the Model Serving Layer — it continues to load models from artifact URIs
- Hyperparameter tuning integration (e.g., Optuna + MLflow) — deferred
- Multi-tenant MLflow server — single shared instance with naming convention isolation
- Replacing the existing `training_jobs` metrics storage — it remains as a secondary/fallback

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant isolation via separate PostgreSQL schemas | MLflow tenant naming must not bypass schema isolation |
| ADR-002 | Single curated base model dslim/bert-base-NER | MLflow experiments always reference the same base model |
| ADR-003 | Shared model serving pool with tenant-aware routing | Model Registry must still expose `active` version endpoint for Serving Layer |
| ADR-004 | OpenSpec SDD governance gates | This change must follow proposal → design → specs → tasks → evidence |
| ADR-006 | Celery + RabbitMQ async GPU workers | MLflow logging runs inside the Celery worker task |
| ADR-007 | Chatbot RAG architecture | No direct constraint — chatbot queries extracted entities, not MLflow |

## Decisions

### Decision 1: MLflow Tracking Server — Standalone Deployment

**Choice:** Deploy a standalone MLflow Tracking Server with PostgreSQL backend store and S3 artifact store.

**Rationale:** A standalone server provides a shared tracking endpoint that all services (training worker, model registry proxy) can connect to. It gives us the MLflow UI for comparing runs at no additional build cost. The PostgreSQL backend store reuses the existing database infrastructure, and the S3 artifact store reuses the existing MinIO/S3 setup.

**Alternatives considered:**
- **Embedded Tracking (no server):** Each worker writes directly to the backend store without a server. Loses the UI and makes cross-tenant debugging harder. Ruled out because the UI is a primary benefit.
- **Managed MLflow (Databricks):** Zero operational overhead but couples us to Databricks. Ruled out for a greenfield project that should remain cloud-agnostic.

### Decision 2: Tenant Isolation via Naming Conventions

**Choice:** Single shared MLflow instance with tenant isolation enforced via naming conventions at the proxy layer and service-level access control.

```
experiment name:    tenant_{tid}
registered model:   tenant_{tid}_ner_model
artifact path:      s3://ner-platform/mlflow/<experiment_id>/<run_id>/artifacts
```

**Rationale:** Running one MLflow server per tenant would multiply operational cost without proportional benefit. Naming conventions provide logical isolation; the Model Registry proxy enforces that Tenant Admin A can only see/promote models in their tenant's namespace.

**Alternatives considered:**
- **One MLflow server per tenant:** Complete isolation but N x operational complexity. Ruled out for MVP — can revisit if a tenant requires air-gapped deployment.
- **MLflow's built-in experiment permissions:** MLflow Enterprise has this but the open-source version does not. The proxy layer must implement its own authorization.

### Decision 3: Model Registry Proxy — Keep External API, Replace Internal Implementation

**Choice:** The existing Model Registry API contracts remain unchanged. The implementation becomes a thin proxy over the MLflow Registry API.

**Status mapping:**

| Custom Status | MLflow Stage |
|---|---|
| `completed` | `Staging` |
| `promoted` | `Production` |
| `archived` | `Archived` |
| `training` | None (no registered model version yet) |

**Rationale:** All existing consumers (Serving Layer, Portal UI, Training Orchestrator) depend on the current API contracts. Changing the external API would require coordinated changes across multiple services. The proxy pattern decouples the migration from the consumers.

**Alternatives considered:**
- **Direct MLflow API consumption from Portal:** Would require Portal to know about MLflow's API. Tight coupling. Ruled out.
- **Replace the custom service entirely:** Simplest but breaks the existing spec contracts. Ruled out for backward compatibility.

### Decision 4: Manual MLflow Logging (Not Autolog)

**Choice:** Use explicit `mlflow.log_params()`, `mlflow.log_metrics()`, and `mlflow.log_model()` calls in the Training Worker rather than `mlflow.transformers.autolog()`.

**Rationale:** Autolog logs a broad set of metrics automatically, but the project needs specific control over what's logged (dataset version, entity config version, per-entity-type F1 scores). Manual logging ensures we only log what's needed and in the expected format.

**Alternatives considered:**
- **`mlflow.transformers.autolog()`:** Quick to set up but logs excessive detail and misses domain-specific metrics (per-entity-type F1, dataset version). Ruled out.
- **MLflow callback for HuggingFace Trainer:** A middle-ground — clean integration but still limited control over domain-specific metrics. Could be adopted later if manual logging becomes verbose.

## Risks / Trade-offs

- [Single shared MLflow instance is a failure blast radius for all tenants] → Deploy MLflow with PostgreSQL HA, regular backups, and health checks. Tenant impact limited to temporary loss of tracking UI/API — model serving is not affected.
- [MLflow version upgrades may break the proxy] → Pin MLflow version in dependencies. Test proxy against new MLflow versions in staging before upgrading.
- [Custom `model_versions` DB table drifts out of sync with MLflow Registry] → Keep the DB table as a read-through cache with the MLflow run ID as the source-of-truth key. A background sync job reconciles if needed.
- [Latency added by MLflow API calls in the training hot path] → MLflow logging is asynchronous (queued writes). The training worker's critical path (GPU compute) is not blocked.

## Migration Plan

1. Deploy MLflow Tracking Server in dev environment (Docker Compose)
2. Set up PostgreSQL backend store database and MinIO artifact bucket
3. Add `mlflow` dependency to `pyproject.toml`
4. Modify Training Worker to log params/metrics/model to MLflow during training
5. Build Model Registry proxy implementation against MLflow Registry API
6. Deploy and test against a dev tenant end-to-end
7. Write K8s manifests for the MLflow server
8. Integration test: submit training job → MLflow run created → model appears in Registry → promote via existing API → verify Serving Layer picks it up

**Rollback:** Keep the old `model_versions` DB table and direct S3 artifact storage intact. If MLflow integration fails, the Model Registry proxy falls back to the DB-backed implementation. The training worker's existing metrics persistence code path is not removed — only augmented.

## Open Questions

- Should the MLflow Tracking Server be exposed externally (with auth) or internal-only? Internal-only is safer for MVP; external access with JWT auth can be added if the Portal needs to embed the MLflow UI.
- What is the correct MLflow version to pin? Requires research on latest stable and compatibility with PostgreSQL backend store.
