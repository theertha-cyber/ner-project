## 1. Setup and data model

- [x] 1.1 Add pinned `duckdb` to `pyproject.toml` dependencies and update `poetry.lock` (the shared `Dockerfile` installs from the lock file)
- [x] 1.2 Add settings to `src/shared/config.py`: tabular limits (100 MB, 1M rows, 20 files), executor limits (512 MB, thread cap, 10 s, 1,000 rows, semaphore 4), cache dir and byte budget, description token budget, and the `NER_TABULAR_FILES_ENABLED` kill switch defaulting to **on**
- [x] 1.3 Alembic migration (platform database only) creating `public.tabular_files` (id, tenant_id, display_name, served_version, status, created/updated, deleted_at) and `public.tabular_file_versions` (file_id, version, status, source_kind, sheet, storage keys, profile JSON, review JSON, load report JSON, contract JSON, timestamps), with a unique `(file_id, version)` and a tenant index
- [x] 1.4 Add a `src/shared/tabular_files/store.py` repository (platform-session only) for file and version CRUD, served-version switch in one transaction, the non-deleted count per tenant, and ready contracts per tenant
- [x] 1.5 Add a `src/shared/tabular_files/storage.py` MinIO helper that builds keys only from server IDs (`tenants/{tid}/tabular/{file_id}/v{n}/original.{ext}` and `data.parquet`), following `src/document_service/services/storage.py`

## 2. Parsing, identifiers and type inference

- [x] 2.1 Implement `sanitize_identifier` / `sanitize_all` (lowercase, non-alnum runs to `_`, trim, `c_` prefix for digit-leading, empty or reserved, 63-char truncate, `_2`/`_3` dedupe) in `src/shared/tabular_files/identifiers.py`
- [x] 2.2 Test: `tests/test_tabular_identifiers.py` covers "Headers become safe identifiers"
- [x] 2.3 Implement CSV staging: DuckDB `read_csv(all_varchar=true, header=true)` into a staging table in a worker-local DuckDB file, with the row cap checked while streaming
- [x] 2.4 Implement XLSX staging: `openpyxl.load_workbook(read_only=True, data_only=True)`, per selected sheet, merged-header and missing-header detection (`UNSUPPORTED_SHEET_LAYOUT`), rows streamed into the same staging path, row cap enforced
- [x] 2.5 Test: `tests/test_tabular_parsing.py` covers "Formula cells use cached values", "Merged header is rejected", "Row cap is enforced while streaming"
- [x] 2.6 Implement type inference in SQL over the full staging table: null-token mapping, per-candidate TRY_CAST failure counts, leading-zero regex for `bigint`, `DD/MM` versus `MM/DD` resolution, `date_format_required`, mixed-column warnings with first row numbers
- [x] 2.7 Test: `tests/test_tabular_type_inference.py` covers "Leading zeros stay text", "Null tokens are ignored", "Mixed column falls back with a warning", "Ambiguous dates are not guessed", "Unambiguous day-first dates are detected", plus a bad value in the last row only
- [x] 2.8 Implement the profile builder (null, distinct, min/max, top-10 values for text columns with ≤50 distinct values, warnings, row count) and persist it to the version row with status `needs_review`

## 3. Ingest tasks and gateway API

- [x] 3.1 Add Celery tasks `profile_tabular_version(file_id, version)` and `publish_tabular_version(file_id, version)` with identity-only payloads, following `src/document_service/blob_sync/tasks.py`; on failure they set status `failed` with a finite reason. Define their `celery_app` with `task_routes` sending both to the `tabular_ingest` queue, and have the gateway enqueue on that queue
- [x] 3.2 Gateway `POST /api/v1/data-sources/files`: tenant admin only, tenant from auth context, extension allow-list (`.csv`, `.xlsx`), streaming 100 MB cap, 20-file cap, store original, create v1 in `profiling`, enqueue profile
- [x] 3.3 Test: `tests/test_tabular_upload.py` covers "CSV upload is accepted", "Macro-enabled workbook is rejected", "Oversized file is rejected while streaming", "Per-tenant file cap", "Non-administrator cannot upload"
- [x] 3.4 Test: `tests/test_tabular_storage.py` covers "Tenant-owned tenant uploads a file" and "Object keys never cross tenants"
- [x] 3.5 Gateway `GET /data-sources/files` (list with served and pending versions), `GET /data-sources/files/{id}/versions/{v}/profile`
- [x] 3.6 Gateway `PUT /data-sources/files/{id}/versions/{v}/review`: validate edits (sanitized identifiers, allowed types, formats, null tokens), recompute the load report with TRY_CAST using the reviewed settings (rows read, to load, rejected, first 100 reject row numbers with `cast_failed`), and return a 20-row typed preview without excluded columns
- [x] 3.7 Test: `tests/test_tabular_profile_review.py` covers "Profile is ready for review", "Forcing a stricter type reports rejects", "Excluded column disappears from preview", "Invalid identifier edit is refused"
- [x] 3.8 Gateway `POST /data-sources/files/{id}/versions/{v}/publish` with `Idempotency-Key`. It enforces the publish gate (`DATE_FORMAT_REQUIRED`, `DESCRIPTION_REQUIRED`, duplicate identifiers), then runs the publish task. That task writes Parquet via `COPY (SELECT approved casts ... WHERE all casts succeed) TO ... (FORMAT PARQUET)`, uploads it, stores the canonical contract, and switches the served version in one transaction
- [x] 3.9 Test: `tests/test_tabular_publish.py` covers "Unresolved date format blocks publish", "Missing table description blocks publish", "Successful publish" (asserting Parquet column types via DuckDB)
- [x] 3.10 Gateway `POST /data-sources/files/{id}/versions` (re-upload creates v{n+1}), the schema diff (added, removed, retyped, renamed) against the served version in the review payload, and old-version object cleanup after a successful switch
- [x] 3.11 Gateway `DELETE /data-sources/files/{id}`: mark `deleted` first, then remove all version objects and contracts
- [x] 3.12 Test: `tests/test_tabular_versions.py` covers "Old version stays live during review", "Schema diff is shown", "Publishing switches the served version", "Deleted file leaves chat immediately"

## 4. Chat: capability, tool, generator, executor

- [x] 4.1 Implement `resolve_tabular_capability(platform_session, tenant_id)` in `src/shared/tabular_files/capability.py`, returning served contracts of `ready`, non-deleted files, or `{"executable": False}`; it never raises for absence
- [x] 4.2 Render the tool description from contracts in the `entry_text_for_relation` shape with types, under the token budget (overflow lists relation names only); add a fixed `TABULAR_TOOL_ADDENDUM`
- [x] 4.3 Add `TabularFilesTool` (args schema `{query}` only) and register it per turn in `orchestrator_node` beside the external block, using its own platform session; exceptions are logged and the tool stays unregistered
- [x] 4.4 Test: `tests/test_tabular_capability.py` covers "Tenant with a ready file gets the tool", "Tenant without ready files sees no change" (byte-identical planner input), "Resolution failure degrades safely", "Another tenant's files are never offered", "Kill switch removes the tool"
- [x] 4.5 Implement `src/chat_api/services/tabular_sql_generator.py` reusing the ADR-016 prompt rules builder and `validate_statement`, with a contract of `{relations: included columns, joins: []}`, at most 2 retries fed back with reason class and identifier only, and an LLM client not wrapped by tracers
- [x] 4.6 Test: `tests/test_tabular_sql_generator.py` covers "Question becomes one validated SELECT", "Excluded column cannot be queried", "Cross-file query is rejected", "Write statement never executes", "Exhausted generation gives a fixed message"
- [x] 4.7 Implement the Parquet cache (`src/chat_api/services/tabular_cache.py`): LRU with byte budget keyed `tenant/file/version`, streamed download to temp then atomic rename, entries not matching the served version ignored
- [x] 4.8 Implement the executor (`src/chat_api/services/tabular_executor.py`):
  1. `:memory:` connection with `memory_limit` and `threads`
  2. `CREATE TABLE` from the cached Parquet for referenced relations only
  3. `SET enable_external_access=false; SET lock_configuration=true`
  4. rewrite `%(pN)s` to `$pN` and bind a params dict
  5. 10 s interrupt timer, fetch 1,001 rows for the truncation flag
  6. close the connection

  It runs in a worker thread behind a per-worker semaphore and maps errors to `execution_timeout`, `execution_failed` and `resource_limit`
- [x] 4.9 Test: `tests/test_tabular_executor.py` covers:
  - "Filesystem access is blocked during the statement" (`read_csv`, `read_parquet` on a path, `ATTACH`, `COPY TO`, `INSTALL`, `LOAD`, `SET enable_external_access=true`)
  - "Timeout interrupts a long query"
  - "Result rows are capped"
  - "Stale cache is not used"
  - "Instruction text in a cell is inert"
- [x] 4.10 Wire the tool into `retrieval_execution_node` with a tool envelope (rows, relation and column names, truncated flag, outcome class, no SQL) and route rows into prompt assembly through their own channel, mirroring the external channel
- [x] 4.11 Test: `tests/test_tabular_files_tool.py` covers "Tool schema exposes no tenancy or file-location parameters", "Tool reads only the context tenant's files", "Tool registered only when a file is ready", "Envelope omits SQL text"
- [x] 4.12 Add the `tabular_file` citation type in `source_assembly_node` and the API schemas (file display name, version, sheet, relation and column names; no rows or params) and persist it
- [x] 4.13 Test: `tests/test_tabular_citations.py` covers "Citation names file and columns only" (reload a persisted conversation and assert no param or row values)

## 5. Deployment wiring

- [x] 5.1 Add the `celery_worker_tabular` service to `docker-compose.yml`, modelled on `celery_worker_blob_sync` (same image, `env_file`, broker, result backend, database and `NER_MINIO_ENDPOINT` env, the same `depends_on`), with the command `celery -A <tabular tasks module> worker -Q tabular_ingest --pool=solo --loglevel=info`
- [x] 5.2 Confirm the gateway service has the broker env it needs to publish to `tabular_ingest`, and add it if missing
- [x] 5.3 Add a named volume (such as `tabular_cache`) mounted on `chat_api` at `NER_TABULAR_CACHE_DIR`, and set that env var in the `chat_api` service
- [x] 5.4 Rebuild images with `docker compose build` and confirm `python -c "import duckdb"` succeeds in the `chat_api`, `gateway` and `celery_worker_tabular` containers
- [x] 5.5 Confirm that `task_routes`, the worker `-Q` argument and the gateway enqueue all name `tabular_ingest` (verification Risk 8)

## 6. Portal

- [x] 6.1 Add tabular file API client and hooks in `src/portal/src/lib/data-sources.ts` / `src/portal/src/hooks/use-data-sources.ts` (list, upload, profile, review, publish, new version, delete) with `Idempotency-Key` on mutations
- [x] 6.2 Build the "Uploaded files" section (`src/portal/src/components/data-sources/uploaded-files.tsx`) on `/settings/data-sources`: served and pending versions, status labels, the upload control with the stated limits and fixed error messages, and residency help text for `tenant_owned` tenants
- [x] 6.3 Build the review screen (`src/portal/src/components/data-sources/file-review.tsx`) with per-column editors, table description, null tokens, load report, 20-row preview, schema diff, and a publish control disabled with blocking reasons listed
- [x] 6.4 Add "Upload new version" and a "Delete" confirmation naming the file
- [x] 6.5 Test: `src/portal/src/components/data-sources/uploaded-files.test.tsx` covers "Administrator sees uploaded files", "Pending version shown alongside served version", "Unsupported file is refused with a fixed message", "Delete requires confirmation"
- [x] 6.6 Test: `src/portal/src/components/data-sources/file-review.test.tsx` covers "Review shows blocking reasons", "Type change refreshes the load report", "Successful publish returns to the list"

## 7. Rollout

- [x] 7.1 Wire the `NER_TABULAR_FILES_ENABLED` kill switch (default on). When it is off: hide the portal section, have the upload endpoints refuse requests, and short-circuit `resolve_tabular_capability` to non-executable without reading any table. Add `NER_TABULAR_FILES_ENABLED: "true"` to the relevant compose services so it is explicit
- [x] 7.2 Run `graphify update .` after code changes
- [x] 7.3 Update `docs/` tenant-facing notes with the residency disclosure (ADR-019) and the file-format limits

## 8. End-to-end

- [x] 8.1 Write `tests/test_tabular_end_to_end.py` (marked `verification` and `integration`, following `tests/test_cited_document_viewer_end_to_end.py`). It drives the real gateway and chat routes with a signed JWT, real MinIO, real DuckDB and the real validator, and stubs only the planner and generator LLM calls. It covers "Automated upload-to-answer path"
- [x] 8.2 Bring up the compose stack, then upload `sales_q3.csv` through the portal, review it, publish it and ask "total closed revenue in EMEA?" in chat. Record timestamps, screenshots and the answer in `qa/evidences/tabular-file-data-sources/live-smoke.md`. This covers "Live stack answers from an uploaded file"

## 9. Verification & Evidence

- [x] 9.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [x] 9.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [x] 9.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [x] 9.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent).
- [x] 9.6 Run `openspec validate tabular-file-data-sources --type change --strict` and confirm
         it exits clean before archive.
