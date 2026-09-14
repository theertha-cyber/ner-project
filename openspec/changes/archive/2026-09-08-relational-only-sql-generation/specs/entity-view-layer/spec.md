## ADDED Requirements

### Requirement: The query-surface resolver is the one authoritative description of the readable relations

A single resolver SHALL describe, per tenant schema, everything a consumer needs to know about the generated relations it may read: the relation names, the columns each declares with their SQL types, and the entity-definition metadata behind each relation and each `subject` entity column — the definition's name, description, examples, value kind, and value unit.

The resolver SHALL derive the relation set from the same function that decides what the reconciler maintains, and the `subject` column layout from the same function that decides the projection's column list, so the described surface cannot diverge from the surface that exists. Its consumers — the execution role's grant list, the SQL validation layer's table and column whitelist, and the SQL generator's generation context — SHALL all obtain their view of the surface from this one resolver. A second, separately maintained list of readable relations or columns SHALL NOT exist.

The resolver SHALL exclude a definition that is inactive, a definition with no assigned `sql_identifier`, and the child table an active `single` definition retains from an earlier `multi` life, exactly as the existing surface rule requires.

#### Scenario: The resolver reports columns and types, not just names

- **GIVEN** a tenant with an active `single` definition of kind `number` and an active `multi` definition
- **WHEN** the surface is resolved
- **THEN** the result SHALL name the `subject` column the `single` definition owns and declare it `DOUBLE PRECISION`
- **AND** the result SHALL name the child table and its fixed column list

#### Scenario: The resolver carries the definition's semantics

- **GIVEN** an active definition with a description and examples recorded in the catalog
- **WHEN** the surface is resolved
- **THEN** the result SHALL carry that definition's name, description, and examples alongside its relation or column

#### Scenario: The relation set matches what the reconciler maintains

- **GIVEN** any set of definitions
- **WHEN** the surface is resolved and the reconciler's expected table set is computed
- **THEN** the two SHALL be equal

#### Scenario: Off-surface relations are excluded

- **GIVEN** a tenant with an inactive definition, a definition with no `sql_identifier`, and a `single` definition whose child table was retained from a `multi` era
- **WHEN** the surface is resolved
- **THEN** none of those tables SHALL appear in the resolved relation set
- **AND** the `single` definition SHALL appear as a `subject` column

#### Scenario: One tenant's surface never includes another's relations

- **GIVEN** two tenants with different catalogs
- **WHEN** both schemas are resolved in one call
- **THEN** each schema's entry SHALL contain only that tenant's relations
- **AND** every requested schema SHALL be present in the result, carrying at least `subject`

#### Scenario: A base-model definition resolves through its label mapping

- **GIVEN** an active definition whose `base_label_mapping` maps a CoNLL label rather than matching the definition name
- **WHEN** the surface is resolved
- **THEN** the definition SHALL appear on the surface under its own name
- **AND** the mapped labels SHALL be available for associating stored entity data with that relation

### Requirement: Provisioning smoke-checks the generated relations

The execution role's smoke check SHALL read from every relation on the tenant's resolved query surface, not only from the static whitelist. A missing grant on a generated relation SHALL therefore surface during provisioning, as a permission error on a throwaway read, rather than in production as a structured retrieval failure on a user's question.

#### Scenario: A generated relation is smoke-checked

- **GIVEN** a tenant schema whose surface includes a generated child table
- **WHEN** the smoke check runs under the restricted role
- **THEN** it SHALL attempt a bounded read from that table as well as from each static whitelisted table

#### Scenario: A missing grant on a generated relation is caught at provisioning time

- **GIVEN** a generated relation the execution role has not been granted `SELECT` on
- **WHEN** the smoke check runs
- **THEN** it SHALL raise a permission error
- **AND** the failure SHALL identify the relation
