## Context

The entity types backend was implemented with a flat URL prefix (`/api/v1/entity-types`) and UUID-based route parameters, while the rest of the gateway uses tenant-scoped URLs for all tenant resources. The sp-09 frontend spec (and the generated hooks) correctly targets `/api/v1/tenants/{slug}/entity-types` with name-based identifiers, but there was no backend to handle that path. All four operation types (list, create, update, toggle) return 404, making the entity types page non-functional even though both the frontend and the database table are in place.

There are four concrete defects:
1. Wrong router prefix — no route handles `/api/v1/tenants/{slug}/entity-types`
2. Wrong identifier — routes use `entity_id` (UUID) but the spec uses `name`
3. Missing PATCH endpoint for `is_active` toggle
4. `_row_to_dict` returns `examples` and `base_label_mapping` as raw JSON strings, not parsed values

## Goals / Non-Goals

**Goals:**
- Fix the four defects so the entity types page lists, creates, edits, and toggles entities correctly
- Align backend routes to the tenant-scoped URL convention used by every other resource in the gateway
- Keep all changes inside `entity_types.py` and `entity_service.py` — no schema migrations, no frontend changes

**Non-Goals:**
- Migrating any existing data or supporting the old URL prefix alongside the new one
- Changing authentication or authorization logic beyond what's needed to wire the tenant slug
- Modifying the `entity_definitions` DB table structure

## Currently-In-Force ADRs

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|-----------------------------|
| ADR-001 | Tenant data isolation via separate DB schemas | All queries must filter by `tenant_id`; already satisfied by the service |
| ADR-004 | OpenSpec spec-driven governance | Changes must trace to a spec artifact |

ADR-002 is partially superseded by ADR-008. ADRs 003, 005, 006, 007 are unrelated to this change.

## Decisions

### Decision 1: Adopt tenant-scoped URL prefix, remove old flat prefix entirely

**Choice:** Register the router at `/api/v1/tenants/{tenant_slug}/entity-types` and remove `/api/v1/entity-types`. No deprecation shim.

**Rationale:** No production traffic relies on the old URL — the frontend never successfully called it. Adding a shim would require maintaining two code paths with no benefit and would create confusion in the API surface.

**Alternatives considered:**
- Keep old prefix with 301 redirect → ruled out: redirect doesn't propagate JWT headers and adds unnecessary complexity
- Support both prefixes simultaneously → ruled out: zero known callers on old prefix

### Decision 2: Look up entity types by `name`, not UUID

**Choice:** The `{name}` path segment is used in GET single, PUT, PATCH, and DELETE routes. Service queries use `WHERE name = :name AND tenant_id = :tid`.

**Rationale:** The sp-09 spec and the frontend hooks are designed around `name` as the stable, human-readable identifier. Names are unique per tenant (enforced at the DB level). Using UUID would require the frontend to store and pass back UUIDs from the list response, which the current hooks don't do.

**Alternatives considered:**
- UUID-based routes → ruled out: requires frontend changes; names are already unique per tenant

### Decision 3: PATCH for is_active toggle, not PUT

**Choice:** Add a dedicated `PATCH /{name}` endpoint that accepts only `{"is_active": boolean}` and updates only that column.

**Rationale:** The frontend toggle hook sends PATCH. Using PUT for a toggle would require sending the full entity payload, which the toggle button doesn't have access to. PATCH semantics (partial update) are correct here.

**Alternatives considered:**
- Reuse PUT with full payload → ruled out: toggle button doesn't hold the full entity; would couple UI state unnecessarily

### Decision 4: Parse JSON columns in _row_to_dict

**Choice:** Call `json.loads()` on `examples` and `base_label_mapping` in `_row_to_dict` only when the value is a string (guard for `None` and already-parsed values from the ORM driver).

**Rationale:** These columns are stored as JSON strings via `json.dumps()` in the write path. Without `json.loads()` on read, the frontend receives a string where it expects an array/object, causing the card to render incorrectly.

**Alternatives considered:**
- Use SQLAlchemy `JSON` column type to auto-deserialize → ruled out: the service uses raw `text()` queries; switching to ORM mapped columns is out of scope for a bug fix

### Decision 5: Flatten create/update response shape

**Choice:** `create_entity_type` and `update_entity_type` return the flat dict from `_row_to_dict` directly, not wrapped in `{"entity_type": {...}}`. `_get_by_id` is kept as an internal helper; its wrapping is only stripped at the service method boundary.

**Rationale:** The frontend `useCreateEntityType` and `useUpdateEntityType` hooks type the return as `EntityType` (flat). The list endpoint already returns a flat array, so consistency is improved.

**Alternatives considered:**
- Change the frontend hooks to unwrap `entity_type` key → ruled out: the backend is wrong per spec; fixing the source is cleaner

## Risks / Trade-offs

- [Removing old URL immediately may break scripts or Postman collections that were manually tested against `/api/v1/entity-types`] → Acceptable: document in PR description; no production consumers exist
- [Looking up by name means a rename (via PUT) changes the URL for subsequent requests] → Acceptable: name changes are already blocked by the frontend (NAME is disabled in edit mode per the sp-09 spec)
- [json.loads guard on already-parsed values] → Low risk: SQLAlchemy `text()` always returns strings for text columns on PostgreSQL; the guard is defensive only

## Migration Plan

1. Update `entity_types.py`: change router prefix, update route parameters from `entity_id` to `name`, add PATCH handler
2. Update `entity_service.py`: add `toggle_entity_type(tenant_id, name, is_active)` method, update `_get_by_id` (or add `_get_by_name`) to query by name, fix `_row_to_dict` JSON parsing, strip `{"entity_type": ...}` wrapper from create/update returns
3. Verify all five endpoints against the spec scenarios (list, GET by name, POST, PUT by name, PATCH by name, DELETE by name)
4. No DB migration required — no schema changes

**Rollback:** Revert both files. No data was mutated by the code change itself.

## Open Questions

- Should `_get_by_id` (UUID lookup) be kept for any internal use, or replaced entirely by `_get_by_name`? Current usage is only internal after create/update — can be safely replaced.
