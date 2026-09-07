## 1. Hygiene — no behaviour change

Land and verify this group alone. Nothing here changes observable behaviour, so a later bisect separates mechanical substitution from real work.

- [x] 1.1 Add a single shared `schema_for_tenant(tenant_id)` helper in `src/shared/` and replace the ten local `_schema` definitions (document service API, OCR worker, annotation service ×5, chat API ×2, extraction service ×2) with imports of it. Output must be byte-identical for every input.
- [x] 1.2 Route database engine acquisition through one resolver in `src/shared/database.py` that still returns today's process-global engine. No call site changes what it does with the engine.
- [x] 1.3 Run the full test suite with no test file modified and confirm the pass/fail set is identical to the pre-change baseline. Record the baseline diff as evidence.

## 2. Content-store boundary

- [x] 2.1 Define the content-store contract with exactly three operations — put returning an opaque storage reference or nothing, open by reference, delete by reference. The contract must name no bucket, container, endpoint, region, or credential.
- [x] 2.2 Implement the platform MinIO adapter over the existing `MinioStorageClient`, with key construction moved inside the adapter and a delete operation exposed. Support two configured instances: durable and working.
- [x] 2.3 Configure the working store instance with an independent object-lifetime policy so an abandoned working copy expires without depending on the application. Record the chosen duration against approval item A2.
- [ ] 2.4 Verify rows 23–27 in `tests/test_content_store.py` (reference round-trip, idempotent delete, contract introspection, no precomputed key, key construction confined to the adapter).

## 3. Ingestion boundary and upload adapter

Do not split this group across releases — a half-extracted use case with the route still writing storage directly leaves `documents` with two writers holding different retention behaviour.

- [x] 3.1 Define the normalized document contract: tenant identity, filename, content access, purpose, ingesting actor, source reference (`source_type`, `source_id`, optional external identity, version, source timestamps, opaque metadata), optional declared media type and size. Retention is not an adapter-supplied field.
- [x] 3.2 Define the declared content-acquisition capability (`single_use` / `reopenable`) and have the upload adapter declare `single_use`.
- [x] 3.3 Implement `DocumentIngestionService.ingest` in a new `src/document_service/ingestion/` package: id generation, extension and size validation, checksum via the existing `compute_content_hash`, duplicate identification, retention resolution from the tenant profile, rejection of `single_use` + `source_only`, content store put against the durable or working instance, row insert, dispatch. It must reference no HTTP type, no storage client construction, and no provider API.
- [x] 3.4 Define the dispatcher contract carrying document identity and tenant identity only — no bytes, no storage reference, no media type — with an in-process default preserving today's `asyncio.create_task` behaviour.
- [x] 3.5 Thin the upload route in `src/document_service/api/v1/documents.py` to an adapter: keep tenant and role resolution, the role-to-purpose policy, multipart handling, and status mapping; remove key construction, the storage client, the row insert, and the direct OCR trigger. Response body and status codes unchanged.
- [x] 3.6 Write `source_type='platform_upload'` and the reserved `source_id='platform-upload'` on every upload, and reserve that identifier against future configured sources.
- [ ] 3.7 Verify rows 1–7 in `tests/test_ingestion_boundary.py` (ingestion operation owns the row write, sole-writer static check, HTTP-free invocation, purpose carriage, absent optional metadata, non-synthesised timestamps, adapter cannot assert tenant).
- [ ] 3.8 Verify rows 8–11 in `tests/test_ingestion_boundary.py` (upload declares `single_use`, incompatible combination rejected, resolution decided once and recorded, platform-computed checksum).
- [ ] 3.9 Verify rows 12–17 in `tests/test_ingestion_boundary.py` and confirm every existing scenario in `tests/test_document_ingestion.py` and `tests/test_document_content_hash.py` still passes with edits confined to mock patch targets and fixture DDL, and record the reviewed diff as evidence (unchanged behaviour, reserved source recorded, identifier stable, identifier reserved, role policy at the boundary, route references no store).
- [ ] 3.10 Verify rows 18–20 in `tests/test_ingestion_boundary.py` (default dispatch unchanged, dispatch carries no content, recording dispatcher observes exactly one dispatch).
- [ ] 3.11 Verify rows 64–71 in `tests/test_document_ingestion.py` (the six existing upload scenarios unmodified, plus the two retention scenarios).

## 4. Processing pipeline corrections

- [x] 4.1 Change `process_document` to take document identity and tenant identity, load the document, and resolve bytes by its recorded `retention_mode` — durable store for `platform_blob`, working store for `ephemeral`. `source_only` resolution raises an explicit not-yet-supported error in this change.
- [x] 4.2 Replace the `blob_path.split(".")` extractor selection with media-type resolution ordered declared media type → filename extension → content sniff. Remove or make authoritative the dead `content_type` parameter on `process_document` and `trigger_ocr`.
- [x] 4.3 Make the transition to `processing` conditional on the document still being `pending`.
- [x] 4.4 Order reprocessing as resolve-then-purge: delete the document's existing text spans and chunks only after bytes are successfully resolved, scoped by document id only. Do not touch the delete-document path.
- [x] 4.5 Delete the working copy and null the persisted storage reference when an `ephemeral` document reaches `processed` or `failed`.
- [x] 4.6 Make a reprocess request whose bytes are unresolvable fail explicitly, leaving spans, chunks, and document status unchanged.
- [ ] 4.7 Verify rows 72–81 in `tests/test_document_ingestion.py` and `tests/test_ocr_media_type_resolution.py` (three existing OCR scenarios, resolution from persisted state, both media-type resolution paths, repeat dispatch no-op, reprocess idempotency, cross-document isolation, derived data preserved when bytes are gone).
- [ ] 4.8 Verify rows 41–42 in `tests/test_content_store.py` (OCR never parses the storage reference; processing succeeds with no durable reference).

## 5. Retention lifecycle

- [x] 5.1 Implement the three retention modes and record the resolved value on the document. Reject any value outside `platform_blob`, `ephemeral`, `source_only` at the database level.
- [ ] 5.2 Verify rows 28–31 in `tests/test_retention_lifecycle.py` (mode stored not inferred, platform retention reopens from the durable store, retention follows tenant configuration, adapter cannot override).
- [ ] 5.3 Verify rows 32–37 in `tests/test_retention_lifecycle.py` against a **real working store instance**, not an in-memory stand-in (ephemeral end to end, working copy deleted on success, deleted on failure, durable store untouched, ephemeral query document retrievable, NULL reference is not a failure).
- [ ] 5.4 Verify rows 38–40 in `tests/test_retention_lifecycle.py` (retained document reprocesses, expired ephemeral reprocess fails explicitly with derived data intact, retry within the window reuses the working copy).

## 6. Schema — provenance, retention, visibility

- [x] 6.1 Write the Alembic migration adding `origin`, `source_type`, `source_id`, `external_id`, `source_version`, `source_created_at`, `source_modified_at`, `origin_metadata`, `retention_mode`, and the ingesting-actor kind to `tenant_template.documents`, all additive and defaulted, with a `DO $$` loop over `tenant_%` schemas following the `030`/`034` pattern. Constrain `retention_mode` to the three declared values. No unique constraint on the external identity. No foreign keys. No new column duplicating `blob_path`.
- [ ] 6.2 Verify rows 82–87 in `tests/test_document_provenance_migration.py` (existing rows readable with defaults including `source_id='platform-upload'` and `retention_mode='platform_blob'`, every `tenant_%` schema carries the columns, new tenant inherits them, retention mode constrained, duplicate external identities permitted, no second storage-reference column).
- [x] 6.3 Narrow the non-administrative list filter in `list_documents` so it applies only to documents whose ingesting actor is a human; system-ingested documents are visible tenant-wide.
- [ ] 6.4 Verify rows 88–92 in `tests/test_document_visibility.py` (own uploads visible, another user's upload hidden, system-ingested visible tenant-wide, listing and retrieval agree, administrators unaffected).

## 7. Control plane — integration profiles

- [ ] 7.1 Write the migration creating the integration-profile table in `public`, holding adapter selections, typed non-secret configuration, typed secret references, and status. Backfill a default profile per existing tenant selecting the platform adapters.
- [ ] 7.2 Implement the typed per-adapter configuration schema with a closed key set and declared types, and secret-reference fields validated against a `<scheme>://<path>` grammar. No heuristic credential detection anywhere.
- [ ] 7.3 Implement the status model `draft → validated → active → paused → error → retired` with the permitted transitions only; activation from `draft` refused, recovery from `error` only through revalidation, `retired` terminal.
- [ ] 7.4 Implement defaults-only execution: any recorded non-default adapter selection may be stored but cannot be activated, and ingestion always uses executable adapters regardless of what is recorded.
- [ ] 7.5 Implement the secret-reference resolution seam: resolution takes tenant identity and reference, reads the reference only from that tenant's own profile, resolves once at the edge, and passes resolved values into an immutable tenant-bound context. Adapters receive values, never references or a resolver. An unresolvable reference moves the profile to `error` with a sanitised reason.
- [ ] 7.6 Record source type, content-store kind, and retention mode on ingestion observability output using values from the declared set only, and confirm no tenant configuration reaches a log record, span attribute, or metric label.
- [ ] 7.7 Verify rows 43–63 in `tests/test_tenant_integration_profile.py` (profile existence and `public` placement, readable with unreadable tenant schema, non-default recordable but not activatable, ingestion uses executable adapters, unknown key rejected, secret grammar enforced, valid reference stored verbatim, no value inspection, five status-model scenarios, admin reads, cross-tenant resolution, no persisted or logged secrets, tenant-facing refusal, observability content).
- [ ] 7.8 Verify rows 93–99 in `tests/shared/test_tenant_credential_hygiene.py` (no persisted credential, schema-based rejection, resolved values do not outlive the operation, adapters hold no resolver, profile errors rather than process failure, sanitised reason) and confirm the existing `NER_JWT_SECRET` startup fail-fast test passes unmodified.

## 8. Architectural invariants

- [ ] 8.1 Verify rows 21–22 in `tests/test_pipeline_source_neutrality.py` (no `source_type`, `source_id`, or storage-adapter-kind conditional exists in the OCR worker, chunking, embedding, extraction, retrieval, or chat modules; two documents from different source types produce equivalent spans and equal chunk counts).
- [ ] 8.2 Confirm by review that no port, repository, or dialect abstraction was introduced over PostgreSQL, pgvector, SQLAlchemy, Celery, MLflow, or model serving, and that `src/shared/retrieval/` is untouched by this change.
- [ ] 8.3 Confirm by review that no pull-source connector, sync engine, tenant-hosted database routing, index boundary, or business-database query path was implemented, and that no `document_sources` table was created.

## 9. Verification & Evidence

- [ ] 9.1 Run all acceptance-criteria tests for every scenario in verification.md § Spec Alignment and confirm all pass.
- [ ] 9.2 Collect functional evidence (screenshot / test output / log) for each scenario — record one entry per row in verification.md § Evidence Log.
- [ ] 9.3 Confirm every Hallucination Risk mitigation step in verification.md § Hallucination Risk Register.
- [ ] 9.4 Confirm all ADR compliance steps in verification.md § Pattern & ADR Compliance.
- [ ] 9.5 Complete Audit Record sign-off in verification.md § Audit Record (human reviewer required — this task cannot be marked complete by an agent).
- [ ] 9.6 Run `openspec validate tenant-pluggable-data-foundation --type change --strict` and confirm it exits clean before archive.
