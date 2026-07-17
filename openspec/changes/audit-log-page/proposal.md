## Why

The system admin dashboard currently has no audit log page — the route exists (`/audit`) but shows only a placeholder. System admins need visibility into all tenant-scoped actions (training job submissions, approvals/rejections, model promotions, entity type changes, document uploads, tenant status toggles) to monitor platform activity, investigate incidents, and maintain compliance.

## What Changes

- **New frontend page at `/audit`** — a timeline-based audit log view for the `system_admin` role
- **New API endpoint** — `GET /api/v1/audit-log` on the gateway, returning paginated audit events
- **New gateway database model** — `AuditEvent` table storing tenant-aware action records
- **New frontend hook** — `use-audit-log` for fetching and paginating audit events
- **Sidebar navigation entry** — already exists for `system_admin` but now leads to a real page

## Capabilities

### New Capabilities

- `audit-log`: System-wide audit event timeline showing action, actor, target, role, kind, and timestamp with color-coded kind badges. Paginated. Available only to `system_admin` role.

### Modified Capabilities

<!-- No existing spec requirements are changing. -->

## Impact

- **Gateway** (`src/gateway/`): New `AuditEvent` model + migration + API route
- **Portal** (`src/portal/`): New page, hook, and component; no existing page modified
- **No breaking changes** to existing APIs or data models
- **No new external dependencies**

## Open Questions

- Should audit log retention have a TTL / cleanup policy? (defer to production)
- Should `tenant_admin` also see audit events scoped to their tenant? (not in scope for this change)
- Pagination: cursor-based (consistent with ADR-001) or offset-based? (offset is fine for audit — bounded dataset)
