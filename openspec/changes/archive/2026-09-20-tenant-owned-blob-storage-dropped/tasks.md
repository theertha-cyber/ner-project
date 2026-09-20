Task groups 1–7 follow the six ordered steps in design.md § Migration Plan. Groups 1–4 are inert by construction: nothing changes tenant-visible behaviour until group 5. Do not reorder them.

Prerequisite: `tenant-postgresql-data-plane` must be archived before group 5, because the `tenant-integration-profile` and `tenant-data-source-control-plane` deltas here modify its requirement text.

## 1. Backend attribution (migration step 1 — inert)

- [ ] 1.1 Add `content_store_kind` (nullable varchar) to the `documents` table in `src/shared/tenant_store/baseline.py`, defaulted for new rows to the platform store's declared kind.
- [ ] 1.2 Add a tenant-store revision under `src/shared/tenant_store/revisions/` that adds the column and backfills every existing row whose storage reference is non-NULL to the platform kind, leaving storage reference, retention mode, and status untouched.
- [ ] 1.3 Add the matching Alembic revision under `alembic/versions/` for the platform-plane tenant schemas.
- [ ] 1.4 Persist the producing store's `kind` alongside the storage reference in `DocumentIngestionService._insert_row`, written in the same statement as the reference.
- [ ] 1.5 Expose the recorded kind on the document read model wherever the storage reference is already read, without exposing it through any tenant-facing API response.
- [ ] 1.6 Verify attribution recording and backfill in `tests/test_content_store_attribution.py`: scenarios 9, 10, 11, 17, 18.

## 2. Route reads and deletes by recorded kind (migration step 2 — inert)

- [ ] 2.1 Add a store registry that resolves a `ContentStore` from a recorded kind, raising a typed error for a kind it cannot resolve. Register the platform MinIO store under its existing `kind`.
- [ ] 2.2 Convert every `open` call site to resolve its store from the document's recorded kind — document content routes in `document_service`, chat-attachment reads in `chat_api`, `services/ocr_worker.py`, and `blob_sync/reopen.py`.
- [ ] 2.3 Convert every `delete` call site the same way, including the conversation hard-delete path that removes attachment objects (ADR-011).
- [ ] 2.4 Make a missing or unresolvable recorded kind fail explicitly rather than falling back to a default store, and confirm an absent kind on a `source_only` or post-deletion `ephemeral` document is not treated as an error.
- [ ] 2.5 Verify read/delete routing in `tests/test_content_store_attribution.py` with a second fake backend registered: scenarios 12, 13, 14, 15, 16, 31, 32.

## 3. The content-store connection provider (migration step 3 — inert)

- [ ] 3.1 Add `PROVIDER_AZURE_BLOB_CONTENT_STORE = "azure_blob_content_store"` to `src/shared/data_sources/providers.py` with its closed config keys (`account`, `container`, optional `prefix`), its `connection_string_ref` secret field, and its own secret kind.
- [ ] 3.2 Reject a draft that shares a secret reference with, or names the same container as, the tenant's `azure_blob` source connection.
- [ ] 3.3 Implement the write-capable connection test: container reachable over TLS; scratch-key round trip whose read returns identical bytes; scratch object removed on every terminal path; lifecycle expiry rule present and scoped to the working prefix with a lifetime no greater than the configured working-copy lifetime. Each failure returns a finite safe reason class naming no container, account, endpoint, or credential.
- [ ] 3.4 Extend the one-active-per-provider constraint and the lifecycle service to cover the new provider, with no parallel activation path.
- [ ] 3.5 Add the control-plane API surface for the provider, accepting it for a tenant of any data-plane mode.
- [ ] 3.6 Verify provider validation and activation in `tests/test_tenant_content_store_connection.py`: scenarios 33, 34, 35, 36, 37, 40, 41, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75.

## 4. The Azure Blob content store adapter (migration step 4 — inert)

- [ ] 4.1 Add `AzureBlobContentStore` under `src/document_service/content_store/` implementing `put`/`open`/`delete` with the synchronous `azure.storage.blob.BlobServiceClient` — not the `.aio` client — declaring `kind = "tenant_azure_blob"`, and register it in the store registry from task 2.1.
- [ ] 4.2 Construct keys inside the adapter under one tenant-scoped durable prefix and one tenant-scoped working prefix, both defined by a single shared constant that task 3.3's lifecycle assertion also reads. Expose no prefix, container, or key rule to any caller.
- [ ] 4.3 Make `get_durable_store()` and `get_working_store()` tenant-scoped, resolving the tenant's `content_store_adapter` selection and its executability, and returning the platform store for every non-executable outcome.
- [ ] 4.4 Add a bounded per-tenant cache of resolved stores, invalidated when a tenant's content-store connection is paused, retired, or replaced.
- [ ] 4.5 Thread the resolved store through `DocumentIngestionService._durable()` / `._working()` and `ocr_worker`, replacing the process-wide instances. Update `reset_stores()` for the tenant-scoped shape.
- [ ] 4.6 Make an unreachable tenant store reject an upload before its bytes are accepted and fail content reads with a finite safe error, with no fallback write, no platform-side buffering, and no effect on service readiness.
- [ ] 4.7 Verify the adapter against Azurite in `tests/test_azure_blob_content_store.py`: scenarios 38, 39.
- [ ] 4.8 Verify routing, isolation, caching, and fail-closed behaviour in `tests/test_tenant_content_store_routing.py`: scenarios 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58.

## 5. Make the selection executable and relax the retention rules (migration step 5 — behaviour change)

- [ ] 5.1 Map `("content_store_adapter", "tenant_azure_blob")` in `src/shared/data_sources/resolver.py` to the content-store provider, not to `PROVIDER_AZURE_BLOB`, with no data-plane-mode condition.
- [ ] 5.2 Consult the resolved content store in `DocumentIngestionService._write_content` and remove the docstring stating that `content_store_adapter` is not consulted.
- [ ] 5.3 Make `RetentionModeNotPermittedForDataPlane` fire only for a `tenant_owned` tenant with no executable content-store selection, and block `azure_postgresql_data_plane` activation on `platform_blob` only under that same condition.
- [ ] 5.4 Reject retiring or pausing the content-store connection of a tenant recording `platform_blob` until its retention mode is changed.
- [ ] 5.5 Widen `SYNC_ALLOWED_RETENTION` in `src/document_service/blob_sync/sync.py` to admit `platform_blob` only when the tenant's content store resolves to its own container, and refuse the sync with a finite safe reason class otherwise.
- [ ] 5.6 Confirm the training worker and model loader still resolve platform storage directly and were not converted to the content-store boundary.
- [ ] 5.7 Verify profile executability and retention rules in `tests/test_tenant_integration_profile.py`: scenarios 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95, 96, 97, 98, 99.
- [ ] 5.8 Verify retention semantics and chat-attachment routing in `tests/test_original_document_storage_routing.py`: scenarios 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30.
- [ ] 5.9 Verify the sync relaxation in `tests/test_azure_blob_source_sync.py`: scenarios 1, 2, 3, 4, 5, 6, 7, 8.
- [ ] 5.10 Verify the residency exclusion in `tests/test_tenant_content_store_routing.py`: scenarios 59, 60.
- [ ] 5.11 Verify pause, retirement, and same-container replacement in `tests/test_tenant_content_store_connection.py`: scenarios 42, 43, 44.

## 6. Portal

- [ ] 6.1 Add the `azure_blob_content_store` form schema and detail route to the data-sources area, omitting the sync-activity section and "Sync now" control.
- [ ] 6.2 Show a safe indication of which content store serves the tenant's uploads, derived from the executable selection rather than the recorded one, naming no container, account, endpoint, or credential.
- [ ] 6.3 State that content stored before activation remains in its original location, without implying activation relocated it.
- [ ] 6.4 Present a finite safe unavailable state on document and chat-attachment surfaces when the tenant's content store is unreachable, keeping the rest of the portal usable.
- [ ] 6.5 Verify the portal surface in `src/portal/src/app/(auth)/settings/data-sources/content-store.test.tsx`: scenarios 76, 77, 78, 79, 80, 81, 82, 83, 84.

## 7. Local stack and documentation

- [ ] 7.1 Add an Azurite service to `docker-compose.yml` as a stand-in tenant container, with a seeded container and a working-prefix lifecycle rule, wired for local `env://` secret resolution only.
- [ ] 7.2 Record a new ADR under `docs/adr/` covering the write-capable content-store provider, content-store residency, and the conditional supersession of ADR-017's "`platform_blob` is rejected for a `tenant_owned` tenant" clause. Do not edit ADR-017.
- [ ] 7.3 State the model-artifact and experiment-tracking residency exclusion in tenant-facing residency documentation under `docs/`.
- [ ] 7.4 Run the full path end to end against Azurite: upload, chat attachment, ephemeral expiry, reprocess, conversation delete.

## 8. Verification & Evidence

- [ ] 8.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 8.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 8.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 8.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 8.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 8.6 Run `openspec validate tenant-owned-blob-storage --type change --strict` and confirm it exits clean before archive.
