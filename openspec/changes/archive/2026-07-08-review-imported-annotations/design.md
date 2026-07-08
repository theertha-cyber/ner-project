## Context

`imported_annotations` (`{tenant_schema}.imported_annotations`: `id`, `tokens TEXT[]`, `tags TEXT[]`, `source_file`, `row_index`, `created_at`) is populated only by `POST /api/v1/annotation-import` (`src/annotation_service/api/v1/import_.py`) and read only by `GET /api/v1/annotation-export`. It has no relationship to `documents`, `annotation_tasks`, or `spans`. The interactive annotation workspace (`AnnotationPage.tsx` + `span-reducer.ts`) is built entirely around character-offset `spans` tied to a `document_id`, and its entity colors are computed client-side from `entity_definitions` order (`buildEntityColors` in `AnnotationPage.tsx`), never persisted.

The existing `annotation-import-ui` spec has a binding scenario ("Import does not create annotation tasks") that this change must not violate — imports remain staging-only. This feature adds a way to *see and fix* what's in that staging table, in place, without promoting rows into the task pipeline.

## Goals / Non-Goals

**Goals:**
- Let annotators/tenant admins browse `imported_annotations` rows document-wise (one row = one unit), filtered by `source_file` and entity type.
- Render every token of a row with `O` tokens plain and `B-`/`I-` runs highlighted in the entity's color, matching the visual language of the main workspace.
- Allow retyping, deleting, and creating spans by token range, validated against the tenant's entity types.
- Track review progress per row.

**Non-Goals:**
- Materializing imported rows into `documents`/`annotation_tasks`/`spans`. This surface is permanently parallel to the interactive workspace, not a staging area for it.
- Reusing `span-reducer.ts` or the char-offset span API — a new, simpler token-index reducer is used instead.
- Introducing a formal review workflow (e.g. multi-stage approval) — `reviewed` is a simple progress marker, not a state machine.

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-------------------|--------------------------|
| ADR-001-tenant-data-isolation | Tenant isolation via per-tenant Postgres schema (`tenant_<uuid>`); no cross-tenant queries; migrations applied uniformly to `tenant_template` and every existing `tenant_*` schema | New columns on `imported_annotations` and new endpoints must stay within the existing schema-per-tenant boundary — no new `tenant_id` column needed, and the migration must follow the multi-schema `DO $$ ... FOR schema_name IN ...` apply pattern already used in `alembic/versions/012_reconcile_training_jobs_columns.py` |

(ADR-002 is partially superseded by ADR-008 but neither concerns this feature. ADR-003, 004, 005, 006, 007 are in force but not load-bearing here — no model-serving, governance, agent-boundary, training, or chat concerns in this change.)

## Decisions

### Decision 1: New capability, not a modification of `annotation-import-ui`

**Choice:** Ship this as a new capability (`annotation-import-review`) rather than editing the `annotation-import-ui` spec.

**Rationale:** `annotation-import-ui` governs the upload → parse → preview → result flow and explicitly asserts import doesn't touch the task queue. This feature is a separate concern (reviewing what's already staged) with its own requirements; keeping it a separate capability avoids overloading one spec with two different UI surfaces and makes the "staging is unaffected" guarantee easy to verify by inspection (the existing spec file simply doesn't change).

**Alternatives considered:**
- Add requirements to `annotation-import-ui` — rejected, would conflate upload-time behavior with post-import review behavior in one spec file, and risks accidentally weakening the "no tasks created" guarantee during future edits.

### Decision 2: Token-index edit model, not char-offset spans

**Choice:** Represent an editable span in this surface as `{start_token_index, end_token_index, entity_type}`, derived from and written directly back onto the row's `tags[]` array (contiguous `B-X`/`I-X*` collapses to one span; editing a span rewrites the corresponding slice of `tags[]`).

**Rationale:** `tokens[]` and `tags[]` are already positionally aligned 1:1 — there is no text to re-tokenize and no char-offset math needed. This is strictly simpler than the workspace's span model and avoids reconstructing a synthetic document text just to reuse `span-reducer.ts`.

**Alternatives considered:**
- Reconstruct document text by joining tokens and reuse the existing char-offset `spans` machinery — rejected in the parent proposal discussion: it would require materializing a document, which is explicitly out of scope, and buys no real benefit since the token array is already the source of truth.

### Decision 3: `reviewed` as a simple boolean + audit fields, not a status enum

**Choice:** Add `reviewed BOOLEAN NOT NULL DEFAULT FALSE`, `reviewed_at TIMESTAMPTZ NULL`, `reviewed_by VARCHAR NULL` to `imported_annotations`.

**Rationale:** The only requirement is "let annotators tell what they've already gone through in a large batch." A boolean plus who/when satisfies that without inventing a multi-state lifecycle that nothing in the current requirements calls for.

**Alternatives considered:**
- A shared status enum mirroring `annotation_tasks.status` (`unannotated`/`in-progress`/`completed`) — rejected as over-scoped; there's no "in-progress" concept for a single row edit, and introducing a shared enum couples this table to task-queue semantics it deliberately doesn't participate in.

### Decision 4: Entity colors computed client-side, same scheme as the main workspace

**Choice:** Reuse the existing `buildEntityColors`-style computation (index into a fixed palette by `entity_definitions` creation order) in the new frontend surface, fetched via the same `useEntityTypes()` hook.

**Rationale:** Entity colors are not persisted anywhere today; recomputing them the same way guarantees visual consistency between the two surfaces (a `PER` entity looks the same color whether you're in the workspace or the review surface) without adding a new persistence requirement.

**Alternatives considered:**
- Persist colors on `entity_definitions` — rejected as out of scope; would change the main workspace's behavior too and isn't required by this feature.

## Risks / Trade-offs

- [Editing `tags[]` in place discards edit history — no audit trail of what an annotator changed] → Acceptable for MVP since `imported_annotations` is not itself a system of record for training (export is); revisit if compliance requires an audit log later.
- [Large imports (thousands of rows from one 50MB file) make the list endpoint pagination-critical] → Require pagination and `source_file`/entity-type filters from day one (already scoped in proposal); no unbounded "list all" endpoint.
- [Token-index edits bypass the entity-type validation path used at import time if implemented separately] → Reuse `get_known_entity_types_lower` (already in `import_.py`) directly in the new update endpoint rather than reimplementing validation.

## Migration Plan

1. Add a new Alembic migration adding `reviewed`, `reviewed_at`, `reviewed_by` columns to `imported_annotations` in `tenant_template` and all existing `tenant_*` schemas, following the loop pattern in migration 012. Default `reviewed = FALSE` for all existing rows (no backfill logic needed beyond the column default).
2. Add the new list/detail/update endpoints to `src/annotation_service` (additive, no changes to existing `import_.py`/`export.py` behavior).
3. Add the new frontend list page and token-range editor (additive route/component, no changes to `AnnotationPage.tsx`).
4. Rollback: drop the three new columns and remove the new endpoints/routes; `imported_annotations` and existing import/export behavior are unaffected since nothing existing was modified.

## Open Questions

- Final filter set for the list endpoint (source_file + entity type confirmed; reviewed-state filter likely useful but left to specs.md to make a firm requirement or explicitly defer).
- Whether `reviewed_by` should store a user id or email — follow whatever convention `annotation_tasks.assignee`/`annotator_user_id` already uses for consistency; confirm during spec-writing.
