## ADDED Requirements

### Requirement: A generated `subject` column's physical type equals the type its definition declares

After any successful reconciliation of a tenant schema, every `subject` column owned by an
active `single` entity definition SHALL have exactly the PostgreSQL type that definition's
`value_kind` declares. The reconciler SHALL determine the column's actual type from the
database rather than assuming the type it was created with, and SHALL emit the DDL that
converges any column whose actual type differs.

A divergence SHALL NOT be resolved by skipping, by logging alone, or by leaving the column at
its existing type. Reconciliation either converges the column or fails; it SHALL NOT report
success over a schema that still disagrees with the catalog.

This invariant SHALL hold for every supported `value_kind` and in every direction between the
types they declare, including pairs PostgreSQL provides no cast between.

#### Scenario: A column created under one kind converges when the kind changes

- **GIVEN** an active `single` definition whose `subject` column exists as `TEXT`
- **WHEN** its `value_kind` is changed to one declaring `DOUBLE PRECISION` and the schema is reconciled
- **THEN** the column's physical type SHALL be `DOUBLE PRECISION`

#### Scenario: Convergence works in the reverse direction

- **GIVEN** an active `single` definition whose `subject` column exists as `DOUBLE PRECISION`
- **WHEN** its `value_kind` is changed to one declaring `TEXT` and the schema is reconciled
- **THEN** the column's physical type SHALL be `TEXT`

#### Scenario: Convergence works between types with no PostgreSQL cast

- **GIVEN** an active `single` definition whose `subject` column exists as `DOUBLE PRECISION`
- **WHEN** its `value_kind` is changed to `date` and the schema is reconciled
- **THEN** the column's physical type SHALL be `DATE`
- **AND** the reconciliation SHALL NOT raise

#### Scenario: A kind change cannot fail on the data the column holds

- **GIVEN** a `subject` column of type `TEXT` holding values that cannot be parsed as a number
- **WHEN** its definition's `value_kind` is changed to one declaring `DOUBLE PRECISION` and the schema is reconciled
- **THEN** the reconciliation SHALL succeed
- **AND** the column's physical type SHALL be `DOUBLE PRECISION`

#### Scenario: An already-correct column is left untouched

- **GIVEN** a tenant schema whose every `subject` column already matches its declared type
- **WHEN** the schema is reconciled
- **THEN** no column-type statement SHALL be emitted
- **AND** the reconciliation SHALL be idempotent over repeated runs

#### Scenario: A newly created column needs no convergence

- **GIVEN** an active `single` definition whose `subject` column does not exist yet
- **WHEN** the schema is reconciled
- **THEN** the column SHALL be created at its declared type
- **AND** no column-type statement SHALL be emitted for it

### Requirement: Converging a column preserves the system of record and destroys no relation

Converging a column's type SHALL discard the values that column held, because they are a
projection computed under the definition's previous `value_kind` and are not the correct
representation under the new one. The correct value SHALL be re-derived from the entity store
by the existing projection at the next extraction of each document; no cast of the previous
column value SHALL be treated as the new value.

Convergence SHALL NOT read from, write to, or alter `document_entities`, and SHALL NOT drop or
truncate any generated relation or column. Each converged column SHALL be logged, naming the
column and both types, so that a cleared column is attributable.

#### Scenario: The entity store is untouched by a type change

- **GIVEN** a tenant whose `document_entities` holds rows for a `single` definition
- **WHEN** that definition's `value_kind` changes and the schema is reconciled
- **THEN** `document_entities` SHALL be unchanged in content and shape

#### Scenario: The column is cleared rather than cast

- **GIVEN** a `subject` column of type `TEXT` holding `'5 years'`
- **WHEN** its definition's `value_kind` changes to one declaring `DOUBLE PRECISION` and the schema is reconciled
- **THEN** the column SHALL hold NULL
- **AND** the reconciliation SHALL emit a log line naming the column and both types

#### Scenario: No generated relation is dropped by a type change

- **GIVEN** any set of definitions and any physical schema state
- **WHEN** the reconciliation statements are generated
- **THEN** they SHALL contain no `DROP TABLE`, `DROP COLUMN`, `DELETE`, or `TRUNCATE`

#### Scenario: The projection writes the new representation after convergence

- **GIVEN** a `single` definition whose `value_kind` has changed and whose column has converged
- **WHEN** a document carrying that entity is extracted
- **THEN** the column SHALL hold the representation the new `value_kind` selects

### Requirement: A column no active `single` definition owns is left at its existing type

A `subject` column whose definition is inactive, or whose cardinality has moved to `multi`, is
off the query surface: nothing projects into it and no generated statement may read it. The
reconciler SHALL leave such a column's type and contents alone, exactly as it retains the child
table a definition keeps after a cardinality flip.

#### Scenario: A deactivated definition's column keeps its type and rows

- **GIVEN** an active `single` definition whose `subject` column holds values
- **WHEN** the definition is deactivated and the schema is reconciled
- **THEN** the column SHALL retain its type and its values

#### Scenario: A column reclaimed by a reactivated definition converges

- **GIVEN** a deactivated `single` definition whose column type no longer matches its `value_kind`
- **WHEN** the definition is reactivated and the schema is reconciled
- **THEN** the column's physical type SHALL match its declared type

### Requirement: A failed convergence leaves the catalog and the physical schema consistent

An entity-definition write and the reconciliation it triggers SHALL remain in one transaction,
so that a reconciliation that raises rolls the catalog change back with it. The system SHALL
NOT commit a `value_kind` whose column could not be converged.

#### Scenario: A failing reconciliation rolls back the definition change

- **GIVEN** an entity-definition update that changes `value_kind`
- **WHEN** the reconciliation raises while applying the schema change
- **THEN** the update SHALL NOT be committed
- **AND** the definition's persisted `value_kind` SHALL still match the column's physical type
