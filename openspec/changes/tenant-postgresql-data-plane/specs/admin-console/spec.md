## ADDED Requirements

### Requirement: System Admin chooses and observes the tenant data plane

The Create Tenant form SHALL offer a data-plane choice of "Platform database" (default) or "Tenant-owned Azure PostgreSQL", stating that the choice cannot be changed after creation and that tenant-owned tenants must use temporary or source-only original retention. The tenant list and detail views SHALL show each tenant's data-plane mode and status class and, for tenant-owned tenants, the last store health outcome class. Document counts and document quota usage SHALL be taken from the content-free document registry. No view SHALL display tenant store endpoints, credentials, or provider diagnostics.

#### Scenario: System Admin creates a tenant-owned tenant

- **GIVEN** an authenticated System Admin on `/admin/tenants`
- **WHEN** they click "Create Tenant", enter a name, select "Tenant-owned Azure PostgreSQL", and submit
- **THEN** the request SHALL include `data_plane_mode: "tenant_owned"`
- **AND** the tenant detail view SHALL show data plane "Tenant-owned" with status "Awaiting store"

#### Scenario: Document counts remain visible during a tenant outage

- **GIVEN** a tenant-owned tenant with an unreachable store and 12 registered documents
- **WHEN** the System Admin views the tenant detail page
- **THEN** document quota usage SHALL show 12
- **AND** store health SHALL show "Unreachable"
