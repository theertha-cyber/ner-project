# Tasks 8.2 and 8.3 — architectural scope review

Reviewed against `main...HEAD`. Commands are reproducible from the repository root.

## 8.2 — No abstraction was introduced over the platform's chosen technologies

| Claim | Check | Result |
|---|---|---|
| `src/shared/retrieval/` is untouched | `git diff --stat main...HEAD -- src/shared/retrieval/` | empty |
| The `Retriever` protocol and the chat retrieval path are unmodified | `git diff main...HEAD -- src/shared/retrieval/ src/chat_api/services/` | empty |
| No port, repository, or dialect abstraction over PostgreSQL, pgvector, SQLAlchemy, Celery, MLflow, or model serving | `grep -rln "Repository\|Dialect"` over every module this change adds | no matches |
| Engine acquisition is a resolver, not a router | `src/shared/database.py` | `EngineResolver.resolve(tenant_id)` accepts and **ignores** `tenant_id`, returning the process-global engine. No branch on tenant exists. |

The only boundaries this change introduces are the two the design names: the content store
(put / open / delete) and the ingestion contract. Relational persistence keeps raw SQL
against PostgreSQL, exactly as before.

## 8.3 — No deferred capability was started

| Claim | Check | Result |
|---|---|---|
| No pull-source connector or `DocumentSource` contract | `grep -rn "class DocumentSource\|def discover\|def check_connection\|def fetch("` over `src/` | no matches |
| No sync engine, discovery, checkpoints, scheduling, or deletion reconciliation | file listing of `src/document_service/ingestion/` | `contract.py`, `dispatcher.py`, `errors.py`, `service.py` only |
| No `document_sources` table | `grep -rn "document_sources" src/ alembic/` | three hits, all a pre-existing `document_sources: list[str]` request field in `analytics_service/api/v1/schemas.py`; no table, no migration |
| No tenant-hosted database routing | `src/shared/database.py`, migrations 038 and 039 | none; 039 creates one control-plane table in `public` |
| No index boundary | `git diff --stat main...HEAD -- src/shared/retrieval/` | empty |
| No business-database query path | changed-file list | nothing under `src/chat_api/services/sql*` or the tool registry |

The adapter names for deferred sources (`keka`, `s3`, `azure_blob`, `sharepoint`,
`tenant_postgresql`, `external_index`) appear only as *declared, recordable* values in
`src/shared/integration_profile/adapters.py`. None is executable: `unsupported_selections`
refuses activation for any of them, and `DocumentIngestionService` never reads the
profile's adapter selection at all. Verification rows 46-48 and 53 hold that line.

## Files this change touches, by group

Hygiene (group 1) — 12 modules losing a duplicated `_schema`, plus `src/shared/database.py`.
Content store (group 2) — `src/document_service/content_store/`, `services/storage.py`.
Ingestion and processing (groups 3-5) — `src/document_service/ingestion/`,
`api/v1/documents.py`, `services/ocr_worker.py`, `src/shared/document_retention.py`.
Schema and control plane (groups 6-7) — migrations 038 and 039,
`src/shared/integration_profile/`, one metric family in `domain_metrics.py`.

Nothing outside those groups was modified.
