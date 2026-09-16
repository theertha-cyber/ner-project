## ADDED Requirements

### Requirement: Entity Type Responses Include Provenance

Every entity type object returned by the tenant-scoped entity-type routes — list, single
GET, and the flat objects returned by `POST` and `PUT` — SHALL include `provenance`
(`"manual"` | `"suggested"` | `"imported"`) and `provenance_ref` (string or `null`).

#### Scenario: List response includes provenance

- **GIVEN** entity types created by hand, by schema-proposal approval, and by import mapping
- **WHEN** a caller sends `GET /api/v1/tenants/{slug}/entity-types`
- **THEN** each entity type in the response SHALL carry a `provenance` field with the
  corresponding value and a `provenance_ref` field

#### Scenario: Create response includes provenance

- **GIVEN** a valid create payload with no `provenance` field
- **WHEN** a caller sends `POST /api/v1/tenants/{slug}/entity-types`
- **THEN** the flat response object SHALL include `provenance: "manual"` and
  `provenance_ref: null`

#### Scenario: A client-supplied provenance on create is ignored

- **GIVEN** a create payload that sets `provenance: "suggested"`
- **WHEN** a caller sends `POST /api/v1/tenants/{slug}/entity-types`
- **THEN** the created entity type SHALL have `provenance: "manual"` — provenance is
  assigned by the server according to the creation path, not the request body
