# Tasks — cap-6-local-compose-delivery-migration-and-operational-evidence

## Task 1: Delivery-evidence pytest module

- [x] Create `tests/test_local_compose_delivery_evidence.py` (hermetic, no stack, no Azure):
  - [x] 1a. Migration chain: parse `revision`/`down_revision` across `alembic/versions/*.py`; assert linear chain 039 → 040 → 041 → 042 with a single head and no broken link.
  - [x] 1b. Additive-only: assert `upgrade()` bodies of 040/041/042 contain no drop-table/drop-column on pre-existing tables (downgrade-only DROPs permitted).
  - [x] 1c. Compose sequencing/readiness contract: parse `docker-compose.yml`; assert `db-init` runs `alembic upgrade head` before app start, every app service gates on `db-init: service_completed_successfully`, `postgres-test`/`redis` healthchecks exist, and data-source-touched services (gateway, chat_api, document_service, celery workers) carry the required `depends_on`.
  - [x] 1d. Declared-metric finite-label contract: assert families `ner_data_source_lifecycle_total`, `ner_data_source_tests_total`, `ner_blob_sync_total`, `ner_external_pg_query_total` are declared with the exact finite value sets (providers, actions, outcomes, reasons, triggers) and no `tenant_id`/entity-type label.
  - [x] 1e. Fixture direct-query performance check: 10 sequential `execute_external_query` calls against `FixtureExternalDatabase` (drift check + validation + execution); assert 0 errors and p95 end-to-end ≤ 10 s (dev operating target, not a production SLO).

## Task 2: Local delivery runbook

- [x] Create `docs/runbooks/tenant-data-sources-local-delivery.md`: rolling deployment sequence, migration order, health/readiness checklist with ports/URLs, safe-telemetry reference, compatible rollback/roll-forward procedure with the 30-minute dev target, explicit out-of-scope list (staging/prod/K8s/SLOs/RPO/RTO/TLS), and the Azure-deferred/inactive gate.

## Task 3: Live evidence and verification record

- [x] Run the new evidence module plus the CAP-2–CAP-4 regression modules; record totals.
- [x] Capture `docker compose ps`, per-service `/health`, `alembic heads`, and `telemetry_scan.py --dry-run` plus live `--skip-flow` output with exit code and record counts.
- [x] Perform a timed compatible-recovery exercise (restart one app service, restore to health-checked state on the system clock) and record start/end/elapsed in the runbook evidence section.
- [x] Fill `verification.md` Evidence Log rows; `openspec validate <slug> --strict` must pass.
