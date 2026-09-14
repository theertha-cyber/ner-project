## ADDED Requirements

### Requirement: Tenant-supplied names are slugged into safe SQL identifiers

`to_sql_identifier(name, taken)` SHALL convert an arbitrary tenant-supplied entity name into a Postgres identifier matching `^e_[a-z0-9][a-z0-9_]*$`, at most 63 characters, deterministic for the same `(name, taken)` input, and absent from `taken`. It SHALL lowercase, replace every non-alphanumeric character with `_`, collapse runs of `_`, strip leading and trailing `_`, prefix `e_`, truncate to 63 characters **before** appending any collision suffix, and never raise on degenerate input. A raw tenant-supplied name SHALL NOT be interpolated into any generated DDL.

#### Scenario: Punctuation and spacing are slugged

- **GIVEN** an entity definition named `"Skills & Tools"`
- **WHEN** `to_sql_identifier` is called with an empty `taken` set
- **THEN** it SHALL return `e_skills_tools`

#### Scenario: A reserved word is neutralized by the prefix

- **GIVEN** an entity definition named `"select"`
- **WHEN** `to_sql_identifier` is called
- **THEN** it SHALL return `e_select`
- **AND** the result SHALL be usable as a bare view name without quoting

#### Scenario: A name starting with a digit is still valid

- **GIVEN** an entity definition named `"2024 Revenue"`
- **WHEN** `to_sql_identifier` is called
- **THEN** the result SHALL match `^e_[a-z0-9][a-z0-9_]*$`

#### Scenario: An over-length name is truncated before suffixing

- **GIVEN** an entity definition whose name is 200 characters of `a`
- **AND** a `taken` set already containing the un-suffixed slug
- **WHEN** `to_sql_identifier` is called
- **THEN** the returned identifier SHALL be at most 63 characters
- **AND** it SHALL NOT be a member of `taken`

#### Scenario: Collisions resolve deterministically

- **GIVEN** two definitions named `"Vendor Name"` and `"vendor-name"`
- **WHEN** `to_sql_identifier` is called for each in order, accumulating results into `taken`
- **THEN** the two returned identifiers SHALL differ
- **AND** repeating the same sequence SHALL produce the same two identifiers

#### Scenario: Degenerate input yields a valid fallback

- **GIVEN** an entity definition named `""`, `"---"`, or a name of only non-Latin characters that slug to nothing
- **WHEN** `to_sql_identifier` is called
- **THEN** it SHALL return a valid identifier rather than raising
- **AND** the result SHALL match `^e_[a-z0-9][a-z0-9_]*$`

#### Scenario: An injection attempt produces an inert identifier

- **GIVEN** an entity definition named `"; DROP TABLE documents; --"`
- **WHEN** `to_sql_identifier` is called and the result is used to build view DDL
- **THEN** no generated statement SHALL contain `DROP TABLE`, `;`, or `--` outside a single-quoted literal
- **AND** the identifier SHALL match `^e_[a-z0-9][a-z0-9_]*$`

### Requirement: View DDL is produced by a pure function

`build_entity_view_statements(schema, definitions)` SHALL return a `list[str]` of DDL statements and SHALL NOT execute anything, open a connection, or require a database. The same inputs SHALL yield byte-identical output on every call. Every returned statement SHALL be safe to re-run against a schema where it has already been applied.

#### Scenario: The generator touches no database

- **GIVEN** a list of entity definition specs and a schema name
- **WHEN** `build_entity_view_statements` is called with no database configured or reachable
- **THEN** it SHALL return the statement list without error

#### Scenario: Generation is idempotent

- **GIVEN** the same schema and definition list
- **WHEN** `build_entity_view_statements` is called twice
- **THEN** the two returned lists SHALL be equal

#### Scenario: The schema name is validated

- **GIVEN** a schema argument that is not a bare SQL identifier
- **WHEN** `build_entity_view_statements` is called
- **THEN** it SHALL raise rather than emit the statement

### Requirement: Each active multi-valued entity gets a child view

For every definition with `is_active` true and `cardinality = 'multi'`, the generator SHALL emit a `CREATE OR REPLACE VIEW <schema>.<sql_identifier> WITH (security_barrier)` selecting `document_id`, `entity_value AS value`, `normalized_value`, `value_number`, `value_number_high`, `value_date`, `value_date_high`, `value_unit`, `confidence`, `page_number`, and `occurrence_count` from `<schema>.document_entities`, filtered to that entity's types. Child views SHALL use `CREATE OR REPLACE` because their column list is fixed by the generator and does not vary with the definition set.

#### Scenario: A multi definition produces its child view

- **GIVEN** an active definition with `name = 'SKILL'`, `sql_identifier = 'e_skill'`, `cardinality = 'multi'`
- **WHEN** statements are generated for schema `tenant_acme`
- **THEN** the output SHALL contain a `CREATE OR REPLACE VIEW tenant_acme.e_skill` statement
- **AND** that statement SHALL include `WITH (security_barrier)`
- **AND** it SHALL select from `tenant_acme.document_entities`

#### Scenario: Many multi definitions each get their own view

- **GIVEN** three active `multi` definitions with distinct `sql_identifier` values
- **WHEN** statements are generated
- **THEN** the output SHALL contain exactly three child-view `CREATE OR REPLACE VIEW` statements

### Requirement: Entity type matching is case-insensitive and covers base-model labels

The predicate in every generated view SHALL match `upper(entity_type)` against the uppercased definition `name` **and** against every key of that definition's `base_label_mapping`. Exact-case equality SHALL NOT be used, because no comparison anywhere in the extraction, normalization, or retrieval path assumes stored case equals definition case, and because on the base-model path `document_entities.entity_type` holds a CoNLL label rather than the tenant's name.

#### Scenario: Stored case differing from definition case still matches

- **GIVEN** a definition named `Skill` and rows stored with `entity_type = 'SKILL'`
- **WHEN** the child view is generated and queried
- **THEN** the view SHALL return those rows

#### Scenario: A base-model label maps into the view

- **GIVEN** a definition named `Employer` with `base_label_mapping` containing the key `ORG`
- **WHEN** the child view is generated
- **THEN** the emitted predicate SHALL admit both `EMPLOYER` and `ORG`

#### Scenario: A definition without a base label mapping matches on name alone

- **GIVEN** a definition whose `base_label_mapping` is NULL or empty
- **WHEN** the child view is generated
- **THEN** the emitted predicate SHALL admit only the uppercased definition name

### Requirement: Each tenant gets a subject view pivoting its single-valued entities

The generator SHALL emit exactly one `<schema>.subject` view per tenant schema. It SHALL select `d.id AS document_id` and `d.filename` from `<schema>.documents`, `LEFT JOIN` `<schema>.document_entities`, group by `d.id, d.filename`, and project one aggregated column per active `cardinality = 'single'` definition. The `LEFT JOIN` is mandatory: a document with zero extracted entities SHALL still yield a row, so counting documents and filtering documents both work against the same view.

#### Scenario: A single definition becomes a subject column

- **GIVEN** an active definition with `sql_identifier = 'e_email'` and `cardinality = 'single'`
- **WHEN** the `subject` view is generated
- **THEN** the view SHALL project a column named `email`

#### Scenario: Zero single definitions still yields a valid view

- **GIVEN** a definition list containing no active `single` definitions
- **WHEN** the `subject` view is generated
- **THEN** the statement SHALL still be valid SQL projecting `document_id` and `filename`

#### Scenario: A document with no entities still appears

- **GIVEN** a document row with no matching `document_entities` rows
- **WHEN** `subject` is queried
- **THEN** it SHALL return one row for that document with NULL entity columns

#### Scenario: A pivot column name colliding with an identity column is disambiguated

- **GIVEN** an active `single` definition whose `sql_identifier` is `e_filename` or `e_document_id`
- **WHEN** the `subject` view is generated
- **THEN** the projected column SHALL NOT duplicate `filename` or `document_id`
- **AND** the statement SHALL be valid SQL

#### Scenario: A typed single entity projects both typed and textual columns

- **GIVEN** an active `single` definition with `value_kind` of a non-text kind and `sql_identifier = 'e_years_experience'`
- **WHEN** the `subject` view is generated
- **THEN** it SHALL project the typed column as `years_experience`
- **AND** it SHALL project the surface text as `years_experience_text`

### Requirement: The subject view is dropped and recreated, never replaced in place

Because `CREATE OR REPLACE VIEW` cannot add, rename, or reorder columns, and because adding or removing a `single` definition changes `subject`'s column list, the generator SHALL always emit `DROP VIEW IF EXISTS <schema>.subject CASCADE` immediately followed by `CREATE VIEW <schema>.subject`. The pair SHALL be executed inside the caller's transaction so no reader observes a missing view.

#### Scenario: The drop precedes the create

- **GIVEN** any definition list
- **WHEN** statements are generated
- **THEN** the output SHALL contain `DROP VIEW IF EXISTS <schema>.subject CASCADE`
- **AND** the corresponding `CREATE VIEW <schema>.subject` SHALL appear after it

#### Scenario: Adding a single definition changes the column list cleanly

- **GIVEN** a schema where `subject` already exists with one pivot column
- **WHEN** a second `single` definition is added and the statements are re-applied
- **THEN** the statements SHALL succeed without a `cannot change name of view column` error
- **AND** `subject` SHALL project both pivot columns

#### Scenario: Re-applying an unchanged definition list is a no-op in effect

- **GIVEN** a schema whose views already match the definition list
- **WHEN** the statements are applied again
- **THEN** they SHALL succeed
- **AND** the resulting view definitions SHALL be unchanged

### Requirement: Views for inactive or deleted definitions are dropped without touching rows

The module SHALL provide a way to emit `DROP VIEW IF EXISTS <schema>.<sql_identifier>` for definitions that are inactive or no longer present. A generated drop SHALL only ever name a view and SHALL NOT emit `DROP TABLE`, `DELETE`, or `TRUNCATE`.

#### Scenario: An inactive definition gets no child view but does get a drop

- **GIVEN** a definition with `is_active` false and `cardinality = 'multi'`
- **WHEN** statements are generated
- **THEN** the output SHALL NOT contain a `CREATE OR REPLACE VIEW` for its identifier
- **AND** the output SHALL contain `DROP VIEW IF EXISTS` for its identifier

#### Scenario: Dropping a view leaves the underlying rows intact

- **GIVEN** a schema with a populated `document_entities` and an existing child view
- **WHEN** the drop statement for that view is executed
- **THEN** the view SHALL no longer exist
- **AND** the row count of `document_entities` SHALL be unchanged

### Requirement: The reconciler applies generated DDL idempotently per tenant schema

`reconcile_entity_views(session, schema, definitions)` SHALL execute the generated statements against `schema` and return the statements applied. It SHALL be safe to run repeatedly. It SHALL skip — without raising — any schema that does not contain a `document_entities` table, which is the older-template case migrations `029` and `035` guard the same way. It SHALL create the bare `subject` view for a tenant schema that has no definitions at all.

#### Scenario: A missing view is created

- **GIVEN** a tenant schema with `document_entities` but no entity views
- **WHEN** the reconciler runs with one active `multi` definition
- **THEN** the child view SHALL exist afterwards and be queryable

#### Scenario: A stale view is repaired

- **GIVEN** a tenant schema whose `subject` view predates a newly added `single` definition
- **WHEN** the reconciler runs with the updated definition list
- **THEN** `subject` SHALL project the new pivot column

#### Scenario: An orphaned view is dropped

- **GIVEN** a tenant schema with a child view whose definition has since been deactivated
- **WHEN** the reconciler runs
- **THEN** that view SHALL no longer exist

#### Scenario: A schema without document_entities is skipped

- **GIVEN** a tenant schema provisioned from a template predating `document_entities`
- **WHEN** the reconciler runs against it
- **THEN** it SHALL return without raising
- **AND** it SHALL create no views in that schema

#### Scenario: A tenant with no definitions still gets subject

- **GIVEN** a tenant schema with `document_entities` and an empty definition list
- **WHEN** the reconciler runs
- **THEN** `<schema>.subject` SHALL exist and be queryable
- **AND** it SHALL project `document_id` and `filename`

#### Scenario: Running twice changes nothing the second time

- **GIVEN** a reconciled tenant schema
- **WHEN** the reconciler runs again with the same definitions
- **THEN** it SHALL succeed
- **AND** the set of views in the schema SHALL be identical
