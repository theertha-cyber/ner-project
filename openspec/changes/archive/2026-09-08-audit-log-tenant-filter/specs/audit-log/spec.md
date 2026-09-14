## ADDED Requirements

### Requirement: Audit Log Endpoint Tenant Filtering

The `GET /api/v1/admin/audit-log` endpoint SHALL accept an optional `tenant_id` query parameter. When `tenant_id` is omitted or empty, the endpoint SHALL return events for all tenants exactly as it does today (no behavior change). When `tenant_id` is supplied, the endpoint SHALL return only audit events whose `tenant_id` column equals the supplied value, with `total` reflecting the filtered count and results still ordered by `created_at` descending, paginated by the existing `page`/`per_page` parameters.

#### Scenario: No tenant filter supplied

- **GIVEN** an authenticated System Admin and audit events across multiple tenants
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?page=1&per_page=50` with no `tenant_id`
- **THEN** the response SHALL include events from all tenants
- **AND** `total` SHALL equal the total count of all audit events

#### Scenario: Tenant filter supplied

- **GIVEN** an authenticated System Admin, tenant `tid-123` with 5 audit events, and other tenants with additional events
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?tenant_id=tid-123&page=1&per_page=50`
- **THEN** the response SHALL include only the 5 events belonging to `tid-123`
- **AND** `total` SHALL equal `5`
- **AND** events SHALL be ordered by `created_at` descending

#### Scenario: Tenant filter with no matching events

- **GIVEN** an authenticated System Admin and tenant `tid-456` with zero audit events
- **WHEN** the System Admin calls `GET /api/v1/admin/audit-log?tenant_id=tid-456`
- **THEN** the response SHALL include an empty `events` array
- **AND** `total` SHALL equal `0`

### Requirement: Audit Log Page Tenant Filter UI

The System Admin `/audit` page SHALL display a searchable tenant filter above the audit event list, near the page title/metadata. The filter's default and first option SHALL be "All Tenants". Every existing tenant returned by `GET /api/v1/admin/tenants` SHALL appear as an option below it. Selecting a tenant SHALL refresh the displayed audit events to that tenant's events only, using the tenant-filtered endpoint request, and SHALL reset pagination to page 1. Selecting "All Tenants" after a tenant was selected SHALL restore the full, unfiltered chronological audit history. The selected tenant SHALL be retained in page state for the duration of the page visit (no persistence across reload/navigation is required).

#### Scenario: Default view shows all tenants

- **GIVEN** an authenticated System Admin navigating to `/audit` for the first time in this session
- **WHEN** the page loads
- **THEN** the tenant filter SHALL show "All Tenants" as the selected value
- **AND** the event list SHALL show events from all tenants, most recent first

#### Scenario: Filtering to a specific tenant

- **GIVEN** an authenticated System Admin on `/audit` with the filter set to "All Tenants", and tenant "Acme Corp" exists with audit events
- **WHEN** the System Admin selects "Acme Corp" from the tenant filter
- **THEN** the event list SHALL refresh to show only "Acme Corp" events
- **AND** pagination SHALL reset to page 1
- **AND** chronological ordering (most recent first) SHALL be preserved

#### Scenario: Returning to All Tenants

- **GIVEN** an authenticated System Admin on `/audit` with the filter set to "Acme Corp"
- **WHEN** the System Admin selects "All Tenants" from the filter
- **THEN** the event list SHALL refresh to show the complete, unfiltered audit history
- **AND** pagination SHALL reset to page 1

#### Scenario: Empty state for a tenant with no audit events

- **GIVEN** an authenticated System Admin on `/audit`, and tenant "New Co" exists with zero audit events
- **WHEN** the System Admin selects "New Co" from the tenant filter
- **THEN** the page SHALL display an empty-state message indicating no audit events exist for the selected tenant
- **AND** SHALL NOT display pagination controls

#### Scenario: Tenant filter is searchable

- **GIVEN** an authenticated System Admin on `/audit` with more than one tenant available in the filter
- **WHEN** the System Admin types a partial tenant name into the filter
- **THEN** the dropdown SHALL narrow its visible options to tenants matching the typed text
