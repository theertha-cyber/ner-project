## ADDED Requirements

### Requirement: The generated relational surface is the canonical query model

The SQL generator SHALL generate SQL against the tenant's generated relational tables — `subject` and the active `e_<slug>` child tables — as its single query model. The generation prompt SHALL NOT instruct the model to query `document_entities`, to filter on `entity_type`, to self-join entity rows to assemble a subject, or to reason about one fact per row. No routing decision SHALL be made between an EAV query model and a relational one: there is one model.

`document_entities` SHALL remain readable by the execution role and accepted by the validation layer so that pre-existing static-table questions continue to work and so the grounding and defect probes can read it, but it SHALL NOT be presented to the generator as the query model.

#### Scenario: The prompt presents the relational surface, not the EAV table

- **GIVEN** a tenant with an active `multi` definition `Skill` (`e_skill`) and an active `single` definition `Email`
- **WHEN** the SQL-generation prompt is constructed
- **THEN** the prompt SHALL describe `subject` and `e_skill` as the tables to query
- **AND** the prompt SHALL NOT instruct the model to select from `document_entities`
- **AND** the prompt SHALL NOT instruct the model to filter on `entity_type`

#### Scenario: A single-valued entity is answered from a subject column

- **GIVEN** an active `single` definition whose `subject` column is `email`
- **WHEN** the model is asked for the tenant's email addresses
- **THEN** the generated statement SHALL read the `email` column of `subject`
- **AND** the statement SHALL pass validation

#### Scenario: A multi-valued entity is answered from its child table

- **GIVEN** an active `multi` definition whose child table is `e_skill`
- **WHEN** the model is asked which subjects have a given skill
- **THEN** the generated statement SHALL read `e_skill`
- **AND** the statement SHALL join `subject` on `document_id` when it needs the subject's filename or a single-valued fact

### Requirement: One resolver supplies the tenant's relational surface to the generator

The tenant's readable relational surface SHALL be resolved once per question from `entity_definitions`, by the same resolver that produces the execution role's `SELECT` grants and the validation layer's table whitelist. The resolved surface SHALL carry, for each relation, its columns and their declared SQL types, and it SHALL be passed into SQL generation. Generated relations SHALL NOT be hard-coded in the generator, and no second table list SHALL be maintained.

The resolved surface SHALL be tenant-specific and SHALL reflect the catalog as it stands at question time: a definition added, removed, deactivated, reactivated, or moved between cardinalities changes the surface at the next question without a code change.

#### Scenario: The generator receives the tenant's own tables

- **GIVEN** two tenants whose catalogs define different entity types
- **WHEN** a question is asked in each tenant
- **THEN** each generation prompt SHALL contain only that tenant's generated relations
- **AND** neither prompt SHALL contain the other tenant's relations

#### Scenario: An inactive definition is not exposed to the generator

- **GIVEN** a definition that has been deactivated while its generated table is retained
- **WHEN** the surface is resolved
- **THEN** the prompt SHALL NOT list that table
- **AND** the validation layer SHALL reject a statement naming it
- **AND** the execution role SHALL NOT hold `SELECT` on it

#### Scenario: A child table retained from a multi era is not exposed to the generator

- **GIVEN** a definition whose cardinality is now `single` and whose child table was retained from when it was `multi`
- **WHEN** the surface is resolved
- **THEN** the prompt SHALL NOT list that table
- **AND** the prompt SHALL list the definition's `subject` column instead

#### Scenario: A definition added after the last question appears without a deployment

- **GIVEN** a tenant whose catalog gains a new active `multi` definition with an assigned `sql_identifier`
- **WHEN** the next question is asked
- **THEN** the newly generated table SHALL appear in the prompt, the whitelist, and the grants

#### Scenario: The prompt, the whitelist, and the grants agree

- **GIVEN** any tenant schema
- **WHEN** the set of relations named in the prompt, the set accepted by the validation layer, and the set granted to the execution role are computed
- **THEN** all three SHALL be produced by the same resolver
- **AND** the three sets SHALL be equal for the generated relations

### Requirement: The generator is given the semantic meaning of each relation and column

Raw SQL identifiers SHALL NOT be the only description of the surface. For each generated relation and each `subject` entity column, the generation context SHALL carry the semantic metadata the tenant authored on the corresponding entity definition — at minimum its display name, and its description, examples, declared value kind, and value unit where present — so a natural-language concept can be mapped onto the relation or column that holds it.

The generation context SHALL additionally carry a bounded sample of the values that actually occur, drawn from the tenant's own data and keyed by the relation or column those values are projected into, not by the storage-level entity type. The sample SHALL be capped per relation or column, capped in total, and truncated per value, and SHALL be fetched once per invocation and reused across attempts. A relation or column that contributes no sample values SHALL still be listed.

#### Scenario: A definition's description reaches the prompt

- **GIVEN** an active definition named `Skill` whose description reads "a technology or professional capability"
- **WHEN** the generation prompt is constructed
- **THEN** the prompt SHALL associate `e_skill` with the name `Skill` and with that description

#### Scenario: A typed column advertises its kind

- **GIVEN** an active `single` definition with `value_kind` `number` projected as `subject.years_experience DOUBLE PRECISION`
- **WHEN** the generation prompt is constructed
- **THEN** the prompt SHALL declare that column's SQL type
- **AND** the prompt SHALL indicate that it holds a parsed numeric value

#### Scenario: Value samples are keyed by relation, not by entity type

- **GIVEN** a tenant whose stored `entity_type` values include `PER` mapped through `base_label_mapping` onto a definition projected as `subject.name`
- **WHEN** the value samples are assembled
- **THEN** the sampled values SHALL be listed under `subject.name`
- **AND** they SHALL NOT be listed under a bare `PER` entity type

#### Scenario: A relation with no sampled values is still listed

- **GIVEN** an active definition whose projected rows carry no usable sample values
- **WHEN** the generation prompt is constructed
- **THEN** its relation SHALL still appear in the listed surface

#### Scenario: Grounding is fetched once per invocation

- **GIVEN** an invocation that requires three attempts
- **WHEN** the loop completes
- **THEN** the surface-resolution and value-sample queries SHALL have been executed once, not once per attempt

### Requirement: Base-model tenants resolve to the same relational surface

A tenant whose extraction ran on the shared base model, whose stored `entity_type` values are CoNLL labels rather than the tenant's own entity names, SHALL be given the same relational surface as a tenant running a fine-tuned model. The association between a stored label and the relation or column it projects into SHALL be derived from the definition's `base_label_mapping` through the shared entity-type-literal helper, never from equality against the definition name.

#### Scenario: A base-label definition appears on the surface

- **GIVEN** an active `multi` definition named `Person` whose `base_label_mapping` maps `PER`
- **WHEN** the surface is resolved
- **THEN** its child table SHALL appear on the surface
- **AND** the prompt SHALL present it under the definition's own name

#### Scenario: Base-label values are sampled under the right relation

- **GIVEN** stored entities whose `entity_type` is `ORG`, belonging to a definition projected as `e_employer`
- **WHEN** the value samples are assembled
- **THEN** those values SHALL be listed under `e_employer`

### Requirement: Document-scoped questions stay document-scoped on the relational surface

When a question is scoped to a set of documents, the executed statement SHALL be constrained to those documents by a bound predicate applied to every scoped relation it references, including `subject` and every generated child table. The constraint SHALL be applied structurally to the validated statement rather than requested of the generating model in prose, and SHALL therefore survive aggregation, grouping, and the row limit.

If a document scope is supplied and the statement references no relation the scope can be applied to, the attempt SHALL NOT be treated as a successful tenant-wide answer. It SHALL be classified as a defect and retried, and SHALL be reported as a failure if no attempt can be scoped.

#### Scenario: A subject query is constrained to the scoped documents

- **GIVEN** a question resolved to a single document
- **AND** a generated statement selecting from `subject`
- **WHEN** the scope is applied
- **THEN** the executed statement SHALL restrict `subject` to the scoped `document_id` values through a bound parameter
- **AND** the scoped identifiers SHALL NOT appear as literals in the statement text

#### Scenario: A child-table query is constrained to the scoped documents

- **GIVEN** a question resolved to a set of documents
- **AND** a generated statement selecting from `e_skill` joined to `subject`
- **WHEN** the scope is applied
- **THEN** both relations SHALL be constrained by the bound predicate

#### Scenario: The scope survives aggregation over the relational surface

- **GIVEN** a document-scoped question producing an aggregate over `e_skill` with a `GROUP BY`
- **WHEN** the scope is applied
- **THEN** the predicate SHALL apply underneath the grouping
- **AND** the aggregate SHALL be computed only over the scoped documents

#### Scenario: The scope is applied before the row limit truncates

- **GIVEN** a document-scoped statement carrying a `LIMIT`
- **WHEN** the scope is applied
- **THEN** the predicate SHALL constrain the source rows
- **AND** the limit SHALL apply to in-scope rows only

#### Scenario: An unscopeable statement is not a silent tenant-wide answer

- **GIVEN** a document scope is supplied
- **AND** the generated statement references no relation the scope can be applied to
- **WHEN** the attempt completes
- **THEN** the attempt SHALL NOT be classified `success`
- **AND** the attempt SHALL be retried with feedback naming the problem

#### Scenario: The scope is reapplied to every attempt

- **GIVEN** a document-scoped question that requires two attempts
- **WHEN** the loop completes
- **THEN** every executed statement SHALL have carried the bound scope predicate

### Requirement: Invalid relational SQL is rejected before execution

The validation layer SHALL reject a statement that names a relation outside the resolved surface and the static whitelist, and SHALL reject a statement that names a column no resolved relation declares. A column reference the validation layer cannot attribute to a specific relation SHALL be accepted rather than rejected, so that a parser gap degrades into a database error rather than into a false rejection of a correct query. All existing validation rules — SELECT-only, no DDL or DML keywords, no `UNION`, no schema-qualified names, no function-call sources, no role switching, the length bound, and the enforced row limit — SHALL continue to apply unchanged.

#### Scenario: A relation not on the surface is rejected

- **GIVEN** a generated statement selecting from `e_unknown`
- **WHEN** the validation layer inspects it
- **THEN** the statement SHALL be rejected
- **AND** the statement SHALL NOT be executed

#### Scenario: A column no relation declares is rejected

- **GIVEN** a generated statement selecting `subject.salary` where `subject` declares no `salary` column
- **WHEN** the validation layer inspects it
- **THEN** the statement SHALL be rejected
- **AND** the rejection SHALL name the offending column

#### Scenario: A valid relational statement passes

- **GIVEN** a generated statement joining `e_skill` to `subject` on `document_id`, selecting declared columns, carrying a row limit
- **WHEN** the validation layer inspects it
- **THEN** the statement SHALL be accepted

#### Scenario: Another tenant's generated relation is rejected

- **GIVEN** a generated statement naming a table that exists only in another tenant's schema
- **WHEN** the validation layer inspects it against the querying tenant's resolved surface
- **THEN** the statement SHALL be rejected

### Requirement: Relational failures are detected and corrected without entity-type patterns

Defect detection SHALL NOT depend on the presence of `entity_type` comparisons in the generated SQL. A zero-row result SHALL be returned as a legitimate empty answer unless a deterministic defect proves the statement could not have matched, and the system SHALL NOT retry on row count alone.

The defect signals in force SHALL be decidable from the statement and the tenant's own metadata:

- a relation or column reference that is not on the resolved surface, detected before execution;
- a filter on a value that does exist in the tenant's data but is projected into a relation or column the statement did not query, reported in relational terms naming the relation or column that does hold it;
- a filter requiring a filename no document in the tenant carries;
- a supplied document scope that could not be applied to the statement.

Retry feedback SHALL name the relation and column at fault and SHALL direct the model to the relation or column that holds the value, and SHALL NOT instruct the model to re-issue the query against a different `entity_type`.

#### Scenario: A wrong relation is corrected on retry

- **GIVEN** the first generated statement reads a relation not on the surface
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified as a validation failure
- **AND** the retry prompt SHALL contain the rejected statement and the reason
- **AND** the retry prompt SHALL list the relations that are on the surface

#### Scenario: A value filed under a different relation is explained in relational terms

- **GIVEN** the first statement filters `e_skill.normalized_value = 'oracle'` and returns zero rows
- **AND** the value `oracle` occurs in the tenant's data under a definition projected as `e_employer`
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified as an empty result with a defect
- **AND** the retry feedback SHALL name `e_employer` as the relation that holds the value
- **AND** the retry feedback SHALL NOT reference `entity_type`

#### Scenario: An unexplained empty relational result is not retried

- **GIVEN** a statement that validates, executes without error, returns zero rows, and references only relations and columns on the surface
- **AND** no other defect signal fires
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified `success`
- **AND** an empty result SHALL be returned without error

#### Scenario: A database error on a relational statement is retried

- **GIVEN** a validated statement whose join predicate is wrong and raises at execution
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified as an execution failure
- **AND** the retry prompt SHALL contain the sanitized error and the previous statement

#### Scenario: A filename filter that matches no document is still detected

- **GIVEN** a statement requiring `subject.filename` to match a literal no document in the tenant carries
- **AND** the statement returns zero rows
- **WHEN** the attempt completes
- **THEN** the attempt SHALL be classified as an empty result with a defect
- **AND** the retry feedback SHALL state that no document carries that filename

### Requirement: A tenant whose relational surface is unpopulated reports the source as unavailable

Where a tenant's documents have entity data but have not been projected into the relational surface, a relational query returns zero rows for a reason unrelated to the question. Such a result SHALL NOT be reported as a legitimate empty answer.

Before answering, the system SHALL determine whether the relational surface holds data for the question's extent — the tenant, or the scoped documents when a document scope is supplied. If it does not, while `document_entities` does hold data for that extent, structured retrieval SHALL fail explicitly, so the turn reports the structured source as unavailable rather than asserting that nothing was found. No historical EAV-to-relational backfill SHALL be introduced: the supported migration path is re-extraction under a new model version, which reconciles the schema and repopulates the surface.

#### Scenario: An unprojected tenant does not get a confident empty answer

- **GIVEN** a tenant whose `document_entities` holds rows
- **AND** whose `subject` table holds none
- **WHEN** a structured question is asked
- **THEN** structured retrieval SHALL report a failure
- **AND** the turn SHALL report the structured source as unavailable
- **AND** the turn SHALL NOT report that no matching records exist

#### Scenario: An unprojected document under a document scope does not get a confident empty answer

- **GIVEN** a question scoped to a document that has entity rows but no `subject` row
- **WHEN** the question is asked
- **THEN** structured retrieval SHALL report a failure rather than an empty answer

#### Scenario: A populated surface answers normally

- **GIVEN** a tenant whose documents have been projected
- **WHEN** a structured question is asked and legitimately matches nothing
- **THEN** the empty result SHALL be returned as a successful, genuinely empty answer

#### Scenario: Re-extraction is the migration path

- **GIVEN** a tenant reported as unprojected
- **WHEN** a new model version is promoted and batch extraction is run over its documents
- **THEN** the tenant's schema SHALL be reconciled and its relational surface populated by the existing extraction flow
- **AND** subsequent questions SHALL be answered from the relational surface
