## Why

The mlflow-integration change (archived 2026-06-12) was implemented and unit-tested, but lacks a single comprehensive end-to-end test script that can be run on demand to verify the entire integration works correctly. Without such a script, regressions go undetected, onboarding new developers requires manual MLflow checks, and CI cannot gate on MLflow health. A single `pytest` target that exercises the full stack — MLflow server, model registry proxy, DB cache, tenant isolation, and failure paths — gives confidence that the integration is intact.

## What Changes

- **New**: A comprehensive test script `tests/test_mlflow_verification.py` that exercises every acceptance criterion from the mlflow-integration change's three specs (mlflow-infrastructure, training-worker, model-registry)
- **New**: A pytest marker `@pytest.mark.verification` and a Makefile / script entry point to run it
- **No BREAKING changes** — this is purely additive test coverage

## Capabilities

### New Capabilities

- `mlflow-verification-tests`: A comprehensive, single-command test suite that verifies the MLflow integration end-to-end. Covers MLflow server health, experiment/run lifecycle, parameter/metric/artifact logging, model registration and staging, model registry proxy CRUD with real MLflow, DB cache fallback on MLflow outage, tenant isolation via naming conventions, dual-write consistency (MLflow + DB), and failure-path handling. Gated behind `NER_MLFLOW_INTEGRATION_TESTS=1` to avoid running in environments without an MLflow server.

### Modified Capabilities

- _None — this change adds tests only, no requirement changes to existing capabilities._

## Impact

| Area | Impact |
|---|---|
| `tests/test_mlflow_verification.py` | New file (~300-400 lines) |
| `pyproject.toml` or `pytest.ini` | May add `verification` marker |
| MLflow server (local dev) | Must be running on port 5000 for these tests |
| PostgreSQL (test DB) | Must be running for DB cache verification |
| CI pipeline | New test target that requires MLflow service |

## Open Questions

- Should the verification script live as a standalone file or be merged into the existing `test_mlflow_integration_live.py`?
- Should it include a fixture that auto-starts the MLflow server via `docker compose` if it's not already running?
- What's the correct "all clear" signal — all tests pass, or a single combined assertion that summarizes health?
