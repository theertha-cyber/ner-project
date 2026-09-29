# ADR-018. Uploaded Tabular Files Are Queried via Locked In-Process DuckDB over Parquet

- **Status:** accepted
- **Date:** 2026-09-23

## Context

Tenant administrators need the chatbot to answer exact quantitative questions (sums, counts, filters, rankings) over CSV and XLSX files they upload. RAG over row chunks, the ADR-012 CSV attachment path, cannot do this: it retrieves similar rows, not all matching rows, and leaves arithmetic to the LLM. The platform already has a safe pattern for exact answers: contract-governed SQL (ADR-013, ADR-016), where an allow-list validator accepts one parameterized SELECT and an engine with restricted capability executes it.

The options for uploaded files were:
- load them into Postgres tables in tenant schemas
- let the LLM write pandas code and execute it
- define a JSON query language executed with pandas
- run LLM Python in a sandbox container
- query with an embedded analytical engine

Executing model-authored Python inside a service is unacceptable. Cell contents are untrusted input to the LLM, so prompt injection can steer the generated code, and Python cannot be allow-listed. Loading into tenant Postgres would require DDL on tenant-owned stores and put uploaded bulk data in the transactional database.

## Decision

1. **Parquet is the query copy.** Each published version of an uploaded table is converted once to Parquet, with the column types the administrator approved. The original file is kept separately. The query copy is immutable; changes arrive as new versions.
2. **DuckDB is the engine, in process and in memory, per query.**
   - Each accepted statement runs in a fresh `:memory:` DuckDB connection, loaded only with the referenced tables of the authenticated tenant's served versions.
   - External access is then disabled and configuration locked before the statement runs.
   - The connection enforces memory, thread, time and row caps, and is closed afterwards.
   - No DuckDB database file persists.
3. **The only model-authored code that runs is validated SQL.** Statements are produced under the ADR-016 rules and accepted by the existing contract validator before execution. No model-generated Python, pandas expression or other code SHALL be evaluated anywhere on this path.
4. **Contracts govern visibility.** An administrator-reviewed contract (relations, included columns, types, descriptions, approved value hints) is the sole source of schema context and validation allow-lists. Excluded columns do not exist from the model's point of view.
5. **No cross-source joins.** An uploaded file is never joined with external PostgreSQL relations or platform tables. Joins between uploaded files are disabled until a later ADR introduces declared join keys.

## Consequences

- Exact answers over spreadsheets without a new database server or tenant-store DDL; `duckdb` becomes a platform dependency.
- The ADR-013/016 safety shape extends to a second engine. Any widening of the validator grammar now affects both paths and needs coordinated tests.
- Two independent walls stop hostile SQL: validator rejection, then an engine with no file, network or extension access holding only one tenant's referenced tables.
- Query latency depends on loading Parquet into memory per query. Very large files are bounded by upload limits, and a service that needs warehouse-scale data must use a different source type.
- Future formats (for example JSON lines, or `.xls` via a converter) can reuse the same publish-to-Parquet and locked-query pipeline.
- The CSV attachment RAG path (ADR-012, proposed) remains separate. The same file may exist in both paths with different semantics.
