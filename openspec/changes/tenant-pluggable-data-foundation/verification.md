# Verification Plan

**Change:** tenant-pluggable-data-foundation
**Generated:** 2026-09-07
**Status:** 🔴 Incomplete — Evidence Log and Audit Record must be filled by a human reviewer before archive.

---

## 1. Spec Alignment

Map every requirement and every scenario in this change to a testable acceptance criterion.
Each row drives one evidence entry in Section 5.

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | document-ingestion-boundary | Single application-owned ingestion entry point | Upload creates a document through the ingestion operation | Given an authenticated tenant user, when they POST a PDF, then the `documents` row is created by the ingestion operation and the response is 201 with the pre-change body fields | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 2 | document-ingestion-boundary | Single application-owned ingestion entry point | No second writer of the documents table exists | Given the source tree, when INSERTs targeting a `documents` relation are enumerated outside tests and migrations, then exactly one exists and it resides in the ingestion operation | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 3 | document-ingestion-boundary | Single application-owned ingestion entry point | The ingestion operation is callable without an HTTP request | Given a normalized document built with no FastAPI request and no `UploadFile`, when the operation is invoked, then a document is created, processing is dispatched, and no exception is raised | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 4 | document-ingestion-boundary | Normalized document contract | Purpose is carried on the contract | Given a normalized document with purpose `training`, when ingested and processed, then the stored purpose is `training` and no chunks or embeddings are produced | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 5 | document-ingestion-boundary | Normalized document contract | Optional source metadata is absent without error | Given no external identity, version, or source timestamps, when ingested, then ingestion succeeds and those stored fields are NULL | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 6 | document-ingestion-boundary | Normalized document contract | Source timestamps are never synthesised | Given a source supplying no modified timestamp, when ingested, then the stored source-modified timestamp is NULL and is not set to ingestion time | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 7 | document-ingestion-boundary | Normalized document contract | An adapter cannot assert a tenant identity | Given source metadata carrying a different tenant identifier, when ingested, then the document is written to the authenticated tenant's schema and the metadata value has no effect | `tests/test_ingestion_boundary.py` (task 3.7) | - [ ] |
| 8 | document-ingestion-boundary | Declared content-acquisition capability | Platform upload declares single-use content | Given the platform upload adapter, when it constructs a normalized document, then the declared content-acquisition capability is `single_use` | `tests/test_ingestion_boundary.py` (task 3.8) | - [ ] |
| 9 | document-ingestion-boundary | Declared content-acquisition capability | A single-use source is never assigned source-only retention | Given a profile requesting `source_only`, when a `single_use` document is submitted, then ingestion is rejected naming the incompatible combination, no row is created, and no bytes are written | `tests/test_ingestion_boundary.py` (task 3.8) | - [ ] |
| 10 | document-ingestion-boundary | Declared content-acquisition capability | Content resolution is decided once and recorded | Given a profile selecting `ephemeral` and a `single_use` upload, when ingested, then `retention_mode` is `ephemeral` and processing obtains bytes from that recorded value without re-deriving it | `tests/test_ingestion_boundary.py` (task 3.8) | - [ ] |
| 11 | document-ingestion-boundary | Declared content-acquisition capability | Checksum is computed by the platform over the bytes it read | Given a source declaring a non-SHA-256 version string, when ingested, then the stored checksum is the platform SHA-256 of the bytes read and the declared version is stored separately | `tests/test_ingestion_boundary.py` (task 3.8) | - [ ] |
| 12 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | Upload behaviour is unchanged | Given the existing document ingestion test suite, when run against the refactored route with edits confined to mock patch targets and fixture DDL, then every existing scenario still passes | existing `tests/test_document_ingestion.py` + `tests/test_document_content_hash.py`, plus a reviewed diff of both files (task 3.9) | - [ ] |
| 13 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | Uploaded documents record the reserved platform source | Given an authenticated tenant user, when they upload, then `source_type` is `platform_upload` and `source_id` is exactly `platform-upload` | `tests/test_ingestion_boundary.py` (task 3.9) | - [ ] |
| 14 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | The reserved source identifier is stable across uploads | Given one tenant uploading two documents at different times, when both rows are read, then their `source_id` values are identical and neither is a generated identifier | `tests/test_ingestion_boundary.py` (task 3.9) | - [ ] |
| 15 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | The reserved identifier cannot be claimed by a configured source | Given an attempt to register a document source with `source_id` `platform-upload`, when written, then it is rejected as reserved | `tests/test_ingestion_boundary.py` (task 3.9) | - [ ] |
| 16 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | Role-to-purpose policy remains at the HTTP boundary | Given a `business_user`, when they POST with `purpose=training`, then the response is 403 and no document row is created | `tests/test_ingestion_boundary.py` (task 3.9) | - [ ] |
| 17 | document-ingestion-boundary | Platform upload is an adapter over the ingestion contract | The route does not reference the content store | Given the upload route module, when its imports and references are inspected, then no object-storage client type is referenced and no storage key is constructed | `tests/test_ingestion_boundary.py` (task 3.9) | - [ ] |
| 18 | document-ingestion-boundary | Injectable processing dispatch | Default dispatch is unchanged | Given the default dispatcher, when a document is uploaded, then processing is scheduled in-process exactly as before this change | `tests/test_ingestion_boundary.py` (task 3.10) | - [ ] |
| 19 | document-ingestion-boundary | Injectable processing dispatch | Dispatch carries no content | Given the dispatcher contract, when its parameters are inspected, then they comprise the document identity and tenant identity only | `tests/test_ingestion_boundary.py` (task 3.10) | - [ ] |
| 20 | document-ingestion-boundary | Injectable processing dispatch | A test dispatcher observes dispatch without executing it | Given a recording dispatcher, when a document is ingested, then exactly one dispatch is recorded for that document id and no OCR executes | `tests/test_ingestion_boundary.py` (task 3.10) | - [ ] |
| 21 | document-ingestion-boundary | The processing pipeline contains no source-specific behaviour | No source conditionals exist downstream of ingestion | Given the OCR worker, chunking, embedding, extraction, retrieval, and chat modules, when their statements are inspected, then none branches on `source_type`, `source_id`, or a storage adapter kind | `tests/test_pipeline_source_neutrality.py` (task 8.1) | - [ ] |
| 22 | document-ingestion-boundary | The processing pipeline contains no source-specific behaviour | Two documents from different sources follow one path | Given one document ingested through the upload adapter and one ingested directly with a different source type, same content and purpose, when both are processed, then their text spans are equivalent and their chunk counts are equal | `tests/test_pipeline_source_neutrality.py` (task 8.1) | - [ ] |
| 23 | original-document-storage | Document content store boundary | Storing returns an opaque reference | Given a configured content store, when bytes are put, then a storage reference is returned and opening it yields the identical bytes | `tests/test_content_store.py` (task 2.4) | - [ ] |
| 24 | original-document-storage | Document content store boundary | Deleting removes the bytes | Given bytes previously put and their reference, when delete is called, then a subsequent open does not return the bytes and a repeat delete is safe | `tests/test_content_store.py` (task 2.4) | - [ ] |
| 25 | original-document-storage | Document content store boundary | The boundary exposes no storage configuration | Given the boundary's contract definition, when its operations and types are inspected, then no bucket, container, endpoint, region, or credential is named | `tests/test_content_store.py` (task 2.4) | - [ ] |
| 26 | original-document-storage | The storage reference is an outcome, never an input | The upload path does not precompute a key | Given the ingestion operation and the upload route, when their statements are inspected, then neither constructs a storage path or key, and the persisted reference equals the store's return value | `tests/test_content_store.py` (task 2.4) | - [ ] |
| 27 | original-document-storage | The storage reference is an outcome, never an input | Key construction lives inside the platform adapter | Given the platform MinIO adapter, when bytes are put for a tenant, then the object key is constructed inside the adapter and is scoped to that tenant's prefix | `tests/test_content_store.py` (task 2.4) | - [ ] |
| 28 | original-document-storage | Retention mode is explicit and determines content resolution | Retention mode is stored, not inferred | Given an `ephemeral` document whose working copy has been deleted, when its row is read, then `retention_mode` is `ephemeral` and does not change because the reference became unusable | `tests/test_retention_lifecycle.py` (task 5.2) | - [ ] |
| 29 | original-document-storage | Retention mode is explicit and determines content resolution | Platform retention reopens from the durable store | Given a `platform_blob` document, when processing obtains its bytes, then they are read from the durable content store using the recorded reference | `tests/test_retention_lifecycle.py` (task 5.2) | - [ ] |
| 30 | original-document-storage | Retention mode is explicit and determines content resolution | Retention follows tenant configuration, not source type | Given two tenants whose profiles select `platform_blob` and `ephemeral`, when each uploads the same document, then the recorded retention modes are `platform_blob` and `ephemeral` respectively | `tests/test_retention_lifecycle.py` (task 5.2) | - [ ] |
| 31 | original-document-storage | Retention mode is explicit and determines content resolution | An adapter cannot override retention | Given an adapter asserting a retention preference in source metadata, when its document is ingested, then the retention applied is the one resolved from the tenant profile | `tests/test_retention_lifecycle.py` (task 5.2) | - [ ] |
| 32 | original-document-storage | Ephemeral retention uses a bounded working copy | An ephemeral document processes end to end | Given a tenant profile selecting `ephemeral`, when a PDF is uploaded and processing completes, then status is `processed` and text spans exist | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 33 | original-document-storage | Ephemeral retention uses a bounded working copy | The working copy is deleted on success | Given that document, when processing reaches `processed`, then the working copy has been deleted from the working store and the persisted reference is NULL | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 34 | original-document-storage | Ephemeral retention uses a bounded working copy | The working copy is deleted on failure | Given a corrupt `ephemeral` document, when processing reaches `failed`, then the working copy has been deleted and the persisted reference is NULL | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 35 | original-document-storage | Ephemeral retention uses a bounded working copy | Nothing is written to the durable store under ephemeral retention | Given an `ephemeral` profile and an instrumented durable store, when a document is uploaded and processed, then no put and no open occurred against the durable store | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 36 | original-document-storage | Ephemeral retention uses a bounded working copy | An ephemeral query document becomes retrievable | Given an `ephemeral` `purpose='query'` document, when processing completes and semantic retrieval runs for text it contains, then its chunks are retrievable and match its extracted text | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 37 | original-document-storage | Ephemeral retention uses a bounded working copy | A NULL reference is not reported as a failure | Given a successfully processed `ephemeral` document whose working copy is deleted, when its metadata is retrieved, then status is `processed` and no error message is present | `tests/test_retention_lifecycle.py` against a real working store (task 5.3) | - [ ] |
| 38 | original-document-storage | Reprocessability is bounded by retention mode | Reprocessing a retained document succeeds | Given a processed `platform_blob` document, when reprocessed, then bytes are read from the durable store and processing succeeds | `tests/test_retention_lifecycle.py` (task 5.4) | - [ ] |
| 39 | original-document-storage | Reprocessability is bounded by retention mode | Reprocessing an expired ephemeral document fails explicitly | Given a processed `ephemeral` document whose working copy is deleted, when reprocessing is requested, then it fails identifying the bytes as unresolvable, existing spans and chunks are unchanged, and status does not become `failed` | `tests/test_retention_lifecycle.py` (task 5.4) | - [ ] |
| 40 | original-document-storage | Reprocessability is bounded by retention mode | Retries within the processing window reuse the recorded resolution | Given an `ephemeral` document whose first attempt raised a transient error before a terminal state, when attempted again while the working copy exists, then bytes come from the working copy and processing can succeed | `tests/test_retention_lifecycle.py` (task 5.4) | - [ ] |
| 41 | original-document-storage | No consumer parses the storage reference | OCR does not read the storage reference to choose an extractor | Given the OCR processing path, when its statements are inspected, then the reference is never split, parsed, or pattern-matched, and extractor selection derives from the resolved media type | `tests/test_content_store.py` (task 4.8) | - [ ] |
| 42 | original-document-storage | No consumer parses the storage reference | Processing succeeds for a document with no durable reference | Given an `ephemeral` document being processed for the first time, when the worker runs, then bytes are obtained through the recorded content resolution and processing succeeds | `tests/test_content_store.py` (task 4.8) | - [ ] |
| 43 | tenant-integration-profile | Per-tenant integration profile in control-plane storage | Every tenant has a profile | Given a provisioned tenant, when its profile is read, then a profile exists and its selected adapters are the platform defaults | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 44 | tenant-integration-profile | Per-tenant integration profile in control-plane storage | Profiles live in the control plane | Given the profile migration, when its target schema is inspected, then the table is created in `public` and not in `tenant_template` or any `tenant_%` schema | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 45 | tenant-integration-profile | Per-tenant integration profile in control-plane storage | A profile is readable when the tenant schema is unavailable | Given a tenant whose schema is unreadable, when its profile is read, then the profile is returned and no error is raised | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 46 | tenant-integration-profile | Only platform default adapters are executable in this change | A non-default selection may be recorded | Given a `draft` profile, when its index adapter is set to a recorded-but-unsupported value, then the write succeeds and the profile remains `draft` | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 47 | tenant-integration-profile | Only platform default adapters are executable in this change | A non-default selection cannot be activated | Given a `draft` profile selecting a non-default relational or index adapter, when activation is attempted, then it is rejected naming the unsupported selection and the profile does not enter `active` | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 48 | tenant-integration-profile | Only platform default adapters are executable in this change | Ingestion always uses executable adapters | Given a tenant whose profile records a non-default source selection, when a document is ingested, then the platform upload source and platform content store serve it and the recorded selection has no effect | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 49 | tenant-integration-profile | Typed profile configuration with an allowlisted shape | An unknown configuration key is rejected | Given a profile write carrying a key outside the declared set for that adapter kind, when performed, then it is rejected naming the unknown key and no row is persisted | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 50 | tenant-integration-profile | Typed profile configuration with an allowlisted shape | A secret field must hold a reference, not a value | Given a secret-reference field carrying a literal that does not match `<scheme>://<path>`, when written, then it is rejected and no row is persisted | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 51 | tenant-integration-profile | Typed profile configuration with an allowlisted shape | A valid reference is accepted and stored verbatim | Given a secret-reference field matching the grammar, when written, then it succeeds and the stored value is the reference exactly as supplied | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 52 | tenant-integration-profile | Typed profile configuration with an allowlisted shape | Validation does not depend on value inspection | Given a non-secret string field whose value resembles a credential, when written, then it is accepted on the basis of the declared schema and no heuristic rejection occurs | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 53 | tenant-integration-profile | Profile status model | A draft profile is not used to serve requests | Given a tenant whose profile is `draft`, when a document is ingested, then the platform defaults are used and the draft selections have no effect | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 54 | tenant-integration-profile | Profile status model | Activation from draft is refused | Given a profile in `draft`, when activation is attempted without validation, then the transition is rejected and the profile remains `draft` | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 55 | tenant-integration-profile | Profile status model | An unresolvable reference moves the profile to error | Given an `active` profile whose reference cannot be resolved, when resolution is attempted, then the profile transitions to `error` with a reason naming the reference and its failure class and containing no credential material | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 56 | tenant-integration-profile | Profile status model | An errored profile recovers only through revalidation | Given a profile in `error`, when activation is attempted directly, then it is rejected, and a successful revalidation moves it to `validated` | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 57 | tenant-integration-profile | Profile status model | A retired profile is terminal | Given a profile in `retired`, when any transition to another status is attempted, then it is rejected | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 58 | tenant-integration-profile | Profiles hold secret references, never secret values | Administrative reads never return secrets | Given a profile containing secret references, when returned through any administrative API, then the response contains the references and no resolved credential value | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 59 | tenant-integration-profile | Profiles hold secret references, never secret values | Resolution is scoped to the owning tenant | Given a reference belonging to tenant A, when resolution is attempted with tenant B's identity, then resolution fails and no credential is returned | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 60 | tenant-integration-profile | Profiles hold secret references, never secret values | Resolved credentials are never persisted or logged | Given any reference resolution, when it completes, then no resolved value appears in any database row, log record, span attribute, or metric label | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 61 | tenant-integration-profile | Profiles are developer-managed | Tenant users cannot modify profiles | Given a `tenant_admin`, when they attempt to modify their tenant's profile through any tenant-facing API, then the request is rejected | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 62 | tenant-integration-profile | Adapter selection is observable | Ingestion records the adapters that served it | Given a document ingested for a tenant, when the ingestion's observability output is inspected, then it records the source type, content-store kind, and retention mode, all drawn from the declared supported set | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 63 | tenant-integration-profile | Adapter selection is observable | No tenant configuration appears in observability output | Given a profile containing non-secret configuration such as a host name, when any ingestion log record, span attribute, or metric label is inspected, then it does not contain that configuration | `tests/test_tenant_integration_profile.py` (task 7.7) | - [ ] |
| 64 | document-ingestion (MODIFIED) | Document Upload | Upload a PDF document | Given an authenticated tenant user with a valid JWT, when they POST a PDF as multipart/form-data, then the response is 201 containing `id`, `filename`, `content_type`, `status: "pending"`, `file_size` | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 65 | document-ingestion (MODIFIED) | Document Upload | Upload an unsupported file type | Given an authenticated tenant user, when they POST a `.exe` file, then the response is 422 and the message indicates the file type is not supported | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 66 | document-ingestion (MODIFIED) | Document Upload | Upload exceeds file size limit | Given an authenticated tenant user, when they POST a 100MB file, then the response is 413 and the message indicates the 50MB limit | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 67 | document-ingestion (MODIFIED) | Document Upload | Upload without a purpose field defaults to query | Given an authenticated tenant user, when they POST a PDF with no `purpose`, then the response is 201 and the stored purpose is `query` | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 68 | document-ingestion (MODIFIED) | Document Upload | Upload with an explicit training purpose | Given an authenticated tenant user, when they POST a PDF with `purpose=training`, then the response is 201 and the stored purpose is `training` | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 69 | document-ingestion (MODIFIED) | Document Upload | Upload with an invalid purpose value is rejected | Given an authenticated tenant user, when they POST with `purpose=invalid-value`, then the response is 422 and the message indicates purpose must be `query` or `training` | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 70 | document-ingestion (MODIFIED) | Document Upload | Platform retention stores the original durably | Given a tenant profile selecting `platform_blob`, when a document is uploaded, then the bytes are written to the durable store, the persisted reference is that store's return value, and `retention_mode` is `platform_blob` | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 71 | document-ingestion (MODIFIED) | Document Upload | Ephemeral retention stores no durable original | Given a tenant profile selecting `ephemeral`, when a document is uploaded and processed, then the response is 201, `retention_mode` is `ephemeral`, and the persisted reference is NULL after a terminal state | `tests/test_document_ingestion.py` (task 3.11) | - [ ] |
| 72 | document-ingestion (MODIFIED) | Async OCR Processing | PDF text extraction succeeds | Given a `pending` document of content type `application/pdf`, when the worker runs and PyMuPDF extracts text, then status becomes `processed` and text spans with character offsets are inserted | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 73 | document-ingestion (MODIFIED) | Async OCR Processing | Image OCR succeeds | Given a `pending` document of content type `image/png`, when the worker runs and Tesseract extracts text, then status becomes `processed` and text spans are inserted | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 74 | document-ingestion (MODIFIED) | Async OCR Processing | OCR processing fails | Given a corrupt `pending` PDF, when the worker runs and PyMuPDF raises, then status becomes `failed` and the record contains an error message | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 75 | document-ingestion (MODIFIED) | Async OCR Processing | The worker resolves bytes from persisted state alone | Given a dispatched job carrying only document id and tenant id, when the worker runs, then it resolves bytes using the recorded `retention_mode` and requires no path, media type, or bytes from the dispatcher | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 76 | document-ingestion (MODIFIED) | Async OCR Processing | Declared media type selects the extractor | Given a document declared `image/png` whose reference ends in `.bin`, when the worker runs, then the image OCR path is selected and the reference is not inspected | `tests/test_ocr_media_type_resolution.py` (task 4.7) | - [ ] |
| 77 | document-ingestion (MODIFIED) | Async OCR Processing | Filename extension is the fallback when the declared type is generic | Given a PDF uploaded as `application/octet-stream` named `report.pdf`, when the worker runs, then the PDF extraction path is selected and the outcome matches pre-change behaviour | `tests/test_ocr_media_type_resolution.py` (task 4.7) | - [ ] |
| 78 | document-ingestion (MODIFIED) | Async OCR Processing | Repeated dispatch performs no second extraction | Given a document already out of `pending`, when processing is dispatched again, then no extraction runs and the span count is unchanged | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 79 | document-ingestion (MODIFIED) | Async OCR Processing | Reprocessing does not duplicate spans or chunks | Given a processed `platform_blob` `purpose='query'` document with known counts, when reprocessed, then both counts equal those of a single run | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 80 | document-ingestion (MODIFIED) | Async OCR Processing | Reprocessing one document does not affect another | Given two processed documents in one tenant schema, when one is reprocessed, then the other's spans and chunks are unchanged | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 81 | document-ingestion (MODIFIED) | Async OCR Processing | Derived data is not deleted when bytes cannot be resolved | Given a processed document whose bytes are unresolvable, when reprocessing is attempted, then it fails before any deletion and existing spans and chunks are unchanged | `tests/test_document_ingestion.py` (task 4.7) | - [ ] |
| 82 | document-ingestion (MODIFIED) | Document provenance and retention metadata | Existing documents remain valid after migration | Given pre-change documents, when the migration is applied, then every row remains readable with `source_type` `platform_upload`, `source_id` `platform-upload`, and `retention_mode` `platform_blob` | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 83 | document-ingestion (MODIFIED) | Document provenance and retention metadata | The migration reaches every existing tenant schema | Given several provisioned tenant schemas, when the migration is applied, then every `tenant_%` schema's `documents` table and `tenant_template.documents` carry the new columns | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 84 | document-ingestion (MODIFIED) | Document provenance and retention metadata | A newly provisioned tenant inherits the columns | Given the migration applied, when a new tenant is provisioned, then its `documents` table carries the new columns | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 85 | document-ingestion (MODIFIED) | Document provenance and retention metadata | Retention mode is constrained to the declared values | Given an attempt to write a `retention_mode` outside `platform_blob`, `ephemeral`, `source_only`, when performed, then it is rejected | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 86 | document-ingestion (MODIFIED) | Document provenance and retention metadata | Duplicate external identities are permitted | Given two documents in one tenant sharing `source_id` and external identity, when both are inserted, then both succeed with no constraint violation | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 87 | document-ingestion (MODIFIED) | Document provenance and retention metadata | No second storage-reference column is introduced | Given the migration, when the columns it adds are enumerated, then none duplicates the existing `blob_path` column's purpose | `tests/test_document_provenance_migration.py` (task 6.2) | - [ ] |
| 88 | document-ingestion (MODIFIED) | Document visibility by ingesting actor | A user sees their own uploads | Given a non-administrative user who has uploaded a document, when they list documents, then their own document is listed | `tests/test_document_visibility.py` (task 6.4) | - [ ] |
| 89 | document-ingestion (MODIFIED) | Document visibility by ingesting actor | A user does not see another user's upload | Given two non-administrative users each having uploaded, when the first lists documents, then the second user's document is not listed | `tests/test_document_visibility.py` (task 6.4) | - [ ] |
| 90 | document-ingestion (MODIFIED) | Document visibility by ingesting actor | A system-ingested document is visible tenant-wide | Given a document whose ingesting actor is a source system, when a non-administrative user lists documents, then that document is listed | `tests/test_document_visibility.py` (task 6.4) | - [ ] |
| 91 | document-ingestion (MODIFIED) | Document visibility by ingesting actor | Listing and retrieval agree | Given a `purpose='query'` system-ingested document and a non-administrative user, when that user asks a question whose answer cites it, then the cited document is also listable by that user | `tests/test_document_visibility.py` (task 6.4) | - [ ] |
| 92 | document-ingestion (MODIFIED) | Document visibility by ingesting actor | Administrators are unaffected | Given a `tenant_admin`, when they list documents, then every non-deleted document in the tenant is listed regardless of ingesting actor | `tests/test_document_visibility.py` (task 6.4) | - [ ] |
| 93 | secret-hygiene (ADDED) | Per-Tenant Integration Credentials Are References Only | No credential value is persisted | Given a profile configured with a secret reference, when every column of the stored row is inspected, then no column contains a credential value and the reference is stored in auditable plain form | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 94 | secret-hygiene (ADDED) | Per-Tenant Integration Credentials Are References Only | A value in a secret field is rejected by schema, not by heuristic | Given a declared secret-reference field carrying a literal credential, when validated, then it is rejected for failing the reference grammar and not by inspecting whether the value resembles a secret | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 95 | secret-hygiene (ADDED) | Per-Tenant Integration Credentials Are References Only | Resolved credentials do not outlive the operation | Given an operation that resolves a tenant credential, when it completes, then the resolved value was not written to any database row, cache, or file | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 96 | secret-hygiene (ADDED) | Per-Tenant Integration Credentials Are References Only | Credential resolution is not reachable from adapter code | Given a source or content-store adapter, when its dependencies are inspected, then it receives already-resolved values and receives neither a reference nor a resolver | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 97 | secret-hygiene (ADDED) | Runtime Credential Resolution Failure Is Explicit | An unresolvable reference errors the profile, not the process | Given a running service and an unresolvable tenant reference, when resolution is attempted, then the profile moves to `error` with a recorded reason and the process continues serving other tenants | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 98 | secret-hygiene (ADDED) | Runtime Credential Resolution Failure Is Explicit | The failure reason carries no credential material | Given a resolution failure, when the recorded reason and emitted log record are inspected, then they name the reference and failure class and contain no credential value or raw provider payload | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |
| 99 | secret-hygiene (ADDED) | Runtime Credential Resolution Failure Is Explicit | Process-level secret-class settings still fail fast | Given `NER_JWT_SECRET` absent from the environment, when the application starts, then startup fails and the per-tenant deviation does not weaken this behaviour | `tests/shared/test_tenant_credential_hygiene.py` (task 7.8) | - [ ] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Content resolution and the working copy (Decision 2) | An agent implements `ephemeral` by holding bytes in memory and handing them to the in-process task, or by passing a path through the dispatch payload — both explicitly rejected alternatives. It would pass a single-process test and fail on restart, on retry, and under any queued dispatcher. | Read the dispatcher contract and confirm it carries only document and tenant identity (row 19). Read the worker and confirm it loads the document and resolves bytes from `retention_mode` (row 75). Run row 40 by restarting or re-invoking the worker after a transient failure and confirm bytes still resolve. Confirm the ephemeral tests run against a real working store, not a stand-in (rows 32–37). |
| 2 | Working-copy deletion (Decision 2, Decision 3) | An agent deletes the working copy only on success, leaving failed documents' bytes resident indefinitely; or nulls the reference without deleting; or deletes before the terminal state, breaking retry. | Verify rows 33 and 34 cover both terminal paths. Inspect the store after a deliberately failed document and confirm the object is gone. Confirm the delete and the reference-null happen in the same step, and that row 40's retry still finds the copy. Confirm the store's independent expiry is configured (task 2.3), not merely intended. |
| 3 | Reprocess ordering (Decision 5) | An agent writes purge-then-resolve, or writes the purge without a document-id predicate, or marks an unresolvable document `failed`. Each destroys or corrupts derived data that was valid. | Read every DELETE added to the processing path and confirm each is parameterised by a single document id and sequenced after a successful resolve. Run rows 39, 80, and 81 and confirm spans, chunks, and status all survive an unresolvable reprocess. |
| 4 | Media-type resolution order (Decision 4) | An agent implements only the declared media type, dropping the filename fallback, or reorders the steps. `application/octet-stream` uploads — common in practice — would route to the wrong extractor, silently changing behaviour for real documents. | Read the resolution function and confirm the order is declared type → filename extension → sniff, with the extension reachable. Run row 77. Diff extractor selection against pre-change behaviour on a sample of real documents. |
| 5 | Profile configuration validation (Decision 8) | An agent implements credential detection by scanning values for secret-looking strings — the approach the spec explicitly forbids — or accepts free-form JSONB and validates nothing. Both leak or falsely reject. | Read the validation code and confirm it rejects on declared key set, declared type, and reference grammar only (rows 49–52, 94). Confirm no regex or entropy check is applied to non-secret values. Confirm row 52 passes with a credential-looking but non-secret string. |
| 6 | Status model transitions (Decision 8) | An agent implements the statuses as a free-form string column with no transition guard, so `draft → active` and `error → active` both succeed and the readiness check is bypassed. | Read the transition guard and confirm each permitted edge is enumerated. Run rows 54, 56, and 57. Attempt a direct `draft → active` write at the persistence layer and confirm it is refused. |
| 7 | Migration reach and column duplication (Decision 6) | An agent applies additive columns to `tenant_template` only, omitting the `DO $$` loop over existing `tenant_%` schemas, as migrations `030` and `034` had to guard against; or introduces a `storage_reference` column alongside `blob_path`, widening the very drift the deferred change exists to close. | Read the migration and confirm both the template statement and the loop are present. Apply against a seeded multi-tenant database and assert per-schema column presence (row 83) and inheritance by a new tenant (row 84). Enumerate added columns and confirm none duplicates `blob_path` (row 87). |
| 8 | Scope creep beyond the foundation | An agent "helpfully" reshapes the `Retriever` signature, creates a `document_sources` table, adds a per-tenant engine router, or begins a pull-source contract — all named as deferred, and all touching code this change must leave alone. | Diff the change set and confirm `src/shared/retrieval/` is untouched (task 8.2). Confirm no `document_sources` table, no per-tenant connection routing beyond the resolver returning the global engine, and no `DocumentSource` pull contract (task 8.3). Confirm the chat path is unmodified. |

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-001 Tenant Data Isolation via Separate Database Schemas | Tenant content lives in per-tenant PostgreSQL schemas; isolation enforced by construction | New tenant-scoped state stays in `tenant_{tid}`; new platform-scoped state stays in `public`. No code path may reach tenant data without the tenant id that entered from the JWT. | Confirm provenance columns land on `tenant_template.documents` and every `tenant_%` schema, and the profile table lands in `public` (rows 44, 83). Grep the ingestion operation and adapters for any tenant id sourced from a request body or source metadata rather than authenticated context (row 7). Confirm the working store's keys are tenant-prefixed (row 27). |
| ADR-003 Per-Tenant Model Serving Topology | Model serving is isolated per tenant | The model plane, including MinIO usage for model artifacts, is out of scope. | Diff the change set and confirm `model_serving/services/model_loader.py` and `training_service/worker.py` are untouched and neither is routed through the content-store boundary. |
| ADR-004 OpenSpec Spec-Driven Development Governance | Every feature traceable from spec to executable evidence | Every acceptance criterion needs an executable artifact that fails when its THEN clause is violated. | Confirm every row in Section 1 has a named artifact before archive, and spot-check that at least rows 2, 33, 39, 52, and 87 fail when the corresponding behaviour is reverted. |
| ADR-007 Chatbot Architecture with Full RAG and Guardrails | Tenant-scoped RAG with citations and guardrails, P95 under 10s | Retrieval is out of scope and must be untouched. The one chat-adjacent effect is the visibility rule, which makes listing agree with what retrieval already returns. | Confirm `src/shared/retrieval/` and `src/chat_api/` retrieval paths are unmodified (task 8.2). Run row 91 and confirm a cited document is listable by the same user. Compare chat p95 on a fixed query set before and after. |

---

## 4. Evidence Requirements

Evidence that **MUST** be collected and logged in Section 5 before this change is archived.
Do not archive while any item below remains unchecked.

### Functional Evidence

- [ ] Rows 1–7: test output showing the ingestion operation owns the row write, is the sole `documents` writer, runs with no HTTP context, and carries purpose, optional metadata, non-synthesised timestamps, and authenticated tenant identity correctly
- [ ] Rows 8–11: test output for the `single_use` declaration, rejection of the `single_use` + `source_only` combination, resolution decided once and recorded, and platform-computed checksum
- [ ] Row 12: full run of `tests/test_document_ingestion.py` and `tests/test_document_content_hash.py`, with a reviewed diff of both files showing edits confined to mock patch targets and fixture DDL
- [ ] Rows 13–17: test output for the reserved `platform-upload` source id, its stability, its reservation against configured sources, the 403 role case, and a static check that the route references no storage client
- [ ] Rows 18–20: test output for default in-process dispatch, a dispatcher contract carrying only identity, and a recording dispatcher observing exactly one dispatch
- [ ] Rows 21–22: static analysis showing no `source_type` / `source_id` / adapter-kind conditional downstream of ingestion, plus equivalent processing output for two documents of different source types
- [ ] Rows 23–27: test output for put/open round-trip, idempotent delete, contract introspection, no precomputed key, and adapter-confined key construction
- [ ] Rows 28–31: test output for retention mode stored not inferred, durable reopen, retention following tenant configuration, and adapter override refused
- [ ] Rows 32–37: end-to-end run **against a real working store instance** — ephemeral processing to `processed`, working copy deleted on success and on failure, durable store untouched, chunks retrievable, NULL reference not a failure
- [ ] Rows 38–40: test output for retained reprocess, explicit failure on an expired ephemeral reprocess with derived data intact, and retry within the window reusing the working copy
- [ ] Rows 41–42: static check that the OCR path never parses the storage reference, plus a passing first-processing run with no durable reference
- [ ] Rows 43–48: test output for default profile existence, `public` placement, readability with an unreadable tenant schema, non-default selection recordable but not activatable, and ingestion using executable adapters regardless
- [ ] Rows 49–52: test output for unknown-key rejection, secret-grammar enforcement, verbatim reference storage, and acceptance of a credential-looking non-secret value
- [ ] Rows 53–57: test output for the five status-model scenarios including the explicit `error` state and terminal `retired`
- [ ] Rows 58–63: test output for administrative reads, cross-tenant resolution refusal, absence of resolved values in rows, logs, spans and metric labels, tenant-facing refusal, and observability content drawn from the declared set
- [ ] Rows 64–71: full document-upload suite output including both retention scenarios
- [ ] Rows 72–81: OCR suite output covering PDF, image, failure, resolution from persisted state, both media-type paths, repeat dispatch, reprocess idempotency, cross-document isolation, and derived-data preservation
- [ ] Rows 82–87: migration applied to a seeded multi-tenant database — per-schema column presence, new-tenant inheritance, retention-mode constraint, permitted duplicate external identities, and no duplicate storage-reference column
- [ ] Rows 88–92: visibility suite output for own uploads, another user's upload, system-ingested tenant-wide visibility, listing/retrieval agreement, and unaffected administrators
- [ ] Rows 93–99: secret-hygiene test output including schema-based rejection and unchanged `NER_JWT_SECRET` startup fail-fast behaviour

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations)
- [ ] All ADR compliance steps in Section 3 confirmed ✓
- [ ] No undocumented architectural patterns introduced
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files)
- [ ] Confirmed no port, repository, or dialect abstraction was introduced over PostgreSQL, pgvector, SQLAlchemy, Celery, MLflow, or model serving, and that `src/shared/retrieval/` is untouched
- [ ] Confirmed no pull-source connector, sync engine, `document_sources` table, per-tenant connection routing, index boundary, or business-database query path was implemented
- [ ] Confirmed the working store is configured with an independent object-lifetime policy, with the chosen duration recorded against approval item A2

### Edge Case Evidence

- [ ] Risk 1 mitigation confirmed — dispatcher carries identity only; worker resolves from `retention_mode`; ephemeral tests run against a real working store
- [ ] Risk 2 mitigation confirmed — working copy deleted on both terminal paths, reference nulled in the same step, store expiry configured
- [ ] Risk 3 mitigation confirmed — resolve precedes purge; every DELETE scoped by document id; unresolvable reprocess leaves data and status intact
- [ ] Risk 4 mitigation confirmed — media-type resolution order read and the `application/octet-stream` PDF case exercised
- [ ] Risk 5 mitigation confirmed — validation rejects on declared schema only; no value-inspection heuristic present
- [ ] Risk 6 mitigation confirmed — status transitions enumerated and guarded; direct `draft → active` refused at the persistence layer
- [ ] Risk 7 mitigation confirmed — migration inspected for both the template statement and the `tenant_%` loop; added columns enumerated for duplication
- [ ] Risk 8 mitigation confirmed — change set diffed for retrieval, `document_sources`, connection routing, and pull-contract scope creep

---

## 5. Evidence Log

Record collected evidence here. Every row in Section 1 must have at least one matching
entry. Do not pre-fill — entries must describe real observations.

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** tenant-pluggable-data-foundation
**Proposal:** `openspec/changes/tenant-pluggable-data-foundation/proposal.md`
**Spec files reviewed:**

- specs/document-ingestion-boundary/spec.md
- specs/original-document-storage/spec.md
- specs/tenant-integration-profile/spec.md
- specs/document-ingestion/spec.md
- specs/secret-hygiene/spec.md

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
| Approval items A1–A3 in proposal.md signed off | - [ ] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [ ] |
| No hallucinated requirements introduced | - [ ] |
| No undocumented patterns used | - [ ] |
| No AI-invented fields, endpoints, or behaviours present | - [ ] |
| Every THEN clause in specs has a corresponding evidence entry | - [ ] |
| Hallucination risk register reviewed and all mitigations confirmed | - [ ] |
| Deferred scope confirmed absent from the implementation | - [ ] |

**Archive approved by:** ___________________________

**Date:** ___________

**Notes:**
<!-- Record the resolutions of approval items A1 (working-store transit), A2 (working-store
     expiry duration), and A3 (tenant-wide visibility of system-ingested documents) here. -->
