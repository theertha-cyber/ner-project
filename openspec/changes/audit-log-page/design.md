## Context

The audit log page at `/audit` currently shows a `<PlaceholderScreen />`. System admins need real-time visibility into platform-wide actions. The mockup (in `docs/NER Platform.html`) defines the exact UI: a vertical timeline with color-coded kind badges, actor details, and timestamps. No backend model or API exists today for storing or serving audit events. Audit events are generated implicitly by existing operations (tenant create/deactivate, training job approve/reject, model promote, etc.) but are not persisted.

## Goals / Non-Goals

**Goals:**
- Persist audit events in a new `public.audit_events` table in the gateway's database
- Expose a paginated `GET /api/v1/admin/audit-log` endpoint requiring `system_admin`
- Render the audit log page at `/audit` exactly matching the mockup timeline UI
- Audit events fire from existing gateway operations (tenant CRUD, training job approve/reject, model promote, entity type changes)

**Non-Goals:**
- Event sourcing or CQRS — audit is a simple append-only log, not a system of record
- Tenant-admin scoped audit — only system admin sees all events
- Retention or TTL cleanup — out of scope for MVP
- Distributed tracing integration — audit events capture business actions, not request traces

## Currently-In-Force ADRs

All ADRs are in **Proposed** status. None are formally in force, so no ADR constraints apply to this design.

| ADR | Decision Summary | Constraint on This Design |
|-----|-----------------|--------------------------|
| — | — | None |

## Decisions

### Decision 1: Append-only audit table in `public` schema

**Choice:** A single `public.audit_events` table storing all events with a `tenant_id` nullable FK.

**Rationale:** Following the existing pattern of shared tables in `public` schema (tenants, tenant_users, entity_definitions). `tenant_id` is nullable because system-level actions (e.g., `tenant.deactivate`) may not have a tenant context or may reference a tenant that was just created/deleted. The `kind` column maps to the mockup's kind color map: `create`, `approve`, `promote`, `complete`, `run`, `reject`, `update`.

**Alternatives considered:**
- Per-tenant schema: Overkill — audit is a system concern, not a tenant one. Cross-tenant queries would require UNION.
- Separate audit service: Premature — the gateway already owns the data model for system-level tables.

### Decision 2: Manual event recording at action sites (not DB triggers or CDC)

**Choice:** Each existing service method that generates an audit-worthy action explicitly calls `AuditService.record()`.

**Rationale:** Explicit. Follows the existing service layer pattern. No hidden side effects. Easy to include action-specific context (target name, kind).

**Alternatives considered:**
- SQL triggers: Invisible to the codebase, hard to test, cannot include computed context.
- CDC (Debezium/Walrus): Over-engineered for a simple append log.

### Decision 3: Offset-based pagination on the API

**Choice:** `GET /api/v1/admin/audit-log?page=1&per_page=50` with offset pagination.

**Rationale:** Consistent with the existing `list_tenants` pagination pattern. Audit logs are a bounded, ordered dataset — cursor pagination adds complexity without benefit here.

**Alternatives considered:**
- Cursor-based: Follows ADR-001's default but audit is read-only append with no concurrent modification risk. Offset is simpler.

### Decision 4: New `AuditLog` React component inline in the page, no new route-level component

**Choice:** Build the audit page with a self-contained `AuditLogTimeline` component in the page file, using a new `use-audit-log` hook for data fetching.

**Rationale:** The audit page has one surface — the timeline. No sub-views or modals (unlike users, docs, tenants). A single component suffices. The existing pattern for simple pages is to keep the component in or near the page file.

**Alternatives considered:**
- Separate `components/audit/` directory: Premature abstraction given the single surface.

## Risks / Trade-offs

- [Forgotten recording sites] → New actions might be added without calling `audit_service.record()`. Mitigation: Add a checklist item in the task for each action site.
- [Performance as audit log grows] → The table grows unbounded. Mitigation: Defer TTL/indexing to production monitoring; add a `created_at` index upfront.
- [Mockup uses inline styles; portal uses Tailwind] → The mockup's inline styles define the visual target. The React implementation will use Tailwind classes that produce the same visual result.

## Migration Plan

1. Generate Alembic migration `020_create_audit_events_table`
2. Deploy migration to dev
3. Deploy gateway code with new model, service, and route
4. Deploy portal code with new page, hook, and component
5. Verify that existing actions produce audit events visible at `/audit`

**Rollback:** Revert code + run `alembic downgrade 019`.

## Open Questions

- Should audit logging be retroactive for existing records? No — only forward events.
- Should the `actor` field store user ID or email? Email (matching mockup data), with user ID as a secondary field for JOINs.
