## Why

Tenant administrators have no user interface for the approved Azure data-source backends: CAP-2 delivered the tenant-scoped connection control plane, CAP-3 the durable Blob synchronization, and CAP-4 the contract-governed PostgreSQL query path, but all lifecycle, sync, and contract state is reachable only through raw API calls. This change adds the three inventory-defined administration screens (SCR-1–SCR-3) to the existing portal shell so tenant admins can manage their two approved provider connections without ever seeing prohibited payloads.

## What Changes

- Adds a tenant-admin-only `/settings/data-sources` collection route (SCR-1) with server-backed, URL-backed search, provider/status filters, last-activity sort with ascending-`id` tie-breaker, and numbered pagination at 20 per page, including loading, empty, filtered-empty, and safe error states.
- Adds a connection detail route `/settings/data-sources/[connectionId]` (SCR-2) presenting provider-specific non-sensitive configuration, secret-reference selection, safe test/activation state with the `network_approved`/`governance_approved` evidence checklist, schedule/sync aggregate status, and confirmed pause, replacement, and retirement actions. All mutations send an `Idempotency-Key`; idempotent replays and finite safe error codes with request ID are rendered.
- Adds a schema-contract route `/settings/data-sources/[connectionId]/schema-contracts` (SCR-3) for PostgreSQL connections with contract upload, validation, publish, safe drift state, and URL-backed paginated contract history.
- Adds the tenant-admin sidebar navigation entry for data sources without altering existing routes (document upload, chat, and all current navigation stay as-is).
- Enforces the safe-display boundary throughout: no secrets, connection strings, endpoint details, provider diagnostics, SQL, prompts, answers, database rows, or tenant content are ever rendered.
- Follows the UI contract (`docs/design/ui-contract.md`, Clean foundation with existing portal override, platform web, tokens `src/portal/design-system/ner-portal/tokens.css` via `src/portal/src/app/globals.css`) and implements against the approved mockups `docs/design/mockup/data-sources.html`, `connection-detail.html`, and `schema-contracts.html`.

## Capabilities

### New Capabilities

- `tenant-data-source-portal`: tenant-admin data-source collection, safe connection lifecycle interface, and schema-contract administration interface in the portal, consuming the CAP-2 through CAP-4 safe contracts.

### Modified Capabilities

- None. The backend capabilities (`tenant-data-source-control-plane`, `azure-blob-source-sync`, `external-postgresql-chat`) are consumed, not changed; no backend requirement behaviour changes.

## Impact

- Portal only: new routes, components, hooks, and tests under `src/portal`; one navigation entry in `nav-config.ts`.
- Backend services, APIs, and database schemas are untouched.
- Existing upload and chat UI is not redesigned; no new accessibility, browser, or localisation promises beyond the UI contract.

## Open Questions

- Secret-reference picker implementation (free-text reference vs. picker control) — must preserve the closed-schema and write-only-values boundary either way.
- Browser support matrix and localisation scope remain implementation-contract decisions per the inventory gaps; defaults are current portal behaviour unless the design step says otherwise.
