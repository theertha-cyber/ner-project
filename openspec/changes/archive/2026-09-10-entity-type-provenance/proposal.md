## Why

The Tenant Admin Console restructure makes one Entity Types page the single home for the
schema every annotation method labels against — manual, automated (LLM schema proposal),
and import (type mapping). All three already write into the same canonical
`public.entity_definitions` table, so the "single source of truth" requirement is met at
the data layer. What is missing is *legibility*: when a Tenant Admin opens Entity Types and
sees a type they do not recognise, there is nothing on the card that says where it came
from. The Page Content Spec calls for a provenance chip — `manual`, `suggested (schema
vN)`, or `imported` — "same card, one extra line, and it explains where a type an admin
doesn't recognise came from."

## What Changes

- Add a `provenance` field to an entity type: `manual` (created by hand — the default),
  `suggested` (created by approving an LLM schema-proposal candidate), or `imported`
  (created while mapping an unknown type during annotation import). Set once at creation,
  never changed by a later edit.
- The schema-proposal approval path stamps `provenance = 'suggested'` (and, where a
  proposal id is available, records it) instead of relying on the default.
- The import type-map "create new" path stamps `provenance = 'imported'`.
- Entity type read responses (`GET .../entity-types`, single GET, create/update responses)
  include `provenance`.
- The `EntityTypeCard` renders a provenance chip.

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

- `entity-config`: an entity type gains a `provenance` field (`manual` | `suggested` |
  `imported`), assigned at creation and immutable thereafter.
- `entity-types-backend`: entity type read/create/update responses include `provenance`.
- `entity-types-screen`: `EntityTypeCard` displays a provenance chip.

## Impact

- **Backend**: `src/gateway/models/__init__.py` (`EntityDefinition.provenance` column),
  `src/gateway/services/entity_service.py` (accept + default provenance on create, expose
  on reads), `src/gateway/api/v1/entity_types.py` (response shape),
  `src/annotation_service/services/schema_proposal.py` (pass `suggested` on approve).
- **Database**: `entity_definitions.provenance VARCHAR(16) NOT NULL DEFAULT 'manual'`
  (`server_default` — `entity_service.create` inserts via an explicit column list). Additive.
- **Frontend**: `src/portal/src/components/entity-types/EntityTypeCard.tsx`,
  `src/portal/src/types/entity-types.ts` (`provenance` on `EntityType`).
- **No impact**: extraction, analytics projections, versioning, tenant scoping — provenance
  is descriptive metadata only.

## Open Questions

- Should `provenance` record *which* schema proposal or import file produced a `suggested`
  / `imported` type (a nullable `provenance_ref`)? The Page Content Spec shows "from: schema
  v3", implying a reference. Assume a nullable `provenance_ref VARCHAR` holding the schema
  version label or source filename, populated best-effort.
- Existing rows all become `manual` on backfill. Is that acceptable for types that were
  actually created by the (pre-existing) schema-proposal flow? Assume yes — there is no
  reliable signal to reclassify them, and `manual` is the safe "created directly" reading.
