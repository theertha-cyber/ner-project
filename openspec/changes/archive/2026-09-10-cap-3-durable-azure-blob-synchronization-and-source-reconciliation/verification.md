# Verification Plan

**Change:** cap-3-durable-azure-blob-synchronization-and-source-reconciliation
**Status:** Complete — implementation evidence recorded 2026-09-10.

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|---|---|---|---|---|---|
| 1 | azure-blob-source-sync | Common durable Blob ingestion | New object is synchronized | A newly discovered supported object enters the common pipeline with tenant-schema derived outputs and no Azure downstream branch. | Sync integration test (`test_new_object_synchronizes_through_common_ingestion`) | - [x] |
| 2 | azure-blob-source-sync | Common durable Blob ingestion | Manual trigger runs the same job as the schedule | A tenant-admin manual trigger enqueues the durable sync job with a manual trigger class. | Manual-trigger test (`test_manual_trigger_enqueues_the_same_durable_job`) | - [x] |
| 3 | azure-blob-source-sync | Common durable Blob ingestion | Scheduled cadence with missed-schedule catch-up | A stale active connection gets exactly one catch-up run. | Scheduler catch-up tests (`test_scheduler_cadence_and_catchup_decisions`, `test_stale_connection_gets_one_catchup_run`) | - [x] |
| 4 | azure-blob-source-sync | Common durable Blob ingestion | Inactive connection never syncs | A non-active connection executes no sync job via scheduler or manual trigger. | Inactive-gate tests (`test_inactive_connection_never_syncs`, `test_platform_blob_profile_blocks_the_run`) | - [x] |
| 5 | azure-blob-source-sync | Common durable Blob ingestion | Overlapping runs are prevented by the durable lease | A second trigger during a held lease performs no enumeration/ingestion and records a lease-held outcome. | Lease-overlap tests (`test_overlapping_run_records_lease_held_without_ingesting`, `test_lease_is_released_after_success`) | - [x] |
| 6 | azure-blob-source-sync | Idempotent source version reconciliation and temporary retention | Retry or unchanged object | A retry or unchanged version creates zero duplicate documents, provenance, spans, chunks, embeddings, or extraction outputs. | Idempotency test (`test_retry_or_unchanged_version_creates_no_duplicates`) | - [x] |
| 7 | azure-blob-source-sync | Idempotent source version reconciliation and temporary retention | Changed object is atomically replaced | A changed version ingests a new document and replaces prior derived outputs in one transaction. | Replacement test (`test_changed_version_replaces_prior_derived_outputs`) | - [x] |
| 8 | azure-blob-source-sync | Idempotent source version reconciliation and temporary retention | Deleted source object | A twice-confirmed missing object has its derived records excluded from retrieval with provenance retained. | Missing-object test (`test_missing_object_hides_only_on_second_confirmation`) | - [x] |
| 9 | azure-blob-source-sync | Idempotent source version reconciliation and temporary retention | Single absence does not hide content | One absence adjacent to a listing failure keeps derived records retrievable. | Single-absence test (`test_single_absence_adjacent_to_listing_failure_stays_visible`) | - [x] |
| 10 | azure-blob-source-sync | Idempotent source version reconciliation and temporary retention | Processing reaches a terminal outcome | No durable original Blob copy remains in MinIO after success, failure, or cancellation. | Temp-cleanup tests (`test_temporary_bytes_deleted_on_success`, `test_temporary_bytes_deleted_on_object_failure`) | - [x] |
| 11 | azure-blob-source-sync | Tenant-scoped safe sync status | Sync status exposes only safe classes | Status reads contain only finite outcome classes, identifiers, and correlation timestamps. | Status-shape test (`test_sync_status_exposes_only_safe_classes`) | - [x] |
| 12 | azure-blob-source-sync | Tenant-scoped safe sync status | Failed listing records a distinct outcome | A listing failure records a distinct outcome class and marks nothing missing. | Listing-failure test (`test_failed_listing_records_distinct_outcome_and_marks_nothing`) | - [x] |
| 13 | document-ingestion-boundary | Azure Blob sync submits through the common ingestion boundary | Sync document enters through the common boundary | A sync-submitted document creates a sourced row with no Azure downstream branch. | Boundary contract tests (`test_source_only_document_reopens_through_registered_provider`, row-2 single-writer guard `test_row_2_only_the_ingestion_operation_inserts_documents`) | - [x] |
| 14 | document-ingestion-boundary | Azure Blob sync submits through the common ingestion boundary | Sync documents cannot assert tenant identity | Ingestion uses only the authenticated tenant, ignoring source metadata. | Tenant-authority tests (`test_sync_documents_cannot_assert_tenant_identity`, `test_cross_tenant_connection_use_is_blocked_without_enumeration`) | - [x] |
| 15 | retrieval-core | Retrieval excludes superseded and confirmed-missing source documents | Superseded document chunks are excluded | No retriever returns chunks of a superseded document. | Retrieval-exclusion test (`test_retrievers_exclude_hidden_documents`) | - [x] |
| 16 | retrieval-core | Retrieval excludes superseded and confirmed-missing source documents | Confirmed-missing document chunks are excluded | No retriever returns chunks of a confirmed-missing document while provenance persists. | Retrieval-exclusion test (`test_retrievers_exclude_hidden_documents`) | - [x] |
| 17 | telemetry-tenant-safety | Touched OCR failure paths emit safe structured error classes | OCR failure records a class, not a payload | Failure records carry only finite classes and correlation metadata with no traceback or interpolated message. | Telemetry unit tests (`test_classify_processing_error_uses_finite_classes`, `test_ocr_worker_source_contains_no_unsafe_telemetry`, `test_failed_processing_stores_class_without_traceback`) + metric-contract tests + static scan 2026-09-10 (no print/traceback/secret patterns in `blob_sync/`) | - [x] |

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required | Disposition 2026-09-10 |
|---|---|---|---|---|
| 1 | Tenant authority | Reading tenant identity from the queued payload or source metadata. | Confirm every sync operation derives tenant from the authenticated/connection-owning context. | Confirmed: `_active_blob_connection` requires the connection row to belong to the invoking tenant (`sync.py:122-141`); `test_cross_tenant_connection_use_is_blocked_without_enumeration` and `test_sync_documents_cannot_assert_tenant_identity` pass. |
| 2 | Secret handling | Logging provider errors, endpoints, or resolving credentials into sync state. | Inspect provider runtime and telemetry tests for outcome classes only. | Confirmed: provider failures surface as four finite reasons (`provider.py:21-31`); sync logging carries trigger/reason classes only; no credential resolution on the sync path. |
| 3 | Missing semantics | Hiding documents after a single absence or a failed listing. | Exercise single-absence and listing-failure paths. | Confirmed: `test_missing_object_hides_only_on_second_confirmation`, `test_single_absence_adjacent_to_listing_failure_stays_visible`, and `test_failed_listing_records_distinct_outcome_and_marks_nothing` pass. |
| 4 | Replacement atomicity | Purging old outputs in a separate commit from marking the new document live. | Verify one-transaction replace in the replacement test. | Confirmed: purge + hide + ledger relink share one transaction (`sync.py:315-327`); `test_changed_version_replaces_prior_derived_outputs` asserts old outputs gone and ledger relinked. |
| 5 | Temporary retention | Persisting a working reference where a later reader treats it as durable. | Confirm `finally`-scoped deletion and that no durable-store call exists on the sync path. | Confirmed: staged bytes deleted in `finally` (`sync.py:329-334`); `test_new_object_synchronizes_through_common_ingestion` asserts the durable store never saw the bytes; both temp-cleanup tests pass. |
| 6 | Live Azure | Attempting real Azure calls or credentials in tests. | Confirm fixture/fake provider seam and no live credential in the suite. | Confirmed: `FixtureBlobProvider` throughout; unregistered connections hit `DeferredLiveProvider` which refuses with `prerequisite_missing` (`test_deferred_live_provider_blocks_the_run`); no live credential in the suite. |

## 3. Pattern & ADR Compliance

| ADR | Constraint | Verification Step | Disposition 2026-09-10 |
|---|---|---|---|
| ADR-001 | Sync state in tenant schema; server-side tenant scope; no caller-supplied tenant authority. | Review ledger/run/lease persistence and tests for tenant binding. | Confirmed: all four sync tables are tenant-schema qualified; tenant derived from connection row, never payload; cross-tenant test passes. |
| ADR-012 | Contained Azure runtime, common ingestion, ledger/lease idempotency, temp-only bytes, replace/hide semantics. | Review provider seam, idempotency tests, cleanup tests, retrieval exclusion. | Confirmed: SDK knowledge confined to `provider.py`; all ingestion via `DocumentIngestionService.ingest()`; 26/26 sync tests pass; no Azure branches downstream (row-2 guard + `test_new_object_synchronizes_through_common_ingestion`). |
| ADR-006 | Celery/RabbitMQ durable-work pattern with identity-only JSON payloads. | Review task definition and trigger payloads. | Confirmed: `trigger_manual_sync` returns task name plus string-only `[tenant, connection, trigger]` args (`test_manual_trigger_enqueues_the_same_durable_job`); broker wiring deferred to CAP-6 per design Open Questions. |

## 4. Evidence Requirements

- [x] Passing executable tests cover every Section 1 scenario.
- [x] Code review confirms the contained provider runtime, one sync use case, and tenant-schema ledger/lease design decisions.
- [x] Code review confirms ADR-001, ADR-006, and ADR-012 constraints.
- [x] Telemetry scan confirms sync and touched OCR paths contain no prohibited payload classes.
- [x] Datastore hygiene: sync/ledger test rows removed after the suite.

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|---|---|---|---|---|
| 1 | Executable tests | `tests/test_azure_blob_source_sync.py`: 26 passed | Rows 1–17 | ralph CAP-3 apply | 2026-09-10 |
| 2 | Executable tests | `tests/test_ingestion_boundary.py`: 19 passed (incl. row-2 single-writer guard) | Row 13 | ralph CAP-3 apply | 2026-09-10 |
| 3 | Executable tests | `tests/test_tenant_data_source_control_plane.py` + `tests/test_tenant_integration_profile.py` + `tests/test_chunk_metadata_ingest.py`: 75 passed | CAP-2 control plane (dependency) | ralph CAP-3 apply | 2026-09-10 |
| 4 | Static review | `blob_sync/` + OCR diff scanned for print/traceback/secret/endpoint patterns: none found | Row 17 | ralph CAP-3 apply | 2026-09-10 |

## 6. Audit Record

**Change slug:** cap-3-durable-azure-blob-synchronization-and-source-reconciliation

- [x] Design, ADR, specification, implementation, and executable evidence reviewed.

Known pre-existing issues outside this change (noted, not fixed): `tests/test_analytics_dashboard.py` fails collection (`SyntaxError` at line 98, last touched by commit `60cdf60`); `tests/test_document_ingestion.py::test_docx_extractor_returns_paragraph_text` fails on missing `docx` module in the environment. Both reproduce without this change's files and are recorded for a later run.
