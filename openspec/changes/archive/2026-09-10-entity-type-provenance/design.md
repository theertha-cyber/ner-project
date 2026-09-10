## Context

All three annotation methods write entity types into `public.entity_definitions` through
`src/gateway/services/entity_service.py` — manual creation directly, schema-proposal
approval via the same service, and (after the `import-annotation-training-eligibility`
change) import type-mapping via the same service. The table has no field recording which
path created a row, so the Entity Types page cannot show the provenance chip the Page
Content Spec calls for.

## Goals / Non-Goals

**Goals**
- Record, at creation, whether an entity type was made by hand, suggested by the LLM, or
  created while mapping an import — and never let a later edit change that.
- Surface it on every entity-type read and on the card.

**Non-Goals**
- No reclassification of existing rows (all backfill to `manual`).
- No behavioural effect — extraction, projections, versioning, tenant scoping are
  untouched.
- No new endpoint — provenance rides existing responses.

## Currently-In-Force ADRs

| ADR | Constraint |
|-----|-----------|
| ADR-001 tenant-data-isolation | `provenance` is a column on the existing tenant-scoped `entity_definitions`; no change to scoping. |
| ADR-007 entity-config-single-writer (if in force) | The only writer of `entity_definitions` stays `entity_service`; the schema-proposal and import paths pass provenance *to* it, they do not write the column themselves. |

## Decisions

### Decision 1: `provenance` is a `NOT NULL` column with a `server_default` of `'manual'`

`entity_service.create` inserts through an explicit column list. Following the pattern used
for `cardinality` (migration 037), the column needs a `server_default` so a `create_all`-built
schema and a migration-built schema agree and so an insert that does not name the column
still satisfies `NOT NULL`. `entity_service.create` is extended to accept an optional
`provenance` / `provenance_ref` and name them in the column list when provided.

### Decision 2: The creation path decides provenance; the request body cannot

The plain `POST` endpoint never reads `provenance` from the body — it always creates
`manual`. `schema_proposal` approval calls `entity_service.create(..., provenance='suggested',
provenance_ref=<schema version label>)`. The import type-map "create new" path calls
`entity_service.create(..., provenance='imported', provenance_ref=<source filename>)`.

*Rationale:* provenance is a fact about how the row came to exist, not user input. Letting
the body set it would let a hand-created type masquerade as suggested.

### Decision 3: Immutability is enforced by omission, not a trigger

`entity_service.update` does not touch `provenance` / `provenance_ref`. There is no code
path that updates them after creation, so no trigger or check constraint is needed. A
verification scenario asserts an update leaves provenance unchanged.

## Risks / Trade-offs

- **Backfill imprecision:** entity types created by the pre-existing schema-proposal flow
  become `manual`. Acceptable — there is no stored signal to distinguish them and `manual`
  reads as "created directly", which is not misleading.
- **`provenance_ref` for `suggested`:** the schema-proposal record may not always carry a
  clean version label; `provenance_ref` is nullable and populated best-effort.

## Migration Plan

1. Migration `044`: `ALTER TABLE public.entity_definitions ADD COLUMN provenance VARCHAR(16)
   NOT NULL DEFAULT 'manual', ADD COLUMN provenance_ref VARCHAR(255)`. Existing rows take
   the default. Additive.
2. `scripts/setup_test_db.py` `entity_definitions` DDL + the annotation-test inline
   `entity_definitions` DDLs gain the columns.
3. No data backfill beyond the default.

## Open Questions

- Chip wording when `provenance_ref` is null for a `suggested` type: `"suggested"` alone.
  Confirmed acceptable.
