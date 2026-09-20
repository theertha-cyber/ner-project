## Context

`src/shared/tenant_store/` (ADR-017, Design Decision 5) already establishes the intended shape: a tenant-scoped table change is written once, as a `src/shared/tenant_store/revisions/NNNN_<name>.py` module exposing `REVISION: int` and `statements(schema: str) -> list[str]`. A tenant-scoped Alembic migration is supposed to call that module's `statements()` inside its own `tenant_template` + `pg_namespace` loop (for platform-hosted tenants), and `src/shared/tenant_store/migrate.py` separately calls `apply.py`, which applies the same pending revisions to each `tenant_owned` tenant's remote Azure store.

Migration `055_chat_messages_attachments.py` did not follow this: it hand-wrote its own `ALTER TABLE ... ADD COLUMN attachments jsonb` DDL directly, with no matching revision module. `migrate.py` had nothing new to apply to Azure-hosted tenant stores, so tenant `arjunj` (mode `tenant_owned`) never got the column while platform-hosted tenants did — a full chat outage for that tenant (`asyncpg.exceptions.UndefinedColumnError: column m.attachments does not exist`). A revision module, `003_chat_messages_attachments.py`, was added out-of-band and `migrate.py` was re-run to fix the immediate outage; `055` itself was left untouched, so today the same DDL exists in two places by hand.

`tests/test_tenant_store_parity.py` exists specifically to catch tenant-scoped tables drifting from `baseline.py` + revisions, but it does not check that an Alembic migration's own DDL matches a revision module's output — it only compares end-state schema shape after both paths have (separately) been run to head. It caught nothing here because migration `055`'s hand-written DDL happens to produce the same end shape as revision `003` — the problem isn't a shape mismatch, it's that revision `003` didn't exist until it was manually added after the outage.

While implementing the `055` fix, running `test_tenant_store_parity.py` (blocked locally at first by an unrelated interpreter issue — the repo's ambient `python` resolved a namespace package shadowing the real `alembic` install; `venv/Scripts/python.exe`, which has `alembic` actually installed, does not have this problem) surfaced that it **fails on unmodified `main`**, independent of this change: `baseline.py` is missing `documents.conversation_id` and `document_chunks.conversation_id`. Migrations `053_documents_conversation_id.py` and `054_document_chunks_conversation_id.py` — which shipped alongside `055` in the same conversation-scoped-attachments work — have the identical defect: hand-written DDL, no matching revision module. Confirmed via `git stash` (test fails identically with and without the `055` fix applied) that this is a separate, pre-existing instance of the same bug, not something this change introduced. Folded into this change's scope rather than deferred: same root cause, same fix shape, same PR-sized blast radius, and leaving it out would mean `tests/test_tenant_store_parity.py` stays red even after this change merges.

## Goals / Non-Goals

**Goals:**

- Migration `055` (and, folded in during verification, `053` and `054`) computes its `upgrade()` DDL by calling a revision module's `statements()`, not by hand-writing SQL — one authored definition per DDL change, two call sites (Alembic's platform loop, `migrate.py`'s Azure loop).
- `tests/test_tenant_store_parity.py` passes — it was red on unmodified `main` because of `053`/`054`'s gap, independent of `055`.
- A new automated check makes it structurally hard for a future tenant-scoped migration to ship without a matching revision module and without calling it, so this class of bug cannot silently reoccur.

**Non-Goals:**

- Delegating `055`/`053`/`054`'s `downgrade()`s to a revision-module-provided reverse statement list. The `src/shared/tenant_store/revisions` system (`apply.py`/`migrate.py`) has no downgrade path at all — tenant-owned Azure stores are only ever moved forward, consistent with the additive-migrations-only stance (ADR-014). The two-copies-drift risk this change addresses only exists for `upgrade()`, the direction that reaches both platform schemas and Azure tenant stores; each migration's `downgrade()` has exactly one caller (Alembic's own local rollback) and nothing else to drift against, so all three keep their existing hand-written `DROP COLUMN`/`DROP CONSTRAINT` DDL unchanged. Adding a revision-module downgrade helper here would be unused abstraction, not a gap closure.

- Not migrating the ~50+ other pre-existing tenant-scoped Alembic migrations that predate the `revisions/` convention (captured in `002_main_feature_backlog.py`'s backlog catch-up) to also delegate — out of scope, flagged as a possible follow-up audit. `053`/`054` were pulled into scope specifically because fixing `055` alone left `test_tenant_store_parity.py` red; no other pre-existing migration was found to cause a currently-failing test.
- Not changing `baseline.py`, `apply.py`, or `migrate.py`'s control flow — those already work correctly; the gap was entirely in migration `055` not participating in the existing convention.
- Not replacing Alembic with the `revisions/` system for platform-hosted tenants, or vice versa (see ADR-017 Decision 5's "Alternatives considered" — already ruled out, not reopened here).

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| ADR-017-tenant-owned-postgresql-data-plane | Tenant-scoped Alembic migrations must call the matching `src/shared/tenant_store/revisions/NNNN_*.py` module's `statements()`, so DDL is written once and applies to both platform and tenant-owned stores | This design implements exactly that call for migrations `053`, `054`, and `055`; does not revisit the decision, only closes a gap in applying it |
| ADR-014-mandatory-conversation-scoped-retrieval / ADR-011-conversation-scoped-chat-attachments | Attachments are scoped per conversation and rendered per message | Unaffected — this change only touches how the `attachments` column's DDL is authored, not the feature's behavior |

## Decisions

### Decision 1: Delegate by import, not by codegen

**Choice:** Each of `055.upgrade()`, `053.upgrade()`, and `054.upgrade()` imports its matching revision module (`003_chat_messages_attachments`, `004_documents_conversation_id`, `005_document_chunks_conversation_id` respectively — or however each is named/imported given its leading-digit filename) and calls its `statements(schema)` inside the existing per-schema loop, executing each returned string with `op.execute(...)`. No build step generates a migration's body from its revision file. All three `downgrade()`s are unchanged (see Non-Goals).

**Rationale:** Matches the pattern the convention already describes in `revisions/__init__.py`'s docstring — "the tenant-scoped Alembic migration then calls this module's `statements()`". Keeps each Alembic migration file as a thin, readable wrapper (schema-discovery loop + `op.execute`), while the revision module remains the single place DDL text lives. Avoids introducing a code-generation step, which would add its own drift risk (generated file going stale) for no benefit here — the loop bodies are already nearly identical between each migration's current DO-block-per-schema style and what a direct `statements()` call produces. Having three call sites (rather than one) also validated the pattern generalizes cleanly — `053`'s guarded foreign key (`documents.conversation_id → conversations.id`) and `054`'s partial index both fit the same `statements(schema) -> list[str]` shape without special-casing.

**Alternatives considered:**
- Generate a migration's DDL at authoring time by reading its revision module — ruled out: extra tooling for three call sites, no protection against someone hand-editing the generated file later.
- Move the loop itself into a shared helper every delegating migration calls, passing only the revision module — ruled out for this change as scope creep; now that three migrations share near-identical loop bodies, this is a stronger candidate for a follow-up than it was with just `055` (see Open Questions).

### Decision 2: Static source check as the enforcement mechanism

**Choice:** Add a test that parses each `alembic/versions/*.py` file touching a `tenant_template`-qualified table (detected via a regex/AST scan for `tenant_template.` or the per-schema loop's `pg_namespace` pattern) and asserts the file imports something from `src.shared.tenant_store.revisions`. Migrations that don't touch tenant-scoped tables (the large majority — platform-only tables, data backfills, index-only changes on non-tenant tables) are exempt. Pre-existing migrations are grandfathered by an explicit filename set, captured once, with `053`, `054`, and `055` deliberately excluded from that set — they are the motivating cases and are asserted (by a dedicated test) to never be silently grandfathered even if the set is regenerated carelessly later.

**Rationale:** Cheap, fast, runs in normal `pytest` without spinning up a database, and directly targets the failure mode that occurred: a migration containing tenant-scoped DDL with no revisions-module import. A shape-comparison test (`test_tenant_store_parity.py`) already exists and stays as-is — it catches drift after the fact; this new check catches the missing-delegation pattern before a migration can even be reviewed as "done."

**Alternatives considered:**
- Runtime check: apply revision N's `statements()` to a scratch schema, apply migration N's DDL to another scratch schema, diff `information_schema` — ruled out as the primary mechanism: stronger, but requires a database in the loop, slower, and mostly redundant with what `test_tenant_store_parity.py` already does. Could be added later as belt-and-suspenders; not required to close this specific gap.
- Code review checklist / PR template item only — ruled out: exactly what was supposed to happen for `055` and didn't; not durable.

## Risks / Trade-offs

- [The static check's tenant-scoped-DDL detection (regex/AST heuristic) could false-positive on a migration that legitimately touches `tenant_template` without needing a revision module, or false-negative on an obfuscated/dynamically-built statement] → Keep the heuristic narrow and documented; allow an explicit `# tenant-store-revision: exempt — <reason>` comment escape hatch reviewed like any other suppression, so a real exception doesn't block unrelated work.
- [The check could misfire on `downgrade()` bodies, which legitimately hand-write DDL since downgrades are out of scope for delegation] → Scope the static check to each migration's `upgrade()` function body only; `downgrade()` is never scanned.
- [Rewiring `055`/`053`/`054` changes their exact executed SQL text (from inline multi-statement `DO $$...$$` blocks to whatever shape `apply.py`/`statements()` iteration produces) — a byte-for-byte diff of executed statements, even if schema-equivalent, is a behavior change on databases that re-run this migration] → All three are already applied everywhere it matters on the platform side (original runs); `arjunj`'s tenant-owned store was brought current via `migrate.py`/`db-init` using the new revisions `003`, `004`, `005` directly. This change only affects future fresh-database bootstraps or migration re-runs, which use `IF NOT EXISTS`/idempotent DDL in both the old and new path, so end state is identical. Verified via `test_tenant_store_parity.py` (now passing) and a fresh-database `alembic upgrade head` run.
- [`053`/`054` were discovered mid-implementation, not planned upfront — risk of a narrower fix than `055`'s (e.g. missing `053`'s guarded foreign key or `054`'s partial index in the corresponding revision module)] → Each new revision module's output was diffed by hand against the original migration's inline DDL, and verified end-to-end against a real scratch schema (`apply()` called directly) confirming the column, FK, and index all appear with correct names/shapes before the fix was run against `arjunj`'s real store.

## Migration Plan

1. Rewire `055.upgrade()` to call revision `003`'s `statements()`.
2. While verifying step 1 against a fresh database, discover `test_tenant_store_parity.py` fails on unmodified `main` (missing `053`/`054` revisions) — add revision modules `004_documents_conversation_id` and `005_document_chunks_conversation_id`, rewire `053.upgrade()`/`054.upgrade()` to call them.
3. Add the static enforcement test, with `053`, `054`, and `055` un-grandfathered (tested for real, not skipped).
4. Run `test_tenant_store_parity.py` and a fresh `alembic upgrade head` locally to confirm identical end-state schema shape; confirm the parity test passes (was previously red on `main`).
5. Run `docker compose build db-init && docker compose up db-init` to push revisions `003`, `004`, `005` to `arjunj`'s real tenant-owned Azure store (already `ready`/`migration_required` eligible); confirm `public.tenant_data_planes.schema_revision = 5` afterward.

No further data migration or deploy-order changes required beyond step 5 — `alembic_version` bookkeeping is untouched (all three migrations already exist and are already applied to every platform database); only the `tenant_owned` side needed the explicit `migrate.py` run this change already performed.

Rollback: revert the commit. No platform database state depends on these migrations' internal implementation, only their net effect (the columns/FK/index existing), which is unchanged by this refactor. `arjunj`'s tenant-owned store would keep its now-correct schema even after a code rollback — the DDL already applied there does not un-apply itself.

## Open Questions

- Should the shared per-schema-loop-plus-`statements()`-call pattern be extracted into a small helper (e.g. `src/shared/tenant_store/alembic_bridge.py: apply_revision(op, revision_module)`) once a second migration adopts delegation, to avoid each migration re-deriving the loop? Deferred — revisit once there's a second real call site to generalize from.
- Retrofitting pre-`revisions/`-convention migrations (before `002_main_feature_backlog`) to delegate is out of scope here; worth a separate tracked follow-up if audit shows more drift risk there.
