## 1. Revision module: verify upgrade coverage

- [x] 1.1 Confirm `src/shared/tenant_store/revisions/003_chat_messages_attachments.py`'s `statements(schema)` produces DDL identical to `055`'s current inline `upgrade()` SQL (same `ADD COLUMN IF NOT EXISTS attachments jsonb` on `tenant_template` and every `tenant_%` schema).
- [x] 1.2 Unit test the revision module's `statements()` against a scratch schema (add to or extend `tests/test_tenant_store_revisions.py`).

## 2. Rewire migration 055's upgrade to delegate

- [x] 2.1 Rewrite `alembic/versions/055_chat_messages_attachments.py`'s `upgrade()` to import `src.shared.tenant_store.revisions` revision `003` and execute its `statements(schema)` inside the existing `tenant_template` + `pg_namespace` per-schema loop, removing the inline `ALTER TABLE ... ADD COLUMN` SQL strings.
- [x] 2.2 Leave `055.downgrade()` unchanged — no revision-module delegation for downgrades (see design.md Non-Goals: the `revisions/` system has no downgrade path, so there is nothing for `downgrade()` to drift against).
- [x] 2.3 Confirm `055.upgrade()`'s executed SQL text is semantically identical to before (same `IF NOT EXISTS`/idempotent guards, same target schema set) — diff old vs. new statement strings manually.

## 3. Delegation enforcement check

- [x] 3.1 Write a static check (new test, e.g. `tests/test_tenant_store_migration_delegation.py`) that scans each `alembic/versions/*.py` file's `upgrade()` function body only (not `downgrade()`) for tenant-scoped DDL (references to `tenant_template.` or the `pg_namespace`/`tenant_%` per-schema loop pattern) and asserts the file imports from `src.shared.tenant_store.revisions`, unless the file carries an explicit `# tenant-store-revision: exempt — <reason>` comment.
- [x] 3.2 Run the check against the full current `alembic/versions/` tree; confirm no existing delegated migration is falsely flagged, and confirm migrations predating the `revisions/` convention are covered by the exemption path (or explicitly excluded per design.md's non-goals) rather than failing the build.
- [x] 3.3 Add a regression case: a fixture migration file reproducing the pre-fix (hand-written DDL, no `revisions` import) shape of `055`, asserting the check fails and names that file.

## 4. Extend the fix to migrations 053/054 (same bug, found during verification)

- [x] 4.1 While verifying task 2.3 against a fresh database, run `tests/test_tenant_store_parity.py`; discover it fails on unmodified `main` (missing `documents.conversation_id` / `document_chunks.conversation_id` from `baseline.py`). Confirm via `git stash` that the failure is identical with and without this change's `055` fix — i.e. it is a separate, pre-existing gap, not a regression.
- [x] 4.2 Add `src/shared/tenant_store/revisions/004_documents_conversation_id.py`, mirroring `alembic/versions/053_documents_conversation_id.py`'s DDL (column add + guarded foreign key to `conversations`).
- [x] 4.3 Add `src/shared/tenant_store/revisions/005_document_chunks_conversation_id.py`, mirroring `alembic/versions/054_document_chunks_conversation_id.py`'s DDL (column add + partial index).
- [x] 4.4 Rewrite `053.upgrade()` and `054.upgrade()` to import and delegate to revisions `004` and `005` respectively, same pattern as `055`; leave both `downgrade()`s unchanged (same Non-Goals rationale as `055`).
- [x] 4.5 Un-grandfather `053_documents_conversation_id.py` and `054_document_chunks_conversation_id.py` in `tests/test_tenant_store_migration_delegation.py`'s `GRANDFATHERED_MIGRATIONS` set; extend the "motivating migrations are not grandfathered" test to cover both.
- [x] 4.6 Confirm `tests/test_tenant_store_parity.py` now passes.
- [x] 4.7 Verify end-to-end against a real scratch schema (`apply()` called directly, not just the parity comparison): confirm `documents.conversation_id`, `document_chunks.conversation_id`, the `documents_conversation_id_fkey` constraint, and `idx_document_chunks_conversation_id` index all appear correctly.
- [x] 4.8 Run `docker compose build db-init && docker compose up db-init` and confirm `arjunj`'s tenant-owned store reaches `schema_revision = 5`, `status = ready` in `public.tenant_data_planes`.

## 5. Verification & Evidence

- [x] 5.1 Run all acceptance-criteria tests for every scenario in
         verification.md § Spec Alignment and confirm all pass.
- [x] 5.2 Collect functional evidence (screenshot / test output / log) for each
         scenario — record one entry per row in verification.md § Evidence Log.
- [x] 5.3 Confirm every Hallucination Risk mitigation step in
         verification.md § Hallucination Risk Register.
- [x] 5.4 Confirm all ADR compliance steps in
         verification.md § Pattern & ADR Compliance.
- [x] 5.5 Complete Audit Record sign-off in verification.md § Audit Record
         (human reviewer required — this task cannot be marked complete by an agent). Signed by arjoonjayakumar, 2026-09-18.
- [x] 5.6 Run `openspec validate single-source-tenant-ddl --type change --strict` and confirm
         it exits clean before archive. (`Change 'single-source-tenant-ddl' is valid`.)
