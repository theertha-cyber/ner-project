## Why

Migration `055_chat_messages_attachments` hand-wrote its `ALTER TABLE ... ADD COLUMN attachments` DDL directly in the Alembic migration instead of calling a `src/shared/tenant_store/revisions/` module, as Design Decision 5 of `tenant-postgresql-data-plane` (ADR-017) requires. No matching revision module was shipped in that PR, so `migrate.py` never applied the column to `tenant_owned` Azure data-plane databases. Tenant `arjunj`'s chat broke (`UndefinedColumnError: column m.attachments does not exist`) while platform-hosted tenants worked fine. A revision module (`003_chat_messages_attachments`) was added out-of-band to unblock the tenant, but migration `055` still hand-writes its own copy of the same DDL — two definitions of one change, exactly the drift the convention exists to prevent, and nothing currently enforces the convention.

While verifying the fix, `tests/test_tenant_store_parity.py` was found to fail identically on unmodified `main` — the exact same bug already existed in migrations `053_documents_conversation_id` and `054_document_chunks_conversation_id` (their `conversation_id` columns, FK, and index were also missing from any revision module, so `arjunj`'s tenant-owned store was missing them too, silently, with no error surfaced yet because nothing had exercised that code path). Folded into this change rather than tracked separately since it's the identical bug, fixed with the identical pattern, in migrations that shipped alongside `055` in the same feature area (conversation-scoped chat attachments/retrieval).

## What Changes

- Rewire `alembic/versions/055_chat_messages_attachments.py`'s `upgrade()` to import `src/shared/tenant_store/revisions/003_chat_messages_attachments.py` and call its `statements(schema)` inside the migration's existing `tenant_template` + `pg_namespace` loop, instead of hand-written SQL. `055.downgrade()` is left unchanged — the `revisions/` system has no downgrade path at all (tenant-owned stores are only ever moved forward), so there is nothing for a hand-written downgrade to drift against; see design.md.
- Rewire `alembic/versions/053_documents_conversation_id.py` and `alembic/versions/054_document_chunks_conversation_id.py`'s `upgrade()`s the same way, against two new revision modules (`004_documents_conversation_id`, `005_document_chunks_conversation_id`) — same bug, same fix, found during verification of the `055` fix.
- Add a repo-level static check (test) that fails when a tenant-scoped Alembic migration's `upgrade()` body contains DDL keywords that don't route through a `src/shared/tenant_store/revisions` module, so a future migration can't skip the revision module the way `053`, `054`, and `055` did. Pre-existing migrations are grandfathered by explicit filename except `053`, `054`, and `055`, which are the motivating cases and must pass for real.
- No schema/data change — the resulting DDL applied to any schema is byte-identical to what `053`/`054`/`055` and revisions `003`/`004`/`005` each already produce today.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `tenant-schema-migrations`: adds the requirement that a tenant-scoped Alembic migration's DDL is authored once, in a `src/shared/tenant_store/revisions` module, and referenced (not duplicated) by the Alembic migration — closing the gap that let migrations `053`, `054`, and `055` ship without updating `migrate.py`'s Azure tenant-owned path.

## Impact

- `alembic/versions/053_documents_conversation_id.py`, `054_document_chunks_conversation_id.py`, `055_chat_messages_attachments.py` — each rewired to call a revision module.
- `src/shared/tenant_store/revisions/003_chat_messages_attachments.py` (pre-existing), `004_documents_conversation_id.py`, `005_document_chunks_conversation_id.py` (new) — the single-source DDL definitions.
- New test `tests/test_tenant_store_migration_delegation.py` enforcing the single-source convention; extension to `tests/test_tenant_store_revisions.py`.
- `tests/test_tenant_store_parity.py`, which failed on unmodified `main` (missing `conversation_id` columns from `053`/`054`), now passes.
- Tenant `arjunj`'s Azure tenant-owned store migrated live to `schema_revision=5` (`003`+`004`+`005` applied) via `docker compose up db-init`.
- No runtime behavior change for any already-migrated platform-hosted database; this is a source-level de-duplication plus a real data-plane fix for `tenant_owned` stores that were missing columns.

## Open Questions

- Should the new enforcement check be a static/AST check (scan migration source for raw DDL keywords) or a runtime check (diff the DDL the migration executes against the revision module's `statements()` output on a scratch schema)? Resolved during design: static AST-based check on `upgrade()` only, `downgrade()` never scanned.
- Should this pass also retrofit any other pre-existing tenant-scoped migrations that predate the `revisions/` convention (e.g., migrations shipped before `002_main_feature_backlog`'s backlog catch-up)? Scope-limited to `053`/`054`/`055` (all three now fixed) plus the new enforcement check for future migrations; other pre-`revisions/`-convention migrations remain grandfathered and out of scope — flagged as a possible follow-up audit.
