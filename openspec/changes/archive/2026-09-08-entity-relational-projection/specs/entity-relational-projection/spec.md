## ADDED Requirements

### Requirement: The projection is written inside the existing per-document extraction transaction

The relational projection SHALL be written inside the single per-document transaction that already persists `extracted_entities` and `document_entities`. No additional transaction, background job, database trigger, or post-commit step SHALL be introduced. Within that transaction the order SHALL be: delete the document's `document_entities` rows, delete the document's relational rows, insert `extracted_entities`, insert `document_entities`, project the relational tables.

#### Scenario: EAV and relational commit together

- **GIVEN** a document that extracts three entities routed to active definitions
- **WHEN** the extraction transaction commits
- **THEN** `document_entities` SHALL contain the three entities
- **AND** the corresponding generated tables SHALL contain rows derived from the same three entities

#### Scenario: A failure rolls both back

- **GIVEN** a document whose transaction raises after `insert_document_entities` and before commit
- **WHEN** the transaction rolls back
- **THEN** the document SHALL have zero rows in `extracted_entities`
- **AND** zero rows in `document_entities`
- **AND** zero rows in every generated table
- **AND** the run's `failed_count` SHALL be incremented and the run SHALL continue with the next document

#### Scenario: No second synchronization path exists

- **GIVEN** the extraction service source
- **WHEN** the relational tables are written
- **THEN** the write SHALL originate only from the per-document transaction in the extraction worker
- **AND** no scheduled job, trigger, or refresh mechanism SHALL write them

### Requirement: The projection consumes the in-memory entity list and never re-reads the EAV store

The projection SHALL take the same final `list[NormalizedEntity]` that is passed to `insert_document_entities`. It SHALL NOT issue a `SELECT` against `document_entities` to build its statements.

#### Scenario: The projection issues no read of document_entities

- **GIVEN** a document being projected
- **WHEN** the projection statements are built and executed
- **THEN** no `SELECT` against `document_entities` SHALL be issued by the projection

#### Scenario: Post-processing results reach the relational tables

- **GIVEN** a document whose post-processing merged two candidate entities into one
- **WHEN** the projection runs
- **THEN** the generated table SHALL contain the merged entity only
- **AND** entities recorded in the post-processing outcome as discarded SHALL appear in neither store

### Requirement: Entities are routed to definitions by entity-type literal, case-insensitively

Routing SHALL build an index keyed by every uppercased literal returned by `entity_type_literals(definition)` — the uppercased definition `name` plus every uppercased key of that definition's `base_label_mapping` — and SHALL route each entity by the uppercased, stripped value of its `entity_type`. Routing by equality against the definition `name` alone SHALL NOT be used.

#### Scenario: A fine-tuned label routes by name

- **GIVEN** an active definition named `Skill` and an entity whose `entity_type` is `SKILL`
- **WHEN** the entity is routed
- **THEN** it SHALL route to the `Skill` definition

#### Scenario: A base-model CoNLL label routes through base_label_mapping

- **GIVEN** an active definition named `Employer` whose `base_label_mapping` contains the key `ORG`
- **AND** an entity whose `entity_type` is `ORG`
- **WHEN** the entity is routed
- **THEN** it SHALL route to the `Employer` definition
- **AND** the row SHALL be written to that definition's generated table

#### Scenario: Stored case differing from definition case still routes

- **GIVEN** an active definition named `Employer` and an entity whose `entity_type` is `employer`
- **WHEN** the entity is routed
- **THEN** it SHALL route to the `Employer` definition

#### Scenario: Routing and DDL agree on the literal set

- **GIVEN** any definition
- **WHEN** its generated relation is created and its entities are routed
- **THEN** both SHALL derive the entity-type literals from the same `entity_type_literals` helper

### Requirement: A literal claimed by two active definitions routes to exactly one

When two or more active definitions claim the same uppercased entity-type literal, the system SHALL treat it as a catalog misconfiguration and SHALL route the entity to exactly one definition: the one whose own uppercased `name` equals the literal; if no definition's name matches, the first definition by `sql_identifier` sort order. The system SHALL log a warning naming the colliding definitions. The entity SHALL NOT be written to more than one generated table.

#### Scenario: A name match wins the collision

- **GIVEN** an active definition named `ORG` and another named `Employer` whose `base_label_mapping` contains the key `ORG`
- **AND** an entity whose `entity_type` is `ORG`
- **WHEN** the entity is routed
- **THEN** it SHALL route to the definition named `ORG` only
- **AND** a warning SHALL be logged

#### Scenario: With no name match, sort order decides deterministically

- **GIVEN** two active definitions, neither named `ORG`, both mapping the base label `ORG`
- **WHEN** an entity with `entity_type` `ORG` is routed
- **THEN** it SHALL route to the definition whose `sql_identifier` sorts first
- **AND** repeating the same input SHALL produce the same routing

#### Scenario: A collision never double-writes

- **GIVEN** any colliding literal
- **WHEN** the projection statements are generated
- **THEN** the entity SHALL appear in exactly one generated table

### Requirement: Entities matching no definition are written to the EAV store only

An entity whose uppercased `entity_type` is claimed by no active definition SHALL be written to `document_entities` and SHALL be skipped by the projection. The skip SHALL be logged at debug level and SHALL NOT fail the document.

#### Scenario: An undefined type still reaches the system of record

- **GIVEN** an entity whose `entity_type` matches no active definition's literals
- **WHEN** the document is persisted
- **THEN** the entity SHALL exist in `document_entities`
- **AND** it SHALL appear in no generated table
- **AND** the document SHALL be counted as processed, not failed

### Requirement: Each active multi-valued definition receives one row per routed entity

For a definition with `cardinality = 'multi'` and `is_active` true, every routed entity SHALL be written as one row in that definition's generated table, carrying `document_id`, `value`, `normalized_value`, the typed value fields, `value_unit`, `confidence`, `page_number`, and `occurrence_count`. The insert SHALL use `ON CONFLICT (document_id, normalized_value) DO UPDATE` as a safety net, retaining the greater `confidence` and summing `occurrence_count`.

#### Scenario: Three routed entities produce three rows

- **GIVEN** an active `multi` definition and three routed entities with distinct `normalized_value`
- **WHEN** the projection runs
- **THEN** the generated table SHALL contain exactly three rows for that document

#### Scenario: Two source labels collapsing onto one definition do not raise

- **GIVEN** an active `multi` definition claiming two base labels
- **AND** two routed entities that share a `normalized_value`
- **WHEN** the projection runs
- **THEN** the statement SHALL NOT raise a unique-violation
- **AND** the surviving row SHALL carry the greater of the two `confidence` values

### Requirement: Single-valued selection is deterministic

For a definition with `cardinality = 'single'` and `is_active` true, exactly one value per document SHALL be written to the `subject` row. Selection SHALL be performed in memory over the routed entities by sorting on `(-confidence, -occurrence_count, normalized_value)` and taking the first. Selection SHALL NOT be expressed in generated SQL.

#### Scenario: The highest-confidence value is selected

- **GIVEN** three entities routed to one `single` definition with confidences 0.9, 0.7, and 0.5
- **WHEN** selection runs
- **THEN** the entity with confidence 0.9 SHALL be written to `subject`

#### Scenario: A confidence tie is broken deterministically

- **GIVEN** two entities routed to one `single` definition with equal `confidence` and equal `occurrence_count`
- **WHEN** selection runs twice over the same input in different list orders
- **THEN** both runs SHALL select the same entity
- **AND** the selected entity SHALL be the one whose `normalized_value` sorts first

#### Scenario: Unselected values remain in the system of record

- **GIVEN** three entities routed to one `single` definition
- **WHEN** the document is persisted
- **THEN** `subject` SHALL carry one value
- **AND** `document_entities` SHALL still contain all three entities

### Requirement: The projected column value is determined by the definition's value kind

The value written to a `subject` column SHALL be selected by the definition's `value_kind`: `entity.value_number` for `number`, `money`, `duration`, and `boolean`; `entity.value_date` for `date`; the entity's surface value for `text`, NULL, and any other kind. When a typed kind yields no parsed value, the column SHALL be NULL. The surface text SHALL NOT be written into a typed column as a fallback.

#### Scenario: A numeric kind writes the parsed number

- **GIVEN** a `single` definition with `value_kind` `number` and a routed entity whose `value_number` is 7.0
- **WHEN** the projection runs
- **THEN** the `subject` column SHALL hold 7.0

#### Scenario: An unparseable typed value writes NULL

- **GIVEN** a `single` definition with `value_kind` `number` and a routed entity whose `value_number` is NULL
- **WHEN** the projection runs
- **THEN** the `subject` column SHALL be NULL
- **AND** it SHALL NOT contain the entity's surface text

#### Scenario: A text kind writes the surface value

- **GIVEN** a `single` definition with `value_kind` `text`
- **WHEN** the projection runs
- **THEN** the `subject` column SHALL hold the entity's surface value

### Requirement: Every extracted document gets a subject row

A document that completes extraction SHALL have exactly one `subject` row carrying its `document_id` and `filename`, even when zero entities were extracted or none routed to a `single` definition. A document that has never been extracted SHALL have no `subject` row.

#### Scenario: A zero-entity document still gets a row

- **GIVEN** a document from which the model extracted no entities
- **WHEN** extraction completes for that document
- **THEN** `subject` SHALL contain one row for it
- **AND** every entity column in that row SHALL be NULL
- **AND** `filename` SHALL be populated

#### Scenario: A never-extracted document has no row

- **GIVEN** a document in `processed` status that no extraction run has covered
- **WHEN** `subject` is queried
- **THEN** it SHALL contain no row for that document

#### Scenario: A definition with no matching entities yields no child rows

- **GIVEN** an active `multi` definition and a document with no entities routed to it
- **WHEN** extraction completes
- **THEN** that definition's generated table SHALL contain zero rows for the document
- **AND** the document SHALL still have a `subject` row

### Requirement: Re-extraction replaces a document's entity rows rather than appending

Before inserting, the transaction SHALL delete the document's rows from `document_entities` and from every generated relational table. The delete SHALL cover all existing generated tables, not only those whose definitions are currently active. `extracted_entities` SHALL NOT be deleted by the worker.

#### Scenario: Re-extraction under a new model version does not duplicate

- **GIVEN** a document already extracted under model version 3 with five entities in `document_entities`
- **WHEN** the document is re-extracted under model version 4 producing five entities
- **THEN** `document_entities` SHALL contain five rows for that document, not ten
- **AND** the generated tables SHALL reflect only the newest extraction

#### Scenario: The idempotency ledger is preserved

- **GIVEN** a document re-extracted under a new model version
- **WHEN** the transaction commits
- **THEN** `extracted_entities` SHALL retain the rows from the earlier run
- **AND** SHALL additionally contain the new run's rows

#### Scenario: A deactivated definition's stale rows are still cleared

- **GIVEN** a document with rows in a generated table whose definition has since been deactivated
- **WHEN** the document is re-extracted
- **THEN** those stale rows SHALL be deleted
- **AND** no new rows SHALL be written to that table

### Requirement: Relational rows are deleted through a shared pure statement builder

The projection module SHALL expose `build_relational_delete_statements(schema, document_id, specs)` as a pure function returning parameterized statements and executing nothing, so that the synchronous extraction worker and the asynchronous document-delete path execute identical statements. The delete SHALL remove the document's rows from every generated child table and its `subject` row.

#### Scenario: The builder executes nothing

- **GIVEN** a schema, a document id, and a definition list
- **WHEN** `build_relational_delete_statements` is called with no database reachable
- **THEN** it SHALL return the statement list without error

#### Scenario: Both callers use the same statements

- **GIVEN** the extraction worker's delete path and the document-delete endpoint's delete path
- **WHEN** each builds its statements for the same document
- **THEN** the two statement lists SHALL be equal

#### Scenario: The subject row is included

- **GIVEN** a document with a `subject` row and rows in two child tables
- **WHEN** the delete statements are executed
- **THEN** all three SHALL be removed

### Requirement: A missing generated relation fails the document

If projection encounters a missing table or missing column, the document SHALL fail: the transaction SHALL roll back, `failed_count` SHALL be incremented, and the run SHALL continue. The condition SHALL NOT be silently skipped and SHALL NOT be repaired by emitting DDL inside the per-document transaction.

#### Scenario: A missing table fails the document visibly

- **GIVEN** an active definition whose generated table has been dropped out of band
- **WHEN** a document routing entities to it is projected
- **THEN** the document SHALL be recorded as failed
- **AND** the run SHALL continue with remaining documents
- **AND** the document SHALL have no rows in `document_entities`

#### Scenario: Projection emits no DDL

- **GIVEN** any document being projected
- **WHEN** the projection statements are generated
- **THEN** none of them SHALL be a `CREATE`, `ALTER`, or `DROP` statement

### Requirement: Provenance fields are not projected

`source_entity_value`, `source_entity_type`, `postprocess_status`, `postprocess_model`, `postprocess_prompt_version`, `postprocess_at`, `extraction_schema_version`, `char_start`, and `char_end` SHALL remain in `document_entities` and SHALL NOT be written to any generated table. `confidence` and `page_number` SHALL be projected to child tables and SHALL NOT be projected to `subject`.

#### Scenario: Child tables carry values, not provenance

- **GIVEN** an entity carrying full provenance
- **WHEN** it is projected into a child table
- **THEN** the row SHALL carry `confidence` and `page_number`
- **AND** SHALL carry no provenance column

#### Scenario: Provenance remains joinable

- **GIVEN** a projected entity
- **WHEN** `document_entities` is joined to the child table on `(document_id, normalized_value)`
- **THEN** the provenance for that entity SHALL be retrievable

### Requirement: Generated identifiers are validated and unassigned definitions are skipped

Every identifier used in a generated statement SHALL come from `entity_definitions.sql_identifier` and SHALL be validated against `^e_[a-z0-9][a-z0-9_]*$` before entering any DDL or DML position. A definition whose `sql_identifier` is NULL SHALL be skipped, and SHALL NOT be slugged at read time. Entity-type literals SHALL be treated as values, not identifiers.

#### Scenario: A definition with no identifier is skipped

- **GIVEN** an active definition whose `sql_identifier` is NULL
- **WHEN** projection statements are generated
- **THEN** no statement SHALL reference that definition
- **AND** no identifier SHALL be derived from its `name` at generation time

#### Scenario: A hostile entity name cannot reach a statement

- **GIVEN** a definition named `"; DROP TABLE documents; --"` with a validated `sql_identifier`
- **WHEN** projection statements are generated
- **THEN** no statement SHALL contain `DROP TABLE`
- **AND** the entity-type literal SHALL be passed as a bound parameter rather than interpolated

### Requirement: Generated statements are schema-qualified by the caller

Every generated statement SHALL be qualified with the tenant schema string supplied by the caller — the same value already passed to `insert_document_entities`. The projection module SHALL NOT resolve a tenant schema itself, and definitions SHALL be loaded filtered by `tenant_id`.

#### Scenario: The module resolves no schema

- **GIVEN** the projection module
- **WHEN** statements are generated
- **THEN** the schema SHALL come from the caller's argument
- **AND** the module SHALL contain no tenant-to-schema resolution

#### Scenario: Statements target only the caller's schema

- **GIVEN** schema `tenant_acme`
- **WHEN** statements are generated
- **THEN** every table reference SHALL be qualified with `tenant_acme`
