## Context

The mlflow-integration change (archived 2026-06-12) added MLflow Tracking Server infrastructure, Training Worker integration with MLflow run logging, and a Model Registry proxy over the MLflow Registry API. Unit tests and mocked integration tests exist, but there is no single, comprehensive end-to-end test script that verifies the entire integration against a live MLflow server. This change fills that gap with a standalone verification test suite.

Existing test coverage:
- `tests/test_mlflow_registry.py` — 10 unit tests (mocked MLflow client)
- `tests/test_model_registry.py` — 15 API integration tests (mocked MLflow via monkeypatch)
- `tests/test_mlflow_integration_live.py` — 10 live integration tests (requires MLflow on :5000)

The gap: no single test target exercises the full stack — server health, experiment/run lifecycle, model registration, proxy CRUD, DB cache fallback, tenant isolation, and failure paths — all against a real MLflow server.

## Goals / Non-Goals

**Goals:**
- A single `pytest` target (`tests/test_mlflow_verification.py`) that exercises every acceptance criterion from the mlflow-integration change's specs
- Gated behind `NER_MLFLOW_INTEGRATION_TESTS=1` to avoid accidental runs without MLflow
- Covers all five layers: infrastructure health, training worker integration, model registry proxy, end-to-end lifecycle, and resilience
- Independent of the Celery stack — tests exercise the `mlflow_registry` module functions + direct `MlflowClient` calls, not the full training pipeline

**Non-Goals:**
- Replacing existing unit or API integration tests (these remain for fast CI feedback)
- Testing the actual HuggingFace training loop (that belongs in training-worker tests)
- Adding MLflow infrastructure changes or new features
- Testing the Model Serving Layer's model loading from MLflow-managed URIs

## Currently-In-Force ADRs

All ADRs are in "Proposed" status, not formally accepted. For a test-only change, no ADR imposes meaningful constraints on the design.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001 | Tenant data isolation via separate PostgreSQL schemas | Test must create/clean up tenant-scoped resources |
| ADR-002 | Single base model dslim/bert-base-NER | Tests reference `tenant_{tid}` naming convention |
| ADR-006 | Celery + RabbitMQ async GPU workers | Tests avoid Celery dependency — call mlflow_registry functions directly |
| ADR-008 | Base model as default (v0) when no active model | Tests verify base model fallback in get_active_model() |

## Decisions

### Decision 1: Standalone Test File (Not Merged Into Existing Tests)

**Choice:** Create `tests/test_mlflow_verification.py` as a new standalone file rather than merging into `test_mlflow_integration_live.py`.

**Rationale:** The existing live test file already has 10 tests covering basic MLflow client operations. The verification suite will be 3-4x larger and is conceptually different — it's a regression gate, not a development aid. Keeping them separate makes it easy to run just the verification gate in CI.

**Alternatives considered:**
- **Merge into existing file:** Would create a >400-line test file mixing basic client tests with comprehensive verification. Harder to maintain.
- **A script (not pytest):** Would lose pytest fixture infrastructure, parallelization, and reporting. Ruled out.

### Decision 2: Direct MLflow Client + Proxy Calls (Not Celery Task)

**Choice:** Tests exercise the `mlflow_registry` module functions (`list_model_versions`, `get_active_model`, `promote_model_version`, `demote_model_version`) and direct `MlflowClient` calls, not the Celery `fine_tune_model` task.

**Rationale:** Running the full Celery training task requires a GPU, a HuggingFace model download, and a real annotation dataset. That's impractical for a verification gate. The test script verifies the MLflow infrastructure and registry proxy independently, which is the integration surface that matters for regression detection. The training worker's MLflow integration is covered by unit tests with mocked datasets.

**Alternatives considered:**
- **Full Celery pipeline test:** Would need GPU, HuggingFace model, and annotation data. Too heavy for CI.
- **Synthetic training run with small model:** Possible but adds significant complexity and download time.

### Decision 3: Database Cache Fixture With Real PostgreSQL

**Choice:** Tests create tenant-specific PostgreSQL schemas and `model_versions` tables for verifying DB cache writes and reads, mirroring the existing pattern in `test_mlflow_integration_live.py`.

**Rationale:** The cache fallback is a critical resilience path. Testing it requires the real PostgreSQL schema to exist. Using an existing test DB (e.g., `ner_test` on port 54320 via the conftest defaults) avoids coupling to the main dev DB.

**Alternatives considered:**
- **In-memory SQLite for cache:** Would not match the production PostgreSQL schema. Risk of false positives.
- **Skip cache testing in verification:** Would leave a gap in regression coverage for the resilience path.

## Risks / Trade-offs

- [Test collides with concurrent runs using same tenant_id] → Each test generates a UUID-based tenant_id to avoid collisions. Fixture-level cleanup deletes experiments and registered models.
- [MLflow server not running when tests execute] → Guarded by `NER_MLFLOW_INTEGRATION_TESTS=1`. Tests fail fast with a clear error if MLflow is unreachable.
- [Slow test execution due to real MLflow API calls] → Each test creates/tears down its own resources. Total run time estimated at 15-30s for the full suite.
- [State leakage between test classes due to shared MLflow server] → Unique tenant_id per test function. The MLflow server is treated as a shared but isolated resource.

## Migration Plan

1. Create `tests/test_mlflow_verification.py` with the five test layers
2. Run the test suite against a local MLflow server (`docker compose up -d mlflow`)
3. Verify all tests pass
4. Document the test target and preconditions in `tasks.md` and `verification.md`

**Rollback:** Delete the test file. No production code changes mean no rollback risk.

## Open Questions

- Should the verification script include a `docker compose up -d mlflow --wait` auto-start fixture? Currently assumes the server is externally managed.
- Should CI run this as a separate job that starts MLflow via Docker Compose?
