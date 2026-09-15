# Bugs: Tenant Self-Service Data Sources

Known defects and review concerns for the tenant self-service data sources feature
(requirement: [`docs/requirement/tenant-self-service-data-sources.md`](../requirement/tenant-self-service-data-sources.md);
decomposition: [`docs/decomposition/02-tenant-self-service-data-sources.md`](../decomposition/02-tenant-self-service-data-sources.md);
ADR-011 to ADR-014).

**How to maintain this file:** one section per bug. Tick a task when it is done. Update **Status** when the bug moves on
(`Open` → `In progress` → `Fixed` → `Verified`). Add new bugs at the bottom with the next ID. Do not delete fixed bugs;
they are the history.

| ID | Title | Severity | Status | Found |
|----|-------|----------|--------|-------|
| [DS-001](#ds-001-last-run-status-never-updates) | Last-run status never updates | High | Fixed (API verified live; portal check pending) | 2026-09-11 |
| [DS-002](#ds-002-portal-shows-internal_error-for-every-data-source-error) | Portal shows `INTERNAL_ERROR` for every data-source error | High | Fixed (API shape verified live; portal check pending) | 2026-09-11 |
| [DS-003](#ds-003-blob-sync-scheduler-appears-stuck) | Blob sync scheduler appears stuck | High | Verified (stall alert still to add) | 2026-09-11 |
| [DS-004](#ds-004-gateway-blocks-its-event-loop-while-enqueuing-a-manual-sync) | Gateway blocks its event loop while enqueuing a manual sync | Medium | Open | 2026-09-11 |
| [DS-005](#ds-005-gateway-had-no-celery-broker-configured) | Gateway had no Celery broker configured | High | Verified | 2026-09-11 |
| [DS-006](#ds-006-blob-sync-containers-download-the-tokenizer-at-startup-and-die-if-it-fails) | Blob sync containers download the tokenizer at startup and die if it fails | High | Open | 2026-09-11 |
| [DS-007](#ds-007-blob-sync-ocr-tests-fail-on-a-stale-test-fixture-schema) | Blob sync OCR tests fail on a stale test-fixture schema | Medium | Open | 2026-09-11 |

---

## DS-001: Last-run status never updates

- **Severity:** High
- **Status:** Fixed 2026-09-11 (tests pass; live check pending)
- **Found:** 2026-09-11, while implementing OpenSpec change `manual-blob-sync-trigger`
- **Affects:** portal connection detail view ("Sync activity" panel), `GET /api/v1/data-sources/{id}`

**What happens.** The connection response always returns `last_sync: {"outcome": "never_run", "completed_at": null}`.
`to_connection_dict` in [`src/shared/data_sources/store.py`](../../src/shared/data_sources/store.py) hard-codes it and never
reads the real run history (`read_sync_status` in [`src/document_service/blob_sync/sync.py`](../../src/document_service/blob_sync/sync.py)).

**Effect.** After a successful "Sync now" the portal shows "Sync queued", but:

- the "Last run" line never changes;
- the "Sync already running" notice (lease-held) can never appear;
- spec rows 12 and 15 of `manual-blob-sync-trigger` pass in Vitest only because the tests mock the response.

**Workaround.** To confirm a run happened, query the tenant's run ledger directly, e.g.:

```sql
SELECT trigger, outcome, reason, objects_seen, objects_ingested, started_at, completed_at
FROM tenant_d2eb33ab_68f1_4e67_a841_f040f7eaf233.azure_blob_sync_runs
ORDER BY started_at DESC LIMIT 5;
```

A new `manual` row means the trigger worked.

**Tasks**

- [x] Decide whether this needs an OpenSpec change: no. The `last_sync` shape is unchanged (only real values now), and `manual-blob-sync-trigger` spec rows 12 and 15 depend on it, so the fix ships with that change
- [x] Populate `last_sync` from the tenant's latest *completed* `azure_blob_sync_runs` row (`service.latest_sync_outcomes`); runs still in progress and outcomes outside the finite set are skipped; a tenant without sync tables reads `never_run` (checked with `to_regclass`, no DDL on the read path)
- [x] One ledger query per request for any number of connections (`DISTINCT ON (connection_id)`); every gateway route that returns a connection goes through `_render`/`_render_many`, so mutation responses don't reset the portal cache to `never_run`
- [x] Added `lease_held` to `lc.SYNC_OUTCOMES`
- [x] Backend test `test_connection_reports_latest_completed_sync_run` (detail, list, and a mutation response all report the newest finished run)
- [x] Live API check (2026-09-11, rebuilt gateway): `GET /api/v1/data-sources/a484a121…` and the list both return `last_sync: {"outcome": "succeeded", "completed_at": "2026-09-11T09:20:39.374863+00:00"}`, matching the newest completed ledger row (`manual`, succeeded, 09:20:39)
- [ ] Live portal check: "Sync now" followed by a refresh shows the new last run in the portal (user to check)
- [ ] Consider one delayed refetch after "Sync now": the immediate refresh usually shows the *previous* run because the worker hasn't finished yet, so "Sync already running" only appears if the worker records lease-held before the refetch (no polling per design Decision 4)

**Side note.** Two `manual` rows in the ledger above have `completed_at` earlier than `started_at`
(started 06:21 and 05:53, both completed 06:05:43). Check whether the run-finish write reuses a stale timestamp.

- [ ] Investigate `completed_at` < `started_at` on manual runs

---

## DS-002: Portal shows `INTERNAL_ERROR` for every data-source error

- **Severity:** High
- **Status:** Fixed 2026-09-11 (tests pass; live check pending). Fixed in this session instead of the separate task.
- **Found:** 2026-09-11
- **Affects:** every data-source mutation in the portal (create, update, test, activate, pause, replace, retire, sync, contracts)

**What happens.** `parseSafeError` in [`src/portal/src/lib/data-sources.ts`](../../src/portal/src/lib/data-sources.ts) reads
`code`, `message`, and `request_id` from the top level of the response body. The gateway
(`_error` in [`src/gateway/api/v1/data_sources.py`](../../src/gateway/api/v1/data_sources.py)) nests them:
`{"error": {"code", "message", "request_id"}}`. `authFetch` does not unwrap it.

**Effect.** Refusals such as a paused connection (`INACTIVE_CONNECTION`), `TEST_REQUIRED`, or `SYNC_UNAVAILABLE` most likely
render as `INTERNAL_ERROR`. Portal tests don't catch it because their mocks use the top-level shape.

**Tasks**

- [x] Confirm against real gateway code: `_error` in `data_sources.py` and `external_pg_contracts.py` (which also nests `reason` and `field_errors`) and `app_error_handler` in `src/gateway/main.py` all return `{"error": {...}}`; FastAPI's `HTTPException` (401/403 from `require_tenant_admin`) returns `{"detail": ...}`
- [x] `parseSafeError` reads `body.error` first and falls back to a top-level envelope; framework 401/403 map to `UNAUTHENTICATED` / `FORBIDDEN` without echoing `detail`
- [x] Switched tests to the nested envelope: `data-sources.test.ts` (plus new nested and 401/403 cases), `use-data-sources.test.tsx`, `sync-activity.test.tsx`, `schema-contracts/page.test.tsx`
- [x] Live API check (2026-09-11, rebuilt gateway): an unknown connection returns `404 {"error": {"code": "CONNECTION_NOT_FOUND", "message": ..., "request_id": ...}}`, the nested shape the new parser reads
- [ ] Live portal check: pausing a Blob connection and triggering a sync shows `INACTIVE_CONNECTION` (user to check; pausing changes real connection state)

---

## DS-003: Blob sync scheduler appears stuck

- **Severity:** High
- **Status:** Verified 2026-09-11 (fix deployed; scheduled runs resume. Follow-up: a signal that catches a silent stall)
- **Found:** 2026-09-11, about 08:20 UTC
- **Affects:** scheduled and catch-up Azure Blob sync (`celery_beat_blob_sync`, `celery_worker_blob_sync`)

**What happens.** For the active Blob connection `a484a121-7318-4de9-b634-b23d7c1a4dc9` (tenant
`d2eb33ab-68f1-4e67-a841-f040f7eaf233`), the newest run was a `scheduled` run at 06:25 UTC. Nothing was recorded in the
~2 hours after that, although the cadence is 15 minutes. `celery_beat_blob_sync` had been up the whole time.

**Root cause (confirmed 2026-09-11 from logs).** Beat publishes `blob_sync_tick` every 60 s, but
[`src/document_service/blob_sync/tasks.py`](../../src/document_service/blob_sync/tasks.py) set no route for it, so it went to
Celery's default `celery` queue (`'routing_key': 'celery'`). The general-purpose `celery_worker` consumes that queue, does not
know the task, and drops it:

```
Received unregistered task of type 'blob_sync_tick'.
The message has been ignored and discarded.
```

The `celery_worker_blob_sync` worker only consumes `-Q blob_sync`, so no tick ever ran and no scheduled or catch-up sync
was enqueued. (`enqueue_sync` passed `queue=` explicitly, which is why manual runs still worked.)

**Fix.** `celery_app.conf.task_routes` now routes both `blob_sync_run` and `blob_sync_tick` to `blob_sync`.

**Tasks**

- [x] Find where `blob_sync_tick` is published (`celery_worker` log: unregistered task, routing key `celery`)
- [x] Route `blob_sync_tick` and `blob_sync_run` to `blob_sync` via `task_routes` in `tasks.py`
- [x] Add regression test `tests/test_blob_sync_task_routing.py` (routes resolve to `blob_sync`; beat schedules the tick)
- [x] Rebuild and recreate `celery_beat_blob_sync` and `celery_worker_blob_sync` (both then exited at startup: see DS-006)
- [x] Live check: `celery_worker_blob_sync` logged `blob_sync_tick` received and succeeded at 09:04:48 UTC (`{'enqueued': []}`: not due yet, the last run was 08:55); zero unregistered-task errors in `celery_worker` since the restart
- [x] Live check: the tick at 09:11:48 UTC enqueued `a484a121…`; a `scheduled` run started 09:11:48, `succeeded` (2 seen, 0 ingested)
- [ ] Add a health signal (metric or alert) that would catch a silent scheduler stall

---

## DS-004: Gateway blocks its event loop while enqueuing a manual sync

- **Severity:** Medium (review concern)
- **Status:** Open
- **Found:** 2026-09-11, while implementing `manual-blob-sync-trigger`
- **Affects:** `POST /api/v1/data-sources/{id}/sync` and, when Redis is down, the whole gateway

**What happens.** `request_manual_sync` (`src/shared/data_sources/service.py`) calls the enqueue seam `_enqueue_blob_sync`,
which calls Celery's synchronous `send_task`, directly inside the async route handler.

**Effect.** With Redis healthy this takes milliseconds. With Redis down, Celery retries the publish and the gateway's
event loop is blocked for the whole retry window, so every request to the gateway stalls, not just the sync.

**Tasks**

- [ ] Raise in code review for `manual-blob-sync-trigger`
- [ ] Run the enqueue off the event loop (e.g. `run_in_threadpool` / `asyncio.to_thread`)
- [ ] Bound the publish retry (short timeout, limited retries) so the route fails fast with `SYNC_UNAVAILABLE`
- [ ] Test: a slow or failing enqueue does not block a concurrent request

---

## DS-005: Gateway had no Celery broker configured

- **Severity:** High
- **Status:** Verified (manual sync reached the worker on 2026-09-11)
- **Found:** 2026-09-11, while preparing live verification of `manual-blob-sync-trigger`
- **Affects:** `POST /api/v1/data-sources/{id}/sync` in the local Compose stack

**What happened.** The `gateway` service in `docker-compose.yml` had no `NER_CELERY_BROKER_URL`, so `settings.celery_broker_url`
fell back to `redis://localhost:6379/0`. Nothing listens there inside the gateway container, so a manual sync would most
likely have failed with `SYNC_UNAVAILABLE` (503), after blocking the gateway (see DS-004). Unit tests could not catch it
because they replace the enqueue seam with a fake.

**Tasks**

- [x] Add `NER_CELERY_BROKER_URL` and `NER_CELERY_RESULT_BACKEND` (`redis://redis:6379/0`) to the gateway `environment` in `docker-compose.yml`
- [x] Rebuild and recreate `gateway`, `portal`, `celery_worker_blob_sync`; confirm the gateway container shows `redis://redis:6379/0`
- [x] Live check: a new `manual` row (`succeeded`, started 2026-09-11 08:55:55 UTC) appeared in `azure_blob_sync_runs` after the rebuild, so the gateway now reaches the broker
- [ ] Check other deployment manifests (`docs/deploy/`, Kubernetes) set the broker for the gateway too

---

## DS-006: Blob sync containers download the tokenizer at startup and die if it fails

- **Severity:** High
- **Status:** Open
- **Found:** 2026-09-11, after recreating `celery_beat_blob_sync` and `celery_worker_blob_sync` for DS-003
- **Affects:** every container whose startup imports `src.shared.retrieval` (blob sync worker and beat here; likely other services too)

**What happens.** Importing `src.document_service.blob_sync.tasks` pulls in
`blob_sync` → `sync` → `ingestion` → `ocr_worker` → `src.shared.retrieval.chunking`, which runs
`TOKENIZER = tiktoken.get_encoding("cl100k_base")` at module level
([`src/shared/retrieval/chunking.py:5`](../../src/shared/retrieval/chunking.py)). tiktoken downloads the ~1.7 MB BPE file over
the internet on first use and caches it inside the container, so a freshly created container downloads it again. On
2026-09-11 the download broke off:

```
requests.exceptions.ChunkedEncodingError: ('Connection broken: IncompleteRead(1326682 bytes read, 354444 more expected)', ...)
```

Both containers exited with code 2. Compose sets no restart policy for them, so they stayed down: no manual or scheduled
sync could run until someone noticed.

**Tasks**

- [ ] Pre-download the `cl100k_base` encoding at image build time (set `TIKTOKEN_CACHE_DIR` in the `Dockerfile` and warm it with `tiktoken.get_encoding`) so startup needs no internet
- [ ] Consider loading the tokenizer lazily instead of at import, so a missing file fails the chunking call, not the whole worker
- [ ] Add `restart: unless-stopped` (or similar) to `celery_worker_blob_sync` and `celery_beat_blob_sync` in `docker-compose.yml`
- [ ] Check which other services import `src.shared.retrieval` at startup and have the same exposure
- [ ] Live check: recreate the blob sync containers with networking to the internet blocked and confirm they start

---

## DS-007: Blob sync OCR tests fail on a stale test-fixture schema

- **Severity:** Medium (test suite, not production)
- **Status:** Open
- **Found:** 2026-09-11, running `tests/test_azure_blob_source_sync.py` in full while fixing DS-001
- **Affects:** `test_failed_processing_stores_class_without_traceback`, `test_source_only_document_reopens_through_registered_provider`

**What happens.** Both tests fail with:

```
asyncpg.exceptions.UndefinedColumnError: column "ocr_applied_flag" of relation "documents" does not exist
```

`ocr_worker.py` writes `ocr_applied_flag` (lines 590 and 639), and the real schema has it (migration `002_tenant_template_schema.py`,
`tests/conftest.py`). But the `tenant` fixture in `tests/test_ingestion_boundary.py` creates its own `{schema}.documents`
table (line 91) without that column. Not caused by the DS-001/DS-002 changes: neither touches the OCR worker or that fixture.

**Tasks**

- [ ] Add `ocr_applied_flag BOOLEAN DEFAULT false` to the `documents` DDL in `tests/test_ingestion_boundary.py` (or build that fixture from the tenant template instead of a hand-copied table)
- [ ] Re-run `tests/test_azure_blob_source_sync.py` in full and confirm both tests pass
