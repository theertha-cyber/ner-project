# Verification Plan

**Change:** tabular-file-data-sources
**Generated:** 2026-09-23
**Status:** 🟡 Evidence collected 2026-09-23. Audit Record (§6) awaits human reviewer sign-off before archive.

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tabular-file-ingestion | Tabular file upload validation | CSV upload is accepted | Given an admin with <20 files, when they upload a 2 MB CSV, then the original is stored, a v1 record in `profiling` exists, and profiling is enqueued | `tests/test_tabular_upload.py` | - [x] |
| 2 | tabular-file-ingestion | Tabular file upload validation | Macro-enabled workbook is rejected | Given an admin, when they upload `.xlsm`, then the response is `UNSUPPORTED_FILE_TYPE` and no object or record exists | `tests/test_tabular_upload.py` | - [x] |
| 3 | tabular-file-ingestion | Tabular file upload validation | Oversized file is rejected while streaming | Given an admin, when they upload 150 MB, then `FILE_TOO_LARGE` is returned after at most 100 MB read and no object exists | `tests/test_tabular_upload.py` | - [x] |
| 4 | tabular-file-ingestion | Tabular file upload validation | Per-tenant file cap | Given 20 non-deleted files, when another is uploaded, then `FILE_LIMIT_REACHED` is returned | `tests/test_tabular_upload.py` | - [x] |
| 5 | tabular-file-ingestion | Tabular file upload validation | Non-administrator cannot upload | Given a non-admin user, when they call upload, then the authorization error is returned and nothing is stored | `tests/test_tabular_upload.py` | - [x] |
| 6 | tabular-file-ingestion | Platform object storage layout | Tenant-owned tenant uploads a file | Given a `tenant_owned` tenant, when a CSV is uploaded, then the original is in platform MinIO under `tenants/{id}/tabular/{file_id}/v1/` and the metadata row is in `public` via a platform session | `tests/test_tabular_storage.py` | - [x] |
| 7 | tabular-file-ingestion | Platform object storage layout | Object keys never cross tenants | Given uploads from tenants A and B, when objects are listed, then every A object sits under `tenants/{A}/tabular/` only | `tests/test_tabular_storage.py` | - [x] |
| 8 | tabular-file-ingestion | Safe file parsing | Formula cells use cached values | Given an XLSX cell `=B2*C2` cached as 1200, when profiled, then the value is 1200 and no formula is evaluated | `tests/test_tabular_parsing.py` | - [x] |
| 9 | tabular-file-ingestion | Safe file parsing | Merged header is rejected | Given a sheet with a merged banner header, when profiled, then it is reported `UNSUPPORTED_SHEET_LAYOUT` and not publishable | `tests/test_tabular_parsing.py` | - [x] |
| 10 | tabular-file-ingestion | Safe file parsing | Row cap is enforced while streaming | Given 1.2M rows, when profiled, then the file is `failed` with `ROW_LIMIT_EXCEEDED` without a full load | `tests/test_tabular_parsing.py` | - [x] |
| 11 | tabular-file-ingestion | Column identifier sanitization | Headers become safe identifiers | Given the five example headers, when sanitized, then the identifiers are `order_id`, `c_2024_revenue`, `c_select`, `amount`, `amount_2` and labels are kept | `tests/test_tabular_identifiers.py` | - [x] |
| 12 | tabular-file-ingestion | Type inference by candidate elimination | Leading zeros stay text | Given `007, 012, 145`, when inferred, then the type is `text` | `tests/test_tabular_type_inference.py` | - [x] |
| 13 | tabular-file-ingestion | Type inference by candidate elimination | Null tokens are ignored | Given `1200, 450, N/A, -, ""`, when inferred, then the type is `bigint` with null count 3 | `tests/test_tabular_type_inference.py` | - [x] |
| 14 | tabular-file-ingestion | Type inference by candidate elimination | Mixed column falls back with a warning | Given 9,990 integers and 10 `abc`, when inferred, then the type is `text` with a warning (count 10 plus row numbers) | `tests/test_tabular_type_inference.py` | - [x] |
| 15 | tabular-file-ingestion | Type inference by candidate elimination | Ambiguous dates are not guessed | Given all-ambiguous slash dates, when inferred, then the column is `date_format_required` with no format | `tests/test_tabular_type_inference.py` | - [x] |
| 16 | tabular-file-ingestion | Type inference by candidate elimination | Unambiguous day-first dates are detected | Given values including `25/04/2026`, when inferred, then the type is `date` with format `DD/MM/YYYY` | `tests/test_tabular_type_inference.py` | - [x] |
| 17 | tabular-file-ingestion | Draft profile | Profile is ready for review | Given profiling finished, when the profile is requested, then per-column stats and `region` values are returned and the status is `needs_review` | `tests/test_tabular_profile_review.py` | - [x] |
| 18 | tabular-file-ingestion | Administrator review and load report | Forcing a stricter type reports rejects | Given 10 non-integer values, when the type is set to `bigint`, then the report shows 10 rejects with row numbers and `cast_failed` | `tests/test_tabular_profile_review.py` | - [x] |
| 19 | tabular-file-ingestion | Administrator review and load report | Excluded column disappears from preview | Given `salary` is excluded, when the preview is shown, then it has no `salary` | `tests/test_tabular_profile_review.py` | - [x] |
| 20 | tabular-file-ingestion | Administrator review and load report | Invalid identifier edit is refused | Given a column, when the identifier is set to `drop table x`, then a validation error names the field | `tests/test_tabular_profile_review.py` | - [x] |
| 21 | tabular-file-ingestion | Publish gate | Unresolved date format blocks publish | Given an included `date_format_required` column, when publishing, then `DATE_FORMAT_REQUIRED` names the column and the status stays `needs_review` | `tests/test_tabular_publish.py` | - [x] |
| 22 | tabular-file-ingestion | Publish gate | Missing table description blocks publish | Given no table description, when publishing, then `DESCRIPTION_REQUIRED` is returned | `tests/test_tabular_publish.py` | - [x] |
| 23 | tabular-file-ingestion | Publish gate | Successful publish | Given a complete review, when publishing, then `v1/data.parquet` exists with approved types, the contract lists only included columns, and the status is `ready` | `tests/test_tabular_publish.py` | - [x] |
| 24 | tabular-file-ingestion | Versioned replace | Old version stays live during review | Given v1 `ready` and v2 `needs_review`, when chat queries, then v1 is used | `tests/test_tabular_versions.py` | - [x] |
| 25 | tabular-file-ingestion | Versioned replace | Schema diff is shown | Given the example v1 and v2 schemas, when v2 review opens, then the diff shows `amount` retyped, `region` removed, `country` added | `tests/test_tabular_versions.py` | - [x] |
| 26 | tabular-file-ingestion | Versioned replace | Publishing switches the served version | Given v2 reviewed, when published, then the next query uses v2 and v1's objects are gone | `tests/test_tabular_versions.py` | - [x] |
| 27 | tabular-file-ingestion | File deletion | Deleted file leaves chat immediately | Given a ready file, when deleted, then the next turn does not offer it and no objects remain under its prefix | `tests/test_tabular_versions.py` | - [x] |
| 28 | tabular-file-chat | Capability-gated tabular tool | Tenant with a ready file gets the tool | Given a ready `sales_q3`, when planning, then `tabular_files` is registered and its description names `sales_q3` and its columns | `tests/test_tabular_capability.py` | - [x] |
| 29 | tabular-file-chat | Capability-gated tabular tool | Tenant without ready files sees no change | Given only a `needs_review` file, when planning, then the planner input is byte-identical to a no-file tenant | `tests/test_tabular_capability.py` | - [x] |
| 30 | tabular-file-chat | Capability-gated tabular tool | Resolution failure degrades safely | Given the control-plane read fails, when planning, then the tool is absent and the turn continues | `tests/test_tabular_capability.py` | - [x] |
| 31 | tabular-file-chat | Capability-gated tabular tool | Another tenant's files are never offered | Given A has files and B has none, when B chats, then there is no `tabular_files` | `tests/test_tabular_capability.py` | - [x] |
| 32 | tabular-file-chat | Contract-validated SQL generation | Question becomes one validated SELECT | Given `sales_q3`, when asked for closed EMEA revenue, then the executed statement is one SELECT summing `amount` with `EMEA` and `closed` as bound params | `tests/test_tabular_sql_generator.py` | - [x] |
| 33 | tabular-file-chat | Contract-validated SQL generation | Excluded column cannot be queried | Given `salary` is excluded, when a candidate references it, then it is rejected `unapproved_column` and not executed | `tests/test_tabular_sql_generator.py` | - [x] |
| 34 | tabular-file-chat | Contract-validated SQL generation | Cross-file query is rejected | Given two ready files, when a candidate selects both, then it is rejected `unapproved_join` | `tests/test_tabular_sql_generator.py` | - [x] |
| 35 | tabular-file-chat | Contract-validated SQL generation | Write statement never executes | Given a candidate `DROP TABLE sales_q3`, when validated, then it is rejected `write_or_ddl` and nothing executes | `tests/test_tabular_sql_generator.py` | - [x] |
| 36 | tabular-file-chat | Locked in-memory execution | Filesystem access is blocked during the statement | Given a locked connection, when file read, ATTACH, COPY TO or INSTALL is executed, then each is refused and no file I/O occurs | `tests/test_tabular_executor.py` | - [x] |
| 37 | tabular-file-chat | Locked in-memory execution | Timeout interrupts a long query | Given a statement running >10 s, when executed, then it is interrupted with `execution_timeout` | `tests/test_tabular_executor.py` | - [x] |
| 38 | tabular-file-chat | Locked in-memory execution | Result rows are capped | Given a 5,000-row result, when executed, then ≤1,000 rows are passed on with the truncated flag set | `tests/test_tabular_executor.py` | - [x] |
| 39 | tabular-file-chat | Locked in-memory execution | Stale cache is not used | Given v1 cached and v2 served, when queried, then v2 is used | `tests/test_tabular_executor.py` | - [x] |
| 40 | tabular-file-chat | Safe tabular outcomes | Exhausted generation gives a fixed message | Given three rejected candidates, when the turn ends, then the outcome is `generation_exhausted` with its fixed message and no SQL text | `tests/test_tabular_sql_generator.py` | - [x] |
| 41 | tabular-file-chat | Tabular citations without row values | Citation names file and columns only | Given an answer from `sales_q3.csv`, when the conversation is reloaded, then the citation shows file, version and columns, and no `EMEA`, `closed` or row values | `tests/test_tabular_citations.py` | - [x] |
| 42 | tabular-file-chat | Prompt injection resistance | Instruction text in a cell is inert | Given a cell containing injection text returned as a result, when the turn completes, then only a validated SELECT ran and no environment, file or network access occurred | `tests/test_tabular_executor.py` | - [x] |
| 43 | tenant-data-source-portal | Uploaded files section | Administrator sees uploaded files | Given two files, when the admin opens the page, then both are listed with status labels in a section separate from connections | `src/portal/src/components/data-sources/uploaded-files.test.tsx` | - [x] |
| 44 | tenant-data-source-portal | Uploaded files section | Pending version shown alongside served version | Given v1 ready and v2 in review, when rendered, then the entry shows v1 served and v2 pending | `src/portal/src/components/data-sources/uploaded-files.test.tsx` | - [x] |
| 45 | tenant-data-source-portal | Uploaded files section | Unsupported file is refused with a fixed message | Given the server returns `UNSUPPORTED_FILE_TYPE`, when uploading, then the fixed message is shown and no entry is added | `src/portal/src/components/data-sources/uploaded-files.test.tsx` | - [x] |
| 46 | tenant-data-source-portal | File review interface | Review shows blocking reasons | Given a `date_format_required` column and no table description, when review opens, then publish is disabled and both reasons are listed | `src/portal/src/components/data-sources/file-review.test.tsx` | - [x] |
| 47 | tenant-data-source-portal | File review interface | Type change refreshes the load report | Given the review screen, when `amount` becomes `numeric`, then the recomputed report is requested and the new reject count is shown | `src/portal/src/components/data-sources/file-review.test.tsx` | - [x] |
| 48 | tenant-data-source-portal | File review interface | Successful publish returns to the list | Given no blockers, when publishing, then the request carries a fresh `Idempotency-Key` and the file shows as `ready` | `src/portal/src/components/data-sources/file-review.test.tsx` | - [x] |
| 49 | tenant-data-source-portal | File replace and delete controls | Delete requires confirmation | Given a ready file, when Delete is activated, then a confirmation naming the file appears and the request is sent only after confirming | `src/portal/src/components/data-sources/uploaded-files.test.tsx` | - [x] |
| 50 | retrieval-tools | Tabular files tool | Tool schema exposes no tenancy or file-location parameters | Given the tool, when `args_schema.properties` is inspected, then the only key is `query` | `tests/test_tabular_files_tool.py` | - [x] |
| 51 | retrieval-tools | Tabular files tool | Tool reads only the context tenant's files | Given A and B each with `sales_q3`, when invoked with A's context, then all rows come from A's served version | `tests/test_tabular_files_tool.py` | - [x] |
| 52 | retrieval-tools | Tabular files tool | Tool registered only when a file is ready | Given one ready file, when the registry is built, then `get("tabular_files")` returns the tool and the export includes it | `tests/test_tabular_files_tool.py` | - [x] |
| 53 | retrieval-tools | Tabular files tool | Envelope omits SQL text | Given a successful call, when the envelope is returned, then it has rows, names and the truncation flag, and no SQL | `tests/test_tabular_files_tool.py` | - [x] |
| 54 | tabular-file-chat | Capability-gated tabular tool | Kill switch removes the tool | Given a ready file and `NER_TABULAR_FILES_ENABLED` off, when planning, then `tabular_files` is absent and planner input is byte-identical to a no-file tenant | `tests/test_tabular_capability.py` | - [x] |
| 55 | tabular-file-chat | End-to-end tabular answer | Automated upload-to-answer path | Given real routes, MinIO and DuckDB with only the LLMs stubbed, when `sales_q3.csv` is uploaded, reviewed and published and the question is asked, then the envelope and generation prompt carry `1650` and the persisted citation names `sales_q3.csv` without `EMEA` or `closed` | `tests/test_tabular_end_to_end.py` | - [x] |
| 56 | tabular-file-chat | End-to-end tabular answer | Live stack answers from an uploaded file | Given the compose stack with `celery_worker_tabular`, the cache volume and a real LLM, when the file is uploaded and published through the portal and the question is asked, then profiling finishes within 60 s, the status reaches `ready`, and the answer contains `1650` cited to `sales_q3.csv` | `qa/evidences/tabular-file-data-sources/live-smoke.md` (manual run log and screenshots) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | DuckDB lockdown order (Design Decision 5) | Sets `enable_external_access=false` before loading (breaks every query), or builds views instead of tables, or skips `lock_configuration`, leaving `SET enable_external_access=true` possible | Read the executor: the load statements run strictly before both `SET`s; run the lockdown test that tries `SET enable_external_access=true`, `read_csv`, `ATTACH`, `COPY TO`, `INSTALL` after the lock and confirm each fails |
| 2 | Placeholder rewrite (Decision 4) | Rewrites before validation, uses string formatting to inline values, or edits the prompt or validator to `?` style | Confirm `validate_statement` receives the untouched `%(pN)s` text; the rewrite touches only `_PLACEHOLDER_RE` matches; params are bound, never interpolated; `validator.py` and the prompt rules are unchanged in the diff |
| 3 | Connections table misuse (Decision 1) | Models files as a new provider in `providers.py`/`tenant_data_source_connections` | Diff shows no change to `PROVIDERS` or migration 049 artifacts; the new migration creates only `public.tabular_files` and `public.tabular_file_versions` |
| 4 | Session selection (Decision 2 / D10) | Reads `public.tabular_*` through the tenant-resolved `session` inside `orchestrator_node` | Confirm capability resolution opens its own platform session like the external block; test with a `tenant_owned` tenant fixture |
| 5 | SQL identifier injection in load step (Decision 5/6) | Builds `CREATE TABLE {name}` or `read_parquet('{path}')` from model output or unsanitized headers | Relation names come only from the served contract (already sanitized at publish) and paths only from the cache manager; grep the executor for any f-string using generator output |
| 6 | Citation content (Decision 8) | Includes params or first-row values in the citation for "transparency" | Inspect the citation schema and a persisted conversation row: no param or row values present |
| 7 | Type inference sampling (Decision 6) | Infers from the first N rows only, or lets DuckDB's sniffer pick types | Inference SQL scans the full staging table; `read_csv` uses `all_varchar=true`; test with a bad value in the last row |
| 8 | Celery queue routing (Decision 6) | Defines the tasks but omits `task_routes`, or names a queue the compose worker does not consume, so uploads stay in `profiling` forever | Compare the `task_routes` queue name, the `-Q` argument of `celery_worker_tabular` in `docker-compose.yml`, and the gateway's enqueue call — all three must say `tabular_ingest`; the live smoke run (row 56) shows the status leaving `profiling` |
| 9 | End-to-end test fidelity (Risks: layered-only testing) | Stubs MinIO, the executor or the validator in `test_tabular_end_to_end.py`, turning it into another unit test | Read the test's fixtures: only the planner and generator LLM calls may be stubbed; MinIO, DuckDB, the validator and the HTTP routes must be real |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001-tenant-data-isolation | Tenant identity from auth context; tenant-prefixed storage | Tenant is never taken from request or tool arguments; object keys are tenant-prefixed | Grep endpoints and tool: `tenant_id` comes only from auth/ToolContext; test row 7 passes |
| ADR-007-chatbot-architecture | Graph-based chat with orchestrated tools | The tool plugs into the existing graph without new nodes or agentic loops | Graph topology unchanged in `build_chat_graph`; only registry and source assembly change |
| ADR-011-tenant-scoped-azure-connection-control-plane | Closed provider catalog, one active connection per provider | Files are not connections | `providers.py` and the connection migrations are untouched |
| ADR-012-durable-azure-blob-source-synchronization | Celery durable ingest with identity-only payloads | Ingest tasks carry IDs only, never file bytes or tenant data | Inspect task signatures and enqueue calls |
| ADR-013 (+ ADR-015 clarification) | Contract allow-lists, row cap, no result-row retention, telemetry redaction | Row cap; no rows or params in citations; no SQL or schema in telemetry | Tests 38 and 41; inspect logging calls for SQL or param fields |
| ADR-016-contract-grounded-external-sql-generation | Fixed rules, local validation, bounded retries, no LLM tracing | Reuse the rules and validator; at most 2 retries; generator client untraced | Diff shows the rules and validator reused; retry count test; client construction has no LangSmith wrapper |
| ADR-018-uploaded-tabular-files-queried-via-locked-duckdb-over-parquet | Locked in-memory DuckDB over Parquet; only validated SQL executes | No model-generated code other than SQL; lockdown before execution | Test 36; grep for `exec(`/`eval(` in new modules (none) |
| ADR-019-uploaded-tabular-files-stored-in-platform-object-storage-for-all-tenants | Platform MinIO and `public` metadata for all tenants | No tenant-store DDL; residency disclosure in portal | Migration targets the platform database only; portal help text present |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Rows 1–5: gateway upload tests pass (accept, `.xlsm` reject, streaming size reject, cap reject, non-admin reject)
- [x] Rows 6–7: storage tests show keys under `tenants/{id}/tabular/...` for a `tenant_owned` fixture and no cross-tenant keys
- [x] Rows 8–10: parser tests pass (cached formula value, merged header rejection, row-cap streaming stop)
- [x] Row 11: sanitizer table-driven test passes for the five example headers
- [x] Rows 12–16: inference table-driven tests pass (leading zeros, null tokens, mixed fallback with warning, ambiguous date, day-first date)
- [x] Row 17: profile endpoint test output shows stats and `needs_review`
- [x] Rows 18–20: review endpoint tests pass (reject counts, excluded preview, invalid identifier)
- [x] Rows 21–23: publish tests pass (two gate refusals; success writes Parquet, and a DuckDB schema read shows approved types)
- [x] Rows 24–26: versioning tests pass (served v1 during review, diff content, switch plus v1 object removal)
- [x] Row 27: deletion test shows the tool is absent next turn and no objects remain
- [x] Rows 28–31: orchestrator tests pass (registration, byte-identical planner input, failure degrade, cross-tenant absence)
- [x] Rows 32–35: generator and validator tests pass (param binding, excluded column, join, DDL)
- [x] Rows 36–39: executor tests pass (lockdown refusals, timeout, row cap, version-keyed cache)
- [x] Row 40: outcome test shows the fixed message without SQL
- [x] Row 41: persisted citation inspected and free of row and param values
- [x] Row 42: injection fixture test passes, with no statement other than a validated SELECT executed
- [x] Rows 43–49: portal component tests pass. Screenshots waived by the user on 2026-09-23; the live smoke log describes the Uploaded files section and review screen as observed
- [x] Rows 50–53: retrieval-tools tests pass (args schema keys, tenant scoping, registry, envelope shape)
- [x] Row 54: capability test with the flag off shows no tool and byte-identical planner input
- [x] Row 55: `tests/test_tabular_end_to_end.py` output passes, asserting `1650` in the envelope and the prompt and a citation naming `sales_q3.csv` without `EMEA` or `closed`
- [x] Row 56: live-smoke log with the timestamps of the upload leaving `profiling` (4.4 s) and reaching `ready`, the chat answer containing `1,650`, and the persisted citation naming `sales_q3.csv`. Screenshot waived by the user on 2026-09-23

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [x] All ADR compliance steps in Section 3 confirmed (agent review, 2026-09-23; see Evidence Log #8)
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)

### Edge Case Evidence

- [x] Risk 1: lockdown ordering reviewed and the post-lock refusal test observed passing
- [x] Risk 2: validator input verified as untouched `%(pN)s` text; `validator.py` and the prompt rules are unchanged in the diff
- [x] Risk 3: no provider catalog or connection-table changes in the diff
- [x] Risk 4: capability resolution verified in code to use its own platform session (`nodes.py` orchestrator and guardrail). No automated `tenant_owned` capability fixture exists; the live smoke tenant `arjunj` is `tenant_owned` and resolution worked there (see Evidence Log #6)
- [x] Risk 5: executor load statements verified to use only contract and cache-manager values
- [x] Risk 6: citation payload inspected for the absence of params and row values
- [x] Risk 7: last-row bad-value inference test observed passing
- [x] Risk 8: queue name confirmed `tabular_ingest` in `task_routes`, the compose worker `-Q` and the gateway enqueue call. Caveat: the name comes from a setting (`NER_TABULAR_CELERY_QUEUE`) while compose hardcodes it, and no test covers the routing
- [x] Risk 9: **deviation recorded.** Real parts: MinIO, DuckDB, the validator, the executor and the HTTP routes. But the test also stubs the chat guardrail and answer model, and replaces the Celery hop with direct worker calls. The live smoke exercises both for real (see Evidence Log #6)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Test output | `qa/evidences/tabular-file-data-sources/pytest-tabular.txt`: `tests/test_tabular_*.py -v`, 105 passed | Rows 1–42, 50–55 | Claude (agent) | 2026-09-23 |
| 2 | Test output | `qa/evidences/tabular-file-data-sources/vitest-tabular.txt`: `uploaded-files`, `file-review`, `CitationCard` and data-sources page tests, 26 passed | Rows 43–49 | Claude (agent) | 2026-09-23 |
| 3 | Test output | Lockdown refusals after the lock (`read_csv`, `read_parquet`, `ATTACH`, `COPY TO`, `INSTALL`, `LOAD`, `SET enable_external_access=true`, `glob`): `test_tabular_executor.py::test_filesystem_access_is_blocked_during_the_statement[*]` passed | Row 36, Risk 1 | Claude (agent) | 2026-09-23 |
| 4 | Test output | `test_tabular_type_inference.py::test_bad_value_in_the_last_row_only` passed (50,000 ints then `oops` gives `text`, warning row 50002) | Row 14, Risk 7 | Claude (agent) | 2026-09-23 |
| 5 | Persisted row | `qa/evidences/tabular-file-data-sources/persisted-citation.json`: the reloaded conversation's `tabular_file` source carries `sales_q3.csv`, v1, relation and `amount, region, status` only, with no `EMEA`, `closed` or row value | Row 41, Risk 6 | Claude (agent) | 2026-09-23 |
| 6 | Manual run log | `qa/evidences/tabular-file-data-sources/live-smoke.md`: compose stack with a real LLM on `tenant_owned` tenant `arjunj`. Profiling took 4.4 s, `ready` at 13:49:11, answer "1,650" cited to `sales_q3.csv`. Three defects were found and fixed during the run, each with a test | Row 56, Risks 4, 8, 9 | Claude (agent), portal session by Arjun | 2026-09-23 |
| 7 | Code review | Risk register read-through (subagent): risks 1–3 and 5–8 confirmed at file:line; risk 4 has no `tenant_owned` capability fixture (covered live by #6); risk 9 deviation (guardrail, answer model and Celery hop also stubbed) | Risks 1–9 | Claude (agent) | 2026-09-23 |
| 8 | Code review | ADR read-through (subagent): 001, 007, 011, 012, 016, 018 and 019 compliant. 013/015 was partial because two gateway `logger.exception` calls could log platform SQL and bound values in tracebacks; fixed to `error_class`-only logging in `src/gateway/api/v1/tabular_files.py`, and upload and versions tests re-run (17 passed) | Section 3 | Claude (agent) | 2026-09-23 |
| 9 | Spec coverage | All 56 `#### Scenario:` blocks in `specs/**/spec.md` match the 56 Spec Alignment rows by name; `openspec validate tabular-file-data-sources --type change --strict` reports "Change 'tabular-file-data-sources' is valid" | Section 1 | Claude (agent) | 2026-09-23 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** tabular-file-data-sources
**Proposal:** `openspec/changes/tabular-file-data-sources/proposal.md`
**Spec files reviewed:**
  - specs/tabular-file-ingestion/spec.md
  - specs/tabular-file-chat/spec.md
  - specs/tenant-data-source-portal/spec.md
  - specs/retrieval-tools/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [ ] |
| All ADRs in Section 3 verified compliant | - [ ] |
| Spec Alignment table complete (no missing scenarios) | - [ ] |
| Evidence Log populated with real evidence | - [ ] |
| All functional evidence items in Section 4 checked | - [ ] |
| All structural evidence items in Section 4 checked | - [ ] |
| All edge case evidence items in Section 4 checked | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
