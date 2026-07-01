## ADDED Requirements

### Requirement: Entity Types API Tenant-Scoped Routes

The system SHALL expose all entity type CRUD endpoints under the tenant-scoped URL prefix `/api/v1/tenants/{tenant_slug}/entity-types`. The backend router SHALL be registered at this prefix, replacing the previous `/api/v1/entity-types` prefix. The `tenant_slug` path segment SHALL be validated against the authenticated user's JWT tenant claim by the existing dependency chain.

#### Scenario: List entity types returns 200 for authenticated tenant admin

- **GIVEN** a tenant admin is authenticated with a valid JWT for tenant slug `"acme-corp"`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types`
- **THEN** the response status is 200
- **AND** the body is `{"entity_types": [...]}` containing all entity definitions for that tenant

#### Scenario: Old URL returns 404

- **GIVEN** any authenticated user
- **WHEN** they send `GET /api/v1/entity-types`
- **THEN** the response status is 404

### Requirement: Entity Type Routes Use Name Identifier

The system SHALL accept the entity type `name` (string) as the path parameter on GET, PUT, DELETE, and PATCH endpoints (e.g., `/entity-types/{name}`). The service layer SHALL look up entity definitions by `(tenant_id, name)` rather than by UUID `id`.

#### Scenario: GET by name returns correct entity

- **GIVEN** an entity type with `name = "vendor_name"` exists for tenant `"acme-corp"`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types/vendor_name`
- **THEN** the response status is 200
- **AND** the body contains the entity with `"name": "vendor_name"`

#### Scenario: GET by name returns 404 when not found

- **GIVEN** no entity type named `"nonexistent"` exists for tenant `"acme-corp"`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types/nonexistent`
- **THEN** the response status is 404

#### Scenario: PUT by name updates and returns updated entity

- **GIVEN** an entity type `"vendor_name"` at version 1 exists for the tenant
- **WHEN** they send `PUT /api/v1/tenants/acme-corp/entity-types/vendor_name` with updated description
- **THEN** the response status is 200
- **AND** the returned entity has `"version": 2` and the updated description

### Requirement: PATCH Endpoint for Toggling Active Status

The system SHALL expose `PATCH /api/v1/tenants/{tenant_slug}/entity-types/{name}` accepting `{"is_active": boolean}` to soft-toggle an entity type's active status. The endpoint SHALL update only the `is_active` column and return the updated entity.

#### Scenario: Deactivate sets is_active to false

- **GIVEN** an entity type `"ship_to_location"` with `is_active = true`
- **WHEN** they send `PATCH /api/v1/tenants/acme-corp/entity-types/ship_to_location` with `{"is_active": false}`
- **THEN** the response status is 200
- **AND** the returned entity has `"is_active": false`

#### Scenario: Reactivate sets is_active to true

- **GIVEN** an entity type `"ship_to_location"` with `is_active = false`
- **WHEN** they send `PATCH /api/v1/tenants/acme-corp/entity-types/ship_to_location` with `{"is_active": true}`
- **THEN** the response status is 200
- **AND** the returned entity has `"is_active": true`

#### Scenario: PATCH on nonexistent name returns 404

- **GIVEN** no entity type named `"ghost"` exists for the tenant
- **WHEN** they send `PATCH /api/v1/tenants/acme-corp/entity-types/ghost` with `{"is_active": false}`
- **THEN** the response status is 404

### Requirement: Entity Type Read Responses Deserialize JSON Columns

The system SHALL return `examples` as a JSON array (`string[]`) and `base_label_mapping` as a JSON object (`Record<string, string[]>`) in all API responses. The service layer SHALL call `json.loads()` on these columns when reading from the database, since they are stored as JSON strings.

#### Scenario: List response has parsed examples array

- **GIVEN** an entity type was created with `examples = ["Acme Supplies", "Global Tech Ltd"]`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types`
- **THEN** the `examples` field in the response is a JSON array, not a string

#### Scenario: List response has parsed base_label_mapping object

- **GIVEN** an entity type was created with `base_label_mapping = {"ORG": []}`
- **WHEN** they send `GET /api/v1/tenants/acme-corp/entity-types`
- **THEN** the `base_label_mapping` field in the response is a JSON object, not a string

### Requirement: Create and Update Endpoints Return Flat Entity Object

The system SHALL return the entity type object directly (not wrapped in `{"entity_type": {...}}`) from `POST` and `PUT` endpoints, consistent with the shape expected by the frontend mutation hooks.

#### Scenario: POST returns flat entity on success

- **GIVEN** a valid create payload
- **WHEN** they send `POST /api/v1/tenants/acme-corp/entity-types`
- **THEN** the response body is a flat JSON object with `id`, `name`, `description`, `examples`, etc. at the top level (not nested under an `"entity_type"` key)

#### Scenario: PUT returns flat entity on success

- **GIVEN** an existing entity type `"vendor_name"`
- **WHEN** they send `PUT /api/v1/tenants/acme-corp/entity-types/vendor_name` with valid payload
- **THEN** the response body is a flat JSON object with the updated fields at the top level
