## Context

The chatbot has two data paths today. RAG over documents, which is what CSV chat attachments use per the proposed ADR-012, cannot compute exact aggregates. Contract-governed text-to-SQL (ADR-013, ADR-016) is exact, but only for tenants with an active external Azure PostgreSQL connection. Tenants whose data lives in spreadsheets have no exact path.

Constraints that shape this design:

- **Connections are not a fit for files.** `public.tenant_data_source_connections` enforces `uq_data_source_active_provider` (one active connection per `(tenant_id, provider)`, migration 049), and every provider requires secret references and a connection test (`src/shared/data_sources/providers.py`).
- **Reusable validator.** `validate_statement(statement, contract)` (`src/shared/external_postgres/validator.py`) is a `sqlparse`-based allow-list over a plain `{"relations", "joins"}` dict. It already rejects writes, multiple statements, subqueries, CTEs, set operations, window functions, inline literals, unapproved relations, columns, functions and joins.
- **Placeholder style mismatch.** The external generator's prompt fixes placeholders as psycopg `%(pN)s`, which DuckDB does not accept.
- **Capability resolution pattern.** It reads control-plane tables through a separate platform session (Design D10 in `orchestrator_node`), because a `tenant_owned` tenant's session has no `public.*` tables.
- **Existing object storage.** Platform MinIO is reached through `boto3` (`src/document_service/services/storage.py`, keys `tenants/{tenant_id}/documents/...`). The product decision for v1 is that every tenant's files live there.
- **Existing Celery precedent** for durable background ingest (`src/document_service/blob_sync/tasks.py`, ADR-012 durable blob sync).

## Goals / Non-Goals

**Goals:**

- Exact answers (sums, counts, averages, filters, rankings) over tenant-uploaded CSV and XLSX files.
- Tenant administrators govern what the chatbot sees: types, names, descriptions, exclusions, value hints.
- No LLM-authored code runs except validator-accepted SELECT statements in a sandboxed engine.
- No new database server, and no tenant-store DDL.
- Tenants without ready files see no change in planner input.

**Non-Goals:**

- Joins across uploaded files, or between an uploaded file and an external PostgreSQL relation.
- `.xls`, `.xlsm`, multiple tables per sheet, multi-row headers, or merged header cells.
- Editing row values in the portal.
- Storing file data in a `tenant_owned` tenant's own infrastructure.
- Retrieval-based (embedding) selection of file contracts for the prompt.
- Replacing or changing the ADR-012 CSV attachment path.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-001-tenant-data-isolation (as amended by ADR-011/017 where applicable) | Schema-per-tenant; tenant-prefixed object storage; tenant identity from auth context | Object keys must be tenant-prefixed; tenant is never taken from request fields or tool args |
| ADR-007-chatbot-architecture | Platform RAG and SQL chat design | New tool plugs into the existing graph; does not replace platform paths |
| ADR-011-tenant-scoped-azure-connection-control-plane | Closed two-provider connection catalog, one active per provider | Files must not be modelled as connections (catalog closed, one-active index) |
| ADR-012-durable-azure-blob-source-synchronization | Celery/RabbitMQ durable ingest | Ingest runs as Celery tasks with identity-only payloads |
| ADR-013-contract-governed-external-postgresql-chat (clarified by ADR-015) | Contract allow-lists, validator, row cap, no result-row retention, telemetry redaction | Same guards apply: contract-derived validation, row cap, no row values in citations, no SQL or schema to LangSmith |
| ADR-016-contract-grounded-external-sql-generation | Fixed-rule prompt, local validation before execution, bounded retries | Generator reuses the rules and validator unchanged; retries feed back only the reason class and identifier |

Proposed, not in force but relevant: ADR-012-csv-branch (CSV attachments as RAG), which this design leaves untouched, and ADR-017 (tenant-owned data plane), whose residency intent this design knowingly does not extend to uploaded files in v1.

## Decisions

### Decision 1: New control-plane table, not the connections table

**Choice:** `public.tabular_files` holds one row per file with its served version pointer, plus `public.tabular_file_versions` with one row per version. A version row holds status, storage keys, profile JSON, review JSON, load report and canonical contract.

**Rationale:** the one-active-per-provider index would cap a tenant at one file. Connection semantics (secrets, test, activate, pause) do not apply to an uploaded file. A dedicated table keeps versioning explicit and serves "old version live while new one is reviewed" with a single pointer update.

**Alternatives considered:**
- *Each file as a `tabular_file` connection:* ruled out by `uq_data_source_active_provider` and required secret fields.
- *One `tabular_file` connection as a feature toggle, with files as children:* adds a lifecycle with no user value and still needs catalog, secret and test changes.

### Decision 2: Platform MinIO for all tenants, metadata in `public`

**Choice:** originals and Parquet go under `tenants/{tenant_id}/tabular/{file_id}/v{n}/`. Metadata is read and written only through platform sessions.

**Rationale:** this is the v1 product decision. Keeping the data and its metadata on the platform side avoids tenant-store DDL and matches the D10 rule for capability reads. The key prefix follows the convention the codebase actually writes (`tenants/{id}/...`).

**Alternatives considered:**
- *Tenant-owned blob storage for `tenant_owned` tenants:* dropped on 2026-09-20 for complexity and retention conflicts.
- *Per-tenant schema tables for metadata:* requires DDL to ship to tenant-owned stores and a tenant-store read during capability resolution.

### Decision 3: DuckDB over Parquet as the query engine

**Choice:** each published version is converted once to Parquet with the approved types. At query time an in-memory DuckDB connection loads the referenced tables and runs the validated SELECT.

**Rationale:** the result is exact, needs no database server, and the query copy is typed, columnar and compressed, so the engine reads only the referenced columns and skips row groups that cannot match. Types are fixed at publish, so they are never re-inferred per query. DuckDB is an in-process library and holds no state after the connection closes.

**Alternatives considered:**
- *Load rows into Postgres tables in the tenant schema:* needs DDL on tenant-owned stores and a staging and promote step, and puts uploaded data in the transactional database.
- *LLM-generated pandas executed with `exec`:* arbitrary code execution inside `chat_api`, with its credentials and network. Prompt injection through cell contents makes this exploitable, and Python cannot be allow-listed.
- *JSON query spec executed by pandas:* safe, but it needs a new grammar and executor, is less expressive, and pandas scales worse than DuckDB.
- *Sandboxed Python container:* heavy new infrastructure for flexibility v1 does not need.

### Decision 4: Reuse the validator unchanged; rewrite placeholders after validation

**Choice:** the generator keeps the ADR-016 fixed rules, including `%(pN)s` placeholders, and `validate_statement` runs on that exact text. The contract passed to it is `{"relations": {name: {"columns": [...]}}, "joins": []}` built from the served contracts, with excluded columns omitted. After acceptance, `_PLACEHOLDER_RE` rewrites `%(pN)s` to `$pN`, and params are bound by name.

**Rationale:** one validator and one prompt grammar, no drift between SQL paths. An empty join list makes every multi-relation statement fail with `unapproved_join`, which is exactly the v1 no-join rule. The rewrite runs on already-validated text and changes only placeholder tokens.

**Alternatives considered:**
- *A DuckDB-specific prompt that uses `?` or `$1`:* forks the grammar, and the validator's placeholder handling would need changes.
- *Validator changes for DuckDB:* not needed. The allowed functions (`SUM`, `COUNT`, `AVG`, `MIN`, `MAX`, `COALESCE`, `NULLIF`, `CAST`, `EXTRACT`, `DATE_TRUNC`, `NOW`, `CURRENT_DATE`, `CURRENT_TIMESTAMP`, `LOWER`, `UPPER`) and `ILIKE` all exist in DuckDB.

### Decision 5: Load, then lock

**Choice:** per query:
1. `duckdb.connect(":memory:")` with `memory_limit` and `threads` set.
2. For each referenced relation, `CREATE TABLE <relation> AS SELECT * FROM read_parquet('<local cache path>')`.
3. `SET enable_external_access=false; SET lock_configuration=true`.
4. Execute the validated statement with a 10-second interrupt timer.
5. Fetch at most 1,001 rows and set the truncation flag if the extra row exists.
6. Close the connection.

**Rationale:** disabling external access also blocks `read_parquet` on local paths, so loading has to finish before the lock. After the lock, the statement cannot read files, `ATTACH`, `COPY TO`, `INSTALL` or `LOAD`, or change settings. Parquet is read from a local cache rather than through `httpfs`, which would require external access. Relation and path strings in the load step come from server-side contract and cache metadata, never from the model.

**Alternatives considered:**
- *Lock first, then create views over Parquet:* the views read lazily at query time, which fails once external access is off.
- *Allowed-paths settings in newer DuckDB:* not verified for the pinned version, so it is deferred as an optimization.

### Decision 6: Ingest with DuckDB (trusted code); XLSX via openpyxl

**Choice:** CSV profiling reads the file with DuckDB `read_csv(..., all_varchar=true, header=true)`, so every column arrives as text. Inference runs in SQL over the whole table: per-candidate `count(*) FILTER (WHERE value IS NOT NULL AND TRY_CAST(value AS <type>) IS NULL)`, a leading-zero regex for integer candidates, and day/month range checks for slash dates. XLSX sheets are read with `openpyxl.load_workbook(read_only=True, data_only=True)` and streamed into the same staging table. Publish runs `COPY (SELECT <approved casts> FROM staging WHERE <all casts succeed>) TO 'data.parquet' (FORMAT PARQUET)` and uploads the result.

**Rationale:** one engine for inference, the load report (TRY_CAST failure counts and row numbers) and Parquet writing. Full-table evidence avoids "first 10k rows said integer" surprises. The worker is platform code and may use DuckDB with external access. `openpyxl` is already a dependency, and `data_only=True` never evaluates formulas. The only new dependency is `duckdb`.

Both tasks are routed explicitly (`task_routes`) to a dedicated `tabular_ingest` queue, consumed by a new `celery_worker_tabular` compose service. That service is modelled on `celery_worker_blob_sync`: same image, broker, MinIO and database environment, `--pool=solo`. The gateway publishes on the same broker. A dedicated queue keeps a slow profile of a 100 MB file from delaying blob sync or extraction. Explicit routing avoids the known failure where tasks land on Celery's default `celery` queue that no worker consumes.

**Alternatives considered:**
- *Run the tasks on the existing `celery_worker_blob_sync`:* couples unrelated workloads, and a large profile would block sync ticks.
- *pandas plus pyarrow:* two more dependencies, whole-frame memory use, and weaker control over dtypes.
- *DuckDB's own type sniffer:* its choices (for example on leading zeros or ambiguous dates) are not the product rules, so inference stays under our control on top of all-varchar reads.
- *DuckDB's Excel extension:* requires installing an extension at runtime.

### Decision 7: Capability-gated tool mirroring `external_database`

**Choice:** in `orchestrator_node`, beside the external capability block, `resolve_tabular_capability(platform_session, tenant_id)` returns the served contracts of ready files. When there is at least one, it builds a per-turn copy of the registry, registers `TabularFilesTool` with a description rendered in the `entry_text_for_relation` shape under a token budget, and appends a fixed prompt addendum. A resolution exception is logged and leaves the tool unregistered.

**Rationale:** this is the established pattern: byte-identical planner input for tenants without the capability, and tenant authority from auth context only.

**Alternatives considered:**
- *Fold files into `external_database`:* different engine, different gating, different failure messages, and it would couple two independently gated capabilities.

### Decision 8: Citations carry names, not values

**Choice:** a `tabular_file` citation carries the file display name, served version, sheet, and the relation and column names that `validate_statement` accepted. Rows go to generation through a separate channel and are not persisted. Filter parameter values are excluded from citations.

**Rationale:** consistent with ADR-013 as clarified by ADR-015. Parameter values can be as sensitive as rows, for example a customer name.

**Alternatives considered:**
- *Show filters with values in the citation:* more transparent, but it retains data that the external path deliberately does not.

### Decision 9: Local Parquet cache and concurrency limits

**Choice:** each `chat_api` worker keeps an LRU disk cache under a configured directory with a byte budget, keyed by `tenant_id/file_id/version`. Downloads are streamed from MinIO to a temporary file and renamed into place. An `asyncio.Semaphore` caps concurrent tabular executions per worker (default 4). Execution runs in a worker thread so the event loop is not blocked.

In compose, the cache directory (`NER_TABULAR_CACHE_DIR`) is a named volume mounted on `chat_api`, so it survives container restarts and does not fill the container's writable layer.

**Rationale:** repeated questions over the same file skip the download. Version-in-key means a new publish never serves stale data. The caps bound memory to roughly 4 × 512 MB per worker.

## Risks / Trade-offs

- [Residency: `tenant_owned` tenants' uploaded data lives in platform MinIO] → state it in the portal help text and tenant documentation; record it as an accepted v1 gap; revisit when tenant-owned object storage is designed.
- [DuckDB lockdown behaves differently in the pinned version] → pin `duckdb`; add an executor test that tries `read_csv`/`read_parquet` on a path, `ATTACH`, `COPY ... TO`, `INSTALL`, `LOAD` and `SET` after lockdown and asserts each is refused.
- [The `sqlparse` validator misreads DuckDB-specific syntax] → the validator rejects unknown constructs by default. Lockdown is the second wall, and the engine holds only the referenced tables of one tenant.
- [Memory pressure from concurrent large files] → per-connection `memory_limit`, per-worker semaphore, 1M-row and 100 MB caps; the `resource_limit` outcome is surfaced safely.
- [Planner mis-routes numeric questions to RAG when a CSV is both an attachment and an uploaded file] → the `tabular_files` description and addendum state that it answers aggregates over named files; evaluate with the retrieval-eval harness.
- [Tool description grows with many wide files] → token budget with truncation to relation names; embedding selection deferred.
- [Admin-approved value hints expose sample values to the LLM] → only approved hints are published; the same telemetry exclusion as the SQL generator applies.
- [Type inference edge cases produce wrong types] → full-table evidence, warnings, admin override, load report and a publish gate on ambiguous dates.
- [Ingest tasks published to a queue no worker consumes, leaving uploads stuck in `profiling`] → explicit `task_routes` to `tabular_ingest`, a dedicated compose worker, and the live-stack end-to-end scenario, which fails if profiling does not finish within 60 s.
- [Every layer passes its own tests but the full path is broken] → an automated end-to-end test through the real routes, MinIO and DuckDB, with only the LLM stubbed, plus a live-stack smoke run with the real LLM (the precedent is `tests/test_cited_document_viewer_end_to_end.py`).
- [Object key prefix differs from ADR-001's written `tenant-<uuid>/` convention] → follow the prefix the code already writes; flagged under Open Questions.

## Migration Plan

1. Add the pinned `duckdb` dependency, update `poetry.lock`, and rebuild images. The shared `Dockerfile` installs from the lock file, so no Dockerfile edit is needed.
2. Alembic migration: create `public.tabular_files` and `public.tabular_file_versions` on the platform database only. The migration is additive and needs no backfill.
3. Compose: add the `celery_worker_tabular` service on `tabular_ingest`, and add the named cache volume and `NER_TABULAR_CACHE_DIR` to `chat_api`.
4. Deploy the gateway endpoints, ingest tasks, chat tool, executor and portal section together, with `NER_TABULAR_FILES_ENABLED` at its default (on). The tool registers only for tenants with `ready` files, so tenants without uploads are unaffected.
5. Run the live-stack end-to-end smoke test and record its evidence.

**Kill switch and rollback:** setting `NER_TABULAR_FILES_ENABLED=false` hides the portal section, makes the upload endpoints refuse requests, and short-circuits `resolve_tabular_capability` to non-executable. Chat then reverts to byte-identical behaviour. Use it if a lockdown weakness or a data problem is found. Tables and objects can stay in place. Dropping them is a separate, explicit cleanup.

## Open Questions

- **ADR-001 object key prefix:** ADR-001 states `tenant-<uuid>/`, while `storage.py` writes `tenants/{tenant_id}/`. This design follows the code. The ADR step should record whether ADR-001's wording needs a clarifying amendment.
- **Residency exception:** storing `tenant_owned` tenants' uploaded file data on the platform is a deliberate v1 exception to ADR-017's residency intent. The ADR step should record it as a new ADR so the exception is explicit and revisitable.
- **Auto-drafted descriptions:** draft column descriptions with an LLM during profiling, or leave them for the administrator? Proposed for v1: leave them empty. Only the table description is required to publish.
- **Description token budget:** proposed at 2,000 tokens for the tool description; to be tuned with retrieval-eval.
- **Cache directory and budget:** proposed defaults of `/var/cache/ner/tabular` and 2 GB per worker; confirm against the container disk allocation in deployment.
