## Why

Tenants keep much of their operational data in spreadsheets: sales exports, price lists, inventory counts. Today the chatbot cannot answer quantitative questions over them. The only CSV path (ADR-012) chunks rows into text for RAG, which returns *similar* rows rather than *all matching* rows, and leaves arithmetic to the LLM. "Total closed revenue in EMEA" comes back wrong. Tenants without an external PostgreSQL database have no way to get exact aggregates over their own tabular data.

## What Changes

- **Tabular file upload on the Data Sources page.** Tenant admins upload `.csv` and `.xlsx` files (one table per selected sheet) in a new "Uploaded files" section. `.xls` and `.xlsm` are rejected. Limits: 100 MB and 1M rows per file, 20 files per tenant, enforced while streaming.
- **Profiling with admin review.** A background worker profiles each upload. It detects the header, sanitizes column names to safe identifiers, infers types by candidate elimination, applies null tokens, and computes per-column stats. Ambiguous date formats are never guessed. The admin reviews a draft schema, fixes types and names, writes or approves table and column descriptions, excludes columns, and approves value hints. They also see a load report (rows read, loaded and rejected, with reasons) and a typed preview before publishing. Nothing reaches chat before publish.
- **Parquet as the query copy, stored in platform MinIO.** On publish, the file is converted once to Parquet with the approved types. The original is kept for download and audit. This applies to all tenants in v1, including `tenant_owned` ones.
- **Contract-governed SQL over uploaded files.** A new `tabular_files` retrieval tool is offered to the planner only when the tenant has at least one ready file. Questions become one SELECT, produced by the existing contract-grounded generation approach and checked by the existing AST validator, unchanged. The statement then runs in an in-memory, locked-down DuckDB instance that holds only that tenant's file. The LLM never produces executable Python.
- **Versioned replace and delete.** Re-upload creates a new version with its own review and a schema diff against the previous one. The prior version stays live until the new one is published. Delete removes the stored objects, the contract and cached copies.
- **Row values are not retained in citations.** An answer cites file name, version, sheet and the columns used. It does not cite row values or filter parameter values, consistent with the external-database answer rule.
- **Deployment wiring and kill switch.** A new `celery_worker_tabular` compose service consumes the `tabular_ingest` queue, and both ingest tasks are routed to it explicitly. `chat_api` gets a named volume for the Parquet cache. `duckdb` reaches every image through `poetry.lock`. The whole feature sits behind `NER_TABULAR_FILES_ENABLED`, which defaults to **on**, so upload-to-chat works right after deploy and can be switched off in one env change.
- **End-to-end proof.** An automated end-to-end test and a live-stack smoke run cover the full path: upload `sales_q3.csv`, review, publish, ask "total closed revenue in EMEA?", and get `1650` cited to `sales_q3.csv`.
- **Coexistence with ADR-012.** CSV chat attachments and documents keep their existing RAG ingestion path. This change adds a separate, admin-governed source type and does not modify that path.

## Capabilities

### New Capabilities

- `tabular-file-ingestion`: upload, validation limits, profiling and type inference, admin review, Parquet publication, versioning, deletion, and MinIO storage layout for tenant tabular files.
- `tabular-file-chat`: the capability-gated `tabular_files` tool, SQL generation and validation against published file contracts, the locked DuckDB executor with its resource limits, safe outcomes, and citation content.

### Modified Capabilities

- `tenant-data-source-portal`: the Data Sources page gains an "Uploaded files" section with upload, review, publish, re-upload and delete flows, and status display.
- `retrieval-tools`: adds the `tabular_files` tool to the per-request registry, gated on server-side resolution of ready files for the authenticated tenant.

## Impact

- **Backend:** new control-plane table `public.tabular_files` (Alembic migration, platform database only, no tenant-store DDL). New gateway endpoints under `/data-sources/files`. New Celery ingest tasks. A new generator and executor in `src/chat_api/services/`. A tool registration in `orchestrator_node` (`src/chat_api/graph/nodes.py`). Citation shaping in `source_assembly_node`.
- **Reused unchanged:** `validate_statement` (`src/shared/external_postgres/validator.py`), the generation prompt rules and the index entry rendering shape. The MinIO client follows `src/document_service/services/storage.py`.
- **Portal:** Data Sources page, a new upload and review flow, status chips.
- **Dependencies:** adds `duckdb`. `openpyxl` is already present. Neither `pandas` nor `pyarrow` is needed.
- **Storage:** new MinIO prefix `tenants/{tenant_id}/tabular/{file_id}/v{n}/`.
- **Operations:**
  - new compose service `celery_worker_tabular` on the `tabular_ingest` queue; the gateway publishes to that queue on the shared broker
  - a named volume on `chat_api` for the Parquet cache, plus per-query memory and CPU caps
  - an updated `poetry.lock` and rebuilt images
  - the `NER_TABULAR_FILES_ENABLED` kill switch, default on

## Open Questions

- **Residency gap (accepted for v1):** file data for `tenant_owned` tenants lives in platform MinIO, not in their own store. The tenant-owned blob storage plan was dropped on 2026-09-20. This needs to be stated to those tenants, and it is tracked as a risk.
- **DuckDB version pin:** the executor relies on `enable_external_access=false` and `lock_configuration=true` behaving as documented in the pinned version. This has to be confirmed by a test that attempts a file read, `ATTACH`, `COPY TO` and `INSTALL` after lockdown.
- **Tool description size:** how many file contracts to include in the planner description before truncating (proposed: all ready files up to the 20-file cap, within a token budget). Retrieval-based selection of file contracts is deferred.
- **Auto-drafted descriptions:** whether v1 drafts column descriptions with an LLM or leaves them empty for the admin to fill in. If drafted, sample values go to the LLM during ingest, which needs the same telemetry exclusion as the SQL generator.
