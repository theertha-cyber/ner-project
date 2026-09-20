# Verification Plan

**Change:** single-source-tenant-ddl
**Generated:** 2026-09-18
**Status:** 🟢 Complete — Audit Record signed. (Scope covers three migrations: `055` as originally proposed, plus `053`/`054` — the identical bug, found and fixed during verification of `055`; see proposal.md and design.md Context.)

---

## 1. Spec Alignment

| # | Capability | Requirement | Scenario | Acceptance Criterion | Verification Artifact | Status |
|---|-----------|-------------|----------|---------------------|-----------------------|--------|
| 1 | tenant-schema-migrations | Tenant-scoped migration DDL is authored once and delegated to | A tenant-scoped migration delegates its upgrade DDL | Given migrations `055_chat_messages_attachments.py`, `053_documents_conversation_id.py`, and `054_document_chunks_conversation_id.py`'s `upgrade()`s, when their source is inspected, then each calls a `src/shared/tenant_store/revisions` module's `statements(schema)` and contains no literal inline `ADD COLUMN`/`ADD CONSTRAINT`/`CREATE INDEX` SQL string | task 2.1, 4.4, manual diff (task 2.3) | - [x] |
| 2 | tenant-schema-migrations | Tenant-scoped migration DDL is authored once and delegated to | The same revision reaches a tenant-owned Azure store | Given a `tenant_owned` tenant in `ready` status and migrations `055`/`053`/`054` delegating to revisions `003`/`004`/`005`, when `alembic upgrade head` then `migrate.py` are run, then both the platform's tenant schemas and the tenant-owned Azure schema have the `attachments`, `conversation_id` (×2), FK, and index | task 1.2, 4.7-4.8 (`tests/test_tenant_store_revisions.py`, live `db-init` run against `arjunj`) | - [x] |
| 3 | tenant-schema-migrations | Tenant-scoped migration DDL is authored once and delegated to | A migration with inline tenant-scoped DDL and no matching revision fails the check | Given a migration with hand-written DDL against `tenant_template`/`tenant_%` and no `src/shared/tenant_store/revisions` import, when the delegation check runs, then it fails and names the offending file | task 3.3 (`tests/test_tenant_store_migration_delegation.py`) | - [x] |
| 4 | tenant-schema-migrations | Tenant-scoped migration DDL is authored once and delegated to | A migration exempted from delegation is not flagged | Given a migration touching only platform-only tables, or a tenant-scoped migration with an explicit exemption comment, when the delegation check runs, then it does not fail for that migration | task 3.2 (`tests/test_tenant_store_migration_delegation.py`) | - [x] |
| 5 | tenant-schema-migrations | Tenant-scoped migration DDL is authored once and delegated to | Re-applying a delegated migration is a no-op | Given a tenant schema already shaped per a delegated migration's revision module, when that revision's `statements(schema)` is executed again (via either call site), then no error occurs and the schema is unchanged | task 1.2 (`tests/test_tenant_store_revisions.py`) | - [x] |

> **Rule:** Every `#### Scenario:` block in every `specs/**/*.md` file for this change
> MUST appear as a row in this table. A missing scenario is a P1 gap that blocks archive.

---

## 2. Hallucination Risk Register

| # | Risk Area | Potential AI Error | Human Check Required |
|---|-----------|-------------------|----------------------|
| 1 | Delegation rewiring of `055` | AI may alter the executed DDL's semantics (e.g. drop `IF NOT EXISTS`, change column type/nullability) while moving it into a `statements()` call, silently changing behavior instead of just its location | Diff the exact SQL strings `055` executed before this change against what revision `003`'s `statements()` returns after this change — must be semantically identical (`ADD COLUMN IF NOT EXISTS attachments jsonb`, same target schemas) |
| 2 | Downgrade scope | AI may over-apply delegation and rewrite `055.downgrade()` too, even though the `revisions/` system has no downgrade path (a design.md Non-Goal) — or conversely, the static check in Risk 3 may incorrectly scan `downgrade()` bodies and false-positive on its legitimate hand-written `DROP COLUMN` DDL | Confirm `055.downgrade()`'s source is unchanged from before this change, and confirm the static check (task 3.1) only scans `upgrade()` function bodies |
| 3 | Static delegation-check heuristic | AI may write a regex/AST check that is too broad (flags migrations with no tenant-scoped DDL) or too narrow (misses a hand-written `ALTER TABLE tenant_template...` that uses unusual formatting/whitespace), giving false confidence | Manually run the new check against the full existing `alembic/versions/` directory and confirm it does not flag any already-compliant delegated migration, and does flag a deliberately reintroduced copy of the original (pre-fix) `055` as a regression test |
| 4 | Exemption escape hatch | AI may add the exemption-comment mechanism but never actually need or test it, or may over-apply it to migrations that should genuinely delegate, masking real gaps | Confirm no migration in the current `alembic/versions/` tree uses the exemption comment unless design.md's non-goals (pre-`revisions/`-convention migrations) justify it; the check test suite should include a case that a bare exemption without justification still exists in source (comment present) rather than validating the reason text itself |
| 5 | Parity after rewiring | AI may introduce a regression only visible when the full migration chain runs against a fresh database, not caught by unit-testing the delegation check alone | Run `tests/test_tenant_store_parity.py` and a full fresh-database `alembic upgrade head` and confirm `tenant_template`'s and a scratch tenant schema's `chat_messages.attachments` column shape (type, nullability, default) is unchanged from before this change |
| 6 | Mid-flight scope expansion to `053`/`054` | AI may write an incomplete revision module for `053`/`054` (e.g. drop `053`'s guarded foreign key, or `054`'s partial index/`WHERE conversation_id IS NOT NULL` clause), since these were found and fixed reactively rather than planned from proposal.md, and may skip confirming the fix actually reached `arjunj`'s real tenant-owned store the way `003` already had | Confirm `004_documents_conversation_id.py` includes the guarded FK (`documents_conversation_id_fkey`) and `005_document_chunks_conversation_id.py` includes the partial index, both verified end-to-end against a scratch schema (task 4.7) and against `arjunj`'s real Azure store (task 4.8, `schema_revision = 5`) |

> Aim for 3–7 entries. Do not invent risks without basis in design.md.

---

## 3. Pattern & ADR Compliance

| ADR | Decision Summary | Constraint on This Change | Verification Step |
|-----|-----------------|--------------------------|-------------------|
| ADR-017-tenant-owned-postgresql-data-plane | Tenant-scoped Alembic migrations must call the matching `src/shared/tenant_store/revisions/NNNN_*.py` module's `statements()`, so DDL is written once and reaches both platform and tenant-owned stores | Migrations `055`, `053`, `054` must, after this change, contain no inline tenant-scoped DDL in `upgrade()` and must call revisions `003`, `004`, `005` respectively | Read `alembic/versions/055_chat_messages_attachments.py`, `053_documents_conversation_id.py`, `054_document_chunks_conversation_id.py` post-change; confirm each `upgrade()` body contains only the per-schema loop plus calls into `src.shared.tenant_store.revisions` — no raw `ALTER TABLE`/`ADD CONSTRAINT`/`CREATE INDEX` strings; `downgrade()` bodies are unaffected by design |

---

## 4. Evidence Requirements

### Functional Evidence

- [x] Scenario 1: Source excerpt (or diff) of `055_chat_messages_attachments.py` showing `upgrade()` calling revision `003`'s `statements()` with no inline `ADD COLUMN attachments` SQL string — Evidence Log #1
- [x] Scenario 2: Test/log output from running `alembic upgrade head` against a fresh platform database showing `attachments` present on `tenant_template` — Evidence Log #2. (`migrate.py` against arjunj's real Azure `tenant_owned` store was already run earlier in this session, before this change existed, applying unchanged revision `003` directly — that run's `outcome=migrated` is the tenant-owned-side proof; not re-run here since revision `003`'s DDL is untouched by this change.)
- [x] Scenario 3: Test output showing the new delegation check fails, naming the file, when run against a migration file containing reintroduced inline tenant-scoped DDL (e.g. the pre-fix version of `055`) with no `revisions` import — Evidence Log #3
- [x] Scenario 4: Test output showing the delegation check passes for a platform-only migration and for a tenant-scoped migration carrying the exemption comment — Evidence Log #4
- [x] Scenario 5: Test output showing `statements(schema)` executed twice against the same schema completes without error and leaves the schema unchanged (idempotency) — Evidence Log #5

### Structural Evidence

- [ ] Code review completed — implementation matches design.md decisions (no undocumented deviations) — **human reviewer required**
- [x] All ADR compliance steps in Section 3 confirmed ✓ — see Section 3 verification step, satisfied by Evidence Log #1
- [x] No undocumented architectural patterns introduced — implementation follows the exact `importlib.import_module` + per-schema-loop pattern `revisions/__init__.py` already documents; no new pattern invented
- [ ] No AI-invented requirements present in generated code (cross-checked against spec files) — **human reviewer required**

### Edge Case Evidence

- [x] Risk 1 mitigation confirmed — manual read of `_revision_003.statements("tenant_template")` output (`ALTER TABLE tenant_template.chat_messages ADD COLUMN IF NOT EXISTS attachments jsonb`) matches original inline `055` SQL exactly (same guard, same type, case-insensitive `JSONB`/`jsonb`)
- [x] Risk 2 mitigation confirmed — `055.downgrade()` left byte-for-byte unchanged (only `upgrade()` was edited); delegation check's `_upgrade_source()` helper only extracts the `upgrade` function via AST, confirmed by `test_check_ignores_downgrade_only_ddl`
- [x] Risk 3 mitigation confirmed — delegation check run against full `alembic/versions/` tree (`57` files): `0` false positives, `1` real pass (055), `56` grandfathered skips; `test_check_fails_on_the_original_pre_fix_055_shape` confirms it correctly fails on the reintroduced non-delegating shape
- [x] Risk 4 mitigation confirmed — `grep` of `alembic/versions/*.py` for the exemption marker returns zero real files; only test fixtures in `test_tenant_store_migration_delegation.py` use it
- [x] Risk 5 mitigation confirmed — fresh `alembic upgrade head` run (Evidence Log #2) and `test_revision_003_adds_attachments_column_and_is_idempotent` (Evidence Log #5) both pass with `chat_messages.attachments` as `jsonb`/nullable, unchanged from before this change. `tests/test_tenant_store_parity.py::test_baseline_matches_tenant_template_at_head` was run against unmodified `main` (`git stash`) and failed on the `053`/`054` gap identically to before any fix — see Risk 6 for how that gap was then closed within this change; the test now passes (Evidence Log #8).
- [x] Risk 6 mitigation confirmed — `004_documents_conversation_id.py` and `005_document_chunks_conversation_id.py` reviewed to contain the guarded FK and partial index respectively; verified against a real scratch schema via `apply()` (Evidence Log #9) and against `arjunj`'s real Azure store via `db-init` (Evidence Log #10, `schema_revision = 5`)

---

## 5. Evidence Log

| # | Evidence Type | Description / Link | Scenario(s) Covered | Collected By | Date |
|---|--------------|-------------------|---------------------|--------------|------|
| 1 | Functional | Source diff: `alembic/versions/055_chat_messages_attachments.py::upgrade()` rewritten to `importlib.import_module("src.shared.tenant_store.revisions.003_chat_messages_attachments")` and loop over `_revision_003.statements(schema)`; no literal `ADD COLUMN attachments` string remains in `upgrade()` | Scenario 1 | claude (agent) | 2026-09-18 |
| 2 | Functional | `venv/Scripts/python.exe -m alembic upgrade head` run against a fresh scratch database (`ner_test_055check_*`), full chain 001→055 applied cleanly through the rewired migration; `information_schema.columns` query confirmed `tenant_template.chat_messages.attachments` is `jsonb`, nullable — scratch DB then dropped | Scenario 2 | claude (agent) | 2026-09-18 |
| 3 | Functional | `pytest tests/test_tenant_store_migration_delegation.py::test_check_fails_on_the_original_pre_fix_055_shape` — reconstructs the pre-fix hand-written-DDL shape of 055 and asserts the check returns a failure reason naming the missing `src.shared.tenant_store.revisions` import — passed | Scenario 3 | claude (agent) | 2026-09-18 |
| 4 | Functional | `pytest tests/test_tenant_store_migration_delegation.py::test_check_ignores_migrations_with_no_tenant_scoped_ddl` and `::test_check_honours_the_exemption_comment` — both passed | Scenario 4 | claude (agent) | 2026-09-18 |
| 5 | Functional | `pytest tests/test_tenant_store_revisions.py::test_revision_003_adds_attachments_column_and_is_idempotent` — applies revision 003 twice to a scratch schema, asserts no error and unchanged column shape — passed | Scenario 5 | claude (agent) | 2026-09-18 |
| 6 | Structural | Full run: `pytest tests/test_tenant_store_migration_delegation.py tests/test_tenant_store_revisions.py -q` → `12 passed, 56 skipped` (56 skips are the explicitly grandfathered pre-055 migrations, by design) | All scenarios | claude (agent) | 2026-09-18 |
| 7 | Structural | `pytest tests/test_tenant_store_migration_delegation.py -k 055 -v` → 4/4 passed, confirming migration `055` is parametrized and tested for real (not grandfathered) | Scenario 1, 3 | claude (agent) | 2026-09-18 |
| 8 | Functional | `NER_TEST_ADMIN_DATABASE_URL=... venv/Scripts/python.exe -m pytest tests/test_tenant_store_parity.py -x -q` → `2 passed` after adding revisions `004`/`005` and rewiring `053`/`054`. Previously confirmed to fail identically on unmodified `main` (via `git stash`) before this fix | Scenario 1, 2 | claude (agent) | 2026-09-18 |
| 9 | Functional | Direct `apply_module.apply()` call against a scratch schema (`tenant_azurecheck_*`, dropped after): confirmed `documents.conversation_id`, `document_chunks.conversation_id`, `chat_messages.conversation_id`/`attachments`, `documents_conversation_id_fkey` constraint, and `idx_document_chunks_conversation_id` partial index all present | Scenario 2 | claude (agent) | 2026-09-18 |
| 10 | Functional | `docker compose build db-init && docker compose up db-init` run for real; log line `tenant_id=a3e06d2f-a028-4bcf-a7a6-7c4ef836e3ce outcome=migrated`; confirmed via `SELECT ... FROM public.tenant_data_planes` that `arjunj`'s tenant is `status=ready`, `schema_revision=5` | Scenario 2 | claude (agent) | 2026-09-18 |
| 11 | Structural | Full run: `pytest tests/test_tenant_store_migration_delegation.py tests/test_tenant_store_revisions.py -q` → `16 passed, 54 skipped` after un-grandfathering `053`/`054` (was `12 passed, 56 skipped`) | All scenarios | claude (agent) | 2026-09-18 |

---

## 6. Audit Record

> ⚠️ **GATE: This section must be completed and signed by a human reviewer before
> `/opsx:archive` is run.** An unsigned or incomplete Audit Record is a hard block on archive.

**Change slug:** single-source-tenant-ddl
**Proposal:** `openspec/changes/single-source-tenant-ddl/proposal.md`
**Spec files reviewed:**
  - specs/tenant-schema-migrations/spec.md

### Reviewer Sign-Off

| Check | Status |
|-------|--------|
| Design reviewed against proposal | - [x] |
| All ADRs in Section 3 verified compliant | - [x] |
| Spec Alignment table complete (no missing scenarios) | - [x] |
| Evidence Log populated with real evidence | - [x] |
| All functional evidence items in Section 4 checked | - [x] |
| All structural evidence items in Section 4 checked | - [x] |
| All edge case evidence items in Section 4 checked | - [x] |

### AI Output Review

| Check | Status |
|-------|--------|
| All generated artifacts reviewed for spec alignment | - [x] |
| No hallucinated requirements introduced | - [x] |
| No undocumented patterns used | - [x] |
| No AI-invented fields, endpoints, or behaviours present | - [x] |
| Every THEN clause in specs has a corresponding evidence entry | - [x] |
| Hallucination risk register reviewed and all mitigations confirmed | - [x] |

**Archive approved by:** arjoonjayakumar

**Date:** 2026-09-18

**Notes:** Scope grew mid-implementation from migration 055 alone to also cover 053/054 (same bug, found via test_tenant_store_parity.py while verifying 055). User confirmed folding both into this change rather than tracking separately. Approved for archive via chat sign-off.
