## RENAMED Requirements

- FROM: `### Requirement: View DDL is produced by a pure function`
- TO: `### Requirement: Table DDL is produced by a pure function`

- FROM: `### Requirement: Each active multi-valued entity gets a child view`
- TO: `### Requirement: Each active multi-valued entity gets a child table`

- FROM: `### Requirement: Each tenant gets a subject view pivoting its single-valued entities`
- TO: `### Requirement: Each tenant gets a subject table with one column per single-valued entity`

## MODIFIED Requirements

### Requirement: Table DDL is produced by a pure function

`build_entity_table_statements(schema, definitions)` SHALL return a `list[str]` of DDL statements and SHALL NOT execute anything, open a connection, or require a database. The same inputs SHALL yield byte-identical output on every call, with definitions ordered by `sql_identifier`. Every returned statement SHALL be safe to re-run against a schema where it has already been applied, using `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, and `CREATE INDEX IF NOT EXISTS`. No returned statement SHALL be a `DROP`, `DELETE`, or `TRUNCATE`.

#### Scenario: The generator touches no database

- **GIVEN** a list of entity definition specs and a schema name
- **WHEN** `build_entity_table_statements` is called with no database configured or reachable
- **THEN** it SHALL return the statement list without error

#### Scenario: Generation is idempotent

- **GIVEN** the same schema and definition list
- **WHEN** `build_entity_table_statements` is called twice
- **THEN** the two returned lists SHALL be equal

#### Scenario: The schema name is validated

- **GIVEN** a schema argument that is not a bare SQL identifier
- **WHEN** `build_entity_table_statements` is called
- **THEN** it SHALL raise rather than emit the statement

#### Scenario: Every statement is re-runnable

- **GIVEN** any definition list
- **WHEN** statements are generated
- **THEN** every `CREATE TABLE` SHALL carry `IF NOT EXISTS`
- **AND** every `ALTER TABLE … ADD COLUMN` SHALL carry `IF NOT EXISTS`
- **AND** every `CREATE INDEX` SHALL carry `IF NOT EXISTS`

#### Scenario: No destructive statement is ever emitted

- **GIVEN** any definition list, including inactive and orphaned definitions
- **WHEN** statements are generated
- **THEN** the output SHALL contain no `DROP TABLE`, `DROP VIEW`, `DROP COLUMN`, `DELETE`, or `TRUNCATE`

### Requirement: Each active multi-valued entity gets a child table

For every definition with `is_active` true and `cardinality = 'multi'`, the generator SHALL emit `CREATE TABLE IF NOT EXISTS <schema>.<sql_identifier>` with the fixed column list `document_id VARCHAR NOT NULL`, `value TEXT NOT NULL`, `normalized_value TEXT NOT NULL`, `value_number DOUBLE PRECISION`, `value_number_high DOUBLE PRECISION`, `value_date DATE`, `value_date_high DATE`, `value_unit TEXT`, `confidence DOUBLE PRECISION NOT NULL`, `page_number INTEGER`, and `occurrence_count INTEGER NOT NULL DEFAULT 1`, with `PRIMARY KEY (document_id, normalized_value)`, plus `CREATE INDEX IF NOT EXISTS` on `normalized_value`. The column list SHALL be fixed and SHALL NOT be derived from `value_kind`, so that introducing a new value kind never requires an `ALTER` on an existing child table. The child tables SHALL have no foreign key to `documents`; referential integrity is maintained by delete propagation.

#### Scenario: A multi definition produces its child table

- **GIVEN** an active definition with `name = 'SKILL'`, `sql_identifier = 'e_skill'`, `cardinality = 'multi'`
- **WHEN** statements are generated for schema `tenant_acme`
- **THEN** the output SHALL contain `CREATE TABLE IF NOT EXISTS tenant_acme.e_skill`
- **AND** that statement SHALL declare `PRIMARY KEY (document_id, normalized_value)`
- **AND** the output SHALL contain a `CREATE INDEX IF NOT EXISTS` on its `normalized_value`

#### Scenario: Many multi definitions each get their own table

- **GIVEN** three active `multi` definitions with distinct `sql_identifier` values
- **WHEN** statements are generated
- **THEN** the output SHALL contain exactly three child-table `CREATE TABLE IF NOT EXISTS` statements

#### Scenario: The column list does not vary with value kind

- **GIVEN** two active `multi` definitions with different `value_kind` values
- **WHEN** statements are generated
- **THEN** both child tables SHALL declare the identical column list

#### Scenario: No foreign key to documents is declared

- **GIVEN** any active `multi` definition
- **WHEN** its `CREATE TABLE` statement is generated
- **THEN** it SHALL declare no `REFERENCES` clause

### Requirement: Each tenant gets a subject table with one column per single-valued entity

The generator SHALL emit exactly one `CREATE TABLE IF NOT EXISTS <schema>.subject (document_id VARCHAR PRIMARY KEY, filename TEXT)` per tenant schema, followed by one `ALTER TABLE <schema>.subject ADD COLUMN IF NOT EXISTS <column> <type>` per active `cardinality = 'single'` definition. The column type SHALL be `DOUBLE PRECISION` for `value_kind` of `number`, `money`, `duration`, or `boolean`; `DATE` for `date`; and `TEXT` for `text`, NULL, or any other kind. Exactly one column SHALL be added per single definition. The column name SHALL be the `sql_identifier` with its `e_` prefix stripped, disambiguated against `document_id`, `filename`, and every already-taken column by the existing uniqueness rule. `filename` SHALL be denormalized onto `subject` and written on every projection.

#### Scenario: A single definition becomes a subject column

- **GIVEN** an active definition with `sql_identifier = 'e_email'` and `cardinality = 'single'`
- **WHEN** statements are generated
- **THEN** the output SHALL contain `ADD COLUMN IF NOT EXISTS email TEXT`

#### Scenario: Zero single definitions still yields a valid subject table

- **GIVEN** a definition list containing no active `single` definitions
- **WHEN** statements are generated
- **THEN** the output SHALL still contain the `CREATE TABLE IF NOT EXISTS <schema>.subject` statement projecting `document_id` and `filename`
- **AND** SHALL contain no `ADD COLUMN` statement

#### Scenario: A typed single entity gets a typed column only

- **GIVEN** an active `single` definition with `value_kind` `number` and `sql_identifier = 'e_years_experience'`
- **WHEN** statements are generated
- **THEN** the output SHALL contain `ADD COLUMN IF NOT EXISTS years_experience DOUBLE PRECISION`
- **AND** SHALL NOT contain a `years_experience_text` column

#### Scenario: A date kind gets a DATE column

- **GIVEN** an active `single` definition with `value_kind` `date`
- **WHEN** statements are generated
- **THEN** its column SHALL be declared `DATE`

#### Scenario: A column name colliding with an identity column is disambiguated

- **GIVEN** an active `single` definition whose `sql_identifier` is `e_filename` or `e_document_id`
- **WHEN** statements are generated
- **THEN** the added column SHALL NOT be named `filename` or `document_id`
- **AND** the statement SHALL be valid SQL

#### Scenario: Adding a single definition later does not rewrite the table

- **GIVEN** a schema whose `subject` table already exists with one entity column
- **WHEN** a second `single` definition is added and the statements are re-applied
- **THEN** the new column SHALL be added with no default
- **AND** the existing rows SHALL be preserved with NULL in the new column

### Requirement: Entity type matching is case-insensitive and covers base-model labels

The set of entity-type literals for a definition SHALL be the uppercased definition `name` plus every uppercased key of that definition's `base_label_mapping`, sorted. It SHALL be exposed as a public helper, `entity_type_literals(definition)`, so that the DDL generator, the projection router, and the query-surface resolver all derive it from one implementation. Exact-case equality SHALL NOT be used, because no comparison anywhere in the extraction, normalization, or retrieval path assumes stored case equals definition case, and because on the base-model path `document_entities.entity_type` holds a CoNLL label rather than the tenant's name.

#### Scenario: The literal set is publicly available

- **GIVEN** the entity view layer module
- **WHEN** a caller outside the module needs a definition's entity-type literals
- **THEN** `entity_type_literals` SHALL be importable as a public name

#### Scenario: Stored case differing from definition case still matches

- **GIVEN** a definition named `Skill` and rows stored with `entity_type = 'SKILL'`
- **WHEN** the literal set is computed
- **THEN** it SHALL contain `SKILL`

#### Scenario: A base-model label is included

- **GIVEN** a definition named `Employer` with `base_label_mapping` containing the key `ORG`
- **WHEN** the literal set is computed
- **THEN** it SHALL contain both `EMPLOYER` and `ORG`

#### Scenario: A definition without a base label mapping yields the name alone

- **GIVEN** a definition whose `base_label_mapping` is NULL or empty
- **WHEN** the literal set is computed
- **THEN** it SHALL contain only the uppercased definition name

#### Scenario: The set is deterministically ordered

- **GIVEN** any definition
- **WHEN** the literal set is computed twice
- **THEN** both results SHALL be equal and sorted

### Requirement: The reconciler applies generated DDL idempotently per tenant schema

`reconcile_entity_tables(session, schema, definitions)` SHALL execute the generated statements against `schema` and return the statements applied. It SHALL be safe to run repeatedly. It SHALL skip — without raising — any schema that does not contain a `document_entities` table, which is the older-template case migrations `029` and `035` guard the same way. It SHALL create the bare `subject` table for a tenant schema that has no definitions at all. It SHALL NOT drop any relation or column.

#### Scenario: A missing table is created

- **GIVEN** a tenant schema with `document_entities` but no generated entity tables
- **WHEN** the reconciler runs with one active `multi` definition
- **THEN** the child table SHALL exist afterwards and be queryable

#### Scenario: A stale subject table is repaired

- **GIVEN** a tenant schema whose `subject` table predates a newly added `single` definition
- **WHEN** the reconciler runs with the updated definition list
- **THEN** `subject` SHALL carry the new column
- **AND** existing rows SHALL be preserved

#### Scenario: A schema without document_entities is skipped

- **GIVEN** a tenant schema provisioned from a template predating `document_entities`
- **WHEN** the reconciler runs against it
- **THEN** it SHALL return without raising
- **AND** it SHALL create no tables in that schema

#### Scenario: A tenant with no definitions still gets subject

- **GIVEN** a tenant schema with `document_entities` and an empty definition list
- **WHEN** the reconciler runs
- **THEN** `<schema>.subject` SHALL exist and be queryable
- **AND** it SHALL have the columns `document_id` and `filename`

#### Scenario: Running twice changes nothing the second time

- **GIVEN** a reconciled tenant schema
- **WHEN** the reconciler runs again with the same definitions
- **THEN** it SHALL succeed
- **AND** the set of tables and columns in the schema SHALL be identical

#### Scenario: A freshly provisioned tenant is covered at run start

- **GIVEN** a tenant schema cloned from `tenant_template`, which carries no generated entity tables
- **WHEN** a batch extraction run reconciles before its document loop
- **THEN** every active definition's table SHALL exist before the first document is projected

## ADDED Requirements

### Requirement: Deactivation and orphaning never drop a generated relation

Because `is_active` is a reversible flag — `toggle_entity_type` flips it in both directions and `soft_delete_entity_type` only sets it false — the system SHALL NOT drop or alter a generated table or column when a definition becomes inactive or disappears from the catalog. An inactive definition SHALL be excluded from projection, from the execution role's grants, and from the query-surface whitelist, while its table and rows are retained. Reactivation SHALL restore the definition to all three without recreating data. A table whose definition is absent from the catalog entirely SHALL be left in place and logged; removing genuinely dead tables is a manual operator action.

The same rule applies to a cardinality change. When a definition moves from `multi` to `single` the system SHALL NOT drop its child table or its rows, and SHALL exclude that retained table from projection, from the execution role's grants, and from the query-surface whitelist — the `subject` column becomes the definition's active representation. The system SHALL NOT create a child table for a definition whose current cardinality is `single`. Because reconciliation is tenant-wide, a child table can exist for a `single` definition only as a retention from an earlier `multi` period; the reconciler SHALL log such a table as retained and off the query surface, distinctly from an orphan, because a definition still claims it and the orphan report therefore never names it.

#### Scenario: Deactivation keeps the table and its rows

- **GIVEN** an active `multi` definition whose generated table holds rows
- **WHEN** the definition is deactivated and the reconciler runs
- **THEN** the table SHALL still exist
- **AND** its row count SHALL be unchanged
- **AND** no statement emitted SHALL be a `DROP`

#### Scenario: A deactivated definition leaves the query surface

- **GIVEN** a deactivated definition whose table exists
- **WHEN** the execution role's grants and the query whitelist are resolved
- **THEN** neither SHALL include that table

#### Scenario: Reactivation restores the surface over retained data

- **GIVEN** a definition deactivated while its table held rows
- **WHEN** it is reactivated and the reconciler runs
- **THEN** the table SHALL be included in grants and the whitelist again
- **AND** the previously retained rows SHALL still be present

#### Scenario: A cardinality flip to `single` retains the child table off the surface

- **GIVEN** an active `multi` definition whose child table holds rows
- **WHEN** its cardinality is changed to `single` and the reconciler runs
- **THEN** the child table SHALL still exist with its row count unchanged
- **AND** no statement emitted SHALL be a `DROP`
- **AND** the definition's `subject` column SHALL be added
- **AND** the child table SHALL be excluded from grants and from the whitelist

#### Scenario: A `single` definition is never given a child table

- **GIVEN** a definition whose cardinality is `single` and which has no existing child table
- **WHEN** the reconciler runs
- **THEN** no child table SHALL be created for it
- **AND** its `subject` column SHALL be the whole representation

#### Scenario: A retained table off the query surface is logged distinctly from an orphan

- **GIVEN** a child table retained because its definition became `single`
- **WHEN** the reconciler runs
- **THEN** the reconciler SHALL log it as retained and off the query surface
- **AND** it SHALL NOT be reported as an orphan, because a definition still claims it

#### Scenario: An orphaned table is logged, not dropped

- **GIVEN** a generated table whose definition no longer appears in the catalog
- **WHEN** the reconciler runs
- **THEN** the table SHALL remain
- **AND** the reconciler SHALL log its presence

## REMOVED Requirements

### Requirement: The subject view is dropped and recreated, never replaced in place

**Reason**: The requirement existed only because `CREATE OR REPLACE VIEW` cannot add, rename, or reorder columns. With `subject` as a physical table, a new `single` definition is added by `ALTER TABLE … ADD COLUMN IF NOT EXISTS`, which in PostgreSQL 11+ is metadata-only when no default is supplied. There is no drop, no `CASCADE`, and no window in which a reader observes a missing relation.

**Migration**: Replaced by the modified requirement "Each tenant gets a subject table with one column per single-valued entity". No data migration is required — nothing in the running system had called the view generator, so no `subject` view exists to convert.

### Requirement: Views for inactive or deleted definitions are dropped without touching rows

**Reason**: Dropping was safe only while the generated object held no rows. A generated table *is* the rows, and `is_active` is a reversible flag that `toggle_entity_type` flips in both directions, so dropping on deactivation would turn an undo into data loss.

**Migration**: Replaced by the added requirement "Deactivation and orphaning never drop a generated relation". Inactive definitions are now excluded from projection, grants, and the whitelist while their tables are retained.
