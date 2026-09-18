## Context

`POST /api/v1/annotation-import` parses CoNLL/JSONL, validates each row's tags against
`public.entity_definitions`, inserts the valid rows into `{schema}.imported_annotations`,
and returns `imported_count` / `skipped_count` / `warnings`. Rows with unknown types are
**dropped**. `imported_annotations` gained `reviewed` / `reviewed_at` / `reviewed_by` in
migration 017 but nothing reads them for training. Migration 041 (nav-restructure Phase 3)
already added an `annotation_imports` header table with `row_count`, `type_map`,
`training_eligible_at`.

## Goals / Non-Goals

**Goals**
- No imported row is ever lost to an unknown type — it is held and surfaced for mapping.
- Unknown types are mapped to canonical entity types (existing or newly created via the
  entity-config API) — never created implicitly.
- A training-eligible import contributes rows to the training dataset export.
- The Tenant Admin can go import → request training with no forced review step.

**Non-Goals**
- No new entity-type table or create path — mapping-to-new goes through `entity-config`.
- No mandated per-row annotation review before eligibility (`reviewed` stays optional).
- No reconciliation between imported rows and span-derived rows for the same document
  (both are emitted, distinctly sourced).
- No change to the parser, size/MIME limits, or the per-row review endpoints' roles.

## Currently-In-Force ADRs

| ADR | Constraint |
|-----|-----------|
| ADR-001 tenant-data-isolation | `imported_annotations` and `annotation_imports` are tenant-schema tables; entity types are `public.entity_definitions` scoped by `tenant_id`, as today. |
| ADR-011 annotation-idempotency-enforcement | Re-submitting the same file, or re-running a type-map, MUST be idempotent — no duplicate rows, no duplicate entity-type creation, one `training_eligible_at`. |
| ADR-012 annotation-fix-deployment-topology | New endpoints stay in `annotation_service`; training requests go through the existing `training_service` route. |

## Decisions

### Decision 1: Hold unmapped rows in place, mark them pending

`imported_annotations` gains a `pending_mapping BOOLEAN NOT NULL DEFAULT FALSE`. On import,
a row with any unknown type is inserted with `pending_mapping = true`; its tags are stored
as received. `imported_count` counts rows with `pending_mapping = false`; `pending_count`
counts the rest. Export reads only `pending_mapping = false` rows of eligible files.

*Rationale:* keeps every row addressable for the mapping UI and for audit, and makes
"immediately usable" a single boolean rather than a recomputation.

### Decision 2: Mapping rewrites tags in place; the original is kept on the header

`type-map` for `X → y`: `UPDATE imported_annotations SET tags = <rewrite X→y>, pending_mapping = (still has any unknown) WHERE source_file = :f AND 'X' = ANY(<base types of tags>)`.
The header's `type_map` JSON records `{"X": {"to": "y", "created": false}}`. When the last
unknown type on a file is resolved, `training_eligible_at = NOW()`.

*Rationale:* the export path stays a plain read of `tags`; no join-time remapping. The
header keeps the provenance a reviewer needs.

### Decision 3: "Map to new" calls the entity-config create API, then maps

The type-map endpoint, given `{"X": {"create": true}}`, calls the same entity-type creation
path the schema-proposal approval uses, with `provenance = 'imported'` (see the
`entity-type-provenance` change), then applies the rewrite. It never inserts into
`entity_definitions` directly.

### Decision 4: Eligibility = all rows imported AND no unmapped type; `reviewed` is orthogonal

A file is training-eligible when `pending_count = 0`. The `reviewed` flag remains a
per-row quality signal an Annotator Admin or Tenant Admin can set, surfaced in the UI, but
it does not gate eligibility — the brief states imported labelled data is usable as
training data without a mandated re-review.

### Decision 5: Export tags imported rows with a source marker

`annotation-export` emits imported rows with an added `source: "import"` (or an equivalent
marker already used for provenance) so a downstream consumer can tell them from
span-derived rows. Rows from non-eligible files are excluded by the `training_eligible_at`
filter on the header join.

## Risks / Trade-offs

- **Tag-rewrite correctness.** Rewriting `B-X`/`I-X` → `B-y`/`I-y` must preserve the BIO
  prefix and only touch the mapped base type. Covered by a dedicated scenario.
- **Large-file mapping.** A 50MB file with a common unknown type touches many rows in one
  UPDATE. Acceptable — it is one statement, bounded by the 50MB import cap.
- **Backward compat.** Callers reading `skipped_count` see it drop to near-zero (rows are
  held, not skipped). `warnings` is retained for genuinely unparseable rows. Documented.

## Migration Plan

1. Migration `043` (`apply_to_all_tenant_schemas`, additive): add
   `imported_annotations.pending_mapping BOOLEAN NOT NULL DEFAULT FALSE`; ensure
   `annotation_imports` exists (idempotent with 041).
2. `scripts/setup_test_db.py` / annotation test fixtures gain the column and the header
   table.
3. No backfill — existing imported rows are already type-valid (unknown-type rows were
   historically dropped), so `pending_mapping = false` is correct for them; create an
   `annotation_imports` header per distinct existing `source_file` with
   `training_eligible_at = NOW()`.

## Open Questions

- Should the "Unmapped Types" tab show a per-type sample row so the Tenant Admin can judge
  the mapping? Assume yes — one example span in context per unmapped type.
- Do we expose an "unmap" / re-map action? Assume no for v1; a mistaken map is corrected by
  editing the now-canonical entity type or re-importing.
