## ADDED Requirements

### Requirement: Entity Type Provenance

Each entity type SHALL carry a `provenance` value of `manual`, `suggested`, or `imported`,
and an optional `provenance_ref` string. `provenance` SHALL be assigned when the entity
type is created and SHALL NOT change on any later update. Creating an entity type through
the plain create endpoint SHALL default `provenance` to `manual`. Approving an LLM
schema-proposal candidate SHALL create the entity type with `provenance = 'suggested'` and
SHALL set `provenance_ref` to the proposal's schema version label when available. Mapping an
unknown entity type to a newly-created type during annotation import SHALL create it with
`provenance = 'imported'` and SHALL set `provenance_ref` to the source filename.

#### Scenario: A hand-created entity type is manual

- **GIVEN** an authenticated Tenant Admin
- **WHEN** they POST a new entity type through `/api/v1/tenants/{slug}/entity-types`
- **THEN** the created entity type SHALL have `provenance: "manual"`

#### Scenario: An approved schema-proposal candidate is suggested

- **GIVEN** a schema proposal containing a pending candidate `contract_id`
- **WHEN** a Tenant Admin approves that candidate
- **THEN** the created entity type `contract_id` SHALL have `provenance: "suggested"`

#### Scenario: A type created while mapping an import is imported

- **GIVEN** an annotation import with an unmapped type `party_name`
- **WHEN** a Tenant Admin maps it by choosing "create new"
- **THEN** the created entity type `party_name` SHALL have `provenance: "imported"`
- **AND** `provenance_ref` SHALL be the import's source filename

#### Scenario: Provenance is immutable across updates

- **GIVEN** an entity type with `provenance: "suggested"` at version 1
- **WHEN** a Tenant Admin updates its description
- **THEN** the version SHALL increment
- **AND** `provenance` SHALL still be `"suggested"`
