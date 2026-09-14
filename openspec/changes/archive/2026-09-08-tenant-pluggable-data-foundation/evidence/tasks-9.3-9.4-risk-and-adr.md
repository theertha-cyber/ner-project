# Tasks 9.3 and 9.4 — hallucination risk register and ADR compliance

## Task 9.3 — Hallucination Risk Register mitigations

| # | Risk | Mitigation confirmed |
|---|---|---|
| 1 | Ephemeral implemented in memory, or a path passed through the dispatch payload | `ProcessingDispatcher.dispatch` takes `(document_id, tenant_id)` and nothing else; `InProcessDispatcher.dispatch` names no bytes, reference, or media type (row 19). `process_document` loads the document and calls `resolve_content`, which branches on the recorded `retention_mode` (row 75). Row 40 re-invokes the worker after a transient failure and the bytes still resolve. Rows 32-37 ran against the live working bucket — **verified passing with real MinIO credentials, 11 passed, 0 skipped** — not a stand-in. |
| 2 | Working copy deleted on success only, or nulled without deleting, or deleted before the terminal state | `_release_working_copy` is called on the `processed` path, the `failed` path, and the unresolvable-bytes path, and it deletes the object and nulls `blob_path` in the same call. Rows 33 and 34 assert both terminal paths against the live bucket. Row 40 confirms the copy survives a non-terminal failure so a retry finds it. **Mutation check:** removing the call from the failure path makes row 34 fail. The independent expiry is configured, not intended: `MinioContentStore(expiry_days=...)` issues `put_bucket_lifecycle_configuration` at construction, and `settings.working_copy_expiry_days` defaults to 1 (approval item A2). |
| 3 | Purge-then-resolve, an unparameterised purge, or an unresolvable document marked `failed` | Every DELETE added to the processing path is in `_purge_derived_data`, both statements carry `WHERE document_id = :id`, and it is called only after `resolve_content` returned bytes. Rows 39, 80, and 81 pass. **Mutation check:** moving the purge above the resolve makes rows 39 and 81 both fail. |
| 4 | Only the declared media type honoured, or the steps reordered | `resolve_media_type` tries declared type, then filename extension, then a content sniff, and returns the first that resolves; the extension branch is reachable because generic types (`application/octet-stream`, `*/*`, empty) fall through by design. Row 77 covers the octet-stream case end to end. **Not done here:** the register also asks for a diff of extractor selection against pre-change behaviour on a sample of real documents. That needs a real document corpus this environment does not have, and is left for the human reviewer. |
| 5 | Credential detection by scanning values | `validate_configuration` checks membership in a closed key set and `isinstance` against a declared type; `validate_secret_references` checks a regex whose scheme comes from a declared allowlist. No entropy check, no pattern scan over non-secret values — asserted by a static check over the module's code lines in row 94. Row 52 passes with `AKIAIOSFODNN7EXAMPLE` in a declared string field. **Mutation check:** adding an "it looks uppercase and long" rejection makes row 52 fail. |
| 6 | Free-form status column with no transition guard | `PERMITTED_TRANSITIONS` enumerates every permitted edge; `assert_transition` is the only way status changes. Rows 54, 56, and 57 pass. A direct write of an undeclared status at the persistence layer is refused by the `CHECK` constraint in migration 039 (`test_the_status_column_rejects_a_value_outside_the_model`). `draft → active` is absent from the map, so activation cannot bypass validation. |
| 7 | Migration reaches only `tenant_template`, or duplicates `blob_path` | Migration 038 issues both the template statement and the `DO $$` loop over `tenant\_%` schemas, from one shared `COLUMNS` list so the two cannot drift. Rows 83 and 84 apply it to a seeded multi-tenant database and assert per-schema presence and inheritance. Row 87 enumerates the added columns. **Mutation check:** adding a `storage_reference` column makes row 87 fail. |
| 8 | Scope creep into deferred work | See `tasks-8.2-8.3-scope-review.md`. `src/shared/retrieval/` and the chat retrieval path have an empty diff; no `document_sources` table; the engine resolver ignores `tenant_id`; no `DocumentSource` pull contract exists. |

## Task 9.4 — ADR compliance

| ADR | Verification step | Result |
|---|---|---|
| ADR-001 Tenant Data Isolation | Provenance columns land on `tenant_template.documents` and every `tenant_%` schema; the profile table lands in `public` | Rows 83 and 44 pass. `test_row_44` asserts `tenant_integration_profiles` exists in `public` and in no schema beginning `tenant_`. |
| ADR-001 | No tenant id sourced from a request body or source metadata | The route reads `request.state.tenant_id` (set by the JWT middleware) into `NormalizedDocument.tenant_id`; the ingestion operation uses that field alone. Row 7 submits source metadata carrying a different tenant identifier and asserts the document lands in the authenticated tenant's schema. |
| ADR-001 | Working-store keys are tenant-prefixed | Row 27: every reference starts `tenants/{tenant_id}/`, and two tenants with the same document id get different references. |
| ADR-003 Per-Tenant Model Serving | `model_serving/services/model_loader.py` and `training_service/worker.py` untouched and not routed through the content store | `git diff --stat main...HEAD -- src/model_serving/ src/training_service/` is empty. Neither imports `src.document_service.content_store`. |
| ADR-004 Spec-Driven Governance | Every Section 1 row has a named artifact; spot-check that rows 2, 33, 39, 52, and 87 fail when the behaviour is reverted | All 99 rows have artifacts, all passing. **Five mutation spot-checks performed, all caught:** a second `documents` INSERT in the route (row 2 — this also exposed and fixed a real gap in the detector, which previously missed `{_schema(tenant_id)}.documents`); removing failure-path cleanup (row 34, standing in for row 33 on the same code path); purge-before-resolve (row 39); a value-inspection heuristic (row 52); a `storage_reference` column (row 87). |
| ADR-007 Chatbot Architecture | Retrieval untouched; a cited document is listable by the same user | `git diff main...HEAD -- src/shared/retrieval/ src/chat_api/services/` is empty. Row 91 passes. **Not done here:** the chat P95 comparison on a fixed query set needs a live LLM backend and a baseline measurement, and is left for the human reviewer. Nothing in this change touches the retrieval or generation path, so no latency effect is expected. |

## Explicitly not confirmed by this agent

Two register/ADR steps need inputs this environment does not have, and are called out rather
than quietly ticked:

- Risk 4's diff of extractor selection over a sample of **real** documents.
- ADR-007's chat P95 comparison before and after.

Approval items A1-A3 in `proposal.md` are product and security decisions and remain
unsigned. Section 6's Audit Record is deliberately left unchecked (task 9.5).
