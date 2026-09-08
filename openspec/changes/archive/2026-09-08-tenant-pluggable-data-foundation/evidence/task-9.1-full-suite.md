# Task 9.1 — full suite run

## Result

| Run | Command | Result | Wall time |
|---|---|---|---|
| Baseline (`main`, commit `ea95bb5`) | `pytest -q --continue-on-collection-errors` | 94 failed, 2185 passed, 33 skipped, 33 errors | 595s |
| Final (`feat/tenant-pluggable-data-foundation`, `5d6c8fe8`) | same, plus `--durations=25` | 91 failed, **2311 passed**, 33 skipped, 32 errors | 533s |

Both runs were taken with the **full docker compose stack up** — see "Environment" below, which
is the condition that makes the two comparable.

## Failing-set diff — the result that matters

`baseline_ids.txt` (129 entries) against `final_ids.txt` (125 entries):

```
=== NEW (failing now, not in baseline) ===
(none)
=== FIXED (in baseline, passing now) ===
ERROR  tests/test_training_jobs.py::TestUpdateJobProgress::test_update_with_none_metrics
FAILED tests/test_dashboard_summary.py::TestSystemAdminStats::test_stats_are_active_tenants_users_pending_approvals_training_running
FAILED tests/test_extraction_worker_normalization.py::TestWorkerNormalizesEntitiesOnIngest::test_batch_extraction_persists_normalized_entities
FAILED tests/test_training_jobs.py::TestModelVersionsStatusLifecycle::test_update_to_failed
```

**This change introduces no new failure.** The four that flipped to passing are in
`test_training_jobs.py`, `test_dashboard_summary.py`, and
`test_extraction_worker_normalization.py` — none of which this change touches. They are the
order- and shared-database-dependent cases already characterised in
`task-1.3-baseline-diff.md`, where isolating them gave an identical 10 failed / 94 passed on
both the clean tree and the changed tree. They are flake settling, not repairs.

Passing count rose by 126, which is this change's own verification suite.

## Every test this change owns passes

Grepping the failure list for the twelve files this change adds or edits — `test_content_store`,
`test_ingestion_boundary`, `test_pipeline_source_neutrality`, `test_ocr_media_type_resolution`,
`test_retention_lifecycle`, `test_document_provenance_migration`, `test_document_visibility`,
`test_tenant_integration_profile`, `test_tenant_credential_hygiene`, `test_document_ingestion`,
`test_document_content_hash`, `test_chunk_metadata_ingest` — returns nothing.

## Environment

The comparability of these two runs depends on one thing that is easy to get wrong, so it is
recorded here.

An earlier attempt at this run took **44+ minutes and was abandoned**. Docker Desktop had died
mid-session and only `postgres-test` and `minio` had been restarted; the other eighteen services
were down. Every test reaching a downed service got an immediate connection refusal that
`tenacity` then retried for up to `retry_max_total_seconds = 30.0`. The symptom was a process
consuming 141 seconds of CPU across 44 minutes of wall time with **zero** rows in
`pg_stat_activity` — blocked in backoff, not working. Its pass/fail set would have overstated
failures and was not comparable to the baseline.

Before the run recorded above, the full stack was brought up (`docker compose up -d`; redis
needed an explicit start after being SIGTERM'd, which had aborted gateway and portal) and all
eleven ports were probed open: 8000, 8001, 8002, 8003, 8004, 8006, 8007, 5000, 6379, 9000, 55432.

**Anyone reproducing this must bring the whole stack up first**, or the numbers will not match.

## Timing

Slowest cases, from `--durations=25`; nothing pathological:

| Time | Test |
|---|---|
| 35.51s | `test_document_service_storage_retry.py::test_ensure_bucket_raises_after_retry_bound_exhausted` (deliberately exhausts the retry bound) |
| 27.19s | `test_training_worker.py::TestOnnxIntegration::test_onnx_export_and_inference` |
| 10.48s | `test_tenant_provisioning.py::test_scenario_4_paginated_list` |
| 6.70s | `test_training_worker.py::TestMlflowModelLogging::test_mlflow_transformers_log_model_succeeds` |

Everything below that is under 5s. No test this change adds appears in the top 25.
